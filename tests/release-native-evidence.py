#!/usr/bin/env python3
"""Exercise the 1.3.1 native release evidence boundary with retained files."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release-check-1.3.1.py"
SPEC = importlib.util.spec_from_file_location("release_check_131", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
ISO_SHA = "a" * 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


class NativeReleaseEvidence(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.files = self.root / "files"
        self.files.mkdir()
        self.record_path = self.root / "native.json"
        self.values = {name: b"retained native evidence\n" for name in release.NATIVE_EVIDENCE}
        for name in release.NATIVE_RESULTS:
            self.values[name] = b"0\n"
        self.values["source-world.log"] = b">>> World build completed\n"
        self.values["source-kernel.log"] = b">>> Kernel build for GENERIC completed\n"
        self.values["ports.built"] = b"lang/dotnet dotnet-9.0.14\n"
        self.manifest = {
            "source_revision": release.SOURCE,
            "ports_revision": release.PORTS,
            "jail_osversion": 1600029,
            "packages": {"daemonarchy-1.3.1,1.pkg": [1, "0" * 64],
                         "dotnet-9.0.14.pkg": [1, "1" * 64]},
            "built_sha256": sha(self.values["ports.built"]),
        }
        self.values["package-manifest.json"] = (json.dumps(self.manifest) + "\n").encode()
        self.native = {
            "schema": "daemonarchy/native-release-evidence@1",
            "source_commit": release.SOURCE,
            "ports_commit": release.PORTS,
            "desktop_commit": release.DESKTOP,
            "iso_installer_commit": release.ISO_PRODUCT,
            "osversion": 1600029,
            "iso_sha256": ISO_SHA,
        }
        self.write()

    def write(self):
        for name, data in self.values.items():
            (self.files / name).write_bytes(data)
        self.native["evidence"] = {name: sha(data) for name, data in self.values.items()}
        self.record_path.write_text(json.dumps(self.native) + "\n")
        self.release_record = {"native_evidence_sha256": sha(self.record_path.read_bytes())}

    def check(self):
        with patch.dict(os.environ, {
            "DAEMONARCHY_NATIVE_RECORD": str(self.record_path),
            "DAEMONARCHY_NATIVE_EVIDENCE_ROOT": str(self.files),
        }):
            release.native_evidence(self.release_record, ISO_SHA)

    def test_exact_native_build_selection_passes(self):
        self.check()

    def test_changed_evidence_refuses_even_when_record_is_unchanged(self):
        self.check()
        (self.files / "bulk.log").write_text("replaced\n")
        with self.assertRaisesRegex(ValueError, "bulk.log"):
            self.check()

    def test_nonzero_native_result_refuses_even_when_rehashed(self):
        self.values["bulk.exit"] = b"1\n"
        self.write()
        with self.assertRaisesRegex(ValueError, "native result failed: bulk.exit"):
            self.check()

    def test_changed_release_or_incomplete_evidence_refuses(self):
        self.native["iso_sha256"] = "b" * 64
        self.write()
        with self.assertRaisesRegex(ValueError, "selects other release inputs"):
            self.check()
        self.native["iso_sha256"] = ISO_SHA
        del self.values["ports.built"]
        self.write()
        with self.assertRaisesRegex(ValueError, "inventory is incomplete"):
            self.check()

    def test_missing_required_dotnet_build_refuses_even_when_rehashed(self):
        self.values["ports.built"] = b"ports-mgmt/pkg pkg-2.8.4\n"
        self.manifest["built_sha256"] = sha(self.values["ports.built"])
        self.values["package-manifest.json"] = (json.dumps(self.manifest) + "\n").encode()
        self.write()
        with self.assertRaisesRegex(ValueError, "dotnet build result is absent"):
            self.check()


class MacBookReleaseDecision(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "decision.json"
        self.decision = json.loads(release.DECISION.read_text())

    def check(self):
        self.path.write_text(json.dumps(self.decision) + "\n")
        record = {
            "evidence_status": release.EVIDENCE_STATUS,
            "macbook_release_decision_sha256": sha(self.path.read_bytes()),
        }
        with patch.object(release, "DECISION", self.path):
            release.macbook_release_decision(record)

    def test_operator_confirmation_and_final_iso_waiver_pass(self):
        self.check()

    def test_final_iso_result_cannot_be_promoted_to_passed(self):
        self.decision["final_public_iso_checks"]["fresh_install"] = "passed"
        with self.assertRaisesRegex(ValueError, "must remain not rerun"):
            self.check()

    def test_hardware_rooted_attestation_cannot_be_inferred(self):
        self.decision["hardware_rooted_attestation"] = "passed"
        with self.assertRaisesRegex(ValueError, "unsupported physical result"):
            self.check()

    def test_changed_decision_digest_is_rejected(self):
        self.path.write_text(json.dumps(self.decision) + "\n")
        record = {
            "evidence_status": release.EVIDENCE_STATUS,
            "macbook_release_decision_sha256": "0" * 64,
        }
        with patch.object(release, "DECISION", self.path):
            with self.assertRaisesRegex(ValueError, "digest differs"):
                release.macbook_release_decision(record)


if __name__ == "__main__":
    unittest.main()
