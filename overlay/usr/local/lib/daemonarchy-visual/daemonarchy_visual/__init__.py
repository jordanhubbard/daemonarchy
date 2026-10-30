"""Daemonarchy visual SDK: terminal graphics, effects, input and sound cues.

The installer is this SDK's first consumer and a plain sample host is its
second (sdk/visual/examples/sample_host.py). The SDK draws, animates, reads
input actions and asks for audio cues. It holds no installation state and
performs no privileged operation: a host passes in immutable observations and
decides what an action means.

Versioning: API_VERSION is (major, minor). A minor release only adds names; a
major release may remove or change them. A host or plugin asks for the version
it was written against with `compatible("1.0")`; 1.1 added `inline`, overlay screens, `NoInput`
and `run_scene(keep=, screen=)`; 1.2 added `arcade` helpers and the `plugin` runtime (import them as
submodules); 1.3 added `windows` (open, close, resize, select, list and title, mediated by the host).
"""

from .caps import Capabilities, detect
from .palette import Colors, gradient, mix
from .glyphs import Glyphs
from .canvas import Canvas, Screen
from .layout import Rect
from .timeline import ManualClock, MonotonicClock, Timeline, Tween
from .effects import Fireworks, Particles
from .input import ACTIONS, KeyMap, NoInput, decode_keys
from . import inline
from .audio import Audio, NullAudio, ThreadedAudio
from .scene import Scene, run_scene
from . import windows

API_VERSION = (1, 3)
__version__ = "1.3.0"

__all__ = [
    "ACTIONS", "API_VERSION", "Audio", "Canvas", "Capabilities", "Colors", "Fireworks", "Glyphs", "KeyMap",
    "ManualClock", "MonotonicClock", "NoInput", "NullAudio", "Particles", "Rect", "Scene", "Screen", "ThreadedAudio",
    "Timeline", "Tween", "compatible", "decode_keys", "detect", "gradient", "inline", "mix", "run_scene", "windows",
]


def compatible(requested):
    """True if this SDK can serve code written for API `requested` ("1.0" or (1, 0))."""
    if isinstance(requested, str):
        try:
            major, minor = (int(part) for part in requested.split(".")[:2])
        except ValueError:
            return False
    else:
        major, minor = requested
    return major == API_VERSION[0] and minor <= API_VERSION[1]
