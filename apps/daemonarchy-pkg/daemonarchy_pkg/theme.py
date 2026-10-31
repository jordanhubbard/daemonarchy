"""Colour for the window, taken from the SDK's palette so it matches the installer and the terminal tools.

The SDK (`daemonarchy_visual.palette`) has no GUI toolkit; what the window shares with it is the
palette: the logo gradient, the accent colours and the grays. They become one CSS file. The same
values are repeated below for a desktop that does not have the SDK installed, and a test fails if
they drift from the SDK's.

Kinds of change and kinds of trust each have one colour, used for the plan, the rows and the
progress, so a red thing always means removal or a broken signature. Colour is never the only
carrier of meaning: every chip also has text.
"""
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SDK_DIRS = ('/usr/local/lib/daemonarchy-visual', str(HERE.parents[2] / 'overlay/usr/local/lib/daemonarchy-visual'))

FALLBACK = dict(LOGO=((255, 70, 70), (230, 50, 140), (132, 93, 249)), WINAMP=((0, 210, 70), (180, 230, 0), (255, 220, 0),
                (255, 120, 0), (255, 40, 40)), WHITE=(240, 240, 240), GRAY=(150, 150, 150), DIM=(90, 90, 100),
                CYAN=(0, 230, 255), GREEN=(0, 220, 90), RED=(255, 60, 60), YELLOW=(255, 220, 0), PURPLE=(132, 93, 249),
                MAGENTA=(230, 50, 140), ORANGE=(255, 120, 0))
BACKGROUND, SURFACE, RAISED = (16, 16, 24), (24, 24, 34), (32, 32, 44)


def sdk_palette():
    """The SDK's palette module, or None when the SDK is not installed."""
    for directory in SDK_DIRS:
        if (Path(directory) / 'daemonarchy_visual/palette.py').is_file():
            if directory not in sys.path:
                sys.path.append(directory)
            try:
                from daemonarchy_visual import palette
                return palette
            except ImportError:
                return None
    return None


def tokens():
    palette = sdk_palette()
    if palette is None:
        return dict(FALLBACK)
    return {name: getattr(palette, name) for name in FALLBACK}


# What each kind of change, and each trust state, is called and coloured.
KIND = dict(install='GREEN', upgrade='CYAN', reinstall='PURPLE', downgrade='ORANGE', remove='RED')
TRUST = dict(signed='GREEN', unsigned='YELLOW', broken='RED')
BADGE = dict(installed='GREEN', update='CYAN', available='GRAY')
LABEL = dict(install='Install', upgrade='Upgrade', reinstall='Reinstall', downgrade='Downgrade', remove='Remove',
             autoremove='Remove unused',
             signed='Signed', unsigned='Not signed', broken='Key missing', installed='Installed', update='Update',
             available='Available')


def hexcolor(rgb):
    return '#%02x%02x%02x' % tuple(rgb)


def luminance(rgb):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(first, second):
    """WCAG contrast ratio of two colours (1 to 21)."""
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def reduced_motion(settings_animations=None, env=None):
    """True when motion should be off: DAEMONARCHY_REDUCED_MOTION=1, or GTK's gtk-enable-animations is false."""
    env = os.environ if env is None else env
    if env.get('DAEMONARCHY_REDUCED_MOTION', '') not in ('', '0'):
        return True
    return settings_animations is False


def css(palette=None):
    """The window's stylesheet. Every colour is a token above; sizes are in the stylesheet only."""
    t = palette or tokens()
    c = {name: hexcolor(t[name]) for name in ('WHITE', 'GRAY', 'DIM', 'CYAN', 'GREEN', 'RED', 'YELLOW', 'PURPLE',
                                              'MAGENTA', 'ORANGE')}
    bg, surface, raised = hexcolor(BACKGROUND), hexcolor(SURFACE), hexcolor(RAISED)
    first, second, third = (hexcolor(x) for x in t['LOGO'])
    chips = '\n'.join(f'.chip-{kind} {{ color: {c[colour]}; border-color: {c[colour]}; }}'
                      for kind, colour in {**KIND, **TRUST, **BADGE}.items())
    return f"""
window.daemonarchy-pkg, .daemonarchy-pkg {{ background: {bg}; color: {c['WHITE']}; }}
.daemonarchy-pkg .sidebar {{ background: {surface}; padding: 8px; }}
.daemonarchy-pkg .sidebar row {{ border-radius: 8px; padding: 8px 12px; margin: 2px 0; }}
.daemonarchy-pkg .sidebar row:selected {{ background-image: linear-gradient(90deg, {first}, {second}, {third}); color: #ffffff; }}
.daemonarchy-pkg .result-row {{ padding: 8px 12px; border-bottom: 1px solid {raised}; }}
.daemonarchy-pkg .result-row:selected {{ background: {raised}; }}
.daemonarchy-pkg .name {{ font-weight: bold; font-size: 110%; }}
.daemonarchy-pkg .comment, .daemonarchy-pkg .hint {{ color: {c['GRAY']}; }}
.daemonarchy-pkg .chip {{ border: 1px solid {c['GRAY']}; border-radius: 10px; padding: 0 8px; font-size: 85%; }}
{chips}
.daemonarchy-pkg .detail {{ background: {surface}; padding: 16px; }}
.daemonarchy-pkg .primary {{ background-image: linear-gradient(90deg, {first}, {second}, {third}); color: #ffffff;
    border-radius: 8px; border: none; font-weight: bold; }}
.daemonarchy-pkg .danger {{ background: {c['RED']}; color: #1a0000; border-radius: 8px; border: none; font-weight: bold; }}
.daemonarchy-pkg progressbar trough {{ background: {raised}; min-height: 12px; border-radius: 6px; }}
.daemonarchy-pkg progressbar progress {{ background-image: linear-gradient(90deg, {c['GREEN']}, {c['CYAN']}, {c['PURPLE']});
    min-height: 12px; border-radius: 6px; }}
.daemonarchy-pkg .warning {{ color: {c['YELLOW']}; }}
.daemonarchy-pkg .error {{ color: {c['RED']}; }}
.daemonarchy-pkg .ok {{ color: {c['GREEN']}; }}
.daemonarchy-pkg .log {{ font-family: monospace; color: {c['GRAY']}; }}
"""
