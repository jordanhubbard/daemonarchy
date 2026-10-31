#!/usr/bin/env python3
"""The 1.4.x release gate refuses what its record does not prove (no network, no litai)."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts/release-check-1.4.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def record(**over):
    value = {"schema": "daemonarchy/release-inputs@1", "version": "1.5.0",
             "tag": "daemonarchy-1.5.0", "installer_commit": "a" * 40}
    value.update(over)
    return value


class Gate(unittest.TestCase):
    def setUp(self):
        self._root = gate.ROOT

    def tearDown(self):
        gate.ROOT = self._root

    def fixture(self, tmp, version="1.5.0"):
        root = Path(tmp)
        (root / "release").mkdir()
        (root / "release/current.json").write_text(json.dumps({"version": version}))
        gate.ROOT = root

    def test_accepts_matching_record(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            gate.check_record(record(), "1.5.0", "a" * 40)

    def test_refuses_each_mismatch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp)
            for bad in (record(version="1.4.1"), record(tag="daemonarchy-1.4.1"),
                        record(installer_commit="b" * 40), record(schema="x"),
                        record(assets={"a.iso.xz": [1, "sha256:TODO"]})):
                with self.subTest(bad), self.assertRaises(ValueError):
                    gate.check_record(bad, "1.5.0", "a" * 40)

    def test_refuses_placeholder_or_stale_current_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp, version="1.4.1")
            with self.assertRaises(ValueError):
                gate.check_record(record(), "1.5.0", "a" * 40)

    def test_refuses_without_evidence_paths(self):
        for variable in ("DAEMONARCHY_RELEASE_RECORD", "DAEMONARCHY_RELEASE_ASSETS"):
            with self.subTest(variable):
                env = {k: v for k, v in __import__("os").environ.items() if k != variable}
                done = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/release-check-1.4.py")],
                                      capture_output=True, text=True, env=env)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn("refused", done.stderr)


if __name__ == "__main__":
    unittest.main()
