#!/usr/bin/env python3
"""Contract tests use synthetic observations, never native timing claims."""

import copy
import importlib.util
from pathlib import Path
import unittest
import tempfile
import sys
import json

spec = importlib.util.spec_from_file_location(
    "measurements",
    Path(__file__).resolve().parents[1] / "scripts/release-measurements.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
IDENTITY = "sha256:" + "a" * 64


def run(scenario="clean", elapsed=100):
    result = {
        "schema": m.SCHEMA,
        "scenario": scenario,
        "baseline_kind": "normalized",
        "selection_identity": IDENTITY,
        "gate_scope_identity": IDENTITY,
        "measurement_scope_identity": IDENTITY,
        "worker_pool_identity": IDENTITY,
        "observation_identity": IDENTITY,
        "complete": True,
        "wall_time_ns": elapsed,
        "gates": {
            name: IDENTITY
            for name in (
                "build",
                "package",
                "sign",
                "iso",
                "native",
                "fresh-install",
                "upgrade",
                "rollback",
            )
        },
        "actions": [
            {
                "action_id": "browser",
                "action_key": IDENTITY,
                "kind": "compile",
                "origin": "www/chromium",
                "disposition": "executed" if scenario == "clean" else "requalified",
                "reason": "synthetic test fixture",
                "receipt_identity": IDENTITY,
                "output_identity": IDENTITY,
                "input_identity": IDENTITY,
                "worker_id": "fixture",
                "wall_time_ns": 1,
                "cache_read_bytes": 4,
                "cache_write_bytes": 0,
            }
        ],
    }

    resources = {
        "cpu_millis": 1000,
        "memory_mib": 64,
        "disk_mib": 64,
        "network_mbps": 1,
    }
    result["execution_mode"] = "single-machine"
    result["worker_pool"] = {
        "schema": "daemonarchy/measured-worker-pool@1",
        "catalogue_identity": IDENTITY,
        "admission_policy_identity": IDENTITY,
        "workers": [
            {
                "worker_id": "fixture",
                "worker_identity": IDENTITY,
                "physical_host_identity": IDENTITY,
                "capability_contract_identity": IDENTITY,
                "allocation_identity": IDENTITY,
                "slots": 1,
                "resources": resources,
            }
        ],
    }
    result["worker_pool_identity"] = m.content_identity(result["worker_pool"])
    result["worker_observations"] = [
        {
            "worker_id": "fixture",
            "worker_identity": IDENTITY,
            "physical_host_identity": IDENTITY,
            "catalogue_identity": IDENTITY,
            "observation_identity": IDENTITY,
            "parent_host_binding_receipt_identity": IDENTITY,
            "available_resources": resources,
        }
    ]
    result["gate_scope"] = {
        "schema": "daemonarchy/measured-gate-scope@1",
        "requirements": [
            {"gate": name, "policy_identity": IDENTITY, "target_identity": IDENTITY}
            for name in sorted(result["gates"])
        ],
        "waivers": [],
    }
    result["gate_scope_identity"] = m.content_identity(result["gate_scope"])
    return result


class Measurements(unittest.TestCase):
    def test_observer_retains_success_failure_and_timeout_without_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, code, timeout, expected in (
                ("ok", "print('observed')", 2, "exited"),
                ("failed", "raise SystemExit(7)", 2, "exited"),
                ("timeout", "import time; time.sleep(5)", 1, "timed-out"),
            ):
                record = m.observe(
                    [sys.executable, "-c", code], root / name, timeout_seconds=timeout
                )
                self.assertEqual(record["status"], expected)
                self.assertFalse(record["complete"])
                self.assertGreater(record["wall_time_ns"], 0)
                self.assertEqual(
                    record, json.loads((root / name / "observation.json").read_text())
                )
            self.assertEqual(
                json.loads((root / "failed" / "observation.json").read_text())[
                    "exit_status"
                ],
                7,
            )
            with self.assertRaises(FileExistsError):
                m.observe(
                    [sys.executable, "-c", "pass"], root / "ok", timeout_seconds=2
                )

    def test_terminal_observation_reopens_exact_command_context_and_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            context = {
                field: IDENTITY
                for field in (
                    "action_key",
                    "input_identity",
                    "selection_identity",
                    "worker_pool_identity",
                    "worker_identity",
                )
            }
            context["worker_id"] = "fixture"
            context["worker_pool_identity"] = run()["worker_pool_identity"]
            for field in (
                "physical_host_identity",
                "observation_identity",
                "parent_host_binding_receipt_identity",
            ):
                context[field] = IDENTITY
            raw = m.observe(
                [sys.executable, "-c", "print('observed')"],
                root / "job",
                timeout_seconds=2,
                context=context,
            )
            candidate = run()
            row = candidate["actions"][0]
            row.update(
                {
                    "observation_path": "job/observation.json",
                    "terminal_receipt_identity": raw["identity"],
                    "command_identity": raw["command_identity"],
                    "wall_time_ns": raw["wall_time_ns"],
                }
            )
            self.assertTrue(m.verify_observations(candidate, root))
            candidate["selection_identity"] = "sha256:" + "b" * 64
            with self.assertRaisesRegex(ValueError, "context"):
                m.verify_observations(candidate, root)
            candidate["selection_identity"] = IDENTITY
            (root / "job" / "stdout.log").write_text("replaced")
            with self.assertRaisesRegex(ValueError, "log changed"):
                m.verify_observations(candidate, root)

    def test_two_vm_ids_on_one_physical_host_cannot_claim_distributed_work(self):
        candidate = run()
        candidate["execution_mode"] = "distributed"
        second_worker = copy.deepcopy(candidate["worker_pool"]["workers"][0])
        second_worker["worker_id"] = "fixture-guest-two"
        second_worker["worker_identity"] = "sha256:" + "b" * 64
        candidate["worker_pool"]["workers"].append(second_worker)
        second_observation = copy.deepcopy(candidate["worker_observations"][0])
        second_observation.update(
            {
                "worker_id": second_worker["worker_id"],
                "worker_identity": second_worker["worker_identity"],
            }
        )
        candidate["worker_observations"].append(second_observation)
        second_action = copy.deepcopy(candidate["actions"][0])
        second_action.update(
            {
                "action_id": "independent",
                "action_key": "sha256:" + "b" * 64,
                "worker_id": second_worker["worker_id"],
            }
        )
        candidate["actions"].append(second_action)
        candidate["worker_pool_identity"] = m.content_identity(candidate["worker_pool"])
        with self.assertRaisesRegex(ValueError, "two physical hosts"):
            m.validate(candidate)
        # Distinct actual parent bindings satisfy structure, not authentication.
        second_worker["physical_host_identity"] = "sha256:" + "c" * 64
        second_observation["physical_host_identity"] = second_worker[
            "physical_host_identity"
        ]
        candidate["worker_pool_identity"] = m.content_identity(candidate["worker_pool"])
        m.validate(candidate)

    def test_relabelled_pool_changed_resources_or_waived_scope_cannot_normalize(self):
        baseline = run()
        candidate = run("unchanged")
        candidate["worker_pool"]["workers"][0]["resources"]["cpu_millis"] += 1000
        with self.assertRaisesRegex(ValueError, "actual resources"):
            m.compare(baseline, candidate)
        candidate["worker_pool_identity"] = m.content_identity(candidate["worker_pool"])
        with self.assertRaises(ValueError):
            m.compare(baseline, candidate)
        candidate = run("unchanged")
        candidate["gate_scope"]["waivers"] = ["fixture final-ISO waiver"]
        candidate["gate_scope_identity"] = m.content_identity(candidate["gate_scope"])
        with self.assertRaisesRegex(ValueError, "waived"):
            m.compare(baseline, candidate)

    def test_recovered_historical_failed_stages_never_become_clean_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "retained-checkpoint.json"
            original = {
                "schema": "daemonarchy/native-traced-build-checkpoint@1",
                "original_run": {
                    "source_revision": "a" * 40,
                    "status": "failed",
                    "phases": [
                        {
                            "name": "buildworld",
                            "exit": 0,
                            "elapsed_seconds": 12.25,
                            "log_sha256": "a" * 64,
                        },
                        {"name": "sets", "exit": -1, "elapsed_seconds": 2},
                    ],
                },
            }
            path.write_text(json.dumps(original))
            recovered = m.recover_historical_phases(path, release_source="b" * 40)
            self.assertFalse(recovered["comparison_eligible"])
            self.assertFalse(recovered["matches_release_source"])
            self.assertEqual(
                recovered["phase_observations"][0]["reported_elapsed_seconds"], 12.25
            )
            self.assertIsNone(recovered["phase_observations"][0]["started_utc"])
            self.assertEqual(json.loads(path.read_text()), original)
            with self.assertRaises(ValueError):
                m.compare(recovered, run("unchanged"))

    def test_thresholds_and_bytes_are_computed(self):
        self.assertTrue(m.compare(run(), run("unchanged", 10))["target_met"])
        self.assertFalse(m.compare(run(), run("unchanged", 11))["target_met"])
        result = m.compare(run(), run("compatible-update", 25))
        self.assertTrue(result["target_met"])
        self.assertEqual(result["cache_read_bytes"], 4)

    def test_inequivalent_scope_pool_or_historical_baseline_refused(self):
        for field in (
            "gate_scope_identity",
            "worker_pool_identity",
            "measurement_scope_identity",
            "baseline_kind",
        ):
            candidate = run("unchanged", 1)
            candidate[field] = (
                "historical-observation"
                if field == "baseline_kind"
                else "sha256:" + "b" * 64
            )
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.compare(run(), candidate)

    def test_compilation_cannot_hide_in_reuse_or_package_runs(self):
        for scenario in ("unchanged", "compatible-update", "package-only", "iso-only"):
            candidate = run(scenario)
            candidate["actions"][0]["disposition"] = "executed"
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                m.validate(candidate)

    def test_missing_reason_receipt_negative_bytes_bool_time_or_gate_refused(self):
        for field, value in (
            ("reason", ""),
            ("receipt_identity", None),
            ("cache_read_bytes", -1),
            ("wall_time_ns", True),
        ):
            candidate = run()
            candidate["actions"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.validate(candidate)
        candidate = run()
        del candidate["gates"]["rollback"]
        with self.assertRaisesRegex(ValueError, "gates"):
            m.validate(candidate)

    def test_duplicate_execution_and_omitted_obligation_refused(self):
        candidate = run()
        candidate["actions"].append(copy.deepcopy(candidate["actions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            m.validate(candidate)
        candidate = run("unchanged")
        candidate["actions"][0]["action_id"] = "other"
        with self.assertRaisesRegex(ValueError, "obligations"):
            m.compare(run(), candidate)


if __name__ == "__main__":
    unittest.main()
