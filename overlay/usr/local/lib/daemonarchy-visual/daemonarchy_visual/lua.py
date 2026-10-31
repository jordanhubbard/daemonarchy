"""Sandboxed Lua extensions: a pixel surface, a hostile-output-safe protocol and the scene that runs them.

An extension whose entry file ends in `.lua` runs in its own low-priority process (sandbox.lua)
with no `os`, `io`, `require`, `load` or `debug`, a per-tick instruction budget, and memory, file
and fork limits. It can only ask for a few drawing and sound operations. The host (this module)
owns that process and treats everything it writes as hostile: every line is validated and clamped,
a frame has a deadline and a size cap, and a plugin that breaks a rule is killed and reported as a
failed result. Unlike a Python entry (plugin_child.py: signed content, process isolation for its
bugs) this is meant to be safe to run even if the content is not ours.

API level 1.5. A plugin defines `init()` and `tick(dt)` and sees a fixed 64x40 pixel surface, 16
colours (0 is transparent), `gfx.clear/pixel/rect`, `sfx.blip(freq, ms, wave, vol)` and
`input.held(name)`; names are the SDK's actions (left, right, up, down, fire, select) plus `space`.
"""

import math
import os
import re
import resource
import select
import shutil
import subprocess
import time

from .scene import Scene

SANDBOX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox.lua")
LOGICAL = (64, 40)               # every plugin sees this; the host scales it by whole numbers
PALETTE = (
    None, (10, 30, 70), (210, 180, 110), (255, 140, 0), (255, 90, 90), (255, 220, 0),
    (0, 200, 120), (0, 200, 255), (240, 240, 240), (130, 90, 250), (90, 90, 100),
    (30, 120, 60), (180, 60, 140), (255, 160, 200), (60, 60, 200), (20, 20, 20),
)
MAX_LINE = 96                    # bytes per protocol line
MAX_OPS = 4096                   # operations per frame
MAX_FRAME_BYTES = 1 << 18
MAX_BAD_LINES = 16
WAVES = ("sq", "tri", "noise")
FRAME_TIMEOUT = 0.5
NOBODY = 65534
INT = re.compile(r"-?[0-9]{1,6}")
ACTION_NAMES = {"fire": ("fire", "space"), "select": ("select", "return")}
HELD = ("up", "down", "left", "right", "fire", "select")


class PixelSurface:
    """A grid of palette indices drawn as half-blocks: two pixels per terminal row."""

    def __init__(self, width, height):
        if not (1 <= width <= 320 and 2 <= height <= 200 and height % 2 == 0):
            raise ValueError("surface must be 1..320 wide and an even 2..200 high")
        self.width, self.height = width, height
        self.pixels = bytearray(width * height)

    @property
    def cell_size(self):
        return self.width, self.height // 2

    def clear(self, color=0):
        self.pixels[:] = bytes([color]) * len(self.pixels)

    def pixel(self, x, y, color):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = color

    def rect(self, x, y, w, h, color):
        x0, x1 = max(0, x), min(self.width, x + w)
        if x1 <= x0:
            return
        row = bytes([color]) * (x1 - x0)
        for yy in range(max(0, y), min(self.height, y + h)):
            self.pixels[yy * self.width + x0:yy * self.width + x1] = row

    def apply(self, op):
        if op[0] == "C":
            self.clear()
        elif op[0] == "P":
            self.pixel(*op[1:])
        elif op[0] == "R":
            self.rect(*op[1:])

    def cell(self, col, row, unicode=True, scale=1):
        """(char, style) for one terminal cell; style is (fg, bg, bold). At scale n a pixel is n cells wide."""
        x = col // scale
        top = self.pixels[min(self.height - 1, 2 * row // scale) * self.width + x]
        bottom = self.pixels[min(self.height - 1, (2 * row + 1) // scale) * self.width + x]
        if not top and not bottom:
            return " ", None
        if not unicode:
            return "#", (PALETTE[top or bottom], None, False)
        if top == bottom:
            return "█", (PALETTE[top], None, False)
        if top and bottom:
            return "▀", (PALETTE[top], PALETTE[bottom], False)
        if top:
            return "▀", (PALETTE[top], None, False)
        return "▄", (PALETTE[bottom], None, False)

    def blit(self, canvas, x, y, unicode=True, scale=1):
        cols, rows = self.cell_size
        for row in range(rows * scale):
            for col in range(cols * scale):
                char, style = self.cell(col, row, unicode, scale)
                if char != " ":
                    canvas.put(x + col, y + row, char, style)


def fit_scale(columns, rows, logical=LOGICAL):
    """The largest whole-number scale at which the surface fits, or 0 if even scale 1 does not."""
    return max(0, min(columns // logical[0], rows // (logical[1] // 2)))


def parse_op(line, width, height):
    """One validated op from a plugin's output line, or None. Never raises."""
    if len(line) > MAX_LINE:
        return None
    parts = line.split()
    if not parts:
        return None
    kind = parts[0]
    if kind != "S" and not all(INT.fullmatch(p) for p in parts[1:]):
        return None
    try:
        if kind in ("F", "C", "E") and len(parts) == 1:
            return (kind,)
        if kind == "P" and len(parts) == 4:
            x, y, c = (int(p) for p in parts[1:])
            return ("P", x, y, max(0, min(15, c)))
        if kind == "R" and len(parts) == 6:
            x, y, w, h, c = (int(p) for p in parts[1:])
            return ("R", x, y, max(0, min(width, w)), max(0, min(height, h)), max(0, min(15, c)))
        if kind == "S" and len(parts) == 5 and parts[3] in WAVES \
                and all(INT.fullmatch(p) for p in (parts[1], parts[2], parts[4])):
            return ("S", max(30, min(8000, int(parts[1]))), max(5, min(400, int(parts[2]))),
                    parts[3], max(0, min(100, int(parts[4]))))
    except ValueError:
        pass
    return None


def find_lua():
    for name in ("flua", "lua5.4", "lua54", "lua"):
        found = shutil.which(name) or (name == "flua" and os.path.exists("/usr/libexec/flua") and "/usr/libexec/flua")
        if found:
            return found
    return None


def limit_child(memory_bytes):
    """Runs in the child before exec: low priority, bounded memory, no files, no forks, never root."""
    def apply():
        os.nice(10)
        for name, value in (("RLIMIT_AS", memory_bytes), ("RLIMIT_NOFILE", 16), ("RLIMIT_FSIZE", 0),
                            ("RLIMIT_CORE", 0)):
            if hasattr(resource, name):
                resource.setrlimit(getattr(resource, name), (value, value))
        if os.geteuid() == 0:
            os.setgroups([])
            os.setgid(NOBODY)
            os.setuid(NOBODY)
            if os.geteuid() == 0:
                os._exit(126)       # never run a plugin as root
    return apply


class LuaProcess:
    """One sandboxed plugin. frame() returns the frame's ops, or None once the plugin has failed."""

    def __init__(self, path, width, height, lua=None, seed=1, memory_mb=128):
        self.width, self.height = width, height
        self.failure, self.buffer, self.bad = None, b"", 0
        lua = lua or find_lua()
        if lua is None:
            self.failure, self.process = "no Lua interpreter", None
            return
        try:
            self.process = subprocess.Popen(
                [lua, "-E", SANDBOX, str(path), str(width), str(height), str(seed)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd="/",
                env={}, close_fds=True, start_new_session=True, preexec_fn=limit_child(memory_mb << 20))
        except (OSError, subprocess.SubprocessError) as error:
            self.failure, self.process = "could not start: " + error.__class__.__name__, None

    @property
    def alive(self):
        return self.process is not None and self.failure is None

    def fail(self, reason):
        if self.failure is None:
            self.failure = reason
        self.stop()
        return None

    def frame(self, dt_ms, held=(), timeout=FRAME_TIMEOUT):
        if not self.alive:
            return None
        try:
            self.process.stdin.write(("T %d %s\n" % (max(0, min(1000, int(dt_ms))), ",".join(held))).encode("ascii"))
            self.process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            return self.fail("exited")
        deadline = time.monotonic() + timeout
        fd = self.process.stdout.fileno()
        ops = []
        while True:
            while b"\n" in self.buffer:
                raw, self.buffer = self.buffer.split(b"\n", 1)
                op = parse_op(raw.decode("ascii", "replace"), self.width, self.height)
                if op is None:
                    self.bad += 1
                    if self.bad > MAX_BAD_LINES:
                        return self.fail("protocol violations")
                elif op[0] == "F":
                    return ops
                elif op[0] == "E":
                    return self.fail("plugin error")
                else:
                    ops.append(op)
                    if len(ops) > MAX_OPS:
                        return self.fail("too many operations")
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                return self.fail("frame timeout")
            chunk = os.read(fd, 65536)
            if not chunk:
                return self.fail("exited")
            self.buffer += chunk
            if len(self.buffer) > MAX_FRAME_BYTES:
                return self.fail("output flood")

    def stop(self):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            os.killpg(process.pid, 9)
        except (ProcessLookupError, PermissionError):
            pass
        for stream in (process.stdin, process.stdout):
            try:
                stream.close()
            except OSError:
                pass
        process.wait()


class HeldKeys:
    """Terminals report key repeat, never key release; an action counts as held for a while after the last event.

    The first press is held longer than later repeats because keyboards pause before they repeat.
    """

    def __init__(self, first=0.40, repeat=0.12):
        self.first, self.repeat = first, repeat
        self.until, self.count = {}, {}

    def press(self, name, now):
        if self.until.get(name, 0) < now:
            self.count[name] = 0
        self.count[name] = self.count.get(name, 0) + 1
        self.until[name] = now + (self.first if self.count[name] == 1 else self.repeat)

    def held(self, now):
        return sorted(name for name, until in self.until.items() if until >= now)


class LuaScene(Scene):
    """A scene whose logic is a sandboxed Lua plugin. The host's run_scene drives it like any scene."""

    def __init__(self, plugin, clock=None, lua=None, seed=None):
        self.plugin, self.title = plugin, plugin.name
        self.min_size = plugin.min_size if any(plugin.min_size) else (LOGICAL[0], LOGICAL[1] // 2 + 2)
        self.lua, self.seed = lua, seed if seed is not None else int(time.time()) & 0xFFFF
        self.surface = PixelSurface(*LOGICAL)
        self.keys, self.process, self.now = HeldKeys(), None, 0.0
        self.failure = None
        self.started = None

    def start(self, ctx):
        entry = os.path.join(self.plugin.directory, self.plugin.entry)
        self.process = LuaProcess(entry, *LOGICAL, lua=self.lua, seed=self.seed,
                                  memory_mb=self.plugin.limits["memory_mb"])
        if self.process.failure:
            self.fail(self.process.failure)

    def fail(self, reason):
        self.failure = reason
        self.done, self.result = True, {"failed": reason}
        self.stop()

    def stop(self):
        process, self.process = self.process, None
        if process is not None:
            process.stop()

    def update(self, dt, ctx, actions):
        if self.process is None:
            return
        self.now += dt
        if "input" in self.plugin.capabilities:
            for action in actions:
                if action in HELD:
                    for name in ACTION_NAMES.get(action, (action,)):
                        self.keys.press(name, self.now)
        ops = self.process.frame(dt * 1000, self.keys.held(self.now),
                                 timeout=self.plugin.limits["frame_ms"] / 1000.0)
        if ops is None:
            return self.fail(self.process.failure or "plugin exited")
        for op in ops:
            if op[0] == "S":
                if "audio" in self.plugin.capabilities:
                    ctx.audio.blip(op[1], op[2], op[3], op[4] / 100.0)
            else:
                self.surface.apply(op)

    def draw(self, canvas, ctx):
        scale = max(1, fit_scale(canvas.width, canvas.height))
        cols, rows = self.surface.cell_size
        x, y = max(0, (canvas.width - cols * scale) // 2), max(0, (canvas.height - rows * scale) // 2)
        self.surface.blit(canvas, x, y, ctx.glyphs.unicode, scale)

    def plain_lines(self, ctx):
        return [self.title + " (needs a graphical terminal)"]
