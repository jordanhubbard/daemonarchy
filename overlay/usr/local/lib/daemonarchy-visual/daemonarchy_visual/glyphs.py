"""Glyph sets: Unicode block and box characters, with an ASCII twin for serial and dumb terminals."""


class Glyphs:
    def __init__(self, unicode):
        self.unicode = unicode
        if unicode:
            self.levels = " ▁▂▃▄▅▆▇█"
            self.h, self.v = "─", "│"
            self.corners = "╭╮╰╯"
            self.full, self.empty, self.cap = "█", "░", "▀"
            self.icons = dict(done="●", active="▶", pending="○", skipped="·", failed="✗")
            self.dot = "·"
        else:
            self.levels = " .:-=+*#%"
            self.h, self.v = "-", "|"
            self.corners = "++++"
            self.full, self.empty, self.cap = "#", ".", "-"
            self.icons = dict(done="*", active=">", pending="o", skipped="-", failed="x")
            self.dot = "|"
