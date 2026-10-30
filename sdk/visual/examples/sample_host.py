#!/usr/bin/env python3
"""A small program that is not the installer, built only on the visual SDK.

  python3 sample_host.py            run in a terminal: gradient title, a meter you
                                    nudge with the arrow keys, fireworks on Space,
                                    q to quit. Plain terminals get a few lines.

It exists to show that the SDK stands on its own: no installer module, no
installation state and no privilege is involved.
"""

import os
import sys

try:
    import daemonarchy_visual as sdk
except ImportError:  # running from a checkout rather than an installed package
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                        "overlay", "usr", "local", "lib", "daemonarchy-visual")
    sys.path.insert(0, os.path.normpath(root))
    import daemonarchy_visual as sdk

from daemonarchy_visual import effects, palette
from daemonarchy_visual.input import FdSource, Raw


class Hello(sdk.Scene):
    title = "Daemonarchy visual SDK"

    def start(self, ctx):
        self.age, self.level = 0.0, 0.5
        self.fireworks = sdk.Fireworks(ctx.width, max(1, ctx.height // 2))
        self.rise = sdk.Tween(0.0, 1.0, 0.6, "ease_out")

    def update(self, dt, ctx, actions):
        self.age += dt
        self.rise.advance(dt)
        for action in actions:
            if action == "right":
                self.level = min(1.0, self.level + 0.05)
            elif action == "left":
                self.level = max(0.0, self.level - 0.05)
            elif action == "fire":
                self.fireworks.burst()
                ctx.audio.cue("win")
        if not ctx.reduced:
            self.fireworks.step(dt, spawning=False)

    def draw(self, canvas, ctx):
        row = int(canvas.height // 2 * self.rise.value)
        effects.gradient_text(canvas, max(0, (canvas.width - len(self.title)) // 2), row, self.title,
                              palette.LOGO, 0.0 if ctx.reduced else self.age * 0.2)
        canvas.bar(max(0, canvas.width // 2 - 20), row + 2, 40, self.level, ctx.glyphs, (palette.GREEN, None, False),
                   (palette.DIM, None, False))
        canvas.put(max(0, (canvas.width - 40) // 2), canvas.height - 1,
                   "left/right: meter   space: fireworks   q: quit", (palette.GRAY, None, False))
        if not ctx.reduced:
            for x, y, char, color in self.fireworks.cells(ctx.glyphs.unicode):
                canvas.put(x, y, char, (color, None, False))

    def plain_lines(self, ctx):
        return [self.title, "Run this in a color terminal to see the animation."]


def main():
    caps = sdk.detect()
    with Raw(sys.stdin.fileno()):
        result = sdk.run_scene(Hello(), caps, sys.stdout, FdSource(sys.stdin.fileno()), sdk.NullAudio())
    return 0 if result.reason in ("plain", "quit", "done", "eof") else 1


if __name__ == "__main__":
    raise SystemExit(main())
