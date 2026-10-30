"""Input: decode terminal bytes into keys, and keys into the SDK's small set of actions.

A host or plugin reacts to actions (`left`, `fire`, `pause`...), never to raw
keys, so the same scene works from a keyboard, over SSH or a serial line, and
under a different key map. Actions carry no meaning beyond the scene.
"""

import os
import re
import select
import termios
import tty

ACTIONS = ("up", "down", "left", "right", "fire", "pause", "select", "back", "quit", "mute", "help")

KEYS = {b"\x1b[A": "up", b"\x1b[B": "down", b"\x1b[C": "right", b"\x1b[D": "left", b"\x1bOA": "up",
        b"\x1bOB": "down", b"\x1bOC": "right", b"\x1bOD": "left", b"\x1b[5~": "pgup", b"\x1b[6~": "pgdn",
        b"\x1b[H": "home", b"\x1b[F": "end", b"\x1b[1~": "home", b"\x1b[4~": "end", b"\x1b[Z": "backtab"}


def decode_keys(buffer, final=False):
    """Split terminal input into keys. Returns (keys, unconsumed)."""
    keys = []
    while buffer:
        if buffer[:1] == b"\x1b":
            for sequence, name in KEYS.items():
                if buffer.startswith(sequence):
                    keys.append(name)
                    buffer = buffer[len(sequence):]
                    break
            else:
                match = re.match(rb"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1bO.", buffer)
                if match:
                    buffer = buffer[match.end():]  # Unknown sequence: ignore.
                elif len(buffer) == 1 and not final:
                    break  # Maybe the start of a sequence; wait briefly.
                else:
                    keys.append("esc")
                    buffer = buffer[1:]
            continue
        byte = buffer[0]
        buffer = buffer[1:]
        if byte == 9:
            keys.append("tab")
        elif byte in (10, 13):
            keys.append("enter")
        elif byte == 3:
            keys.append("ctrl-c")
        elif 32 <= byte < 127:
            keys.append(chr(byte))
    return keys, buffer


class KeyMap:
    """Keys to actions. The default suits games: arrows or WASD, space to fire, p pause, q or Esc to quit."""

    DEFAULT = {
        "up": "up", "w": "up", "k": "up", "down": "down", "s": "down", "j": "down",
        "left": "left", "a": "left", "h": "left", "right": "right", "d": "right", "l": "right",
        " ": "fire", "f": "fire", "enter": "select", "p": "pause", "esc": "back", "q": "quit",
        "ctrl-c": "quit", "m": "mute", "?": "help",
    }

    def __init__(self, mapping=None):
        self.mapping = dict(self.DEFAULT if mapping is None else mapping)

    def actions(self, keys):
        return [self.mapping[key] for key in keys if key in self.mapping]


class Raw:
    """Put a terminal in cbreak mode for the duration of a `with` block; a no-op without a tty."""

    def __init__(self, fd):
        self.fd, self.saved = fd, None

    def __enter__(self):
        try:
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except (termios.error, OSError, ValueError):
            self.saved = None
        return self

    def __exit__(self, *exc):
        if self.saved is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
            except (termios.error, OSError, ValueError):
                pass
        return False


class FdSource:
    """Actions read without blocking from a file descriptor (a terminal in cbreak mode, a pipe)."""

    def __init__(self, fd, keymap=None):
        self.fd, self.keymap, self.buffer, self.eof = fd, keymap or KeyMap(), b"", False

    def poll(self, timeout=0.0):
        actions = []
        try:
            ready, _, _ = select.select([self.fd], [], [], timeout)
            if ready:
                data = os.read(self.fd, 4096)
                if not data:
                    self.eof = True
                self.buffer += data
        except (OSError, ValueError):
            self.eof = True
        keys, self.buffer = decode_keys(self.buffer, final=self.eof or not self.buffer)
        return self.keymap.actions(keys)


class ListSource:
    """Scripted actions for tests and recordings: one list of actions per poll."""

    def __init__(self, script):
        self.script = list(script)
        self.eof = False

    def poll(self, timeout=0.0):
        if not self.script:
            self.eof = True
            return []
        step = self.script.pop(0)
        return [step] if isinstance(step, str) else list(step)


class NoInput:
    """A source with no input that never ends: for animations whose host reads the keyboard itself."""

    eof = False

    def poll(self, timeout=0.0):
        return []
