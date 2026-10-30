#!/usr/bin/env python3
"""The installer draws through the visual SDK. This holds it to that: every remaining hand-written terminal
escape in the installer is on an explicit allow-list with its reason, and the welcome frame, the logo and the
terminal restore go through charm (the SDK), with a plain-text fallback when Python is unavailable."""

import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBEXEC = ROOT / "overlay/usr/local/libexec/daemonarchy-installer"
CHARM = LIBEXEC / "charm.py"
LOGO = ROOT / "overlay/usr/local/share/daemonarchy-installer/logo.txt"

ESCAPE = re.compile(r"\\033\[|\\e\[|\\x1b\[|\\033\]|\\x1b\]|\\0337|\\0338")

# Every hand-written escape that is allowed to remain, by file, with why. Anything else is a failure:
# draw it with the SDK (daemonarchy_visual: Screen, Canvas, inline, ansi) instead.
ALLOWED = {
    "install": [
        (re.compile(r"^log\(\) \{ printf '\\033\[32m==>\\033\[0m"),
         "the install log's line prefix: a log protocol the progress screen parses and strips, not a screen"),
    ],
    "install-views": [
        (re.compile(r"^ANSI = re\.compile"), "strips escapes from text before showing it"),
    ],
    "progress-model.py": [
        (re.compile(r"^ANSI = re\.compile"), "strips escapes from text before showing it"),
    ],
    "configurator": [
        (re.compile(r"dot=\$'\\033\[(?:32m●|90m○)\\033\[0m'"),
         "coloured status dots in the network menu's gum labels (a gum prompt's item text)"),
        (re.compile(r"printf '\\033\[%d;1H\\0337'"),
         "places and saves the cursor for ttfx, the optional third-party text-effect tool on the welcome screen"),
    ],
}


class Audit(unittest.TestCase):
    def test_every_remaining_raw_escape_in_the_installer_is_allowed_and_explained(self):
        unexplained = []
        for path in sorted(LIBEXEC.iterdir()):
            if not path.is_file():
                continue
            try:
                lines = path.read_text().splitlines()
            except UnicodeError:
                continue
            for number, line in enumerate(lines, 1):
                if not ESCAPE.search(line):
                    continue
                if not any(pattern.search(line.strip()) for pattern, _why in ALLOWED.get(path.name, [])):
                    unexplained.append(f"{path.name}:{number}: {line.strip()[:100]}")
        self.assertEqual(unexplained, [], "hand-written terminal escapes outside the SDK:\n" + "\n".join(unexplained))

    def test_the_allow_list_has_no_stale_entries(self):
        for name, entries in ALLOWED.items():
            text = (LIBEXEC / name).read_text().splitlines()
            for pattern, why in entries:
                self.assertTrue(any(pattern.search(line.strip()) for line in text), f"{name}: no longer needed: {why}")

    def test_the_python_screens_import_the_sdk(self):
        for name in ("progress-dashboard.py", "charm.py", "install-views", "daemonarchy-extensions"):
            self.assertIn("daemonarchy_visual", (LIBEXEC / name).read_text(), name)

    def test_the_welcome_frame_and_logo_go_through_charm_with_a_plain_fallback(self):
        text = (LIBEXEC / "configurator").read_text()
        self.assertIn('"$CHARM" welcome --logo "$LOGO_PATH"', text)
        self.assertIn('"$CHARM" logo --logo "$LOGO_PATH"', text)
        self.assertIn('"$CHARM" restore', text)
        greeter = text[text.index("greeter() {"):text.index("\nabort() {")]
        for raw in ("[?25l", "[2J", "gum style"):
            self.assertNotIn(raw, greeter, raw)
        self.assertIn("cat \"$LOGO_PATH\"", greeter, "without Python the welcome falls back to plain text")


class Pty:
    def __init__(self, argv, env, rows=30, cols=100):
        import fcntl
        import pty
        import struct
        import termios
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True)
        os.close(slave)

    def output(self, seconds=6):
        import select
        data, end = b"", time.monotonic() + seconds
        while time.monotonic() < end:
            if select.select([self.master], [], [], 0.05)[0]:
                try:
                    block = os.read(self.master, 65536)
                except OSError:
                    break
                if not block:
                    break
                data += block
            elif self.proc.poll() is not None:
                break
        self.proc.wait(timeout=5)
        os.close(self.master)
        return data.decode("utf-8", "replace")


def charm(*argv, tty=False, **env):
    environ = dict(os.environ, TERM="xterm-256color", DAEMONARCHY_SOUND="off", **env)
    if tty:
        return Pty([sys.executable, "-I", str(CHARM), *argv], environ)
    return subprocess.run([sys.executable, "-I", str(CHARM), *argv], capture_output=True, text=True, env=environ)


class CharmCommands(unittest.TestCase):
    ARGS = ("welcome", "--logo", str(LOGO), "--logo-row", "5", "--tagline-row", "20", "--hint-row", "22",
            "--tagline", "Omarchy's desktop spliced onto FreeBSD's daemon · 1.4.1", "--hint", "Press Return for installer options")

    def test_welcome_draws_logo_tagline_and_hint_on_a_terminal(self):
        out = charm(*self.ARGS, tty=True).output()
        plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out)
        self.assertIn("Press Return for installer options", plain)
        self.assertIn("spliced onto FreeBSD's daemon", plain)
        self.assertTrue(out.startswith("\x1b[H\x1b[2J\x1b[?25l"), "clears, hides the cursor, then draws")
        self.assertIn("\x1b[22;", out, "the hint is on its row")
        self.assertNotIn("\x1b[?25h", out, "the cursor stays hidden for the animation that follows")
        first = next(line for line in LOGO.read_text().splitlines() if line.strip())
        self.assertIn(first.strip()[:8], plain)

    def test_welcome_is_plain_text_off_a_terminal(self):
        out = charm(*self.ARGS)
        self.assertEqual(out.returncode, 0)
        self.assertNotIn("\x1b", out.stdout)
        self.assertIn("Press Return for installer options", out.stdout)

    def test_logo_clears_and_draws_it_and_restore_puts_the_terminal_back(self):
        out = charm("logo", "--logo", str(LOGO), "--left", "4", tty=True).output()
        self.assertTrue(out.startswith("\x1b[H\x1b[2J"))
        self.assertNotIn("gum", out)
        restored = charm("restore", tty=True).output()
        self.assertEqual(restored, "\x1b[0m\x1b[H\x1b[2J\x1b[?25h")

    def test_bad_arguments_never_fail_the_installer(self):
        for argv in (("welcome",), ("welcome", "--logo", "/nonexistent"), ("logo",), ("logo", "--logo", "/nonexistent")):
            self.assertEqual(charm(*argv).returncode, 0, argv)


if __name__ == "__main__":
    unittest.main()
