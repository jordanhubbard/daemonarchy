"""Helpers for small arcade scenes: a fixed simulation step, a centered playfield, a HUD and banners.

Games keep their rules in plain classes with a deterministic `step(dt, actions)` so they can be
tested without a terminal; the scene only draws. Terminal cells are about twice as tall as wide,
so a playfield is measured in cells and games draw wide glyphs (two cells) where shape matters.
"""

from .layout import Rect
from .palette import CYAN, DIM, GRAY, GREEN, RED, WHITE, YELLOW


class FixedStep:
    """Turns variable frame times into whole simulation steps of `1/rate` seconds."""

    def __init__(self, rate=30, limit=5):
        self.step, self.limit, self.carry = 1.0 / rate, limit, 0.0

    def steps(self, dt):
        self.carry += dt
        count = 0
        while self.carry >= self.step and count < self.limit:
            self.carry -= self.step
            count += 1
        if count == self.limit:
            self.carry = 0.0   # fell behind: drop the backlog rather than spiral
        return count


def playfield(canvas, width, height):
    """A rectangle of the requested size centered on the canvas, shrunk to fit; leaves a row for the HUD."""
    area = Rect(0, 1, canvas.width, canvas.height - 2)
    return area.centered(min(width, canvas.width - 2), min(height, canvas.height - 3))


def frame(canvas, rect, ctx, style=(DIM, None, False)):
    canvas.box(rect.x - 1, rect.y - 1, rect.w + 2, rect.h + 2, ctx.glyphs, style)


def hud(canvas, ctx, title, score, lives=None, level=None):
    """One status row at the top: title, score, lives and level."""
    canvas.put(0, 0, " " * canvas.width)
    canvas.put(1, 0, title, (CYAN, None, True))
    heart = "♥" if ctx.glyphs.unicode else "*"
    for labels in (True, False):          # the compact form drops the words when the row is narrow
        parts = [f"SCORE {score:06d}" if labels else f"{score:06d}"]
        if level is not None:
            parts.append(f"LEVEL {level}" if labels else f"L{level}")
        if lives is not None:
            parts.append(("LIVES " if labels else "") + heart * lives)
        text = ("   " if labels else " ").join(parts)
        if len(title) + len(text) + 4 <= canvas.width or not labels:
            break
    canvas.put(max(len(title) + 3, canvas.width - len(text) - 1), 0, text[:max(0, canvas.width - len(title) - 4)],
               (WHITE, None, True))


def footer(canvas, text):
    canvas.put(max(0, (canvas.width - len(text)) // 2), canvas.height - 1, text[:canvas.width], (GRAY, None, False))


def banner(canvas, text, sub="", good=True):
    """A message over the middle of the screen."""
    row = canvas.height // 2
    color = GREEN if good else RED
    canvas.put(max(0, (canvas.width - len(text)) // 2), row, text, (color, None, True))
    if sub:
        canvas.put(max(0, (canvas.width - len(sub)) // 2), row + 2, sub, (YELLOW, None, False))
