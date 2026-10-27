#!/usr/bin/env python3
"""Exercise measured progress, the shared model, the install screen and its tmux session.

Nothing here installs anything: logs are synthetic or a scrubbed retained
real install log, and activity comes from the host kernel or fake counters.
"""
import codecs
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'overlay/usr/local/libexec/daemonarchy-installer/progress-dashboard.py'
spec = importlib.util.spec_from_file_location('installer_progress', SCRIPT)
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)
model = ui.model
demo_spec = importlib.util.spec_from_file_location('installer_visuals_demo', ROOT/'scripts/installer-visuals-demo.py')
demo = importlib.util.module_from_spec(demo_spec)
demo_spec.loader.exec_module(demo)
WRAPPER = ROOT/'overlay/usr/local/libexec/daemonarchy-installer/dashboard'
SHARE = ROOT/'overlay/usr/local/share/daemonarchy-installer'
LIBEXEC = ROOT/'overlay/usr/local/libexec/daemonarchy-installer'
sound = ui.sound
charm = ui.charm
# Every test that starts a screen gets a private sound directory, so a player
# or setting on the test host is never touched.
SOUND_ROOT = tempfile.TemporaryDirectory(prefix='daemonarchy-sound-test-')


def metric(current=1, total=3):
    return dict(schema='daemonarchy/installer-progress@1', phase='base',
                label='Release archives expanded', current=current, total=total, unit='archives')


def package(sequence=1, current=0, state='started'):
    return dict(schema='daemonarchy/package-progress-event@1', phase='download',
                input_sha256='a'*64, repository_database_sha256='b'*64,
                sequence=sequence, state=state, verified_bytes=current, total_bytes=100,
                verified_packages=int(current == 100), total_packages=1)


class MeasuredProgressTests(unittest.TestCase):
    def test_elapsed_time_and_full_meter_are_not_completion(self):
        state = ui.Progress()
        state.phase_changed('base')
        state.event(metric(3))
        before = state.key()
        for style in ('bars', 'spectrum', 'scope', 'plain'):
            for width in (1, 8, 20, 80, 256):
                text = ui.lines(state, style, width, idle=True)
                self.assertTrue(all(len(row) <= min(width, 240) for row in text))
                self.assertNotIn('Daemonarchy is installed.', '\n'.join(text))
                self.assertEqual(state.key(), before)
        self.assertIn('next progress report', '\n'.join(ui.lines(state, 'bars', 80, idle=True)))

    def test_counts_ignore_fetch_starts_partial_updates_and_duplicates(self):
        state = ui.Progress()
        for line in ('@@phase fetch', 'Number of packages to be fetched: 2',
                     'Fetching one.pkg: 30% 1 MiB', 'Fetching one.pkg: 100% 2 MiB',
                     'Fetching one.pkg: 100% 2 MiB'):
            state.line(line)
        self.assertEqual(state.meter[1:3], (1, 2))
        state.line('Number of packages to be fetched: 1')  # retry has a new native count
        self.assertIsNone(state.meter)
        state.line('Fetching two.pkg: 100%')
        self.assertEqual(state.meter[1:3], (1, 1))
        state.line('@@phase install')
        state.line('[ 1/2] Installing first-1.0...')
        self.assertEqual(state.meter[0], 'Processing package position')
        self.assertNotIn('installed', '\n'.join(ui.lines(state, 'bars', 120)))

    def test_package_journal_requires_exact_pins_sequence_and_monotone_bytes(self):
        state = ui.Progress(('a'*64, 'b'*64))
        state.line(json.dumps(package()), True)
        state.line(json.dumps(package(2, 100, 'verified')), True)
        self.assertEqual(state.meter[1:3], (100, 100))
        self.assertNotIn('Daemonarchy is installed.', '\n'.join(ui.lines(state, 'scope', 120)))
        before = state.meter
        state.line(json.dumps(package(2, 100, 'verified')), True)
        self.assertIn('sequence', state.warning)
        self.assertEqual(state.meter, before)
        for row in (dict(package(), input_sha256='c'*64), package(3, 99, 'verified'),
                    dict(package(3), verified_packages=True)):
            other = ui.Progress(('a'*64, 'b'*64))
            other.line(json.dumps(row), True)
            self.assertTrue(other.warning)
        invalid = ui.Progress()
        invalid.line(json.dumps(package()), True)
        self.assertEqual(invalid.warning, 'Unbound package progress')

    def test_recorded_journal_rejects_package_count_drift_without_advancing(self):
        fixture = ROOT/'tests/fixtures/installer-progress/native-acquisition.jsonl'
        rows = [json.loads(line) for line in fixture.read_text().splitlines()]
        first_verified = next(i for i, row in enumerate(rows) if row['verified_packages'] == 1)
        for change in ({'verified_packages': 0}, {'total_packages': 9},
                       {'total_packages': 0, 'verified_packages': 0}):
            with self.subTest(change=change):
                state = ui.Progress((rows[0]['input_sha256'], rows[0]['repository_database_sha256']))
                for row in rows[:first_verified + 1]:
                    state.event(row)
                self.assertEqual(state.item, '1 of 8 archives verified')
                before = state.key(), state.sequence
                with self.assertRaisesRegex(ValueError, 'counters'):
                    state.event(dict(rows[first_verified + 1], **change))
                self.assertEqual((state.key(), state.sequence), before)
                state.event(rows[first_verified + 1])
                self.assertEqual(state.sequence, rows[first_verified + 1]['sequence'])

    def test_journal_cannot_rewind_install_phase_or_turn_failure_into_success(self):
        state = ui.Progress(('a'*64, 'b'*64))
        state.phase_changed('install')
        state.event(package())
        self.assertEqual(state.phase, 'install')
        state.event(package(2, 0, 'failed'))
        self.assertTrue(state.failed)
        self.assertNotIn('Daemonarchy is installed.', '\n'.join(ui.lines(state, 'bars', 120, result=0)))

    def test_invalid_counters_and_escape_sequences_do_not_change_authority(self):
        state = ui.Progress()
        state.phase_changed('base')
        state.event(metric(2))
        for current in (-1, True, 1.5, 4):
            with self.assertRaises(ValueError):
                state.event(metric(current))
        state.line('@@progress ' + json.dumps(metric(1)))
        self.assertIn('backwards', state.warning)
        self.assertEqual(state.meter[1], 2)
        self.assertNotIn('\033', ui.clean('\033]2;title\007hello\033[2J\r\nworld'))

    def test_tail_keeps_partial_lines_bounds_work_and_detects_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'log'
            path.write_bytes(b'@@pha')
            reader, state = ui.Tail(path), ui.Progress()
            reader.poll(state)
            self.assertEqual(state.phase, 'start')
            with path.open('ab') as out:
                out.write(b'se base\n@@progress ' + json.dumps(metric()).encode() + b'\n')
            reader.poll(state)
            self.assertEqual(state.meter[1], 1)
            old_offset = reader.offset
            with path.open('ab') as out:
                out.write(b'x'*(1024*1024))
            reader.poll(state)
            self.assertLessEqual(reader.offset-old_offset, 256*1024)
            self.assertLessEqual(len(reader.pending), 65536)
            replacement = path.with_name('new')
            replacement.write_text('@@phase disk\n')
            replacement.replace(path)
            reader.poll(state)
            self.assertEqual(state.phase, 'disk')
            self.assertIsNone(state.meter)
            self.assertIn('restarted', state.warning)

    def test_real_plain_process_preserves_backend_failure_and_sanitizes_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase base\nError: failed\033[2J payload\n')
            status.write_text('7\n')
            result = subprocess.run([sys.executable, str(SCRIPT), str(log), str(status), '--style', 'plain'], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 7)
            self.assertNotIn(b'\033', result.stdout)
            self.assertIn(b'failed payload', result.stdout)
            self.assertNotIn(b'Daemonarchy is installed.', result.stdout)
            status.write_text('corrupt')
            result = subprocess.run([sys.executable, str(SCRIPT), str(log), str(status), '--style', 'plain'], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 1)

    def test_recorded_native_acquisition_replays_all_styles_without_installation_success(self):
        fixture = ROOT/'tests/fixtures/installer-progress/native-acquisition.jsonl'
        provenance = json.loads(fixture.with_name('native-acquisition-provenance.json').read_text())
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), provenance['journal_sha256'])
        rows = fixture.read_text().splitlines()
        self.assertEqual(len(rows), 16)
        state = ui.Progress((provenance['input_sha256'], provenance['repository_database_sha256']))
        for row in rows:
            state.line(row, True)
            self.assertFalse(state.warning)
        self.assertEqual(state.sequence, 16)
        self.assertEqual(state.meter[1:3], (29831, 29831))
        self.assertEqual(state.item, '8 of 8 archives verified')
        for style in ('bars', 'spectrum', 'scope'):
            with self.subTest(style=style), tempfile.TemporaryDirectory() as directory:
                log, status = Path(directory)/'log', Path(directory)/'status'
                log.touch()
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 15, 100, 0, 0))
                env = dict(os.environ, TERM='xterm-256color')
                argv = [sys.executable, str(SCRIPT), str(log), str(status), '--style', style,
                        '--events', str(fixture), '--input-pin', provenance['input_sha256'],
                        '--repository-pin', provenance['repository_database_sha256']]
                child = subprocess.Popen(argv, env=env, stdout=slave, stderr=slave)
                captured = bytearray()
                try:
                    deadline = time.monotonic()+5
                    while b'8 of 8 archives verified' not in captured and time.monotonic() < deadline:
                        if select.select([master], [], [], 0.1)[0]:
                            captured.extend(os.read(master, 65536))
                    self.assertIsNone(child.poll())
                    self.assertIn(b'29,831 / 29,831 bytes', captured)
                    self.assertIn(b'8 of 8 archives verified', captured)
                    self.assertNotIn(b'Daemonarchy is installed.', captured)
                    # Acquisition has no installer result. Stop only the viewer.
                    child.send_signal(signal.SIGTERM)
                    deadline = time.monotonic()+5
                    while b'\033[?25h' not in captured and time.monotonic() < deadline:
                        if select.select([master], [], [], 0.1)[0]:
                            captured.extend(os.read(master, 65536))
                    self.assertEqual(child.wait(timeout=5), 143)
                    self.assertIn(b'\033[?25h', captured)
                    self.assertFalse(status.exists())
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=5)
                    os.close(master)
                    os.close(slave)

    def test_completed_owner_is_reported_after_incremental_backlog_drains(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase finish\n' + 'ordinary installer detail\n'*40000)
            status.write_text('0\n')
            result = subprocess.run([sys.executable, str(SCRIPT), str(log), str(status), '--style', 'plain'], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn(b'Daemonarchy is installed.', result.stdout.splitlines()[-1])
            self.assertLess(len(result.stdout), 4096)

    def test_real_tty_styles_color_depth_and_owner_completion(self):
        # vt100 serial: 8 basic colors only; xterm: 16 colors; xterm-256color: 256-color
        # syntax; COLORTERM=truecolor: 24-bit; the vt(4) console never gets 256 or 24-bit.
        cases = [('bars', 'vt100', {}, rb'\033\[0(?:;1)?;3[0-7]m', (b'38;5;', b'38;2;', b';9')),
                 ('spectrum', 'xterm-256color', {}, rb'38;5;\d+m', (b'38;2;',)),
                 ('scope', 'xterm', {}, rb';9[0-7]m', (b'38;5;', b'38;2;')),
                 ('spectrum', 'xterm-256color', {'COLORTERM': 'truecolor'}, rb'38;2;\d+;\d+;\d+m', ()),
                 ('spectrum', 'xterm-256color', {'COLORTERM': 'truecolor', 'DAEMONARCHY_CONSOLE': 'vt'},
                  rb';9[0-7]m', (b'38;5;', b'38;2;'))]
        for style, terminal, extra, pattern, forbidden in cases:
            with self.subTest(style=style, term=terminal, extra=extra), tempfile.TemporaryDirectory() as directory:
                log, status = Path(directory)/'log', Path(directory)/'status'
                log.write_text('@@phase base\n@@progress ' + json.dumps(metric(3)) + '\n')
                env = dict(clean_env(), TERM=terminal, **extra)
                with Terminal([str(log), str(status), '--style', style], env, 15, 80) as tty:
                    tty.wait(b'3 / 3 archives')
                    self.assertRegex(bytes(tty.captured), pattern)
                    for sequence in forbidden:
                        self.assertNotIn(sequence, tty.captured)
                    self.assertNotIn(b'Daemonarchy is installed.', tty.captured)
                    status.write_text('0\n')
                    self.assertEqual(tty.exit_code(), 0)
                    self.assertIn(b'Daemonarchy is installed.', tty.captured)
                    self.assertIn(b'\033[?25h', tty.captured)

    def test_real_tty_wait_resize_reduced_motion_and_signal_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase base\n@@progress ' + json.dumps(metric()) + '\n')
            env = dict(clean_env(), TERM='vt100', NO_COLOR='1', DAEMONARCHY_REDUCED_MOTION='1')
            with Terminal([str(log), str(status), '--style', 'scope'], env, 8, 20) as tty:
                tty.read_for(6)
                self.assertIsNone(tty.child.poll())
                self.assertNotIn(b'Daemonarchy is installed.', tty.captured)
                self.assertIn(b'Base sets', tty.captured)
                # A real kernel window-size change must not require another event.
                tty.resize(12, 80)
                tty.wait(b'1 / 3 archives')
                tty.child.send_signal(signal.SIGTERM)
                self.assertEqual(tty.exit_code(), 143)
                self.assertIn(b'\033[?25h', tty.captured)
                self.assertNotIn(b'\033[36m', tty.captured)
                self.assertNotIn(b'\033[0;3', tty.captured)  # NO_COLOR
                # Reduced motion redraws at most once a second and only changed cells.
                self.assertLess(len(tty.captured), 8192)
                self.assertFalse(status.exists())


def clean_env():
    env = dict(os.environ)
    for name in ('NO_COLOR', 'COLORTERM', 'DAEMONARCHY_REDUCED_MOTION', 'DAEMONARCHY_CONSOLE',
                 'DAEMONARCHY_COLOR', 'DAEMONARCHY_GLYPHS', 'DAEMONARCHY_PROGRESS_STYLE',
                 'DAEMONARCHY_SOUND', 'DAEMONARCHY_SOUND_DEVICE', 'DAEMONARCHY_UNATTENDED'):
        env.pop(name, None)
    env['LANG'] = 'C.UTF-8'
    env['DAEMONARCHY_SOUND_DIR'] = tempfile.mkdtemp(dir=SOUND_ROOT.name)
    env['DAEMONARCHY_SOUND_KLD'] = 'off'
    # Never the host's real audio device; tests that play use a file instead.
    env['DAEMONARCHY_SOUND_DEVICE'] = '/nonexistent/daemonarchy-test-dsp'
    return env


class Terminal:
    """The real dashboard on a kernel pseudo-terminal, with keyboard input."""

    def __init__(self, argv, env, rows, cols, command=None):
        self.argv, self.env, self.rows, self.cols = argv, env, rows, cols
        self.command = command or [sys.executable, str(SCRIPT)]
        self.captured = bytearray()

    def __enter__(self):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', self.rows, self.cols, 0, 0))
        def controlling_terminal():
            # A new session whose controlling terminal is this pty, so window
            # size changes reach the screen (and tmux) as SIGWINCH.
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        self.child = subprocess.Popen([*self.command, *self.argv], env=self.env,
                                      stdin=slave, stdout=slave, stderr=slave, preexec_fn=controlling_terminal)
        os.close(slave)
        self.screen = demo.ColorScreen(self.rows, self.cols)
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        return self

    def __exit__(self, *_exc):
        if self.child.poll() is None:
            self.child.kill()
            self.child.wait(timeout=5)
        os.close(self.master)

    def read_once(self, timeout=0.1):
        if select.select([self.master], [], [], timeout)[0]:
            try:
                data = os.read(self.master, 65536)
            except OSError:
                return False
            self.captured.extend(data)
            self.screen.feed(self.decoder.decode(data))
            return bool(data)
        return False

    def read_for(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.read_once()

    def wait(self, needle, seconds=6):
        deadline = time.monotonic() + seconds
        while needle not in self.captured and time.monotonic() < deadline:
            self.read_once()
        if needle not in self.captured:
            raise AssertionError(f'{needle!r} never appeared; screen:\n' + self.text())

    def wait_screen(self, text, seconds=6, present=True):
        deadline = time.monotonic() + seconds
        while (text in self.text()) != present and time.monotonic() < deadline:
            self.read_once()
        if (text in self.text()) != present:
            raise AssertionError(f'{text!r} {"missing from" if present else "still on"} screen:\n' + self.text())

    def text(self):
        return '\n'.join(self.lines())

    def lines(self):
        return [''.join(cell[0] for cell in row) for row in self.screen.cells]

    def exit_code(self, seconds=10):
        """Wait for the process while reading: a FreeBSD pty drops unread output at close."""
        deadline = time.monotonic() + seconds
        while self.child.poll() is None and time.monotonic() < deadline:
            self.read_once(0.05)
        self.drain()
        return self.child.wait(timeout=1)

    def send(self, data):
        os.write(self.master, data)

    def resize(self, rows, cols):
        self.rows, self.cols = rows, cols
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
        self.screen = demo.ColorScreen(rows, cols)

    def drain(self):
        while self.read_once(0.2):
            pass


class FakeCounters:
    """Deterministic kernel counters for the activity model."""

    def __init__(self):
        self.ncpu = 2
        self.tick = 0

    def advance(self):
        self.tick += 1

    def cpu(self):
        return [(self.tick * 50, self.tick * 100), (self.tick * 25, self.tick * 100)]

    def memory(self):
        return dict(total=8 << 30, used=3 << 30, arc=1 << 30)

    def disks(self):
        return {'nda0': (self.tick * 1000, self.tick * (8 << 20), self.tick * 10, self.tick * 90),
                'md0': (0, self.tick * 999999, 0, self.tick * 999)}

    def network(self):
        return {'em0': (self.tick * (2 << 20), self.tick * 4096)}

    def zfs_written(self, pool):
        return self.tick * (16 << 20)


class StagesTickerAndActivityTests(unittest.TestCase):
    def test_timeline_uses_installer_clock_and_marks_skips_and_failure(self):
        clock = [1000.0]
        state = model.Progress(clock=lambda: clock[0], wall=lambda: 1700005000.0)
        for line in ('@@phase disk', '@@step partition 1700004900', '@@step pool 1700004930', '@@phase base',
                     '@@step base 1700004960'):
            state.line(line)
        rows = {row['key']: row for row in state.timeline.rows()}
        self.assertEqual(rows['partition']['state'], 'done')
        self.assertAlmostEqual(rows['partition']['elapsed'], 30.0)
        self.assertEqual(rows['encrypt']['state'], 'skipped')  # never started before a later stage
        self.assertAlmostEqual(rows['pool']['elapsed'], 30.0)
        self.assertEqual(rows['base']['state'], 'active')
        self.assertAlmostEqual(rows['base']['elapsed'], 40.0)
        self.assertNotIn('cuda', rows)  # optional stages appear only when they run
        clock[0] += 5
        self.assertAlmostEqual(state.timeline.total(), 105.0)
        state.line('@@step partition 1700004999')  # never rewinds
        self.assertEqual(state.timeline.active, 'base')
        state.line('@@step encrypt 99999999999')  # implausible clock: arrival time is used
        self.assertEqual(state.timeline.active, 'encrypt')
        self.assertTrue(state.encrypted)
        state.timeline.finish(failed=True)
        rows = {row['key']: row for row in state.timeline.rows()}
        self.assertEqual(rows['encrypt']['state'], 'failed')

    def test_ticker_counts_real_pkg_lines_and_ignores_repository_files(self):
        state = model.Progress()
        for line in ('@@phase fetch', 'Fetching meta.conf: . done', 'Number of packages to be fetched: 3',
                     'Fetching data: .......... done', 'Fetching meta.conf: . done',
                     'Fetching bash-5.3.20: .......... done', 'Fetching sddm-0.21.0.36_7: .......... done'):
            state.line(line)
        self.assertEqual(state.meter[1:3], (2, 3))
        self.assertEqual(list(state.ticker.names), ['bash-5.3.20', 'sddm-0.21.0.36_7'])
        for line in ('@@phase install', '[ 1/2] Installing indexinfo-0.3.1_1...',
                     '[ 1/2] Extracting indexinfo-0.3.1_1: .... done', '[ 2/2] Installing bash-5.3.20...',
                     'pkg: POST-INSTALL script failed'):
            state.line(line)
        self.assertEqual(state.ticker.kind, 'install')
        self.assertEqual((state.ticker.current, state.ticker.total), (2, 2))
        self.assertEqual(list(state.ticker.names), ['indexinfo-0.3.1_1', 'bash-5.3.20'])
        self.assertEqual(state.item, 'bash-5.3.20')
        self.assertIsNone(state.ticker.rate(time.monotonic()))  # under ten seconds observed: no rate
        state.line('@@target disk nda0')
        state.line('@@target pool zroot')
        state.line('@@target disk ../../etc/passwd')
        self.assertEqual((state.target_disk, state.target_pool), ('nda0', 'zroot'))

    def test_activity_rates_come_from_counter_differences(self):
        source, clock = FakeCounters(), [0.0]
        activity = model.Activity(source, interval=0.25, clock=lambda: clock[0])
        self.assertFalse(activity.sample('nda0', 'zroot'))  # first sample has no rate yet
        for _ in range(4):
            clock[0] += 1.0
            source.advance()
            activity.sample('nda0', 'zroot')
        current = activity.view()['current']
        self.assertAlmostEqual(current['disk_write'], 8 << 20)  # only the target disk, never md0
        self.assertAlmostEqual(current['iops'], 100)
        self.assertAlmostEqual(current['net_rx'], 2 << 20)
        self.assertAlmostEqual(current['net_tx'], 4096)
        self.assertEqual([round(c, 2) for c in current['cores']], [0.5, 0.25])
        self.assertAlmostEqual(current['zfs_write'], 16 << 20)
        self.assertEqual(len(activity.view()['history']['disk_write']), 4)
        # Without a named target every real disk counts, but memory disks never do.
        other = model.Activity(source, interval=0.0, clock=lambda: clock[0])
        other.sample()
        clock[0] += 1
        source.advance()
        other.sample()
        self.assertAlmostEqual(other.view()['current']['disk_write'], 8 << 20)
        self.assertFalse(model.Activity(None).view()['available'])

    def test_real_counters_are_readable_here(self):
        source = model.counters()
        if source is None:
            self.skipTest('no supported counter source on this host')
        activity = model.Activity(source, interval=0.0)
        activity.sample()
        time.sleep(0.3)
        activity.sample()
        current = activity.view()['current']
        self.assertTrue(activity.view()['available'], activity.view()['error'])
        self.assertGreater(len(current['cores']), 0)
        self.assertGreater(current['memory']['total'], 0)
        for key in ('disk_write', 'disk_read', 'iops', 'net_rx', 'net_tx'):
            self.assertGreaterEqual(current[key], 0)

    def test_gui_adapter_keeps_live_installer_keys_and_adds_shared_model(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase base\n@@progress ' + json.dumps(metric(2)) + '\n')
            progress = model.InstallProgress(log, status, source=None)
            view = progress.poll()
            for key in ('title', 'details', 'fraction', 'done', 'succeeded', 'recent'):
                self.assertIn(key, view)
            self.assertEqual(view['title'], 'Installing FreeBSD')
            self.assertAlmostEqual(view['fraction'], 2 / 3)
            self.assertFalse(view['done'])
            self.assertIn('stages', view)
            self.assertIn('ticker', view)
            self.assertIn('activity', view)
            json.dumps(view)  # plain data for any front end
            # The dashboard keeps the names the live installer imports from it.
            for name in ('Progress', 'Tail', 'lines', 'status', 'clean'):
                self.assertTrue(hasattr(ui, name))
            status.write_text('0\n')
            view = progress.poll()
            self.assertTrue(view['done'] and view['succeeded'])


def snapshot(**changes):
    state = model.Progress()
    for line in ('@@phase disk', '@@phase base', '@@progress ' + json.dumps(metric(2))):
        state.line(line)
    activity = model.Activity(FakeCounters(), interval=0.0)
    activity.source.advance()
    activity.sample('nda0')
    activity.source.advance()
    activity.sample('nda0')
    snap = dict(schema='daemonarchy/installer-snapshot@1', phase='base', title='Installing FreeBSD',
                meter=dict(label='Release archives expanded', current=2, total=3, unit='archives'),
                item='', stages=state.timeline.rows(), elapsed=12.0,
                ticker=dict(kind='install', names=['bash-5.3.20', 'sddm-0.21.0.36_7'], current=2, total=1188,
                            serial=2, rate=None),
                activity=activity.view(), target=dict(disk='nda0', pool='zroot', encrypted=True),
                warning='', failed=False, result=None, done=False, succeeded=False, idle=0.0, recent=[])
    snap.update(changes)
    return snap


class RenderingTests(unittest.TestCase):
    def app(self, unicode=True, style='spectrum'):
        args = type('Args', (), dict(style=style, log=Path('/nonexistent/log')))()
        env = dict(DAEMONARCHY_GLYPHS='unicode' if unicode else 'ascii', TERM='xterm-256color')
        return ui.App(None, args, env, False, True, False)

    def test_frames_fill_every_size_without_overflow(self):
        for unicode in (True, False):
            for style in ui.STYLES:
                for rows, cols in ((3, 10), (8, 20), (24, 80), (25, 80), (48, 128), (70, 224), (200, 400)):
                    with self.subTest(unicode=unicode, style=style, size=(rows, cols)):
                        app = self.app(unicode, style=style)
                        app.visuals.advance(snapshot())
                        canvas = app.frame(cols, rows, snapshot())
                        self.assertEqual(len(canvas.chars), rows)
                        self.assertTrue(all(len(row) == cols for row in canvas.chars))
                        text = '\n'.join(canvas.plain())
                        if not unicode:
                            self.assertTrue(text.isascii())
                        if rows >= 8:
                            self.assertIn('Base sets', text)
                        self.assertNotRegex(text, r'\d+%  ?(?:done|complete)')

    def test_color_depth_never_sends_truecolor_to_the_vt_console(self):
        depth = ui.color_depth
        self.assertEqual(depth({'TERM': 'xterm', 'NO_COLOR': '1'}, False), 'none')
        self.assertEqual(depth({'TERM': 'vt100'}, False), '8')
        self.assertEqual(depth({'TERM': 'xterm'}, True), '16')
        self.assertEqual(depth({'TERM': 'xterm-256color'}, False), '256')
        self.assertEqual(depth({'TERM': 'xterm-256color', 'COLORTERM': 'truecolor'}, False), 'truecolor')
        self.assertEqual(depth({'TERM': 'xterm-256color', 'COLORTERM': 'truecolor'}, True), '16')
        self.assertEqual(depth({'TERM': 'xterm', 'DAEMONARCHY_COLOR': 'truecolor'}, True), '16')
        colors = ui.Colors('16')
        for rgb in ((255, 60, 60), (0, 220, 90), (132, 93, 249), (90, 90, 100), (255, 255, 255)):
            code = colors.sgr((rgb, None, False))
            self.assertRegex(code, r'^\033\[0;(?:3[0-7]|9[0-7])m$')
        self.assertEqual(ui.Colors('8').sgr(((255, 0, 0), None, True)), '\033[0;1;31m')
        self.assertEqual(ui.Colors('none').sgr(((255, 0, 0), None, False)), '\033[0m')
        self.assertFalse(ui.unicode_ok({'TERM': 'vt100', 'LANG': 'C.UTF-8'}, False))
        self.assertTrue(ui.unicode_ok({'TERM': 'xterm', 'LANG': 'C'}, True))
        self.assertFalse(ui.unicode_ok({'TERM': 'xterm', 'LANG': 'C'}, False))

    def test_key_decoding_needs_no_function_keys(self):
        keys, rest = ui.decode_keys(b'v\tq\x1b[A\x1b[6~\x1b[Z\x03?')
        self.assertEqual(keys, ['v', 'tab', 'q', 'up', 'pgdn', 'backtab', 'ctrl-c', '?'])
        self.assertEqual(rest, b'')
        keys, rest = ui.decode_keys(b'\x1b')
        self.assertEqual((keys, rest), ([], b'\x1b'))  # maybe the start of a sequence
        self.assertEqual(ui.decode_keys(b'\x1b', final=True)[0], ['esc'])


class RetainedInstallReplayTests(unittest.TestCase):
    FIXTURE = ROOT/'tests/fixtures/installer-progress/macbook-1.3.1-install.log'

    def test_fixture_is_scrubbed_and_matches_its_provenance(self):
        provenance = json.loads(self.FIXTURE.with_name('macbook-1.3.1-install-provenance.json').read_text())
        data = self.FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), provenance['fixture_sha256'])
        text = data.decode('utf-8')
        package_row = re.compile(r'^(?:\t|\[\s*\d+/\d+\] |Fetching )')
        for line in text.splitlines():
            self.assertNotRegex(line, r'\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b')
            self.assertNotRegex(line, r'[\w.+-]+@[\w-]+\.[\w.-]+')
            self.assertNotRegex(line, r'\b[0-9a-fA-F]{32,}\b')
            self.assertNotRegex(line, r'(?i)ssid|/home/[^u]|password|psk=')
            if not package_row.match(line):
                self.assertNotRegex(line, r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
        self.assertNotRegex(text, r'Boot[0-9A-F]{4}\* (?!Daemonarchy|Other boot entry)')
        self.assertNotIn('@@phase user', text)  # the account stage was never reached

    def test_replay_of_real_macbook_install_shows_stages_ticker_and_no_success(self):
        clock = [0.0]
        state = model.Progress(clock=lambda: clock[0])
        seen_fetch = None
        for line in self.FIXTURE.read_text().split('\n')[:-1]:  # the last line was cut off mid-write
            clock[0] += 0.05
            state.line(line)
            if state.phase == 'fetch' and state.meter:
                seen_fetch = state.meter
        self.assertFalse(state.warning)
        self.assertEqual(seen_fetch[1:], (931, 931, 'archives'))
        self.assertEqual(state.phase, 'install')
        self.assertEqual(state.meter, ('Processing package position', 976, 1188, 'packages'))
        self.assertEqual(state.item, 'suitesparse-cholmod-5.3.5')
        self.assertEqual(state.ticker.kind, 'install')
        self.assertEqual(state.ticker.names[-1], 'suitesparse-cholmod-5.3.5')
        self.assertEqual(state.ticker.serial, 931 + 976)
        self.assertGreater(state.ticker.rate(clock[0]), 0)
        rows = {row['key']: row['state'] for row in state.timeline.rows()}
        self.assertEqual([rows[key] for key in ('partition', 'base', 'loader', 'config', 'fetch')], ['done'] * 5)
        self.assertEqual(rows['packages'], 'active')
        self.assertEqual(rows['encrypt'], 'skipped')  # this 1.3.1 log has no step markers
        self.assertEqual(rows['account'], 'pending')
        self.assertEqual(model.title(state), 'Installing the desktop')
        self.assertNotIn('installed', '\n'.join(ui.lines(state, 'bars', 120)).lower().replace('installing', ''))

    def test_replay_through_the_real_screen_in_a_pty(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.touch()
            env = dict(clean_env(), TERM='xterm-256color', DAEMONARCHY_ACTIVITY='off')
            lines = self.FIXTURE.read_bytes().splitlines(keepends=True)
            with Terminal([str(log), str(status)], env, 40, 120) as tty:
                for start in range(0, len(lines), 400):
                    with log.open('ab') as stream:
                        stream.writelines(lines[start:start + 400])
                    tty.read_for(0.15)
                tty.wait_screen('976 / 1,188 packages', 10)
                screen = tty.text()
                self.assertIn('suitesparse-cholmod-5.3.5', screen)
                self.assertIn('Installing 976/1,188', screen)
                self.assertIn('Packages', screen)
                self.assertIn('Activity counters unavailable', screen)
                self.assertNotIn('Daemonarchy is installed', screen)
                tty.child.send_signal(signal.SIGTERM)
                self.assertEqual(tty.exit_code(), 143)


@unittest.skipUnless(shutil.which('tmux'), 'tmux is not installed')
class TmuxWindowControlTests(unittest.TestCase):
    """The install screen as window 0 of the installer's real tmux session.

    Keys go through the real kernel pty with tmux's default Ctrl-b prefix;
    tmux's own list-panes and capture-pane report what is on screen.
    """
    PREFIX = b'\x02'

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.socket = f'daemonarchy-test-{os.getpid()}-{self._testMethodName[-24:]}'
        self.addCleanup(lambda: subprocess.run(['tmux', '-L', self.socket, 'kill-server'], capture_output=True))
        self.log, self.status = self.root/'log', self.root/'status'
        self.log.write_text('@@phase base\n@@progress ' + json.dumps(metric(1)) + '\nfirst log line\n')

    def env(self, **extra):
        return dict(clean_env(), TERM='xterm-256color', ISO_SHARE=str(SHARE), DAEMONARCHY_ACTIVITY='off',
                    DAEMONARCHY_TMUX_SOCKET=self.socket, DAEMONARCHY_PANE_SHELL='/bin/sh',
                    DAEMONARCHY_REMOTE_STATE=str(self.root/'remote'),
                    DAEMONARCHY_REMOTE_PUBLIC=str(self.root/'remote.status'), **extra)

    def screen(self, rows=40, cols=140, **extra):
        return Terminal([str(self.log), str(self.status)], self.env(**extra), rows, cols,
                        command=['bash', str(WRAPPER)])

    def tmux(self, *args):
        return subprocess.run(['tmux', '-L', self.socket, *args], capture_output=True, text=True).stdout

    def panes(self):
        rows = self.tmux('list-panes', '-s', '-F', '#{window_index}.#{pane_index} #{pane_id} #{pane_title} '
                         '#{pane_dead} #{window_zoomed_flag} #{pane_in_mode} #{window_active}')
        return [row.split() for row in rows.splitlines()]

    def windows(self):
        return self.tmux('list-windows', '-F', '#{window_index}:#{window_name}').split()

    def capture(self, target, history=False):
        return self.tmux('capture-pane', '-p', '-t', target, *(('-S', '-') if history else ()))

    def until(self, tty, check, seconds=8, message=''):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            tty.read_once(0.05)
            try:
                if check():
                    return
            except (IndexError, KeyError, ValueError):
                pass
        self.fail(message or f'condition not met; panes={self.panes()} windows={self.windows()}')

    def press(self, tty, *keys):
        for key in keys:
            tty.send(key)
            tty.read_for(0.4)

    def choose(self, tty, target, key):
        """Answer the chooser of a new pane or window once it is showing."""
        self.until(tty, lambda: 'What should this pane show?' in self.capture(target))
        self.press(tty, key)

    def started(self, tty):
        self.until(tty, lambda: 'Base sets' in self.capture('install:0.0'), 10)
        self.assertEqual(self.panes()[0][2], 'progress')

    def test_splits_windows_views_and_navigation_use_tmux_default_keys(self):
        with self.screen() as tty:
            self.started(tty)
            self.press(tty, self.PREFIX + b'%')
            self.until(tty, lambda: len(self.panes()) == 2)
            self.choose(tty, 'install:0.1', b'1')  # log
            self.until(tty, lambda: 'first log line' in self.capture('install:0.1'))
            with self.log.open('a') as stream:
                stream.write('second log line\n')
            self.until(tty, lambda: 'second log line' in self.capture('install:0.1'))
            self.press(tty, self.PREFIX + b'"')
            self.until(tty, lambda: len(self.panes()) == 3)
            self.choose(tty, 'install:0.2', b'd')  # diagnostics
            self.until(tty, lambda: '== Processes using the most CPU' in self.capture('install:0.2', True))
            self.press(tty, self.PREFIX + b'c')
            self.until(tty, lambda: len(self.windows()) == 2)
            self.choose(tty, 'install:1.0', b's')
            self.until(tty, lambda: 'install-shell#' in self.capture('install:1.0'))
            self.assertIn('1:shell', self.windows())
            tty.send(b'echo pane-$((40+2))\r')
            self.until(tty, lambda: 'pane-42' in self.capture('install:1.0'))
            self.press(tty, self.PREFIX + b'0')
            self.until(tty, lambda: self.panes()[0][6] == '1')
            self.press(tty, self.PREFIX + b'n')
            self.until(tty, lambda: self.panes()[-1][6] == '1')
            self.press(tty, self.PREFIX + b'p')
            self.until(tty, lambda: self.panes()[0][6] == '1')
            # o and the arrow keys move between panes of window 0.
            before = self.tmux('display-message', '-p', '#{pane_index}').strip()
            self.press(tty, self.PREFIX + b'o')
            self.until(tty, lambda: self.tmux('display-message', '-p', '#{pane_index}').strip() != before)
            self.until(tty, lambda: self.tmux('display-message', '-p', '#{pane_index}').strip() == '0')
            self.press(tty, self.PREFIX + b'\x1b[C')  # Right: to a pane of the right column
            self.until(tty, lambda: self.tmux('display-message', '-p', '#{pane_index}').strip() != '0')
            self.press(tty, self.PREFIX + b'\x1b[D')  # Left: back to the progress view
            self.until(tty, lambda: self.tmux('display-message', '-p', '#{pane_index}').strip() == '0')
            self.press(tty, self.PREFIX + b'z')
            self.until(tty, lambda: self.panes()[0][4] == '1')
            self.press(tty, self.PREFIX + b'z')
            self.until(tty, lambda: self.panes()[0][4] == '0')
            self.press(tty, self.PREFIX + b'G', self.PREFIX + b'H')
            self.until(tty, lambda: {'2:log', '3:diagnostics'} <= set(self.windows()))
            self.assertFalse(self.status.exists())
            self.assertIsNone(tty.child.poll())

    def test_progress_window_cannot_be_closed_and_closing_others_asks_first(self):
        with self.screen() as tty:
            self.started(tty)
            progress = self.panes()[0][1]
            self.press(tty, self.PREFIX + b'x', self.PREFIX + b'&', self.PREFIX + b'd')
            tty.read_for(0.5)
            self.assertEqual([row[1] for row in self.panes()], [progress])
            self.assertEqual(self.tmux('list-clients', '-F', '#{client_session}').split(), ['install'])
            self.press(tty, self.PREFIX + b'%')
            self.until(tty, lambda: len(self.panes()) == 2)
            self.choose(tty, 'install:0.1', b'2')
            self.press(tty, self.PREFIX + b'x')
            self.press(tty, b'n')  # tmux's own y/n confirmation
            self.assertEqual(len(self.panes()), 2)
            self.press(tty, self.PREFIX + b'x', b'y')
            self.until(tty, lambda: len(self.panes()) == 1)
            self.press(tty, self.PREFIX + b'c')
            self.choose(tty, 'install:1.0', b's')
            self.until(tty, lambda: len(self.windows()) == 2)
            self.press(tty, self.PREFIX + b'&', b'y')
            self.until(tty, lambda: len(self.windows()) == 1)
            # C-b w offers a window menu that has no kill action.
            self.press(tty, self.PREFIX + b'w')
            self.until(tty, lambda: self.tmux('display-message', '-p', '#{client_flags}') is not None)
            tty.send(b'\x1b')
            # A crashed or interrupted progress view comes straight back.
            tty.send(b'\x03\x03')
            self.until(tty, lambda: self.panes()[0][1] == progress and self.panes()[0][3] == '0'
                       and 'Base sets' in self.capture(progress), 10)
            self.assertIsNone(tty.child.poll())
            self.assertFalse(self.status.exists())

    def test_help_copy_mode_and_literal_prefix(self):
        with self.screen() as tty:
            self.started(tty)
            keys = self.tmux('list-keys', '-N', '-T', 'prefix')
            for text in ('Split left/right', 'Split top/bottom', 'Close the pane', 'Zoom', 'New window',
                         'Window list', 'Scroll/copy mode', 'Detach is not available', 'install log',
                         'diagnostics', 'remote debugging', 'Send C-b'):
                self.assertIn(text, keys)
            self.press(tty, self.PREFIX + b'?')
            self.until(tty, lambda: self.panes()[0][5] == '1')  # the key list in tmux's view mode
            self.press(tty, b'q')
            self.until(tty, lambda: self.panes()[0][5] == '0')
            self.press(tty, self.PREFIX + b'%')
            self.choose(tty, 'install:0.1', b'1')
            self.until(tty, lambda: 'first log line' in self.capture('install:0.1'))
            self.press(tty, self.PREFIX + b'[')
            self.until(tty, lambda: self.panes()[1][5] == '1')
            self.press(tty, b'q')
            self.until(tty, lambda: self.panes()[1][5] == '0')
            self.press(tty, self.PREFIX + b'x', b'y', self.PREFIX + b'c')
            self.choose(tty, 'install:1.0', b's')
            self.until(tty, lambda: 'install-shell#' in self.capture('install:1.0'))
            tty.send(b'cat -v\r')
            tty.read_for(0.5)
            tty.send(self.PREFIX + self.PREFIX + b'\r')
            self.until(tty, lambda: '^B' in self.capture('install:1.0'))
            tty.send(b'\x04exit\r')  # exit closes the pane, as in tmux
            self.until(tty, lambda: len(self.windows()) == 1)

    def test_sound_keys_and_status_line(self):
        pcm = self.root/'dsp.raw'
        env = dict(DAEMONARCHY_SOUND='on', DAEMONARCHY_SOUND_DEVICE=f'file:{pcm}', DAEMONARCHY_SOUND_DIR=str(self.root/'sound'))
        self.addCleanup(sound.stop, dict(DAEMONARCHY_SOUND_DIR=env['DAEMONARCHY_SOUND_DIR']))
        with self.screen(**env) as tty:
            self.started(tty)
            self.assertEqual(self.tmux('show', '-gv', '@sound').strip(), '♪70%')
            keys = self.tmux('list-keys', '-N', '-T', 'prefix')
            for text in ('Sound: mute or unmute', 'Sound: volume up', 'Sound: volume down', 'Sound: ambient'):
                self.assertIn(text, keys)
            self.press(tty, self.PREFIX + b'm')
            self.until(tty, lambda: self.tmux('show', '-gv', '@sound').strip() == '♪ muted')
            self.press(tty, self.PREFIX + b'm', self.PREFIX + b'+')
            self.until(tty, lambda: self.tmux('show', '-gv', '@sound').strip() == '♪80%')
            self.press(tty, self.PREFIX + b'-', self.PREFIX + b'-')
            self.until(tty, lambda: self.tmux('show', '-gv', '@sound').strip() == '♪60%')
            self.until(tty, lambda: '♪ 60%' in self.capture('install:0.0'))
            # The player started with the screen; volume feedback reached the (file) device.
            self.until(tty, lambda: pcm.exists() and pcm.stat().st_size > 0)

    def test_completion_waits_for_open_shell_then_reports_the_result(self):
        with self.screen() as tty:
            self.started(tty)
            self.press(tty, self.PREFIX + b'%')
            self.choose(tty, 'install:0.1', b'4')
            self.until(tty, lambda: 'install-shell#' in self.capture('install:0.1'))
            self.status.write_text('0\n')
            self.until(tty, lambda: 'Close the other panes' in self.capture('install:0.0'))
            self.assertIn('Daemonarchy is installed.', self.capture('install:0.0'))
            tty.read_for(1)
            self.assertIsNone(tty.child.poll())  # the shell is never killed
            tty.send(b'exit\r')
            self.assertEqual(tty.exit_code(), 0)
            self.assertIn(b'Daemonarchy is installed.', tty.captured)

    def test_failed_install_reports_its_status_through_tmux(self):
        with self.screen() as tty:
            self.started(tty)
            self.status.write_text('7\n')
            self.assertEqual(tty.exit_code(), 7)
            self.assertIn(b'Installer stopped (exit 7)', tty.captured)

    def test_small_terminal_is_zoom_only_and_resize_reflows(self):
        with self.screen(rows=14, cols=50) as tty:
            self.started(tty)
            self.press(tty, self.PREFIX + b'%')
            self.until(tty, lambda: len(self.windows()) == 2)  # a full-screen window, not a split
            self.assertEqual(len(self.panes()), 2)
            self.choose(tty, 'install:1.0', b'1')
            self.press(tty, self.PREFIX + b'0')
            tty.resize(40, 140)
            self.until(tty, lambda: self.tmux('display-message', '-p', '-t', 'install:0', '#{window_width}').strip() == '140')
            self.press(tty, self.PREFIX + b'%')
            self.until(tty, lambda: len([p for p in self.panes() if p[0].startswith('0.')]) == 2)
            self.choose(tty, 'install:0.1', b'2')
            self.until(tty, lambda: 'Base sets' in self.capture('install:0.0'))
            tty.resize(24, 80)
            self.until(tty, lambda: self.tmux('display-message', '-p', '-t', 'install:0', '#{window_width}').strip() == '80')
            self.until(tty, lambda: 'Installing FreeBSD' in self.capture('install:0.0'))

    def test_remote_debug_window_and_pairing_banner(self):
        remote = self.root/'remote'
        (remote/'requests').mkdir(parents=True)
        (remote/'active').touch()
        (remote/'requests'/('a' * 64)).write_text('SHA256:agentfingerprint (ED25519)\nssh-ed25519 AAAA\n')
        calls = self.root/'calls'
        stub = self.root/'remote-debug'
        stub.write_text(f'#!/bin/sh\necho "$@" >>{calls}\necho "Agent pairing request: SHA256:agentfingerprint"\n'
                        'printf "Does this match? [y/N] "\nread answer\necho "answer=$answer" >>' + str(calls) + '\n')
        stub.chmod(0o755)
        with self.screen(DAEMONARCHY_REMOTE_DEBUG=str(stub)) as tty:
            self.started(tty)
            self.until(tty, lambda: 'pairing request waiting: press C-b R' in self.capture('install:0.0'))
            self.press(tty, self.PREFIX + b'R')
            self.until(tty, lambda: 'Does this match?' in self.capture('install:1.0'))
            self.assertIn('1:remote-debug', self.windows())
            tty.send(b'y\r')
            self.until(tty, lambda: calls.exists() and 'answer=y' in calls.read_text())
            self.assertEqual(calls.read_text().splitlines()[0], 'listen')
            tty.send(b'\r')  # leave the view; a background listener would keep running
            self.until(tty, lambda: len(self.windows()) == 1)
            self.assertFalse(self.status.exists())

    def test_serial_class_terminals_get_the_direct_screen(self):
        env = self.env()
        env['TERM'] = 'vt100'
        with Terminal([str(self.log), str(self.status)], env, 24, 80, command=['bash', str(WRAPPER)]) as tty:
            tty.wait(b'1 / 3 archives')
            self.assertEqual(self.tmux('list-sessions'), '')
            self.assertNotIn('┌'.encode(), tty.captured)
            self.status.write_text('0\n')
            self.assertEqual(tty.exit_code(), 0)



class FakeClient:
    """Records cues instead of sending them."""

    def __init__(self):
        self.cues, self.levels = [], []

    def play(self, cue, **params):
        self.cues.append(cue)
        return True

    def ambient(self, levels):
        self.levels.append(levels)
        return True


def event_log(*rows):
    return [dict(serial=index + 1, **row) for index, row in enumerate(rows)]


class SoundEventTests(unittest.TestCase):
    """Sounds and flourishes come from the model's events, which come from real markers."""

    def test_model_events_follow_markers_packages_and_the_result(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase disk\n@@step partition 1\n@@step pool 2\n@@phase base\n@@phase install\n'
                           + ''.join(f'[{i}/120] Installing p{i}-1.0...\n' for i in range(1, 61)))
            now = [1000.0]
            monitor = model.Monitor(log, status, source=None, clock=lambda: now[0])
            monitor.poll()
            kinds = [(e['kind'], e.get('stage')) for e in monitor.snapshot()['events']]
            self.assertEqual(kinds[:6], [('stage-start', 'partition'), ('stage-done', 'partition'),
                                         ('stage-start', 'pool'), ('stage-done', 'pool'),
                                         ('stage-start', 'base'), ('stage-done', 'base')])
            packages = [e for e in monitor.snapshot()['events'] if e['kind'] == 'packages']
            self.assertEqual((packages[-1]['current'], packages[-1]['total']), (60, 120))
            self.assertTrue(packages[-1]['milestone'])  # 50 was crossed
            # Nothing happens with time alone, until a genuine wait is announced once.
            serial = monitor.events.serial
            now[0] += model.WAITING - 1
            monitor.poll()
            self.assertEqual(monitor.events.serial, serial)
            now[0] += 2
            monitor.poll()
            monitor.poll()
            self.assertEqual([e['kind'] for e in monitor.snapshot()['events'][-1:]], ['waiting'])
            self.assertEqual(monitor.events.serial, serial + 1)
            status.write_text('3\n')
            monitor.poll()
            done = monitor.snapshot()['events'][-1]
            self.assertEqual((done['kind'], done['result'], done['succeeded']), ('done', 3, False))

    def test_event_to_sound_mapping(self):
        client = FakeClient()
        clock = [0.0]
        director = sound.Director(client, clock=lambda: clock[0])
        history = event_log(dict(kind='stage-start', stage='base'))
        director.feed(dict(events=history))
        self.assertEqual(client.cues, [], 'a screen that starts late does not replay history')
        rows = history
        new = [dict(serial=2, kind='stage-done', stage='base'), dict(serial=3, kind='stage-start', stage='packages'),
               dict(serial=4, kind='packages', current=49, total=120, milestone=False),
               dict(serial=5, kind='packages', current=50, total=120, milestone=True),
               dict(serial=6, kind='warning', text='x'), dict(serial=7, kind='waiting', seconds=21),
               dict(serial=8, kind='done', result=0, succeeded=True)]
        director.feed(dict(events=rows + new))
        self.assertEqual(client.cues, ['stage_done', 'stage', 'tick', 'milestone', 'net_fail', 'attract', 'fanfare'],
                         'the 50th package is a milestone; a burst of package lines is one blip')
        clock[0] += 1
        director.feed(dict(events=rows + new + [dict(serial=9, kind='packages', current=51, total=120)]))
        self.assertEqual(client.cues[-1], 'tick')
        failed = sound.Director(FakeClient())
        failed.feed(dict(events=[dict(serial=4, kind='done', result=1, succeeded=False)]))
        self.assertEqual(failed.client.cues, ['error'], 'a known result is announced even to a late screen')
        self.assertEqual(sound.Director.cues_for(dict(kind='failed')), [('error', {})])

    def test_ambient_levels_are_measured_activity_only(self):
        self.assertIsNone(sound.ambient_levels({}))
        idle = sound.ambient_levels(dict(current=dict(cores=[0.0, 0.0], disk_write=0, disk_read=0, net_rx=0, net_tx=0),
                                         peaks={}))
        self.assertEqual(idle, dict(cpu=0.0, disk=0.0, net=0.0))
        busy = sound.ambient_levels(snapshot()['activity'])
        self.assertGreater(busy['disk'], 0.5)
        ambient = sound.Ambient()
        block = [0.0] * 4096
        ambient.update(idle, 0.0)
        ambient.fill(block, 0, 0.0)
        self.assertEqual(max(map(abs, block)), 0.0, 'no measured activity, no music')
        ambient.update(busy, 0.0)
        ambient.fill(block, 4096, 0.0)
        self.assertGreater(max(map(abs, block)), 0.0)
        block = [0.0] * 4096
        ambient.fill(block, 8192 * 10, 5.0)  # measurements stopped arriving
        self.assertFalse(ambient.active(5.0))

    def test_flourishes_start_only_from_events(self):
        visuals = ui.Visuals(ui.Glyphs(True), logo=[])
        base = snapshot()
        visuals.advance(dict(base, events=event_log(dict(kind='stage-start', stage='base', label='Base sets'))))
        self.assertIsNone(visuals.card, 'history is not a new stage')
        visuals.advance(dict(base, events=event_log(dict(kind='stage-start', stage='base', label='Base sets'),
                                                    dict(kind='stage-done', stage='base', label='Base sets'),
                                                    dict(kind='packages', what='install', current=100, total=900,
                                                         milestone=True))))
        self.assertIn('base', visuals.flash)
        self.assertEqual(visuals.milestone[0], '100 packages')
        self.assertIsNone(visuals.finale)
        visuals.advance(dict(base, done=True, succeeded=True, result=0,
                             events=event_log(*[dict(kind='x')] * 3, dict(kind='done', result=0, succeeded=True))))
        self.assertEqual(visuals.finale[0], True)
        # The shimmer moves only with measured activity.
        still = ui.Visuals(ui.Glyphs(True), logo=[])
        quiet = dict(base, activity=dict(base['activity'], current={}, peaks={}))
        for _ in range(5):
            still.advance(quiet)
            time.sleep(0.01)
        self.assertEqual(still.shimmer, 0.0)
        reduced = ui.Visuals(ui.Glyphs(True), reduced=True, logo=[])
        for _ in range(3):
            reduced.advance(base)
        self.assertEqual(reduced.shimmer, 0.0)

    def test_finale_card_and_mascot_render_in_every_size(self):
        args = type('Args', (), dict(style='spectrum', log=Path('/nonexistent/log')))()
        for unicode in (True, False):
            for rows, cols in ((8, 20), (24, 80), (40, 140), (60, 200)):
                app = ui.App(None, args, dict(DAEMONARCHY_GLYPHS='unicode' if unicode else 'ascii', TERM='xterm'),
                             False, True, False)
                app.visuals.seen = 0
                for snap in (snapshot(events=event_log(dict(kind='stage-start', stage='base', label='Base sets'))),
                             snapshot(done=True, succeeded=True, result=0, title='Daemonarchy is installed.',
                                      events=event_log(dict(kind='stage-start', stage='base', label='Base sets'),
                                                       dict(kind='done', result=0, succeeded=True)))):
                    for _ in range(3):
                        app.visuals.advance(snap)
                        canvas = app.frame(cols, rows, snap)
                    self.assertTrue(all(len(row) == cols for row in canvas.chars))
                    text = '\n'.join(canvas.plain())
                    if not unicode:
                        self.assertTrue(text.isascii(), text)
                if rows >= 24:
                    self.assertIn('Daemonarchy is installed', text)
                if cols >= 140:
                    self.assertTrue(any(c in text for c in ('▀█▄▄▄█▀', '\\_____/')), 'the mascot stands top right')


class SoundControlTests(unittest.TestCase):
    def env(self, **extra):
        return dict(clean_env(), **extra)

    def test_mode_resolution_and_automatic_silence(self):
        resolve = sound.resolve
        env = self.env()
        self.assertEqual(resolve(env, {}, '', 'vt', True), ('on', 'default'))
        self.assertEqual(resolve(env, {}, '', 'serial', True)[0], 'off')
        self.assertEqual(resolve(env, {}, '', 'none', True)[0], 'off')
        self.assertEqual(resolve(env, {}, '', 'vt', False), ('off', 'no audio device'))
        unattended = self.env(DAEMONARCHY_UNATTENDED='1')
        self.assertIn('unattended', resolve(unattended, {}, '', 'vt', True)[1])
        self.assertEqual(resolve(unattended, {}, 'on', 'vt', True)[0], 'on', 'the loader can ask for sound')
        self.assertEqual(resolve(self.env(DAEMONARCHY_UNATTENDED='1', DAEMONARCHY_SOUND='quiet'), {}, '', 'vt', True)[0],
                         'quiet', 'so can the CIDATA answers')
        self.assertEqual(resolve(env, {}, 'off', 'vt', True)[0], 'off')
        self.assertEqual(resolve(env, dict(mode='quiet'), 'off', 'vt', True)[0], 'quiet', 'the installer choice wins')
        self.assertEqual(sound.console_kind({}, '/dev/ttyu0'), 'serial')
        self.assertEqual(sound.console_kind({}, '/dev/ttyv0'), 'vt')
        self.assertEqual(sound.console_kind({'TERM': 'vt100'}, '/dev/ttyv0'), 'serial')
        self.assertEqual(sound.console_kind({}, ''), 'none')
        self.assertEqual(sound.console_kind({'WAYLAND_DISPLAY': 'wayland-1'}, ''), 'vt')

    def test_mute_volume_ambient_and_labels(self):
        device = tempfile.NamedTemporaryFile(prefix='dsp-')
        self.addCleanup(device.close)
        env = self.env(DAEMONARCHY_SOUND='on', DAEMONARCHY_SOUND_DEVICE=f'file:{device.name}')
        self.addCleanup(sound.stop, env)
        state = sound.State(env)
        self.assertEqual(state.label(), '♪ 70%')
        self.assertEqual(sound.ctl('toggle-mute', env).label(), '♪ muted')
        self.assertEqual(sound.ctl('toggle-mute', env).label(), '♪ 70%')
        for _ in range(6):
            state = sound.ctl('up', env)
        self.assertEqual(state.volume, 100)
        for _ in range(12):
            state = sound.ctl('down', env)
        self.assertEqual((state.volume, state.muted, state.audible()), (0, True, False))
        sound.ctl('up', env)
        self.assertEqual(sound.ctl('ambient', env).ambient, False)
        self.assertEqual(sound.ctl('ambient', env).ambient, True)
        chosen = dict(env)
        del chosen['DAEMONARCHY_SOUND']
        quiet = sound.ctl('mode=quiet', chosen)
        self.assertEqual(quiet.label(), '♪ quiet 10%')
        client = sound.Client(chosen)
        self.assertFalse(client.wants('tick'), 'quiet keeps only the moments that matter')
        self.assertTrue(client.wants('fanfare'))
        with self.assertRaises(ValueError):
            sound.ctl('mode=loud', env)
        off = sound.State(self.env(DAEMONARCHY_SOUND='off'))
        self.assertFalse(off.audible())
        self.assertIn('off', off.label(False))
        self.assertTrue(off.label(False).isascii())

    def test_sending_never_blocks_or_fails(self):
        env = self.env(DAEMONARCHY_SOUND='on')
        client = sound.Client(env)
        started = time.monotonic()
        for _ in range(500):
            self.assertFalse(client.play('tick'))  # no player: dropped
        # A player that never reads: its queue fills and further cues are dropped, never waited on.
        directory = Path(env['DAEMONARCHY_SOUND_DIR'])
        directory.mkdir(parents=True, exist_ok=True)
        stalled = socket_bound(directory/'sock')
        try:
            results = [client.play('fanfare') for _ in range(5000)]
            self.assertTrue(results[0])
            self.assertFalse(results[-1])
        finally:
            stalled.close()
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertFalse(client.play('no-such-cue'))

    def test_player_writes_oss_pcm_and_respects_mute(self):
        with tempfile.TemporaryDirectory() as directory:
            pcm = Path(directory)/'dsp.raw'
            env = self.env(DAEMONARCHY_SOUND='on', DAEMONARCHY_SOUND_DEVICE=f'file:{pcm}')
            run = lambda *argv: subprocess.run([sys.executable, str(LIBEXEC/'sound.py'), *argv], env=env,
                                               capture_output=True, text=True, timeout=10)
            try:
                self.assertEqual(run('ensure').returncode, 0)
                self.assertEqual(run('play', 'stage_done').returncode, 0)
                expected = len(sound.render('stage_done')) * 2
                deadline = time.monotonic() + 5
                while (not pcm.exists() or pcm.stat().st_size < expected) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertGreaterEqual(pcm.stat().st_size, expected)
                written = -1
                while written != pcm.stat().st_size and time.monotonic() < deadline + 5:
                    written = pcm.stat().st_size  # Let the cue (and the wall-clock padding) finish.
                    time.sleep(0.5)
                run('ctl', 'mute')
                run('play', 'fanfare')
                time.sleep(0.6)
                self.assertEqual(pcm.stat().st_size, written, 'muted: nothing reaches the device')
                self.assertIn('muted', run('label', '--long').stdout)
            finally:
                run('stop')

    def test_player_stays_while_used_and_exits_when_left_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            env = self.env(DAEMONARCHY_SOUND='on', DAEMONARCHY_SOUND_DEVICE=f'file:{directory}/dsp.raw')
            player = subprocess.Popen([sys.executable, str(LIBEXEC/'sound.py'), 'serve', '--idle-exit', '1'], env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.addCleanup(lambda: player.poll() is None and player.kill())
            client = sound.Client(env)
            deadline = time.monotonic() + 2.5
            while time.monotonic() < deadline:
                client._send(dict(hello=1))  # what Director.feed's keepalive sends
                time.sleep(0.3)
            self.assertIsNone(player.poll(), 'a front end that keeps in touch keeps the player')
            self.assertEqual(player.wait(timeout=5), 0, 'left alone, the player exits by itself')
            self.assertFalse((Path(env['DAEMONARCHY_SOUND_DIR'])/'pid').exists())

    def test_no_device_or_a_broken_device_is_silent_and_reported(self):
        env = self.env(DAEMONARCHY_SOUND='on', DAEMONARCHY_SOUND_DEVICE='/nonexistent/dsp')
        self.assertFalse(sound.ensure(env))
        self.assertEqual(sound.State(env).label(), '♪ off (no audio device)')
        with tempfile.TemporaryDirectory() as directory:
            env = self.env(DAEMONARCHY_SOUND='on', DAEMONARCHY_SOUND_DEVICE=directory)  # open() fails
            player = sound.Player(env)
            self.assertFalse(player.device.open())
            player.status('off', player.device.error)
            self.assertIn('audio device unavailable', sound.State(env).label())
        env = self.env()
        self.assertEqual(sound.resolve(env, {}, '', 'serial', True)[0], 'off')
        self.assertFalse(sound.ensure(dict(env, TERM='vt100')))

    def test_an_install_finishes_the_same_with_sound_broken(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase base\n@@phase install\n[1/2] Installing a-1...\n[2/2] Installing b-1...\n')
            status.write_text('5\n')
            sound_dir = Path(directory)/'not-a-directory'
            sound_dir.write_text('')
            env = dict(clean_env(), DAEMONARCHY_SOUND='on', DAEMONARCHY_SOUND_DIR=str(sound_dir),
                       DAEMONARCHY_SOUND_DEVICE='/nonexistent/dsp')
            result = subprocess.run([sys.executable, str(SCRIPT), str(log), str(status), '--style', 'plain'],
                                    env=env, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 5)
            self.assertIn(b'Installer stopped (exit 5)', result.stdout)
            self.assertEqual(result.stderr, b'')

    def test_screen_keys_mute_and_set_the_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase base\n@@progress ' + json.dumps(metric(1)) + '\n')
            env = dict(clean_env(), TERM='xterm-256color', DAEMONARCHY_SOUND='on', DAEMONARCHY_CELEBRATE='0')
            settings = Path(env['DAEMONARCHY_SOUND_DIR'])/'settings'
            with Terminal([str(log), str(status)], env, 30, 120) as tty:
                tty.wait_screen('♪ 70%')
                tty.send(b'm')
                tty.wait_screen('♪ muted')
                self.assertIn('muted=1', settings.read_text())
                tty.send(b'm+')
                tty.wait_screen('♪ 80%')
                tty.send(b'--')
                tty.wait_screen('♪ 60%')
                tty.send(b'a')
                tty.wait_screen('ambient off')
                status.write_text('0\n')
                self.assertEqual(tty.exit_code(), 0)

    def test_previews_and_raw_chimes_are_real_pcm(self):
        for name in sound.CUES:
            samples = sound.render(name)
            self.assertGreater(len(samples), sound.RATE * 0.01, name)
            self.assertLess(len(samples), sound.RATE * 3, name)
            peak = max(abs(v) for v in samples)
            self.assertTrue(500 < peak < 32767, (name, peak))
            self.assertIn(name, sound.DESCRIPTIONS)
        self.assertNotEqual(sound.render('tick', step=1), sound.render('tick', step=2), 'the ticker walks a scale')
        with tempfile.TemporaryDirectory() as directory:
            written = sound.preview(directory)
            self.assertEqual(len(written), len(sound.CUES) + 2)
            header = (Path(directory)/'tour.wav').read_bytes()[:44]
            self.assertEqual((header[:4], header[8:16]), (b'RIFF', b'WAVEfmt '))
            self.assertEqual(struct.unpack('<HHI', header[20:28]), (1, 1, sound.RATE))
        raw = sound.raw8k(sound.render('boot'))
        self.assertAlmostEqual(len(raw) / 8000, len(sound.render('boot')) / sound.RATE, delta=0.01)


def socket_bound(path):
    import socket as socket_module
    server = socket_module.socket(socket_module.AF_UNIX, socket_module.SOCK_DGRAM)
    server.bind(str(path))
    return server


class CharmTests(unittest.TestCase):
    def charm(self, *argv, **extra):
        env = dict(clean_env(), TERM='xterm-256color', DAEMONARCHY_SOUND='off', **extra)
        return subprocess.run([sys.executable, str(LIBEXEC/'charm.py'), *argv], env=env, capture_output=True,
                              text=True, timeout=10)

    def test_flourishes_print_plain_text_off_a_terminal_and_never_fail(self):
        self.assertEqual(self.charm('transition', 'Select install disk').stdout, 'Select install disk\n')
        self.assertRegex(self.charm('result', 'ok', 'DNS', '--left', '2').stdout, r'^  (?:√|ok) DNS\n$')
        self.assertRegex(self.charm('result', 'fail', 'Clock').stdout, r'^(?:×|x) Clock\n$')
        self.assertEqual(self.charm('result', 'ok', 'DNS', LANG='C', LC_ALL='C').stdout, 'ok DNS\n')
        self.assertIn('nda0 will be destroyed', self.charm('warn', 'All data on nda0 will be destroyed.').stdout)
        for argv in (('no-such-command',), ('result',), ('attract', '--logo', '/nonexistent')):
            self.assertEqual(self.charm(*argv).returncode, 0)
        wrapper = subprocess.run(['/bin/sh', str(LIBEXEC/'charm'), 'transition', 'x'], env=dict(clean_env(), PATH='/nonexistent'),
                                 capture_output=True, text=True)
        self.assertEqual(wrapper.returncode, 1, 'without Python the caller falls back to plain text')

    def test_flourishes_on_a_terminal_are_short_and_reduced_motion_is_static(self):
        for reduced in ('', '1'):
            with self.subTest(reduced=reduced):
                env = dict(clean_env(), TERM='xterm-256color', DAEMONARCHY_SOUND='off', DAEMONARCHY_REDUCED_MOTION=reduced)
                started = time.monotonic()
                with Terminal(['warn', 'All partitions on nda0 will be destroyed.'], env, 10, 80,
                              command=[sys.executable, str(LIBEXEC/'charm.py')]) as tty:
                    self.assertEqual(tty.exit_code(), 0)
                    self.assertIn('All partitions on nda0 will be destroyed.', tty.text())
                elapsed = time.monotonic() - started
                self.assertLess(elapsed, 3.0)
                if reduced:
                    self.assertNotIn(b'\033[0;1;38;5', tty.captured, 'no pulses, no color changes')

    def test_mascot_and_fireworks_are_bounded(self):
        for unicode in (True, False):
            for expression in charm.MASCOT_UNICODE:
                frame = charm.mascot_frame(expression, unicode)
                self.assertEqual(len(frame), charm.MASCOT_H)
                self.assertTrue(all(len(row) <= charm.MASCOT_W for row in frame))
                if not unicode:
                    self.assertTrue(''.join(frame).isascii())
        fireworks = charm.Fireworks(40, 10)
        for _ in range(60):
            fireworks.step(0.1)
        cells = list(fireworks.cells())
        self.assertTrue(cells)
        self.assertTrue(all(0 <= x < 40 and 0 <= y < 10 for x, y, _c, _s in cells))
        self.assertEqual(charm.mascot_expression(0, 'working', 0.0, reduced=True), 'idle')
        self.assertEqual(charm.mascot_expression(3.0, 'happy'), 'happy')

class CostTests(unittest.TestCase):
    def test_drawing_cost_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_bytes(RetainedInstallReplayTests.FIXTURE.read_bytes())
            env = dict(clean_env(), TERM='xterm-256color')
            with Terminal([str(log), str(status)], env, 60, 200) as tty:
                tty.read_for(2)
                before, cpu_before = len(tty.captured), cpu_seconds(tty.child.pid)
                tty.read_for(6)
                rate = (len(tty.captured) - before) / 6
                cpu = cpu_seconds(tty.child.pid) - cpu_before
                self.assertLess(rate, 30000, 'animated output stays bounded')
                self.assertLess(cpu, 6 * 0.5, 'drawing uses well under half a core')


def cpu_seconds(pid):
    """User+system CPU of a process from ps(1), on FreeBSD and Linux."""
    value = subprocess.run(['ps', '-o', 'time=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    days, _, clock = value.rpartition('-')
    seconds = 0.0
    for part in clock.split(':'):
        seconds = seconds * 60 + float(part)
    return seconds + (int(days) * 86400 if days else 0)

PKG_EVENTS = ROOT/'overlay/usr/local/libexec/daemonarchy-installer/pkg-events'
events_loader = importlib.machinery.SourceFileLoader('pkg_events', str(PKG_EVENTS))
events_spec = importlib.util.spec_from_loader('pkg_events', events_loader)
pkg_events = importlib.util.module_from_spec(events_spec)
events_loader.exec_module(pkg_events)


class PackageFetchMeasurementTests(unittest.TestCase):
    """pkg prints only dots when not on a terminal; its event pipe reports bytes."""
    FIXTURE = ROOT/'tests/fixtures/installer-progress/pkg-fetch-events.jsonl'

    def provenance(self):
        return json.loads(self.FIXTURE.with_name('pkg-fetch-events-provenance.json').read_text())

    def test_real_pkg_events_become_archive_bytes(self):
        provenance = self.provenance()
        data = self.FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), provenance['fixture_sha256'])
        lines = []
        converter = pkg_events.Converter(lines.append, clock=lambda: 0.0)
        for event in pkg_events.events(data[i:i + 997] for i in range(0, len(data), 997)):
            converter.event(event)
        rows = [json.loads(line[8:]) for line in lines]
        self.assertEqual([row['archives'] for row in rows if row['file'] == ''], [1, 2, 3])  # one line per archive
        last = rows[-1]
        self.assertEqual(last['archives'], 3)
        self.assertEqual(last['bytes'], provenance['archive_bytes_total'])
        names = {row['file'] for row in rows if row['file']}
        self.assertEqual(names, set(provenance['archives']))  # never meta.conf or data.pkg
        self.assertTrue(all(row['bytes'] <= provenance['archive_bytes_total'] for row in rows))
        self.assertEqual([row['bytes'] for row in rows], sorted(row['bytes'] for row in rows))

    def test_event_reader_process_reads_everything_before_the_end_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            fifo, ready = Path(directory)/'pipe', Path(directory)/'ready'
            os.mkfifo(fifo)
            reader = subprocess.Popen([sys.executable, str(PKG_EVENTS), str(fifo), str(ready)],
                                      stdout=subprocess.PIPE, text=True)
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            with fifo.open('wb') as pipe:  # pkg opens, writes and closes ...
                pipe.write(self.FIXTURE.read_bytes())
            with fifo.open('w') as pipe:  # ... then install writes its marker.
                pipe.write('{"type":"DAEMONARCHY_END"}\n')
            output, _ = reader.communicate(timeout=10)
            self.assertEqual(reader.returncode, 0)
            last = json.loads(output.splitlines()[-1][8:])
            self.assertEqual((last['archives'], last['bytes']), (3, self.provenance()['archive_bytes_total']))

    def test_fetch_lines_feed_the_model_screen_and_graphical_installer(self):
        state = model.Progress()
        for line in ('@@phase fetch', '2 MiB to be downloaded.', 'Number of packages to be fetched: 3',
                     '@@fetch {"schema":"daemonarchy/pkg-fetch@1","archives":0,"bytes":8192,"file":"utf8proc-2.12.0",'
                     '"file_bytes":8192,"file_total":88146}',
                     'Fetching utf8proc-2.12.0: .......... done',
                     '@@fetch {"schema":"daemonarchy/pkg-fetch@1","archives":1,"bytes":88146,"file":"","file_bytes":0,'
                     '"file_total":0}'):
            state.line(line)
        self.assertFalse(state.warning)
        self.assertEqual(state.meter[1:], (1, 3, 'archives'))
        self.assertEqual(state.fetch['bytes'], 88146)
        self.assertEqual(state.fetch_estimate, '2 MiB')
        text = '\n'.join(ui.lines(state, 'bars', 200))
        self.assertIn('Received 86.1 KiB of about 2 MiB', text)
        self.assertNotRegex(text, r'\d+%')
        # A retry runs pkg again from zero: a new attempt, never negative progress.
        state.line('@@fetch {"schema":"daemonarchy/pkg-fetch@1","archives":0,"bytes":100,"file":"tmux-3.8",'
                   '"file_bytes":100,"file_total":603611}')
        self.assertEqual(state.fetch['attempt'], 2)
        for bad in ('{"schema":"daemonarchy/pkg-fetch@1","archives":-1,"bytes":0,"file_bytes":0,"file_total":0}',
                    '{"schema":"daemonarchy/pkg-fetch@1","archives":0,"bytes":5,"file_bytes":9,"file_total":9}',
                    '{"schema":"other","archives":0,"bytes":0,"file_bytes":0,"file_total":0}'):
            other = model.Progress()
            other.line('@@fetch ' + bad)
            self.assertTrue(other.warning)
            self.assertIsNone(other.fetch)
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase fetch\n5 GiB to be downloaded.\n@@fetch {"schema":"daemonarchy/pkg-fetch@1",'
                           '"archives":2,"bytes":3000000,"file":"tmux-3.8","file_bytes":4096,"file_total":603611}\n')
            view = model.InstallProgress(log, status, source=None).poll()
            self.assertEqual(view['fetch']['archives'], 2)
            self.assertTrue(any('Received 2.9 MiB of about 5 GiB' in row and 'now tmux-3.8' in row
                                for row in view['details']))

    @unittest.skipUnless(sys.platform.startswith('freebsd') and os.geteuid() == 0
                         and os.environ.get('DAEMONARCHY_NATIVE_PKG_FETCH') == '1',
                         'native: FreeBSD root with DAEMONARCHY_NATIVE_PKG_FETCH=1')
    def test_native_pkg_fetch_bytes_match_the_downloaded_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            fifo, ready, out = Path(directory)/'pipe', Path(directory)/'ready', Path(directory)/'out'
            os.mkfifo(fifo)
            reader = subprocess.Popen([sys.executable, str(PKG_EVENTS), str(fifo), str(ready)],
                                      stdout=subprocess.PIPE, text=True)
            while not ready.exists():
                time.sleep(0.02)
            try:
                fetched = subprocess.run(['pkg', '-o', f'EVENT_PIPE={fifo}', 'fetch', '-y', '-o', str(out),
                                          'tmux', 'libevent', 'utf8proc'], capture_output=True, text=True,
                                         timeout=240, env=dict(os.environ, IGNORE_OSVERSION='yes',
                                                               ASSUME_ALWAYS_YES='yes'))
            finally:
                with fifo.open('w') as pipe:
                    pipe.write('{"type":"DAEMONARCHY_END"}\n')
                output, _ = reader.communicate(timeout=30)
            self.assertEqual(fetched.returncode, 0, fetched.stderr)
            # Dots only, as in the installer's log: no byte progress in pkg's own output.
            self.assertRegex(fetched.stdout, r'Fetching tmux-[^:]+: \.+ done')
            self.assertNotIn('100%', fetched.stdout)
            last = json.loads(output.splitlines()[-1][8:])
            sizes = [path.stat().st_size for path in out.rglob('*.pkg')]
            self.assertEqual(last['archives'], len(sizes))
            self.assertEqual(last['bytes'], sum(sizes))

if __name__ == '__main__':
    unittest.main(verbosity=2)
