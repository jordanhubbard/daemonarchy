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

    def reuse(self):
        self.native["schema"] = "daemonarchy/native-release-evidence@2"
        del self.values["bulk.log"]
        del self.values["bulk.exit"]
        self.values["image-install.exit"] = b"0\n"
        self.values["native-signed-feed-check.exit"] = b"0\n"
        self.values["native-signed-feed-check.log"] = (
            b"Selected root OSVERSION: 1600029; IGNORE_OSVERSION unset\n"
            b"Daemonarchy-Test repository update completed. 203 packages processed.\n")
        self.values["image-install.log"] = ("\n".join(
            "Installing " + name.removesuffix(".pkg") + "..."
            for name in (*release.REUSED_ARCHIVES, "daemonarchy-1.3.1,1.pkg")) + "\n").encode()
        checks = ("\n".join("Checking " + name.split("-")[0] + ": . done"
                            for name in release.REUSED_ARCHIVES) +
                  "\nChecking daemonarchy: . done\n").encode()
        # Multiword package names require their full registered names.
        checks = checks.replace(b"Checking hyprland: . done",
                                b"Checking hyprland-preview-share-picker: . done")
        checks = checks.replace(b"Checking obs: . done",
                                b"Checking obs-studio: . done")
        self.values["pkg-check-deps.log"] = checks
        self.values["pkg-check-files.log"] = checks
        self.values["runtime-smoke.log"] = (b"Chromium 154.0.8037.57\n"
                                             b"OBS Studio - 32.2.2\n"
                                             b"CEF RTLD_NOW load passed\n")
        provenance = {
            "schema": "daemonarchy/package-reuse-candidate@1",
            "status": "admitted_for_release",
            "source_revision": release.SOURCE,
            "ports_revision": release.PORTS,
            "selected_base_osversion": 1600029,
            "retained_archives": [
                {"archive": name, "name": name.split("-")[0],
                 "sha256": "sha256:" + digest,
                 "source_tree_equal": True, "qualification": "admitted_for_release",
                 "public_release": "packages-16-amd64-1.1.1"}
                for name, digest in release.REUSED_ARCHIVES.items()],
        }
        for item in provenance["retained_archives"]:
            if item["archive"].startswith("hyprland-preview-share-picker-"):
                item["name"] = "hyprland-preview-share-picker"
            if item["archive"].startswith("obs-studio-"):
                item["name"] = "obs-studio"
        self.values["reuse-provenance.json"] = (json.dumps(provenance) + "\n").encode()
        self.manifest["schema"] = "daemonarchy/madmax-package-import@2"
        self.manifest["assembly_kind"] = "selected-base-installed-reuse"
        self.manifest["image_install_log_sha256"] = sha(self.values["image-install.log"])
        self.manifest["reuse_provenance_sha256"] = sha(self.values["reuse-provenance.json"])
        self.manifest["packages"].update({name: [1, digest]
                                          for name, digest in release.REUSED_ARCHIVES.items()})
        self.values["package-manifest.json"] = (json.dumps(self.manifest) + "\n").encode()
        self.write()

    def test_qualified_reuse_with_exact_public_archives_passes(self):
        self.reuse()
        self.check()

    def closure(self):
        self.reuse()
        self.native["schema"] = "daemonarchy/native-release-evidence@3"
        self.values["native-signed-feed-check.log"] = (
            b"Selected root OSVERSION: 1600029; IGNORE_OSVERSION unset\n"
            b"Daemonarchy-Test repository update completed. 204 packages processed.\n")
        self.values["installer-mirror-closure.json"] = (json.dumps({
            "schema": "daemonarchy/installer-mirror-closure@1",
            "installer_iso_sha256": ISO_SHA,
            "missing_names": ["py312-brotli"],
            "selected_package_count": 203,
            "native_closure_package_count": 982,
        }) + "\n").encode()
        self.values["native-public-feed-check.exit"] = b"0\n"
        self.values["native-public-feed-check.log"] = (
            b"Selected root OSVERSION: 1600029; IGNORE_OSVERSION unset\n"
            b"Daemonarchy-Public repository update completed. 204 packages processed.\n"
            b"Native 1600029 client verified public signed feed with 204 packages\n")
        self.manifest["packages"]["py312-brotli-1.2.0.pkg"] = [14342, "2" * 64]
        self.values["package-manifest.json"] = (json.dumps(self.manifest) + "\n").encode()
        self.write()

    def test_corrected_public_feed_with_mirror_closure_passes(self):
        self.closure()
        self.check()

    def test_corrected_feed_without_public_client_result_refuses(self):
        self.closure()
        self.values["native-public-feed-check.exit"] = b"1\n"
        self.write()
        with self.assertRaisesRegex(ValueError, "native result failed"):
            self.check()

    def test_reuse_with_changed_archive_digest_refuses_even_when_rehashed(self):
        self.reuse()
        self.manifest["packages"]["cef-152.0.6.pkg"][1] = "f" * 64
        self.values["package-manifest.json"] = (json.dumps(self.manifest) + "\n").encode()
        self.write()
        with self.assertRaisesRegex(ValueError, "retained archive lacks exact public"):
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
