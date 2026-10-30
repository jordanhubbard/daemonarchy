#!/usr/bin/env python3
"""Read-only installer screen. Counters come from events, never elapsed time.

The screen shows the install engine's stage timeline, measured counters, a
ticker of the packages native pkg reports, and live activity from kernel
counters (disk, network, CPU, memory, ZFS). Meters and graphs move only with
those real observations; there is no estimated percentage.

Flourishes follow the model's events: a stage card and a sound when a stage
starts, a sparkle when one finishes, a blip per reported package and a
fanfare with fireworks only for the installer's own successful result. The
banner shimmers at a pace set by measured activity, the mascot's trident
keeps time with it, and after a long genuine wait the mascot says so. Sound
(sound.py) is optional: m mutes, + and - set the volume, a toggles the
ambient layer; in tmux the same keys follow C-b.

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
# The visual SDK ships beside libexec (/usr/local/lib/daemonarchy-visual); this screen is its first consumer.
SDK_PATH = HERE.parents[1] / 'lib' / 'daemonarchy-visual'
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))
from daemonarchy_visual.caps import color_depth, unicode_ok  # noqa: E402
from daemonarchy_visual.canvas import Canvas, Screen  # noqa: E402
from daemonarchy_visual.glyphs import Glyphs  # noqa: E402
from daemonarchy_visual.input import KEYS, decode_keys  # noqa: E402
from daemonarchy_visual.palette import (CYAN, DIM, GRAY, GREEN, LOGO, PURPLE, RED, SCOPE, VT16, WHITE,  # noqa: E402
                                        WINAMP, YELLOW, Colors, gradient, mix)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


model = _load('daemonarchy_progress_model', 'progress-model.py')


def _optional(name, filename):
    """Sound and charm are extras: the screen works without them."""
    try:
        return _load(name, filename)
    except (OSError, ImportError, SyntaxError):
        return None


sound = _optional('daemonarchy_sound', 'sound.py')
charm = _optional('daemonarchy_charm', 'charm.py')

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


# Color, glyphs, the canvas and gradients come from the visual SDK (imported above).


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
        # Flourishes, each started by a model event (see effects()).
        self.seen = None
        self.card = None  # (label, started)
        self.flash = {}  # stage key -> until
        self.milestone = ('', 0.0)  # (text, until)
        self.note_until = 0.0
        self.shimmer = 0.0
        self.fireworks = None
        self.finale = None  # (succeeded, started)
        self.mood = 'idle'
        self.level = 0.0
        self.visual_box = None

    def effects(self, snap, now):
        """Start flourishes for events this screen has not shown yet."""
        events = snap.get('events') or []
        if self.seen is None:
            self.seen = max((e['serial'] for e in events), default=0)
            events = [e for e in events if e['kind'] == 'done']  # A late start shows only a known result.
        for event in events:
            if event['serial'] <= self.seen and event['kind'] != 'done':
                continue
            self.seen = max(self.seen, event['serial'])
            kind = event['kind']
            if kind == 'stage-start':
                self.card = (event.get('label', ''), now)
            elif kind == 'stage-done':
                self.flash[event.get('stage')] = now + 1.5
            elif kind == 'packages':
                self.note_until = now + 0.15
                if event.get('milestone'):
                    what = 'packages' if event.get('what') == 'install' else 'downloads'
                    self.milestone = (f"{event.get('current', 0):,} {what}", now + 2.0)
            elif kind == 'done' and self.finale is None:
                self.finale = (bool(event.get('succeeded')), now)
                self.card = None

    def advance(self, snap):
        now = time.monotonic()
        dt = max(0.0, min(0.5, now - self.last))
        self.last = now
        self.effects(snap, now)
        if self.finale and self.finale[0] and not self.reduced and self.fireworks is not None:
            self.fireworks.step(dt, spawning=now - self.finale[1] < 6.0)
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
        # The banner shimmer moves only as fast as the machine is measured to work.
        levels = [v for k, v in self.shown.items() if not k.startswith('cpu')] or [0.0]
        self.level = max(levels + [sum(v for k, v in self.shown.items() if k.startswith('cpu'))
                                   / max(1, len([k for k in self.shown if k.startswith('cpu')]))])
        if not self.reduced:
            self.shimmer += dt * 9.0 * self.level
        if snap.get('done'):
            self.mood = 'happy' if snap.get('succeeded') else 'sad'
        elif snap.get('idle', 0) >= model.WAITING:
            self.mood = 'waiting'
        else:
            self.mood = 'working'

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
            # The gradient drifts with measured activity; an idle machine leaves it still.
            for index, row in enumerate(self.logo):
                t = (index / max(1, len(self.logo) - 1) + self.shimmer * 0.02) % 2.0
                color = gradient(LOGO, 2.0 - t if t > 1.0 else t)
                canvas.put(x + (w - max(len(r) for r in self.logo)) // 2, y + index, row, (color, None, True))
            return len(self.logo)
        text = ' D A E M O N A R C H Y ' if w >= 40 else 'DAEMONARCHY'
        glint = int(self.shimmer) % (len(text) + 12) if not self.reduced and self.level > 0.02 else -99
        for index, char in enumerate(text[:w]):
            color = gradient(LOGO, index / max(1, len(text) - 1))
            if abs(index - glint) <= 1:
                color = WHITE if index == glint else mix(color, WHITE, 0.5)
            canvas.put(x + index, y, char, (color, None, True))
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
        now = time.monotonic()
        spark = '☼' if self.g.unicode else '*'
        for index, line in enumerate(lines_):
            cx = x
            for row, text in line:
                style = (colors[row['state']], None, row['state'] in ('active', 'failed'))
                if self.flash.get(row['key'], 0) > now and row['state'] == 'done':
                    # A finished stage sparkles briefly (the stage_done sound plays with it).
                    lit = self.reduced or int((self.flash[row['key']] - now) * 6) % 2 == 0
                    style = (WHITE if lit else GREEN, None, True)
                    text = spark + text[1:]
                canvas.put(cx, y + index, text, style, w - (cx - x))
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
        now = time.monotonic()
        note = ('♪' if self.g.unicode else '*') if now < self.note_until else ' '
        label = f"{note}{verb} {ticker['current']:,}/{ticker['total']:,}{rate} "
        canvas.put(x, y, label, (YELLOW, None, True), w)
        text, until = self.milestone
        if text and now < until:
            spark = '☼' if self.g.unicode else '*'
            banner = f' {spark} {text} {spark} '
            lit = self.reduced or int((until - now) * 5) % 2 == 0
            canvas.put(x + len(label), y, banner, (WHITE if lit else YELLOW, PURPLE if lit else None, True),
                       max(0, w - len(label)))
            label += banner
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
        full_w = w
        self.visual_box = None
        # Always: the stage, then measured counters; everything else as room allows.
        visual_min = 6
        want_logo = self.logo and h >= len(self.logo) + 34 and w >= 75
        mascot = None
        if charm and w >= 110 and h >= 20:
            # The mascot stands at the top right; the header text makes room for it.
            mascot = (x + w - charm.MASCOT_W, y + (len(self.logo) - charm.MASCOT_H if want_logo else 0))
            if not want_logo:
                w -= charm.MASCOT_W + 1
        if want_logo:
            y += self.banner(canvas, x, y, full_w if mascot is None else full_w - charm.MASCOT_W - 1,
                             len(self.logo)) + 1
        elif h >= 14:
            y += self.banner(canvas, x, y, w, 1)
        y += self.timeline(canvas, x, y, w, 2 if h >= 12 else 1, snap)
        if y < bottom:
            y += self.status(canvas, x, y, w, max(1, min(5, bottom - y - (6 if h >= 14 else 0))), snap)
        if mascot is not None:
            self.draw_mascot(canvas, *mascot, snap)
            y = max(y, mascot[1] + charm.MASCOT_H)
        w = full_w
        remaining = bottom - y
        ticker_rows = 1 if snap['ticker']['names'] and remaining >= 2 else 0
        metric_rows = min(4, max(0, remaining - ticker_rows - (visual_min if remaining >= visual_min + 4 else 0)))
        visual_rows = remaining - ticker_rows - metric_rows - (1 if remaining > 12 else 0)
        if visual_rows >= 4 and w >= 20:
            gap = 1 if remaining > 12 else 0
            used = self.visual(canvas, x, y + gap, w, visual_rows, snap, style)
            self.visual_box = (x, y + gap, w, used)
            y += gap + used
        if metric_rows:
            y += self.metrics(canvas, x, y, w, metric_rows, snap)
        if ticker_rows and y < bottom:
            # Directly under the meters; a spare row first when there is room.
            self.ticker(canvas, x, min(bottom - 1, y + 1), w, 1, snap)
        self.overlays(canvas, x, top, w, h, snap)

    # -- flourishes

    def draw_mascot(self, canvas, x, y, snap):
        expression = charm.mascot_expression(time.monotonic(), self.mood, self.level, self.reduced)
        for row, text in enumerate(charm.mascot_frame(expression, self.g.unicode)):
            for col, char in enumerate(text):
                canvas.put(x + col, y + row, char, (charm.mascot_style(char, row, col), None, True))

    def centered(self, canvas, box, row, text, style, frame_style):
        bx, by, bw, bh = box
        text = text[:max(0, bw - 6)]
        width = len(text) + 4
        left = bx + (bw - width) // 2
        g = self.g
        canvas.put(left, by + row - 1, g.corners[0] + g.h * (width - 2) + g.corners[1], frame_style)
        canvas.put(left, by + row, g.v + ' ' + text + ' ' + g.v, frame_style)
        canvas.put(left + 2, by + row, text, style)
        canvas.put(left, by + row + 1, g.corners[2] + g.h * (width - 2) + g.corners[3], frame_style)

    def overlays(self, canvas, x, y, w, h, snap):
        now = time.monotonic()
        box = self.visual_box
        spark = '☼' if self.g.unicode else '*'
        if self.finale:
            succeeded, started = self.finale
            area = box or (x, y, w, h)
            if succeeded:
                if self.fireworks is None and charm and not self.reduced:
                    self.fireworks = charm.Fireworks(area[2], area[3])
                if self.fireworks is not None:
                    for px, py, char, color in self.fireworks.cells(self.g.unicode):
                        canvas.put(area[0] + px, area[1] + py, char, (color, None, True))
                if area[3] >= 5:
                    t = (now - started) * 0.5
                    color = gradient(LOGO, (t % 2.0) if (t % 2.0) <= 1 else 2 - t % 2.0) if not self.reduced else GREEN
                    self.centered(canvas, area, area[3] // 2, f'{spark} Daemonarchy is installed {spark}',
                                  (WHITE, None, True), (color, None, True))
            elif area[3] >= 5:
                lit = self.reduced or now - started > 1.5 or int((now - started) * 4) % 2 == 0
                self.centered(canvas, area, area[3] // 2, snap['title'],
                              (WHITE if lit else RED, RED if lit else None, True), (RED, None, True))
            return
        if self.card and box and box[3] >= 5:
            label, started = self.card
            age = now - started
            if age < 1.6:
                text = f'{spark} {label} {spark}'
                if not self.reduced and age < 0.25:
                    keep = max(1, int(len(text) * age / 0.25))
                    middle = len(text) // 2
                    text = ' ' * (middle - keep // 2) + text[middle - keep // 2:middle - keep // 2 + keep]
                    text = text.ljust(len(f'{spark} {label} {spark}'))
                fade = (not self.reduced) and age > 1.3
                self.centered(canvas, box, 2, text, ((GRAY if fade else WHITE), None, True),
                              ((DIM if fade else CYAN), None, True))
            else:
                self.card = None
        if self.mood == 'waiting' and box and box[3] >= 4:
            idle = model.format_elapsed(snap.get('idle', 0))
            text = (f' {spark} Still working: no new progress report for {idle}. '
                    'The graphs show live activity; nothing here is estimated. ')
            canvas.put(box[0] + 1, box[1] + box[3] - 1, text[:max(0, box[2] - 2)], (YELLOW, None, False))

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

# Key decoding comes from the visual SDK (imported above).


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

class _Utf8Out:
    """The console gets UTF-8 whatever the locale says; the SDK's Screen writes text."""

    def write(self, text):
        sys.stdout.buffer.write(text.encode('utf-8', 'replace'))

    def flush(self):
        sys.stdout.flush()


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
        self.screen = Screen(_Utf8Out(), self.colors, alt=True)
        self.message, self.message_until = '', 0.0
        self.interrupt_at = 0.0
        self.input = b''
        self.input_at = 0.0
        self.quit = None
        self.started = time.monotonic()
        self.director = None
        self.sound_state = None
        if sound is not None:
            try:
                self.director = sound.Director(sound.Client(env))
                self.sound_state = self.director.client.state
            except Exception:  # noqa: BLE001 - the screen never depends on sound.
                self.director = None

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
        elif key in ('m', '+', '=', '-', 'a') and sound is not None:
            action = {'m': 'toggle-mute', '+': 'up', '=': 'up', '-': 'down', 'a': 'ambient'}[key]
            try:
                state = sound.ctl(action, self.env)
                if self.director:
                    self.director.client.checked = 0.0
                ambient = state.ambient and state.mode == 'on'
                self.say(state.label(self.glyphs.unicode) + (f"  ambient {'on' if ambient else 'off'}"
                                                             if key == 'a' else ''))
            except (OSError, ValueError) as error:
                self.say('Sound control unavailable: ' + clean(error))

    def feed_sound(self, snap):
        if self.director is not None:
            try:
                self.director.feed(snap)
            except Exception:  # noqa: BLE001 - sound never affects the installation or the screen.
                self.director = None

    def sound_label(self, short=False):
        if self.sound_state is None:
            return ''
        try:
            state = self.director.client._fresh() if self.director else self.sound_state
        except OSError:
            return ''
        return state.short(self.glyphs.unicode) if short else state.label(self.glyphs.unicode)

    def keys_hint(self):
        if self.tmux.active:
            return ('C-b c new window  C-b % / C-b " split  C-b G log  C-b H diagnostics  '
                    'C-b R remote debug  C-b m mute  C-b +/- volume  C-b ? all keys  v style')
        return 'v style  m mute  +/- volume  a ambient. Window controls need tmux, which is not available here.'

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
        label = self.sound_label(short=width < 100)
        room = width - 1
        # The sound state sits at the right; an important message keeps the whole row.
        important = text != self.keys_hint()
        if label and room - len(label) - 2 >= (len(text) if important else 20):
            room -= len(label) + 2
            muted = 'muted' in label or ' off' in label
            canvas.put(width - 1 - len(label), height - 1, label, (GRAY if muted else PURPLE, None, not muted))
        canvas.put(0, height - 1, text[:max(0, room)], (color, None, False))
        return canvas

    def curtain(self, canvas):
        """The screen opens like a curtain, rows appearing top to bottom (0.45 s)."""
        age = time.monotonic() - self.started
        if not self.reduced and age < 0.45:
            for row in range(int(canvas.height * age / 0.45), canvas.height):
                canvas.fill(0, row, canvas.width, 1)

    def render(self, snap):
        size = os.get_terminal_size(sys.stdout.fileno())
        width, height = max(10, min(size.columns, 400)), max(3, min(size.lines, 200))
        self.visuals.advance(snap)
        canvas = self.frame(width, height, snap)
        self.curtain(canvas)
        self.screen.present(canvas)  # writes only what changed; clears when the size changes

    def waiting_for_panes(self):
        return self.monitor.result is not None and self.tmux.other_panes() > 0


def run_plain(monitor, style):
    previous = None
    director = None
    if sound is not None:
        try:
            director = sound.Director(sound.Client())
        except Exception:  # noqa: BLE001
            director = None
    while True:
        monitor.poll()
        if director is not None:
            try:
                director.feed(monitor.snapshot())
            except Exception:  # noqa: BLE001 - sound never affects the installation.
                director = None
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
        if os.environ.get('TMUX'):
            # End the installer's session now that its result is recorded
            # (install-screen's pane-died hook does the same where it fires).
            subprocess.run(['tmux', 'kill-session'], capture_output=True, timeout=5, check=False)
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
    try:
        celebrate = max(0.0, min(30.0, float(env.get('DAEMONARCHY_CELEBRATE', '') or (2.0 if app.reduced else 4.0))))
    except ValueError:
        celebrate = 4.0
    celebrate_until, held_input = None, 0.0
    code, finished = 1, False
    try:
        app.screen.enter()
        next_frame = 0.0
        while True:
            monitor.poll()
            now = time.monotonic()
            if now >= next_frame:
                started = time.monotonic()
                snap = monitor.snapshot()
                app.feed_sound(snap)
                app.render(snap)
                cost = time.monotonic() - started
                # Bound CPU: never spend more than about a quarter of the time drawing.
                next_frame = now + max(1.0 / fps, cost * 4)
            if app.quit is not None:
                code = app.quit
                break
            if monitor.result is not None and not app.waiting_for_panes():
                if celebrate_until is None:
                    # Hold the finale (fireworks and fanfare, or the failure) briefly; any key skips it.
                    celebrate_until = time.monotonic() + celebrate
                    held_input = app.input_at
                if time.monotonic() >= celebrate_until or app.input_at != held_input:
                    state = monitor.state
                    code = monitor.result if monitor.result else (1 if state.warning or state.failed else 0)
                    finished = True
                    snap = monitor.snapshot()
                    app.feed_sound(snap)
                    app.render(snap)
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
        app.screen.leave()
        print('Dashboard unavailable: ' + clean(error), file=sys.stderr)
        code = 1
        app = None
    finally:
        if saved is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, saved)  # TCSADRAIN waits for a pty reader
        if app is not None:
            app.screen.leave()
        sys.stdout.write('\n')
        if app is not None and monitor.result is not None:
            width = app.screen.size[0] if app.screen.size else 80
            sys.stdout.write('\n'.join(final_summary(monitor, app.style, width)) + '\n')
        sys.stdout.flush()
    return code, finished


if __name__ == '__main__':
    raise SystemExit(main())
