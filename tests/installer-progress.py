#!/usr/bin/env python3
"""Exercise measured progress and real viewer lifecycle without installing anything."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
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
        for style, terminal, color in [('bars', 'vt100', b'\033[36m'),
                                       ('spectrum', 'xterm-256color', b'\033[38;5;82m'),
                                       ('scope', 'xterm', b'\033[35m')]:
            with self.subTest(style=style), tempfile.TemporaryDirectory() as directory:
                log, status = Path(directory)/'log', Path(directory)/'status'
                log.write_text('@@phase base\n@@progress ' + json.dumps(metric(3)) + '\n')
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 15, 80, 0, 0))
                env = dict(os.environ, TERM=terminal)
                env.pop('NO_COLOR', None)
                env.pop('DAEMONARCHY_REDUCED_MOTION', None)
                child = subprocess.Popen([sys.executable, str(SCRIPT), str(log), str(status), '--style', style], env=env, stdout=slave, stderr=slave)
                captured = bytearray()
                try:
                    deadline = time.monotonic()+5
                    while b'3 / 3 archives' not in captured and time.monotonic() < deadline:
                        if select.select([master], [], [], 0.1)[0]:
                            captured.extend(os.read(master, 65536))
                    self.assertIn(color, captured)
                    self.assertNotIn(b'Daemonarchy is installed.', captured)
                    status.write_text('0\n')
                    deadline = time.monotonic()+5
                    while b'\033[?25h' not in captured and time.monotonic() < deadline:
                        if select.select([master], [], [], 0.1)[0]:
                            captured.extend(os.read(master, 65536))
                    self.assertEqual(child.wait(timeout=5), 0)
                    self.assertIn(b'Daemonarchy is installed.', captured)
                    self.assertIn(b'\033[?25h', captured)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait(timeout=5)
                    os.close(master)
                    os.close(slave)

    def test_real_tty_wait_resize_reduced_motion_and_signal_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory)/'log', Path(directory)/'status'
            log.write_text('@@phase base\n@@progress ' + json.dumps(metric()) + '\n')
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 8, 20, 0, 0))
            env = dict(os.environ, TERM='vt100', NO_COLOR='1', DAEMONARCHY_REDUCED_MOTION='1')
            child = subprocess.Popen([sys.executable, str(SCRIPT), str(log), str(status), '--style', 'scope'], env=env, stdout=slave, stderr=slave)
            captured = bytearray()
            try:
                deadline = time.monotonic()+6
                while time.monotonic() < deadline:
                    if select.select([master], [], [], 0.2)[0]:
                        captured.extend(os.read(master, 65536))
                self.assertIsNone(child.poll())
                self.assertNotIn(b'Daemonarchy is installed.', captured)
                self.assertIn(b'BARS', captured)
                # A real kernel window-size change must not require another event.
                fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', 12, 80, 0, 0))
                time.sleep(0.4)
                child.send_signal(signal.SIGTERM)
                self.assertEqual(child.wait(timeout=5), 143)
                while select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                        if not chunk:
                            break
                        captured.extend(chunk)
                    except OSError:
                        break
                self.assertIn(b'\033[?25h', captured)
                self.assertNotIn(b'\033[36m', captured)
                self.assertLess(len(captured), 4096)  # idle polling is not an animation loop
                self.assertFalse(status.exists())
                self.assertIn(b'1 / 3 archives', captured)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                os.close(master)
                os.close(slave)


if __name__ == '__main__':
    unittest.main(verbosity=2)
