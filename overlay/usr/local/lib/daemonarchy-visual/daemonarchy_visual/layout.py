"""Rectangles and the small amount of layout the screens need."""


class Rect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, max(0, w), max(0, h)

    def inset(self, dx, dy=None):
        dy = dx if dy is None else dy
        return Rect(self.x + dx, self.y + dy, self.w - 2 * dx, self.h - 2 * dy)

    def split_h(self, left):
        """Split into a left part `left` cells wide and the remainder."""
        left = max(0, min(self.w, left))
        return Rect(self.x, self.y, left, self.h), Rect(self.x + left, self.y, self.w - left, self.h)

    def split_v(self, top):
        top = max(0, min(self.h, top))
        return Rect(self.x, self.y, self.w, top), Rect(self.x, self.y + top, self.w, self.h - top)

    def centered(self, w, h):
        w, h = min(w, self.w), min(h, self.h)
        return Rect(self.x + (self.w - w) // 2, self.y + (self.h - h) // 2, w, h)

    def contains(self, x, y):
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def __eq__(self, other):
        return isinstance(other, Rect) and (self.x, self.y, self.w, self.h) == (other.x, other.y, other.w, other.h)

    def __repr__(self):
        return f"Rect({self.x}, {self.y}, {self.w}, {self.h})"


def center_x(width, text_width):
    return max(0, (width - text_width) // 2)
