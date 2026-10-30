#!/usr/bin/env python3
"""Daemonarchy's flourishes: the mascot, sparkles, fireworks and short terminal animations.

  charm.py attract --logo PATH --top ROW   animate the welcome logo and mascot until killed
  charm.py transition TITLE [--left N]     a screen title typed in with a whoosh
  charm.py result ok|fail TEXT [--left N]  a check result with a sparkle and a sound
  charm.py warn TEXT [--left N]            the disk commit warning: three red pulses and a klaxon
  charm.py cheer TITLE [SUBTITLE]          a short celebration (first boot, the live desktop)

The configurator calls these between its gum prompts; the install screen
imports the mascot and fireworks. Every animation is short, decorative and
tied to something that just happened (a screen change, a check result, a
confirmation, a result) or to a genuine wait for the operator. None of them
draws or implies progress. Reduced motion (DAEMONARCHY_REDUCED_MOTION=1)
draws the final frame only; serial and dumb terminals get plain lines;
NO_COLOR drops color. Sounds go through sound.py and are never required.
Nothing here can fail a caller: every command exits 0.
"""
import importlib.util
import math
import os
from pathlib import Path
import signal
import sys

HERE = Path(__file__).resolve().parent
# The visual SDK ships beside libexec (/usr/local/lib/daemonarchy-visual). Every flourish here is drawn
# with it: capability detection, effects, canvas, screens and inline text effects.
SDK_PATH = HERE.parents[1] / 'lib' / 'daemonarchy-visual'
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))
import daemonarchy_visual as sdk  # noqa: E402
from daemonarchy_visual import effects as sdk_effects  # noqa: E402
from daemonarchy_visual.palette import (CYAN, DIM, GRAY, GREEN, LOGO, MAGENTA, PURPLE, RED, SPARKS,  # noqa: E402
                                        WHITE, YELLOW)

Fireworks = sdk.Fireworks  # the SDK's seeded particle fireworks; kept here under its old name

# ------------------------------------------------------------------ the mascot
#
# A small original daemon: horns, a round face, a trident. Eleven columns by
# five rows. Unicode frames use only glyphs from the vt(4) Terminus font
# (blocks, CP437 shapes, Greek Psi); ASCII frames serve serial terminals.

MASCOT_UNICODE = dict(
    idle=(' ▲     ▲ Ψ ',
          '▐█▀▀▀▀▀█▌│ ',
          '▐█ ● ● █▌│ ',
          '▐█  ▼  █▌┘ ',
          ' ▀█▄▄▄█▀   '),
    blink=(' ▲     ▲ Ψ ',
           '▐█▀▀▀▀▀█▌│ ',
           '▐█ ─ ─ █▌│ ',
           '▐█  ▼  █▌┘ ',
           ' ▀█▄▄▄█▀   '),
    work=(' ▲     ▲   ',
          '▐█▀▀▀▀▀█▌ Ψ',
          '▐█ ● ● █▌ │',
          '▐█  ▼  █▌─┘',
          ' ▀█▄▄▄█▀   '),
    left=(' ▲     ▲ Ψ ',
          '▐█▀▀▀▀▀█▌│ ',
          '▐█● ●  █▌│ ',
          '▐█  ▼  █▌┘ ',
          ' ▀█▄▄▄█▀   '),
    right=(' ▲     ▲ Ψ ',
           '▐█▀▀▀▀▀█▌│ ',
           '▐█  ● ●█▌│ ',
           '▐█  ▼  █▌┘ ',
           ' ▀█▄▄▄█▀   '),
    happy=('☼▲     ▲ Ψ☼',
           '▐█▀▀▀▀▀█▌│ ',
           '▐█ ^ ^ █▌│ ',
           '▐█ ╰─╯ █▌┘ ',
           ' ▀█▄▄▄█▀   '),
    sad=(' ▲     ▲   ',
         '▐█▀▀▀▀▀█▌  ',
         '▐█ × × █▌  ',
         '▐█ ╭─╮ █▌Ψ ',
         ' ▀█▄▄▄█▀ │ '),
)
MASCOT_ASCII = dict(
    idle=(' /\\   /\\ Y ', '| o   o | | ', '|   v   |-\' ', ' \\_____/    ', '            '),
    blink=(' /\\   /\\ Y ', '| -   - | | ', '|   v   |-\' ', ' \\_____/    ', '            '),
    work=(' /\\   /\\   ', '| o   o |  Y', '|   v   |--\'', ' \\_____/    ', '            '),
    left=(' /\\   /\\ Y ', '|o   o  | | ', '|   v   |-\' ', ' \\_____/    ', '            '),
    right=(' /\\   /\\ Y ', '|  o   o| | ', '|   v   |-\' ', ' \\_____/    ', '            '),
    happy=('*/\\   /\\ Y*', '| ^   ^ | | ', '|  \\_/  |-\' ', ' \\_____/    ', '            '),
    sad=(' /\\   /\\   ', '| x   x |   ', '|  /-\\  | Y ', ' \\_____/  | ', '            '),
)
MASCOT_W, MASCOT_H = 12, 5


def mascot_style(char, row, col=0):
    """Color for one mascot cell: red horns, a yellow trident, white eyes, a purple face."""
    if char in '☼*':
        return YELLOW
    if col >= 9:
        return YELLOW
    if row == 0:
        return RED
    if char in '●^─×ox-v▼╰╯╭╮_' and 1 <= row <= 3 and 2 <= col <= 6:
        return WHITE
    return MAGENTA if row < 3 else PURPLE


def mascot_frame(expression, unicode=True):
    frames = MASCOT_UNICODE if unicode else MASCOT_ASCII
    return frames.get(expression, frames['idle'])


def mascot_expression(now, mood='idle', level=0.0, reduced=False):
    """Pick a frame. Blinks and glances are decorative; 'work' follows a measured level."""
    if mood in ('happy', 'sad'):
        return mood
    if reduced:
        return 'idle'
    if mood == 'waiting':
        return ('left', 'idle', 'right', 'idle', 'blink', 'idle')[int(now * 1.6) % 6]
    if mood == 'working' and level > 0.05:
        # The trident goes up and down at a pace set by the measured activity level.
        return 'work' if math.sin(now * (2 + 10 * level)) > 0 else 'idle'
    return 'blink' if now % 4.0 < 0.15 else 'idle'



# ------------------------------------------------------------------ terminal helpers

def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sound():
    try:
        return _load('daemonarchy_sound', 'sound.py')
    except (OSError, ImportError, SyntaxError):
        return None


def play(cue):
    module = sound()
    if module is not None:
        try:
            module.Client().play(cue)
        except Exception:  # noqa: BLE001 - sound is never allowed to fail a caller.
            pass


class Term:
    """Where and how to draw: the SDK's negotiated capabilities, plus the stream and a way to write."""

    def __init__(self, env=None, stream=None):
        self.out = stream or sys.stdout
        self.caps = sdk.detect(env, self.out)
        self.colors = sdk.Colors(self.caps.depth)
        self.plain, self.reduced, self.unicode = self.caps.plain, self.caps.reduced, self.caps.unicode
        self.clock = sdk.MonotonicClock()

    def write(self, text):
        try:
            self.out.write(text)
            self.out.flush()
        except (OSError, ValueError):
            pass

    def size(self):
        return self.caps.width, self.caps.height


def transition(term, title, left=0):
    """The screen title typed in, with a whoosh."""
    play('whoosh')
    sdk.inline.type_line(term.caps, term.colors, term.write, term.clock, title, left, LOGO)


def result(term, ok, text, left=0):
    """A check result: a mark that sparkles once, then stays."""
    play('net_ok' if ok else 'net_fail')
    sdk.inline.result_line(term.caps, term.colors, term.write, term.clock, ok, text, left)


def warn(term, text, left=0):
    """The disk commit warning: three red pulses with the klaxon; the text stays bold red."""
    play('warn')
    sdk.inline.pulse_line(term.caps, term.colors, term.write, term.clock, text, left)


class Cheer(sdk.Scene):
    """Sparkles around a title, a happy mascot, fireworks. Decorative, short, and over by itself."""

    def __init__(self, title, subtitle=''):
        self.title, self.subtitle = title, subtitle
        self.age = 0.0

    def start(self, ctx):
        self.top = max(1, ctx.height // 2 - 4)
        self.fireworks = Fireworks(ctx.width, max(1, self.top + 6))
        self.duration = 0.0 if ctx.reduced else 1.6

    def update(self, dt, ctx, actions):
        self.age += dt
        if not ctx.reduced:
            self.fireworks.step(1 / 15)
        self.done = self.age >= self.duration  # reduced motion: one frame, then done

    def draw(self, canvas, ctx):
        width, top = canvas.width, self.top
        if not ctx.reduced:
            for x, y, char, color in self.fireworks.cells(ctx.glyphs.unicode):
                if 0 <= x < width - 1 and 0 <= y < canvas.height - 1:
                    canvas.put(x, y, char, (color, None, False))
        canvas.sprite(max(0, (width - MASCOT_W) // 2), top - 6, mascot_frame('happy', ctx.glyphs.unicode),
                      lambda char, row, col: (mascot_style(char, row, col), None, True), transparent=None)
        sdk_effects.gradient_text(canvas, max(0, (width - len(self.title)) // 2), top, self.title, LOGO,
                                  self.age * 0.6)
        if self.subtitle:
            canvas.put(max(0, (width - len(self.subtitle)) // 2), top + 2, self.subtitle, (GRAY, None, False))

    def plain_lines(self, ctx):
        return [self.title] + ([self.subtitle] if self.subtitle else [])


def cheer(term, title, subtitle=''):
    """A short celebration: sparkles around a title, the greeting chime, a happy mascot."""
    play('greeting')
    caps = term.caps
    sdk.run_scene(Cheer(title, subtitle), caps, term.out, sdk.NoInput(), clock=term.clock, fps=15, keep=True)
    if not caps.plain:
        top = max(1, caps.height // 2 - 4)
        term.write(f'\033[{min(caps.height, top + 5)};1H\033[?25h' + term.colors.sgr())


class Attract(sdk.Scene):
    """The welcome screen's idle animation while it waits for Return.

    The logo's colors drift slowly and the mascot blinks and looks around. It is
    decorative only: the screen is waiting for the operator, and says so.
    """

    def __init__(self, logo, mascot_x):
        self.logo, self.mascot_x, self.age = logo, mascot_x, 0.0
        self.mascot_y = max(0, len(logo) - MASCOT_H)

    def update(self, dt, ctx, actions):
        self.age += dt

    def draw(self, canvas, ctx):
        shift = 0.0 if ctx.reduced else self.age * 0.08
        for row, text in enumerate(self.logo):
            t = (row / max(1, len(self.logo) - 1) + shift) % 2.0
            t = 2.0 - t if t > 1.0 else t
            canvas.put(0, row, text, (sdk.gradient(LOGO, t), None, True))
        if self.mascot_x is not None:
            expression = mascot_expression(self.age, 'waiting', reduced=ctx.reduced)
            canvas.sprite(self.mascot_x, self.mascot_y, mascot_frame(expression, ctx.glyphs.unicode),
                          lambda char, row, col: (mascot_style(char, row, col), None, True), transparent=None)


def attract(term, logo_path, top=1, tagline_row=None):
    if term.plain:
        return
    try:
        logo = [row.rstrip('\n') for row in Path(logo_path).read_text(encoding='utf-8').splitlines()][:24]
    except (OSError, UnicodeError):
        return
    width, _height = term.size()
    logo_w = max((len(row) for row in logo), default=0)
    left = max(0, (width - logo_w) // 2)
    mascot_x = logo_w + 3 if left + logo_w + 3 + MASCOT_W < width else None
    region_w = (mascot_x + MASCOT_W) if mascot_x is not None else logo_w
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    # An overlay: only the logo and mascot cells are drawn, and the host's own text and cursor are left alone.
    screen = sdk.Screen(term.out, term.colors, origin=(left, top - 1), full=False, size=(max(1, region_w), len(logo)))
    sdk.run_scene(Attract(logo, mascot_x), term.caps, term.out, sdk.NoInput(), clock=term.clock,
                  fps=1.0 if term.reduced else 8.0, preempt=lambda: bool(stop), screen=screen, keep=True)
    term.write(term.colors.sgr())


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__.strip())
        return 0
    try:
        term = Term()
        command, rest = argv[0], argv[1:]
        left = 0
        if '--left' in rest:
            index = rest.index('--left')
            try:
                left = int(rest[index + 1])
            except (IndexError, ValueError):
                left = 0
            del rest[index:index + 2]
        if command == 'transition' and rest:
            transition(term, ' '.join(rest), left)
        elif command == 'result' and len(rest) >= 2:
            result(term, rest[0] in ('ok', '0'), ' '.join(rest[1:]), left)
        elif command == 'warn' and rest:
            warn(term, ' '.join(rest), left)
        elif command == 'cheer' and rest:
            cheer(term, rest[0], ' '.join(rest[1:]))
        elif command == 'attract':
            logo, top = None, 1
            if '--logo' in rest:
                logo = rest[rest.index('--logo') + 1]
            if '--top' in rest:
                top = int(rest[rest.index('--top') + 1])
            if logo:
                attract(term, logo, top)
    except Exception:  # noqa: BLE001 - a flourish never fails the installer.
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
