"""Terminal capability negotiation: color depth, glyph set, motion, size.

Nothing is assumed and nothing is silently approximated: a host reads the
result and chooses a presentation. Environment knobs, all optional:

  DAEMONARCHY_COLOR=none|8|16|256|truecolor   force a color depth
  NO_COLOR                                    no color at all
  DAEMONARCHY_GLYPHS=ascii|unicode            force the glyph set
  DAEMONARCHY_REDUCED_MOTION=1                reduce animation
  DAEMONARCHY_CHARM=off                       plain output only
  DAEMONARCHY_CONSOLE=vt                      the FreeBSD vt(4) console
"""

import os
import sys

PLAIN_TERMS = ("", "dumb", "vt100", "vt102", "vt220", "ansi", "cons25")


def color_depth(env, console):
    """none, 8, 16, 256 or truecolor.

    vt(4) parses 38;5;N but quantizes it to its 16-color palette, and it does
    not implement 38;2;R;G;B: teken reads R, G and B as separate attributes
    (bold, underline, blink, reverse...). The console therefore gets direct
    16-color output, and truecolor is never sent to it.
    """
    forced = env.get("DAEMONARCHY_COLOR", "")
    term = env.get("TERM", "")
    if "NO_COLOR" in env or forced == "none":
        return "none"
    if forced in ("8", "16", "256"):
        depth = forced
    elif forced == "truecolor":
        depth = "truecolor"
    elif term in ("vt100", "vt102", "vt220", "ansi", "cons25") or term.startswith("vt"):
        depth = "8"
    elif "256color" in term:
        depth = "256"
        if env.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
            depth = "truecolor"
    else:
        depth = "16"
    if console and depth in ("256", "truecolor"):
        depth = "16"
    return depth


def unicode_ok(env, console):
    forced = env.get("DAEMONARCHY_GLYPHS", "")
    if forced in ("ascii", "unicode"):
        return forced == "unicode"
    term = env.get("TERM", "")
    if term in ("vt100", "vt102", "vt220", "ansi", "cons25", "dumb"):
        return False
    if console:
        return True  # vt(4) is UTF-8 and its fonts carry block, box and braille glyphs.
    locale = " ".join(env.get(name, "") for name in ("LC_ALL", "LC_CTYPE", "LANG")).upper()
    return "UTF-8" in locale or "UTF8" in locale


def reduced_motion(env):
    return env.get("DAEMONARCHY_REDUCED_MOTION", "").lower() in ("1", "yes", "true")


class Capabilities:
    """What this terminal can show. Build with `detect`; tests may construct one directly."""

    def __init__(self, depth="16", unicode=True, reduced=False, plain=False, console=False,
                 width=80, height=24, audio=True):
        self.depth = depth          # none, 8, 16, 256 or truecolor
        self.unicode = unicode      # block and box glyphs available
        self.reduced = reduced      # fewer or no animations; never required to play
        self.plain = plain          # no cursor addressing: serial, dumb terminals, pipes
        self.console = console      # the FreeBSD vt(4) console
        self.width, self.height = width, height
        self.audio = audio          # audio cues may be requested (a host still may mute them)

    @property
    def small(self):
        """True when a full-screen scene cannot fit; scenes show a message instead."""
        return self.width < 40 or self.height < 16

    @property
    def tier(self):
        return "plain" if self.plain else "basic" if self.depth in ("none", "8", "16") else "rich"

    def __repr__(self):
        return (f"Capabilities(depth={self.depth!r}, unicode={self.unicode}, reduced={self.reduced}, "
                f"plain={self.plain}, console={self.console}, size={self.width}x{self.height})")


def size(stream=None):
    stream = stream or sys.stdout
    try:
        terminal = os.get_terminal_size(stream.fileno())
        return max(1, terminal.columns), max(1, terminal.lines)
    except (OSError, ValueError, AttributeError):
        return 80, 24


def detect(env=None, stream=None):
    """Negotiate capabilities for `stream` (stdout by default) under `env` (os.environ by default)."""
    env = dict(os.environ if env is None else env)
    stream = stream or sys.stdout
    tty = hasattr(stream, "isatty") and stream.isatty()
    try:
        name = os.ttyname(stream.fileno()) if tty else ""
    except (OSError, ValueError, AttributeError):
        name = ""
    console = env.get("DAEMONARCHY_CONSOLE", "vt" if name.startswith("/dev/ttyv") else "") == "vt"
    plain = (not tty or env.get("TERM", "") in PLAIN_TERMS or env.get("DAEMONARCHY_CHARM") == "off")
    width, height = size(stream)
    return Capabilities(
        depth="none" if plain else color_depth(env, console),
        unicode=unicode_ok(env, console),
        reduced=reduced_motion(env),
        plain=plain,
        console=console,
        width=width,
        height=height,
        audio=env.get("DAEMONARCHY_SOUND", "") != "off",
    )
