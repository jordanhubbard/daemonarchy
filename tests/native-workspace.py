#!/usr/bin/env python3
"""Actual Git deployment, upstream refresh and retained-state refusal checks."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native-workspace.py"
spec = importlib.util.spec_from_file_location("native_workspace", SCRIPT)
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class NativeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "native"
        self.origin = self.base / "origin"
        self.origin.mkdir()
        self.git(self.origin, "init", "--quiet")
        (self.origin / "input.c").write_text("original source\n")
        self.pin = self.commit("original")
        self.url = self.origin.as_uri()
        self.config = self.base / "selection.json"
        self.authored = {"schema": workspace.SCHEMA, "control_repository": self.url,
                         "trees": {name: {"repository": self.url, "upstream": self.url,
                                          "revision": self.pin} for name in ("src", "ports")}}
        self.config.write_text(json.dumps(self.authored))
        self.selected = workspace.selection(self.config, self.pin)

    def git(self, path, *args):
        return subprocess.check_output(["git", "-C", str(path), *args], text=True,
                                       stderr=subprocess.DEVNULL).strip()

    def commit(self, message):
        self.git(self.origin, "add", ".")
        self.git(self.origin, "-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                 "commit", "--quiet", "-m", message)
        return self.git(self.origin, "rev-parse", "HEAD")

    def test_independent_checkout_survives_origin_retirement(self):
        report = workspace.deploy(self.root, self.selected)
        self.assertTrue(report["ok"])
        self.assertFalse(report["selection"]["execution_qualified"])
        self.assertFalse(report["selection"]["lifecycle_receipt"])
        self.origin.rename(self.base / "retired-origin")
        self.assertTrue(workspace.inspect(self.root)["ok"])
        for name in ("control", "src", "ports"):
            path = self.root / name
            self.assertEqual((path / "input.c").read_text(), "original source\n")
            self.assertFalse((path / ".git/objects/info/alternates").exists())
            self.git(path, "fsck", "--connectivity-only")
        for name in workspace.OUTPUTS:
            self.assertTrue((self.root / name).is_dir())

    def test_upstream_refresh_preserves_selected_source_and_control(self):
        workspace.deploy(self.root, self.selected)
        (self.origin / "input.c").write_text("upstream change\n")
        upstream_pin = self.commit("upstream")
        self.git(self.root / "src", "fetch", "upstream", "HEAD")
        self.assertEqual(self.git(self.root / "src", "rev-parse", "FETCH_HEAD"), upstream_pin)
        self.assertEqual(self.git(self.root / "src", "rev-parse", "HEAD"), self.pin)
        self.assertTrue(workspace.inspect(self.root)["ok"])
        self.assertEqual((self.root / "control/input.c").read_text(), "original source\n")

    def test_existing_work_and_failed_deployments_are_preserved(self):
        self.root.mkdir()
        sentinel = self.root / "local-work"
        sentinel.write_text("retain me\n")
        with self.assertRaisesRegex(ValueError, "new or empty"):
            workspace.deploy(self.root, self.selected)
        self.assertEqual(sentinel.read_text(), "retain me\n")

    def test_failure_retains_incomplete_checkout_and_does_not_retry_over_it(self):
        self.selected["repositories"]["src"]["revision"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "git fetch failed"):
            workspace.deploy(self.root, self.selected)
        self.assertTrue((self.root / ".incomplete").exists())
        self.assertTrue((self.root / "control/input.c").is_file())
        with self.assertRaisesRegex(ValueError, "incomplete deployment"):
            workspace.inspect(self.root)
        with self.assertRaisesRegex(ValueError, "new or empty"):
            workspace.deploy(self.root, self.selected)

    def test_dirty_or_changed_selection_refuses_inspection(self):
        workspace.deploy(self.root, self.selected)
        source = self.root / "src/input.c"
        source.write_text("developer edit\n")
        with self.assertRaisesRegex(ValueError, "local changes"):
            workspace.inspect(self.root)
        self.assertEqual(source.read_text(), "developer edit\n")
        source.write_text("original source\n")
        record = self.root / "workspace.json"
        data = json.loads(record.read_text())
        data["selection"]["repositories"]["src"]["revision"] = "0" * 40
        record.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            workspace.inspect(self.root)

    def test_redirected_output_and_legacy_root_refuse(self):
        workspace.deploy(self.root, self.selected)
        objects = self.root / "obj"
        objects.rmdir()
        objects.symlink_to(self.origin, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "redirected"):
            workspace.inspect(self.root)
        for root in ("/", "/usr", "/usr/src", "/usr/src/alternate", "/usr/ports/alternate"):
            with self.subTest(root=root), self.assertRaises(ValueError):
                workspace.root_path(root)

    def test_moving_ref_credentials_and_duplicate_metadata_refuse(self):
        self.authored["trees"]["src"]["revision"] = "main"
        self.config.write_text(json.dumps(self.authored))
        with self.assertRaisesRegex(ValueError, "exact 40-character"):
            workspace.selection(self.config, self.pin)
        self.assertFalse(self.root.exists())
        with self.assertRaisesRegex(ValueError, "without credentials"):
            workspace.repository_url("https://user:secret@example.invalid/repo.git")
        self.config.write_text('{"schema":"first","schema":"second"}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            workspace.selection(self.config, self.pin)

    def test_plan_command_has_no_side_effects(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root),
                                 "--selection", str(self.config), "--control-revision", self.pin],
                                capture_output=True, text=True, check=True)
        self.assertFalse(json.loads(result.stdout)["writes"])
        self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
