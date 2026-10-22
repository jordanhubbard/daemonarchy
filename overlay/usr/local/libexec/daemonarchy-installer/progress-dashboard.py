#!/usr/bin/env python3
"""Read-only installer dashboard. Counters come from events, never elapsed time."""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import re
import signal
import sys
import time

PHASES = dict(start='Starting', disk='Preparing the disk', base='Installing FreeBSD',
              loader='Installing the boot loader', config='Configuring the system',
              fetch='Gathering packages', install='Installing the desktop',
              user='Creating your account', checkouts='Installing development checkouts',
              cuda='Installing GPU applications', finish='Checking and finishing')
ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')


def clean(value, maximum=160):
    value = ANSI.sub('', str(value))
    return ''.join(c if c.isascii() and c.isprintable() else ' ' for c in value)[:maximum]


def integer(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


class Progress:
    def __init__(self, pins=None):
        self.phase = 'start'
        self.meter = None
        self.item = ''
        self.history = deque(maxlen=24)
        self.warning = ''
        self.failed = False
        self.pins = pins
        self.sequence = 0
        self.downloads = set()
        self.download_total = 0
        self.archive_bytes, self.archive_total = 0, None
        self.recent = deque(maxlen=8)

    def phase_changed(self, phase):
        if phase not in PHASES:
            self.warning = 'Unknown progress phase'
        elif phase != self.phase:
            self.phase, self.meter, self.item = phase, None, ''
            self.history.clear()
            self.downloads.clear()
            self.download_total = 0

    def measured(self, label, current, total, unit):
        if not integer(current) or not integer(total) or current > total or total == 0:
            raise ValueError('Invalid measured counter')
        label, unit = clean(label, 40), clean(unit, 20)
        if not label or not unit:
            raise ValueError('Missing measured counter label')
        previous = self.meter
        if previous and previous[0] == label and previous[3] == unit and previous[2] != total:
            raise ValueError('Measured total changed without a new phase')
        if previous and previous[0] == label and previous[2:] == (total, unit):
            if current < previous[1]:
                raise ValueError('Measured counter moved backwards')
            delta = current - previous[1]
        else:
            self.history.clear()
            delta = current
        self.meter = label, current, total, unit
        if delta:
            self.history.append(delta)

    def event(self, row):
        if not isinstance(row, dict):
            raise ValueError('Progress event is not an object')
        if row.get('schema') == 'daemonarchy/installer-progress@1':
            if row.get('phase') != self.phase:
                raise ValueError('Counter does not belong to the active phase')
            self.measured(row['label'], row['current'], row['total'], row['unit'])
            return
        if row.get('schema') != 'daemonarchy/package-progress-event@1' or not self.pins:
            raise ValueError('Unbound package progress')
        if (row.get('input_sha256'), row.get('repository_database_sha256')) != self.pins:
            raise ValueError('Package progress pin mismatch')
        sequence = row.get('sequence')
        if not integer(sequence) or sequence != self.sequence + 1:
            raise ValueError('Package progress sequence mismatch')
        if row.get('phase') != 'download' or row.get('state') not in {
                'started', 'verified', 'failed', 'cancelled'}:
            raise ValueError('Unknown package acquisition state')
        current, total = row['verified_bytes'], row['total_bytes']
        packages, count = row['verified_packages'], row['total_packages']
        if (not all(integer(x) for x in (current, total, packages, count))
                or current > total or packages > count or total == 0
                or current < self.archive_bytes
                or self.archive_total not in (None, total)):
            raise ValueError('Invalid package acquisition counters')
        self.sequence, self.archive_bytes, self.archive_total = sequence, current, total
        if self.phase == 'start':
            self.phase_changed('fetch')
        if self.phase == 'fetch':
            self.measured('Verified archives', current, total, 'bytes')
            self.item = f"{packages} of {count} archives verified"
        self.failed = self.failed or row['state'] in {'failed', 'cancelled'}

    def line(self, line, journal=False):
        try:
            if journal:
                self.event(json.loads(line))
            elif line.startswith('@@progress '):
                self.event(json.loads(line[11:]))
            elif line.startswith('@@phase '):
                self.phase_changed(line[8:].strip())
            else:
                text = clean(line, 4096)
                if text.strip():
                    self.recent.append(text[:160])
                total = re.search(r'packages to be fetched:\s*(\d+)\s*$', text)
                if self.phase == 'fetch' and total:
                    self.download_total = int(total[1])
                    self.downloads.clear()
                    self.meter = None
                    self.history.clear()
                fetched = re.match(r'^Fetching (\S+):\s*100%(?:\s|$)', text)
                if self.phase == 'fetch' and fetched and self.download_total:
                    self.downloads.add(fetched[1])
                    self.measured('Downloads reported complete', len(self.downloads),
                                  self.download_total, 'archives')
                package = re.match(r'^\[\s*(\d+)/(\d+)\] (?:Installing|Extracting|Upgrading) (.+)', text)
                if self.phase == 'install' and package:
                    self.measured('Processing package position', int(package[1]), int(package[2]), 'packages')
                    self.item = clean(package[3].removesuffix('...'), 80)
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            self.warning = clean(error)

    def key(self):
        return self.phase, self.meter, self.item, tuple(self.history), self.warning, self.failed


class Tail:
    """At most 256 KiB read and 64 KiB pending per poll, including partial lines."""
    def __init__(self, path, journal=False):
        self.path, self.journal = Path(path), journal
        self.offset, self.identity, self.pending, self.discard = 0, None, b'', False

    def poll(self, state):
        try:
            with self.path.open('rb') as stream:
                stat = os.fstat(stream.fileno())
                identity = stat.st_dev, stat.st_ino
                if self.identity is not None and (identity != self.identity or stat.st_size < self.offset):
                    state.warning = 'Progress log restarted; counters reset'
                    state.phase, state.meter, state.sequence = 'start', None, 0
                    state.history.clear()
                    state.downloads.clear()
                    state.archive_bytes, state.archive_total = 0, None
                    self.offset, self.pending, self.discard = 0, b'', False
                self.identity = identity
                stream.seek(self.offset)
                data = stream.read(256 * 1024)
                self.offset += len(data)
        except FileNotFoundError:
            return True
        rows = (self.pending + data).split(b'\n')
        self.pending = rows.pop()
        for row in rows:
            if self.discard:
                self.discard = False
            elif len(row) > 65536:
                state.warning = 'Oversized progress line ignored'
            else:
                state.line(row.decode('utf-8', errors='replace'), self.journal)
        if len(self.pending) > 65536:
            self.pending, self.discard = b'', True
            state.warning = 'Oversized progress line ignored'
        return self.offset >= stat.st_size


def lines(state, style, width, idle=False, result=None):
    width = max(1, min(width, 240))
    title = PHASES[state.phase]
    if result is not None:
        title = ('Daemonarchy is installed.' if not state.warning and not state.failed else 'Installer exited 0; progress record needs inspection') if result == 0 else f'Installer stopped (exit {result}); inspect the install log.'
    elif state.failed:
        title = 'Acquisition failed; waiting for installer cleanup'
    output = ['DAEMONARCHY / ' + style.upper(), title]
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
    if state.warning:
        output.append('Progress unavailable: ' + state.warning)
    elif idle and result is None:
        output.append('Waiting for the next progress report')
    if result is None:
        output.append('Meters describe observed work; installation is still running.')
    elif result != 0:
        output.extend(state.recent)
    return [clean(line, width) for line in output]


def status(path):
    try:
        value = Path(path).read_text().strip()
    except FileNotFoundError:
        return None
    if not value:
        return None
    if not re.fullmatch(r'\d{1,3}', value) or int(value) > 255:
        raise ValueError('Invalid installer result file')
    return int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('status', type=Path)
    parser.add_argument('--style', choices=('bars', 'spectrum', 'scope', 'plain'), default=os.environ.get('DAEMONARCHY_PROGRESS_STYLE', 'bars'))
    parser.add_argument('--events', type=Path)
    parser.add_argument('--input-pin')
    parser.add_argument('--repository-pin')
    args = parser.parse_args(argv)
    if args.events and not all(re.fullmatch('[0-9a-f]{64}', pin or '') for pin in (args.input_pin, args.repository_pin)):
        parser.error('--events requires the exact input and repository SHA-256 pins')
    state = Progress((args.input_pin, args.repository_pin) if args.events else None)
    readers = [Tail(args.log)] + ([Tail(args.events, True)] if args.events else [])
    interactive = args.style != 'plain' and sys.stdout.isatty() and os.environ.get('TERM', '') not in ('', 'dumb')
    color = interactive and 'NO_COLOR' not in os.environ
    reduced = os.environ.get('DAEMONARCHY_REDUCED_MOTION', '').lower() in ('1', 'yes', 'true')
    style = 'bars' if reduced and args.style != 'plain' else args.style
    logo = []
    if interactive and os.environ.get('TERM') not in ('vt100', 'vt220', 'ansi'):
        try:
            path = Path(os.environ.get('ISO_SHARE', '/usr/local/share/daemonarchy-installer'))/'logo.txt'
            with path.open(encoding='utf-8') as stream:
                logo = [''.join(c for c in row if c.isprintable())[:240] for row in stream.read(8192).splitlines()[:20]]
        except (OSError, UnicodeError):
            pass
    previous, changed_at = None, time.monotonic()
    def stop(signum, _frame):
        raise InterruptedError(signum)
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, stop)
    try:
        if interactive:
            sys.stdout.write('\033[?25l\033[2J')
        while True:
            old = state.key()
            drained = all([reader.poll(state) for reader in readers])
            if state.key() != old:
                changed_at = time.monotonic()
            result = status(args.status)
            size = os.get_terminal_size(sys.stdout.fileno()) if interactive else os.terminal_size((120, 24))
            idle = time.monotonic() - changed_at >= 5
            key = state.key(), size, idle, result, drained
            if key != previous:
                text = lines(state, style, size.columns, idle, result if drained else None)
                slots = max(1, size.lines - 1)
                if result not in (None, 0) and drained:
                    tail = list(state.recent)[-max(1, slots - 3):] if slots > 3 else []
                    text = text[:min(2, slots)] + tail
                    if slots > 2:
                        text.append(clean('Full install log: ' + str(args.log), size.columns))
                text = text[:slots]
                if logo and len(logo) + len(text) < size.lines and all(len(row) <= size.columns for row in logo):
                    text = logo + text
                if interactive:
                    palette = {'bars': (81, 36), 'spectrum': (82, 32), 'scope': (213, 35)}
                    extended, basic = palette.get(style, (81, 36))
                    prefix = (f'\033[38;5;{extended}m' if '256color' in os.environ.get('TERM', '') else f'\033[{basic}m') if color else ''
                    sys.stdout.write('\033[H' + prefix + '\n'.join(text) + ('\033[0m' if color else '') + '\033[J')
                else:
                    sys.stdout.write(' | '.join(text) + '\n')
                sys.stdout.flush()
                previous = key
            if result is not None and drained:
                return result if result else (1 if state.warning or state.failed else 0)
            time.sleep(0.2)
    except InterruptedError as error:
        return 128 + error.args[0]
    except (OSError, ValueError) as error:
        print('Dashboard unavailable: ' + clean(error), file=sys.stderr)
        return 1
    finally:
        if interactive:
            sys.stdout.write('\033[0m\033[?25h\n')
            sys.stdout.flush()


if __name__ == '__main__':
    raise SystemExit(main())
