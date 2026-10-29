#!/usr/bin/env python3
"""Portable contract checks; synthetic clocks are not native performance evidence."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "installer_measurements", ROOT / "scripts/installer-measurements.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
IDENTITY = "sha256:" + "a" * 64


def context():
    return {
        "schema": m.CONTEXT_SCHEMA,
        "image": {"identity": IDENTITY, "release": "1.4.1", "size_bytes": 1000},
        "selection": {
            "identity": IDENTITY,
            "catalogue_identity": IDENTITY,
            "package_count": 3,
            "download_bytes": 900,
        },
        "target": {
            "kind": "physical",
            "machine_class": "MacBookPro16-1",
            "worker_id": "macbook",
            "worker_identity": IDENTITY,
            "storage": "nvme-zfs",
            "link_mbps": 1000,
            "link_measurement": "measured",
            "cache_mode": "network",
        },
    }


class InstallerMeasurements(unittest.TestCase):
    def fixture(self, root, *, status="complete", exit_status=0, log=None):
        diagnostics = root / "diagnostics"
        diagnostics.mkdir()
        values = {
            "status": status,
            "exit-code": str(exit_status),
            "started-utc": "2026-10-29T19:59:55Z",
            "updated-utc": "2026-10-29T20:02:00Z",
        }
        for name, value in values.items():
            (diagnostics / name).write_text(value + "\n")
        if log is None:
            log = "\n".join(
                (
                    "@@step partition 1793304000",
                    "@@step pool 1793304010",
                    "@@step base 1793304020",
                    "@@step loader 1793304030",
                    "@@step config 1793304040",
                    "@@step fetch 1793304050",
                    "Number of packages to be fetched: 3",
                    '@@fetch {"schema":"daemonarchy/pkg-fetch@1","archives":3,"bytes":900,'
                    '"file":"","file_bytes":0,"file_total":0}',
                    "@@step packages 1793304080",
                    "Number of packages to be installed: 3",
                    "[ 3/3] Extracting desktop-1.0: done",
                    "@@step finish 1793304100",
                )
            ) + "\n"
        log_path = root / "install.log"
        log_path.write_text(log)
        context_path = root / "context.json"
        context_path.write_text(json.dumps(context()))
        return diagnostics, log_path, context_path

    def test_complete_measurement_binds_context_log_timing_and_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = m.measure(*self.fixture(root))
            self.assertTrue(result["complete"])
            self.assertEqual(result["wall_time_seconds"], 125)
            self.assertEqual(result["unattributed_start_seconds"], 5)
            self.assertEqual(result["phase_span_seconds"], 120)
            self.assertEqual(result["phases"][5]["name"], "fetch")
            self.assertEqual(result["phases"][5]["elapsed_seconds"], 30)
            self.assertEqual(result["package_observations"]["reported_fetch_bytes"], 900)
            self.assertEqual(result["package_observations"]["reported_fetch_attempts"], 1)
            self.assertEqual(result["package_observations"]["extracted_packages"], 3)
            self.assertEqual(result["context_identity"], m.content_identity(context()))
            self.assertTrue(result["context_quality"]["link_condition_known"])
            self.assertRegex(result["identity"], r"^sha256:[0-9a-f]{64}$")
            self.assertIn("grants no", result["limitations"])

    def test_terminal_failure_is_retained_without_claiming_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = "@@step partition 1793304000\n@@step base 1793304020\n@@step fetch 1793304050\n"
            result = m.measure(*self.fixture(root, status="failed", exit_status=7, log=log))
            self.assertFalse(result["complete"])
            self.assertEqual(result["exit_status"], 7)

    def test_complete_status_requires_full_stages_and_consistent_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.fixture(root, log="@@step partition 1793304000\n")
            with self.assertRaisesRegex(ValueError, "omits required stages"):
                m.measure(*fixture)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.fixture(root, status="complete", exit_status=3)
            with self.assertRaisesRegex(ValueError, "status and exit disagree"):
                m.measure(*fixture)

    def test_changed_or_ambiguous_inputs_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diagnostics, log_path, context_path = self.fixture(root)
            changed = context()
            changed["target"]["cache_mode"] = "ambient"
            context_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "cache mode"):
                m.measure(diagnostics, log_path, context_path)

            context_path.write_text(json.dumps(context()))
            log_path.write_text("@@step partition 10\n@@step partition 11\n")
            with self.assertRaisesRegex(ValueError, "repeated"):
                m.measure(diagnostics, log_path, context_path)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diagnostics, log_path, context_path = self.fixture(root)
            context_path.write_text('{"schema":"x","schema":"y"}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                m.measure(diagnostics, log_path, context_path)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diagnostics, log_path, context_path = self.fixture(root)
            unknown = context()
            unknown["target"]["link_mbps"] = None
            unknown["target"]["link_measurement"] = "unknown"
            context_path.write_text(json.dumps(unknown))
            result = m.measure(diagnostics, log_path, context_path)
            self.assertFalse(result["context_quality"]["link_condition_known"])

    def test_retries_count_all_measured_transfer_and_clock_bounds_refuse(self):
        event = '@@fetch {"schema":"daemonarchy/pkg-fetch@1","archives":%d,"bytes":%d,' \
                '"file":"","file_bytes":0,"file_total":0}'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = "\n".join((
                "@@step partition 1793304000",
                event % (2, 600),
                event % (0, 100),
                event % (3, 900),
                "@@step base 1793304020",
            )) + "\n"
            result = m.measure(*self.fixture(root, status="failed", exit_status=7, log=log))
            observed = result["package_observations"]
            self.assertEqual(observed["reported_fetch_attempts"], 2)
            self.assertEqual(observed["reported_fetch_archives"], 5)
            self.assertEqual(observed["reported_fetch_bytes"], 1500)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.fixture(root, status="failed", exit_status=7,
                                   log="@@step partition 1793303990\n")
            with self.assertRaisesRegex(ValueError, "precedes diagnostic start"):
                m.measure(*fixture)

    def test_separate_package_transactions_remain_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = "\n".join((
                "@@step fetch 1793304000",
                "Number of packages to be installed: 1",
                "@@step packages 1793304050",
                "Number of packages to be installed: 3",
            )) + "\n"
            result = m.measure(*self.fixture(root, status="failed", exit_status=7, log=log))
            self.assertEqual(result["package_observations"]["declared_package_totals"], [
                {"step": "fetch", "action": "installed", "packages": 1},
                {"step": "packages", "action": "installed", "packages": 3},
            ])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = "\n".join((
                "@@step fetch 1793304000",
                "Number of packages to be fetched: 3",
                "Number of packages to be fetched: 4",
            )) + "\n"
            fixture = self.fixture(root, status="failed", exit_status=7, log=log)
            with self.assertRaisesRegex(ValueError, "changed within fetch"):
                m.measure(*fixture)

    def test_output_is_create_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = m.measure(*self.fixture(root))
            output = root / "measurement.json"
            m.write_new(output, result)
            self.assertEqual(json.loads(output.read_text()), result)
            with self.assertRaises(FileExistsError):
                m.write_new(output, result)


if __name__ == "__main__":
    unittest.main()
