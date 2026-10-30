#!/usr/bin/env python3
"""What runs inside an extension's extra tmux window. Started only by windows.TmuxBackend.

  python3 -I window_view.py SOCKET WINDOW_ID

It connects to the host's private unix socket, draws the frames the host sends (already validated
by the host) with the SDK's Screen, and reports back the window's size and the actions the user
presses. It holds nothing of the extension's and cannot change anything but its own display. It
exits when the host closes the socket or the window is closed.
"""

import json
import os
import select
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daemonarchy_visual import Canvas, Colors, KeyMap, Screen, caps as sdk_caps  # noqa: E402
from daemonarchy_visual.input import FdSource, Raw  # noqa: E402


def draw(screen, rows, width, height):
    canvas = screen.canvas(width, height)
    for y, row in enumerate(rows[:canvas.height]):
        for x, text, style in row[:200]:
            fg, bg, bold = style
            canvas.put(x, y, text, (tuple(fg) if fg else None, tuple(bg) if bg else None, bool(bold)))
    screen.present(canvas)


def main(argv):
    path = argv[1]
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.connect(path)
    caps = sdk_caps.detect(dict(os.environ), sys.stdout)
    screen = Screen(sys.stdout, Colors(caps.depth))
    source = FdSource(sys.stdin.fileno(), KeyMap())
    inbox, rows, size = b"", [], None
    with Raw(sys.stdin.fileno()):
        screen.enter()
        try:
            while True:
                width, height = sdk_caps.size(sys.stdout)
                if (width, height) != size:
                    size = (width, height)
                    conn.sendall((json.dumps({"e": "size", "c": width, "r": height}) + "\n").encode())
                    draw(screen, rows, width, height)
                ready, _, _ = select.select([conn], [], [], 0.1)
                if ready:
                    data = conn.recv(1 << 20)
                    if not data:
                        return 0
                    inbox += data
                    while b"\n" in inbox:
                        line, inbox = inbox.split(b"\n", 1)
                        try:
                            message = json.loads(line)
                            rows = message["rows"]
                        except (ValueError, KeyError, TypeError):
                            continue
                        draw(screen, rows, width, height)
                actions = source.poll(0.0)
                if actions:
                    conn.sendall((json.dumps({"e": "actions", "a": actions}) + "\n").encode())
                if source.eof:
                    return 0
        except (OSError, BrokenPipeError):
            return 0
        finally:
            screen.leave()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
