#!/usr/bin/env python3
"""Native plan evidence parsing, imported-identity and process refusal controls."""

import copy
from contextlib import closing
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native-package-plan.py"
spec = importlib.util.spec_from_file_location("native_package_plan", SCRIPT)
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


def summary(entries, count=None, checked=0):
    count = len(entries) if count is None else count
    return (f"The following {count} package(s) will be affected (of {checked} checked):\n\n"
            "New packages to be INSTALLED:\n" + "\n".join("\t" + line for line in entries) +
            f"\n\nNumber of packages to be installed: {count}\n\nThe process will require 1 MiB more space.\n")


class NativePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected = {"desktop": dict(version="1.0,1", repository="Capture"),
                         "library": dict(version="2.0_3", repository="Capture")}
        self.output = summary(["desktop: 1.0,1", "library: 2.0_3"])

    def test_complete_exact_native_plan(self):
        self.assertEqual(plan.parse_plan(self.output, self.expected, {"Capture"}), self.expected)

    def test_missing_or_empty_evidence_refuses(self):
        for output in ("", "The most recent versions of packages are already installed\n",
                       "Number of packages to be installed: 2\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                plan.parse_plan(output, self.expected, {"Capture"})

    def test_missing_extra_and_changed_packages_refuse(self):
        for entries in (["desktop: 1.0,1"], ["desktop: 1.0,1", "library: 2.0_4"],
                        ["desktop: 1.0,1", "unexpected: 2.0_3"],
                        ["desktop: 1.0,1", "library: 2.0_3", "extra: 1"]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                plan.parse_plan(summary(entries), self.expected, {"Capture"})

    def test_duplicate_and_malformed_entries_refuse(self):
        for entries in (["desktop: 1.0,1", "desktop: 1.0,1"], ["desktop: 1.0,1", "bad line"],
                        ["desktop: 1.0,1", "library: 2.0_3 unparsed"]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                plan.parse_plan(summary(entries), self.expected, {"Capture"})

    def test_counts_and_preexisting_database_refuse(self):
        for output in (summary(["desktop: 1.0,1", "library: 2.0_3"], count=3),
                       self.output.replace("of 0 checked", "of 1 checked"),
                       self.output.replace("installed: 2", "installed: 3")):
            with self.subTest(output=output), self.assertRaises(ValueError):
                plan.parse_plan(output, self.expected, {"Capture"})

    def test_destructive_or_repeated_action_sections_refuse(self):
        for tail in ("Installed packages to be REMOVED:\n\tother: 1\n",
                     "Installed packages to be UPGRADED:\n\tother: 1 -> 2\n",
                     "New packages to be INSTALLED:\n\tother: 1\n"):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                plan.parse_plan(self.output + tail, self.expected, {"Capture"})

    def test_multiple_repositories_require_exact_native_attribution(self):
        with self.assertRaisesRegex(ValueError, "ambiguous repository"):
            plan.parse_plan(self.output, self.expected, {"Capture", "Official"})
        expected = copy.deepcopy(self.expected)
        expected["library"]["repository"] = "Official"
        output = summary(["desktop: 1.0,1 [Capture]", "library: 2.0_3 [Official]"])
        self.assertEqual(plan.parse_plan(output, expected, {"Capture", "Official"}), expected)
        with self.assertRaisesRegex(ValueError, "differs from graph"):
            plan.parse_plan(output, self.expected, {"Capture", "Official"})

    def database(self):
        path = self.root / "repo.sqlite"
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("CREATE TABLE packages (id INTEGER, name TEXT, version TEXT, origin TEXT, arch TEXT, cksum TEXT, path TEXT, pkgsize INTEGER, flatsize INTEGER)")
            connection.execute("CREATE TABLE deps (package_id INTEGER, name TEXT, origin TEXT, version TEXT)")
            connection.execute("INSERT INTO packages VALUES (1,'desktop','1','x11-wm/desktop','FreeBSD:16:amd64','2$encoded','All/desktop-1.pkg',10,100)")
            connection.execute("INSERT INTO deps VALUES (1,'library','devel/library','2')")
        expected = {"desktop": dict(version="1", origin="x11-wm/desktop", abi="FreeBSD:16:amd64",
                                    archive_checksum={"value": "2$encoded"}, archive_path="All/desktop-1.pkg",
                                    download_bytes=10, installed_bytes=100,
                                    dependencies={"library": dict(origin="devel/library", version="2")})}
        return path, expected

    def test_imported_metadata_and_dependencies_match(self):
        database, expected = self.database()
        original = database.read_bytes()
        plan.imported_metadata(database, expected)
        self.assertEqual(database.read_bytes(), original)

    def test_every_imported_identity_field_is_checked(self):
        database, expected = self.database()
        for field in ("version", "origin", "abi", "archive_path", "download_bytes", "installed_bytes"):
            with self.subTest(field=field):
                bad = copy.deepcopy(expected)
                bad["desktop"][field] = "changed"
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    plan.imported_metadata(database, bad)
        bad = copy.deepcopy(expected)
        bad["desktop"]["archive_checksum"]["value"] = "other"
        with self.assertRaisesRegex(ValueError, "identity differs"):
            plan.imported_metadata(database, bad)

    def test_missing_duplicate_and_changed_native_dependencies_refuse(self):
        database, expected = self.database()
        bad = copy.deepcopy(expected)
        bad["desktop"]["dependencies"]["library"]["version"] = "3"
        with self.assertRaisesRegex(ValueError, "dependencies differ"):
            plan.imported_metadata(database, bad)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("INSERT INTO deps VALUES (1,'library','devel/library','2')")
        with self.assertRaisesRegex(ValueError, "dependencies differ"):
            plan.imported_metadata(database, expected)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("DELETE FROM packages")
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            plan.imported_metadata(database, expected)

    def test_installed_packages_after_dry_run_refuse(self):
        database, _ = self.database()
        with self.assertRaisesRegex(ValueError, "installed package database"):
            plan.empty_database(database)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("DELETE FROM packages")
        plan.empty_database(database)

    def test_nonzero_exit_preserves_partial_evidence(self):
        with self.assertRaisesRegex(ValueError, "exit 3"):
            plan.run_step([sys.executable], ["-c", "print('partial plan'); raise SystemExit(3)"], self.root, "refusal")
        self.assertEqual((self.root / "refusal.stdout").read_text(), "partial plan\n")

    def test_stderr_refuses_even_when_child_exits_zero(self):
        with self.assertRaisesRegex(ValueError, "exit 0"):
            plan.run_step([sys.executable], ["-c", "import sys; print('diagnostic',file=sys.stderr)"], self.root, "diagnostic")

    def test_hung_child_has_internal_deadline_and_retains_output(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            plan.run_step([sys.executable], ["-c", "import time; print('before hang',flush=True); time.sleep(60)"], self.root, "hung", timeout=0.3)
        self.assertEqual((self.root / "hung.stdout").read_text(), "before hang\n")

    def test_existing_command_logs_refuse(self):
        (self.root / "occupied.stdout").write_text("retained")
        with self.assertRaises(FileExistsError):
            plan.run_step([sys.executable], ["-c", "print('overwrite')"], self.root, "occupied")
        self.assertEqual((self.root / "occupied.stdout").read_text(), "retained")

    def test_termination_reaps_owned_child_and_preserves_output(self):
        code = ("import importlib.util,sys; from pathlib import Path; "
                f"s=importlib.util.spec_from_file_location('plan',{str(SCRIPT)!r}); "
                "p=importlib.util.module_from_spec(s); s.loader.exec_module(p); p.install_signal_handlers(); "
                f"p.run_step([sys.executable],['-c',\"import os,time; print(os.getpid(),flush=True); time.sleep(60)\"],Path({str(self.root)!r}),'signal')")
        process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            output = self.root / "signal.stdout"
            deadline = time.monotonic() + 5
            while not output.exists() or not output.stat().st_size:
                if process.poll() is not None or time.monotonic() >= deadline:
                    self.fail("owned child did not become ready")
                time.sleep(0.01)
            child_pid = int(output.read_text().strip())
            process.terminate()
            self.assertNotEqual(process.wait(timeout=5), 0)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
