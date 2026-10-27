#!/usr/bin/env python3
"""Native FreeBSD: what the install screen looks like to vt(4).

The screen's real output is fed to sys/teken, the terminal emulator inside
vt(4), built from the host's source tree, and vt's own color reduction is
applied (tests/vt-teken-render.c). This checks the 16-color console output,
256-color syntax (accepted, reduced to 16 by vt), and why 24-bit color is
never sent to the console: teken reads its R, G and B values as separate
attributes. The tmux session's output on the console is checked the same
way. Set VT_RENDER_OUT=DIR to keep HTML renderings in vt's palette.

Requires FreeBSD, cc, tmux and /usr/src/sys/teken. Installs nothing.
"""
import fcntl
import html
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
LIBEXEC = ROOT/'overlay/usr/local/libexec/daemonarchy-installer'
SHARE = ROOT/'overlay/usr/local/share/daemonarchy-installer'
FIXTURE = ROOT/'tests/fixtures/installer-progress/macbook-1.3.1-install.log'
TEKEN = Path(os.environ.get('TEKEN_SRC', '/usr/src/sys/teken'))
VT16 = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (196, 161, 0), (51, 102, 163), (128, 0, 128), (0, 128, 128),
        (191, 191, 191), (46, 51, 54), (255, 0, 0), (0, 255, 0), (255, 255, 0), (115, 158, 207),
        (255, 0, 255), (0, 255, 255), (255, 255, 255)]
ROWS, COLS = 50, 160


def capture(command, env, seconds, rows=ROWS, cols=COLS):
    """Run a command on a pty that is its controlling terminal; return its output."""
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

    def controlling():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    child = subprocess.Popen(command, env=env, stdin=slave, stdout=slave, stderr=slave, preexec_fn=controlling)
    os.close(slave)
    output = bytearray()
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        os.close(master)
    return bytes(output)


@unittest.skipUnless(sys.platform.startswith('freebsd') and (TEKEN / 'teken.c').exists(),
                     'needs FreeBSD with /usr/src/sys/teken')
class VtConsoleColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        work = Path(cls.work.name)
        with (work/'teken_state.h').open('w') as state:
            subprocess.run(['awk', '-f', str(TEKEN/'gensequences'), str(TEKEN/'sequences')], stdout=state, check=True)
        cls.harness = work/'vt-teken-render'
        subprocess.run(['cc', '-O2', '-I', str(work), '-I', str(TEKEN), '-o', str(cls.harness),
                        str(ROOT/'tests/vt-teken-render.c'), str(TEKEN/'teken.c')], check=True)
        cls.log = work/'install.log'
        cls.log.write_bytes(FIXTURE.read_bytes())
        cls.status = work/'install.status'

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def env(self, **extra):
        # Colors only: never start the sound player on the host's real audio device.
        env = dict(os.environ, ISO_SHARE=str(SHARE), LANG='C.UTF-8', DAEMONARCHY_SOUND='off',
                   DAEMONARCHY_SOUND_DIR=str(Path(self.work.name)/'sound'), **extra)
        for name in ('NO_COLOR', 'COLORTERM'):
            env.pop(name, None)
        return env

    def render(self, data, name):
        result = subprocess.run([str(self.harness), str(ROWS), str(COLS)], input=data, capture_output=True, check=True)
        cells = [[cell.split(' ') for cell in line.split('\t')] for line in result.stdout.decode().splitlines()]
        out = os.environ.get('VT_RENDER_OUT')
        if out:
            Path(out).mkdir(parents=True, exist_ok=True)
            rows = []
            for row in cells:
                parts = []
                for code, fg, bg, flags in ((c[0], int(c[1]), int(c[2]), c[3] if len(c) > 3 else '') for c in row):
                    if 'r' in flags:
                        fg, bg = bg, fg
                    style = 'color:#%02x%02x%02x;background:#%02x%02x%02x' % (VT16[fg] + VT16[bg])
                    if 'u' in flags:
                        style += ';text-decoration:underline'
                    parts.append(f'<span style="{style}">{html.escape(chr(int(code[2:], 16)) or " ")}</span>')
                rows.append(''.join(parts))
            Path(out, f'{name}.html').write_text(
                '<!doctype html><meta charset="utf-8"><title>vt(4) ' + name + '</title>'
                '<pre style="font:12px/1.15 \'DejaVu Sans Mono\',monospace;background:#000;display:inline-block;'
                'padding:8px">' + '\n'.join(rows) + '</pre>')
        return cells

    def summary(self, cells, ignore_last_row=False):
        rows = cells[:-1] if ignore_last_row else cells
        flat = [cell for row in rows for cell in row]
        return dict(
            text='\n'.join(''.join(chr(int(c[0][2:], 16)) for c in row) for row in cells),
            garbled=sum(1 for c in flat if len(c) > 3 and c[3]),
            backgrounds=sum(1 for c in flat if c[2] != '0'),
            colors={int(c[1]) for c in flat if chr(int(c[0][2:], 16)) not in ' '})

    def dashboard(self, **extra):
        return capture([sys.executable, str(LIBEXEC/'progress-dashboard.py'), str(self.log), str(self.status)],
                       self.env(**extra), 4)

    def test_console_output_uses_vt_colors_without_stray_attributes(self):
        data = self.dashboard(TERM='xterm', DAEMONARCHY_CONSOLE='vt')
        self.assertNotIn(b'38;2;', data)
        self.assertNotIn(b'38;5;', data)
        result = self.summary(self.render(data, 'console-16'))
        self.assertIn('976 / 1,188 packages', result['text'])
        self.assertIn('Spectrum', result['text'])
        self.assertEqual(result['garbled'], 0)
        self.assertEqual(result['backgrounds'], 0)
        self.assertGreaterEqual(len(result['colors']), 6, result['colors'])

    def test_256_color_syntax_is_reduced_by_vt_without_damage(self):
        data = self.dashboard(TERM='xterm-256color', DAEMONARCHY_COLOR='256')
        self.assertIn(b'38;5;', data)
        result = self.summary(self.render(data, 'console-256-reduced'))
        self.assertEqual(result['garbled'], 0)
        self.assertEqual(result['backgrounds'], 0)
        self.assertGreaterEqual(len(result['colors']), 4)

    def test_24_bit_color_would_corrupt_the_console(self):
        # The control the screen never sends to vt(4): teken reads 38;2;R;G;B as
        # separate attributes, so some colors turn on underline, bright
        # background (blink) or reverse video.
        data = self.dashboard(TERM='xterm-256color', DAEMONARCHY_COLOR='truecolor')
        self.assertIn(b'38;2;', data)
        result = self.summary(self.render(data, 'console-truecolor-negative-control'))
        self.assertGreater(result['garbled'] + result['backgrounds'], 0)

    def test_tmux_session_output_on_the_console(self):
        if not subprocess.run(['sh', '-c', 'command -v tmux'], capture_output=True).stdout:
            self.skipTest('tmux is not installed')
        socket = f'vt-console-test-{os.getpid()}'
        try:
            data = capture(['bash', str(LIBEXEC/'dashboard'), str(self.log), str(self.status)],
                           self.env(TERM='xterm', DAEMONARCHY_CONSOLE='vt', DAEMONARCHY_TMUX_SOCKET=socket), 5)
        finally:
            subprocess.run(['tmux', '-L', socket, 'kill-server'], capture_output=True)
        self.assertNotIn(b'38;2;', data)
        self.assertNotIn(b'38;5;', data)
        cells = self.render(data, 'console-tmux')
        result = self.summary(cells, ignore_last_row=True)  # the tmux status line has a background
        self.assertIn('976 / 1,188 packages', result['text'])
        self.assertIn('C-b ? help', result['text'])
        self.assertEqual(result['garbled'], 0)
        self.assertEqual(result['backgrounds'], 0)
        self.assertGreaterEqual(len(result['colors']), 6, result['colors'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
