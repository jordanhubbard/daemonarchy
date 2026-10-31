#!/usr/bin/env python3
"""Sandboxed Lua extensions: the pixel surface, the plugin protocol, the sandbox itself, the blip sound
request and loading through the plugin registry. Nothing here touches the network or a real terminal."""
import array
import hashlib
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'overlay/usr/local/lib/daemonarchy-visual'
LIBEXEC = ROOT / 'overlay/usr/local/libexec/daemonarchy-installer'
GAMES = ROOT / 'extensions/games'
sys.path.insert(0, str(LIB))

import daemonarchy_visual as sdk  # noqa: E402
from daemonarchy_visual import audio, caps as sdk_caps, input as sdk_input, lua, plugin, timeline  # noqa: E402

sound_spec = importlib.util.spec_from_file_location('installer_sound', LIBEXEC / 'sound.py')
sound = importlib.util.module_from_spec(sound_spec)
sound_spec.loader.exec_module(sound)
progress_spec = importlib.util.spec_from_file_location('installer_progress_tests', ROOT / 'tests/installer-progress.py')
progress_tests = importlib.util.module_from_spec(progress_spec)
progress_spec.loader.exec_module(progress_tests)

LUA = lua.find_lua()
needs_lua = unittest.skipUnless(LUA, 'no Lua interpreter on this host')
needs_openssl = unittest.skipUnless(shutil.which('openssl'), 'no openssl on this host')


class Tty(io.StringIO):
    def isatty(self):
        return True


def capabilities(**kw):
    values = dict(depth='256', unicode=True, reduced=False, plain=False, width=80, height=24)
    values.update(kw)
    return sdk_caps.Capabilities(**values)


def sound_env(directory, mode='on'):
    env = progress_tests.clean_env()
    env.update(DAEMONARCHY_SOUND_DIR=str(directory), DAEMONARCHY_SOUND=mode,
               DAEMONARCHY_SOUND_DEVICE='file:%s/pcm' % directory)
    return env


class Session:
    """A plugin with its surface and held keys on synthetic time, for the tests."""

    def __init__(self, path, width=64, height=40, seed=1):
        self.surface = lua.PixelSurface(width, height)
        self.process = lua.LuaProcess(path, width, height, seed=seed)
        self.keys, self.last = lua.HeldKeys(), None

    @property
    def failure(self):
        return self.process.failure

    def step(self, now, data=b'', keys=()):
        for name in keys:
            self.keys.press(name, now)
        dt = 33 if self.last is None else (now - self.last) * 1000
        self.last = now
        blips = []
        for op in self.process.frame(dt, self.keys.held(now)) or ():
            if op[0] == 'S':
                blips.append(op[1:])
            else:
                self.surface.apply(op)
        return blips

    def close(self):
        self.process.stop()


class FakeCanvas:
    def __init__(self):
        self.cells = {}

    def put(self, x, y, text, style=None, width=None):
        self.cells[(x, y)] = (text, style)


class SurfaceTests(unittest.TestCase):
    def test_half_blocks_pack_two_pixels_per_row(self):
        surface = lua.PixelSurface(2, 4)
        surface.pixel(0, 0, 3)
        surface.pixel(0, 1, 4)
        surface.pixel(1, 0, 5)
        surface.pixel(1, 1, 5)
        self.assertEqual(surface.cell(0, 0), ('▀', (lua.PALETTE[3], lua.PALETTE[4], False)))
        self.assertEqual(surface.cell(1, 0), ('█', (lua.PALETTE[5], None, False)))
        surface.pixel(0, 3, 6)
        self.assertEqual(surface.cell(0, 1), ('▄', (lua.PALETTE[6], None, False)))
        self.assertEqual(surface.cell(1, 1), (' ', None))

    def test_ascii_fallback_uses_plain_characters(self):
        surface = lua.PixelSurface(1, 2)
        surface.pixel(0, 1, 7)
        char, style = surface.cell(0, 0, unicode=False)
        self.assertEqual(char, '#')
        self.assertTrue(char.isascii())

    def test_drawing_clips_and_blit_skips_empty_cells(self):
        surface = lua.PixelSurface(4, 4)
        surface.rect(-5, -5, 100, 100, 2)
        self.assertTrue(all(p == 2 for p in surface.pixels))
        surface.clear()
        surface.pixel(99, 99, 3)
        surface.pixel(1, 0, 3)
        canvas = FakeCanvas()
        surface.blit(canvas, 10, 5)
        self.assertEqual(list(canvas.cells), [(11, 5)])

    def test_size_is_bounded_and_even(self):
        for size in ((0, 2), (2, 3), (321, 2), (2, 202)):
            with self.assertRaises(ValueError):
                lua.PixelSurface(*size)



class ProtocolTests(unittest.TestCase):
    def parse(self, line):
        return lua.parse_op(line, 64, 40)

    def test_valid_operations(self):
        self.assertEqual(self.parse('F'), ('F',))
        self.assertEqual(self.parse('P 3 4 5'), ('P', 3, 4, 5))
        self.assertEqual(self.parse('R 1 2 3 4 5'), ('R', 1, 2, 3, 4, 5))
        self.assertEqual(self.parse('S 440 50 sq 30'), ('S', 440, 50, 'sq', 30))

    def test_values_are_clamped_not_trusted(self):
        self.assertEqual(self.parse('P 3 4 99'), ('P', 3, 4, 15))
        self.assertEqual(self.parse('R 0 0 99999 99999 1'), ('R', 0, 0, 64, 40, 1))
        self.assertEqual(self.parse('S 1 99999 noise 999'), ('S', 30, 400, 'noise', 100))

    def test_hostile_lines_are_ignored(self):
        for line in ('', 'P 1 2', 'P 1 2 x', 'P 1_0 2 3', 'P 1 2 3 4', 'P ١ 2 3', 'X', 'S 440 50 evil 30',
                     'P ' + '9' * 200, 'F extra', 'P 1e3 2 3', 'P 1234567 2 3'):
            self.assertIsNone(self.parse(line), line)

    def test_held_keys_outlast_the_repeat_delay(self):
        keys = lua.HeldKeys()
        keys.press('left', 10.0)
        self.assertEqual(keys.held(10.3), ['left'])       # inside the initial repeat delay
        self.assertEqual(keys.held(10.5), [])
        keys.press('left', 10.6)
        keys.press('left', 10.64)                          # repeating now: short window
        self.assertEqual(keys.held(10.7), ['left'])
        self.assertEqual(keys.held(10.9), [])


def write(directory, name, text):
    path = Path(directory) / name
    path.write_text(text)
    return path


@needs_lua
class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sessions = []

    def run_plugin(self, source, frames=3, keys=()):
        path = write(self.tmp.name, 'plugin.lua', source)
        session = Session(path, 32, 16)
        self.sessions.append(session)
        self.addCleanup(session.close)
        blips = []
        now = time.monotonic()
        for index in range(frames):
            blips += session.step(now + index * 0.033, keys=keys if index == 0 else ())
        return session, blips

    def test_input_and_sound_reach_the_plugin_and_back(self):
        session, blips = self.run_plugin(
            'function tick(dt)\n'
            '  gfx.rect(0, 0, 4, 2, input.held("left") and 5 or 6)\n'
            '  if input.held("fire") then sfx.blip(440, 50, "sq", 0.5) end\n'
            'end\n', keys=['left', 'fire'])
        self.assertIsNone(session.failure)
        self.assertEqual(session.surface.pixels[0], 5)
        self.assertIn((440, 50, 'sq', 50), blips)

    def test_plugin_cannot_reach_the_system(self):
        for attack in ('os.execute("true")', 'io.open("/etc/passwd")', 'require("os")', 'load("return 1")()',
                       'dofile("/etc/passwd")', 'debug.sethook()', 'getmetatable("").__index.dump()',
                       'package.loadlib("x","y")', 'collectgarbage("stop")', 'print("x")', 'pcall(error)',
                       'string.dump(function() end)', 'coroutine.wrap(function() end)()'):
            session, _ = self.run_plugin('function tick(dt) %s end' % attack)
            self.assertEqual(session.failure, 'plugin error', attack)

    def test_runaway_loop_is_stopped(self):
        session, _ = self.run_plugin('function tick(dt) while true do end end', frames=1)
        self.assertEqual(session.failure, 'plugin error')

    def test_memory_hog_is_stopped(self):
        session, _ = self.run_plugin('function tick(dt) local s = ("x"):rep(1000000) end', frames=1)
        self.assertEqual(session.failure, 'plugin error')
        session, _ = self.run_plugin('function tick(dt) local s = "x" while true do s = s .. s end end', frames=1)
        self.assertIsNotNone(session.failure)

    def test_drawing_flood_is_stopped(self):
        session, _ = self.run_plugin('function tick(dt) for i = 1, 100000 do gfx.pixel(0, 0, 1) end end', frames=1)
        self.assertEqual(session.failure, 'plugin error')

    def test_bad_values_fail_the_plugin_not_the_host(self):
        for call in ('gfx.pixel("a", 0, 1)', 'gfx.pixel(0/0, 0, 1)', 'gfx.rect(nil, 0, 1, 1, 1)'):
            session, _ = self.run_plugin('function tick(dt) %s end' % call, frames=1)
            self.assertEqual(session.failure, 'plugin error', call)

    def test_syntax_errors_and_bytecode_are_refused(self):
        session, _ = self.run_plugin('this is not lua', frames=1)
        self.assertIsNotNone(session.failure)
        path = Path(self.tmp.name) / 'bytecode.lua'
        path.write_bytes(subprocess.run([shutil.which('luac') or 'luac', '-o', '-', '-'], input=b'function tick() end',
                                        capture_output=True).stdout or b'\x1bLua')
        session = Session(path, 32, 16)
        self.addCleanup(session.close)
        session.step(0.0)
        self.assertIsNotNone(session.failure)

    def test_environment_is_cleared(self):
        # LUA_INIT would run code in the interpreter before the sandbox starts; the host passes -E and no environment.
        marker = Path(self.tmp.name) / 'marker'
        path = write(self.tmp.name, 'plugin.lua', 'function tick(dt) end')
        import os
        os.environ['LUA_INIT'] = 'io.open("%s", "w"):close()' % marker
        try:
            session = Session(path, 32, 16)
            self.addCleanup(session.close)
            session.step(0.0)
        finally:
            del os.environ['LUA_INIT']
        self.assertFalse(marker.exists())
        self.assertIsNone(session.failure)

    def test_a_failed_session_stays_failed_and_quiet(self):
        session, _ = self.run_plugin('function tick(dt) error("boom") end', frames=1)
        self.assertEqual(session.step(1.0), [])
        self.assertEqual(session.failure, 'plugin error')





class BlipTests(unittest.TestCase):
    """The player side and the client side of the arcade sound request."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def player(self, mode='on'):
        player = sound.Player(sound_env(self.tmp.name, mode), device=types.SimpleNamespace())
        player.state.refresh()
        return player

    @staticmethod
    def send(player, message):
        player.handle(json.dumps(message).encode(), time.monotonic())

    def test_samples_are_bounded_clamped_and_never_louder_than_a_cue(self):
        samples = sound.blip_samples(440, 60, 'sq', 100)
        self.assertEqual(len(samples), int(sound.RATE * 0.060))
        self.assertLess(max(abs(v) for v in samples), 32000 * 0.5)
        self.assertEqual(len(sound.blip_samples(5, 99999, 'tri', 5000)), int(sound.RATE * 0.400))
        self.assertGreater(len(sound.blip_samples(20000, 1, 'noise', -5)), 0)
        self.assertEqual(max(abs(v) for v in sound.blip_samples(440, 60, 'sq', 0)), 0)
        for bad in (('440', 60, 'sq', 50), (440, 60, 'saw', 50), (float('nan'), 60, 'sq', 50), (float('inf'), 60, 'sq', 50), (440, None, 'sq', 50),
                    (True, 60, 'sq', 50), (440, 60, ['sq'], 50)):
            self.assertIsNone(sound.blip_samples(*bad), bad)

    def test_the_player_caps_blip_voices_and_drops_rather_than_queues(self):
        player = self.player()
        for _ in range(10):
            self.send(player, dict(blip=[440, 100, 'sq', 80]))
        self.assertEqual(len(player.voices), sound.BLIP_VOICES)
        for _ in range(100):
            player.mix(time.monotonic())
        self.assertEqual(player.voices, [])
        self.send(player, dict(cue='click'))
        self.send(player, dict(blip=[440, 100, 'noise', 80]))
        self.assertEqual(len(player.voices), 2)
        player.mix(time.monotonic())                      # a cue and a blip together mix without trouble
        self.assertEqual([len(voice) for voice in player.voices], [3])   # the short click is done; the blip plays on

    def test_blips_play_only_in_mode_on(self):
        for mode in ('quiet', 'off'):
            player = self.player(mode)
            self.send(player, dict(blip=[440, 100, 'sq', 80]))
            self.assertEqual(player.voices, [], mode)
        player = self.player()
        player.state.muted = True
        self.send(player, dict(blip=[440, 100, 'sq', 80]))
        self.assertEqual(player.voices, [])

    def test_hostile_blip_messages_are_ignored(self):
        player = self.player()
        for blip in ([], [440], [440, 100, 'sq'], [440, 100, 'sq', 50, 1], 'sq', {'a': 1}, [[1], 100, 'sq', 50],
                     ['x', 100, 'sq', 50], [440, 100, 'evil', 50], [None, None, None, None], [1e999, 100, 'sq', 50]):
            self.send(player, dict(blip=blip))
        player.handle(b'\xff\xfe{"blip": [440,', time.monotonic())
        self.assertEqual(player.voices, [])

    def test_the_client_rate_limits_clamps_and_respects_the_mode(self):
        env = sound_env(self.tmp.name)
        client = sound.Client(env)
        quiet = sound.Client(sound_env(self.tmp.name, 'quiet'))
        self.addCleanup(lambda: [c.sock.close() for c in (client, quiet) if c.sock])
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(listener.close)
        listener.bind(client.path)
        listener.setblocking(False)

        def received():
            messages = []
            while True:
                try:
                    messages.append(json.loads(listener.recv(4096)))
                except BlockingIOError:
                    return messages
        self.assertTrue(client.blip(99999, 99999, 'sq', 999))
        self.assertEqual(received(), [dict(blip=[8000, 400, 'sq', 100])])
        for bad in ((440, 50, 'saw', 50), ('440', 50, 'sq', 50), (float('nan'), 50, 'sq', 50), (float('inf'), 50, 'sq', 50)):
            self.assertFalse(client.blip(*bad))
        sent = sum(client.blip(440, 50, 'sq', 50) for _ in range(200))
        self.assertLessEqual(sent, 9)
        self.assertEqual(len(received()), sent)
        self.assertFalse(quiet.blip(440, 50, 'sq', 50))
        self.assertEqual(received(), [])

    def test_a_real_player_process_plays_a_blip(self):
        env = sound_env(self.tmp.name)
        pcm = Path(self.tmp.name) / 'pcm'
        run = lambda *argv: subprocess.run([sys.executable, str(LIBEXEC / 'sound.py'), *argv], env=env,
                                           capture_output=True, text=True, timeout=10)
        try:
            self.assertEqual(run('ensure').returncode, 0)
            self.assertTrue(sound.Client(env).blip(440, 100, 'sq', 100))
            expected = len(sound.blip_samples(440, 100, 'sq', 100)) * 2
            deadline = time.monotonic() + 5
            while (not pcm.exists() or pcm.stat().st_size < expected) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertGreaterEqual(pcm.stat().st_size, expected)
            data = array.array('h')
            data.frombytes(pcm.read_bytes()[:expected])
            self.assertGreater(max(abs(v) for v in data), 1000, 'audible, not silence')
        finally:
            run('stop')


PROBE = ('-- Probe (toy). Test plugin: fills with colour 5, or 6 while the left key is held.\n'
         'function tick(dt) gfx.rect(0, 0, W, H, input.held("left") and 6 or 5) end\n')


@needs_lua


@needs_lua
class ShippedExtensionTests(unittest.TestCase):
    """The fish tank through the real registry and run_plugin path, like any other extension."""

    def test_the_fish_tank_is_sealed_and_listed(self):
        registry = plugin.Registry(str(GAMES))
        self.assertEqual(registry.refused, {})
        tank = registry.plugins['fishtank']
        self.assertEqual((tank.entry, tank.type, tank.min_size), ('fishtank.lua', 'animation', (64, 22)))

    def test_it_runs_draws_and_ends_on_quit(self):
        registry = plugin.Registry(str(GAMES))
        out, rec = Tty(), audio.RecordingAudio()
        script = [[]] * 6 + [['fire']] + [[]] * 30 + [['quit']]
        result = plugin.run_plugin(registry.plugins['fishtank'], capabilities(width=80, height=26), out,
                                   sdk_input.ListSource(script), rec, clock=timeline.ManualClock(), fps=15)
        self.assertEqual(result.reason, 'quit')
        self.assertTrue(any('▀' in part or '█' in part or '▄' in part for part in [out.getvalue()]), 'drew')

    def test_audio_capability_is_enforced_on_the_host(self):
        registry = plugin.Registry(str(GAMES))
        tank = registry.plugins['fishtank']
        quiet = plugin.Plugin(tank.directory, dict(tank.manifest, capabilities=['draw', 'input']))
        rec = audio.RecordingAudio()
        plugin.run_plugin(quiet, capabilities(width=80, height=26), Tty(), sdk_input.ListSource([['fire']] + [[]] * 30),
                          rec, clock=timeline.ManualClock(), fps=15)
        self.assertEqual(rec.heard, [])

    def test_a_crashing_lua_extension_is_a_failed_result_not_an_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / 'boom'
            directory.mkdir()
            (directory / 'boom.lua').write_text('function tick(dt) error("boom") end\n')
            manifest = dict(api='1.5', capabilities=['draw'], entry='boom.lua', entry_sha256='0' * 64, id='boom',
                            name='Boom', schema=plugin.SCHEMA, type='animation', version='1.0.0')
            (directory / 'manifest.json').write_text(json.dumps(manifest))
            plugin.seal_manifest(str(directory))
            plugin.write_index(str(root))
            registry = plugin.Registry(str(root))
            result = plugin.run_plugin(registry.plugins['boom'], capabilities(width=80, height=26), Tty(),
                                       sdk_input.ListSource([[]] * 5), audio.RecordingAudio(),
                                       clock=timeline.ManualClock(), fps=15)
            self.assertEqual(result.reason, 'done')
            self.assertEqual(result.result, {'failed': 'plugin error'})


class ManifestTests(unittest.TestCase):
    def test_manifest_rules_for_lua_entries(self):
        base = dict(api='1.5', capabilities=['draw'], entry='x.lua', entry_sha256='0' * 64, id='xx',
                    name='X', schema=plugin.SCHEMA, type='animation', version='1.0.0')
        self.assertEqual(plugin.check_manifest(base), [])
        self.assertIn('a Lua extension needs SDK API 1.5 or later', plugin.check_manifest(dict(base, api='1.3')))
        self.assertIn('a Lua extension cannot have the window capability',
                      plugin.check_manifest(dict(base, capabilities=['draw', 'window'])))
        self.assertTrue(plugin.check_manifest(dict(base, entry='x.sh')))
        self.assertEqual(plugin.check_manifest(dict(base, entry='x.py', api='1.3')), [])   # Python entries are unchanged


class AudioBlipTests(unittest.TestCase):
    def test_blip_is_refused_for_bad_values_and_muted_audio(self):
        rec = audio.RecordingAudio()
        self.assertTrue(rec.blip(440, 50, 'sq', 0.5))
        for bad in ((float('nan'), 50, 'sq', 0.5), (440, float('inf'), 'sq', 0.5), ('440', 50, 'sq', 0.5),
                    (440, 50, 'saw', 0.5), (True, 50, 'sq', 0.5)):
            self.assertFalse(rec.blip(*bad), bad)
        rec.muted = True
        self.assertFalse(rec.blip(440, 50, 'sq', 0.5))
        self.assertFalse(audio.NullAudio().blip(440, 50, 'sq', 0.5))
        self.assertEqual(len(rec.heard), 1)

    def test_threaded_audio_routes_tones_and_cues_to_their_own_backends(self):
        tones, cues = [], []
        threaded = audio.ThreadedAudio(lambda name, **p: cues.append(name), tone=lambda **p: tones.append(p))
        self.assertTrue(threaded.blip(440, 50, 'sq', 0.5))
        self.assertTrue(threaded.cue('click'))
        deadline = time.monotonic() + 2
        while (not tones or not cues) and time.monotonic() < deadline:
            time.sleep(0.01)
        threaded.close()
        self.assertEqual(tones, [dict(freq=440.0, ms=50.0, wave='sq', volume=0.5)])
        self.assertEqual(cues, ['click'])
        self.assertFalse(audio.ThreadedAudio(lambda *a, **k: None).blip(440, 50, 'sq', 0.5), 'no tone backend, no tone')


if __name__ == '__main__':
    unittest.main()
