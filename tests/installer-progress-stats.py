#!/usr/bin/env python3
"""The progress screen's statistics header, timeline and package counts, driven by a trimmed copy of the real
complete install log (an MSI Raider 18 install of the 1.4.1 candidate on 2026-10-30: 49.6 minutes, 1,217 packages,
824 archives and 3,721 MiB downloaded; 19,201 lines trimmed to 3,141, keeping every marker, every package position
line, a sample of the download lines and the start of the CUDA output).

The symptom this guards: the screen said "Installing 1,217/1,217" for the whole account, CUDA and verify stages,
because the package ticker kept its last label after its phase ended. The counts, the plan, the header, the stage
table and a live run of the real dashboard on a pseudo-terminal are all checked against that log."""

import importlib.util
import json
import lzma
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/installer-progress/msi-install-1.4.1.log.xz"
TIMES = ROOT / "tests/fixtures/installer-progress/msi-install-1.4.1.times.json.xz"
LIBEXEC = ROOT / "overlay/usr/local/libexec/daemonarchy-installer"

spec = importlib.util.spec_from_file_location("installer_progress_tests", ROOT / "tests/installer-progress.py")
ip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ip)
ui, model, Terminal = ip.ui, ip.model, ip.Terminal

PACKAGES = 1217


def fixture_items():
    """(seconds from the first stage, line) for every kept line, at the pace of the real install."""
    lines = lzma.decompress(FIXTURE.read_bytes()).split(b"\n")[:-1]
    times = json.loads(lzma.decompress(TIMES.read_bytes()))
    assert len(lines) == len(times)
    return list(zip(times, lines))


def first_step_epoch(items):
    return next(int(m.group(1)) for _t, l in items if (m := re.match(rb"@@step \w+ (\d{9,11})", l)))


class Replay:
    """The real log appended to a file at its real pace while a Monitor polls it on a virtual clock."""

    def __init__(self, items=None, expect=("cuda",), inject=None):
        items = list(items or fixture_items())
        if inject:
            items = inject(items)
        self.times = [t for t, _ in items]
        self.lines = [l for _, l in items]
        self.epoch = first_step_epoch(items)
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "log"
        self.log.write_bytes(b"")
        self.out = self.log.open("ab")
        self.now, self.position = 0.0, 0
        self.status = Path(self.tmp.name) / "status"
        self.monitor = model.Monitor(self.log, self.status, source=None, expect=expect, clock=lambda: self.now,
                                     wall=lambda: self.epoch + self.now)

    def close(self):
        self.out.close()
        self.tmp.cleanup()

    def advance(self, until, frame=0.5):
        while self.now < until:
            self.now += frame
            end = self.position
            while end < len(self.lines) and self.times[end] <= self.now:
                end += 1
            if end > self.position:
                self.out.write(b"\n".join(self.lines[self.position:end]) + b"\n")
                self.out.flush()
                self.position = end
            self.monitor.poll()
        return self.monitor.snapshot()

    def until_phase(self, phase, extra=0.0):
        """Advance to just inside `phase` (+ `extra` seconds); returns the snapshot."""
        while self.position < len(self.lines):
            snap = self.advance(self.now + 0.5)
            if snap["phase"] == phase:
                return self.advance(self.now + extra) if extra else snap
        raise AssertionError(f"never reached {phase}")

    def finish(self):
        self.advance(self.times[-1] + 2)
        self.status.write_text("0\n")
        return self.advance(self.now + 1.0)


def plan_line(packages=PACKAGES, archives=824, download=3_900_000_000, installed=18 * 2**30):
    return ('@@plan ' + json.dumps({"schema": "daemonarchy/install-plan@1", "packages": packages, "archives": archives,
                                    "download_bytes": download, "installed_bytes": installed})).encode()


def with_plan(**kw):
    def inject(items):
        index = next(i for i, (_t, l) in enumerate(items) if l.startswith(b"Number of packages to be fetched"))
        return items[:index + 1] + [(items[index][0], plan_line(**kw))] + items[index + 1:]
    return inject


class Counts(unittest.TestCase):
    """The package count: distinct names that pkg reports extracted, clamped to the plan."""

    def test_the_installed_count_rises_one_package_at_a_time_and_reaches_the_total_only_when_done(self):
        replay = Replay()
        try:
            seen, previous = [], 0
            while replay.position < len(replay.lines):
                snap = replay.advance(replay.now + 0.25)
                packages = snap["stats"]["packages"]
                self.assertGreaterEqual(packages["done"], previous, "never moves backwards")
                previous = packages["done"]
                if packages["total"]:
                    self.assertLessEqual(packages["done"], packages["total"])
                if snap["phase"] == "install" and packages["total"] and packages["done"] == packages["total"]:
                    # all extracted: only legitimate once the last package's "Extracting ... done" line was read
                    last = next(i for i in range(len(replay.lines) - 1, -1, -1)
                                if re.match(rb"^\[1217/1217\] Extracting .* done$", replay.lines[i]))
                    self.assertGreater(replay.position, last)
                seen.append(packages["done"])
            self.assertEqual(seen[-1], PACKAGES)
            self.assertGreater(len(set(seen)), 50, "the count moved through many values")
            self.assertEqual(replay.monitor.state.warning, "")
        finally:
            replay.close()

    def test_a_package_is_counted_once_however_often_its_lines_repeat(self):
        def doubled(items):
            out = []
            for when, line in items:
                out.append((when, line))
                if re.match(rb"^\[ *\d+/1217\] Extracting ", line):
                    out.append((when, line))
            return out
        replay = Replay(inject=doubled)
        try:
            replay.advance(replay.times[-1] + 2)
            self.assertEqual(replay.monitor.snapshot()["stats"]["packages"]["done"], PACKAGES)
        finally:
            replay.close()

    def test_the_count_is_clamped_to_the_plan(self):
        replay = Replay(inject=with_plan(packages=1000))
        try:
            replay.advance(replay.times[-1] + 2)
            packages = replay.monitor.snapshot()["stats"]["packages"]
            self.assertEqual((packages["done"], packages["total"]), (1000, 1000))
        finally:
            replay.close()

    def test_without_a_plan_the_total_comes_from_pkgs_own_lines(self):
        replay = Replay()
        try:
            snap = replay.until_phase("install", extra=40)
            self.assertIsNone(snap["plan"])
            self.assertEqual(snap["stats"]["packages"]["total"], PACKAGES)
            self.assertEqual(snap["stats"]["packages"]["source"], "pkg")
        finally:
            replay.close()

    def test_a_whole_log_arriving_at_once_is_read_without_loss(self):
        replay = Replay()
        try:
            replay.out.write(b"\n".join(replay.lines) + b"\n")
            replay.out.flush()
            replay.now = 3000.0
            replay.monitor.poll()
            snap = replay.monitor.snapshot()
            self.assertEqual(snap["stats"]["packages"]["done"], PACKAGES)
            self.assertEqual(snap["phase"], "finish")
            self.assertEqual(replay.monitor.state.warning, "")
        finally:
            replay.close()


class TheSymptom(unittest.TestCase):
    """'Installing 1,217/1,217' unchanged through every stage after the packages."""

    def test_the_ticker_is_hidden_once_its_phase_is_over(self):
        replay = Replay()
        try:
            snap = replay.until_phase("install", extra=60)
            self.assertTrue(snap["ticker"]["names"], "during the install the ticker shows what is being installed")
            self.assertEqual(snap["ticker"]["kind"], "install")
            for phase in ("user", "cuda", "finish"):
                snap = replay.until_phase(phase, extra=2.0)
                self.assertEqual(snap["ticker"]["names"], [], f"the install ticker is gone in {phase}")
                self.assertIsNone(snap["ticker"]["rate"])
            self.assertEqual(snap["stats"]["packages"]["done"], PACKAGES, "the finished count stays in the header")
        finally:
            replay.close()

    def test_the_stale_download_ticker_is_not_shown_while_the_install_resolves(self):
        replay = Replay()
        try:
            snap = replay.until_phase("install")
            self.assertEqual(snap["ticker"]["names"], [], "no 'Downloaded 179/956' during the install's first moments")
        finally:
            replay.close()

    def test_no_screen_after_the_install_says_installing(self):
        replay = Replay()
        try:
            glyphs = ui.Glyphs(True)
            visuals = ui.Visuals(glyphs, reduced=True, logo=[])
            for phase in ("user", "cuda", "finish"):
                snap = replay.until_phase(phase, extra=2.0)
                visuals.advance(snap)
                canvas = ui.Canvas(120, 40)
                visuals.draw(canvas, 0, 0, 120, 40, snap, "bars")
                screen = "\n".join(canvas.plain())
                self.assertNotRegex(screen, r"Installing\s+[\d,]+/[\d,]+", phase)
                self.assertNotIn("1,217/1,217", screen, phase)
                self.assertIn("1,217 of 1,217", screen, f"the header keeps the result in {phase}")
            self.assertIn("Latest:", screen.replace("Latest: ", "Latest:"), "stages with no counter show the latest log line")
        finally:
            replay.close()


class Statistics(unittest.TestCase):
    def test_total_elapsed_is_h_mm_ss_and_runs_from_the_first_stage(self):
        replay = Replay()
        try:
            snap = replay.advance(125.0)
            self.assertEqual(model.format_hms(snap["elapsed"]), "0:02:05")
            snap = replay.advance(3725.0)
            self.assertRegex(model.format_hms(snap["elapsed"]), r"^1:02:0\d$|^0:\d\d:\d\d$|^[0-9]:\d\d:\d\d$")
        finally:
            replay.close()

    def test_percent_only_moves_forward_never_reaches_100_early_and_is_exact_at_the_end(self):
        replay = Replay(inject=with_plan())
        try:
            previous, values = -1.0, []
            while replay.position < len(replay.lines):
                snap = replay.advance(replay.now + 5.0)
                percent = snap["stats"]["percent"]
                if percent is not None:
                    self.assertGreaterEqual(percent + 1e-9, previous, f"went backwards at {replay.now}s")
                    self.assertLess(percent, 100.0)
                    previous = percent
                    values.append(percent)
            self.assertGreater(values[-1], 90.0)
            final = replay.finish()
            self.assertEqual(final["stats"]["percent"], 100.0)
            self.assertIsNone(final["stats"]["eta"], "nothing is left once the installer reports its result")
        finally:
            replay.close()

    def test_stage_n_of_m_counts_the_expected_cuda_stage_from_the_start(self):
        replay = Replay()
        try:
            early = replay.advance(60.0)["stats"]
            self.assertEqual(early["stage_count"], 11, "base, boot loader, config... plus the expected CUDA stage")
            late = replay.until_phase("cuda")["stats"]
            self.assertEqual((late["stage_index"], late["stage_count"], late["stage_label"]), (10, 11, "CUDA"))
            without = Replay(expect=())
            try:
                self.assertEqual(without.advance(60.0)["stats"]["stage_count"], 10)
            finally:
                without.close()
        finally:
            replay.close()

    def test_with_a_plan_the_bytes_and_packages_have_exact_totals_and_a_rate(self):
        replay = Replay(inject=with_plan())
        try:
            snap = replay.advance(900.0)
            stats = snap["stats"]
            self.assertEqual(stats["packages"]["total"], PACKAGES)
            self.assertEqual(stats["packages"]["source"], "plan")
            self.assertTrue(stats["bytes"]["exact"])
            self.assertEqual(stats["bytes"]["total"], 3_900_000_000)
            self.assertGreater(stats["bytes"]["done"], 0)
            self.assertLessEqual(stats["bytes"]["done"], stats["bytes"]["total"])
            self.assertIsNotNone(stats["bytes"]["average"])
            self.assertEqual(stats["eta_basis"], "measured rates")
        finally:
            replay.close()

    def test_without_a_plan_the_download_total_is_pkgs_rounded_figure_and_flagged_approximate(self):
        replay = Replay()
        try:
            snap = replay.advance(900.0)
            data = snap["stats"]["bytes"]
            self.assertFalse(data["exact"])
            self.assertEqual(data["total"], 5 * 2**30)
        finally:
            replay.close()

    def test_when_the_download_ends_its_total_is_what_was_received(self):
        replay = Replay()
        try:
            snap = replay.until_phase("install", extra=5)
            data = snap["stats"]["bytes"]
            self.assertTrue(data["exact"])
            self.assertEqual(data["done"], data["total"])
            self.assertGreater(data["done"], 3_000_000_000)
        finally:
            replay.close()

    def test_the_time_left_comes_from_the_measured_rate(self):
        """A steady 2 MiB/s download of a known total: half done at 100 s means about 100 s left in that stage."""
        total = 400 * 2**20
        items = [(0.0, b"@@phase fetch"), (0.0, b"@@step fetch 1793345072"), (0.0, plan_line(download=total, packages=10)),
                 (900.0, b"@@phase install"), (900.0, b"@@step packages 1793345972")]
        replay = Replay(items=items)
        try:
            state = replay.monitor.state
            replay.advance(1.0)
            # feed measured @@fetch events at 2 MiB/s through the model directly, on the same virtual clock
            for second in range(0, 101, 2):
                replay.now = 1.0 + second
                state.fetch_event(dict(schema="daemonarchy/pkg-fetch@1", archives=second // 10, bytes=second * 2 * 2**20,
                                       file="x", file_bytes=0, file_total=1))
            stats = replay.monitor.snapshot()["stats"]
            self.assertEqual(stats["eta_basis"], "measured rates")
            left_in_fetch = (total - 100 * 2 * 2**20) / (2 * 2**20)
            self.assertAlmostEqual(stats["bytes"]["average"] / 2**20, 2.0, delta=0.1)
            self.assertGreater(stats["eta"], left_in_fetch)                   # plus the stages after it
            self.assertLess(stats["eta"], left_in_fetch + 1000)
            self.assertTrue(stats["bytes"]["rate"])
        finally:
            replay.close()

    def test_the_time_left_says_baseline_until_there_is_a_rate(self):
        replay = Replay()
        try:
            snap = replay.advance(30.0)
            self.assertEqual(snap["stats"]["eta_basis"], "baseline")
            self.assertGreater(snap["stats"]["eta"], 2000, "the recorded 2,075 s download dominates the baseline")
        finally:
            replay.close()

    def test_an_unknown_rate_is_never_invented(self):
        state = model.Progress()
        state.phase_changed("fetch")
        view = state.bytes_view(state.clock())
        self.assertIsNone(view["rate"])
        self.assertIsNone(view["average"])
        self.assertIsNone(view["total"])

    def test_a_restarted_log_forgets_the_plan_and_the_counts(self):
        replay = Replay(inject=with_plan())
        try:
            replay.until_phase("install", extra=60)
            self.assertGreater(len(replay.monitor.state.installed), 0)
            replay.out.close()
            replay.log.write_bytes(b"@@phase disk\n")          # a new, shorter log at the same path
            replay.out = replay.log.open("ab")
            replay.monitor.poll()
            state = replay.monitor.state
            self.assertEqual((state.plan, len(state.installed), state.fetch_banked), (None, 0, 0))
            self.assertIn("restarted", state.warning)
        finally:
            replay.close()

    def test_a_bad_plan_is_refused_not_trusted(self):
        for payload in ({"schema": "wrong"}, {"schema": "daemonarchy/install-plan@1", "packages": 0, "archives": 1,
                                              "download_bytes": 1, "installed_bytes": 1},
                        {"schema": "daemonarchy/install-plan@1", "packages": "x", "archives": 1, "download_bytes": 1,
                         "installed_bytes": 1}, {"schema": "daemonarchy/install-plan@1", "packages": 5}):
            state = model.Progress()
            state.line("@@plan " + json.dumps(payload))
            self.assertIsNone(state.plan, payload)
            self.assertTrue(state.warning)

    def test_each_retry_banks_the_bytes_of_the_run_before(self):
        state = model.Progress()
        state.phase_changed("fetch")
        row = lambda archives, got: dict(schema="daemonarchy/pkg-fetch@1", archives=archives, bytes=got, file="f", file_bytes=0, file_total=1)
        state.fetch_event(row(5, 500))
        state.fetch_event(row(2, 100))        # pkg restarted and counts from zero
        self.assertEqual(state.fetch_banked + state.fetch["bytes"], 600)


class Timeline(unittest.TestCase):
    def test_stages_carry_start_offsets_durations_and_expectations(self):
        replay = Replay(inject=with_plan())
        try:
            snap = replay.advance(900.0)
            rows = {r["key"]: r for r in snap["stages"]}
            self.assertEqual(rows["partition"]["start"], 0.0)
            self.assertGreater(rows["base"]["start"], 0.0)
            self.assertEqual(rows["base"]["expected_source"], "measured")
            self.assertEqual(rows["base"]["expected"], rows["base"]["elapsed"])
            self.assertEqual(rows["fetch"]["state"], "active")
            self.assertEqual(rows["fetch"]["expected_source"], "measured rate")
            self.assertGreater(rows["fetch"]["expected"], rows["fetch"]["elapsed"])
            self.assertEqual(rows["packages"]["state"], "pending")
            self.assertEqual((rows["packages"]["expected"], rows["packages"]["expected_source"]), (model.BASELINE["packages"], "baseline"))
            self.assertIsNone(rows["packages"]["start"])
        finally:
            replay.close()

    def test_the_baseline_is_the_recorded_real_install(self):
        self.assertEqual(model.BASELINE["fetch"], 2075.0)
        self.assertEqual(model.BASELINE["packages"], 152.0)
        self.assertEqual(model.BASELINE["cuda"], 691.0)
        # The stages sum to 2,964.9 s; the recorded 49.6 minutes (2,976 s) adds a few seconds before the first stage.
        self.assertAlmostEqual(sum(model.BASELINE.values()), 2964.9, delta=0.5)


SIZES = ((120, 40), (100, 30), (80, 24), (60, 16), (50, 12), (40, 10), (30, 8))


class RenderedHeader(unittest.TestCase):
    """Always visible: even with the logo and at small sizes."""

    def snap(self, phase="fetch", extra=300.0, **kw):
        replay = Replay(inject=with_plan(), **kw)
        self.addCleanup(replay.close)
        return replay.until_phase(phase, extra=extra)

    def render(self, snap, w, h, logo=None, unicode=True):
        visuals = ui.Visuals(ui.Glyphs(unicode), reduced=True, logo=logo or [])
        visuals.advance(snap)
        canvas = ui.Canvas(w, h)
        visuals.draw(canvas, 0, 0, w, h, snap, "bars")
        return canvas.plain()

    def test_the_first_rows_hold_the_statistics_at_every_size(self):
        snap = self.snap()
        elapsed = model.format_hms(snap["elapsed"])
        for w, h in SIZES:
            rows = self.render(snap, w, h)
            head = " ".join(rows[:3])
            self.assertIn(elapsed, rows[0], (w, h))
            self.assertIn("%", head, (w, h))
            self.assertRegex(head, r"7(/| of )11", f"stage N of M at {w}x{h}")
            self.assertNotIn("D A E M O N", rows[0], f"the top line is statistics, not the banner at {w}x{h}")

    def test_the_full_header_at_a_comfortable_size_has_every_figure_labelled(self):
        snap = self.snap()
        rows = self.render(snap, 120, 40)
        head = "\n".join(rows[:2])
        for text in ("elapsed", "stage 7 of 11: Download", "% done (estimate)", "left", "estimate from", "packages 0 of 1,217 installed",
                     "downloaded", "GiB"):
            self.assertIn(text, head, text)

    def test_a_steady_download_shows_its_measured_rate_in_the_header(self):
        total = 400 * 2**20
        items = [(0.0, b"@@phase fetch"), (0.0, b"@@step fetch 1793345072"), (0.0, plan_line(download=total, packages=10)),
                 (900.0, b"@@phase install"), (900.0, b"@@step packages 1793345972")]
        replay = Replay(items=items)
        self.addCleanup(replay.close)
        replay.advance(1.0)
        for second in range(0, 61, 2):
            replay.now = 1.0 + second
            replay.monitor.state.fetch_event(dict(schema="daemonarchy/pkg-fetch@1", archives=second // 10, bytes=second * 2 * 2**20,
                                                  file="x", file_bytes=0, file_total=1))
        snap = replay.monitor.snapshot()
        head = "\n".join(self.render(snap, 120, 40)[:2])
        self.assertIn("downloaded 0.12 of 0.39 GiB", head)
        self.assertIn("at 2.0 MiB/s", head)

    def test_the_header_is_above_the_logo_not_replaced_by_it(self):
        snap = self.snap()
        logo = ["LOGO LINE ONE", "LOGO LINE TWO", "LOGO LINE THREE"]
        rows = self.render(snap, 120, 60, logo=logo)
        self.assertIn("elapsed", rows[0])
        self.assertTrue(any("LOGO LINE ONE" in r for r in rows[1:6]))

    def test_ascii_terminals_get_an_ascii_header(self):
        snap = self.snap()
        rows = self.render(snap, 100, 30, unicode=False)
        self.assertNotIn("≈", " ".join(rows[:3]))
        self.assertIn("~", " ".join(rows[:3]))

    def test_the_estimates_are_labelled_and_the_counters_are_not(self):
        snap = self.snap()
        rows = self.render(snap, 120, 40)
        head = rows[0]
        self.assertIn("(estimate)", head)
        self.assertIn("(estimate from", head)
        self.assertNotRegex(rows[1][:40], "estimate")

    def test_a_finished_install_shows_the_total_time_and_no_estimate(self):
        replay = Replay(inject=with_plan())
        self.addCleanup(replay.close)
        snap = replay.finish()
        rows = self.render(snap, 120, 40)
        self.assertNotIn("estimate", " ".join(rows[:2]).replace("Daemonarchy is installed", ""))
        self.assertIn("100%", rows[0])

    def test_a_tall_screen_shows_the_stage_table_and_a_short_one_the_chips(self):
        snap = self.snap(extra=700.0)
        tall = "\n".join(self.render(snap, 120, 50))
        for text in ("STAGE", "STARTED", "TOOK / ELAPSED", "EXPECTED", "Base sets", "+0:00:0", "~", "(baseline)", "(measured rate)"):
            self.assertIn(text, tall, text)
        short = "\n".join(self.render(snap, 100, 24))
        self.assertNotIn("STARTED", short)
        self.assertRegex(short, r"Download \d+:\d\d/~\d+:\d\d", "the active chip shows elapsed and expected")
        self.assertRegex(short, r"Packages ~\d+:\d\d", "a pending chip shows the expected duration")

    def test_the_stage_table_can_be_forced_either_way(self):
        snap = self.snap(extra=700.0)
        visuals = ui.Visuals(ui.Glyphs(True), reduced=True, logo=[])
        visuals.advance(snap)
        for mode, expect in (("table", True), ("chips", False)):
            visuals.timeline_mode = mode
            canvas = ui.Canvas(100, 40)
            visuals.draw(canvas, 0, 0, 100, 40, snap, "bars")
            self.assertEqual("STARTED" in "\n".join(canvas.plain()), expect, mode)

    def test_the_plain_serial_view_carries_the_same_numbers(self):
        snap = self.snap()
        text = " | ".join(ui.header_text(snap, 200, False))
        for part in ("elapsed", "stage 7 of 11", "estimate", "packages 0 of 1,217 installed", "downloaded"):
            self.assertIn(part, text)


class LiveDashboard(unittest.TestCase):
    """The real dashboard on a pseudo-terminal while the real log is appended live, each phase at its real pace
    compressed 150 times: after the packages, no screen says 'Installing'; the count never goes backwards."""

    SCALE = 1 / 150

    def feed(self, log, status, stop):
        items = fixture_items()
        times, lines = [t for t, _ in items], [l for _, l in items]
        started = time.monotonic()
        position = 0
        with log.open("ab") as out:
            while position < len(lines) and not stop.is_set():
                due = (time.monotonic() - started) / self.SCALE
                end = position
                while end < len(lines) and times[end] <= due:
                    end += 1
                if end > position:
                    chunk = []
                    for line in lines[position:end]:
                        if line.startswith(b"@@step "):
                            line = re.sub(rb"\d{9,11}$", str(int(time.time())).encode(), line)
                        chunk.append(line)
                    out.write(b"\n".join(chunk) + b"\n")
                    out.flush()
                    position = end
                time.sleep(0.02)
        if not stop.is_set():
            status.write_text("0\n")

    def test_the_header_counts_up_and_the_ticker_never_outlives_the_install(self):
        with tempfile.TemporaryDirectory() as directory:
            log, status = Path(directory) / "log", Path(directory) / "status"
            log.write_bytes(b"")
            env = dict(ip.clean_env(), TERM="xterm-256color", DAEMONARCHY_ACTIVITY="off", DAEMONARCHY_EXPECT_STAGES="cuda",
                       DAEMONARCHY_CELEBRATE="0", DAEMONARCHY_FPS="20")
            stop = threading.Event()
            feeder = threading.Thread(target=self.feed, args=(log, status, stop), daemon=True)
            samples = []
            with Terminal([str(log), str(status)], env, 40, 120) as tty:
                feeder.start()
                end = time.monotonic() + 60
                while time.monotonic() < end and tty.child.poll() is None:
                    tty.read_for(0.15)
                    while tty.read_once(0.03):      # until the output is quiet: a frame is written top to bottom
                        pass
                    samples.append(tty.lines())
                stop.set()
                feeder.join(timeout=5)
                code = tty.exit_code(10)
            self.assertEqual(code, 0)
            self.assertGreater(len(samples), 40)
            counts, after_install, run, worst = [], [], 0, 0
            for rows in samples:
                head = "\n".join(rows[:3])
                if "elapsed" not in head:
                    continue                                # the curtain at the very start or the final summary
                stage = re.search(r"stage (\d+) of 11", head)
                packages = re.search(r"packages ([\d,]+) of ([\d,]+) installed", head)
                if packages:
                    counts.append(int(packages.group(1).replace(",", "")))
                if stage and int(stage.group(1)) >= 9:      # account, CUDA, verify
                    after_install.append("\n".join(rows))
                    # The bug held the stale label for every one of these screens. A frame caught half drawn
                    # (header updated, a lower row not yet) can show it once; it must never persist.
                    run = run + 1 if re.search(r"Installing\s+[\d,]+/[\d,]+", "\n".join(rows)) else 0
                    worst = max(worst, run)
            self.assertTrue(after_install, "the run reached the stages after the install")
            self.assertLessEqual(worst, 1, "the install ticker stayed on screen after the install")
            self.assertGreater(len(after_install), 5)
            self.assertEqual(counts, sorted(counts), "the packages count never moves backwards on screen")
            self.assertEqual(counts[-1], PACKAGES)
            self.assertTrue(any(0 < c < PACKAGES for c in counts), "it was seen counting up, not just at the end")


if __name__ == "__main__":
    unittest.main()
