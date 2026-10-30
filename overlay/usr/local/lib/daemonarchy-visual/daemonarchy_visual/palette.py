"""Colors: palettes, gradients and SGR sequences quantized to the terminal's depth."""

# FreeBSD vt(4)'s default palette (sys/dev/vt/colors/vt_termcolors.c), in ANSI order.
VT16 = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (196, 161, 0), (51, 102, 163), (128, 0, 128), (0, 128, 128),
        (191, 191, 191), (46, 51, 54), (255, 0, 0), (0, 255, 0), (255, 255, 0), (115, 158, 207),
        (255, 0, 255), (0, 255, 255), (255, 255, 255)]

WINAMP = ((0, 210, 70), (180, 230, 0), (255, 220, 0), (255, 120, 0), (255, 40, 40))
SCOPE = ((0, 220, 255), (120, 120, 255), (255, 60, 220))
LOGO = ((255, 70, 70), (230, 50, 140), (132, 93, 249))
WHITE, GRAY, DIM = (240, 240, 240), (150, 150, 150), (90, 90, 100)
CYAN, GREEN, RED, YELLOW, PURPLE = (0, 230, 255), (0, 220, 90), (255, 60, 60), (255, 220, 0), (132, 93, 249)
MAGENTA, ORANGE = (230, 50, 140), (255, 120, 0)
SPARKS = (YELLOW, ORANGE, CYAN, (255, 60, 220), GREEN, WHITE)


class Colors:
    """SGR sequences for a color depth. A style is (foreground, background, bold); colors are RGB or None."""

    def __init__(self, depth):
        self.depth = depth
        self.cache = {}

    @staticmethod
    def nearest(rgb, palette):
        r, g, b = rgb
        return min(range(len(palette)), key=lambda i: (palette[i][0] - r) ** 2 * 3 + (palette[i][1] - g) ** 2 * 4
                   + (palette[i][2] - b) ** 2 * 2)

    @staticmethod
    def xterm256(rgb):
        def level(v):
            return 0 if v < 48 else 1 if v < 115 else (v - 35) // 40
        r, g, b = (min(5, level(v)) for v in rgb)
        cube = 16 + 36 * r + 6 * g + b
        steps = (0, 95, 135, 175, 215, 255)
        cube_rgb = (steps[r], steps[g], steps[b])
        gray = max(0, min(23, (sum(rgb) // 3 - 8) // 10))
        gray_rgb = (8 + gray * 10,) * 3

        def distance(other):
            return sum((x - y) ** 2 for x, y in zip(rgb, other))
        return cube if distance(cube_rgb) <= distance(gray_rgb) else 232 + gray

    def sgr(self, style=(None, None, False)):
        if style in self.cache:
            return self.cache[style]
        fg, bg, bold = style
        codes = ["0"]
        if bold:
            codes.append("1")
        if self.depth != "none":
            for rgb, base in ((fg, 30), (bg, 40)):
                if rgb is None:
                    continue
                if self.depth == "truecolor":
                    codes.append(f"{base + 8};2;{rgb[0]};{rgb[1]};{rgb[2]}")
                elif self.depth == "256":
                    codes.append(f"{base + 8};5;{self.xterm256(rgb)}")
                elif self.depth == "16":
                    index = self.nearest(rgb, VT16)
                    codes.append(str(base + index if index < 8 else base + 60 + index - 8))
                else:
                    codes.append(str(base + self.nearest(rgb, VT16[:8])))
        value = "\033[" + ";".join(codes) + "m"
        self.cache[style] = value
        return value


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def gradient(stops, t):
    # Quantized to 12 steps so neighbouring cells share one color sequence.
    t = round(max(0.0, min(1.0, t)) * 12) / 12
    span = len(stops) - 1
    index = min(span - 1, int(t * span))
    return mix(stops[index], stops[index + 1], t * span - index)
