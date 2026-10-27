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
import random
import signal
import sys
import time

HERE = Path(__file__).resolve().parent

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

RED, MAGENTA, PURPLE = (255, 70, 70), (230, 50, 140), (132, 93, 249)
WHITE, YELLOW, GRAY, DIM = (240, 240, 240), (255, 220, 0), (150, 150, 150), (90, 90, 100)
GREEN, CYAN = (0, 220, 90), (0, 230, 255)
LOGO = (RED, MAGENTA, PURPLE)
SPARKS = (YELLOW, (255, 120, 0), CYAN, (255, 60, 220), GREEN, WHITE)


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


# ------------------------------------------------------------------ fireworks

class Fireworks:
    """Particle bursts for a successful result. Seeded, so recordings repeat."""

    def __init__(self, width, height, seed=1993):
        self.width, self.height = max(1, width), max(1, height)
        self.random = random.Random(seed)
        self.particles = []
        self.next_burst = 0.0
        self.age = 0.0

    def burst(self):
        r = self.random
        x, y = r.uniform(0.15, 0.85) * self.width, r.uniform(0.15, 0.6) * self.height
        color = r.choice(SPARKS)
        for index in range(18):
            angle = 2 * math.pi * index / 18 + r.uniform(-0.1, 0.1)
            speed = r.uniform(6, 14)
            self.particles.append([x, y, math.cos(angle) * speed, math.sin(angle) * speed * 0.5,
                                   r.uniform(0.9, 1.6), color])

    def step(self, dt, spawning=True):
        self.age += dt
        if spawning and self.age >= self.next_burst:
            self.burst()
            self.next_burst = self.age + self.random.uniform(0.35, 0.7)
        alive = []
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 6.0 * dt  # gravity
            p[4] -= dt
            if p[4] > 0 and 0 <= p[0] < self.width and 0 <= p[1] < self.height:
                alive.append(p)
        self.particles = alive

    def cells(self, unicode=True):
        chars = ('☼', '*', '+', '·') if unicode else ('@', '*', '+', '.')
        for x, y, _vx, _vy, life, color in self.particles:
            stage = 0 if life > 1.2 else 1 if life > 0.8 else 2 if life > 0.4 else 3
            yield int(x), int(y), chars[stage], color if stage < 3 else DIM


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
    """Where and how to draw: color depth, glyphs, motion."""

    def __init__(self, env=None, stream=None):
        self.env = dict(os.environ if env is None else env)
        self.out = stream or sys.stdout
        term = self.env.get('TERM', '')
        self.tty = hasattr(self.out, 'isatty') and self.out.isatty()
        self.plain = (not self.tty or term in ('', 'dumb', 'vt100', 'vt102', 'vt220', 'ansi', 'cons25')
                      or self.env.get('DAEMONARCHY_CHARM') == 'off')
        self.reduced = self.env.get('DAEMONARCHY_REDUCED_MOTION', '').lower() in ('1', 'yes', 'true')
        try:
            tty = os.ttyname(self.out.fileno()) if self.tty else ''
        except (OSError, ValueError, AttributeError):
            tty = ''
        console = self.env.get('DAEMONARCHY_CONSOLE', 'vt' if tty.startswith('/dev/ttyv') else '') == 'vt'
        try:
            dashboard = _load('daemonarchy_progress_dashboard', 'progress-dashboard.py')
            depth = dashboard.color_depth(self.env, console) if not self.plain else 'none'
            self.colors = dashboard.Colors(depth)
            self.unicode = dashboard.unicode_ok(self.env, console)
            self.gradient = dashboard.gradient
        except Exception:  # noqa: BLE001
            self.colors, self.unicode, self.gradient = None, False, None

    def sgr(self, fg=None, bold=False, bg=None):
        if self.colors is None:
            return ''
        return self.colors.sgr((fg, bg, bold))

    def write(self, text):
        try:
            self.out.write(text)
            self.out.flush()
        except (OSError, ValueError):
            pass

    def size(self):
        try:
            size = os.get_terminal_size(self.out.fileno())
            return size.columns, size.lines
        except (OSError, ValueError, AttributeError):
            return 80, 24


def _sleep(seconds):
    if seconds > 0:
        time.sleep(seconds)


def transition(term, title, left=0):
    """The screen title typed in, with a whoosh."""
    play('whoosh')
    pad = ' ' * max(0, left)
    if term.plain or term.reduced:
        term.write(pad + title + '\n')
        return
    step = min(0.018, 0.3 / max(1, len(title)))
    term.write(pad)
    for index, char in enumerate(title):
        color = term.gradient(LOGO, index / max(1, len(title) - 1)) if term.gradient else None
        term.write(term.sgr(color, True) + char)
        _sleep(step)
    term.write(term.sgr() + '\n')


def result(term, ok, text, left=0):
    """A check result: a mark that sparkles once, then stays."""
    play('net_ok' if ok else 'net_fail')
    pad = ' ' * max(0, left)
    mark = ('√' if ok else '×') if term.unicode else ('ok' if ok else 'x')
    color = GREEN if ok else RED
    if term.plain or term.reduced:
        term.write(f'{pad}{mark} {text}\n')
        return
    sparkle = ('☼', '*', '+', mark) if term.unicode else ('*', '+', '.', mark)
    for index, char in enumerate(sparkle):
        last = index == len(sparkle) - 1
        term.write('\r' + pad + term.sgr(color if last else YELLOW, True) + char + term.sgr()
                   + ' ' + term.sgr(WHITE if last else GRAY) + text + term.sgr())
        _sleep(0 if last else 0.05)
    term.write('\n')


def warn(term, text, left=0):
    """The disk commit warning: three red pulses with the klaxon; the text stays bold red."""
    play('warn')
    pad = ' ' * max(0, left)
    mark = '▲' if term.unicode else '!'
    line = f' {mark} {text} {mark} '
    if term.plain or term.reduced:
        term.write(f'{pad}{line}\n')
        return
    for pulse in range(6):
        on = pulse % 2 == 0
        style = term.sgr(WHITE, True, RED) if on else term.sgr(RED, True)
        term.write('\r' + pad + style + line + term.sgr())
        _sleep(0.15)
    term.write('\r' + pad + term.sgr(WHITE, True, RED) + line + term.sgr() + '\n')


def cheer(term, title, subtitle=''):
    """A short celebration: sparkles around a title, the greeting chime, a happy mascot."""
    play('greeting')
    if term.plain:
        term.write(title + ('\n' + subtitle if subtitle else '') + '\n')
        return
    width, height = term.size()
    frame = mascot_frame('happy', term.unicode)
    top = max(1, height // 2 - 4)
    left = max(0, (width - len(title)) // 2)
    term.write('\033[?25l\033[2J')
    fireworks = Fireworks(width, max(1, top + 6))
    started = time.monotonic()
    duration = 0.0 if term.reduced else 1.6
    while True:
        now = time.monotonic() - started
        out = ['\033[H\033[2J'] if not term.reduced else ['\033[H']
        if not term.reduced:
            fireworks.step(1 / 15)
            for x, y, char, color in fireworks.cells(term.unicode):
                if 0 <= x < width - 1 and 0 <= y < height - 1:
                    out.append(f'\033[{y + 1};{x + 1}H' + term.sgr(color) + char)
        for row, text in enumerate(frame):
            out.append(f'\033[{top + row - 6};{max(1, (width - MASCOT_W) // 2)}H')
            out.extend(term.sgr(mascot_style(c, row, col), True) + c for col, c in enumerate(text))
        shift = now * 0.6
        out.append(f'\033[{top + 1};{left + 1}H')
        for index, char in enumerate(title):
            color = term.gradient(LOGO, (index / max(1, len(title) - 1) + shift) % 1.0) if term.gradient else None
            out.append(term.sgr(color, True) + char)
        if subtitle:
            out.append(f'\033[{top + 3};{max(1, (width - len(subtitle)) // 2 + 1)}H' + term.sgr(GRAY) + subtitle)
        out.append(term.sgr())
        term.write(''.join(out))
        if now >= duration:
            break
        _sleep(1 / 15)
    term.write(f'\033[{min(height, top + 5)};1H\033[?25h' + term.sgr())


def attract(term, logo_path, top=1, tagline_row=None):
    """The welcome screen's idle animation while it waits for Return.

    The logo's colors drift slowly and the mascot blinks and looks around.
    It is decorative only: the screen is waiting for the operator, and says so.
    """
    if term.plain:
        return
    try:
        logo = [row.rstrip('\n') for row in Path(logo_path).read_text(encoding='utf-8').splitlines()][:24]
    except (OSError, UnicodeError):
        return
    width, height = term.size()
    logo_w = max((len(row) for row in logo), default=0)
    left = max(0, (width - logo_w) // 2)
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    signal.signal(signal.SIGINT, lambda *_: stop.append(1))
    mascot_x = left + logo_w + 3 if left + logo_w + 3 + MASCOT_W < width else None
    mascot_y = top + max(0, len(logo) - MASCOT_H)
    previous = {}
    started = time.monotonic()
    fps = 1.0 if term.reduced else 8.0
    try:
        while not stop:
            now = time.monotonic() - started
            out = []
            shift = 0.0 if term.reduced else now * 0.08
            for row, text in enumerate(logo):
                t = (row / max(1, len(logo) - 1) + shift) % 2.0
                t = 2.0 - t if t > 1.0 else t
                color = term.gradient(LOGO, t) if term.gradient else None
                code = term.sgr(color, True)
                if previous.get(row) != code:  # Only rows whose color changed are redrawn.
                    previous[row] = code
                    out.append(f'\033[{top + row};{left + 1}H{code}{text}{term.sgr()}')
            if mascot_x is not None:
                expression = mascot_expression(now, 'waiting', reduced=term.reduced)
                if previous.get('mascot') != expression:
                    previous['mascot'] = expression
                    for row, text in enumerate(mascot_frame(expression, term.unicode)):
                        out.append(f'\033[{mascot_y + row};{mascot_x + 1}H')
                        out.extend(term.sgr(mascot_style(c, row, col), True) + c for col, c in enumerate(text))
                        out.append(term.sgr())
            if out:
                term.write(''.join(out))
            time.sleep(1 / fps)
    finally:
        term.write(term.sgr())


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
