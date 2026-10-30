#!/usr/bin/env python3
"""SDK windowing: the host-mediated protocol, its limits, the tmux, inline and refusing backends, and a
test extension that opens, resizes, selects, lists, retitles and closes extra windows."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "overlay/usr/local/lib/daemonarchy-visual"
sys.path.insert(0, str(LIB))

import daemonarchy_visual as sdk  # noqa: E402
from daemonarchy_visual import audio, caps as sdk_caps, input as sdk_input, plugin, timeline, windows  # noqa: E402

TMUX = os.environ.get("DAEMONARCHY_TEST_TMUX") or shutil.which("tmux")


class Tty:
    def __init__(self):
        self.parts = []

    def write(self, text):
        self.parts.append(text)

    def flush(self):
        pass

    def isatty(self):
        return True

    def getvalue(self):
        return "".join(self.parts)


class Fake(windows.Backend):
    """Records what the host asked a backend to do."""

    name = "fake"

    def __init__(self, fail=None):
        self.calls, self.fail, self.gone, self.sizes = [], fail, set(), {}

    def available(self):
        return True

    def open(self, window):
        self.calls.append(("open", window.wid, window.title, window.cols, window.rows))
        return self.fail

    def close(self, window):
        self.calls.append(("close", window.wid))

    def resize(self, window):
        self.calls.append(("resize", window.wid, window.cols, window.rows))

    def select(self, window):
        self.calls.append(("select", window.wid))

    def retitle(self, window):
        self.calls.append(("title", window.wid, window.title))

    def observe(self, ws):
        return {w.wid: (None if w.wid in self.gone else self.sizes.get(w.wid, (w.cols, w.rows))) for w in ws}, {}


def manager(**kw):
    backend = kw.pop("backend", None) or Fake()
    return windows.WindowManager(backend, **kw), backend


def events(m):
    return m.take_events()


class ManagerRules(unittest.TestCase):
    def test_open_grants_numbered_windows_and_reports_them(self):
        m, b = manager()
        m.handle([{"op": "open", "ref": 7, "title": "Scratch", "cols": 30, "rows": 8}])
        self.assertEqual(events(m), [{"e": "opened", "ref": 7, "w": 1, "cols": 30, "rows": 8}])
        self.assertEqual(b.calls, [("open", 1, "Scratch", 30, 8)])

    def test_the_window_capability_is_required(self):
        m, b = manager(allowed=False)
        for verb in windows.VERBS:
            m.handle([{"op": verb, "ref": 1, "w": 0, "cols": 30, "rows": 8, "title": "x"}])
        got = events(m)
        self.assertEqual({e["reason"] for e in got}, {"no-window-capability"})
        self.assertEqual(len(got), len(windows.VERBS))
        self.assertEqual(b.calls, [])

    def test_at_most_max_windows_per_run(self):
        m, _ = manager(max_windows=2)
        m.handle([{"op": "open", "ref": i, "title": "w", "cols": 20, "rows": 6} for i in range(3)])
        got = events(m)
        self.assertEqual([e["e"] for e in got], ["opened", "opened", "refused"])
        self.assertEqual(got[2]["reason"], "limit")
        m2, _ = manager(max_windows=99)
        self.assertEqual(m2.max_windows, windows.MAX_WINDOWS[1])
        m3, _ = manager(max_windows=0)
        self.assertEqual(m3.max_windows, windows.MAX_WINDOWS[0])

    def test_sizes_are_bounded_on_open_and_resize(self):
        m, b = manager()
        for cols, rows in ((19, 10), (201, 10), (30, 5), (30, 61), ("30", 10), (True, 10), (30.0, 10), (None, None)):
            m.handle([{"op": "open", "ref": 1, "title": "t", "cols": cols, "rows": rows}])
        self.assertEqual({e["reason"] for e in events(m)}, {"size"})
        self.assertEqual(b.calls, [])
        m.handle([{"op": "open", "ref": 2, "title": "t", "cols": 20, "rows": 6}])
        m.handle([{"op": "resize", "w": 1, "cols": 200, "rows": 60}, {"op": "resize", "w": 1, "cols": 300, "rows": 10}])
        got = events(m)
        self.assertEqual([e["e"] for e in got], ["opened", "resize", "refused"])
        self.assertEqual((m.windows[1].cols, m.windows[1].rows), (200, 60))

    def test_titles_are_reduced_to_short_printable_text(self):
        for raw, expected in (("Hello", "Hello"), ("a'b\"c;d`e$f\\g#h", "abcdefgh"), ("x" * 100, "x" * 40),
                              ("", "window"), ("\x1b[31mred\x07", "[31mred"), (None, "None")):
            self.assertEqual(windows.clean_title(raw), expected)
        m, b = manager()
        m.handle([{"op": "open", "ref": 1, "title": "$(reboot); `x`", "cols": 20, "rows": 6}])
        self.assertEqual(b.calls[0][2], "(reboot) x")

    def test_an_extension_can_only_address_its_own_windows(self):
        m, b = manager()
        m.handle([{"op": "open", "ref": 1, "title": "mine", "cols": 20, "rows": 6}])
        events(m)
        b.calls.clear()
        attempts = [{"op": verb, "w": target, "cols": 30, "rows": 8, "title": "x"}
                    for verb in ("close", "resize", "select", "title") for target in (5, -1, "1", None, 1.0, True)]
        m.handle(attempts[:8])
        m.handle(attempts[8:16])
        m.handle(attempts[16:])
        refused = [e for e in events(m) if e["e"] == "refused"]
        self.assertGreaterEqual(len(refused), 20)
        self.assertTrue(all(e["reason"] in ("not-yours", "rate") for e in refused))
        self.assertEqual(b.calls, [])                     # nothing reached the backend
        m.handle([{"op": "close", "w": 0}])               # window 0 is the run itself: it cannot be closed
        self.assertEqual(events(m)[0]["reason"], "not-yours")

    def test_select_title_and_list_cover_the_run_window_too(self):
        m, b = manager()
        m.primary.update(cols=100, rows=30)
        m.handle([{"op": "open", "ref": 1, "title": "one", "cols": 20, "rows": 6}, {"op": "select", "w": 1},
                  {"op": "title", "w": 0, "title": "Main"}, {"op": "list", "ref": 9}])
        got = events(m)
        listing = got[-1]
        self.assertEqual(listing["e"], "list")
        self.assertEqual([(w["w"], w["title"], w["selected"]) for w in listing["windows"]],
                         [(0, "Main", False), (1, "one", True)])
        self.assertEqual(listing["windows"][0]["cols"], 100)
        m.handle([{"op": "select", "w": 0}])
        self.assertEqual(events(m), [{"e": "selected", "w": 0}])
        self.assertIn(("select", 1), b.calls)

    def test_at_most_eight_operations_a_tick(self):
        m, _ = manager()
        m.handle([{"op": "list", "ref": i} for i in range(12)])
        got = events(m)
        self.assertEqual(sum(1 for e in got if e["e"] == "list"), 8)
        self.assertEqual(sum(1 for e in got if e.get("reason") == "rate"), 4)

    def test_garbage_requests_are_refused_not_raised(self):
        m, _ = manager()
        m.handle([None, 5, "open", {}, {"op": "format"}, {"op": "open"}, {"op": "open", "cols": 20, "rows": 6, "ref": "x"}])
        m.handle("not a list")
        self.assertTrue(all(e["e"] in ("refused", "opened") for e in events(m)))

    def test_a_backend_refusal_is_reported_with_its_reason(self):
        m, _ = manager(backend=Fake(fail="tmux-refused"))
        m.handle([{"op": "open", "ref": 3, "title": "x", "cols": 20, "rows": 6}])
        self.assertEqual(events(m), [{"e": "refused", "op": "open", "ref": 3, "reason": "tmux-refused"}])
        self.assertEqual(m.windows, {})

    def test_closing_reports_who_closed_and_everything_closes_with_the_run(self):
        m, b = manager()
        m.handle([{"op": "open", "ref": 1, "title": "a", "cols": 20, "rows": 6}, {"op": "open", "ref": 2, "title": "b", "cols": 20, "rows": 6},
                  {"op": "select", "w": 2}])
        events(m)
        m.handle([{"op": "close", "w": 2}])
        self.assertEqual(events(m), [{"e": "closed", "w": 2, "by": "extension"}])
        self.assertEqual(m.selected, 0)
        m.close_all()
        self.assertEqual(events(m), [{"e": "closed", "w": 1, "by": "host"}])
        self.assertEqual(m.windows, {})

    def test_the_user_closing_or_resizing_a_window_is_reported(self):
        b = Fake()
        b.name = "tmux"          # the manager trusts observation only for backends that have real windows
        m, _ = manager(backend=b)
        m.handle([{"op": "open", "ref": 1, "title": "a", "cols": 30, "rows": 8}, {"op": "open", "ref": 2, "title": "b", "cols": 30, "rows": 8}])
        events(m)
        m.poll()                                           # seen at the requested size: settled
        self.assertEqual(events(m), [])
        b.sizes[1] = (50, 12)
        b.gone.add(2)
        m.poll()
        self.assertEqual(events(m), [{"e": "resize", "w": 1, "cols": 50, "rows": 12}, {"e": "closed", "w": 2, "by": "user"}])
        self.assertEqual(sorted(m.windows), [1])

    def test_startup_size_noise_is_not_reported_as_a_resize(self):
        b = Fake()
        b.name = "tmux"
        m, _ = manager(backend=b)
        m.handle([{"op": "open", "ref": 1, "title": "a", "cols": 30, "rows": 8}])
        events(m)
        b.sizes[1] = (120, 40)                              # tmux has not applied the request yet
        m.poll()
        self.assertEqual(events(m), [])
        b.sizes[1] = (30, 8)
        m.poll()
        b.sizes[1] = (31, 8)                                # now a real change
        m.poll()
        self.assertEqual(events(m), [{"e": "resize", "w": 1, "cols": 31, "rows": 8}])

    def test_a_request_tmux_will_not_honour_is_reported_after_the_settle_time(self):
        b = Fake()
        b.name = "tmux"
        m, _ = manager(backend=b)
        m.handle([{"op": "open", "ref": 1, "title": "a", "cols": 30, "rows": 8}])
        events(m)
        b.sizes[1] = (120, 40)
        m.windows[1].since -= windows.SETTLE_SECONDS + 1
        m.poll()
        self.assertEqual(events(m), [{"e": "resize", "w": 1, "cols": 120, "rows": 40}])

    def test_unknown_verbs_list_is_exactly_the_agreed_six(self):
        self.assertEqual(windows.VERBS, ("open", "close", "resize", "select", "list", "title"))


class BackendsWithoutTmux(unittest.TestCase):
    def test_no_windows_refuses_explicitly(self):
        m, _ = manager(backend=windows.NoWindows())
        m.handle([{"op": "open", "ref": 1, "title": "x", "cols": 20, "rows": 6}])
        self.assertEqual(events(m), [{"e": "refused", "op": "open", "ref": 1, "reason": "no-windows"}])

    def test_backend_choice_follows_the_terminal(self):
        plain = sdk_caps.Capabilities(plain=True, depth="none")
        rich = sdk_caps.Capabilities(depth="256")
        self.assertIsInstance(windows.choose_backend(plain, {"TMUX": "/x,1,0"}), windows.NoWindows)
        self.assertIsInstance(windows.choose_backend(rich, {}), windows.InlineBackend)
        self.assertIsInstance(windows.choose_backend(rich, {"TMUX": "/nonexistent,1,0"}, tmux="/nonexistent/tmux"),
                              windows.InlineBackend)

    def test_inline_panels_stack_clip_and_the_selected_one_is_in_front(self):
        backend = windows.InlineBackend()
        m, _ = manager(backend=backend)
        m.handle([{"op": "open", "ref": 1, "title": "A", "cols": 20, "rows": 6}, {"op": "open", "ref": 2, "title": "B", "cols": 20, "rows": 6}])
        for w in m.windows.values():
            w.frame = [[(0, f"win {w.title}", (None, None, False))]]
        canvas = sdk.Canvas(60, 20)
        backend.compose(canvas, m.windows.values())
        text = "\n".join(canvas.plain())
        self.assertIn("win B", text)                      # B is in front and covers A's text
        self.assertNotIn("win A", text)
        self.assertIn(" A ", text)                         # but A's title bar still shows
        self.assertEqual(backend.order, [1, 2])
        m.handle([{"op": "select", "w": 1}])
        self.assertEqual(backend.order, [2, 1])
        canvas = sdk.Canvas(60, 20)
        backend.compose(canvas, m.windows.values())
        self.assertIn("win A", "\n".join(canvas.plain()))   # selecting A brings it to the front
        tiny = sdk.Canvas(12, 6)
        backend.compose(tiny, m.windows.values())           # larger than the terminal: clipped, no error
        m.handle([{"op": "close", "w": 1}])
        self.assertEqual(backend.order, [2])


# ---------------------------------------------------------------- the test extension

WINDOW_EXT = '''
from daemonarchy_visual import Scene

class S(Scene):
    title = "windowed"

    def start(self, ctx):
        self.n, self.log, self.wid = 0, [], None

    def on_window_event(self, e):
        self.log.append(e["e"] + (":" + e["reason"] if e.get("reason") else "") + (":by-" + e["by"] if e.get("by") else ""))
        if e["e"] == "opened":
            self.wid = e["w"]

    def window_actions(self, wid, actions):
        self.log.append("keys:%d:%s" % (wid, ",".join(actions)))

    def update(self, dt, ctx, actions):
        self.n += 1
        w = ctx.windows
        if self.n == 2: w.open("Scratch", 30, 8)
        if self.n == 5 and self.wid: w.resize(self.wid, 40, 10)
        if self.n == 7 and self.wid: w.set_title(self.wid, "Renamed")
        if self.n == 8 and self.wid: w.select(self.wid)
        if self.n == 9: w.list()
        if self.n == 11 and self.wid: w.select(0)
        if self.n == 12 and self.wid: w.close(self.wid)
        if self.n == 13: w.close(99)
        if self.n >= 18:
            self.done, self.result = True, ",".join(self.log)

    def draw(self, canvas, ctx):
        canvas.put(0, 0, "main n=%d" % self.n)

    def draw_window(self, wid, canvas, ctx):
        canvas.put(0, 0, "hello from window %d" % wid)

def create(api):
    return S()
'''


def make(root, pid, source, caps=("draw", "input", "window"), limits=None):
    d = Path(root) / pid
    d.mkdir(parents=True, exist_ok=True)
    (d / "game.py").write_text(source)
    manifest = dict(schema=plugin.SCHEMA, id=pid, name=pid.title(), version="1.0.0", kind="game", api="1.3", entry="game.py",
                    entry_sha256="0" * 64, capabilities=list(caps), limits=limits or {})
    (d / "manifest.json").write_text(json.dumps(manifest))
    plugin.seal_manifest(str(d))
    plugin.write_index(str(root))


def run(root, pid, backend, polls=30, **kw):
    p = plugin.Registry(str(root)).plugins[pid]
    out = Tty()
    result = plugin.run_plugin(p, sdk_caps.Capabilities(depth="256", width=100, height=30), out,
                               sdk_input.ListSource([[]] * polls), audio.RecordingAudio(),
                               clock=timeline.ManualClock(), backend=backend, **kw)
    return result, out.getvalue()


class TestExtension(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_it_opens_resizes_selects_lists_retitles_and_closes_inline(self):
        make(self.root, "winext", WINDOW_EXT)
        result, text = run(self.root, "winext", windows.InlineBackend())
        self.assertEqual(result.reason, "done")
        log = result.result.split(",")
        self.assertEqual([e.split(":")[0] for e in log if not e.startswith("keys")],
                         ["opened", "resize", "selected", "list", "selected", "closed", "refused"])
        self.assertIn("refused:not-yours", log)
        self.assertIn("closed:by-extension", log)
        plain = text.replace("\x1b", "")
        self.assertIn("hello from window 1", "".join(c for c in plain if c.isprintable()) or "")

    def test_without_the_window_capability_every_request_is_refused(self):
        make(self.root, "winext", WINDOW_EXT, caps=("draw", "input"))
        result, _ = run(self.root, "winext", windows.InlineBackend())
        log = result.result.split(",")
        self.assertIn("refused:no-window-capability", log)
        self.assertNotIn("opened", [e.split(":")[0] for e in log])

    def test_the_manifest_limit_caps_the_windows(self):
        src = WINDOW_EXT.replace('if self.n == 2: w.open("Scratch", 30, 8)',
                                 'if self.n in (2, 3, 4): w.open("W%d" % self.n, 30, 8)')
        make(self.root, "winext", src, limits={"windows": 2})
        result, _ = run(self.root, "winext", windows.InlineBackend())
        log = result.result.split(",")
        self.assertEqual(log.count("opened"), 2)
        self.assertIn("refused:limit", log)

    def test_serial_and_headless_refuse_explicitly(self):
        make(self.root, "winext", WINDOW_EXT)
        result, _ = run(self.root, "winext", windows.NoWindows())
        self.assertIn("refused:no-windows", result.result.split(","))

    def test_the_extension_process_cannot_reach_tmux_itself(self):
        src = WINDOW_EXT.replace("self.n += 1", "self.n += 1; import subprocess; subprocess.run(['tmux', 'list-windows'])")
        make(self.root, "winext", src)
        result, _ = run(self.root, "winext", windows.InlineBackend())
        self.assertIn("failed", str(result.result))


# ---------------------------------------------------------------- real tmux

@unittest.skipUnless(TMUX, "tmux is not installed")
class RealTmux(unittest.TestCase):
    def setUp(self):
        self.socket = f"daemonarchy-wintest-{os.getpid()}-{int(time.time() * 1000) % 100000}"
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.tmux("-f", "/dev/null", "new-session", "-d", "-s", "inst", "-n", "installer", "-x", "120", "-y", "40", "sleep 600")
        self.backend = windows.TmuxBackend(TMUX, socket_name=self.socket, session="inst")

    def tearDown(self):
        subprocess.run([TMUX, "-L", self.socket, "kill-server"], capture_output=True)
        self.tmp.cleanup()

    def tmux(self, *args):
        return subprocess.run([TMUX, "-L", self.socket, *args], capture_output=True, text=True, timeout=10)

    def names(self):
        return sorted(self.tmux("list-windows", "-t", "inst:", "-F", "#{window_name}").stdout.split())

    def test_open_resize_title_select_close_use_only_tmux_window_operations(self):
        self.assertTrue(self.backend.available())
        m = windows.WindowManager(self.backend, max_windows=2)
        m.handle([{"op": "open", "ref": 1, "title": "Scratch", "cols": 50, "rows": 12}])
        self.assertEqual(events(m)[0]["e"], "opened", "the viewer connected")
        self.assertEqual(self.names(), ["Scratch", "installer"])
        handle = m.windows[1].handle
        self.assertRegex(handle, r"^@\d+$")
        m.handle([{"op": "resize", "w": 1, "cols": 60, "rows": 14}, {"op": "title", "w": 1, "title": "Renamed"}])
        size = self.tmux("display-message", "-p", "-t", handle, "#{window_width}x#{window_height}").stdout.strip()
        self.assertEqual(size, "60x14")
        self.assertEqual(self.names(), ["Renamed", "installer"])
        m.handle([{"op": "select", "w": 1}])
        self.assertEqual(self.tmux("display-message", "-p", "-t", "inst:", "#{window_name}").stdout.strip(), "Renamed")
        m.handle([{"op": "select", "w": 0}])                                  # the run's own window: no tmux call needed
        m.handle([{"op": "close", "w": 1}])
        self.assertEqual(self.names(), ["installer"])
        self.assertEqual(self.backend.created, set())

    def test_the_installers_own_windows_are_never_touched(self):
        self.tmux("new-window", "-d", "-n", "progress", "sleep 600")
        before = self.tmux("list-windows", "-t", "inst:", "-F", "#{window_id} #{window_name}").stdout
        m = windows.WindowManager(self.backend, max_windows=3)
        m.handle([{"op": "open", "ref": 1, "title": "x", "cols": 30, "rows": 8}])
        events(m)
        for wid in (0, 2, 3, 99):
            m.handle([{"op": "close", "w": wid}, {"op": "resize", "w": wid, "cols": 30, "rows": 8},
                      {"op": "title", "w": wid, "title": "pwned"}])
        m.close_all()
        after = self.tmux("list-windows", "-t", "inst:", "-F", "#{window_id} #{window_name}").stdout
        self.assertEqual(before, after)

    def test_frames_reach_the_viewer_and_the_user_closing_the_window_is_reported(self):
        m = windows.WindowManager(self.backend, max_windows=1)
        m.handle([{"op": "open", "ref": 1, "title": "view", "cols": 40, "rows": 8}])
        events(m)
        window = m.windows[1]
        window.frame = [[(0, "VIEWER-OK", ((255, 0, 0), None, True))]]
        self.backend.send_frame(window)
        deadline, seen = time.monotonic() + 8, ""
        while time.monotonic() < deadline and "VIEWER-OK" not in seen:
            time.sleep(0.2)
            seen = self.tmux("capture-pane", "-p", "-t", window.handle).stdout
        self.assertIn("VIEWER-OK", seen)
        self.tmux("send-keys", "-t", window.handle, "a")                    # input from the window reaches the host
        got = {}
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not got:
            got = m.poll()
            time.sleep(0.1)
        self.assertEqual(got, {1: ["left"]})
        self.tmux("kill-window", "-t", window.handle)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and m.windows:
            m.poll()
            time.sleep(0.1)
        self.assertEqual([e for e in events(m) if e["e"] == "closed"], [{"e": "closed", "w": 1, "by": "user"}])

    def test_the_test_extension_runs_end_to_end_on_tmux_and_leaves_no_window_behind(self):
        make(self.root, "winext", WINDOW_EXT)
        result, _ = run(self.root, "winext", self.backend)
        log = result.result.split(",")
        self.assertEqual([e.split(":")[0] for e in log if not e.startswith("keys")],
                         ["opened", "resize", "selected", "list", "selected", "closed", "refused"])
        self.assertEqual(self.names(), ["installer"])


if __name__ == "__main__":
    unittest.main()
