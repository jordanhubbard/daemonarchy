"""Line-oriented flourishes: effects printed in place between a host's own prompts.

These write to a stream a few characters at a time and leave the line as plain
text; they do not take over the screen. Plain terminals and reduced motion get
the final text at once, with no color changes. A host plays its own sound.
"""

from .palette import GRAY, GREEN, LOGO, RED, WHITE, YELLOW, gradient


def _sleep(clock, seconds):
    if seconds > 0:
        clock.sleep(seconds)


def type_line(caps, colors, write, clock, text, left=0, stops=LOGO, per_char=0.018, limit=0.3):
    """A title typed in with a gradient."""
    pad = " " * max(0, left)
    if caps.plain or caps.reduced:
        write(pad + text + "\n")
        return
    step = min(per_char, limit / max(1, len(text)))
    write(pad)
    for index, char in enumerate(text):
        color = gradient(stops, index / max(1, len(text) - 1))
        write(colors.sgr((color, None, True)) + char)
        _sleep(clock, step)
    write(colors.sgr() + "\n")


def result_line(caps, colors, write, clock, ok, text, left=0):
    """A check result: a mark that sparkles once, then stays."""
    pad = " " * max(0, left)
    mark = ("√" if ok else "×") if caps.unicode else ("ok" if ok else "x")
    color = GREEN if ok else RED
    if caps.plain or caps.reduced:
        write(f"{pad}{mark} {text}\n")
        return
    sparkle = ("☼", "*", "+", mark) if caps.unicode else ("*", "+", ".", mark)
    for index, char in enumerate(sparkle):
        last = index == len(sparkle) - 1
        write("\r" + pad + colors.sgr((color if last else YELLOW, None, True)) + char + colors.sgr()
              + " " + colors.sgr((WHITE if last else GRAY, None, False)) + text + colors.sgr())
        _sleep(clock, 0 if last else 0.05)
    write("\n")


def pulse_line(caps, colors, write, clock, text, left=0):
    """A warning: three red pulses, then bold text on red."""
    pad = " " * max(0, left)
    mark = "▲" if caps.unicode else "!"
    line = f" {mark} {text} {mark} "
    if caps.plain or caps.reduced:
        write(f"{pad}{line}\n")
        return
    for pulse in range(6):
        style = (WHITE, RED, True) if pulse % 2 == 0 else (RED, None, True)
        write("\r" + pad + colors.sgr(style) + line + colors.sgr())
        _sleep(clock, 0.15)
    write("\r" + pad + colors.sgr((WHITE, RED, True)) + line + colors.sgr() + "\n")
