#!/usr/bin/env python3
"""Read-only installer screen. Counters come from events, never elapsed time.

The screen shows the install engine's stage timeline, measured counters, a
ticker of the packages native pkg reports, and live activity from kernel
counters (disk, network, CPU, memory, ZFS). Motion on the screen comes only
from those real observations; there is no estimated percentage.

On the console the screen runs as window 0 of a locked-down tmux session
(install-screen): Ctrl-b opens splits and windows for the install log,
diagnostics, remote debugging and shells, so nothing needs function keys or
a virtual console switch.
"""
import argparse
import importlib.util
import math
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import termios
import time

HERE = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model = _load('daemonarchy_progress_model', 'progress-model.py')

# The live desktop's graphical installer imports these names from this file.
PHASES, clean, integer = model.PHASES, model.clean, model.integer
Progress, Tail, status = model.Progress, model.Tail, model.status
STYLES = ('spectrum', 'scope', 'bars')


def lines(state, style, width, idle=False, result=None):
    """Plain status rows: the plain/serial view and the final summary."""
    width = max(1, min(width, 240))
    output = ['DAEMONARCHY / ' + style.upper(), model.title(state, result)]
    if state.meter:
        label, current, total, unit = state.meter
        output.append(f'{label}: {current:,} / {total:,} {unit}')
        length = max(1, min(48, width - 2))
        filled = current * length // total
        if style == 'spectrum':
            peak = max(state.history, default=1)
            output.append('Measured changes:')
            output.append(''.join(' .:-=+*#%'[min(8, delta * 8 // peak)] for delta in state.history))
        elif style == 'scope':
            peak = max(state.history, default=1)
            output.append('Measured changes:')
            output.append(''.join('_' if delta * 2 < peak else '^' for delta in state.history))
        else:
            output.append('[' + '#' * filled + '.' * (length - filled) + ']')
    else:
        output.append('No measured total for this stage')
    if state.item:
        output.append(state.item)
    if state.fetch and state.phase == 'fetch':
        output.append(model.fetch_text(dict(state.fetch, estimate=state.fetch_estimate)))
    if state.warning:
        output.append('Progress unavailable: ' + state.warning)
    elif idle and result is None:
        output.append('Waiting for the next progress report')
    if result is None:
        output.append('Meters describe observed work; installation is still running.')
    elif result != 0:
        output.extend(state.recent)
    return [clean(line, width) for line in output]


# ------------------------------------------------------------------ color

# FreeBSD vt(4)'s default palette (sys/dev/vt/colors/vt_termcolors.c), in ANSI order.
VT16 = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (196, 161, 0), (51, 102, 163), (128, 0, 128), (0, 128, 128),
        (191, 191, 191), (46, 51, 54), (255, 0, 0), (0, 255, 0), (255, 255, 0), (115, 158, 207),
        (255, 0, 255), (0, 255, 255), (255, 255, 255)]


def color_depth(env, console):
    """none, 8, 16, 256 or truecolor.

    vt(4) parses 38;5;N but quantizes it to its 16-color palette, and it does
    not implement 38;2;R;G;B: teken reads R, G and B as separate attributes
    (bold, underline, blink, reverse...). The console therefore gets direct
    16-color output, and truecolor is never sent to it.
    """
    forced = env.get('DAEMONARCHY_COLOR', '')
    term = env.get('TERM', '')
    if 'NO_COLOR' in env or forced == 'none':
        return 'none'
    if forced in ('8', '16', '256'):
        depth = forced
    elif forced == 'truecolor':
        depth = 'truecolor'
    elif term in ('vt100', 'vt102', 'vt220', 'ansi', 'cons25') or term.startswith('vt'):
        depth = '8'
    elif '256color' in term:
        depth = '256'
        if env.get('COLORTERM', '').lower() in ('truecolor', '24bit'):
            depth = 'truecolor'
    else:
        depth = '16'
    if console and depth in ('256', 'truecolor'):
        depth = '16'
    return depth


class Colors:
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

    def sgr(self, style):
        """style = (fg, bg, bold), colors as RGB tuples or None."""
        if style in self.cache:
            return self.cache[style]
        fg, bg, bold = style
        codes = ['0']
        if bold:
            codes.append('1')
        if self.depth != 'none':
            for rgb, base in ((fg, 30), (bg, 40)):
                if rgb is None:
                    continue
                if self.depth == 'truecolor':
                    codes.append(f'{base + 8};2;{rgb[0]};{rgb[1]};{rgb[2]}')
                elif self.depth == '256':
                    codes.append(f'{base + 8};5;{self.xterm256(rgb)}')
                elif self.depth == '16':
                    index = self.nearest(rgb, VT16)
                    codes.append(str(base + index if index < 8 else base + 60 + index - 8))
                else:
                    codes.append(str(base + self.nearest(rgb, VT16[:8])))
        value = '\033[' + ';'.join(codes) + 'm'
        self.cache[style] = value
        return value


# ------------------------------------------------------------------ glyphs

class Glyphs:
    def __init__(self, unicode):
        self.unicode = unicode
        if unicode:
            self.levels = ' ▁▂▃▄▅▆▇█'
            self.h, self.v = '─', '│'
            self.corners = '╭╮╰╯'
            self.full, self.empty, self.cap = '█', '░', '▀'
            self.icons = dict(done='●', active='▶', pending='○', skipped='·', failed='✗')
            self.dot = '·'
        else:
            self.levels = ' .:-=+*#%'
            self.h, self.v = '-', '|'
            self.corners = '++++'
            self.full, self.empty, self.cap = '#', '.', '-'
            self.icons = dict(done='*', active='>', pending='o', skipped='-', failed='x')
            self.dot = '|'


def unicode_ok(env, console):
    forced = env.get('DAEMONARCHY_GLYPHS', '')
    if forced in ('ascii', 'unicode'):
        return forced == 'unicode'
    term = env.get('TERM', '')
    if term in ('vt100', 'vt102', 'vt220', 'ansi', 'cons25', 'dumb'):
        return False
    if console:
        return True  # vt(4) is UTF-8 and its fonts carry block, box and braille glyphs.
    locale = ' '.join(env.get(name, '') for name in ('LC_ALL', 'LC_CTYPE', 'LANG')).upper()
    return 'UTF-8' in locale or 'UTF8' in locale


# ------------------------------------------------------------------ canvas

class Canvas:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.chars = [[' '] * width for _ in range(height)]
        self.styles = [[None] * width for _ in range(height)]

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

    def fill(self, x, y, w, h, char=' ', style=None):
        for row in range(max(0, y), min(self.height, y + h)):
            self.put(x, row, char * max(0, w), style)

    @staticmethod
    def serialize(chars, styles, colors):
        parts, current = [], object()
        for char, style in zip(chars, styles):
            if style != current:
                parts.append(colors.sgr(style or (None, None, False)))
                current = style
            parts.append(char)
        return ''.join(parts)

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
                last = next(i for i in range(self.width - 1, -1, -1) if chars[i] != old_chars[i] or styles[i] != old_styles[i])
            else:
                first, last = 0, self.width - 1
            if y == self.height - 1:
                last = min(last, self.width - 2)  # Never write the bottom-right cell: some terminals scroll.
            if last < first:
                continue
            out.append(f'\033[{y + 1};{first + 1}H' + self.serialize(chars[first:last + 1], styles[first:last + 1], colors) + '\033[0m')
        return out

    def plain(self):
        return [''.join(row) for row in self.chars]


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def gradient(stops, t):
    # Quantized to 12 steps so neighbouring cells share one color sequence.
    t = round(max(0.0, min(1.0, t)) * 12) / 12
    span = len(stops) - 1
    index = min(span - 1, int(t * span))
    return mix(stops[index], stops[index + 1], t * span - index)


WINAMP = ((0, 210, 70), (180, 230, 0), (255, 220, 0), (255, 120, 0), (255, 40, 40))
SCOPE = ((0, 220, 255), (120, 120, 255), (255, 60, 220))
LOGO = ((255, 70, 70), (230, 50, 140), (132, 93, 249))
WHITE, GRAY, DIM = (240, 240, 240), (150, 150, 150), (90, 90, 100)
CYAN, GREEN, RED, YELLOW, PURPLE = (0, 230, 255), (0, 220, 90), (255, 60, 60), (255, 220, 0), (132, 93, 249)


def norm_rate(value, peak, floor):
    peak = max(peak, floor)
    if value <= 0:
        return 0.0
    return max(0.0, min(1.0, math.log1p(value / floor) / math.log1p(peak / floor)))


# ------------------------------------------------------------------ visuals

class Visuals:
    """Draw a snapshot. Animation state only smooths and decays real samples."""

    def __init__(self, glyphs, reduced=False, logo=None):
        self.g = glyphs
        self.reduced = reduced
        self.logo = logo or []
        self.shown = {}
        self.caps = {}
        self.cap_hold = {}
        self.ticker_text = ''
        self.ticker_serial = 0
        self.ticker_shift = 0.0
        self.last = time.monotonic()

    def advance(self, snap):
        now = time.monotonic()
        dt = max(0.0, min(0.5, now - self.last))
        self.last = now
        for key, target in self.targets(snap).items():
            if self.reduced:
                self.shown[key] = target
                self.caps[key] = target
                continue
            value = self.shown.get(key, 0.0)
            rate = 14.0 if target > value else 4.0
            value += (target - value) * min(1.0, dt * rate)
            self.shown[key] = value
            cap = self.caps.get(key, 0.0)
            if value >= cap:
                self.caps[key], self.cap_hold[key] = value, now + 0.8
            elif now > self.cap_hold.get(key, 0):
                self.caps[key] = max(value, cap - dt * 0.6)
        ticker = snap['ticker']
        if ticker['serial'] != self.ticker_serial:
            text = f'  {self.g.dot}  '.join(ticker['names'])
            added = len(text) - len(self.ticker_text) if text.startswith(self.ticker_text[:8]) else len(text)
            self.ticker_serial, self.ticker_text = ticker['serial'], text
            if not self.reduced:
                self.ticker_shift = min(80.0, self.ticker_shift + max(0, added))
        if self.ticker_shift:
            self.ticker_shift *= math.exp(-dt * 5.0)
            if self.ticker_shift < 0.5 or self.reduced:
                self.ticker_shift = 0.0

    def targets(self, snap):
        activity = snap['activity']
        current, peaks = activity['current'], activity['peaks']
        targets = {}
        cores = current.get('cores', [])
        # More than eight cores are averaged in groups of neighbours (C0+ = cores 0..n-1).
        group = max(1, math.ceil(len(cores) / 8))
        for index in range(0, len(cores), group):
            chunk = cores[index:index + group]
            targets[f'cpu{index}'] = sum(chunk) / len(chunk)
        for key, floor in (('disk_write', 1 << 20), ('disk_read', 1 << 20), ('zfs_write', 1 << 20),
                           ('iops', 50.0), ('net_rx', 64 << 10), ('net_tx', 64 << 10)):
            if key in current:
                targets[key] = norm_rate(current[key], peaks.get(key, 0.0), floor)
        return targets

    def bands(self, snap):
        current = snap['activity']['current']
        cores = len(current.get('cores', []))
        group = max(1, math.ceil(cores / 8))
        bands = [(f'cpu{i}', f'C{i}' if group == 1 else f'C{i}+') for i in range(0, cores, group)]
        bands += [('disk_write', 'W'), ('disk_read', 'R'), ('iops', 'IO'), ('net_rx', 'Rx'), ('net_tx', 'Tx')]
        if 'zfs_write' in current:
            bands.append(('zfs_write', 'Z'))
        return [band for band in bands if band[0] in self.shown]

    # -- widgets

    def box(self, canvas, x, y, w, h, title, color, focused=False):
        if w < 4 or h < 2:
            return
        g = self.g
        style = (color, None, focused)
        canvas.put(x, y, g.corners[0] + g.h * (w - 2) + g.corners[1], style)
        for row in range(y + 1, y + h - 1):
            canvas.put(x, row, g.v, style)
            canvas.put(x + w - 1, row, g.v, style)
        canvas.put(x, y + h - 1, g.corners[2] + g.h * (w - 2) + g.corners[3], style)
        if title:
            canvas.put(x + 2, y, f' {title} '[:w - 4], (WHITE if focused else color, None, True))

    def spectrum(self, canvas, x, y, w, h, snap):
        bands = self.bands(snap)
        if not bands or w < 4 or h < 3:
            canvas.put(x, y, 'Live activity unavailable'[:w], (GRAY, None, False))
            return
        rows = h - 1
        gap = 1 if w >= len(bands) * 3 else 0
        width = max(1, (w - gap * (len(bands) - 1)) // len(bands))
        levels = self.g.levels
        for index, (key, label) in enumerate(bands):
            left = x + index * (width + gap)
            if left + width > x + w:
                break
            value = self.shown.get(key, 0.0) * rows
            cap = self.caps.get(key, 0.0) * rows
            for row in range(rows):
                screen_y = y + rows - 1 - row
                fill = value - row
                color = gradient(WINAMP, row / max(1, rows - 1))
                if fill >= 1:
                    char = levels[-1]
                elif fill > 0:
                    char = levels[max(1, int(fill * (len(levels) - 1)))]
                elif not self.reduced and int(cap) == row and cap > 0.15 and cap > value + 0.5:
                    char, color = self.g.cap, WHITE
                else:
                    char = ' '
                canvas.put(left, screen_y, char * width, (color, None, False))
            canvas.put(left, y + rows, label[:width].center(width), (GRAY, None, False))

    def trace(self, canvas, x, y, w, h, values, colors, floor):
        if w < 2 or h < 1:
            return
        if self.g.unicode:
            dots_w, dots_h = w * 2, h * 4
        else:
            dots_w, dots_h = w, h * 3
        data = list(values)[-dots_w:]
        top = max(max(data, default=0.0), floor)
        data = [None] * (dots_w - len(data)) + data
        cells = {}
        previous = None
        for dx, value in enumerate(data):
            if value is None:
                continue
            level = norm_rate(value, top, floor * 0.25)
            dy = int(round((1 - level) * (dots_h - 1)))
            span = range(min(dy, previous), max(dy, previous) + 1) if previous is not None else (dy,)
            previous = dy
            for py in span:
                cells.setdefault((dx // (2 if self.g.unicode else 1), py // (4 if self.g.unicode else 3)), []).append((dx, py))
        for (cx, cy), points in cells.items():
            color = gradient(colors, 1 - cy / max(1, h - 1))
            if self.g.unicode:
                mask = 0
                for dx, py in points:
                    bit = (0x01, 0x02, 0x04, 0x40, 0x08, 0x10, 0x20, 0x80)[(dx % 2) * 4 + py % 4]
                    mask |= bit
                char = chr(0x2800 + mask)
            else:
                char = '^-_'[points[-1][1] % 3] if len(points) == 1 else '|'
            canvas.put(x + cx, y + cy, char, (color, None, False))

    def scope(self, canvas, x, y, w, h, snap, which=('disk_write', 'net_rx')):
        history = snap['activity']['history']
        current = snap['activity']['current']
        labels = dict(disk_write='disk write', net_rx='network in', disk_read='disk read', zfs_write='ZFS logical write')
        floors = dict(disk_write=1 << 20, net_rx=64 << 10, disk_read=1 << 20, zfs_write=1 << 20)
        palettes = [SCOPE, ((255, 200, 0), (255, 90, 0), (255, 40, 120))]
        shown = [key for key in which if history.get(key)]
        if not shown:
            canvas.put(x, y, 'Waiting for activity samples'[:w], (GRAY, None, False))
            return
        each = max(1, h // len(shown))
        for index, key in enumerate(shown):
            top = y + index * each
            rows = each if index < len(shown) - 1 else h - index * each
            label = f'{labels[key]} {model.format_rate(current.get(key)).strip()}'
            canvas.put(x, top, label[:w], (WHITE, None, False))
            self.trace(canvas, x, top + 1, w, rows - 1, history[key], palettes[index % 2], floors[key])

    def gauges(self, canvas, x, y, w, h, snap):
        current = snap['activity']['current']
        rows = []
        cores = current.get('cores', [])
        if cores:
            rows.append(('CPU', sum(cores) / len(cores), f'{sum(cores) / len(cores) * 100:3.0f}% of {len(cores)}'))
        for key, label, unit in (('disk_write', 'Disk W', 'B/s'), ('disk_read', 'Disk R', 'B/s'),
                                 ('iops', 'IOPS', 'op/s'), ('net_rx', 'Net in', 'B/s'), ('net_tx', 'Net out', 'B/s'),
                                 ('zfs_write', 'ZFS', 'B/s')):
            if key in current:
                text = f'{current[key]:7.0f} op/s' if key == 'iops' else model.format_rate(current[key], unit)
                rows.append((label, self.shown.get(key, 0.0), text))
        for index, (label, value, text) in enumerate(rows[:h]):
            bar = max(1, w - 23)
            filled = int(round(value * bar))
            canvas.put(x, y + index, f'{label:<8}', (GRAY, None, False))
            for i in range(bar):
                color = gradient(WINAMP, i / max(1, bar - 1))
                canvas.put(x + 8 + i, y + index, self.g.full if i < filled else self.g.empty,
                           (color if i < filled else DIM, None, False))
            canvas.put(x + 9 + bar, y + index, text[:14], (WHITE, None, False))

    def banner(self, canvas, x, y, w, h):
        if self.logo and h >= len(self.logo) and w >= max(len(row) for row in self.logo):
            for index, row in enumerate(self.logo):
                color = gradient(LOGO, index / max(1, len(self.logo) - 1))
                canvas.put(x + (w - max(len(r) for r in self.logo)) // 2, y + index, row, (color, None, True))
            return len(self.logo)
        text = ' D A E M O N A R C H Y ' if w >= 40 else 'DAEMONARCHY'
        for index, char in enumerate(text[:w]):
            canvas.put(x + index, y, char, (gradient(LOGO, index / max(1, len(text) - 1)), None, True))
        return 1

    def timeline(self, canvas, x, y, w, h, snap):
        items = []
        for row in snap['stages']:
            elapsed = model.format_elapsed(row['elapsed']) if row['elapsed'] is not None else ''
            items.append((row, f"{self.g.icons[row['state']]} {row['label']}" + (f' {elapsed}' if elapsed else '')))
        colors = dict(done=GREEN, active=CYAN, failed=RED, skipped=DIM, pending=GRAY)
        lines_, line, used = [], [], 0
        for row, text in items:
            if used and used + 2 + len(text) > w:
                lines_.append(line)
                line, used = [], 0
            line.append((row, text))
            used += len(text) + (2 if used else 0)
        if line:
            lines_.append(line)
        if len(lines_) > h:
            active = next((i for i, l in enumerate(lines_) if any(r['state'] == 'active' for r, _ in l)), 0)
            start = max(0, min(active, len(lines_) - h))
            lines_ = lines_[start:start + h]
        for index, line in enumerate(lines_):
            cx = x
            for row, text in line:
                canvas.put(cx, y + index, text, (colors[row['state']], None, row['state'] in ('active', 'failed')), w - (cx - x))
                cx += len(text) + 2
        return len(lines_)

    def status(self, canvas, x, y, w, h, snap):
        rows = []
        done = snap['result'] is not None
        title_color = (GREEN if snap['succeeded'] else RED) if done else WHITE
        elapsed = model.format_elapsed(snap['elapsed']) if snap['elapsed'] else ''
        rows.append([(snap['title'], (title_color, None, True)),
                     (f'   elapsed {elapsed}' if elapsed and not done else '', (GRAY, None, False))])
        meter = snap['meter']
        if meter:
            text = f"{meter['label']}: {meter['current']:,} / {meter['total']:,} {meter['unit']}"
            bar = max(0, min(40, w - len(text) - 4))
            parts = [(text, (WHITE, None, False))]
            if bar >= 6:
                filled = meter['current'] * bar // meter['total']
                parts.append(('  ', None))
                for i in range(bar):
                    color = gradient(WINAMP[:3], i / max(1, bar - 1)) if i < filled else DIM
                    parts.append((self.g.full if i < filled else self.g.empty, (color, None, False)))
            rows.append(parts)
        else:
            rows.append([('No measured total for this stage; live activity is shown below', (GRAY, None, False))])
        if snap['item']:
            rows.append([(snap['item'], (CYAN, None, False))])
        if snap.get('fetch') and snap['phase'] == 'fetch':
            rows.append([(model.fetch_text(snap['fetch']), (PURPLE, None, False))])
        if snap['warning']:
            rows.append([('Progress unavailable: ' + snap['warning'], (YELLOW, None, True))])
        elif snap['idle'] >= 5 and not done:
            rows.append([('Waiting for the next progress report; activity below is live', (YELLOW, None, False))])
        if not done:
            rows.append([('Meters describe observed work; installation is still running.', (DIM, None, False))])
        for index, parts in enumerate(rows[:h]):
            cx = x
            for text, style in parts:
                canvas.put(cx, y + index, text, style, w - (cx - x))
                cx += len(text)
        return min(h, len(rows))

    def metrics(self, canvas, x, y, w, h, snap):
        activity = snap['activity']
        current = activity['current']
        target = snap['target']
        rows = []
        if not activity['available'] or not current:
            rows.append([(activity['error'] or 'Collecting activity samples...', (GRAY, None, False))])
        else:
            disk = target['disk'] or ','.join(current.get('disks', [])[:3]) or 'disks'
            rate = model.format_rate
            row = [('Disk ', (GRAY, None, False)), (f'{disk:<6}', (WHITE, None, True)),
                   (' write ', (GRAY, None, False)), (rate(current.get('disk_write')), (WINAMP[3], None, True)),
                   ('  read ', (GRAY, None, False)), (rate(current.get('disk_read')), (WINAMP[1], None, False)),
                   (f"  {current.get('iops', 0):,.0f} IO/s", (WHITE, None, False))]
            if 'zfs_write' in current and target['pool']:
                row += [('  ZFS ', (GRAY, None, False)), (target['pool'], (WHITE, None, False)),
                        (' ' + rate(current['zfs_write']).strip() + ' logical', (PURPLE, None, False))]
            rows.append(row)
            rows.append([('Net  ', (GRAY, None, False)), (f"{current.get('interface') or '-':<6}", (WHITE, None, True)),
                         (' in    ', (GRAY, None, False)), (rate(current.get('net_rx')), (CYAN, None, True)),
                         ('  out  ', (GRAY, None, False)), (rate(current.get('net_tx')), (CYAN, None, False))])
            cores = current.get('cores', [])
            memory = current.get('memory', {})
            gib = 1 << 30
            row = [('CPU  ', (GRAY, None, False)),
                   (f"{len(cores)} cores {sum(cores) / max(1, len(cores)) * 100:3.0f}%", (WHITE, None, False))]
            if memory.get('total'):
                row += [('   Memory ', (GRAY, None, False)),
                        (f"{memory['used'] / gib:.1f} of {memory['total'] / gib:.1f} GiB", (WHITE, None, False))]
            if memory.get('arc'):
                row += [('   ARC ', (GRAY, None, False)), (f"{memory['arc'] / gib:.1f} GiB", (PURPLE, None, False))]
            rows.append(row)
            if target['encrypted']:
                rows.append([('GELI AES-XTS: every pool write shown above is encrypted on ' + (target['disk'] or 'the target'),
                              (PURPLE, None, False))])
        for index, parts in enumerate(rows[:h]):
            cx = x
            for text, style in parts:
                canvas.put(cx, y + index, text, style, w - (cx - x))
                cx += len(text)
        return min(h, len(rows))

    def ticker(self, canvas, x, y, w, h, snap):
        ticker = snap['ticker']
        if not ticker['names']:
            return 0
        verb = 'Installing' if ticker['kind'] == 'install' else 'Downloaded'
        rate = f"  {ticker['rate']:.0f}/min" if ticker['rate'] else ''
        label = f"{verb} {ticker['current']:,}/{ticker['total']:,}{rate} "
        canvas.put(x, y, label, (YELLOW, None, True), w)
        room = w - len(label)
        if room <= 4:
            return 1
        text = self.ticker_text
        shift = int(self.ticker_shift)
        visible = (text + ' ' * shift)[-room:] if len(text) + shift >= room else (text + ' ' * shift).rjust(room)[-room:]
        for index, char in enumerate(visible):
            fade = round(index / max(1, room - 1) * 4) / 4
            canvas.put(x + len(label) + index, y, char, (mix(DIM, WHITE, fade), None, False))
        return 1

    def draw(self, canvas, x, y, w, h, snap, style):
        """The progress view in any rectangle; sections drop as space shrinks."""
        if w < 10 or h < 1:
            return
        top = y
        bottom = y + h
        # Always: the stage, then measured counters; everything else as room allows.
        visual_min = 6
        want_logo = self.logo and h >= len(self.logo) + 34 and w >= 75
        if want_logo:
            y += self.banner(canvas, x, y, w, len(self.logo)) + 1
        elif h >= 14:
            y += self.banner(canvas, x, y, w, 1)
        y += self.timeline(canvas, x, y, w, 2 if h >= 12 else 1, snap)
        if y < bottom:
            y += self.status(canvas, x, y, w, max(1, min(5, bottom - y - (6 if h >= 14 else 0))), snap)
        remaining = bottom - y
        ticker_rows = 1 if snap['ticker']['names'] and remaining >= 2 else 0
        metric_rows = min(4, max(0, remaining - ticker_rows - (visual_min if remaining >= visual_min + 4 else 0)))
        visual_rows = remaining - ticker_rows - metric_rows - (1 if remaining > 12 else 0)
        if visual_rows >= 4 and w >= 20:
            gap = 1 if remaining > 12 else 0
            y += gap + self.visual(canvas, x, y + gap, w, visual_rows, snap, style)
        if metric_rows:
            y += self.metrics(canvas, x, y, w, metric_rows, snap)
        if ticker_rows and y < bottom:
            # Directly under the meters; a spare row first when there is room.
            self.ticker(canvas, x, min(bottom - 1, y + 1), w, 1, snap)
        del top

    def visual(self, canvas, x, y, w, h, snap, style):
        h = min(h, 24)
        if style == 'bars':
            self.gauges(canvas, x, y, w, h, snap)
        elif style == 'scope':
            if w >= 70:
                left = w * 2 // 3
                self.box(canvas, x, y, left - 1, h, 'Scope: real disk and network rates', SCOPE[1])
                self.scope(canvas, x + 1, y + 1, left - 3, h - 2, snap)
                self.box(canvas, x + left, y, w - left, h, 'Spectrum', WINAMP[1])
                self.spectrum(canvas, x + left + 1, y + 1, w - left - 2, h - 2, snap)
            else:
                self.scope(canvas, x, y, w, h, snap)
        else:
            if w >= 70:
                left = w * 11 // 20
                self.box(canvas, x, y, left - 1, h, 'Spectrum: CPU cores, disk, network', WINAMP[1])
                self.spectrum(canvas, x + 1, y + 1, left - 3, h - 2, snap)
                self.box(canvas, x + left, y, w - left, h, 'Scope', SCOPE[1])
                self.scope(canvas, x + left + 1, y + 1, w - left - 2, h - 2, snap)
            else:
                self.spectrum(canvas, x, y, w, h, snap)
        return h


# ------------------------------------------------------------------ input

KEYS = {b'\x1b[A': 'up', b'\x1b[B': 'down', b'\x1b[C': 'right', b'\x1b[D': 'left', b'\x1bOA': 'up',
        b'\x1bOB': 'down', b'\x1b[5~': 'pgup', b'\x1b[6~': 'pgdn', b'\x1b[H': 'home', b'\x1b[F': 'end',
        b'\x1b[1~': 'home', b'\x1b[4~': 'end', b'\x1b[Z': 'backtab'}


def decode_keys(buffer, final=False):
    """Split terminal input into keys. Returns (keys, unconsumed)."""
    keys = []
    while buffer:
        if buffer[:1] == b'\x1b':
            for sequence, name in KEYS.items():
                if buffer.startswith(sequence):
                    keys.append(name)
                    buffer = buffer[len(sequence):]
                    break
            else:
                match = re.match(rb'\x1b\[[0-9;?]*[ -/]*[@-~]|\x1bO.', buffer)
                if match:
                    buffer = buffer[match.end():]  # Unknown sequence: ignore.
                elif len(buffer) == 1 and not final:
                    break  # Maybe the start of a sequence; wait briefly.
                else:
                    keys.append('esc')
                    buffer = buffer[1:]
            continue
        byte = buffer[0]
        buffer = buffer[1:]
        if byte == 9:
            keys.append('tab')
        elif byte in (10, 13):
            keys.append('enter')
        elif byte == 3:
            keys.append('ctrl-c')
        elif 32 <= byte < 127:
            keys.append(chr(byte))
    return keys, buffer


# ------------------------------------------------------------------ tmux

class Tmux:
    """The installer's tmux session, when the screen runs inside one.

    Window controls (splits, windows, the log, diagnostics, remote debugging
    and shells) belong to tmux with its default Ctrl-b bindings; see
    install-screen and install-tmux.conf. This view only reads the session.
    """

    def __init__(self, env):
        self.active = bool(env.get('TMUX')) and bool(env.get('TMUX_PANE'))
        self.pane = env.get('TMUX_PANE', '')
        self.others = 0
        self.checked = 0.0

    def other_panes(self):
        if not self.active:
            return 0
        now = time.monotonic()
        if now - self.checked >= 1.0:
            self.checked = now
            try:
                output = subprocess.run(['tmux', 'list-panes', '-s', '-F', '#{pane_id}'], capture_output=True,
                                        text=True, timeout=2, check=False).stdout.split()
                self.others = len([pane for pane in output if pane != self.pane])
            except (OSError, subprocess.SubprocessError):
                self.others = 0
        return self.others


# ------------------------------------------------------------------ application

class App:
    def __init__(self, monitor, args, env, console, interactive, keyboard):
        self.monitor, self.args, self.env = monitor, args, env
        self.interactive, self.keyboard = interactive, keyboard
        self.reduced = env.get('DAEMONARCHY_REDUCED_MOTION', '').lower() in ('1', 'yes', 'true')
        style = args.style if args.style in STYLES else 'spectrum'
        self.style = 'bars' if self.reduced else style
        self.colors = Colors(color_depth(env, console) if interactive else 'none')
        self.glyphs = Glyphs(unicode_ok(env, console))
        self.visuals = Visuals(self.glyphs, self.reduced, self.load_logo() if interactive else [])
        self.tmux = Tmux(env)
        self.previous = None
        self.size = None
        self.message, self.message_until = '', 0.0
        self.interrupt_at = 0.0
        self.input = b''
        self.input_at = 0.0
        self.quit = None

    def load_logo(self):
        if not self.glyphs.unicode:
            return []
        try:
            path = Path(self.env.get('ISO_SHARE', '/usr/local/share/daemonarchy-installer')) / 'logo.txt'
            with path.open(encoding='utf-8') as stream:
                return [''.join(c for c in row if c.isprintable())[:240] for row in stream.read(8192).splitlines()[:20]]
        except (OSError, UnicodeError):
            return []

    def say(self, text, seconds=4.0):
        self.message, self.message_until = text, time.monotonic() + seconds

    def remote_status(self):
        state = Path(self.env.get('DAEMONARCHY_REMOTE_STATE', str(model.REMOTE_STATE)))
        public = Path(self.env.get('DAEMONARCHY_REMOTE_PUBLIC', str(model.REMOTE_PUBLIC)))
        return model.remote_debug(state, public)

    # -- input

    def read_input(self):
        try:
            data = os.read(sys.stdin.fileno(), 4096)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            self.keyboard = False
            return
        if not data:
            self.keyboard = False
            return
        self.input += data
        self.input_at = time.monotonic()
        self.handle_input()

    def handle_input(self, final=False):
        keys, self.input = decode_keys(self.input, final)
        for key in keys:
            self.key(key)

    def key(self, key):
        if key == 'ctrl-c':
            now = time.monotonic()
            if now - self.interrupt_at < 2:
                self.quit = 130
            else:
                self.interrupt_at = now
                self.say('The installation keeps running. Press Ctrl-C again to leave this screen.')
        elif key == 'v' and not self.reduced:
            self.style = STYLES[(STYLES.index(self.style) + 1) % len(STYLES)]
            self.say(f'Visual style: {self.style}')
        elif key in ('?', 'h'):
            self.say(self.keys_hint(), 8)

    def keys_hint(self):
        if self.tmux.active:
            return ('C-b c new window  C-b % / C-b " split  C-b G log  C-b H diagnostics  '
                    'C-b R remote debug  C-b ? all keys  v style')
        return 'v style. Window controls need tmux, which is not available here.'

    # -- frames

    def footer(self, snap):
        if time.monotonic() < self.message_until:
            return self.message, YELLOW
        remote = None
        try:
            remote = self.remote_status()
        except OSError:
            remote = None
        if remote and remote['pending']:
            where = 'press C-b R' if self.tmux.active else 'run remote-debug listen in a shell'
            return f'Remote agent pairing request waiting: {where} to review it', YELLOW
        if snap['result'] is not None and self.tmux.other_panes():
            return ('Installation finished. Close the other panes and windows to continue '
                    '(exit in a shell, C-b x, C-b &).'), GREEN
        return self.keys_hint(), GRAY

    def frame(self, width, height, snap):
        canvas = Canvas(width, height)
        self.visuals.draw(canvas, 0, 0, width, height - 1, snap, self.style)
        text, color = self.footer(snap)
        canvas.put(0, height - 1, text[:max(0, width - 1)], (color, None, False))
        return canvas

    def render(self, snap):
        size = os.get_terminal_size(sys.stdout.fileno())
        width, height = max(10, min(size.columns, 400)), max(3, min(size.lines, 200))
        out = []
        if (width, height) != self.size:
            self.size = (width, height)
            self.previous = None
            out.append('\033[0m\033[2J')
        self.visuals.advance(snap)
        canvas = self.frame(width, height, snap)
        out.extend(canvas.changes(self.previous, self.colors))
        self.previous = canvas
        if out:
            sys.stdout.buffer.write(''.join(out).encode('utf-8', 'replace'))
            sys.stdout.flush()

    def waiting_for_panes(self):
        return self.monitor.result is not None and self.tmux.other_panes() > 0


def run_plain(monitor, style):
    previous = None
    while True:
        monitor.poll()
        state = monitor.state
        idle = monitor.idle_seconds() >= 5
        key = state.key(), idle, monitor.result
        if key != previous:
            sys.stdout.write(' | '.join(lines(state, style, 120, idle, monitor.result)) + '\n')
            sys.stdout.flush()
            previous = key
        if monitor.result is not None:
            return monitor.result if monitor.result else (1 if state.warning or state.failed else 0)
        time.sleep(0.2)


def final_summary(monitor, style, width):
    state = monitor.state
    rows = lines(state, style, width, False, monitor.result)
    stages = [f"{row['label']} {model.format_elapsed(row['elapsed'])}" for row in state.timeline.rows()
              if row['state'] in ('done', 'failed', 'active')]
    if stages:
        rows.insert(2, clean('Stages: ' + ', '.join(stages), width))
    if monitor.result not in (None, 0):
        rows.append(clean('Full install log: ' + str(monitor.readers[0].path), width))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('log', type=Path)
    parser.add_argument('status', type=Path)
    parser.add_argument('--style', choices=('bars', 'spectrum', 'scope', 'plain'),
                        default=os.environ.get('DAEMONARCHY_PROGRESS_STYLE', 'spectrum'))
    parser.add_argument('--events', type=Path)
    parser.add_argument('--input-pin')
    parser.add_argument('--repository-pin')
    parser.add_argument('--exit-file', type=Path, help='record the exit status here (install-screen)')
    args = parser.parse_args(argv)
    if args.style not in ('bars', 'spectrum', 'scope', 'plain'):
        args.style = 'spectrum'
    if args.events and not all(re.fullmatch('[0-9a-f]{64}', pin or '') for pin in (args.input_pin, args.repository_pin)):
        parser.error('--events requires the exact input and repository SHA-256 pins')
    code, finished = run(args)
    # Only an observed installer result ends the tmux session; an interrupted
    # or crashed view is respawned by install-screen.
    if args.exit_file and finished:
        args.exit_file.write_text(f'{code}\n')
    return code


def run(args):
    env = dict(os.environ)
    pins = (args.input_pin, args.repository_pin) if args.events else None
    source = None if env.get('DAEMONARCHY_ACTIVITY') == 'off' else 'auto'
    monitor = model.Monitor(args.log, args.status, args.events, pins, source=source)
    interactive = args.style != 'plain' and sys.stdout.isatty() and env.get('TERM', '') not in ('', 'dumb')

    def stop(signum, _frame):
        raise InterruptedError(signum)
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, stop)

    if not interactive:
        try:
            return run_plain(monitor, args.style if args.style != 'plain' else 'bars'), True
        except InterruptedError as error:
            return 128 + error.args[0], False
        except (OSError, ValueError) as error:
            print('Dashboard unavailable: ' + clean(error), file=sys.stderr)
            return 1, False

    try:
        tty = os.ttyname(sys.stdout.fileno())
    except OSError:
        tty = ''
    console = env.get('DAEMONARCHY_CONSOLE', 'vt' if tty.startswith('/dev/ttyv') else '') == 'vt'
    keyboard = False
    saved = None
    try:
        keyboard = os.isatty(sys.stdin.fileno()) and os.ttyname(sys.stdin.fileno()) == tty
    except OSError:
        keyboard = False
    if keyboard:
        try:
            saved = termios.tcgetattr(sys.stdin.fileno())
            mode = termios.tcgetattr(sys.stdin.fileno())
            mode[0] &= ~(termios.IXON | termios.ICRNL)
            mode[3] &= ~(termios.ICANON | termios.ECHO | termios.ISIG | termios.IEXTEN)
            mode[6][termios.VMIN], mode[6][termios.VTIME] = 0, 0
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, mode)
        except termios.error:
            keyboard, saved = False, None
    app = App(monitor, args, env, console, True, keyboard)
    fps = 1.0 if app.reduced else max(1.0, min(20.0, float(env.get('DAEMONARCHY_FPS', '10') or 10)))
    code, finished = 1, False
    try:
        sys.stdout.write('\033[?1049h\033[?25l\033[2J')
        sys.stdout.flush()
        next_frame = 0.0
        while True:
            monitor.poll()
            now = time.monotonic()
            if now >= next_frame:
                started = time.monotonic()
                app.render(monitor.snapshot())
                cost = time.monotonic() - started
                # Bound CPU: never spend more than about a quarter of the time drawing.
                next_frame = now + max(1.0 / fps, cost * 4)
            if app.quit is not None:
                code = app.quit
                break
            if monitor.result is not None and not app.waiting_for_panes():
                state = monitor.state
                code = monitor.result if monitor.result else (1 if state.warning or state.failed else 0)
                finished = True
                app.render(monitor.snapshot())
                break
            timeout = max(0.0, min(next_frame - time.monotonic(), 0.1))
            if app.input and time.monotonic() - app.input_at > 0.05:
                app.handle_input(final=True)
            if keyboard:
                ready = select.select([sys.stdin.fileno()], [], [], timeout)[0]
                if ready:
                    app.read_input()
                    next_frame = 0.0
            else:
                time.sleep(timeout)
    except InterruptedError as error:
        code = 128 + error.args[0]
    except (OSError, ValueError) as error:
        sys.stdout.write('\033[0m\033[?25h\033[?1049l')
        print('Dashboard unavailable: ' + clean(error), file=sys.stderr)
        code = 1
        app = None
    finally:
        if saved is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, saved)  # TCSADRAIN waits for a pty reader
        sys.stdout.write('\033[0m\033[?25h\033[?1049l\n')
        if app is not None and monitor.result is not None:
            width = app.size[0] if app.size else 80
            sys.stdout.write('\n'.join(final_summary(monitor, app.style, width)) + '\n')
        sys.stdout.flush()
    return code, finished


if __name__ == '__main__':
    raise SystemExit(main())
