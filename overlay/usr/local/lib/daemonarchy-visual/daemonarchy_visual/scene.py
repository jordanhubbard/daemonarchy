"""Scenes and the loop that runs them.

A scene is a small object: `update(dt, ctx, actions)` advances it, `draw(canvas,
ctx)` paints it, `plain_lines(ctx)` is what a serial or plain terminal gets.
The loop owns timing, input, resizing, pausing, preemption and restoring the
terminal. A host can stop a scene at any frame by returning True from
`preempt`; the scene cannot refuse.
"""

from .audio import NullAudio
from .canvas import Screen
from .glyphs import Glyphs
from .palette import Colors, GRAY, WHITE
from .timeline import MonotonicClock


class Context:
    """What a scene may see: capabilities, colors, glyphs, audio and the clock. No host state."""

    def __init__(self, caps, audio=None, clock=None):
        self.caps = caps
        self.colors = Colors(caps.depth)
        self.glyphs = Glyphs(caps.unicode)
        self.audio = audio or NullAudio()
        self.clock = clock or MonotonicClock()

    @property
    def reduced(self):
        return self.caps.reduced

    @property
    def width(self):
        return self.caps.width

    @property
    def height(self):
        return self.caps.height


class Scene:
    title = ""
    done = False
    result = None

    def start(self, ctx):
        pass

    def update(self, dt, ctx, actions):
        pass

    def draw(self, canvas, ctx):
        pass

    def plain_lines(self, ctx):
        return [self.title] if self.title else []


class RunResult:
    def __init__(self, reason, result=None, frames=0):
        self.reason, self.result, self.frames = reason, result, frames   # done, quit, preempted, eof, plain

    def __repr__(self):
        return f"RunResult({self.reason!r}, {self.result!r}, frames={self.frames})"


MAX_STEP = 0.1  # A long stall (a suspended window) never becomes one huge simulation step.


def run_scene(scene, caps, out, source, audio=None, clock=None, fps=15, preempt=None, size=None,
              suspended=None, max_frames=None):
    """Run `scene` until it is done, the user quits, the host preempts it, or input ends.

    caps        Capabilities (plain terminals get `plain_lines` once and the loop returns)
    out         a text stream for the terminal
    source      an object with poll(timeout) -> [action] (see input.FdSource, input.ListSource)
    preempt     callable -> True to stop at once (prompts, errors and completion use this)
    size        callable -> (width, height), consulted every frame so a resize reflows
    suspended   callable -> True while the scene is not visible: no update, no drawing
    """
    ctx = Context(caps, audio, clock)
    if caps.plain:
        for line in scene.plain_lines(ctx):
            out.write(line + "\n")
        try:
            out.flush()
        except (OSError, ValueError):
            pass
        return RunResult("plain")
    screen = Screen(out, ctx.colors)
    frame_time = 1.0 / max(1, fps)
    paused, frames, last = False, 0, ctx.clock.now()
    scene.start(ctx)
    screen.enter()
    try:
        while True:
            if preempt is not None and preempt():
                return RunResult("preempted", scene.result, frames)
            if max_frames is not None and frames >= max_frames:
                return RunResult("done", scene.result, frames)
            if size is not None:
                caps.width, caps.height = size()
            actions = source.poll(0.0)
            if "quit" in actions or "back" in actions:
                return RunResult("quit", scene.result, frames)
            if source.eof:
                return RunResult("eof", scene.result, frames)
            if "pause" in actions:
                paused = not paused
            if "mute" in actions:
                ctx.audio.muted = not ctx.audio.muted
            now = ctx.clock.now()
            dt = min(MAX_STEP, max(0.0, now - last))
            last = now
            if suspended is not None and suspended():
                ctx.clock.sleep(0.25)
                continue
            canvas = screen.canvas(caps.width, caps.height)
            if caps.small:
                text = "Terminal too small"[:canvas.width]
                canvas.put(max(0, (canvas.width - len(text)) // 2), canvas.height // 2, text, (WHITE, None, True))
            else:
                if not paused:
                    scene.update(dt, ctx, [a for a in actions if a not in ("pause", "mute")])
                scene.draw(canvas, ctx)
                if paused:
                    canvas.put(max(0, (canvas.width - 8) // 2), canvas.height - 2, " PAUSED ", (GRAY, None, True))
            screen.present(canvas)
            frames += 1
            if scene.done:
                return RunResult("done", scene.result, frames)
            spent = ctx.clock.now() - now
            ctx.clock.sleep(frame_time - spent)
    finally:
        screen.leave()
        ctx.audio.close()
