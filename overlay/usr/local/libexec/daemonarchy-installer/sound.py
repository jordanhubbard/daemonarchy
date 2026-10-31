#!/usr/bin/env python3
"""Daemonarchy installer sounds: procedural cues played through FreeBSD OSS.

  sound.py ensure              start the player if sound is allowed here (returns at once)
  sound.py play CUE [CUE...]   queue cues; never blocks, never fails
  sound.py ctl ACTION          mute, unmute, toggle-mute, up, down, ambient, mode=on|quiet|off
  sound.py status              print the resolved mode, volume and reason
  sound.py label [--long]      the on-screen indicator text
  sound.py chime CUE           play one cue outside the installer (first boot, the live desktop)
  sound.py serve               run the player in the foreground (ensure starts it)
  sound.py render DIRECTORY    write a WAV preview of every cue, a tour and an ambient sample
  sound.py render-raw DIR CUE  write CUE.u8 (8 kHz unsigned 8-bit) for players without Python
  sound.py stop                stop the player

Every sound is synthesized here from oscillators and noise; there are no
sample files and nothing with an outside licence. One player process per
user owns /dev/dsp and mixes cues with an optional ambient layer. Front
ends (the install screen, the configurator, the live desktop's graphical
installer) only send datagrams to it with MSG_DONTWAIT, so a missing player,
a full queue or a broken audio device can never slow or fail an install.

Sound is off automatically on serial or headless consoles, in unattended
(CIDATA) installs unless requested, and when there is no audio device.
`daemonarchy.sound=on|quiet|off` in the loader environment, DAEMONARCHY_SOUND
or the installer's own setting choose it explicitly.

Honesty: cues follow real installer events (stage markers, package reports,
network results, the installer's own result). The ambient layer is a
sonification of the same measured activity rates the spectrum draws; with no
measured activity it is silent. No sound implies progress that was not
observed.
"""
import array
import json
import math
import os
from pathlib import Path
import random
import socket
import struct
import subprocess
import sys
import time

RATE = 22050
MODES = ('on', 'quiet', 'off')
VOLUME_DEFAULT = 70
VOLUME_STEP = 10

# OSS ioctls (sys/soundcard.h; the same numbers on FreeBSD and Linux).
SNDCTL_DSP_SPEED = 0xC0045002
SNDCTL_DSP_SETFMT = 0xC0045005
SNDCTL_DSP_CHANNELS = 0xC0045006
SNDCTL_DSP_SETFRAGMENT = 0xC004500A
AFMT_S16_LE = 0x10

# Which cues each mode plays. quiet keeps the moments that matter.
MAJOR = {'boot', 'fanfare', 'error', 'warn', 'commit', 'net_ok', 'net_fail', 'stage', 'stage_done',
         'greeting', 'volume'}
MINOR = {'tick', 'milestone', 'click', 'select', 'whoosh', 'attract'}

# Arcade sound effects ("blips") from plugins are requests, not cues: bounded, and played only in mode "on".
BLIP_WAVES = ('sq', 'tri', 'noise')
BLIP_FREQ, BLIP_MS, BLIP_LOUDEST = (30, 8000), (5, 400), 0.3   # Hz, milliseconds, amplitude ceiling (a cue's own level)
BLIP_VOICES = 4          # at most this many blips sound at once; the rest are dropped, never queued
BLIP_PER_SECOND = 20     # the client sends at most this many, with a small burst allowance


# ------------------------------------------------------------------ settings

def runtime_dir(env=None):
    env = os.environ if env is None else env
    base = env.get('DAEMONARCHY_SOUND_DIR')
    if base:
        return Path(base)
    return Path(env.get('TMPDIR', '/tmp')) / f'daemonarchy-sound-{os.getuid()}'


def read_settings(path):
    values = {}
    try:
        with open(path, encoding='utf-8') as stream:
            for line in stream.read(4096).splitlines()[:32]:
                key, sep, value = line.partition('=')
                if sep:
                    values[key.strip()] = value.strip()
    except (OSError, UnicodeError):
        pass
    result = {}
    if values.get('mode') in MODES:
        result['mode'] = values['mode']
    try:
        result['volume'] = max(0, min(100, int(values['volume'])))
    except (KeyError, ValueError):
        pass
    for key in ('muted', 'ambient'):
        if values.get(key) in ('0', '1'):
            result[key] = values[key] == '1'
    if values.get('reason'):
        result['reason'] = values['reason'][:80]
    return result


def write_settings(path, settings):
    path = Path(path)
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(path.name + f'.{os.getpid()}')
        lines = [f'{key}={int(value) if isinstance(value, bool) else value}'
                 for key, value in sorted(settings.items()) if key in ('mode', 'volume', 'muted', 'ambient', 'reason')]
        temporary.write_text('\n'.join(lines) + '\n')
        os.replace(temporary, path)
        return True
    except OSError:
        return False


_kenv_cache = {}


def kenv(name, runner=subprocess.run):
    """A loader variable, read once per process (the kernel environment is fixed after boot)."""
    if not sys.platform.startswith('freebsd'):
        return ''
    if name not in _kenv_cache:
        try:
            _kenv_cache[name] = runner(['kenv', '-q', name], capture_output=True, text=True, timeout=2,
                                       check=False).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            _kenv_cache[name] = ''
    return _kenv_cache[name]


def console_kind(env, tty=None):
    """vt (a local console or desktop), serial, or none (headless or no terminal)."""
    if env.get('DAEMONARCHY_LIVE') == '1' or env.get('WAYLAND_DISPLAY') or env.get('DISPLAY'):
        return 'vt'
    if env.get('DAEMONARCHY_CONSOLE') == 'vt':
        return 'vt'
    if tty is None:
        try:
            tty = os.ttyname(0)
        except OSError:
            tty = ''
    if tty.startswith(('/dev/ttyu', '/dev/cuau', '/dev/ttyS', '/dev/ttyAMA')):
        return 'serial'
    if env.get('TERM', '') in ('vt100', 'vt102', 'vt220', 'ansi', 'dumb'):
        return 'serial'
    if tty.startswith('/dev/ttyv') or tty.startswith('/dev/tty') and tty[8:].isdigit():
        return 'vt'
    if tty.startswith('/dev/pts/'):
        # A terminal inside the installer's own tmux session or a desktop terminal.
        return 'vt' if env.get('TMUX') or env.get('DAEMONARCHY_INSTALL_SCREEN') else 'none'
    return 'none'


def device_path(env):
    return env.get('DAEMONARCHY_SOUND_DEVICE', '/dev/dsp')


def device_present(env):
    path = device_path(env)
    if path.startswith('file:'):
        return True
    if Path(path).exists():
        return True
    return any(Path('/dev').glob('dsp[0-9]*')) if path == '/dev/dsp' else False


def load_drivers(env, runner=subprocess.run):
    """Load sound(4) drivers once when root on FreeBSD; kldload -n is a no-op when present."""
    if not sys.platform.startswith('freebsd') or os.geteuid() != 0 or env.get('DAEMONARCHY_SOUND_KLD') == 'off':
        return
    for module in ('snd_hda', 'snd_uaudio'):
        try:
            runner(['kldload', '-n', module], capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            pass


def resolve(env=None, settings=None, kenv_value=None, console=None, device=None):
    """(mode, reason). Explicit choices win; then the automatic silences."""
    env = os.environ if env is None else env
    settings = read_settings(runtime_dir(env) / 'settings') if settings is None else settings
    forced = env.get('DAEMONARCHY_SOUND', '').lower()
    if forced in MODES:
        return forced, 'DAEMONARCHY_SOUND'
    if settings.get('mode') in MODES:
        return settings['mode'], settings.get('reason', 'chosen in the installer')
    value = (kenv('daemonarchy.sound') if kenv_value is None else kenv_value).lower()
    if value in MODES:
        return value, 'loader daemonarchy.sound'
    if env.get('DAEMONARCHY_UNATTENDED') == '1':
        return 'off', 'unattended install (daemonarchy.sound=on enables it)'
    kind = console_kind(env) if console is None else console
    if kind == 'serial':
        return 'off', 'serial console'
    if kind != 'vt':
        return 'off', 'no local console'
    present = device_present(env) if device is None else device
    if not present:
        return 'off', 'no audio device'
    return 'on', 'default'


class State:
    """What the controls and the on-screen indicator show."""

    def __init__(self, env=None):
        self.env = os.environ if env is None else env
        self.dir = runtime_dir(self.env)
        self.refresh()

    def refresh(self):
        settings = read_settings(self.dir / 'settings')
        self.mode, self.reason = resolve(self.env, settings)
        self.volume = settings.get('volume', VOLUME_DEFAULT)
        self.muted = settings.get('muted', False)
        self.ambient = settings.get('ambient', True)
        status = read_settings(self.dir / 'status')
        self.device_error = status.get('reason', '') if status.get('mode') == 'off' else ''
        return self

    def audible(self):
        return self.mode != 'off' and not self.muted and self.volume > 0 and not self.device_error

    def label(self, unicode=True):
        note = '♪' if unicode else 'Sound'
        if self.mode == 'off':
            return f'{note} off ({self.reason})'
        if self.device_error:
            return f'{note} off ({self.device_error})'
        if self.muted:
            return f'{note} muted'
        extra = ' quiet' if self.mode == 'quiet' else ''
        return f'{note}{extra} {self.volume}%'

    def short(self, unicode=True):
        note = '♪' if unicode else 'snd'
        if self.mode == 'off' or self.device_error:
            return f'{note} off'
        if self.muted:
            return f'{note} muted'
        return f'{note}{self.volume}%'


# ------------------------------------------------------------------ client

class Client:
    """Fire-and-forget datagrams to the player. Every failure is silent."""

    def __init__(self, env=None):
        self.blip_budget, self.blip_at = 8.0, time.monotonic()
        self.env = os.environ if env is None else env
        self.path = str(runtime_dir(self.env) / 'sock')
        self.sock = None
        self.state = State(self.env)
        self.checked = 0.0

    def _send(self, message):
        try:
            if self.sock is None:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                self.sock.setblocking(False)
            self.sock.sendto(json.dumps(message).encode()[:2048], socket.MSG_DONTWAIT, self.path)
            return True
        except (OSError, ValueError, TypeError):
            return False

    def _fresh(self):
        now = time.monotonic()
        if now - self.checked > 1.0:
            self.checked = now
            self.state.refresh()
        return self.state

    def wants(self, cue):
        state = self._fresh()
        if not state.audible():
            return False
        return cue in MAJOR if state.mode == 'quiet' else True

    def play(self, cue, **params):
        if cue not in CUES or not self.wants(cue):
            return False
        return self._send(dict(cue=cue, **{k: v for k, v in params.items() if isinstance(v, (int, float))}))

    def blip(self, freq, ms, wave, volume):
        """One arcade sound effect. Only in mode "on": quiet keeps the moments that matter, and a game is not one.

        Values are clamped, and sends are rate-limited so a plugin cannot flood the player.
        """
        if wave not in BLIP_WAVES or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (freq, ms, volume)):
            return False
        state = self._fresh()
        if not state.audible() or state.mode != 'on':
            return False
        now = time.monotonic()
        self.blip_budget = min(8.0, self.blip_budget + (now - self.blip_at) * BLIP_PER_SECOND)
        self.blip_at = now
        if self.blip_budget < 1.0:
            return False
        self.blip_budget -= 1.0
        return self._send(dict(blip=[int(max(BLIP_FREQ[0], min(BLIP_FREQ[1], freq))),
                                     int(max(BLIP_MS[0], min(BLIP_MS[1], ms))), wave,
                                     int(max(0, min(100, volume)))]))

    def ambient(self, levels):
        state = self._fresh()
        if not state.audible() or state.mode != 'on' or not state.ambient:
            return False
        clean = {k: max(0.0, min(1.0, float(levels.get(k, 0.0)))) for k in ('cpu', 'disk', 'net')}
        return self._send(dict(ambient=clean))

    def reload(self):
        return self._send(dict(reload=1))

    def keepalive(self):
        """Tell the player a front end is still here; restart it if it has gone."""
        state = self._fresh()
        if state.mode == 'off':
            return False
        if not _player_pid(runtime_dir(self.env)):
            ensure(self.env)
        return self._send(dict(hello=1))


def ctl(action, env=None):
    """Change mute, volume, ambient or mode; returns the new State."""
    env = os.environ if env is None else env
    directory = runtime_dir(env)
    settings = read_settings(directory / 'settings')
    state = State(env)
    if action in ('mute', 'unmute', 'toggle-mute'):
        settings['muted'] = (not state.muted) if action == 'toggle-mute' else action == 'mute'
    elif action in ('up', 'down'):
        volume = settings.get('volume', VOLUME_DEFAULT)
        volume = max(0, min(100, volume + (VOLUME_STEP if action == 'up' else -VOLUME_STEP)))
        settings['volume'] = volume
        settings['muted'] = volume == 0
    elif action in ('ambient', 'ambient-on', 'ambient-off'):
        settings['ambient'] = (not state.ambient) if action == 'ambient' else action == 'ambient-on'
    elif action.startswith('mode='):
        mode = action[5:]
        if mode not in MODES:
            raise ValueError(f'unknown sound mode {mode}')
        settings['mode'] = mode
        settings['reason'] = 'chosen in the installer'
        settings['muted'] = False
    else:
        raise ValueError(f'unknown sound control {action}')
    write_settings(directory / 'settings', settings)
    state.refresh()
    client = Client(env)
    client.reload()
    if action.startswith('mode=') and state.mode != 'off':
        ensure(env)
    if state.audible() and action in ('unmute', 'toggle-mute', 'up', 'down') or action.startswith('mode='):
        client.checked = 0.0
        client.play('volume')
    return state


# ------------------------------------------------------------------ synthesis

def midi(note):
    return 440.0 * 2 ** ((note - 69) / 12)


NOTE = {n: i for i, n in enumerate(('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'))}


def pitch(name):
    """'D4' -> Hz."""
    letters = name[:-1]
    octave = int(name[-1])
    return midi(NOTE[letters] + 12 * (octave + 1))


class Buffer:
    def __init__(self, seconds):
        self.data = [0.0] * int(seconds * RATE)

    def add(self, start, samples):
        offset = int(start * RATE)
        data = self.data
        end = min(len(data), offset + len(samples))
        for i in range(max(0, offset), end):
            data[i] += samples[i - offset]
        return self

    def pcm(self, gain=1.0):
        out = array.array('h')
        for value in self.data:
            value = math.tanh(value * gain * 1.2) / math.tanh(1.2)
            out.append(int(max(-1.0, min(1.0, value)) * 32000))
        return out


def envelope(n, attack, release, total, curve=3.0):
    a = max(1, int(attack * RATE))
    r = max(1, int(release * RATE))
    env = []
    for i in range(n):
        if i < a:
            level = i / a
        else:
            level = math.exp(-curve * (i - a) / max(1, n - a)) if total == 'decay' else 1.0
        if i >= n - r:
            level *= max(0.0, (n - i) / r)
        env.append(level)
    return env


def tone(freq, seconds, wave='square', volume=0.3, attack=0.004, release=0.03, decay=False,
         duty=0.5, slide=None, vibrato=0.0, curve=3.0):
    """One voice. slide: end frequency (exponential glide)."""
    n = max(1, int(seconds * RATE))
    env = envelope(n, attack, release, 'decay' if decay else 'sustain', curve)
    out = [0.0] * n
    phase = 0.0
    ratio = (slide / freq) if slide else 1.0
    for i in range(n):
        t = i / n
        f = freq * (ratio ** t)
        if vibrato:
            f *= 1.0 + vibrato * math.sin(2 * math.pi * 5.5 * i / RATE) * min(1.0, i / (0.15 * RATE))
        phase = (phase + f / RATE) % 1.0
        if wave == 'square':
            v = 1.0 if phase < duty else -1.0
        elif wave == 'triangle':
            v = 4 * abs(phase - 0.5) - 1
        elif wave == 'saw':
            v = 2 * phase - 1
        else:
            v = math.sin(2 * math.pi * phase)
        out[i] = v * env[i] * volume
    return out


def bell(freq, seconds, volume=0.25):
    """Inharmonic partials with fast-decaying highs: a small struck bell."""
    n = int(seconds * RATE)
    out = [0.0] * n
    partials = ((1.0, 1.0, 3.0), (2.0, 0.5, 5.0), (2.76, 0.35, 7.0), (5.4, 0.18, 11.0))
    for ratio, level, damping in partials:
        step = 2 * math.pi * freq * ratio / RATE
        for i in range(n):
            out[i] += math.sin(step * i) * level * math.exp(-damping * i / RATE)
    attack = int(0.002 * RATE)
    for i in range(min(n, attack)):
        out[i] *= i / attack
    return [v * volume / 2.0 for v in out]


def noise(seconds, volume=0.2, low=None, high=None, seed=7, decay=True):
    """LFSR-style noise through a one-pole low-pass whose cutoff glides low->high."""
    rng = random.Random(seed)
    n = int(seconds * RATE)
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        t = i / max(1, n - 1)
        cutoff = (low or 8000) * ((high or low or 8000) / (low or 8000)) ** t
        alpha = 1 - math.exp(-2 * math.pi * cutoff / RATE)
        y += alpha * (rng.uniform(-1, 1) - y)
        level = math.exp(-4 * t) if decay else math.sin(math.pi * t)
        out[i] = y * volume * level
    return out


def cue_boot():
    b = Buffer(2.3)
    for i, name in enumerate(('D3', 'A3', 'D4', 'F#4', 'A4')):
        b.add(i * 0.035, tone(pitch(name), 2.0, 'triangle', 0.16, attack=0.03, release=0.4, decay=True, curve=2.2))
        b.add(i * 0.035, tone(pitch(name) * 1.003, 2.0, 'sine', 0.10, attack=0.05, release=0.4, decay=True, curve=2.0))
    b.add(0.18, bell(pitch('D6'), 1.8, 0.22))
    b.add(0.32, bell(pitch('A6'), 1.4, 0.10))
    for i, name in enumerate(('D6', 'F#6', 'A6', 'D7')):
        b.add(0.55 + i * 0.06, tone(pitch(name), 0.25, 'sine', 0.05, release=0.15, decay=True))
    return b


def cue_fanfare():
    b = Buffer(2.4)
    lead = (('A4', 0.0, 0.12), ('D5', 0.12, 0.12), ('F#5', 0.24, 0.12), ('A5', 0.36, 0.40),
            ('F#5', 0.80, 0.12), ('A5', 0.92, 0.12), ('D6', 1.04, 0.95))
    for name, start, length in lead:
        b.add(start, tone(pitch(name), length, 'square', 0.16, duty=0.25, release=0.05,
                          vibrato=0.006 if length > 0.5 else 0.0))
        b.add(start, tone(pitch(name) / 2 ** (4 / 12), length, 'square', 0.07, duty=0.5, release=0.05))
    for name, start, length in (('D3', 0.0, 0.34), ('A2', 0.36, 0.42), ('D3', 0.80, 0.22), ('D3', 1.04, 0.95)):
        b.add(start, tone(pitch(name), length, 'triangle', 0.28, release=0.06))
    for start in (0.36, 1.04):
        b.add(start, noise(0.18, 0.18, low=3000, high=9000))
    for i, name in enumerate(('D6', 'F#6', 'A6', 'D7', 'A6', 'D7', 'F#7')):
        b.add(1.15 + i * 0.07, tone(pitch(name), 0.18, 'square', 0.035, duty=0.125, decay=True))
    b.add(1.04, bell(pitch('D7'), 1.2, 0.08))
    return b


def cue_error():
    b = Buffer(1.6)
    for i, (name, length) in enumerate((('B3', 0.28), ('A#3', 0.28), ('A3', 0.28))):
        b.add(i * 0.30, tone(pitch(name), length, 'square', 0.14, duty=0.4, release=0.06))
    b.add(0.90, tone(pitch('G#3'), 0.65, 'square', 0.14, duty=0.4, slide=pitch('F#3'), vibrato=0.02, release=0.2))
    return b


def cue_warn():
    b = Buffer(1.0)
    for i in range(3):
        b.add(i * 0.30, tone(660, 0.14, 'square', 0.13, duty=0.3, release=0.02))
        b.add(i * 0.30 + 0.15, tone(523, 0.14, 'square', 0.13, duty=0.3, release=0.02))
    return b


def cue_commit():
    b = Buffer(1.0)
    b.add(0, tone(70, 0.3, 'sine', 0.55, slide=38, decay=True, release=0.05))
    b.add(0, noise(0.12, 0.25, low=900, high=200))
    b.add(0.12, tone(180, 0.7, 'square', 0.07, duty=0.25, slide=1400, release=0.25))
    b.add(0.12, noise(0.75, 0.10, low=400, high=6000, decay=False))
    return b


def cue_stage():
    b = Buffer(0.4)
    for i, name in enumerate(('E5', 'G#5', 'B5', 'E6')):
        b.add(i * 0.045, tone(pitch(name), 0.09 if i < 3 else 0.2, 'square', 0.10, duty=0.25, release=0.04,
                              decay=i == 3))
    return b


def cue_stage_done():
    b = Buffer(0.8)
    b.add(0, bell(pitch('B5'), 0.6, 0.22))
    b.add(0.09, bell(pitch('E6'), 0.7, 0.22))
    return b


def cue_milestone():
    b = Buffer(0.6)
    for i, name in enumerate(('D5', 'F#5', 'A5')):
        b.add(i * 0.06, tone(pitch(name), 0.07, 'square', 0.10, duty=0.125))
    b.add(0.18, tone(pitch('D6'), 0.3, 'square', 0.10, duty=0.125, decay=True, vibrato=0.01))
    return b


def cue_net_ok():
    b = Buffer(0.4)
    b.add(0, tone(pitch('C6'), 0.12, 'sine', 0.22, decay=True))
    b.add(0.08, tone(pitch('G6'), 0.25, 'sine', 0.22, decay=True))
    return b


def cue_net_fail():
    b = Buffer(0.5)
    b.add(0, tone(pitch('E5'), 0.16, 'square', 0.10, duty=0.5))
    b.add(0.17, tone(pitch('A#4'), 0.28, 'square', 0.10, duty=0.5, slide=pitch('A4'), release=0.1))
    return b


def cue_whoosh():
    b = Buffer(0.4)
    b.add(0, noise(0.38, 0.22, low=300, high=5000, decay=False))
    b.add(0, tone(220, 0.38, 'sine', 0.04, slide=880, release=0.15))
    return b


def cue_click():
    return Buffer(0.03).add(0, tone(2200, 0.018, 'square', 0.06, duty=0.5, decay=True, release=0.005))


def cue_select():
    b = Buffer(0.12)
    b.add(0, tone(pitch('A5'), 0.035, 'square', 0.08, duty=0.25))
    b.add(0.04, tone(pitch('E6'), 0.06, 'square', 0.08, duty=0.25, decay=True))
    return b


def cue_greeting():
    b = Buffer(2.0)
    for i, name in enumerate(('D4', 'F#4', 'A4', 'D5', 'F#5', 'A5', 'D6')):
        b.add(i * 0.07, bell(pitch(name), 1.3, 0.13))
    b.add(0, tone(pitch('D3'), 1.6, 'triangle', 0.14, attack=0.08, release=0.5, decay=True))
    return b


def cue_volume():
    return Buffer(0.12).add(0, tone(880, 0.09, 'sine', 0.25, release=0.03))


def cue_attract():
    """A soft two-note 'still here' for genuine waits (attract mode)."""
    b = Buffer(0.6)
    b.add(0, tone(pitch('A4'), 0.18, 'triangle', 0.12, decay=True))
    b.add(0.2, tone(pitch('D5'), 0.3, 'triangle', 0.12, decay=True))
    return b


PENTATONIC = ('D', 'E', 'F#', 'A', 'B')


def cue_tick(step=0):
    """The ticker blip. Its pitch walks a pentatonic scale with the package count."""
    step = int(step) % 15
    name = PENTATONIC[step % 5] + str(5 + step // 5)
    return Buffer(0.06).add(0, tone(pitch(name), 0.045, 'square', 0.06, duty=0.125, decay=True, release=0.01))


# Game cues (daemonarchy-games). Original, generated, short, and never in quiet mode.

def cue_game_laser():
    return Buffer(0.14).add(0, tone(pitch('A6'), 0.12, 'square', 0.07, duty=0.25, decay=True,
                                    slide=pitch('A4'), release=0.02))


def cue_game_hit():
    b = Buffer(0.25)
    b.add(0, noise(0.2, 0.16, low=200, high=2500))
    b.add(0, tone(pitch('E3'), 0.22, 'square', 0.10, decay=True, slide=pitch('A2')))
    return b


def cue_game_explode():
    b = Buffer(0.45)
    b.add(0, noise(0.42, 0.22, low=100, high=3000))
    b.add(0, tone(pitch('A2'), 0.4, 'triangle', 0.15, decay=True, slide=pitch('A1')))
    return b


def cue_game_bounce():
    return Buffer(0.08).add(0, tone(pitch('E5'), 0.06, 'triangle', 0.12, decay=True, release=0.01))


def cue_game_pickup():
    b = Buffer(0.2)
    b.add(0, tone(pitch('C6'), 0.06, 'square', 0.07, duty=0.25, decay=True))
    b.add(0.06, tone(pitch('G6'), 0.1, 'square', 0.07, duty=0.25, decay=True))
    return b


def cue_game_levelup():
    b = Buffer(0.5)
    for i, name in enumerate(('C5', 'E5', 'G5', 'C6')):
        b.add(i * 0.08, tone(pitch(name), 0.12, 'square', 0.07, duty=0.25, decay=True))
    return b


def cue_game_gameover():
    b = Buffer(0.9)
    for i, name in enumerate(('E4', 'C4', 'A3')):
        b.add(i * 0.2, tone(pitch(name), 0.28, 'triangle', 0.13, decay=True))
    return b


def cue_game_win():
    b = Buffer(0.7)
    for i, name in enumerate(('G5', 'C6', 'E6', 'G6')):
        b.add(i * 0.1, tone(pitch(name), 0.25, 'square', 0.07, duty=0.25, decay=True))
    return b


CUES = dict(boot=cue_boot, fanfare=cue_fanfare, error=cue_error, warn=cue_warn, commit=cue_commit,
            stage=cue_stage, stage_done=cue_stage_done, milestone=cue_milestone, net_ok=cue_net_ok,
            net_fail=cue_net_fail, whoosh=cue_whoosh, click=cue_click, select=cue_select,
            greeting=cue_greeting, volume=cue_volume, attract=cue_attract, tick=cue_tick,
            game_laser=cue_game_laser, game_hit=cue_game_hit, game_explode=cue_game_explode,
            game_bounce=cue_game_bounce, game_pickup=cue_game_pickup, game_levelup=cue_game_levelup,
            game_gameover=cue_game_gameover, game_win=cue_game_win)
DESCRIPTIONS = dict(
    boot='boot chime: the installer has started on this console',
    stage='an install stage started (installer @@phase/@@step marker)',
    stage_done='an install stage finished',
    tick='pkg reported a package; pitch follows the package count',
    milestone='every 50 packages pkg reports',
    net_ok='a network check passed (adapter, DHCP, DNS, clock, firmware)',
    net_fail='a network check failed',
    warn='disk commit warning before anything is erased',
    commit='the operator confirmed the disk change; the install starts',
    error='the installer reported failure',
    fanfare='the installer reported success',
    whoosh='screen transition in the configurator',
    select='a choice was made',
    click='key feedback',
    greeting='first boot of the installed system and the live desktop greeting',
    volume='volume or mute feedback',
    attract='a genuine wait: no new progress report for a while',
    game_laser='a game: a shot',
    game_hit='a game: a hit on the player',
    game_explode='a game: something destroyed',
    game_bounce='a game: a bounce',
    game_pickup='a game: food or a bonus',
    game_levelup='a game: the next level',
    game_gameover='a game: the game is over',
    game_win='a game: a perfect game')

_cache = {}


_blips = {}


def blip_samples(freq, ms, wave, volume):
    """PCM for one blip, or None if the request is not acceptable. Cached by a coarse key."""
    if (wave not in BLIP_WAVES or isinstance(freq, bool) or isinstance(ms, bool) or isinstance(volume, bool)
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (freq, ms, volume))):
        return None
    freq = int(max(BLIP_FREQ[0], min(BLIP_FREQ[1], freq)))
    ms = int(max(BLIP_MS[0], min(BLIP_MS[1], ms)))
    level = BLIP_LOUDEST * max(0, min(100, volume)) / 100.0
    key = (round(freq / 10) * 10 or BLIP_FREQ[0], round(ms / 5) * 5, wave, round(level, 2))
    if key not in _blips:
        if len(_blips) >= 64:
            _blips.clear()
        seconds = key[1] / 1000.0
        if wave == 'noise':
            voice = noise(seconds, level, low=min(8000, key[0] * 4), high=max(200, key[0]))
        else:
            voice = tone(key[0], seconds, 'square' if wave == 'sq' else 'triangle', level,
                         attack=0.002, release=min(0.02, seconds / 3), decay=True)
        _blips[key] = Buffer(seconds).add(0, voice).pcm()
    return _blips[key]


def render(cue, **params):
    key = (cue, int(params.get('step', 0)) % 15 if cue == 'tick' else 0)
    if key not in _cache:
        buffer = CUES[cue](key[1]) if cue == 'tick' else CUES[cue]()
        _cache[key] = buffer.pcm()
    return _cache[key]


# ------------------------------------------------------------------ ambient

class Ambient:
    """A chiptune loop whose layers follow measured activity.

    cpu drives the arpeggio's loudness and tempo, disk the bass, network the
    hi-hats. Levels decay to zero without fresh measurements, so a machine
    that is not working is silent.
    """
    CHORDS = (('D3', ('D5', 'F5', 'A5', 'F5')), ('A#2', ('D5', 'F5', 'A#5', 'F5')),
              ('F3', ('C5', 'F5', 'A5', 'F5')), ('C3', ('C5', 'E5', 'G5', 'E5')))

    def __init__(self):
        self.levels = dict(cpu=0.0, disk=0.0, net=0.0)
        self.updated = float('-inf')
        self.step = 0
        self.next_step = 0
        self.voices = []
        self.cache = {}

    def update(self, levels, now):
        for key in self.levels:
            self.levels[key] = float(levels.get(key, 0.0))
        self.updated = now

    def note(self, name, seconds, wave, duty=0.5):
        key = (name, seconds, wave, duty)
        if key not in self.cache:
            self.cache[key] = tone(pitch(name), seconds, wave, 1.0, duty=duty, decay=True, release=0.02)
        return self.cache[key]

    def hat(self):
        if 'hat' not in self.cache:
            self.cache['hat'] = noise(0.04, 1.0, low=7000, high=9000, seed=3)
        return self.cache['hat']

    def active(self, now):
        if now - self.updated > 2.0:
            for key in self.levels:
                self.levels[key] = 0.0
        return any(v > 0.03 for v in self.levels.values())

    def fill(self, mix, start_sample, now):
        """Schedule notes whose start falls in this block."""
        if not self.active(now):
            self.next_step = max(self.next_step, start_sample)
            return
        cpu, disk, net = self.levels['cpu'], self.levels['disk'], self.levels['net']
        bpm = 92 + 48 * cpu
        step_samples = int(RATE * 60 / bpm / 4)
        end = start_sample + len(mix)
        while self.next_step < end:
            at = self.next_step - start_sample
            bar = (self.step // 16) % len(self.CHORDS)
            bass, arp = self.CHORDS[bar]
            beat = self.step % 16
            if cpu > 0.03:
                self.voices.append([at, self.note(arp[beat % 4], 0.11, 'square', 0.25), 0.05 + 0.10 * cpu])
            if disk > 0.03 and beat % 4 == 0:
                self.voices.append([at, self.note(bass, 0.28, 'triangle'), 0.10 + 0.22 * disk])
            if net > 0.03 and beat % 2 == 1:
                self.voices.append([at, self.hat(), 0.04 + 0.10 * net])
            self.step += 1
            self.next_step += step_samples
        keep = []
        for voice in self.voices:
            offset, samples, gain = voice
            begin = max(0, offset)
            for i in range(begin, min(len(mix), offset + len(samples))):
                mix[i] += samples[i - offset] * gain
            if offset + len(samples) > len(mix):
                voice[0] = offset - len(mix)
                keep.append(voice)
        self.voices = keep


# ------------------------------------------------------------------ player

class Device:
    def __init__(self, path):
        self.path = path
        self.fd = None
        self.error = ''

    def open(self):
        if self.fd is not None:
            return True
        try:
            if self.path.startswith('file:'):
                self.fd = os.open(self.path[5:], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                return True
            import fcntl
            fd = os.open(self.path, os.O_WRONLY)
            try:
                for request, value in ((SNDCTL_DSP_SETFRAGMENT, 0x0006000B), (SNDCTL_DSP_SETFMT, AFMT_S16_LE),
                                       (SNDCTL_DSP_CHANNELS, 1), (SNDCTL_DSP_SPEED, RATE)):
                    result = struct.unpack('i', fcntl.ioctl(fd, request, struct.pack('i', value)))[0]
                    if request == SNDCTL_DSP_SETFMT and result != AFMT_S16_LE:
                        raise OSError(0, 'device refuses 16-bit samples')
                    if request == SNDCTL_DSP_CHANNELS and result != 1:
                        raise OSError(0, 'device refuses mono')
            except OSError:
                os.close(fd)
                raise
            self.fd = fd
            self.error = ''
            return True
        except OSError as error:
            self.error = f'audio device unavailable: {error.strerror or error}'[:80]
            return False

    def write(self, data):
        view = memoryview(data)
        while view:
            written = os.write(self.fd, view)
            view = view[written:]

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        self.fd = None


class Player:
    BLOCK = 1024

    def __init__(self, env=None, device=None):
        self.env = os.environ if env is None else env
        self.dir = runtime_dir(self.env)
        self.state = State(self.env)
        self.state.device_error = ''  # The player's own device report never mutes it.
        self.device = device or Device(device_path(self.env))
        self.voices = []
        self.ambient = Ambient()
        self.samples = 0
        self.silent_since = time.monotonic()
        self.played = 0
        self.file_started, self.file_samples = None, 0
        self.last_message = time.monotonic()

    def gain(self):
        state = self.state
        if not state.audible():
            return 0.0
        level = (state.volume / 100.0) ** 1.6
        return level * (0.5 if state.mode == 'quiet' else 1.0)

    def handle(self, data, now):
        self.last_message = now
        try:
            message = json.loads(data.decode('utf-8', 'replace'))
        except ValueError:
            return
        if not isinstance(message, dict):
            return
        if message.get('reload'):
            self.state.refresh()
            self.state.device_error = ''
        elif message.get('quit'):
            raise SystemExit(0)
        elif isinstance(message.get('ambient'), dict):
            self.ambient.update(message['ambient'], now)
        elif isinstance(message.get('blip'), list) and len(message['blip']) == 4:
            blips = sum(1 for voice in self.voices if len(voice) > 2)
            if not self.state.audible() or self.state.mode != 'on' or blips >= BLIP_VOICES or len(self.voices) >= 12:
                return  # Dropped, never played late.
            samples = blip_samples(*message['blip'])
            if samples is not None:
                self.voices.append([0, samples, True])
        elif message.get('cue') in CUES:
            if not self.state.audible() or len(self.voices) >= 12:
                return  # Never queue a backlog: drop rather than play late.
            step = message.get('step', 0) if isinstance(message.get('step', 0), (int, float)) else 0
            self.voices.append([0, render(message['cue'], step=step)])

    def mix(self, now):
        block = [0.0] * self.BLOCK
        for voice in self.voices:
            offset, samples = voice[0], voice[1]
            end = min(len(samples), offset + self.BLOCK)
            for i in range(offset, end):
                block[i - offset] += samples[i] / 32000.0
            voice[0] = end
        self.voices = [v for v in self.voices if v[0] < len(v[1])]
        if self.state.mode == 'on' and self.state.ambient:
            self.ambient.fill(block, self.samples, now)
        self.samples += self.BLOCK
        gain = self.gain()
        out = array.array('h', (int(max(-1.0, min(1.0, math.tanh(v * gain * 1.3) / 0.862)) * 32000) for v in block))
        return out

    def busy(self, now):
        if not self.state.audible():
            self.voices.clear()
            return False
        return bool(self.voices) or (self.state.mode == 'on' and self.state.ambient and self.ambient.active(now))

    def status(self, mode, reason=''):
        write_settings(self.dir / 'status', dict(mode=mode, reason=reason) if reason else dict(mode=mode))

    def drain(self, sock):
        sock.setblocking(False)
        while True:
            try:
                data = sock.recv(4096)
            except (BlockingIOError, InterruptedError):
                return
            self.handle(data, time.monotonic())

    def serve(self, sock, idle_exit=None):
        import select
        try:
            os.nice(5)
        except OSError:
            pass
        self.status('on')
        retry_at = 0.0
        paced = self.device.path.startswith('file:')
        self.file_started = time.monotonic() if paced else None
        while True:
            now = time.monotonic()
            busy = self.busy(now)
            timeout = 0.0 if busy and self.device.fd is not None else (0.05 if busy else 1.0)
            if select.select([sock], [], [], timeout)[0]:
                self.drain(sock)
            now = time.monotonic()
            if not self.busy(now):
                if self.device.fd is not None and now - self.silent_since > 2.0:
                    self.device.close()  # Let other programs (the desktop) use the device.
                if idle_exit is not None and now - max(self.silent_since, self.last_message) > idle_exit:
                    return 0
                continue
            self.silent_since = now
            if self.device.fd is None:
                if now < retry_at or not self.device.open():
                    if now >= retry_at:
                        retry_at = now + 5.0
                        self.status('off', self.device.error)
                    self.voices.clear()  # Without a device, cues are dropped, never delayed.
                    continue
                self.status('on')
            try:
                if paced:
                    # A file stands in for /dev/dsp (tests, recordings): keep it in
                    # step with the wall clock, silence included, so a recording
                    # lines up with a screen cast made at the same time.
                    if self.file_started is None:
                        self.file_started = now
                    behind = int((now - self.file_started) * RATE) - self.file_samples
                    if behind > self.BLOCK:
                        behind = min(behind, RATE * 600)
                        self.device.write(bytes(behind * 2))
                        self.file_samples += behind
                self.device.write(self.mix(now).tobytes())
                self.played += 1
                if paced:
                    self.file_samples += self.BLOCK
                    time.sleep(self.BLOCK / RATE)
            except OSError as error:
                self.device.close()
                self.device.error = f'audio write failed: {error.strerror or error}'[:80]
                self.status('off', self.device.error)
                retry_at = now + 5.0
                self.voices.clear()


def _bind(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / 'sock'
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.bind(str(path))
    except OSError:
        # A stale socket from a player that died; a live one answers nothing either,
        # so check its pid file first.
        pid = _player_pid(directory)
        if pid:
            sock.close()
            return None
        path.unlink(missing_ok=True)
        sock.bind(str(path))
    os.chmod(path, 0o600)
    return sock


def _player_pid(directory):
    try:
        pid = int((directory / 'pid').read_text().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def serve(env=None, idle_exit=None):
    env = os.environ if env is None else env
    directory = runtime_dir(env)
    sock = _bind(directory)
    if sock is None:
        return 0
    (directory / 'pid').write_text(f'{os.getpid()}\n')
    import signal
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, lambda *_: sys.exit(0))
    try:
        return Player(env).serve(sock, idle_exit) or 0
    except (KeyboardInterrupt, SystemExit):
        return 0
    finally:
        sock.close()
        for name in ('sock', 'pid'):
            (directory / name).unlink(missing_ok=True)


IDLE_EXIT = 900.0  # A player nobody has used for 15 minutes exits; `play` starts it again.


def ensure(env=None, idle_exit=IDLE_EXIT):
    """Start the player in the background when sound is allowed. Never waits long."""
    env = dict(os.environ if env is None else env)
    directory = runtime_dir(env)
    mode, reason = resolve(env)
    if mode == 'off':
        write_settings(directory / 'status', dict(mode='off', reason=reason))
        return False
    load_drivers(env)
    if not device_present(env):
        write_settings(directory / 'status', dict(mode='off', reason='no audio device'))
        return False
    if _player_pid(directory):
        return True
    argv = [sys.executable, str(Path(__file__).resolve()), 'serve']
    if idle_exit is not None:
        argv += ['--idle-exit', str(idle_exit)]
    try:
        subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    except OSError:
        return False
    # Give the socket a moment to appear so a cue sent right after is heard.
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and not (directory / 'sock').exists():
        time.sleep(0.02)
    return True


def stop(env=None):
    pid = _player_pid(runtime_dir(env))
    if pid:
        try:
            os.kill(pid, 15)
        except OSError:
            pass


# ------------------------------------------------------------------ events

MILESTONE = 50


class Director:
    """Turns the shared progress model's events into cues and ambient levels.

    Both the console screen and the graphical installer feed it the same
    snapshots, so they make the same sounds for the same real events.
    """

    def __init__(self, client=None, clock=time.monotonic):
        self.client = client or Client()
        self.clock = clock
        self.seen = None
        self.last_tick = float('-inf')
        self.last_ambient = float('-inf')
        self.last_keepalive = clock()
        self.played = []  # (cue, params) for tests and on-screen echoes.

    def cue(self, name, **params):
        self.played.append((name, params))
        del self.played[:-64]
        self.client.play(name, **params)

    @staticmethod
    def cues_for(event):
        kind = event.get('kind')
        if kind == 'stage-start':
            return [('stage', {})]
        if kind == 'stage-done':
            return [('stage_done', {})]
        if kind == 'packages':
            cues = [('tick', dict(step=event.get('current', 0)))]
            if event.get('milestone'):
                cues.append(('milestone', {}))
            return cues
        if kind == 'warning':
            return [('net_fail', {})]
        if kind == 'failed':
            return [('error', {})]
        if kind == 'done':
            return [('fanfare', {})] if event.get('succeeded') else [('error', {})]
        if kind == 'waiting':
            return [('attract', {})]
        return []

    def feed(self, snapshot):
        events = snapshot.get('events') or []
        if self.seen is None:
            # A screen that starts late (or restarts) does not replay history,
            # except a result that is already known.
            self.seen = max((e['serial'] for e in events), default=0)
            for event in events:
                if event.get('kind') == 'done':
                    for name, params in self.cues_for(event):
                        self.cue(name, **params)
        now = self.clock()
        for event in events:
            if event['serial'] <= self.seen:
                continue
            self.seen = event['serial']
            for name, params in self.cues_for(event):
                if name == 'tick':
                    if now - self.last_tick < 0.09:
                        continue  # A backlog of package lines is one blip, not a drum roll.
                    self.last_tick = now
                self.cue(name, **params)
        if now - self.last_keepalive >= 30.0:
            self.last_keepalive = now
            keepalive = getattr(self.client, 'keepalive', None)
            if keepalive:
                keepalive()
        if now - self.last_ambient >= 0.25 and not snapshot.get('done'):
            self.last_ambient = now
            levels = ambient_levels(snapshot.get('activity') or {})
            if levels:
                self.client.ambient(levels)


def _norm(value, peak, floor):
    peak = max(peak, floor)
    if not value or value <= 0:
        return 0.0
    return max(0.0, min(1.0, math.log1p(value / floor) / math.log1p(peak / floor)))


def ambient_levels(activity):
    current, peaks = activity.get('current') or {}, activity.get('peaks') or {}
    if not current:
        return None
    cores = current.get('cores') or []
    cpu = sum(cores) / len(cores) if cores else 0.0
    disk = max(_norm(current.get(k, 0.0), peaks.get(k, 0.0), 1 << 20) for k in ('disk_write', 'disk_read'))
    net = _norm(current.get('net_rx', 0.0) + current.get('net_tx', 0.0),
                peaks.get('net_rx', 0.0) + peaks.get('net_tx', 0.0), 64 << 10)
    return dict(cpu=cpu, disk=disk, net=net)


# ------------------------------------------------------------------ previews

def wav(path, samples):
    data = samples.tobytes() if sys.byteorder == 'little' else _swapped(samples)
    header = b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack(
        '<IHHIIHH', 16, 1, 1, RATE, RATE * 2, 2, 16) + b'data' + struct.pack('<I', len(data))
    Path(path).write_bytes(header + data)


def _swapped(samples):
    copy = array.array('h', samples)
    copy.byteswap()
    return copy.tobytes()


def preview(directory):
    """Every cue, a tour of the install's sounds, and a sample of the ambient layer."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name in CUES:
        path = directory / f'{name}.wav'
        wav(path, render(name, step=0))
        written.append(path)
    gap = array.array('h', [0] * int(RATE * 0.45))
    tour = array.array('h')
    story = ['boot', 'select', 'whoosh', 'net_ok', 'net_ok', 'net_fail', 'net_ok', 'whoosh', 'warn', 'commit',
             'stage', 'stage_done', 'stage']
    for name in story:
        tour.extend(render(name))
        tour.extend(gap)
    for index in range(60, 100):
        tour.extend(render('tick', step=index))
        tour.extend(array.array('h', [0] * int(RATE * 0.08)))
        if index == 99:
            tour.extend(render('milestone'))
    for name in ('stage_done', 'attract', 'stage', 'stage_done', 'fanfare', 'error', 'greeting'):
        tour.extend(gap)
        tour.extend(render(name))
    wav(directory / 'tour.wav', tour)
    written.append(directory / 'tour.wav')
    # Ambient: twelve seconds through an illustrative activity curve (idle, disk
    # writes, then downloads, then idle again), so the silent ends are audible too.
    ambient = Ambient()
    out = array.array('h')
    position = 0
    seconds = 12.0
    while position < seconds * RATE:
        t = position / RATE
        rise = max(0.0, min(1.0, (t - 1.0) / 2.0)) * max(0.0, min(1.0, (11.0 - t) / 1.5))
        ambient.update(dict(cpu=0.6 * rise, disk=rise * (0.9 if t < 7 else 0.3),
                            net=rise * (0.0 if t < 5 else 0.8)), t)
        block = [0.0] * 1024
        ambient.fill(block, position, t)
        out.extend(int(max(-1.0, min(1.0, math.tanh(v * 1.3) / 0.862)) * 32000 * 0.7) for v in block)
        position += 1024
    wav(directory / 'ambient.wav', out)
    written.append(directory / 'ambient.wav')
    return written


def raw8k(samples):
    """8 kHz unsigned 8-bit mono: the format /dev/dsp starts in, for players without ioctls."""
    filtered, y = [], 0.0
    alpha = 1 - math.exp(-2 * math.pi * 3400 / RATE)
    for value in samples:
        y += alpha * (value / 32768.0 - y)
        filtered.append(y)
    out = bytearray()
    step = RATE / 8000
    position = 0.0
    while position < len(filtered) - 1:
        index = int(position)
        frac = position - index
        value = filtered[index] * (1 - frac) + filtered[index + 1] * frac
        out.append(max(0, min(255, int(128 + value * 127))))
        position += step
    return bytes(out)


# ------------------------------------------------------------------ command line

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__.strip())
        return 2
    command, rest = argv[0], argv[1:]
    try:
        if command == 'play':
            client = Client()
            if any(client.wants(name) for name in rest if name in CUES) and not _player_pid(runtime_dir()):
                ensure()  # The player exited after a long quiet spell (or never started).
            for name in rest:
                client.play(name)
            return 0
        if command == 'ensure':
            ensure()
            return 0
        if command == 'serve':
            idle = float(rest[1]) if rest[:1] == ['--idle-exit'] and len(rest) > 1 else None
            return serve(idle_exit=idle)
        if command == 'stop':
            stop()
            return 0
        if command == 'status':
            state = State()
            print(f'mode={state.mode} reason={state.reason!r} volume={state.volume} muted={int(state.muted)} '
                  f'ambient={int(state.ambient)} device_error={state.device_error!r}')
            return 0
        if command == 'label':
            state = State()
            unicode = os.environ.get('DAEMONARCHY_GLYPHS') != 'ascii'
            print(state.label(unicode) if rest[:1] == ['--long'] else state.short(unicode))
            return 0
        if command == 'chime' and rest:
            # Outside the installer (first boot, the live desktop): a player that
            # exits by itself once the cue has played.
            if ensure(idle_exit=3.0):
                client = Client()
                for name in rest:
                    client.play(name)
            return 0
        if command == 'ctl' and rest:
            state = ctl(rest[0])
            tmux = rest[2] if rest[1:2] == ['--tmux'] and len(rest) > 2 else None
            if tmux:
                for args in (['set', '-g', '@sound', state.short()],
                             ['display-message', state.label() + ('  (ambient on)' if state.ambient and state.mode == 'on'
                                                                    and state.audible() else '')]):
                    subprocess.run(['tmux', '-S', tmux, *args], capture_output=True, timeout=3, check=False)
            else:
                print(state.label())
            return 0
        if command == 'render-raw' and len(rest) >= 2:
            directory = Path(rest[0])
            directory.mkdir(parents=True, exist_ok=True)
            for name in rest[1:]:
                (directory / f'{name}.u8').write_bytes(raw8k(render(name)))
            return 0
        if command == 'render' and rest:
            for path in preview(rest[0]):
                print(path)
            return 0
    except ValueError as error:
        print(f'sound: {error}', file=sys.stderr)
        return 2
    except OSError:
        return 0  # Sound never fails a caller.
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
