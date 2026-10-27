#!/usr/bin/env python3
"""Record the real installer screen replaying a retained install log.

The dashboard runs unmodified in a pseudo-terminal of the chosen size and
TERM. The log is appended at a chosen pace, so stages, counters and the
package ticker follow the retained install's own lines. Activity meters show
the machine this demo runs on (they are live kernel counters, not part of the
log). Output: an asciicast v2 recording (play with `asciinema play FILE` or
any asciinema player) and, optionally, an HTML rendering of selected frames.

Example:
  scripts/installer-visuals-demo.py tests/fixtures/installer-progress/macbook-1.3.1-install.log \
      --cast demo.cast --html demo.html --size 48x150 --seconds 60 \
      --key 20:l --key 30:s --key 32:'echo hello\\r' --key 40:Tab --key 44:q
"""
import argparse
import fcntl
import html
import json
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
LIBEXEC = ROOT / 'overlay/usr/local/libexec/daemonarchy-installer'
SHARE = ROOT / 'overlay/usr/local/share/daemonarchy-installer'

XTERM16 = [(0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0), (59, 120, 255), (205, 0, 205), (0, 205, 205),
           (229, 229, 229), (127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0), (92, 92, 255),
           (255, 0, 255), (0, 255, 255), (255, 255, 255)]
# vt(4) default palette (sys/dev/vt/colors/vt_termcolors.c), ANSI order.
VT16 = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (196, 161, 0), (51, 102, 163), (128, 0, 128), (0, 128, 128),
        (191, 191, 191), (46, 51, 54), (255, 0, 0), (0, 255, 0), (255, 255, 0), (115, 158, 207),
        (255, 0, 255), (0, 255, 255), (255, 255, 255)]


def xterm256(index, palette):
    if index < 16:
        return palette[index]
    if index < 232:
        index -= 16
        steps = (0, 95, 135, 175, 215, 255)
        return steps[index // 36], steps[index // 6 % 6], steps[index % 6]
    return (8 + (index - 232) * 10,) * 3


class ColorScreen:
    """Enough of a terminal to replay the dashboard's own output with colors."""

    def __init__(self, rows, cols, palette=XTERM16):
        self.rows, self.cols, self.palette = rows, cols, palette
        self.cells = [[(' ', None, None, False)] * cols for _ in range(rows)]
        self.x = self.y = 0
        self.fg = self.bg = None
        self.bold = False
        self.pending = ''

    def sgr(self, params):
        values = [int(v) if v else 0 for v in params.split(';')] if params else [0]
        i = 0
        while i < len(values):
            v = values[i]
            if v == 0:
                self.fg = self.bg = None
                self.bold = False
            elif v == 1:
                self.bold = True
            elif v == 22:
                self.bold = False
            elif 30 <= v <= 37:
                self.fg = self.palette[v - 30]
            elif 90 <= v <= 97:
                self.fg = self.palette[v - 90 + 8]
            elif 40 <= v <= 47:
                self.bg = self.palette[v - 40]
            elif 100 <= v <= 107:
                self.bg = self.palette[v - 100 + 8]
            elif v in (38, 48) and i + 1 < len(values):
                if values[i + 1] == 5 and i + 2 < len(values):
                    color = xterm256(values[i + 2], self.palette)
                    i += 2
                elif values[i + 1] == 2 and i + 4 < len(values):
                    color = tuple(values[i + 2:i + 5])
                    i += 4
                else:
                    color = None
                if v == 38:
                    self.fg = color
                else:
                    self.bg = color
            elif v == 39:
                self.fg = None
            elif v == 49:
                self.bg = None
            i += 1

    def feed(self, text):
        text = self.pending + text
        self.pending = ''
        i = 0
        while i < len(text):
            char = text[i]
            if char == '\x1b':
                match = re.match(r'\x1b\[([0-9;?]*)([@-~])', text[i:])
                if not match:
                    if len(text) - i < 32:
                        self.pending = text[i:]
                        return
                    i += 1
                    continue
                params, final = match.groups()
                i += match.end()
                if final == 'm' and not params.startswith('?'):
                    self.sgr(params)
                elif final == 'H':
                    parts = (params or '1;1').split(';')
                    self.y = max(0, min(self.rows - 1, int(parts[0] or 1) - 1))
                    self.x = max(0, min(self.cols - 1, int(parts[1] or 1) - 1 if len(parts) > 1 else 0))
                elif final == 'J' and params == '2':
                    self.cells = [[(' ', None, None, False)] * self.cols for _ in range(self.rows)]
                continue
            if char == '\n':
                self.y = min(self.rows - 1, self.y + 1)
                self.x = 0
            elif char == '\r':
                self.x = 0
            elif char >= ' ':
                if self.x < self.cols:
                    self.cells[self.y][self.x] = (char, self.fg, self.bg, self.bold)
                self.x += 1
            i += 1

    def html(self, title):
        rows = []
        for row in self.cells:
            parts, current, run = [], None, ''
            for char, fg, bg, bold in row:
                style = (fg, bg, bold)
                if style != current:
                    if run:
                        parts.append(span(current, run))
                    current, run = style, ''
                run += char
            parts.append(span(current, run))
            rows.append(''.join(parts))
        return (f'<figure><figcaption>{html.escape(title)}</figcaption><pre class="screen">'
                + '\n'.join(rows) + '</pre></figure>')


def teken_html(harness, rows, cols, data, title):
    """Render output exactly as vt(4)'s teken parses it (tests/vt-teken-render.c)."""
    result = subprocess.run([harness, str(rows), str(cols)], input=data, capture_output=True, check=True)
    lines = []
    for line in result.stdout.decode().splitlines():
        parts = []
        for cell in line.split('\t'):
            code, fg, bg, *flags = cell.split(' ')
            fg, bg = int(fg), int(bg)
            if flags and 'r' in flags[0]:
                fg, bg = bg, fg
            parts.append(span((VT16[fg], VT16[bg] if bg else None, False), chr(int(code[2:], 16))))
        lines.append(''.join(parts))
    return (f'<figure><figcaption>{html.escape(title)}</figcaption><pre class="screen">'
            + '\n'.join(lines) + '</pre></figure>')


def span(style, text):
    fg, bg, bold = style or (None, None, False)
    css = []
    if fg:
        css.append('color:#%02x%02x%02x' % fg)
    if bg:
        css.append('background:#%02x%02x%02x' % bg)
    if bold:
        css.append('font-weight:bold')
    text = html.escape(text)
    return f'<span style="{";".join(css)}">{text}</span>' if css else text


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Installer screen frames</title>
<style>body{background:#111;color:#ddd;font-family:sans-serif;margin:16px}
pre.screen{font-family:'DejaVu Sans Mono','Noto Sans Mono',monospace;font-size:12px;line-height:1.15;
background:#000;color:#bfbfbf;padding:8px;display:inline-block;margin:0}
figure{margin:0 0 24px 0}figcaption{margin:0 0 6px 0;color:#9cf}</style></head><body>
%s</body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('log', type=Path, help='retained install log to replay')
    parser.add_argument('--cast', type=Path, help='asciicast v2 output')
    parser.add_argument('--html', type=Path, help='HTML rendering of frames')
    parser.add_argument('--frames', default='', help='comma-separated seconds at which to capture HTML frames')
    parser.add_argument('--size', default='40x120', help='ROWSxCOLS')
    parser.add_argument('--term', default='xterm-256color')
    parser.add_argument('--color', default='', help='DAEMONARCHY_COLOR override (none, 8, 16, 256, truecolor)')
    parser.add_argument('--console', action='store_true', help='render as on the FreeBSD vt(4) console')
    parser.add_argument('--style', default='spectrum')
    parser.add_argument('--seconds', type=float, default=45.0, help='replay duration')
    parser.add_argument('--hold', type=float, default=4.0, help='seconds to keep recording after the log ends')
    parser.add_argument('--result', type=int, help='write this installer result after the log ends')
    parser.add_argument('--key', action='append', default=[], help='SECONDS:KEYS, e.g. 20:l (\\r, \\t, \\x1b escapes)')
    parser.add_argument('--env', action='append', default=[], help='NAME=VALUE for the dashboard')
    parser.add_argument('--reduced-motion', action='store_true')
    parser.add_argument('--tmux', action='store_true', help='run the full tmux install screen (dashboard wrapper)')
    parser.add_argument('--teken', help='render HTML frames with this vt-teken-render binary (FreeBSD)')
    parser.add_argument('--load', help='shell command run during the replay to create real activity')
    parser.add_argument('--command', help='record this shell command instead of the install screen '
                        '(for example scripts/installer-charm-tour.sh); the log is still replayed')
    args = parser.parse_args()
    rows, cols = (int(v) for v in args.size.lower().split('x'))
    lines = args.log.read_bytes().splitlines(keepends=True)
    keys = []
    for item in args.key:
        at, _, data = item.partition(':')
        data = {'Tab': '\t', 'Esc': '\x1b', 'Enter': '\r', 'Ctrl-]': '\x1d'}.get(data, data)
        keys.append((float(at), data.encode().decode('unicode_escape').encode('latin-1')))
    keys.sort()
    frames = sorted(float(v) for v in args.frames.split(',') if v)
    with tempfile.TemporaryDirectory() as directory:
        log, status = Path(directory) / 'install.log', Path(directory) / 'install.status'
        log.touch()
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
        env = dict(os.environ, TERM=args.term, ISO_SHARE=str(SHARE), LANG='C.UTF-8')
        env.pop('NO_COLOR', None)
        if args.color:
            env['DAEMONARCHY_COLOR'] = args.color
        if args.console:
            env['DAEMONARCHY_CONSOLE'] = 'vt'
            env['TERM'] = 'xterm'
        if args.reduced_motion:
            env['DAEMONARCHY_REDUCED_MOTION'] = '1'
        for item in args.env:
            name, _, value = item.partition('=')
            env[name] = value
        env['DAEMONARCHY_DEMO_LOG'], env['DAEMONARCHY_DEMO_STATUS'] = str(log), str(status)
        if args.command:
            command = ['bash', '-c', args.command]
        elif args.tmux:
            env['DAEMONARCHY_TMUX_SOCKET'] = f'daemonarchy-demo-{os.getpid()}'
            env['DAEMONARCHY_PROGRESS_STYLE'] = args.style
            command = ['bash', str(LIBEXEC / 'dashboard'), str(log), str(status)]
        else:
            command = [sys.executable, str(LIBEXEC / 'progress-dashboard.py'), str(log), str(status), '--style', args.style]

        def controlling_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)
        child = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=env,
                                 preexec_fn=controlling_terminal)
        os.close(slave)
        load = subprocess.Popen(['sh', '-c', args.load], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True) if args.load else None
        raw = bytearray()
        events, started = [], time.monotonic()
        screen = ColorScreen(rows, cols, VT16 if args.console else XTERM16)
        captured = []
        written = 0
        end = args.seconds + args.hold
        decoder_pending = b''
        try:
            while True:
                now = time.monotonic() - started
                if now > end + (30 if args.result is not None else 0) or child.poll() is not None and now > 1:
                    break
                target = min(len(lines), int(len(lines) * min(1.0, now / max(0.1, args.seconds))))
                if target > written:
                    with log.open('ab') as stream:
                        stream.writelines(lines[written:target])
                    written = target
                if written == len(lines) and args.result is not None and now >= args.seconds + args.hold / 2 \
                        and not status.exists():
                    status.write_text(f'{args.result}\n')
                while keys and keys[0][0] <= now:
                    os.write(master, keys.pop(0)[1])
                if select.select([master], [], [], 0.02)[0]:
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    raw.extend(data)
                    data = decoder_pending + data
                    cut = len(data)
                    while cut and data[cut - 1] & 0xC0 == 0x80:
                        cut -= 1
                    if cut and data[cut - 1] >= 0xC0:
                        cut -= 1
                    text, decoder_pending = data[:cut].decode('utf-8', 'replace'), data[cut:]
                    events.append([round(now, 3), 'o', text])
                    screen.feed(text)
                while frames and frames[0] <= now:
                    label = (f't = {frames.pop(0):.0f} s, {rows}x{cols}, '
                             f'{"vt(4) console" if args.console else env["TERM"]}')
                    if args.teken:
                        captured.append(teken_html(args.teken, rows, cols, bytes(raw), label + ', rendered by teken'))
                    else:
                        captured.append(screen.html(label))
        finally:
            if load is not None and load.poll() is None:
                os.killpg(load.pid, 15)
            if child.poll() is None:
                child.terminate()
                child.wait(5)
            if args.tmux:
                subprocess.run(['tmux', '-L', env['DAEMONARCHY_TMUX_SOCKET'], 'kill-server'], capture_output=True)
            os.close(master)
        if not args.teken:
            captured.append(screen.html(f'final frame, {rows}x{cols}'))
        if args.cast:
            header = dict(version=2, width=cols, height=rows, timestamp=int(time.time()),
                          title=(f'Daemonarchy: {args.command}' if args.command
                                 else f'Daemonarchy installer screen replaying {args.log.name}'),
                          env=dict(TERM=env['TERM']))
            with args.cast.open('w') as stream:
                stream.write(json.dumps(header) + '\n')
                for event in events:
                    stream.write(json.dumps(event) + '\n')
        if args.html:
            args.html.write_text(PAGE % '\n'.join(captured))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
