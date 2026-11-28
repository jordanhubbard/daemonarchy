#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Exercise preservation of the selected boot files and staging boundaries."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "root_overlay", Path(__file__).resolve().parents[1] / "tools/hwtrace/root-overlay.py"
)
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


class OverlayPreservation(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.source, self.target = self.base / "source", self.base / "target"
        self.source.mkdir()
        self.target.mkdir()

    def test_additive_file_and_existing_directory(self):
        (self.source / "etc").mkdir()
        (self.target / "etc").mkdir()
        (self.source / "etc/control").write_bytes(b"new runtime\n")
        (self.source / "etc/control").chmod(0o555)
        records = overlay.apply_overlay(self.source, self.target)
        self.assertEqual((self.target / "etc/control").read_bytes(), b"new runtime\n")
        self.assertEqual((self.target / "etc/control").stat().st_mode & 0o777, 0o555)
        self.assertEqual(list(records), ["etc/control"])

    def test_kernel_replacement_refused_before_any_copy(self):
        (self.source / "aaa").write_text("must not be copied")
        (self.source / "kernel").write_bytes(b"replacement")
        (self.target / "kernel").write_bytes(b"selected kernel")
        with self.assertRaises(ValueError):
            overlay.apply_overlay(self.source, self.target)
        self.assertEqual((self.target / "kernel").read_bytes(), b"selected kernel")
        self.assertFalse((self.target / "aaa").exists())

    def test_existing_rescue_link_cannot_redirect_write(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.target / "bin").symlink_to(outside, target_is_directory=True)
        (self.source / "bin").mkdir()
        (self.source / "bin/control").write_text("escape")
        with self.assertRaises(ValueError):
            overlay.apply_overlay(self.source, self.target)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlink_refused(self):
        (self.source / "link").symlink_to("/etc/passwd")
        with self.assertRaises(ValueError):
            overlay.apply_overlay(self.source, self.target)

    def test_privileged_mode_refused(self):
        (self.source / "control").write_bytes(b"control")
        (self.source / "control").chmod(0o4755)
        with self.assertRaises(ValueError):
            overlay.apply_overlay(self.source, self.target)


if __name__ == "__main__":
    unittest.main()
