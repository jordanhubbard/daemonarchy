#!/usr/bin/env python3
"""The visual SDK on its own: capabilities, drawing, timelines, input, audio, scenes and the sample host."""

import importlib.machinery
import importlib.util
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "overlay/usr/local/lib/daemonarchy-visual"
sys.path.insert(0, str(LIB))

import daemonarchy_visual as sdk  # noqa: E402
from daemonarchy_visual import audio, caps, effects, input as sdk_input, layout, palette, scene, timeline  # noqa: E402


def load_sample():
    path = ROOT / "sdk/visual/examples/sample_host.py"
    loader = importlib.machinery.SourceFileLoader("sample_host", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Tty(io.StringIO):
    def isatty(self):
        return True


class CapabilityTests(unittest.TestCase):
    def test_vt_console_never_gets_truecolor_or_256(self):
        self.assertEqual(caps.color_depth({"TERM": "xterm-256color", "COLORTERM": "truecolor"}, True), "16")
        self.assertEqual(caps.color_depth({"TERM": "xterm-256color", "COLORTERM": "truecolor"}, False), "truecolor")
        self.assertEqual(caps.color_depth({"TERM": "xterm-256color"}, False), "256")
        self.assertEqual(caps.color_depth({"TERM": "vt100"}, False), "8")
        self.assertEqual(caps.color_depth({"TERM": "xterm", "NO_COLOR": "1"}, False), "none")
        self.assertEqual(caps.color_depth({"TERM": "xterm", "DAEMONARCHY_COLOR": "256"}, True), "16")

    def test_glyphs_follow_locale_and_override(self):
        self.assertTrue(caps.unicode_ok({"TERM": "xterm", "LANG": "en_US.UTF-8"}, False))
        self.assertFalse(caps.unicode_ok({"TERM": "xterm", "LANG": "C"}, False))
        self.assertFalse(caps.unicode_ok({"TERM": "cons25"}, True))
        self.assertTrue(caps.unicode_ok({"TERM": "xterm", "DAEMONARCHY_GLYPHS": "unicode"}, False))

    def test_detect_plain_for_pipes_serial_and_off(self):
        self.assertTrue(sdk.detect({"TERM": "xterm"}, io.StringIO()).plain)
        self.assertEqual(sdk.detect({"TERM": "xterm"}, io.StringIO()).tier, "plain")
        self.assertTrue(sdk.detect({"TERM": "vt100"}, Tty()).plain)
        self.assertTrue(sdk.detect({"TERM": "xterm", "DAEMONARCHY_CHARM": "off"}, Tty()).plain)
        rich = sdk.detect({"TERM": "xterm-256color", "COLORTERM": "truecolor", "LANG": "C.UTF-8",
                           "DAEMONARCHY_REDUCED_MOTION": "1"}, Tty())
        self.assertFalse(rich.plain)
        self.assertEqual((rich.depth, rich.tier, rich.reduced), ("truecolor", "rich", True))

    def test_small_terminal(self):
        self.assertTrue(caps.Capabilities(width=30, height=24).small)
        self.assertTrue(caps.Capabilities(width=80, height=10).small)
        self.assertFalse(caps.Capabilities(width=80, height=24).small)

    def test_api_compatibility(self):
        self.assertTrue(sdk.compatible("1.0"))
        self.assertTrue(sdk.compatible((1, 0)))
        self.assertFalse(sdk.compatible("1.1"))
        self.assertFalse(sdk.compatible("2.0"))
        self.assertFalse(sdk.compatible("x"))


class DrawingTests(unittest.TestCase):
    def test_colors_quantize_to_the_depth(self):
        red = (255, 0, 0)
        self.assertEqual(sdk.Colors("none").sgr((red, None, False)), "\033[0m")
        self.assertIn("38;2;255;0;0", sdk.Colors("truecolor").sgr((red, None, False)))
        self.assertIn("38;5;", sdk.Colors("256").sgr((red, None, True)))
        self.assertEqual(sdk.Colors("16").sgr((red, None, False)), "\033[0;91m")
        self.assertEqual(sdk.Colors("8").sgr((red, (0, 0, 0), False)), "\033[0;31;40m")

    def test_gradient_endpoints(self):
        self.assertEqual(sdk.gradient(palette.LOGO, 0.0), palette.LOGO[0])
        self.assertEqual(sdk.gradient(palette.LOGO, 1.0), palette.LOGO[-1])

    def test_canvas_clips_and_diffs(self):
        c = sdk.Canvas(10, 3)
        c.put(8, 0, "abcdef")
        c.put(-2, 1, "xyz")
        self.assertEqual(c.plain()[0], "        ab")
        self.assertEqual(c.plain()[1], "z")
        d = sdk.Canvas(10, 3)
        d.put(8, 0, "abcdef")
        d.put(-2, 1, "xyz")
        self.assertEqual(d.changes(c, sdk.Colors("none")), [])
        d.put(0, 2, "q")
        out = d.changes(c, sdk.Colors("none"))
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("\033[3;1H"))

    def test_bottom_right_cell_is_never_written(self):
        c = sdk.Canvas(4, 2)
        c.put(0, 1, "wxyz")
        text = "".join(c.changes(None, sdk.Colors("none")))
        self.assertNotIn("z", text)

    def test_box_sprite_bar(self):
        from daemonarchy_visual.glyphs import Glyphs
        c = sdk.Canvas(12, 5)
        c.box(0, 0, 6, 3, Glyphs(False))
        c.sprite(7, 0, ["ab", " c"], style=lambda ch, r, col: (palette.RED, None, False))
        c.bar(0, 4, 8, 0.5, Glyphs(False))
        self.assertEqual(c.plain()[0], "+----+ ab")
        self.assertEqual(c.plain()[1], "|    |  c")
        self.assertEqual(c.plain()[4], "####....")

    def test_screen_clears_on_resize_and_restores(self):
        out = io.StringIO()
        screen = sdk.Screen(out, sdk.Colors("none"))
        screen.enter()
        c = screen.canvas(20, 5)
        screen.present(c)
        first = out.getvalue()
        self.assertIn("\033[2J", first)
        out.truncate(0)
        out.seek(0)
        screen.present(screen.canvas(20, 5))
        self.assertEqual(out.getvalue(), "")
        screen.present(screen.canvas(30, 6))
        self.assertIn("\033[2J", out.getvalue())
        screen.leave()
        self.assertIn("\033[?25h", out.getvalue())

    def test_layout(self):
        r = layout.Rect(0, 0, 80, 24)
        left, right = r.split_h(20)
        self.assertEqual((left.w, right.x, right.w), (20, 20, 60))
        top, bottom = r.split_v(3)
        self.assertEqual((top.h, bottom.y, bottom.h), (3, 3, 21))
        self.assertEqual(r.centered(10, 4), layout.Rect(35, 10, 10, 4))
        self.assertEqual(r.inset(2), layout.Rect(2, 2, 76, 20))


class MotionTests(unittest.TestCase):
    def test_tween_and_easing(self):
        t = sdk.Tween(0, 10, 2.0, "ease_in")
        self.assertEqual(t.value, 0)
        t.advance(1.0)
        self.assertAlmostEqual(t.value, 2.5)
        t.advance(5.0)
        self.assertTrue(t.done)
        self.assertEqual(t.value, 10)

    def test_timeline_fires_in_order_and_survives_a_bad_callback(self):
        hits = []
        tl = sdk.Timeline()
        tl.at(0.5, lambda: hits.append("a")).at(0.2, lambda: 1 / 0).every(0.3, lambda: hits.append("t"))
        tl.advance(0.25)
        tl.advance(0.35)
        tl.advance(0.4)
        self.assertEqual(hits.count("a"), 1)
        self.assertGreaterEqual(hits.count("t"), 2)

    def test_clock_manual(self):
        c = sdk.ManualClock()
        c.sleep(0.5)
        c.sleep(-1)
        self.assertEqual(c.now(), 0.5)

    def test_fireworks_are_seeded_and_fade(self):
        def cells(seed):
            f = sdk.Fireworks(40, 20, seed)
            for _ in range(30):
                f.step(1 / 15)
            return sorted((x, y, ch) for x, y, ch, _c in f.cells())
        self.assertEqual(cells(7), cells(7))
        self.assertNotEqual(cells(7), cells(8))
        f = sdk.Particles(10, 10)
        f.emit(5, 5, 8, life=(0.1, 0.1))
        f.step(1.0)
        self.assertEqual(list(f.cells()), [])

    def test_typed_text(self):
        self.assertEqual(effects.typed("hello", 0.0), "h")
        self.assertEqual(effects.typed("hello", 10.0), "hello")


class InputTests(unittest.TestCase):
    def test_decode_arrow_enter_and_partial_escape(self):
        keys, rest = sdk.decode_keys(b"\x1b[A \r\x1bOC")
        self.assertEqual(keys, ["up", " ", "enter", "right"])
        keys, rest = sdk.decode_keys(b"\x1b")
        self.assertEqual((keys, rest), ([], b"\x1b"))
        keys, rest = sdk.decode_keys(b"\x1b", final=True)
        self.assertEqual(keys, ["esc"])
        keys, _ = sdk.decode_keys(b"\x1b[99;1~x")
        self.assertEqual(keys, ["x"])

    def test_keymap_to_actions(self):
        km = sdk.KeyMap()
        self.assertEqual(km.actions(["left", "a", " ", "p", "q", "z"]), ["left", "left", "fire", "pause", "quit"])
        self.assertTrue(set(km.mapping.values()) <= set(sdk.ACTIONS))
        self.assertEqual(sdk.KeyMap({"x": "fire"}).actions(["x", "a"]), ["fire"])

    def test_list_source_and_fd_source(self):
        import os
        source = sdk_input.ListSource([["left"], "fire"])
        self.assertEqual(source.poll(), ["left"])
        self.assertEqual(source.poll(), ["fire"])
        self.assertEqual(source.poll(), [])
        self.assertTrue(source.eof)
        r, w = os.pipe()
        os.write(w, b"\x1b[Dq")
        fd = sdk_input.FdSource(r)
        self.assertEqual(fd.poll(0.5), ["left", "quit"])
        os.close(w)
        fd.poll(0.1)
        fd.poll(0.1)
        self.assertTrue(fd.eof)
        os.close(r)


class AudioTests(unittest.TestCase):
    def test_cues_are_filtered_and_mutable(self):
        rec = audio.RecordingAudio()
        self.assertTrue(rec.cue("laser"))
        self.assertFalse(rec.cue("not-a-cue"))
        rec.muted = True
        self.assertFalse(rec.cue("hit"))
        self.assertEqual(rec.heard, ["laser"])
        self.assertFalse(sdk.NullAudio().cue("laser"))

    def test_backend_errors_never_escape(self):
        class Bad(audio.Audio):
            def _play(self, name, params):
                raise RuntimeError("device gone")
        self.assertFalse(Bad().cue("blip"))

    def test_threaded_audio_never_blocks_and_drops_when_full(self):
        import threading
        gate = threading.Event()
        played = []

        def slow(name, **params):
            gate.wait(2)
            played.append(name)
        a = sdk.ThreadedAudio(slow, limit=2)
        results = [a.cue("blip") for _ in range(10)]
        self.assertIn(False, results)
        self.assertGreater(a.dropped, 0)
        gate.set()
        a.close()


class Counter(sdk.Scene):
    title = "counter"

    def start(self, ctx):
        self.n, self.seen = 0, []

    def update(self, dt, ctx, actions):
        self.n += 1
        self.seen.extend(actions)
        if "fire" in actions:
            ctx.audio.cue("laser")
        if self.n >= 5:
            self.done, self.result = True, "five"

    def draw(self, canvas, ctx):
        canvas.put(0, 0, f"n={self.n}")

    def plain_lines(self, ctx):
        return ["plain counter"]


class SceneTests(unittest.TestCase):
    def run_scene(self, scene_obj, script=(), **kw):
        out = Tty()
        c = kw.pop("caps", caps.Capabilities(depth="16", width=60, height=20))
        clock = timeline.ManualClock()
        result = sdk.run_scene(scene_obj, c, out, sdk_input.ListSource(script), clock=clock, **kw)
        return result, out.getvalue(), clock

    def test_runs_to_done_and_restores_the_terminal(self):
        s = Counter()
        result, text, _ = self.run_scene(s, [[], [], [], [], [], []])
        self.assertEqual((result.reason, result.result), ("done", "five"))
        self.assertIn("n=1", text)
        self.assertTrue(text.endswith("\033[0m\033[?25h\033[2J\033[H"))

    def test_plain_terminals_get_plain_lines_once(self):
        result, text, _ = self.run_scene(Counter(), caps=caps.Capabilities(plain=True, depth="none"))
        self.assertEqual((result.reason, text), ("plain", "plain counter\n"))

    def test_quit_and_pause(self):
        s = Counter()
        result, _, _ = self.run_scene(s, [[], ["pause"], [], [], ["pause"], [], ["quit"]])
        self.assertEqual(result.reason, "quit")
        self.assertEqual(s.n, 3)  # one before the pause, two after (the resume frame updates)

    def test_actions_reach_the_scene_but_pause_and_mute_do_not(self):
        s = Counter()
        rec = audio.RecordingAudio()
        self.run_scene(s, [["left", "fire"], ["mute"], ["fire"]], audio=rec)
        self.assertEqual(s.seen, ["left", "fire", "fire"])
        self.assertEqual(rec.heard, ["laser"])  # the second fire is muted

    def test_preempt_wins_at_any_frame(self):
        s = Counter()
        flag = []
        result, text, _ = self.run_scene(s, [[]] * 50, preempt=lambda: len(flag) > 0 or flag.append(1) or False)
        self.assertEqual(result.reason, "preempted")
        self.assertLess(s.n, 5)

    def test_resize_reflows_and_small_terminal_shows_a_message(self):
        s = Counter()
        sizes = iter([(60, 20), (60, 20), (20, 8), (20, 8), (60, 20), (60, 20), (60, 20), (60, 20)] * 4)
        result, text, _ = self.run_scene(s, [[]] * 20, size=lambda: next(sizes))
        self.assertIn("Terminal too small", text)
        self.assertEqual(result.reason, "done")

    def test_suspended_scene_neither_updates_nor_draws(self):
        s = Counter()
        result, text, clock = self.run_scene(s, [[]] * 6, suspended=lambda: True, max_frames=0)
        self.assertEqual(s.n, 0)

    def test_a_long_stall_is_clamped(self):
        steps = []

        class Probe(sdk.Scene):
            def update(self, dt, ctx, actions):
                steps.append(dt)
                self.done = len(steps) >= 2

        out = Tty()

        class Jumpy(timeline.ManualClock):
            def now(self):
                self.time += 30.0
                return self.time

        sdk.run_scene(Probe(), caps.Capabilities(depth="none", width=60, height=20), out,
                      sdk_input.ListSource([[]] * 5), clock=Jumpy())
        self.assertTrue(all(dt <= scene.MAX_STEP for dt in steps))


class SampleHostTests(unittest.TestCase):
    def test_sample_host_runs_headless_and_plain(self):
        sample = load_sample()
        out = Tty()
        c = caps.Capabilities(depth="256", width=70, height=22)
        scene_obj = sample.Hello()
        result = sdk.run_scene(scene_obj, c, out, sdk_input.ListSource([["right"], ["fire"], [], [], ["quit"]]),
                               audio.RecordingAudio(), clock=timeline.ManualClock())
        self.assertEqual(result.reason, "quit")
        frame = sdk.Canvas(70, 22)
        scene_obj.draw(frame, scene.Context(c))
        self.assertIn("Daemonarchy visual SDK", "\n".join(frame.plain()))
        plain = io.StringIO()
        sdk.run_scene(sample.Hello(), caps.Capabilities(plain=True, depth="none"), plain, sdk_input.ListSource([]))
        self.assertIn("Run this in a color terminal", plain.getvalue())

    def test_sdk_imports_nothing_from_the_installer(self):
        for path in LIB.rglob("*.py"):
            text = path.read_text()
            for forbidden in ("progress-model", "progress_model", "daemonarchy-installer", "install-integrity", "pkg_target"):
                self.assertNotIn(forbidden, text, f"{path.name} reaches into the installer: {forbidden}")


if __name__ == "__main__":
    unittest.main()
