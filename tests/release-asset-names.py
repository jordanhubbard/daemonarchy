#!/usr/bin/env python3
"""Check versioned public asset names in an exact release record."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify-release-assets.py"
SPEC = importlib.util.spec_from_file_location("release_assets", SCRIPT)
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


class ReleaseAssetNames(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "record.json"

    def record(self, certificate, version="1.3.1", iso=None, isos=None, architectures=None):
        isos = isos or [iso or f"daemonarchy-{version}-amd64.iso"]
        names = [name for image in isos for name in (image, image + ".sha256")] + [
            f"daemonarchy-{version}-boot.txz",
            f"daemonarchy-{version}-boot.txz.sig",
            certificate,
            certificate.removesuffix(".pem") + ".der",
        ]
        record = {
            "schema": "daemonarchy/release-inputs@1", "version": version,
            "tag": f"daemonarchy-{version}", "installer_commit": "a" * 40,
            "source_commit": "b" * 40, "osversion": 1600029,
            "assets": {name: [1, "sha256:" + "c" * 64] for name in names},
        }
        if architectures is not None:
            record["architectures"] = architectures
        self.path.write_text(json.dumps(record) + "\n")
        return record

    def test_patch_version_certificate_for_131(self):
        self.record("daemonarchy-1.3.1.pem")
        _, certificate = assets.read_record(self.path)
        self.assertEqual(certificate, "daemonarchy-1.3.1.pem")

    def test_minor_version_certificate_remains_valid(self):
        self.record("daemonarchy-1.3.pem")
        _, certificate = assets.read_record(self.path)
        self.assertEqual(certificate, "daemonarchy-1.3.pem")

    def test_unversioned_certificate_refused(self):
        self.record("daemonarchy.pem")
        with self.assertRaisesRegex(ValueError, "versioned public certificate"):
            assets.read_record(self.path)

    def test_published_131_keeps_raw_iso(self):
        self.record("daemonarchy-1.3.1.pem")
        record, _ = assets.read_record(self.path)
        self.assertIn("daemonarchy-1.3.1-amd64.iso", record["assets"])

    def test_140_publishes_compressed_iso(self):
        self.record("daemonarchy-1.4.0.pem", "1.4.0", "daemonarchy-1.4.0-amd64.iso.xz")
        record, _ = assets.read_record(self.path)
        self.assertIn("daemonarchy-1.4.0-amd64.iso.xz.sha256", record["assets"])

    def test_140_raw_iso_refused(self):
        self.record("daemonarchy-1.4.0.pem", "1.4.0")
        with self.assertRaisesRegex(ValueError, "incomplete or unexpected"):
            assets.read_record(self.path)

    def test_amd64_name_is_unchanged_by_default(self):
        self.assertEqual(assets.iso_asset("1.4.0"), "daemonarchy-1.4.0-amd64.iso.xz")
        self.assertEqual(assets.iso_asset("1.3.1"), "daemonarchy-1.3.1-amd64.iso")

    def test_140_publishes_one_image_per_architecture(self):
        isos = ["daemonarchy-1.4.0-amd64.iso.xz", "daemonarchy-1.4.0-aarch64.iso.xz"]
        self.record("daemonarchy-1.4.0.pem", "1.4.0", isos=isos, architectures=["amd64", "aarch64"])
        record, _ = assets.read_record(self.path)
        self.assertEqual(assets.iso_assets(record), isos)
        self.assertIn("daemonarchy-1.4.0-aarch64.iso.xz.sha256", record["assets"])

    def test_aarch64_only_release_record(self):
        iso = "daemonarchy-1.4.0-aarch64.iso.xz"
        self.record("daemonarchy-1.4.0.pem", "1.4.0", iso, architectures=["aarch64"])
        record, _ = assets.read_record(self.path)
        self.assertEqual(assets.iso_assets(record), [iso])

    def test_declared_architecture_requires_its_image(self):
        self.record("daemonarchy-1.4.0.pem", "1.4.0", "daemonarchy-1.4.0-amd64.iso.xz",
                    architectures=["amd64", "aarch64"])
        with self.assertRaisesRegex(ValueError, "incomplete or unexpected"):
            assets.read_record(self.path)

    def test_undeclared_architecture_image_refused(self):
        isos = ["daemonarchy-1.4.0-amd64.iso.xz", "daemonarchy-1.4.0-aarch64.iso.xz"]
        self.record("daemonarchy-1.4.0.pem", "1.4.0", isos=isos)
        with self.assertRaisesRegex(ValueError, "incomplete or unexpected"):
            assets.read_record(self.path)

    def test_unsupported_duplicate_or_early_architectures_refused(self):
        for version, architectures, message in (
                ("1.4.0", ["arm64"], "supported architectures"),
                ("1.4.0", ["amd64", "amd64"], "supported architectures"),
                ("1.4.0", [], "supported architectures"),
                ("1.4.0", ["aarch64", "amd64"], "canonical order"),
                ("1.3.1", ["amd64", "aarch64"], "predates aarch64")):
            with self.subTest(architectures=architectures):
                self.record(f"daemonarchy-{version}.pem", version, architectures=architectures)
                with self.assertRaisesRegex(ValueError, message):
                    assets.read_record(self.path)

    def test_140_compressed_iso_must_be_xz(self):
        directory = Path(self.temporary.name) / "assets"
        directory.mkdir()
        iso = "daemonarchy-1.4.0-amd64.iso.xz"
        payload = b"raw ISO bytes, not xz"
        digest = hashlib.sha256(payload).hexdigest()
        files = {
            iso: payload,
            iso + ".sha256": f"{digest}  {iso}\n".encode(),
            "daemonarchy-1.4.0-boot.txz": b"bundle",
            "daemonarchy-1.4.0-boot.txz.sig": b"signature",
            "daemonarchy-1.4.0.pem": b"certificate",
            "daemonarchy-1.4.0.der": b"certificate",
        }
        record = self.record("daemonarchy-1.4.0.pem", "1.4.0", iso)
        for name, content in files.items():
            (directory / name).write_bytes(content)
            record["assets"][name] = [len(content), "sha256:" + hashlib.sha256(content).hexdigest()]
        self.path.write_text(json.dumps(record) + "\n")
        with self.assertRaisesRegex(ValueError, "not an xz stream"):
            assets.verify(self.path, directory)


if __name__ == "__main__":
    unittest.main()
