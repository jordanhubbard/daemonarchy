"""A cell canvas, drawing primitives, and a screen that writes only what changed."""


class Canvas:
    """A grid of characters with styles (foreground, background, bold). Out-of-range drawing is clipped."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.chars = [[" "] * width for _ in range(height)]
        self.styles = [[None] * width for _ in range(height)]

    # -- drawing

    def put(self, x, y, text, style=None, width=None):
        if not 0 <= y < self.height or x >= self.width:
            return
        limit = self.width if width is None else min(self.width, x + width)
        row, styles = self.chars[y], self.styles[y]
        for char in text:
            if x >= limit:
                break
            if x >= 0:
                row[x] = char
                styles[x] = style
            x += 1

    def fill(self, x, y, w, h, char=" ", style=None):
        for row in range(max(0, y), min(self.height, y + h)):
            self.put(x, row, char * max(0, w), style)

    def hline(self, x, y, length, char="-", style=None):
        self.put(x, y, char * max(0, length), style)

    def vline(self, x, y, length, char="|", style=None):
        for row in range(y, y + max(0, length)):
            self.put(x, row, char, style)

    def box(self, x, y, w, h, glyphs, style=None):
        """A rounded frame using a Glyphs set."""
        if w < 2 or h < 2:
            return
        tl, tr, bl, br = glyphs.corners
        self.put(x, y, tl + glyphs.h * (w - 2) + tr, style)
        self.put(x, y + h - 1, bl + glyphs.h * (w - 2) + br, style)
        self.vline(x, y + 1, h - 2, glyphs.v, style)
        self.vline(x + w - 1, y + 1, h - 2, glyphs.v, style)

    def sprite(self, x, y, rows, style=None, transparent=" "):
        """Draw rows of text; `style` is a style, or a function (char, row, col) -> style."""
        for row, text in enumerate(rows):
            for col, char in enumerate(text):
                if char != transparent:
                    self.put(x + col, y + row, char, style(char, row, col) if callable(style) else style)

    def bar(self, x, y, width, fraction, glyphs, style=None, empty_style=None):
        filled = int(max(0.0, min(1.0, fraction)) * width)
        self.put(x, y, glyphs.full * filled, style)
        self.put(x + filled, y, glyphs.empty * (width - filled), empty_style or style)

    # -- output

    @staticmethod
    def serialize(chars, styles, colors):
        parts, current = [], object()
        for char, style in zip(chars, styles):
            if style != current:
                parts.append(colors.sgr(style or (None, None, False)))
                current = style
            parts.append(char)
        return "".join(parts)

    def rows(self, colors):
        return [self.serialize(c, s, colors) for c, s in zip(self.chars, self.styles)]

    def changes(self, previous, colors):
        """Terminal output that turns the previous frame into this one, cell ranges only."""
        out = []
        for y in range(self.height):
            chars, styles = self.chars[y], self.styles[y]
            if previous is not None:
                old_chars, old_styles = previous.chars[y], previous.styles[y]
                if chars == old_chars and styles == old_styles:
                    continue
                first = next(i for i in range(self.width) if chars[i] != old_chars[i] or styles[i] != old_styles[i])
                last = next(i for i in range(self.width - 1, -1, -1)
                            if chars[i] != old_chars[i] or styles[i] != old_styles[i])
            else:
                first, last = 0, self.width - 1
            if y == self.height - 1:
                last = min(last, self.width - 2)  # Never write the bottom-right cell: some terminals scroll.
            if last < first:
                continue
            out.append(f"\033[{y + 1};{first + 1}H"
                       + self.serialize(chars[first:last + 1], styles[first:last + 1], colors) + "\033[0m")
        return out

    def plain(self):
        return ["".join(row).rstrip() for row in self.chars]


class Screen:
    """Owns the terminal region: sizes the canvas, diffs frames and restores the terminal on exit."""

    def __init__(self, out, colors):
        self.out, self.colors = out, colors
        self.previous = None
        self.size = None
        self.entered = False

    def canvas(self, width, height):
        return Canvas(max(10, min(width, 400)), max(3, min(height, 200)))

    def enter(self):
        self.entered = True
        self._write("\033[?25l\033[0m\033[2J")  # hide the cursor, clear

    def leave(self):
        if self.entered:
            self._write("\033[0m\033[?25h\033[2J\033[H")
        self.entered = False

    def present(self, canvas):
        """Write the difference from the last frame; a size change clears and redraws everything."""
        pieces = []
        if self.size != (canvas.width, canvas.height):
            self.size = (canvas.width, canvas.height)
            self.previous = None
            pieces.append("\033[0m\033[2J")
        pieces.extend(canvas.changes(self.previous, self.colors))
        self.previous = canvas
        if pieces:
            self._write("".join(pieces))

    def _write(self, text):
        try:
            self.out.write(text)
            self.out.flush()
        except (OSError, ValueError, BrokenPipeError):
            pass
