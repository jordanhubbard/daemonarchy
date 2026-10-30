#!/usr/bin/env python3
"""parallel-fetch: plan parsing, batching, bounded concurrency, retries and failures, with a fake pkg."""

import atexit
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "overlay/usr/local/libexec/daemonarchy-installer/parallel-fetch"
loader = importlib.machinery.SourceFileLoader("parallel_fetch", str(TOOL))
spec = importlib.util.spec_from_loader(loader.name, loader)
tool = importlib.util.module_from_spec(spec)
loader.exec_module(tool)

PLAN = """Updating repositories...
New packages to be INSTALLED:
\tbash: 5.3.9 [FreeBSD]
\tfltk: 1.3.11 [Daemonarchy]
\tffmpeg: 9.0.2_3,1 [Daemonarchy-Dependencies]
\tzstd: 1.5.7_2

Installed packages to be UPGRADED:
\tpkg: 2.8.3 -> 2.8.4 [FreeBSD]

Installed packages to be REMOVED:
\told: 1.0

Number of packages to be installed: 4
"""

FAKE = r'''#!/usr/bin/env python3
import os, sys, time
args = sys.argv[1:]
cache = os.environ["FAKE_CACHE"]
if args[:1] == ["rquery"]:
    for line in open(os.environ["FAKE_SIZES"]).read().splitlines():
        print(line)
    sys.exit(0)
assert args[:3] == ["fetch", "-y", "-U"], args
ids = args[3:]
activity = os.path.join(cache, "..", "activity")
def note(kind):
    fd = os.open(activity, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    os.write(fd, f"{time.time_ns()} {kind}\n".encode())
    os.close(fd)
note("start")
status = 0
for i in ids:
    time.sleep(float(os.environ.get("FAKE_DELAY", "0.05")))
    if i in os.environ.get("FAKE_DETERMINISTIC", "").split():
        print(f"pkg: No packages matching '{i}' have been found in the repositories")
        status = 1
        break  # pkg stops at the first failure, leaving the rest of the batch unfetched
    marker = os.path.join(cache, "..", "failed-" + i)
    if i in os.environ.get("FAKE_FAIL_ONCE", "").split() and not os.path.exists(marker):
        open(marker, "w").close()
        print(f"pkg: https://mirror.invalid/All/Hashed/{i}~2$x.pkg: Unknown HTTP error")
        status = 1
        break  # pkg stops at the first failure, leaving the rest of the batch unfetched
    real = os.path.join(cache, f"{i}~2$abc.pkg")
    open(real, "wb").write(b"x" * 1000)
    link = os.path.join(cache, f"{i}.pkg")
    if not os.path.lexists(link):
        os.symlink(os.path.basename(real), link)
note("end")
sys.exit(status)
'''


class Fixture:
    def __init__(self, ids=None, **env):
        self.tmp = tempfile.TemporaryDirectory()
        atexit.register(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.fake = self.root / "fakepkg"
        self.fake.write_text(FAKE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        self.ids = ids or [f"pkg{n}-1.0" for n in range(12)]
        self.plan = self.root / "plan.txt"
        self.plan.write_text("New packages to be INSTALLED:\n" + "".join(f"\t{i.rsplit('-', 1)[0]}: {i.rsplit('-', 1)[1]}\n" for i in self.ids))
        sizes = self.root / "sizes"
        sizes.write_text("".join(f"{i} {(n + 1) * 1000}\n" for n, i in enumerate(self.ids)))
        self.env = dict(os.environ, FAKE_CACHE=str(self.cache), FAKE_SIZES=str(sizes), **env)
        self.trace = self.root / "trace.jsonl"

    def run(self, *extra, workers=4):
        env = dict(self.env, DAEMONARCHY_TRACE_FILE=str(self.trace), DAEMONARCHY_TRACE_START_US="0")
        return subprocess.run([sys.executable, str(TOOL), "--plan", str(self.plan), "--cache", str(self.cache),
                               "--workers", str(workers), "--batch", "2", *extra, "--", str(self.fake)],
                              capture_output=True, text=True, env=env)

    def events(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def peak(self):
        """Most fake pkg processes alive at once, from their start/end lines."""
        path = self.root / "activity"
        if not path.exists():
            return 0
        marks = sorted(line.split() for line in path.read_text().splitlines())
        running = peak = 0
        for _stamp, kind in marks:
            running += 1 if kind == "start" else -1
            peak = max(peak, running)
        return peak


class PlanTests(unittest.TestCase):
    def test_parse_plan_takes_install_and_upgrade_sections_only(self):
        items = tool.parse_plan(PLAN)
        self.assertEqual([i["id"] for i in items], ["bash-5.3.9", "fltk-1.3.11", "ffmpeg-9.0.2_3,1", "zstd-1.5.7_2", "pkg-2.8.4"])

    def test_skip_repo_drops_local_packages(self):
        items = tool.parse_plan(PLAN, {"Daemonarchy"})
        self.assertNotIn("fltk-1.3.11", [i["id"] for i in items])
        self.assertIn("ffmpeg-9.0.2_3,1", [i["id"] for i in items])

    def test_unsafe_names_are_ignored(self):
        self.assertEqual(tool.parse_plan("New packages to be INSTALLED:\n\tevil: 1.0;rm -rf /\n"), [])

    def test_batches_start_big_first_and_keep_big_packages_alone(self):
        items = [dict(id=f"p{n}-1") for n in range(6)]
        sizes = {"p0-1": 100 << 20, "p1-1": 1, "p2-1": 2, "p3-1": 3, "p4-1": 4, "p5-1": 5}
        batches = tool.make_batches(items, sizes, per_batch=2)
        self.assertEqual([i["id"] for i in batches[0]], ["p0-1"])
        self.assertTrue(all(len(b) <= 2 for b in batches))
        self.assertEqual(sorted(i["id"] for b in batches for i in b), sorted(i["id"] for i in items))


class PoolTests(unittest.TestCase):
    def test_fetches_everything_within_the_worker_bound(self):
        f = Fixture(FAKE_DELAY="0.15")
        result = f.run(workers=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all((f.cache / f"{i}.pkg").exists() for i in f.ids))
        self.assertLessEqual(f.peak(), 3)
        self.assertGreaterEqual(f.peak(), 2)
        events = f.events()
        self.assertEqual(sum(e["event"] == "download" for e in events), len(f.ids))
        end = next(e for e in events if e["event"] == "fetch_pool_end")
        self.assertEqual((end["complete"], end["missing"]), (len(f.ids), 0))
        lines = [json.loads(l[7:]) for l in result.stdout.splitlines() if l.startswith("@@fetch ")]
        self.assertEqual(lines[-1]["archives"], len(f.ids))
        self.assertEqual(lines[-1]["schema"], "daemonarchy/pkg-fetch@1")

    def test_transient_failure_is_retried_for_just_that_archive(self):
        f = Fixture(FAKE_FAIL_ONCE="pkg3-1.0 pkg7-1.0")
        result = f.run()
        self.assertEqual(result.returncode, 0, result.stderr)
        events = f.events()
        retries = sorted(e["name"] for e in events if e["event"] == "fetch_retry")
        self.assertEqual(retries, ["pkg3-1.0", "pkg7-1.0"])
        failed = [e for e in events if e["event"] == "fetch_batch" and e["status"] != 0]
        self.assertTrue(failed and all(e["error"] == "http" for e in failed))
        self.assertTrue(all((f.cache / f"{i}.pkg").exists() for i in f.ids))

    def test_deterministic_error_stops_at_once(self):
        f = Fixture(FAKE_DETERMINISTIC="pkg5-1.0")
        result = f.run()
        self.assertEqual(result.returncode, 3)
        self.assertIn("No packages matching", result.stderr)
        self.assertEqual([e for e in f.events() if e["event"] == "fetch_retry"], [])

    def test_a_failing_archive_does_not_hold_up_the_rest(self):
        f = Fixture(FAKE_FAIL_ONCE="pkg0-1.0", FAKE_DELAY="0.05")
        result = f.run(workers=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = f.events()
        end = next(e for e in events if e["event"] == "fetch_pool_end")
        self.assertEqual(end["missing"], 0)
        # Only the archive pkg named is charged an attempt; the rest of its batch is not.
        self.assertEqual([e["name"] for e in events if e["event"] == "fetch_retry"], ["pkg0-1.0"])

    def test_archives_already_cached_are_not_fetched_again(self):
        f = Fixture()
        for i in f.ids:
            real = f.cache / f"{i}~2$abc.pkg"
            real.write_bytes(b"x")
            (f.cache / f"{i}.pkg").symlink_to(real.name)
        result = f.run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(f.peak(), 0)

    def test_empty_plan_is_a_usage_error(self):
        f = Fixture()
        f.plan.write_text("nothing here\n")
        self.assertEqual(f.run().returncode, 2)

    def test_each_repository_has_its_own_connection_cap_and_is_named_in_the_trace(self):
        f = Fixture(FAKE_DELAY="0.1")
        lines = "".join(f"\t{i.rsplit('-', 1)[0]}: {i.rsplit('-', 1)[1]} [{'Slow' if n < 6 else 'Fast'}]\n"
                        for n, i in enumerate(f.ids))
        f.plan.write_text("New packages to be INSTALLED:\n" + lines)
        result = f.run("--repo-workers", "Slow=1", "--repo-workers", "Fast=4", workers=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = f.events()
        caps = {e["repo"]: e["workers"] for e in events if e["event"] == "fetch_repo"}
        self.assertEqual(caps["Slow"], 1)
        self.assertLessEqual(caps["Fast"], 4)
        self.assertEqual({e["repo"] for e in events if e["event"] == "download"}, {"Slow", "Fast"})
        slow = sorted((e["t_us"] - e["dur_us"], e["t_us"]) for e in events
                      if e["event"] == "fetch_batch" and e["repo"] == "Slow")
        self.assertTrue(all(a_end <= b_start + 5000 for (_, a_end), (b_start, _) in zip(slow, slow[1:])),
                        "one-connection repository ran two fetches at once")

    def test_repo_workers_must_name_a_repository_and_a_count(self):
        f = Fixture()
        for bad in ("=3", "Slow=0", "Slow=x", "Slow"):
            self.assertEqual(f.run("--repo-workers", bad).returncode, 2, bad)

    def test_trace_has_no_paths_or_commands(self):
        f = Fixture()
        f.run()
        text = f.trace.read_text()
        self.assertNotIn(str(f.root), text)
        self.assertNotIn("fakepkg", text)


if __name__ == "__main__":
    unittest.main()
