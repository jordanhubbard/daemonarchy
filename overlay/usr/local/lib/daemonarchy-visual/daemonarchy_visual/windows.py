"""Windows for extensions: open, close, resize, select, list and title, mediated by the host.

An extension (a plugin running in its own process) never talks to tmux or the terminal. It asks the
host for windows through a small protocol; the host performs the operations, enforces the limits and
reports back with events. Verbs: open, close, resize, select, list, title. Events: opened, refused,
closed, resize, selected, list.

Backends do the work for a given terminal:

  TmuxBackend    each window is a tmux window running a viewer process (window_view.py) that the host
                 feeds frames over a private unix socket. tmux-compatible: new-window, resize-window,
                 select-window, rename-window, kill-window and list-windows only, and only on window
                 ids this host created. The installer's own windows are never addressed.
  InlineBackend  no tmux: windows are framed panels composited inside the one terminal, with a
                 z-order (select brings one to the front). A real degradation, shown as such.
  NoWindows      serial, plain or headless: every open is refused with the reason "no-windows".

Limits the host enforces regardless of the extension: the `window` capability, a maximum number of
windows per run (1-4), size bounds, titles reduced to short printable text, at most 8 operations per
tick, and ownership: an extension can address only windows it opened (and window 0, the run's own
window, for select, list and title; it cannot be closed or resized, because it is the terminal).
"""

import json
import os
import re
import select
import shlex
import socket
import subprocess
import sys
import tempfile
import time

from .canvas import Canvas
from .palette import CYAN, DIM, GRAY, WHITE

VIEWER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "window_view.py")
COLS, ROWS, MAX_WINDOWS, OPS_PER_TICK, TITLE = (20, 200), (6, 60), (1, 4), 8, 40
SETTLE_SECONDS = 3.0
TMUX_ID = re.compile(r"^@\d{1,9}$")
VERBS = ("open", "close", "resize", "select", "list", "title")


def clean_title(text):
    text = "".join(c for c in str(text) if c.isprintable() and c not in "#'\"\\`$;")
    return text.strip()[:TITLE] or "window"


def bounded(value, bounds):
    return isinstance(value, int) and not isinstance(value, bool) and bounds[0] <= value <= bounds[1]


class Window:
    def __init__(self, wid, title, cols, rows):
        self.wid, self.title, self.cols, self.rows = wid, title, cols, rows
        self.handle = None     # backend identifier (a tmux window id)
        self.frame = None      # decoded rows: [[(x, text, style)]]
        self.conn = None       # socket to the viewer
        self.inbox = b""
        self.gone = False
        self.settled = False   # has the window been seen at its requested size? Until then, differences are startup noise
        self.since = time.monotonic()


class Backend:
    name = "none"
    can_spawn = False

    def available(self):
        return False

    def open(self, window):
        return "unsupported"

    def close(self, window):
        pass

    def resize(self, window):
        pass

    def select(self, window):
        pass

    def retitle(self, window):
        pass

    def observe(self, windows):
        """Return {wid: (cols, rows) or None if the window no longer exists}, plus input actions."""
        return {}, {}

    def send_frame(self, window):
        pass

    def spawn(self, title, argv):
        return None

    def shutdown(self):
        pass


class NoWindows(Backend):
    name = "none"

    def open(self, window):
        return "no-windows"


class InlineBackend(Backend):
    """Panels inside the one terminal. The host composites them; there is nothing to launch."""

    name = "inline"

    def __init__(self):
        self.order = []

    def available(self):
        return True

    def open(self, window):
        self.order.append(window.wid)
        return None

    def close(self, window):
        self.order = [w for w in self.order if w != window.wid]

    def select(self, window):
        self.close(window)
        self.order.append(window.wid)

    def observe(self, windows):
        return {w.wid: (w.cols, w.rows) for w in windows}, {}

    def compose(self, canvas, windows, ctx_style=(WHITE, None, False)):
        """Draw the windows over `canvas`, rearmost first; the selected (last) window has the bright frame."""
        by_id = {w.wid: w for w in windows}
        for rank, wid in enumerate(self.order):
            w = by_id.get(wid)
            if w is None:
                continue
            cols, rows = min(w.cols, max(1, canvas.width - 2)), min(w.rows, max(1, canvas.height - 3))
            x, y = min(2 + 3 * rank, max(0, canvas.width - cols - 2)), min(1 + rank, max(0, canvas.height - rows - 3))
            front = rank == len(self.order) - 1
            frame = (CYAN, None, True) if front else (DIM, None, False)
            canvas.fill(x, y, cols + 2, rows + 2, " ", None)
            canvas.put(x, y, "┌" + "─" * cols + "┐", frame)
            for row in range(rows):
                canvas.put(x, y + 1 + row, "│", frame)
                canvas.put(x + cols + 1, y + 1 + row, "│", frame)
            canvas.put(x, y + rows + 1, "└" + "─" * cols + "┘", frame)
            canvas.put(x + 2, y, f" {w.title} "[:cols - 2], (WHITE if front else GRAY, None, True))
            for ry, row in enumerate(w.frame or []):
                if ry >= rows:
                    break
                for fx, text, style in row:
                    if fx < cols:
                        canvas.put(x + 1 + fx, y + 1 + ry, text, style, width=cols - fx)


class TmuxBackend(Backend):
    """tmux windows running viewers. Only window ids this backend created are ever addressed."""

    name = "tmux"
    can_spawn = True

    def __init__(self, tmux="tmux", socket_name=None, session=None, clock=time.monotonic):
        self.tmux, self.socket_name, self.session = tmux, socket_name, session
        self.dir = None
        self.listeners = {}
        self.created = set()

    def _run(self, *args, timeout=3):
        argv = [self.tmux] + (["-L", self.socket_name] if self.socket_name else []) + list(args)
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
            return done.returncode, done.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return 1, ""

    def available(self):
        if not self.socket_name and not os.environ.get("TMUX"):
            return False
        return self._run("display-message", "-p", "#{session_id}")[0] == 0

    def _target(self):
        return [] if not self.session else ["-t", self.session + ":"]

    def _private_dir(self):
        if self.dir is None:
            self.dir = tempfile.mkdtemp(prefix="daemonarchy-windows.")
            os.chmod(self.dir, 0o700)
        return self.dir

    def open(self, window):
        path = os.path.join(self._private_dir(), f"w{window.wid}.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(path)
        listener.listen(1)
        listener.settimeout(4.0)
        command = shlex.join([sys.executable, "-I", VIEWER, path, str(window.wid)])
        code, out = self._run("new-window", "-d", "-P", "-F", "#{window_id}", *self._target(), "-n", window.title, command)
        if code != 0 or not TMUX_ID.match(out):
            listener.close()
            return "tmux-refused"
        window.handle = out
        self.created.add(out)
        try:
            window.conn, _ = listener.accept()
            window.conn.setblocking(False)
        except (OSError, socket.timeout):
            self.close(window)
            listener.close()
            return "viewer-did-not-start"
        listener.close()
        self.resize(window)
        return None

    def _owned(self, window):
        return bool(window.handle) and window.handle in self.created

    def resize(self, window):
        if self._owned(window):
            self._run("set-window-option", "-t", window.handle, "window-size", "manual")
            self._run("resize-window", "-t", window.handle, "-x", str(window.cols), "-y", str(window.rows))

    def select(self, window):
        if self._owned(window):
            self._run("select-window", "-t", window.handle)

    def retitle(self, window):
        if self._owned(window):
            self._run("rename-window", "-t", window.handle, window.title)

    def close(self, window):
        if self._owned(window):
            self._run("kill-window", "-t", window.handle)
            self.created.discard(window.handle)
        if window.conn is not None:
            try:
                window.conn.close()
            except OSError:
                pass
            window.conn = None

    def observe(self, windows):
        code, out = self._run("list-windows", *self._target(), "-F", "#{window_id} #{window_width} #{window_height}")
        sizes, actions = {}, {}
        if code == 0:
            live = {}
            for line in out.splitlines():
                parts = line.split()
                if len(parts) == 3 and TMUX_ID.match(parts[0]) and parts[1].isdigit() and parts[2].isdigit():
                    live[parts[0]] = (int(parts[1]), int(parts[2]))
            for w in windows:
                sizes[w.wid] = live.get(w.handle)
        for w in windows:
            for message in self._read(w):
                if message.get("e") == "actions" and isinstance(message.get("a"), list):
                    actions.setdefault(w.wid, []).extend(str(a) for a in message["a"][:16])
                elif message.get("e") == "size" and bounded(message.get("c"), (1, 1000)) and bounded(message.get("r"), (1, 1000)):
                    sizes[w.wid] = (message["c"], message["r"])
        return sizes, actions

    def _read(self, window):
        if window.conn is None:
            return []
        try:
            ready, _, _ = select.select([window.conn], [], [], 0)
            if ready:
                data = window.conn.recv(65536)
                if not data:
                    window.gone = True
                window.inbox += data
        except (OSError, ValueError):
            window.gone = True
        messages, window.inbox = [], window.inbox[-1 << 16:]
        while b"\n" in window.inbox:
            line, window.inbox = window.inbox.split(b"\n", 1)
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                messages.append(value)
        return messages

    def send_frame(self, window):
        if window.conn is None or window.frame is None:
            return
        rows = [[[x, text, [list(s[0]) if s and s[0] else None, list(s[1]) if s and s[1] else None, bool(s and s[2])]]
                 for x, text, s in row] for row in window.frame]
        try:
            window.conn.setblocking(True)
            window.conn.settimeout(0.5)
            window.conn.sendall((json.dumps({"rows": rows, "title": window.title}, separators=(",", ":")) + "\n").encode())
            window.conn.setblocking(False)
        except (OSError, socket.timeout):
            window.gone = True

    def spawn(self, title, argv):
        """Run `argv` in a new, selected tmux window (the run's own window). Returns its window id."""
        code, out = self._run("new-window", "-P", "-F", "#{window_id}", *self._target(), "-n", clean_title(title),
                              shlex.join(argv))
        if code == 0 and TMUX_ID.match(out):
            self.created.add(out)
            return out
        return None

    def shutdown(self):
        if self.dir:
            for name in os.listdir(self.dir):
                try:
                    os.unlink(os.path.join(self.dir, name))
                except OSError:
                    pass
            try:
                os.rmdir(self.dir)
            except OSError:
                pass
            self.dir = None


def choose_backend(caps, env=None, tmux="tmux"):
    """tmux when the terminal is inside it, the inline panels on any other full-screen terminal, else none."""
    env = os.environ if env is None else env
    if caps.plain:
        return NoWindows()
    if env.get("TMUX"):
        backend = TmuxBackend(tmux)
        if backend.available():
            return backend
    return InlineBackend()


class WindowManager:
    """Everything an extension may ask of windows, checked and performed on its behalf."""

    def __init__(self, backend, allowed=True, max_windows=2):
        self.backend, self.allowed = backend, allowed
        self.max_windows = max(MAX_WINDOWS[0], min(MAX_WINDOWS[1], max_windows))
        self.windows = {}
        self.selected = 0
        self.next_id = 1
        self.events = []
        self.primary = dict(title="", cols=0, rows=0)
        self.dropped = 0

    # -- the extension's requests

    def refuse(self, ref, op, reason):
        self.events.append({"e": "refused", "op": op, "ref": ref, "reason": reason})

    def handle(self, ops):
        for index, op in enumerate(ops if isinstance(ops, list) else []):
            if index >= OPS_PER_TICK:
                self.dropped += 1
                self.refuse(op.get("ref") if isinstance(op, dict) else None, "rate", "rate")
                continue
            if not isinstance(op, dict) or op.get("op") not in VERBS:
                self.refuse(None, "unknown", "bad-request")
                continue
            verb, ref = op["op"], op.get("ref") if isinstance(op.get("ref"), int) else None
            if not self.allowed:
                self.refuse(ref, verb, "no-window-capability")
                continue
            getattr(self, "do_" + verb)(op, ref)

    def owned(self, op):
        wid = op.get("w")
        return wid if isinstance(wid, int) and not isinstance(wid, bool) and wid in self.windows else None

    def do_open(self, op, ref):
        cols, rows = op.get("cols"), op.get("rows")
        if len(self.windows) >= self.max_windows:
            return self.refuse(ref, "open", "limit")
        if not bounded(cols, COLS) or not bounded(rows, ROWS):
            return self.refuse(ref, "open", "size")
        window = Window(self.next_id, clean_title(op.get("title", "window")), cols, rows)
        reason = self.backend.open(window)
        if reason:
            return self.refuse(ref, "open", reason)
        self.next_id += 1
        self.windows[window.wid] = window
        self.events.append({"e": "opened", "ref": ref, "w": window.wid, "cols": cols, "rows": rows})

    def do_close(self, op, ref):
        wid = self.owned(op)
        if wid is None:
            return self.refuse(ref, "close", "not-yours")
        self.drop(wid, "extension")

    def do_resize(self, op, ref):
        wid = self.owned(op)
        if wid is None:
            return self.refuse(ref, "resize", "not-yours")
        if not bounded(op.get("cols"), COLS) or not bounded(op.get("rows"), ROWS):
            return self.refuse(ref, "resize", "size")
        window = self.windows[wid]
        window.cols, window.rows = op["cols"], op["rows"]
        window.settled, window.since = False, time.monotonic()
        self.backend.resize(window)
        self.events.append({"e": "resize", "w": wid, "cols": window.cols, "rows": window.rows})

    def do_select(self, op, ref):
        wid = op.get("w")
        if wid == 0:
            self.selected = 0
            self.events.append({"e": "selected", "w": 0})
            return
        wid = self.owned(op)
        if wid is None:
            return self.refuse(ref, "select", "not-yours")
        self.selected = wid
        self.backend.select(self.windows[wid])
        self.events.append({"e": "selected", "w": wid})

    def do_title(self, op, ref):
        wid = op.get("w")
        title = clean_title(op.get("title", ""))
        if wid == 0:
            self.primary["title"] = title
            return
        wid = self.owned(op)
        if wid is None:
            return self.refuse(ref, "title", "not-yours")
        self.windows[wid].title = title
        self.backend.retitle(self.windows[wid])

    def do_list(self, op, ref):
        listing = [dict(w=0, title=self.primary["title"], cols=self.primary["cols"], rows=self.primary["rows"],
                        selected=self.selected == 0)]
        listing += [dict(w=w.wid, title=w.title, cols=w.cols, rows=w.rows, selected=self.selected == w.wid)
                    for w in self.windows.values()]
        self.events.append({"e": "list", "ref": ref, "windows": listing})

    def drop(self, wid, by):
        window = self.windows.pop(wid, None)
        if window is not None:
            self.backend.close(window)
            if self.selected == wid:
                self.selected = 0
            self.events.append({"e": "closed", "w": wid, "by": by})

    # -- the host's side of each tick

    def poll(self):
        """Notice windows the user closed or resized and gather input from them."""
        if not self.windows:
            return {}
        sizes, actions = self.backend.observe(list(self.windows.values()))
        for wid, window in list(self.windows.items()):
            observed = sizes.get(wid)
            if window.gone or observed is None and self.backend.name == "tmux":
                self.drop(wid, "user")
            elif observed and self.backend.name == "tmux":
                if (observed[0], observed[1]) == (window.cols, window.rows):
                    window.settled = True
                elif window.settled or time.monotonic() - window.since > SETTLE_SECONDS:
                    # The user (or tmux) changed the size, or tmux would not honour the request: report what is real.
                    window.cols, window.rows, window.settled = observed[0], observed[1], True
                    self.events.append({"e": "resize", "w": wid, "cols": window.cols, "rows": window.rows})
        return actions

    def set_frames(self, frames):
        for wid, rows in (frames or {}).items():
            window = self.windows.get(wid)
            if window is not None:
                window.frame = rows
                self.backend.send_frame(window)

    def take_events(self):
        events, self.events = self.events, []
        return events

    def sizes(self):
        return {w.wid: (w.cols, w.rows) for w in self.windows.values()}

    def close_all(self):
        for wid in list(self.windows):
            self.drop(wid, "host")
        self.backend.shutdown()


def blank_canvas(window):
    return Canvas(window.cols, window.rows)


class ExtensionWindows:
    """The extension's side: requests are queued and answered by events on a later tick.

    `open` and `list` return a reference number; the matching `opened`/`refused`/`list` event carries it.
    With the `window` capability absent every request is refused by the host; nothing here talks to a
    terminal or to tmux. The scene hooks `on_window_event(event)`, `window_actions(wid, actions)` and
    `draw_window(wid, canvas, ctx)` (all optional) receive what happens in the windows.
    """

    def __init__(self):
        self.ops, self.known, self.ref = [], {}, 0

    def _ask(self, **op):
        self.ops.append(op)

    def open(self, title, cols, rows):
        self.ref += 1
        self._ask(op="open", ref=self.ref, title=title, cols=cols, rows=rows)
        return self.ref

    def close(self, wid):
        self._ask(op="close", w=wid)

    def resize(self, wid, cols, rows):
        self._ask(op="resize", w=wid, cols=cols, rows=rows)

    def select(self, wid):
        self._ask(op="select", w=wid)

    def set_title(self, wid, title):
        self._ask(op="title", w=wid, title=title)

    def list(self):
        self.ref += 1
        self._ask(op="list", ref=self.ref)
        return self.ref

    def take_ops(self):
        ops, self.ops = self.ops[:2 * OPS_PER_TICK], []
        return ops

    def apply(self, event):
        kind = event.get("e")
        if kind == "opened":
            self.known[event["w"]] = (event["cols"], event["rows"])
        elif kind == "resize" and event.get("w") in self.known:
            self.known[event["w"]] = (event["cols"], event["rows"])
        elif kind == "closed":
            self.known.pop(event.get("w"), None)
