#!/usr/bin/env python3
"""Check versioned public certificate names in an exact release record."""

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

    def record(self, certificate):
        names = [
            "daemonarchy-1.3.1-amd64.iso",
            "daemonarchy-1.3.1-amd64.iso.sha256",
            "daemonarchy-1.3.1-boot.txz",
            "daemonarchy-1.3.1-boot.txz.sig",
            certificate,
            certificate.removesuffix(".pem") + ".der",
        ]
        record = {
            "schema": "daemonarchy/release-inputs@1", "version": "1.3.1",
            "tag": "daemonarchy-1.3.1", "installer_commit": "a" * 40,
            "source_commit": "b" * 40, "osversion": 1600029,
            "assets": {name: [1, "sha256:" + "c" * 64] for name in names},
        }
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


if __name__ == "__main__":
    unittest.main()
