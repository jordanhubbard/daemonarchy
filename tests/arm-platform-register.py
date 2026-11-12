#!/usr/bin/env python3
"""Check retained release scope and refusal of unsupported qualification claims."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("arm_register", ROOT / "scripts/arm-platform-register.py")
register = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(register)


class PlatformRegister(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(register.DEFAULT.read_text())

    def test_current_inventory_is_valid_but_not_qualification(self):
        self.assertEqual(register.validate(self.data), [])
        result = register.summary(self.data)
        self.assertGreaterEqual(result["profiles"], 47)
        self.assertEqual(result["feature_states"]["passed"], 0)
        self.assertIn("not established", result["qualification"])

    def test_removing_any_required_target_is_rejected(self):
        for row in self.data["profiles"]:
            with self.subTest(row=row["id"]):
                candidate = copy.deepcopy(self.data)
                candidate["profiles"] = [r for r in candidate["profiles"] if r["id"] != row["id"]]
                self.assertIn("missing required scope row: " + row["id"], register.validate(candidate))

    def test_variants_can_be_added_without_replacing_scope(self):
        variant = copy.deepcopy(self.data["profiles"][0])
        variant["id"] += "-firmware-variant"
        self.data["profiles"].append(variant)
        self.assertEqual(register.validate(self.data), [])

    def test_duplicate_ids_and_reassigned_ownership_are_rejected(self):
        self.data["profiles"].append(copy.deepcopy(self.data["profiles"][0]))
        self.assertTrue(any("duplicate" in p for p in register.validate(self.data)))
        self.data["profiles"].pop()
        self.data["profiles"][0]["work_item"] = "ARM-008"
        self.assertTrue(any("required work item" in p for p in register.validate(self.data)))

    def test_native_worker_boot_cannot_narrow_vm_desktop_scope(self):
        for name in register.DESKTOP_VMS:
            with self.subTest(name=name):
                candidate = copy.deepcopy(self.data)
                row = next(row for row in candidate["profiles"] if row["id"] == name)
                row["role"] = "server"
                self.assertTrue(any("desktop coverage" in p for p in register.validate(candidate)))

    def test_unknown_identity_is_visible_and_not_invented(self):
        row = self.data["profiles"][0]
        row["identity"]["firmware"] = None
        self.assertIn("firmware", register.summary(self.data)["unresolved_identity"][row["id"]])
        row["identity"]["firmware"] = ""
        self.assertTrue(register.validate(self.data))

    def test_no_partial_feature_matrix_or_inferred_pass(self):
        row = self.data["profiles"][0]
        del row["features"]["audio"]
        self.assertTrue(any("feature matrix" in p for p in register.validate(self.data)))
        row["features"]["audio"] = {"state": "passed", "note": "VM or bootstrap passed"}
        self.assertTrue(any("receipt admission" in p for p in register.validate(self.data)))

    def test_failed_and_blocked_remain_distinct_from_unknown(self):
        row = self.data["profiles"][0]
        row["features"]["boot"] = {"state": "failed", "note": "Final image failed to boot."}
        row["features"]["display"] = {"state": "blocked", "note": "Driver missing."}
        self.assertEqual(register.validate(self.data), [])
        counts = register.summary(self.data)["feature_states"]
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["blocked"], 1)

    def test_bad_sources_and_incomplete_enrollment_are_rejected(self):
        for field, value in (("sources", ["../outside.md"]), ("sources", ["missing.md"]),
                             ("owner", ""), ("hardware", {}), ("identity", {}),
                             ("kind", "arm"), ("features", None), ("kind", []),
                             ("work_item", []), ("role", {}),
                             ("hardware", {"state": [], "note": "bad"})):
            with self.subTest(field=field, value=value):
                candidate = copy.deepcopy(self.data)
                candidate["profiles"][0][field] = value
                self.assertTrue(register.validate(candidate))

    def test_malformed_structures_are_rejected(self):
        for profiles in (None, {}, [None], [{"id": []}]):
            with self.subTest(profiles=profiles):
                candidate = copy.deepcopy(self.data)
                candidate["profiles"] = profiles
                self.assertTrue(register.validate(candidate))

    def test_cli_reports_inventory_limit(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/arm-platform-register.py")],
                                capture_output=True, text=True, check=True)
        self.assertIn("inventory validation only", json.loads(result.stdout)["qualification"])


if __name__ == "__main__":
    unittest.main()
