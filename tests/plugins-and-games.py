#!/usr/bin/env python3
"""The plugin runtime and the four installer games: rules, drawing, trust, isolation and preemption."""

import importlib.machinery
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "overlay/usr/local/lib/daemonarchy-visual"
GAMES = ROOT / "extensions/games"
sys.path.insert(0, str(LIB))

import daemonarchy_visual as sdk  # noqa: E402
from daemonarchy_visual import arcade, audio, caps as sdk_caps, input as sdk_input, plugin, scene, timeline  # noqa: E402

GAME_IDS = ("hordeshot", "shatter", "rockdrift", "wyrm")


def load_game(game_id):
    path = GAMES / game_id / "game.py"
    spec = importlib.util.spec_from_file_location(f"game_{game_id}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Tty(io.StringIO):
    def isatty(self):
        return True


def capabilities(**kw):
    values = dict(depth="256", unicode=True, reduced=False, plain=False, width=80, height=24)
    values.update(kw)
    return sdk_caps.Capabilities(**values)


def run_steps(game, seconds, actions=(), dt=1 / 30):
    for _ in range(int(seconds / dt)):
        game.step(dt, list(actions))


# ---------------------------------------------------------------- the games' rules

class HordeshotRules(unittest.TestCase):
    def setUp(self):
        self.m = load_game("hordeshot")
        self.g = self.m.Game(seed=1)

    def test_a_bullet_kills_the_alien_it_reaches_and_scores_by_row(self):
        g = self.g
        alien = (0, 0)
        g.bullet = [g.alien_x(0) + 1, g.alien_y(0) + 1.3]   # one step up lands inside the alien
        before = len(g.aliens)
        g.step(1 / 30, [])
        self.assertNotIn(alien, g.aliens)
        self.assertEqual((len(g.aliens), g.score, g.bullet), (before - 1, self.m.POINTS[0], None))
        self.assertIn("explode", g.events)

    def test_only_one_shot_at_a_time(self):
        g = self.g
        g.step(1 / 30, ["fire"])
        first = list(g.bullet)
        g.step(1 / 30, ["fire"])
        self.assertLess(g.bullet[1], first[1])       # the same bullet, still travelling
        self.assertEqual(g.events.count("laser"), 0)

    def test_the_horde_reverses_and_descends_at_the_edge(self):
        g = self.g
        g.left = self.m.W - 7 * (self.m.ALIEN_W + self.m.GAP_X) - self.m.ALIEN_W - 1.0   # rightmost alien at the wall
        top = g.top
        g.step_clock = g.step_interval()          # exactly one horde step is due
        g.step(1 / 30, [])
        self.assertEqual(g.direction, -1)
        self.assertEqual(g.top, top + 1)

    def test_a_bomb_costs_a_life_then_grants_a_moment_of_safety(self):
        g = self.g
        g.bombs = [[g.ship_x + 1, self.m.H - 2.2]]
        g.bomb_clock = 99
        g.step(1 / 30, [])
        self.assertEqual((g.lives, g.state), (2, "play"))
        self.assertGreater(g.invulnerable, 1.0)
        g.bombs = [[g.ship_x + 1, self.m.H - 2.2]]
        g.step(1 / 30, [])
        self.assertEqual(g.lives, 2)                  # safe while invulnerable

    def test_losing_every_life_or_being_overrun_ends_the_game_and_fire_restarts(self):
        g = self.g
        g.lives = 1
        g.bombs = [[g.ship_x + 1, self.m.H - 2.2]]
        g.bomb_clock = 99
        g.step(1 / 30, [])
        self.assertEqual(g.state, "over")
        self.assertIn("gameover", g.events)
        g.step(1 / 30, ["fire"])
        self.assertEqual((g.state, g.lives, g.score), ("play", 3, 0))
        h = self.m.Game(seed=2)
        h.top = self.m.H - 3.0
        h.step(1 / 30, [])
        self.assertEqual(h.state, "over")

    def test_clearing_the_wave_starts_a_faster_one(self):
        g = self.g
        interval = g.step_interval()
        g.aliens = set()
        g.step(1 / 30, [])
        self.assertEqual((g.level, len(g.aliens)), (2, self.m.ROWS * self.m.COLS))
        self.assertGreaterEqual(g.score, 100)
        self.assertLess(g.step_interval(), interval)

    def test_same_seed_same_game(self):
        def play(seed):
            g = self.m.Game(seed)
            for i in range(600):
                g.step(1 / 30, ["fire"] if i % 7 == 0 else ["left"] if i % 90 < 45 else ["right"])
            return g.score, g.lives, sorted(g.aliens), [list(b) for b in g.bombs]
        self.assertEqual(play(5), play(5))

    def test_the_cannon_stays_inside_the_field(self):
        g = self.g
        run_steps(g, 3, ["left"])
        self.assertEqual(g.ship_x, 0.0)
        run_steps(g, 4, ["right"])
        self.assertEqual(g.ship_x, self.m.W - 3.0)


class ShatterRules(unittest.TestCase):
    def setUp(self):
        self.m = load_game("shatter")
        self.g = self.m.Game(seed=3)

    def test_the_ball_waits_on_the_paddle_until_fire(self):
        g = self.g
        run_steps(g, 1, ["right"])
        self.assertTrue(g.stuck)
        self.assertAlmostEqual(g.ball[0], g.paddle + self.m.PADDLE_W / 2)
        g.step(1 / 40, ["fire"])
        self.assertFalse(g.stuck)
        self.assertLess(g.velocity[1], 0)

    def test_walls_and_ceiling_reflect(self):
        g = self.g
        g.stuck, g.bricks = False, {(0, 0)}
        g.ball, g.velocity = [0.2, 10.0], [-8.0, 0.0]
        g.step(1 / 20, [])
        self.assertGreater(g.velocity[0], 0)
        g.ball, g.velocity = [20.0, 0.2], [0.0, -8.0]
        g.step(1 / 20, [])
        self.assertGreater(g.velocity[1], 0)

    def test_a_brick_breaks_scores_and_reflects(self):
        g = self.g
        g.stuck = False
        row, col = 2, 3
        g.ball = [col * self.m.BRICK_W + 1.0, self.m.BRICK_TOP + row + 1.2]
        g.velocity = [0.0, -10.0]
        g.step(1 / 40, [])
        self.assertNotIn((row, col), g.bricks)
        self.assertEqual(g.score, self.m.ROW_POINTS[row])
        self.assertGreater(g.velocity[1], 0)

    def test_the_paddle_sends_the_ball_off_at_an_angle_by_where_it_lands(self):
        g = self.g
        g.stuck, g.bricks = False, {(0, 0)}
        g.paddle = 10.0
        g.ball, g.velocity = [g.paddle + self.m.PADDLE_W - 0.5, self.m.H - 2.2], [0.0, 12.0]
        g.step(1 / 40, [])
        self.assertLess(g.velocity[1], 0)
        self.assertGreater(g.velocity[0], 0)         # struck right of centre: goes right

    def test_missing_costs_a_life_and_the_last_ends_the_game(self):
        g = self.g
        for expected in (2, 1):
            g.stuck, g.ball, g.velocity = False, [3.0, self.m.H - 1.2], [0.0, 10.0]
            g.paddle = 30.0
            g.step(1 / 40, [])
            self.assertEqual((g.lives, g.state), (expected, "play"))
        g.stuck, g.ball, g.velocity, g.paddle = False, [3.0, self.m.H - 1.2], [0.0, 10.0], 30.0
        g.step(1 / 40, [])
        self.assertEqual(g.state, "over")

    def test_an_empty_wall_is_a_new_faster_level(self):
        g = self.g
        g.stuck = False
        g.bricks = {(0, 0)}
        g.ball, g.velocity = [1.0, self.m.BRICK_TOP + 0.9], [0.0, -10.0]
        speed = g.speed()
        g.step(1 / 40, [])
        self.assertEqual(g.level, 2)
        self.assertGreater(g.speed(), speed)
        self.assertEqual(len(g.bricks), self.m.BRICK_ROWS * self.m.BRICK_COLS)

    def test_a_fast_ball_cannot_tunnel_through_a_brick(self):
        g = self.g
        g.level = 20
        g.stuck = False
        g.ball, g.velocity = [5.0, self.m.BRICK_TOP + self.m.BRICK_ROWS + 3.0], [0.0, -g.speed()]
        run_steps(g, 0.5, dt=1 / 40)
        self.assertLess(len(g.bricks), self.m.BRICK_ROWS * self.m.BRICK_COLS)


class RockdriftRules(unittest.TestCase):
    def setUp(self):
        self.m = load_game("rockdrift")
        self.g = self.m.Game(seed=4)

    def test_everything_wraps(self):
        g = self.g
        g.ship.update(x=self.m.WU - 0.1, vx=10.0, vy=0.0)
        g.safe = 99
        g.step(0.1, [])
        self.assertLess(g.ship["x"], 2.0)

    def test_thrust_accelerates_along_the_heading_and_turning_rotates_it(self):
        g = self.g
        g.rocks = []
        g.step(1 / 30, ["right"])
        a = g.ship["angle"]
        self.assertGreater(a, -math.pi / 2)
        v0 = math.hypot(g.ship["vx"], g.ship["vy"])
        run_steps(g, 1, ["up"])
        self.assertGreater(math.hypot(g.ship["vx"], g.ship["vy"]), v0 + 3)

    def test_a_shot_splits_a_big_rock_into_two_smaller_and_scores(self):
        g = self.g
        g.rocks = [dict(x=10.0, y=10.0, vx=0.0, vy=0.0, size=3)]
        g.safe = 99
        g.bullets = [dict(x=10.0, y=10.0, vx=0.0, vy=0.0, life=1.0)]
        g.step(1 / 30, [])
        self.assertEqual(sorted(r["size"] for r in g.rocks), [2, 2])
        self.assertEqual(g.score, self.m.POINTS[3])

    def test_the_smallest_rock_just_vanishes_and_the_field_is_replaced(self):
        g = self.g
        g.rocks = [dict(x=10.0, y=10.0, vx=0.0, vy=0.0, size=1)]
        g.safe = 99
        g.bullets = [dict(x=10.0, y=10.0, vx=0.0, vy=0.0, life=1.0)]
        g.step(1 / 30, [])
        self.assertEqual((g.level, len(g.rocks) > 0), (2, True))

    def test_a_collision_costs_a_life_and_respawns_safely(self):
        g = self.g
        g.safe = 0.0
        g.rocks = [dict(x=g.ship["x"], y=g.ship["y"], vx=0.0, vy=0.0, size=2)]
        g.step(1 / 30, [])
        self.assertEqual(g.lives, 2)
        self.assertGreater(g.safe, 1.0)
        g.rocks = [dict(x=g.ship["x"], y=g.ship["y"], vx=0.0, vy=0.0, size=2)]
        g.step(1 / 30, [])
        self.assertEqual(g.lives, 2)

    def test_at_most_four_shots_in_flight(self):
        g = self.g
        g.rocks = []
        for _ in range(10):
            g.step(1 / 30, ["fire"])
        self.assertLessEqual(len(g.bullets), self.m.MAX_BULLETS)

    def test_losing_the_last_life_ends_the_game(self):
        g = self.g
        g.lives, g.safe = 1, 0.0
        g.rocks = [dict(x=g.ship["x"], y=g.ship["y"], vx=0.0, vy=0.0, size=3)]
        g.step(1 / 30, [])
        self.assertEqual(g.state, "over")
        g.step(1 / 30, ["fire"])
        self.assertEqual((g.state, g.lives), ("play", 3))


class WyrmRules(unittest.TestCase):
    def setUp(self):
        self.m = load_game("wyrm")
        self.g = self.m.Game(seed=6)

    def test_it_moves_one_cell_per_interval(self):
        g = self.g
        head = g.snake[0]
        g.step(g.interval() + 0.001, [])
        self.assertEqual(g.snake[0], (head[0] + 1, head[1]))
        self.assertEqual(len(g.snake), 3)

    def test_eating_grows_scores_and_moves_the_food_off_the_snake(self):
        g = self.g
        head = g.snake[0]
        g.food = (head[0] + 1, head[1])
        g.step(g.interval() + 0.001, [])
        self.assertEqual((len(g.snake), g.score), (4, 10))
        self.assertNotIn(g.food, g.snake)
        self.assertIn("pickup", g.events)

    def test_it_cannot_reverse_into_its_neck_even_with_two_quick_keys(self):
        g = self.g
        g.step(0.001, ["up", "left"])
        g.step(g.interval(), [])
        self.assertEqual(g.heading, "up")
        self.assertEqual(g.state, "play")

    def test_walls_and_its_own_body_end_the_game(self):
        g = self.g
        for _ in range(40):
            g.step(g.interval() + 0.001, [])
        self.assertEqual(g.state, "over")
        h = self.m.Game(seed=7)
        h.snake = [(5, 5), (5, 6), (6, 6), (6, 5), (6, 4), (5, 4), (4, 4)]
        h.heading, h.food = "up", (0, 0)
        h.step(h.interval() + 0.001, ["right"])      # into its own coil
        self.assertEqual(h.state, "over")

    def test_chasing_its_own_tail_is_allowed(self):
        h = self.m.Game(seed=8)
        h.snake = [(5, 5), (5, 6), (4, 6), (4, 5)]
        h.heading, h.food = "left", (0, 0)
        h.step(h.interval() + 0.001, ["left"])       # the tail cell moves away this tick
        self.assertEqual(h.state, "play")

    def test_it_speeds_up_as_it_grows_and_restarts_on_fire(self):
        g = self.g
        slow = g.interval()
        g.snake = g.snake + [(0, i) for i in range(10)]
        self.assertLess(g.interval(), slow)
        g.state = "over"
        g.step(0.01, ["fire"])
        self.assertEqual((g.state, len(g.snake)), ("play", 3))


# ---------------------------------------------------------------- the games as scenes

class GameScenes(unittest.TestCase):
    def draw(self, game_id, **kw):
        module = load_game(game_id)
        s = module.create(sdk.API_VERSION)
        c = capabilities(**kw)
        ctx = scene.Context(c, audio.RecordingAudio())
        s.start(ctx)
        for _ in range(20):
            s.update(1 / 15, ctx, ["fire", "left"])
        canvas = sdk.Canvas(c.width, c.height)
        s.draw(canvas, ctx)
        return canvas, ctx

    def test_every_game_draws_at_every_size_and_glyph_mode(self):
        for game_id in GAME_IDS:
            need = load_game(game_id).create(sdk.API_VERSION).min_size
            for kw in (dict(), dict(unicode=False), dict(reduced=True), dict(width=120, height=40),
                       dict(width=need[0], height=need[1], depth="16", unicode=False),
                       dict(width=need[0], height=need[1])):
                with self.subTest(game=game_id, **kw):
                    canvas, _ = self.draw(game_id, **kw)
                    text = "\n".join(canvas.plain())
                    self.assertIn(load_game(game_id).create(sdk.API_VERSION).title.upper(), text)

    def test_below_its_minimum_size_a_game_says_so_and_does_not_run(self):
        for game_id in GAME_IDS:
            s = load_game(game_id).create(sdk.API_VERSION)
            need = s.min_size
            for width, height in ((need[0] - 1, 30), (120, need[1] - 1)):
                out = Tty()
                sdk.run_scene(s, capabilities(width=width, height=height), out, sdk_input.ListSource([[]] * 4),
                              clock=timeline.ManualClock())
                self.assertIn(f"need {need[0]}x{need[1]}", out.getvalue(), (game_id, width, height))

    def test_ascii_mode_draws_only_ascii_in_the_playfield_glyphs(self):
        for game_id in GAME_IDS:
            canvas, _ = self.draw(game_id, unicode=False)
            text = "\n".join(canvas.plain())
            self.assertTrue(text.isascii(), f"{game_id} drew non-ASCII in ASCII mode")

    def test_firing_requests_a_laser_cue_and_a_muted_host_hears_nothing(self):
        for game_id in ("hordeshot", "rockdrift"):
            m = load_game(game_id)
            s = m.create(sdk.API_VERSION)
            rec = audio.RecordingAudio()
            ctx = scene.Context(capabilities(), rec)
            s.start(ctx)
            s.update(0.1, ctx, ["fire"])
            self.assertIn("laser", rec.heard)
            rec2 = audio.RecordingAudio()
            rec2.muted = True
            ctx2 = scene.Context(capabilities(), rec2)
            s.update(0.1, ctx2, ["fire"])
            self.assertEqual(rec2.heard, [])

    def test_every_game_runs_under_the_host_loop_and_quits_on_request(self):
        for game_id in GAME_IDS:
            out = Tty()
            result = sdk.run_scene(load_game(game_id).create(sdk.API_VERSION), capabilities(), out,
                                   sdk_input.ListSource([["left"], ["fire"], ["right"]] * 5 + [["quit"]]),
                                   clock=timeline.ManualClock(), fps=20)
            self.assertEqual(result.reason, "quit", game_id)
            self.assertTrue(out.getvalue().endswith("\033[?25h\033[2J\033[H"))

    def test_plain_terminals_get_a_line_not_a_screen(self):
        for game_id in GAME_IDS:
            out = io.StringIO()
            sdk.run_scene(load_game(game_id).create(sdk.API_VERSION), capabilities(plain=True, depth="none"), out,
                          sdk_input.ListSource([]))
            self.assertIn("needs a color terminal", out.getvalue())
            self.assertNotIn("\033", out.getvalue())

    def test_a_tiny_terminal_gets_a_message_and_the_game_does_not_advance(self):
        m = load_game("wyrm")
        s = m.create(sdk.API_VERSION)
        out = Tty()
        sdk.run_scene(s, capabilities(width=30, height=10), out, sdk_input.ListSource([[]] * 6),
                      clock=timeline.ManualClock())
        self.assertIn("Terminal too small", out.getvalue())
        self.assertEqual(len(s.game.snake), 3)
        self.assertEqual(s.game.clock, 0.0)

    def test_all_four_are_distinct_original_games_with_sealed_manifests(self):
        registry = plugin.Registry(str(GAMES))
        self.assertEqual(registry.refused, {})
        games = registry.list("game")      # other extension types (the Lua fish tank) live beside the games
        self.assertEqual(sorted(p.id for p in games), sorted(GAME_IDS))
        self.assertEqual(len({p.name for p in games}), 4)
        for p in games:
            self.assertEqual(p.entry, "game.py")
            self.assertEqual(set(p.capabilities), {"draw", "input", "audio"})
        self.assertEqual(subprocess.run([sys.executable, "-I", str(ROOT / "scripts/seal-games.py"), "--check"],
                                        capture_output=True, text=True).returncode, 0)


# ---------------------------------------------------------------- trust: the registry

def make_plugin(root, pid, source, caps=("draw", "input", "audio"), limits=None, api="1.2", index=True):
    directory = Path(root) / pid
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "game.py").write_text(source)
    manifest = dict(schema=plugin.SCHEMA, id=pid, name=pid.title(), version="1.0.0", type="game", api=api,
                    entry="game.py", entry_sha256="0" * 64, capabilities=list(caps), limits=limits or {})
    (directory / "manifest.json").write_text(json.dumps(manifest))
    plugin.seal_manifest(str(directory))
    if index:
        plugin.write_index(str(root))
    return directory


TINY = '''
from daemonarchy_visual import Scene

class S(Scene):
    title = "tiny"
    def start(self, ctx):
        self.n, self.seen = 0, []
    def update(self, dt, ctx, actions):
        self.n += 1
        self.seen += actions
        ctx.audio.cue("blip")
        if self.n >= 6:
            self.done, self.result = True, "done"
    def draw(self, canvas, ctx):
        canvas.put(0, 0, "n=%d seen=%s" % (self.n, ",".join(self.seen)))

def create(api):
    return S()
'''


class RegistryTrust(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_sealed_listed_plugin_loads(self):
        make_plugin(self.root, "tiny", TINY)
        registry = plugin.Registry(str(self.root))
        self.assertEqual(list(registry.plugins), ["tiny"])
        self.assertEqual(registry.refused, {})
        self.assertEqual(registry.plugins["tiny"].limits["fps"], 15)

    def test_everything_unlisted_or_altered_is_refused_with_a_reason(self):
        make_plugin(self.root, "good", TINY)
        d = make_plugin(self.root, "edited", TINY)
        (d / "game.py").write_text(TINY + "\n# tampered\n")
        d2 = make_plugin(self.root, "remanifested", TINY)
        manifest = json.loads((d2 / "manifest.json").read_text())
        manifest["capabilities"] = ["draw", "input", "audio"]
        manifest["name"] = "Other"
        (d2 / "manifest.json").write_text(json.dumps(manifest))
        make_plugin(self.root, "unlisted", TINY, index=False)
        registry = plugin.Registry(str(self.root))
        self.assertEqual(list(registry.plugins), ["good"])
        self.assertIn("entry file does not match", registry.refused["edited"])
        self.assertIn("manifest does not match the index", registry.refused["remanifested"])
        self.assertIn("not listed in the index", registry.refused["unlisted"])

    def test_bad_manifests_are_refused(self):
        cases = {
            "nodraw": dict(caps=("input",)),
            "badcap": dict(caps=("draw", "network")),
            "future": dict(api="2.0"),
            "toofast": dict(limits={"fps": 500}),
            "tinymem": dict(limits={"memory_mb": 1}),
            "unknownlimit": dict(limits={"root": 1}),
        }
        for name, kw in cases.items():
            make_plugin(self.root, name, TINY, **kw)
        registry = plugin.Registry(str(self.root))
        self.assertEqual(registry.plugins, {})
        self.assertEqual(sorted(registry.refused), sorted(cases))

    def test_the_directory_name_must_match_the_id_and_links_are_refused(self):
        d = make_plugin(self.root, "real", TINY)
        shutil.copytree(d, self.root / "alias")
        plugin.write_index(str(self.root))
        os.symlink(d, self.root / "linked")
        plugin.write_index(str(self.root))
        registry = plugin.Registry(str(self.root))
        self.assertEqual(list(registry.plugins), ["real"])
        self.assertIn("id does not match its directory", registry.refused["alias"])
        self.assertIn("not a plain directory", registry.refused["linked"])
        os.symlink(d / "game.py", self.root / "real" / "alt.py")
        d3 = make_plugin(self.root, "sym", TINY)
        os.remove(d3 / "game.py")
        os.symlink(d / "game.py", d3 / "game.py")
        self.assertIn("sym", plugin.Registry(str(self.root)).refused)

    def test_a_missing_or_wrong_index_trusts_nothing(self):
        make_plugin(self.root, "tiny", TINY, index=False)
        self.assertEqual(plugin.Registry(str(self.root)).plugins, {})
        (self.root / "index.json").write_text('{"schema": "x", "plugins": {}}')
        registry = plugin.Registry(str(self.root))
        self.assertEqual(registry.plugins, {})
        self.assertIn("index.json", registry.refused)

    def test_an_entry_name_cannot_escape_its_directory(self):
        d = make_plugin(self.root, "esc", TINY)
        manifest = json.loads((d / "manifest.json").read_text())
        manifest["entry"] = "../esc/game.py"
        (d / "manifest.json").write_text(json.dumps(manifest))
        plugin.write_index(str(self.root))
        self.assertIn("bad entry name", plugin.Registry(str(self.root)).refused["esc"])


# ---------------------------------------------------------------- isolation: the real child process

def run(root, pid, script=(), **kw):
    registry = plugin.Registry(str(root))
    p = registry.plugins[pid]
    out = Tty()
    rec = kw.pop("audio", audio.RecordingAudio())
    result = plugin.run_plugin(p, capabilities(), out, sdk_input.ListSource(script), rec, **kw)
    return result, out.getvalue(), rec


class PluginProcess(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_frames_actions_and_cues_cross_the_process_boundary(self):
        make_plugin(self.root, "tiny", TINY)
        result, text, rec = run(self.root, "tiny", [["left"], ["fire"], [], [], [], [], [], []])
        self.assertEqual((result.reason, result.result), ("done", "done"))
        self.assertIn("seen=left,fire", text.replace("\033[0m", ""))
        self.assertIn("blip", rec.heard)

    def test_without_the_input_capability_no_actions_arrive(self):
        make_plugin(self.root, "tiny", TINY, caps=("draw", "audio"))
        _, text, _ = run(self.root, "tiny", [["left"], ["fire"], [], [], [], [], []])
        self.assertNotIn("seen=left", text)
        self.assertIn("seen=", text)

    def test_without_the_audio_capability_cues_are_dropped(self):
        make_plugin(self.root, "tiny", TINY, caps=("draw", "input"))
        _, _, rec = run(self.root, "tiny", [[]] * 8)
        self.assertEqual(rec.heard, [])

    def test_a_crashing_plugin_ends_as_a_failed_result_and_the_host_survives(self):
        make_plugin(self.root, "boom", TINY.replace("self.n += 1", "raise RuntimeError('boom')"))
        result, text, _ = run(self.root, "boom", [[]] * 5)
        self.assertEqual(result.reason, "done")
        self.assertEqual(result.result, {"failed": "plugin raised RuntimeError"})
        self.assertTrue(text.endswith("\033[?25h\033[2J\033[H"))

    def test_a_plugin_that_cannot_even_import_fails_cleanly(self):
        make_plugin(self.root, "broken", "import no_such_module\n")
        result, _, _ = run(self.root, "broken", [[]] * 3)
        self.assertEqual(result.result, {"failed": "plugin exited"})

    def test_a_hung_plugin_is_killed_as_too_slow(self):
        make_plugin(self.root, "hang", TINY.replace("self.n += 1", "import time; time.sleep(30)"),
                    limits={"frame_ms": 20})
        started = time.monotonic()
        result, _, _ = run(self.root, "hang", [[]] * 40)
        self.assertEqual(result.result, {"failed": "too slow"})
        self.assertLess(time.monotonic() - started, 10)

    def test_a_memory_hog_hits_its_limit_instead_of_the_machine(self):
        make_plugin(self.root, "hog", TINY.replace("self.n += 1", "self.big = bytearray(900 * 1024 * 1024)"))
        result, _, _ = run(self.root, "hog", [[]] * 5)
        self.assertEqual(result.result, {"failed": "plugin raised MemoryError"})

    def test_a_plugin_cannot_corrupt_the_protocol_by_printing(self):
        make_plugin(self.root, "chatty", TINY.replace("self.n += 1", "self.n += 1; print('}{ not json'); import sys; sys.stderr.write('x')"))
        result, _, _ = run(self.root, "chatty", [[]] * 8)
        self.assertEqual(result.result, "done")

    def test_a_plugin_cannot_write_data(self):
        target = self.root / "should-not-hold-data"
        make_plugin(self.root, "writer", TINY.replace(
            "self.n += 1", "self.n += 1; f = open(%r, 'w'); f.write('x'); f.flush()" % str(target)))
        result, _, _ = run(self.root, "writer", [[]] * 8)
        self.assertEqual(result.result, {"failed": "plugin raised OSError"})
        self.assertEqual(target.stat().st_size if target.exists() else 0, 0)   # the file size limit is zero

    def test_a_plugin_cannot_start_processes(self):
        make_plugin(self.root, "forker", TINY.replace("self.n += 1", "import os; os.fork()"))
        result, _, _ = run(self.root, "forker", [[]] * 8)
        self.assertIsInstance(result.result, dict)
        self.assertIn("failed", result.result)

    def test_preemption_kills_the_process_at_once(self):
        make_plugin(self.root, "tiny", TINY.replace("self.n >= 6", "self.n >= 100000"))
        registry = plugin.Registry(str(self.root))
        remote = plugin.RemoteScene(registry.plugins["tiny"])
        flags = []

        def preempt():
            flags.append(1)
            return len(flags) > 4
        out = Tty()
        started = time.monotonic()
        result = sdk.run_scene(remote, capabilities(), out, sdk_input.NoInput(), audio.RecordingAudio(),
                               fps=30, preempt=preempt)
        self.assertEqual(result.reason, "preempted")
        self.assertLess(time.monotonic() - started, 3)
        remote.stop()
        self.assertIsNone(remote.proc)

    def test_a_suspended_plugin_costs_nothing_and_resumes(self):
        make_plugin(self.root, "tiny", TINY)
        suspended = [True] * 3 + [False] * 100
        result, text, _ = run(self.root, "tiny", [[]] * 20, suspended=lambda: suspended.pop(0))
        self.assertEqual(result.result, "done")

    def test_the_child_runs_isolated_and_in_a_neutral_directory(self):
        make_plugin(self.root, "where", TINY.replace("self.n += 1", "import os, sys; self.cwd = os.getcwd(); self.iso = sys.flags.isolated; self.n += 1")
                    .replace('"n=%d seen=%s" % (self.n, ",".join(self.seen))', '"cwd=%s iso=%s" % (self.cwd, self.iso)'))
        _, text, _ = run(self.root, "where", [[]] * 8)
        plain = text.replace("\033[0m", "")
        self.assertIn("cwd=/", plain)
        self.assertIn("iso=1", plain)


class FrameValidation(unittest.TestCase):
    def ctx(self):
        return scene.Context(capabilities())

    def test_well_formed_frames_decode(self):
        reply = dict(f=[[["ab", 0], ["c", 1]]], s=[[[1, 2, 3], None, True], [None, None, False]])
        decoded = plugin.RemoteScene.decode(reply, self.ctx())
        self.assertEqual(decoded[0][0], (0, "ab", ((1, 2, 3), None, True)))
        self.assertEqual(decoded[0][1][0], 2)

    def test_malformed_frames_are_rejected(self):
        bad = [
            dict(f=[[["x", 5]]], s=[[None, None, False]]),                          # style index out of range
            dict(f=[[["x" * 500, 0]]], s=[[None, None, False]]),                    # row too wide
            dict(f=[[["x", 0]]] * 200, s=[[None, None, False]]),                    # too many rows
            dict(f=[[["x", 0]]], s=[[[999, 0, 0], None, False]]),                   # color out of range
            dict(f=[[[1, 0]]], s=[[None, None, False]]),                            # run text is not a string
            dict(f=[[["x", "0"]]], s=[[None, None, False]]),                        # style is not an int
            dict(s=[]),                                                             # no frame
        ]
        for reply in bad:
            with self.subTest(reply=str(reply)[:50]), self.assertRaises((ValueError, TypeError, KeyError, IndexError)):
                plugin.RemoteScene.decode(reply, self.ctx())

    def test_the_real_games_run_in_their_own_processes(self):
        registry = plugin.Registry(str(GAMES))
        for game_id in GAME_IDS:
            p = registry.plugins[game_id]
            out = Tty()
            rec = audio.RecordingAudio()
            result = plugin.run_plugin(p, capabilities(), out, sdk_input.ListSource(
                [["left"], ["fire"], ["right"], ["fire"], ["up"]] * 3 + [["quit"]]), rec)
            self.assertEqual(result.reason, "quit", (game_id, result))
            self.assertNotIn("failed", str(result.result), game_id)
            self.assertGreater(len(out.getvalue()), 500, game_id)


if __name__ == "__main__":
    unittest.main()
