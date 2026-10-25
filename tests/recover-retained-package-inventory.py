#!/usr/bin/env python3
"""Pinned historical metadata recovery is distinct from current native admission."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("recovery", Path(__file__).resolve().parents[1] / "scripts/recover-retained-package-inventory.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.provenance = dict(schema="daemonarchy/package-reuse-candidate@1", status="admitted_for_release",
                               source_revision="source", ports_revision="ports", selected_base_osversion=1600029,
                               qualification_scope="historical native fixture only",
                               retained_archives=[dict(archive="chromium-1.pkg", name="chromium", sha256="sha256:" + "a" * 64,
                                                       qualification="admitted_for_release")])
        self.sha = hashlib.sha256(json.dumps(self.provenance).encode()).hexdigest()
        self.manifest = dict(schema="daemonarchy/madmax-package-import@2", assembly_kind="selected-base-installed-reuse",
                             source_revision="source", ports_revision="ports", jail_osversion=1600029,
                             reuse_provenance_sha256=self.sha, packages={"chromium-1.pkg": [10, "a" * 64], "unparsed-name-2.pkg": [20, "b" * 64]})

    def result(self, manifest=None, provenance=None):
        return recovery.recover(manifest or self.manifest, "c" * 64, provenance or self.provenance, self.sha)

    def test_recovers_every_archive_without_new_admission_or_filename_inference(self):
        result = self.result()
        self.assertEqual((result["archive_count"], result["archive_bytes"]), (2, 30))
        self.assertEqual(result["counts"], {
            "admitted_for_recorded_1.3.1_scope": 1, "retained_archive_identity_only": 1})
        for row in result["packages"]:
            self.assertFalse(row["admitted_for_current_release"])
            self.assertFalse(row["bytes_verified_in_this_run"])
            self.assertEqual(row["current_compilation_decision"], "not_determined_by_historical_inventory")
        self.assertIsNone(result["packages"][1]["package_name"])
        self.assertIsNone(result["packages"][1]["package_version"])
        self.assertFalse(result["cache_admission_authorized"])

    def test_mismatched_provenance_archive_or_selected_inputs_refuses(self):
        for key, value in (("reuse_provenance_sha256", "d" * 64), ("source_revision", "other"), ("jail_osversion", 1600030)):
            manifest = copy.deepcopy(self.manifest)
            manifest[key] = value
            with self.assertRaises(ValueError):
                self.result(manifest=manifest)
        manifest = copy.deepcopy(self.manifest)
        manifest["packages"]["chromium-1.pkg"][1] = "e" * 64
        with self.assertRaisesRegex(ValueError, "admitted archive differs"):
            self.result(manifest=manifest)

    def test_missing_duplicate_or_unqualified_historical_receipt_refuses(self):
        provenance = copy.deepcopy(self.provenance)
        provenance["retained_archives"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.result(provenance=provenance)
        provenance = copy.deepcopy(self.provenance)
        provenance["retained_archives"][0]["qualification"] = "pending"
        with self.assertRaisesRegex(ValueError, "unqualified"):
            self.result(provenance=provenance)

    def test_malformed_metadata_or_admission_refuses(self):
        with self.assertRaisesRegex(ValueError, "must be objects"):
            recovery.recover([], "c" * 64, self.provenance, self.sha)
        provenance = copy.deepcopy(self.provenance)
        provenance["retained_archives"] = [None]
        with self.assertRaisesRegex(ValueError, "must be an object"):
            self.result(provenance=provenance)
        manifest = copy.deepcopy(self.manifest)
        manifest["packages"]["chromium-1.pkg"] = []
        with self.assertRaisesRegex(ValueError, "archive size/identity"):
            self.result(manifest=manifest)

    def test_pinned_metadata_is_read_only_and_tampering_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            payload = json.dumps(self.manifest).encode()
            path.write_bytes(payload)
            recovery.read_pinned(path, hashlib.sha256(payload).hexdigest())
            self.assertEqual(path.read_bytes(), payload)
            with self.assertRaisesRegex(ValueError, "differs"):
                recovery.read_pinned(path, "f" * 64)


if __name__ == "__main__":
    unittest.main()
