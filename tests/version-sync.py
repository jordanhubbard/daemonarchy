#!/usr/bin/env python3
"""VERSION is the one release version; every copy of it must agree."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/version.py"


def run(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True)


class VersionTests(unittest.TestCase):
    def test_repository_agrees(self):
        result = run("check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_show_json_matches_file(self):
        shown = json.loads(run("show", "--json").stdout)["version"]
        self.assertEqual(shown, (ROOT / "VERSION").read_text().strip())

    def test_build_iso_takes_version_from_file(self):
        text = (ROOT / "build-iso.sh").read_text()
        self.assertIn('"$here/VERSION"', text)
        self.assertNotIn("pkg query -F \"$daemonarchy_pkg\"", text)

    def test_set_updates_both_and_check_catches_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "scripts").mkdir()
            (tmp / "scripts/version.py").write_text(SCRIPT.read_text())
            (tmp / "VERSION").write_text("1.0.0\n")
            (tmp / "literate.project.json").write_text('{\n  "version": "1.0.0",\n  "profile": "x"\n}\n')
            tool = [sys.executable, "-I", str(tmp / "scripts/version.py")]
            self.assertEqual(subprocess.run([*tool, "set", "2.3.4"], capture_output=True).returncode, 0)
            self.assertEqual((tmp / "VERSION").read_text(), "2.3.4\n")
            self.assertEqual(json.loads((tmp / "literate.project.json").read_text())["version"], "2.3.4")
            (tmp / "VERSION").write_text("2.3.5\n")
            self.assertEqual(subprocess.run([*tool, "check"], capture_output=True).returncode, 1)
            self.assertNotEqual(subprocess.run([*tool, "set", "2.3"], capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
