#!/usr/bin/env python3
"""Shared installer progress and activity model.

One producer for every installer front end: the console dashboard
(progress-dashboard.py) and the live desktop's graphical installer both read
the install log through this module and render the same stages, counters,
package ticker and system activity.

Honesty rules:
- Counters advance only on measured observations (@@progress, native pkg
  positions, verified acquisition events). Elapsed time never becomes a
  completion percentage, and there is no estimated time remaining.
- Activity metrics are rates computed from kernel counters (devstat, ifmib,
  cp_times, vm.stats, ZFS kstats). They show that the machine is working and
  how hard; they do not claim how much of the installation is left.
- Only the installer's result file says whether the installation succeeded.
"""
from collections import deque
import ctypes
import ctypes.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

PHASES = dict(start='Starting', disk='Preparing the disk', base='Installing FreeBSD',
              loader='Installing the boot loader', config='Configuring the system',
              fetch='Gathering packages', install='Installing the desktop',
              user='Creating your account', checkouts='Installing development checkouts',
              cuda='Installing GPU applications', finish='Checking and finishing')

# The timeline in the order the install engine runs it. Optional stages are
# shown only once they start; stages that never start before a later one are
# marked skipped (for example Encrypt on an unencrypted install).
STAGES = (
    ('partition', 'Partition', False), ('encrypt', 'Encrypt', False),
    ('pool', 'ZFS pool', False), ('base', 'Base sets', False),
    ('loader', 'Boot loader', False), ('config', 'Configure', False),
    ('fetch', 'Download', False), ('packages', 'Packages', False),
    ('account', 'Account', False), ('checkouts', 'Checkouts', True),
    ('cuda', 'CUDA', True), ('finish', 'Verify', False))
STAGE_KEYS = tuple(key for key, _label, _optional in STAGES)
PHASE_STAGE = dict(disk='partition', base='base', loader='loader', config='config',
                   fetch='fetch', install='packages', user='account',
                   checkouts='checkouts', cuda='cuda', finish='finish')

ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-Z\\-_]')
PACKAGE_LINE = re.compile(r'^\[\s*(\d+)/(\d+)\] (Installing|Extracting|Upgrading|Reinstalling|Fetching) (.+?)(?:\.\.\.|:.*)?$')
FETCH_LINE = re.compile(r'^Fetching (\S+?):\s*(?:100%|[.\s]*done)(?:\s|$)')
REPOSITORY_FILES = {'meta.conf', 'meta', 'data', 'packagesite.pkg', 'packagesite.yaml',
                    'packagesite.txz', 'data.pkg', 'filesite.pkg'}
DEVICE = re.compile(r'^[a-z][a-z0-9]{0,14}$')
POOL = re.compile(r'^[A-Za-z][A-Za-z0-9_.:-]{0,63}$')


def clean(value, maximum=160):
    value = ANSI.sub('', str(value))
    return ''.join(c if c.isascii() and c.isprintable() else ' ' for c in value)[:maximum]


def integer(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


class Timeline:
    """Stage start/end times from installer markers.

    Times are monotonic seconds. A marker that carries the installer's wall
    clock (@@step NAME EPOCH) fixes the start even when the viewer reads a
    backlog late; markers without one use the moment the viewer read them.
    """

    def __init__(self, clock=time.monotonic, wall=time.time):
        self.clock, self.wall = clock, wall
        self.reset()

    def reset(self):
        self.started = {}
        self.ended = {}
        self.order = []
        self.active = None
        self.failed = None

    def _time(self, epoch):
        now = self.clock()
        if epoch is None:
            return now
        age = self.wall() - epoch
        if 0 <= age < 7 * 86400:
            return now - age
        return now

    def begin(self, key, epoch=None):
        if key not in STAGE_KEYS:
            return False
        at = self._time(epoch)
        if key == self.active:
            # A timestamped marker refines the arrival time of the same stage.
            if epoch is not None:
                self.started[key] = min(self.started[key], at)
                if len(self.order) > 1:
                    previous = self.order[-2]
                    self.ended[previous] = max(self.started[previous], min(self.ended[previous], self.started[key]))
            return True
        if key in self.started:
            return True  # Never rewind to an earlier stage.
        if self.active is not None:
            self.ended[self.active] = at
        self.started[key] = at
        self.order.append(key)
        self.active = key
        return True

    def finish(self, failed=False):
        if self.active is not None and self.active not in self.ended:
            if failed:
                self.failed = self.active
            self.ended[self.active] = self.clock()

    def rows(self):
        now = self.clock()
        reached = [STAGE_KEYS.index(key) for key in self.started]
        last = max(reached, default=-1)
        rows = []
        for index, (key, label, optional) in enumerate(STAGES):
            if key in self.started:
                end = self.ended.get(key, now)
                state = 'failed' if key == self.failed else ('done' if key in self.ended else 'active')
                elapsed = max(0.0, end - self.started[key])
            elif index < last:
                state, elapsed = 'skipped', None
            else:
                state, elapsed = 'pending', None
            if optional and state in ('pending', 'skipped'):
                continue
            rows.append(dict(key=key, label=label, state=state, elapsed=elapsed))
        return rows

    def total(self):
        if not self.started:
            return 0.0
        first = min(self.started.values())
        end = self.clock() if self.active not in self.ended else self.ended[self.active]
        return max(0.0, end - first)


class Ticker:
    """Recently processed package names from native pkg output."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.names = deque(maxlen=48)
        self.kind = None
        self.current = 0
        self.total = 0
        self.serial = 0  # Increments once per newly reported package.
        self.times = deque(maxlen=120)

    def add(self, kind, name, current, total, at):
        if kind != self.kind or total != self.total:
            self.names.clear()
            self.times.clear()
        self.kind, self.current, self.total = kind, current, total
        if not self.names or self.names[-1] != name:
            self.names.append(name)
            self.times.append(at)
            self.serial += 1

    def rate(self, now):
        """Packages per minute over the last minute of real reports."""
        recent = [t for t in self.times if now - t <= 60]
        if len(recent) < 2 or recent[-1] - recent[0] < 10:
            return None  # Too little real time observed (for example a backlog read at once).
        span = max(1.0, now - recent[0])
        return (len(recent) - 1) * 60.0 / span


class Progress:
    def __init__(self, pins=None, clock=time.monotonic, wall=time.time):
        self.clock = clock
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
        self.archive_packages, self.archive_count = 0, None
        self.recent = deque(maxlen=8)
        self.timeline = Timeline(clock, wall)
        self.ticker = Ticker()
        self.target_disk = None
        self.target_pool = None
        self.encrypted = False
        self.lines_read = 0

    def phase_changed(self, phase):
        if phase not in PHASES:
            self.warning = 'Unknown progress phase'
        elif phase != self.phase:
            self.phase, self.meter, self.item = phase, None, ''
            self.history.clear()
            self.downloads.clear()
            self.download_total = 0
            if phase in PHASE_STAGE:
                self.timeline.begin(PHASE_STAGE[phase])

    def step(self, text):
        parts = text.split()
        if not parts:
            return
        epoch = None
        if len(parts) > 1 and re.fullmatch(r'\d{9,11}', parts[1]):
            epoch = int(parts[1])
        if parts[0] == 'encrypt':
            self.encrypted = True
        self.timeline.begin(parts[0], epoch)

    def target(self, text):
        parts = text.split()
        if len(parts) == 2 and parts[0] == 'disk' and DEVICE.fullmatch(parts[1]):
            self.target_disk = parts[1]
        elif len(parts) == 2 and parts[0] == 'pool' and POOL.fullmatch(parts[1]):
            self.target_pool = parts[1]

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
                or current > total or packages > count or total == 0 or count == 0
                or current < self.archive_bytes or packages < self.archive_packages
                or self.archive_total not in (None, total)
                or self.archive_count not in (None, count)):
            raise ValueError('Invalid package acquisition counters')
        self.sequence, self.archive_bytes, self.archive_total = sequence, current, total
        self.archive_packages, self.archive_count = packages, count
        if self.phase == 'start':
            self.phase_changed('fetch')
        if self.phase == 'fetch':
            self.measured('Verified archives', current, total, 'bytes')
            self.item = f"{packages} of {count} archives verified"
        self.failed = self.failed or row['state'] in {'failed', 'cancelled'}

    def line(self, line, journal=False):
        self.lines_read += 1
        try:
            if journal:
                self.event(json.loads(line))
            elif line.startswith('@@progress '):
                self.event(json.loads(line[11:]))
            elif line.startswith('@@phase '):
                self.phase_changed(line[8:].strip())
            elif line.startswith('@@step '):
                self.step(clean(line[7:], 80))
            elif line.startswith('@@target '):
                self.target(clean(line[9:], 80))
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
                fetched = FETCH_LINE.match(text)
                if (self.phase == 'fetch' and fetched and self.download_total
                        and fetched[1] not in REPOSITORY_FILES):
                    self.downloads.add(fetched[1])
                    self.measured('Downloads reported complete', len(self.downloads),
                                  self.download_total, 'archives')
                    self.ticker.add('fetch', clean(fetched[1], 80), len(self.downloads),
                                    self.download_total, self.clock())
                package = PACKAGE_LINE.match(text)
                if package and self.phase in ('install', 'fetch'):
                    current, count, verb = int(package[1]), int(package[2]), package[3]
                    name = clean(package[4].strip(), 80)
                    if self.phase == 'install' and verb in ('Installing', 'Extracting', 'Upgrading', 'Reinstalling'):
                        self.measured('Processing package position', current, count, 'packages')
                        self.item = name
                        if verb != 'Extracting':
                            self.ticker.add('install', name, current, count, self.clock())
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
                    state.archive_packages, state.archive_count = 0, None
                    state.timeline.reset()
                    state.ticker.reset()
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


def title(state, result=None):
    if result is not None:
        if result == 0:
            return ('Daemonarchy is installed.' if not state.warning and not state.failed
                    else 'Installer exited 0; progress record needs inspection')
        return f'Installer stopped (exit {result}); inspect the install log.'
    if state.failed:
        return 'Acquisition failed; waiting for installer cleanup'
    return PHASES[state.phase]


# ------------------------------------------------------------------ metrics

class _Sysctl:
    """sysctl(3) through libc; FreeBSD only. No subprocess per sample."""

    def __init__(self):
        name = ctypes.util.find_library('c') or 'libc.so.7'
        self.libc = ctypes.CDLL(name, use_errno=True)
        self.libc.sysctlbyname.argtypes = [ctypes.c_char_p, ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
        self.libc.sysctl.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_uint, ctypes.c_void_p,
                                     ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]

    def raw(self, name, mib=None):
        for _attempt in range(3):
            size = ctypes.c_size_t(0)
            if mib is None:
                result = self.libc.sysctlbyname(name.encode(), None, ctypes.byref(size), None, 0)
            else:
                array = (ctypes.c_int * len(mib))(*mib)
                result = self.libc.sysctl(array, len(mib), None, ctypes.byref(size), None, 0)
            if result != 0:
                raise OSError(ctypes.get_errno(), name or str(mib))
            size = ctypes.c_size_t(size.value + 4096)
            buffer = ctypes.create_string_buffer(size.value)
            if mib is None:
                result = self.libc.sysctlbyname(name.encode(), buffer, ctypes.byref(size), None, 0)
            else:
                result = self.libc.sysctl(array, len(mib), buffer, ctypes.byref(size), None, 0)
            if result == 0:
                return buffer.raw[:size.value]
            if ctypes.get_errno() != 12:  # ENOMEM: grew between calls
                raise OSError(ctypes.get_errno(), name or str(mib))
        raise OSError(12, name or str(mib))

    def number(self, name):
        data = self.raw(name)
        if len(data) == 4:
            return struct.unpack('=I', data)[0]
        if len(data) == 8:
            return struct.unpack('=Q', data)[0]
        raise OSError(0, f'{name}: unexpected size')


class _Bintime(ctypes.Structure):
    _fields_ = [('sec', ctypes.c_int64), ('frac', ctypes.c_uint64)]


class _Devstat(ctypes.Structure):
    """struct devstat, DEVSTAT_VERSION 6 (sys/devicestat.h)."""
    _fields_ = [('sequence0', ctypes.c_uint), ('allocated', ctypes.c_int),
                ('start_count', ctypes.c_uint), ('end_count', ctypes.c_uint),
                ('busy_from', _Bintime), ('dev_links', ctypes.c_void_p),
                ('device_number', ctypes.c_uint32), ('device_name', ctypes.c_char * 16),
                ('unit_number', ctypes.c_int), ('bytes', ctypes.c_uint64 * 4),
                ('operations', ctypes.c_uint64 * 4), ('duration', _Bintime * 4),
                ('busy_time', _Bintime), ('creation_time', _Bintime),
                ('block_size', ctypes.c_uint32), ('tag_types', ctypes.c_uint64 * 3),
                ('flags', ctypes.c_int), ('device_type', ctypes.c_int),
                ('priority', ctypes.c_int), ('id', ctypes.c_void_p),
                ('sequence1', ctypes.c_uint)]


class _IfData(ctypes.Structure):
    _fields_ = [('type', ctypes.c_uint8), ('physical', ctypes.c_uint8), ('addrlen', ctypes.c_uint8),
                ('hdrlen', ctypes.c_uint8), ('link_state', ctypes.c_uint8), ('vhid', ctypes.c_uint8),
                ('datalen', ctypes.c_uint16), ('mtu', ctypes.c_uint32), ('metric', ctypes.c_uint32),
                ('baudrate', ctypes.c_uint64), ('ipackets', ctypes.c_uint64), ('ierrors', ctypes.c_uint64),
                ('opackets', ctypes.c_uint64), ('oerrors', ctypes.c_uint64), ('collisions', ctypes.c_uint64),
                ('ibytes', ctypes.c_uint64), ('obytes', ctypes.c_uint64)]


class _IfMib(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char * 16), ('pcount', ctypes.c_int), ('flags', ctypes.c_int),
                ('snd_len', ctypes.c_int), ('snd_maxlen', ctypes.c_int), ('snd_drops', ctypes.c_int),
                ('filler', ctypes.c_int * 4), ('data', _IfData)]


def _skip_disk(name):
    # Memory disks hold the live image; optical and enclosure devices are not targets.
    return name.startswith(('md', 'cd', 'pass', 'ses', 'xpt'))


class FreeBSDCounters:
    """Raw cumulative counters from the running FreeBSD kernel."""

    def __init__(self):
        self.sysctl = _Sysctl()
        if self.sysctl.number('kern.devstat.version') != 6:
            raise OSError(0, 'unsupported devstat version')
        self.pagesize = self.sysctl.number('hw.pagesize')
        self.ncpu = self.sysctl.number('hw.ncpu')
        self.long = ctypes.sizeof(ctypes.c_long)

    def cpu(self):
        data = self.sysctl.raw('kern.cp_times')
        values = struct.unpack(f'={len(data) // self.long}{"q" if self.long == 8 else "i"}', data)
        # CPUSTATES: user nice sys intr idle.
        return [(sum(values[i:i + 5]) - values[i + 4], sum(values[i:i + 5]))
                for i in range(0, len(values) - 4, 5)][:256]

    def memory(self):
        number = self.sysctl.number
        total = number('vm.stats.vm.v_page_count') * self.pagesize
        free = (number('vm.stats.vm.v_free_count') + number('vm.stats.vm.v_inactive_count')) * self.pagesize
        result = dict(total=total, used=max(0, total - free))
        try:
            result['arc'] = number('kstat.zfs.misc.arcstats.size')
        except OSError:
            pass
        return result

    def disks(self):
        data = self.sysctl.raw('kern.devstat.all')
        size = ctypes.sizeof(_Devstat)
        header = self.long
        if (len(data) - header) % size:
            raise OSError(0, 'devstat layout mismatch')
        disks = {}
        for offset in range(header, len(data), size):
            stat = _Devstat.from_buffer_copy(data, offset)
            name = stat.device_name.decode('ascii', 'replace') + str(stat.unit_number)
            # DEVSTAT_TYPE_PASS = 0x100; only direct-access disks count.
            if stat.device_type & 0x100 or (stat.device_type & 0xf) != 0 or _skip_disk(name):
                continue
            disks[name] = (stat.bytes[1], stat.bytes[2], stat.operations[1], stat.operations[2])
        return disks

    def network(self):
        count = self.sysctl.number('net.link.generic.system.ifcount')
        interfaces = {}
        for index in range(1, min(count, 256) + 1):
            try:
                data = self.sysctl.raw('', [4, 18, 0, 2, index, 1])
            except OSError:
                continue
            if len(data) < ctypes.sizeof(_IfMib):
                continue
            mib = _IfMib.from_buffer_copy(data)
            name = mib.name.decode('ascii', 'replace')
            # Skip loopback (IFT_LOOP 0x18) and down interfaces (IFF_UP 0x1).
            if mib.data.type == 0x18 or not mib.flags & 1:
                continue
            interfaces[name] = (mib.data.ibytes, mib.data.obytes)
        return interfaces

    def zfs_written(self, pool):
        """Logical bytes written to the target pool's datasets (1 Hz)."""
        try:
            output = subprocess.run(['sysctl', '-q', f'kstat.zfs.{pool}.dataset'], capture_output=True,
                                    text=True, timeout=2, check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        values = [int(m) for m in re.findall(r'\.nwritten: (\d+)$', output, re.M)]
        return sum(values) if values else None


class LinuxCounters:
    """The same counters from /proc, for development hosts and hosted CI."""

    def __init__(self):
        if not Path('/proc/stat').exists():
            raise OSError(0, 'no /proc')
        self.ncpu = os.cpu_count() or 1

    def cpu(self):
        rows = []
        for line in Path('/proc/stat').read_text().splitlines():
            if re.match(r'cpu\d+ ', line):
                values = [int(x) for x in line.split()[1:]]
                idle = values[3] + (values[4] if len(values) > 4 else 0)
                rows.append((sum(values) - idle, sum(values)))
        return rows[:256]

    def memory(self):
        info = {}
        for line in Path('/proc/meminfo').read_text().splitlines():
            key, _, rest = line.partition(':')
            info[key] = int(rest.split()[0]) * 1024 if rest.split() else 0
        total = info.get('MemTotal', 0)
        return dict(total=total, used=max(0, total - info.get('MemAvailable', 0)))

    def disks(self):
        disks = {}
        for line in Path('/proc/diskstats').read_text().splitlines():
            fields = line.split()
            if len(fields) < 10:
                continue
            name = fields[2]
            if not re.fullmatch(r'(?:[sv]d[a-z]+|xvd[a-z]+|nvme\d+n\d+|mmcblk\d+)', name):
                continue
            disks[name] = (int(fields[5]) * 512, int(fields[9]) * 512, int(fields[3]), int(fields[7]))
        return disks

    def network(self):
        interfaces = {}
        for line in Path('/proc/net/dev').read_text().splitlines()[2:]:
            name, _, rest = line.partition(':')
            name, fields = name.strip(), rest.split()
            if name == 'lo' or len(fields) < 9:
                continue
            interfaces[name] = (int(fields[0]), int(fields[8]))
        return interfaces

    def zfs_written(self, pool):
        return None


def counters():
    """The best available counter source, or None (activity then shows unavailable)."""
    for source in (FreeBSDCounters, LinuxCounters):
        if source is FreeBSDCounters and not sys.platform.startswith('freebsd'):
            continue
        try:
            return source()
        except (OSError, AttributeError, ValueError):
            continue
    return None


class Activity:
    """Rates from successive counter samples, with bounded history.

    Every value here is a measured rate or level. History rows are kept per
    channel so renderers can draw spectra and scopes from real samples only.
    """

    CHANNELS = ('disk_write', 'disk_read', 'iops', 'net_rx', 'net_tx', 'cpu', 'zfs_write')

    def __init__(self, source=None, interval=0.25, history=240, clock=time.monotonic):
        self.source = source
        self.interval = interval
        self.clock = clock
        self.previous = None
        self.last = float('-inf')
        self.zfs_last, self.zfs_previous = 0.0, None
        self.current = {}
        self.history = {name: deque(maxlen=history) for name in self.CHANNELS}
        self.peaks = {name: 0.0 for name in self.CHANNELS}
        self.samples = 0
        self.error = '' if source else 'Activity counters unavailable on this system'

    def sample(self, disk=None, pool=None, now=None):
        """Take a sample if the interval has passed. Returns True when values changed."""
        now = self.clock() if now is None else now
        if self.source is None or now - self.last < self.interval:
            return False
        self.last = now
        try:
            raw = dict(cpu=self.source.cpu(), disks=self.source.disks(), net=self.source.network(),
                       memory=self.source.memory())
        except (OSError, ValueError, struct.error) as error:
            self.error = clean(f'Activity counters unavailable: {error}', 120)
            return False
        self.error = ''
        previous, self.previous = self.previous, (now, raw)
        if previous is None:
            return False
        elapsed = now - previous[0]
        if elapsed <= 0:
            return False
        old = previous[1]
        cores = []
        for (busy, total), (busy0, total0) in zip(raw['cpu'], old['cpu']):
            span = total - total0
            cores.append(max(0.0, min(1.0, (busy - busy0) / span)) if span > 0 else 0.0)
        names = [disk] if disk and disk in raw['disks'] else sorted(n for n in raw['disks'] if not _skip_disk(n))
        def delta(table0, table1, keys, field):
            total = 0
            for key in keys:
                if key in table0 and key in table1:
                    total += max(0, table1[key][field] - table0[key][field])
            return total / elapsed
        read, write = delta(old['disks'], raw['disks'], names, 0), delta(old['disks'], raw['disks'], names, 1)
        ops = delta(old['disks'], raw['disks'], names, 2) + delta(old['disks'], raw['disks'], names, 3)
        nets = sorted(raw['net'])
        rx, tx = delta(old['net'], raw['net'], nets, 0), delta(old['net'], raw['net'], nets, 1)
        busiest = max(nets, key=lambda n: sum(raw['net'][n]) - sum(old['net'].get(n, (0, 0))), default='')
        values = dict(disk_write=write, disk_read=read, iops=ops, net_rx=rx, net_tx=tx,
                      cpu=sum(cores) / len(cores) if cores else 0.0)
        if pool and now - self.zfs_last >= 1.0:
            self.zfs_last = now
            written = self.source.zfs_written(pool)
            if written is not None and self.zfs_previous is not None and now > self.zfs_previous[0]:
                values['zfs_write'] = max(0, written - self.zfs_previous[1]) / (now - self.zfs_previous[0])
            elif 'zfs_write' in self.current:
                values['zfs_write'] = self.current['zfs_write']
            self.zfs_previous = (now, written) if written is not None else None
        elif 'zfs_write' in self.current and pool:
            values['zfs_write'] = self.current['zfs_write']
        for name in self.CHANNELS:
            if name in values:
                self.history[name].append(values[name])
                self.peaks[name] = max(values[name], self.peaks[name] * 0.995)
        self.current = dict(values, cores=cores, memory=raw['memory'], disks=names,
                            interface=busiest, interfaces=len(nets))
        self.samples += 1
        return True

    def view(self):
        return dict(available=self.source is not None and not self.error, error=self.error,
                    samples=self.samples, current=dict(self.current),
                    history={name: list(values) for name, values in self.history.items()},
                    peaks=dict(self.peaks))


# ------------------------------------------------------------------ remote debug

REMOTE_STATE = Path('/var/db/daemonarchy/remote-debug')
REMOTE_PUBLIC = Path('/var/run/daemonarchy-debug.status')


def remote_debug(state=REMOTE_STATE, public=REMOTE_PUBLIC):
    """Console-approved remote debug status, read-only."""
    view = dict(listener=False, connected=False, grant=False, port='', addresses='', pending=[])
    try:
        for line in public.read_text().splitlines()[:16]:
            key, _, value = line.partition('=')
            if key in ('listener', 'connected', 'grant'):
                view[key] = value.strip() == '1'
            elif key in ('port', 'addresses'):
                view[key] = clean(value, 120)
    except OSError:
        pass
    try:
        for request in sorted((state / 'requests').iterdir())[:8]:
            name = request.name
            if not re.fullmatch(r'[0-9a-f]{64}', name):
                continue
            if (state / f'{name}.approved').exists() or (state / f'{name}.denied').exists():
                continue
            with request.open() as stream:
                fingerprint = clean(stream.readline(), 120).strip()
            view['pending'].append(dict(id=name, fingerprint=fingerprint))
    except OSError:
        pass
    return view


# ------------------------------------------------------------------ monitor

class Monitor:
    """Everything a front end needs, from the same files and counters.

    poll() reads new log lines, samples activity and returns a plain dict
    (JSON-serializable) snapshot. Both the console dashboard and the live
    desktop's graphical installer render this snapshot.
    """

    def __init__(self, log, status_path, events=None, pins=None, source='auto',
                 clock=time.monotonic, wall=time.time, sample_interval=0.25):
        self.clock = clock
        self.state = Progress(pins, clock, wall)
        self.readers = [Tail(log)] + ([Tail(events, True)] if events else [])
        self.status_path = Path(status_path)
        self.activity = Activity(counters() if source == 'auto' else source, sample_interval, clock=clock)
        self.changed_at = clock()
        self.result = None
        self.drained = False
        self.finished = False

    def poll(self):
        old = self.state.key(), self.state.ticker.serial
        self.drained = all([reader.poll(self.state) for reader in self.readers])
        if (self.state.key(), self.state.ticker.serial) != old:
            self.changed_at = self.clock()
        result = status(self.status_path)
        self.result = result if self.drained else None
        if self.result is not None and not self.finished:
            self.finished = True
            self.state.timeline.finish(failed=self.result != 0 or self.state.failed)
        self.activity.sample(self.state.target_disk, self.state.target_pool)
        return self.result

    def idle_seconds(self):
        return self.clock() - self.changed_at

    def snapshot(self):
        state = self.state
        meter = None
        if state.meter:
            label, current, total, unit = state.meter
            meter = dict(label=label, current=current, total=total, unit=unit)
        ticker = state.ticker
        return dict(
            schema='daemonarchy/installer-snapshot@1',
            phase=state.phase, title=title(state, self.result), meter=meter, item=state.item,
            stages=state.timeline.rows(), elapsed=state.timeline.total(),
            ticker=dict(kind=ticker.kind, names=list(ticker.names), current=ticker.current,
                        total=ticker.total, serial=ticker.serial, rate=ticker.rate(self.clock())),
            activity=self.activity.view(), target=dict(disk=state.target_disk, pool=state.target_pool,
                                                       encrypted=state.encrypted),
            warning=state.warning, failed=state.failed, result=self.result,
            done=self.result is not None,
            succeeded=self.result == 0 and not state.warning and not state.failed,
            idle=self.idle_seconds(), recent=list(state.recent))


class InstallProgress:
    """Drop-in model for the live desktop's graphical installer (LIVE-001).

    poll() keeps the keys the GTK progress page already reads (title, details,
    fraction, done, succeeded, recent) and adds the shared stages, ticker and
    activity so both installers show the same information.
    """

    def __init__(self, log, status_path, source='auto'):
        self.monitor = Monitor(log, status_path, source=source)

    def poll(self):
        self.monitor.poll()
        snap = self.monitor.snapshot()
        meter = snap['meter']
        details = []
        if meter:
            details.append(f"{meter['label']}: {meter['current']:,} / {meter['total']:,} {meter['unit']}")
        else:
            details.append('No measured total for this stage')
        if snap['item']:
            details.append(snap['item'])
        if snap['warning']:
            details.append('Progress unavailable: ' + snap['warning'])
        elif snap['idle'] >= 5 and not snap['done']:
            details.append('Waiting for the next progress report')
        if not snap['done']:
            details.append('Meters describe observed work; installation is still running.')
        snap.update(details=details,
                    fraction=meter['current'] / meter['total'] if meter else None)
        return snap


def format_rate(value, unit='B/s'):
    if value is None:
        return '-'
    for scale, suffix in ((1 << 30, 'G'), (1 << 20, 'M'), (1 << 10, 'K')):
        if value >= scale:
            return f'{value / scale:5.1f} {suffix}{unit}'
    return f'{value:5.0f} {unit}'


def format_elapsed(seconds):
    if seconds is None:
        return ''
    seconds = int(seconds)
    if seconds >= 3600:
        return f'{seconds // 3600}:{seconds % 3600 // 60:02}:{seconds % 60:02}'
    return f'{seconds // 60}:{seconds % 60:02}'


def main(argv=None):
    """Print snapshots as JSON lines (for other front ends and debugging)."""
    import argparse
    parser = argparse.ArgumentParser(description='Emit installer progress snapshots as JSON lines.')
    parser.add_argument('log', type=Path)
    parser.add_argument('status', type=Path)
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args(argv)
    monitor = Monitor(args.log, args.status)
    while True:
        monitor.poll()
        print(json.dumps(monitor.snapshot(), sort_keys=True), flush=True)
        if args.once or monitor.result is not None:
            return 0
        time.sleep(max(0.1, args.interval))


if __name__ == '__main__':
    raise SystemExit(main())
