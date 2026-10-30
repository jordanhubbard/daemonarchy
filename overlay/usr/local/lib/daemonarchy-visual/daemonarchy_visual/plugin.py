"""Plugins: content-identified, capability-scoped, preemptible and failure-isolated scenes.

A plugin is a directory with a `manifest.json` and one entry file. A `Registry` loads plugins
only from a trusted root and only when an `index.json` there names the exact SHA-256 of each
manifest, and each manifest names the exact SHA-256 of its entry file: nothing is imported
from an ambient path, and an unlisted or altered file is refused with a reason.

`run_plugin` runs the entry in a separate process (plugin_child.py) that draws to a virtual
canvas and reports frames over a pipe; the host process owns the terminal. A plugin that
crashes, hangs, overruns its frame budget, sends a malformed frame or exceeds its limits ends
as a failed RunResult; the host is never affected. A host preempts a plugin at any frame and
the process is killed. Capabilities (`draw`, `input`, `audio`) are enforced on both sides: a
plugin without `input` is sent no actions, one without `audio` has its cues dropped.
"""

import hashlib
import json
import os
import re
import select
import subprocess
import sys
import time

from . import compatible
from .canvas import Canvas
from .scene import Scene, run_scene
from .windows import WindowManager

SCHEMA = "daemonarchy/extension@1"
INDEX_SCHEMA = "daemonarchy/visual-plugin-index@1"
TYPES = ("game", "tool", "animation", "visualizer")
CAPABILITIES = ("draw", "input", "audio", "window")
ID = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
ENTRY = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}\.py$")
HEX = re.compile(r"^[0-9a-f]{64}$")
LIMIT_BOUNDS = dict(fps=(1, 30), memory_mb=(96, 512), cpu_seconds=(10, 3600), frame_ms=(20, 1000), windows=(1, 4))
DEFAULT_LIMITS = dict(fps=15, memory_mb=192, cpu_seconds=900, frame_ms=250, windows=2)
CHILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin_child.py")
MAX_REPLY = 1 << 20


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class Plugin:
    def __init__(self, directory, manifest):
        self.directory = directory
        self.id, self.name, self.version = manifest["id"], manifest["name"], manifest["version"]
        self.type, self.entry = manifest["type"], manifest["entry"]
        self.description = manifest.get("description", "")
        self.capabilities = tuple(manifest["capabilities"])
        self.limits = dict(DEFAULT_LIMITS, **manifest.get("limits", {}))
        self.min_size = tuple(manifest.get("min_size", (0, 0)))
        self.manifest = manifest

    def __repr__(self):
        return f"Plugin({self.id!r}, {self.version})"


def check_manifest(manifest):
    """Reasons a manifest is unacceptable (an empty list means acceptable)."""
    problems = []
    if not isinstance(manifest, dict):
        return ["manifest is not an object"]
    if manifest.get("schema") != SCHEMA:
        problems.append("wrong schema")
    if not isinstance(manifest.get("id"), str) or not ID.match(manifest["id"]):
        problems.append("bad id")
    for key in ("name", "version"):
        if not isinstance(manifest.get(key), str) or not 0 < len(manifest[key]) <= 64:
            problems.append(f"bad {key}")
    if manifest.get("type") not in TYPES:
        problems.append("bad type")
    if not isinstance(manifest.get("api"), str) or not compatible(manifest["api"]):
        problems.append(f"needs SDK API {manifest.get('api')!r}")
    if not isinstance(manifest.get("entry"), str) or not ENTRY.match(manifest["entry"]):
        problems.append("bad entry name")
    if not isinstance(manifest.get("entry_sha256"), str) or not HEX.match(manifest["entry_sha256"]):
        problems.append("bad entry_sha256")
    caps = manifest.get("capabilities")
    if not isinstance(caps, list) or not caps or any(c not in CAPABILITIES for c in caps) or "draw" not in caps:
        problems.append("capabilities must be a non-empty subset of draw, input, audio including draw")
    size = manifest.get("min_size", [0, 0])
    if (not isinstance(size, list) or len(size) != 2 or not all(isinstance(v, int) and not isinstance(v, bool) for v in size)
            or not (0 <= size[0] <= 200 and 0 <= size[1] <= 100)):
        problems.append("bad min_size")
    limits = manifest.get("limits", {})
    if not isinstance(limits, dict):
        problems.append("bad limits")
    else:
        for key, value in limits.items():
            low, high = LIMIT_BOUNDS.get(key, (None, None))
            if low is None or not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
                problems.append(f"limit {key} out of bounds")
    return problems


class Registry:
    """The plugins under one trusted root that the root's index vouches for."""

    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.plugins, self.refused = {}, {}
        self.load()

    def refuse(self, name, reason):
        self.refused[name] = reason

    def load(self):
        index_path = os.path.join(self.root, "index.json")
        try:
            with open(index_path, encoding="utf-8") as stream:
                index = json.load(stream)
            if index.get("schema") != INDEX_SCHEMA or not isinstance(index.get("plugins"), dict):
                raise ValueError("wrong index schema")
        except (OSError, ValueError) as error:
            self.refuse("index.json", f"unreadable index: {error}")
            return
        try:
            names = sorted(os.listdir(self.root))
        except OSError:
            return
        for name in names:
            directory = os.path.join(self.root, name)
            if name == "index.json" or not os.path.isdir(directory):
                continue
            self.load_one(name, directory, index["plugins"])

    def load_one(self, name, directory, listed):
        if os.path.islink(directory) or os.path.realpath(directory) != os.path.join(self.root, name):
            return self.refuse(name, "not a plain directory under the root")
        if name not in listed or not isinstance(listed[name], dict):
            return self.refuse(name, "not listed in the index")
        manifest_path = os.path.join(directory, "manifest.json")
        try:
            if os.path.islink(manifest_path) or sha256(manifest_path) != listed[name].get("manifest_sha256"):
                return self.refuse(name, "manifest does not match the index")
            with open(manifest_path, encoding="utf-8") as stream:
                manifest = json.load(stream)
        except (OSError, ValueError) as error:
            return self.refuse(name, f"unreadable manifest: {error}")
        problems = check_manifest(manifest)
        if manifest.get("id") != name:
            problems.append("id does not match its directory")
        if problems:
            return self.refuse(name, "; ".join(problems))
        entry_path = os.path.join(directory, manifest["entry"])
        try:
            if os.path.islink(entry_path) or sha256(entry_path) != manifest["entry_sha256"]:
                return self.refuse(name, "entry file does not match its manifest")
        except OSError as error:
            return self.refuse(name, f"unreadable entry: {error}")
        self.plugins[name] = Plugin(directory, manifest)

    def list(self, type=None):
        return [p for p in self.plugins.values() if type in (None, p.type)]


def write_index(root):
    """Compute `index.json` for every plugin directory under `root` (used by the build, not at run time)."""
    plugins = {}
    for name in sorted(os.listdir(root)):
        manifest = os.path.join(root, name, "manifest.json")
        if os.path.isfile(manifest):
            plugins[name] = {"manifest_sha256": sha256(manifest)}
    with open(os.path.join(root, "index.json"), "w", encoding="utf-8") as stream:
        json.dump({"schema": INDEX_SCHEMA, "plugins": plugins}, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return plugins


def seal_manifest(directory):
    """Set a plugin manifest's entry_sha256 to its entry file's hash (a build step)."""
    path = os.path.join(directory, "manifest.json")
    with open(path, encoding="utf-8") as stream:
        manifest = json.load(stream)
    manifest["entry_sha256"] = sha256(os.path.join(directory, manifest["entry"]))
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")


# ---------------------------------------------------------------- running a plugin


class Failed(Exception):
    pass


class WindowShape:
    """The size a window's frame is validated against."""

    def __init__(self, width, height):
        self.width, self.height = width, height


class RemoteScene(Scene):
    """A scene whose logic runs in the plugin's process. The host's run_scene drives it like any scene."""

    def __init__(self, plugin, clock=None, backend=None):
        self.plugin, self.title = plugin, plugin.name
        self.min_size = plugin.min_size or None
        self.clock = clock
        # Windows are the host's to give: the manager enforces the capability, the count, sizes and ownership.
        self.windows = WindowManager(backend, allowed="window" in plugin.capabilities,
                                     max_windows=plugin.limits["windows"]) if backend is not None else None
        self.proc = None
        self.frame = None
        self.failure = None
        self.strikes = 0

    def start(self, ctx):
        config = dict(capabilities=list(self.plugin.capabilities), limits=self.plugin.limits,
                      depth=ctx.caps.depth, unicode=ctx.caps.unicode, reduced=ctx.caps.reduced,
                      console=ctx.caps.console, width=ctx.width, height=ctx.height)
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-I", CHILD, self.plugin.directory, self.plugin.entry, json.dumps(config)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                close_fds=True, cwd="/", env=env, text=True, bufsize=1)
        except OSError as error:
            self.fail(f"could not start: {error.__class__.__name__}")

    def fail(self, reason):
        self.failure = reason
        self.done, self.result = True, {"failed": reason}
        self.stop()

    def stop(self):
        if self.windows is not None:
            self.windows.close_all()
        proc, self.proc = self.proc, None
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.communicate(timeout=2)
            except (subprocess.SubprocessError, OSError, ValueError):
                pass

    def update(self, dt, ctx, actions):
        if self.proc is None:
            return
        budget = self.plugin.limits["frame_ms"] / 1000.0
        try:
            tick = {"t": dt, "a": [a for a in actions if "input" in self.plugin.capabilities],
                    "w": ctx.width, "h": ctx.height}
            if self.windows is not None:
                self.windows.primary.update(cols=ctx.width, rows=ctx.height)
                from_windows = self.windows.poll()
                selected = self.windows.selected
                if selected and self.windows.backend.name == "inline":   # the front panel has the keyboard
                    from_windows.setdefault(selected, []).extend(tick["a"])
                    tick["a"] = []
                tick["ev"] = self.windows.take_events()
                tick["wa"] = {str(w): a for w, a in from_windows.items() if "input" in self.plugin.capabilities}
            self.proc.stdin.write(json.dumps(tick) + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            return self.fail("plugin exited")
        ready, _, _ = select.select([self.proc.stdout], [], [], budget * 3)
        if not ready:
            self.strikes += 1
            if self.strikes >= 3:
                self.fail("too slow")
            return
        self.strikes = 0
        line = self.proc.stdout.readline(MAX_REPLY)
        if not line:
            return self.fail("plugin exited")
        try:
            reply = json.loads(line)
            if "e" in reply:
                return self.fail("plugin raised " + str(reply["e"])[:40])
            self.frame = self.decode(reply, ctx)
            if self.windows is not None:
                self.windows.handle(reply.get("o", []))
                self.windows.set_frames({int(w): self.decode(f, WindowShape(*self.windows.sizes()[int(w)]))
                                         for w, f in reply.get("F", {}).items() if int(w) in self.windows.windows})
            for cue in reply.get("c", [])[:16]:
                if "audio" in self.plugin.capabilities and isinstance(cue, str):
                    ctx.audio.cue(cue)
            if reply.get("d"):
                self.done = True
                self.result = reply.get("r") if isinstance(reply.get("r"), (str, int, float, bool, type(None))) else None
        except (ValueError, TypeError, KeyError, IndexError):
            self.fail("malformed frame")

    @staticmethod
    def decode(reply, ctx):
        table = reply["s"]
        styles = []
        for fg, bg, bold in table[:512]:
            for color in (fg, bg):
                if color is not None and (len(color) != 3 or not all(isinstance(v, int) and 0 <= v <= 255 for v in color)):
                    raise ValueError("bad color")
            styles.append((tuple(fg) if fg else None, tuple(bg) if bg else None, bool(bold)))
        rows = reply["f"]
        if len(rows) > ctx.height + 2:
            raise ValueError("too many rows")
        decoded = []
        for runs in rows:
            row, x = [], 0
            for text, style in runs:
                if not isinstance(text, str) or not isinstance(style, int) or style >= len(styles):
                    raise ValueError("bad run")
                row.append((x, text, styles[style]))
                x += len(text)
                if x > ctx.width + 2:
                    raise ValueError("row too wide")
            decoded.append(row)
        return decoded

    def draw(self, canvas, ctx):
        if self.frame is not None:
            for y, row in enumerate(self.frame):
                for x, text, style in row:
                    canvas.put(x, y, text, style)
        if self.windows is not None and self.windows.backend.name == "inline":
            self.windows.backend.compose(canvas, self.windows.windows.values())


def run_plugin(plugin, caps, out, source, audio=None, clock=None, fps=None, backend=None, **kwargs):
    """Run a plugin under the host's loop. Returns a RunResult; a plugin failure is `result={"failed": reason}`.

    `backend` is a windows backend (see windows.choose_backend) for a plugin that has the `window` capability.
    """
    scene = RemoteScene(plugin, clock, backend)
    try:
        return run_scene(scene, caps, out, source, audio, clock, fps=fps or plugin.limits["fps"], **kwargs)
    finally:
        scene.stop()
