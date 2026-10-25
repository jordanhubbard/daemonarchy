#!/usr/bin/env python3
"""Metadata-only regression checks; no native qualification claims."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("reuse", Path(__file__).resolve().parents[1] / "scripts/package-reuse-inventory.py")
reuse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reuse)


def package(name):
    return dict(name=name, origin="category/" + name, version="1", artifact=dict(
        path=name + "-1.pkg", sha256="sha256:" + "a" * 64, bytes=100),
        identities={key: {} for key in reuse.IDENTITIES})


def snapshot(rows):
    return dict(schema=reuse.SCHEMA, packages=rows)


class ReuseTests(unittest.TestCase):
    def compare(self, before, after):
        return reuse.compare(snapshot(before), snapshot(after))

    def test_unchanged_bytes_and_identity_still_require_verification(self):
        row = package("chromium")
        result = self.compare([row], [copy.deepcopy(row)])
        self.assertEqual(result["counts"], {"needs_retained_byte_verification": 1})
        self.assertEqual(result["admitted_cache_hits"], 0)
        self.assertIsNone(result["measured_bytes_saved"])

    def test_osversion_and_runtime_changes_requalify_browsers_and_obs(self):
        for name in ("chromium", "cef", "obs-studio"):
            for key in ("osversion", "runtime_dependencies", "runtime_abi_contracts"):
                with self.subTest(name=name, key=key):
                    before = package(name)
                    after = copy.deepcopy(before)
                    after["identities"][key] = "changed"
                    # Known runtime changes never become blanket compilation, even with graph gaps.
                    after["identities"]["toolchain"] = None
                    result = self.compare([before], [after])["packages"][0]
                    self.assertEqual(result["decision"], "needs_requalification")
                    self.assertIn("toolchain", result["unknown_identities"])
                    self.assertFalse(result["admitted_cache_hit"])

    def test_changed_libreoffice_and_each_build_input_require_rebuild(self):
        for key in reuse.BUILD:
            before = package("libreoffice")
            after = copy.deepcopy(before)
            after["identities"][key] = "changed"
            self.assertEqual(self.compare([before], [after])["packages"][0]["decision"], "rebuild_required")

    def test_package_version_alone_does_not_schedule_compilation(self):
        before = package("libreoffice")
        after = copy.deepcopy(before)
        after["version"] = "2"
        self.assertEqual(self.compare([before], [after])["packages"][0]["decision"], "needs_package_review")
        after["identities"]["port_inputs"] = "changed"
        self.assertEqual(self.compare([before], [after])["packages"][0]["decision"], "rebuild_required")

    def test_unknown_identity_never_admits_reuse(self):
        for key in reuse.IDENTITIES:
            before = package("chromium")
            before["identities"].pop(key)
            result = self.compare([before], [copy.deepcopy(before)])["packages"][0]
            self.assertEqual(result["decision"], "blocked_missing_provenance")
            self.assertIn(key, result["reasons"])

    def test_union_includes_added_and_removed_and_rejects_duplicate_names(self):
        result = self.compare([package("old")], [package("new")])
        self.assertEqual(result["counts"], {"new_package": 1, "removed_package": 1})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.compare([package("old")] * 2, [])

    def test_missing_artifact_blocks_and_invalid_digest_refuses(self):
        before = package("old")
        before["artifact"] = None
        self.assertEqual(self.compare([before], [package("old")])["packages"][0]["decision"], "blocked_missing_artifact")
        before["artifact"] = dict(sha256="not-a-sha256", bytes=1)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.compare([before], [])

    def test_public_catalogue_join_does_not_invent_absent_identities(self):
        row = dict(name="chromium", origin="www/chromium", version="1", path="chromium-1.pkg", pkgsize=100,
                   abi="FreeBSD:16:amd64", options={}, annotations={"FreeBSD_version": "1600028"})
        assets = dict(assets=[dict(name="chromium-1.pkg", size=100, digest="sha256:" + "a" * 64)])
        result = reuse.catalogue([row], assets)
        identities = result["packages"][0]["identities"]
        self.assertIsNone(identities["runtime_dependencies"])
        self.assertIsNone(identities["port_inputs"])
        self.assertIsNone(identities["flavor"])
        self.assertEqual(identities["options"], {})
        for mutate in ("size", "digest"):
            damaged = copy.deepcopy(assets)
            damaged["assets"][0][mutate] = 999
            with self.assertRaises(ValueError):
                reuse.catalogue([row], damaged)
        with self.assertRaisesRegex(ValueError, "duplicated"):
            reuse.catalogue([row, row], assets)
        extra = copy.deepcopy(assets)
        extra["assets"].append(dict(name="unlisted.pkg", size=1))
        with self.assertRaisesRegex(ValueError, "absent from catalogue"):
            reuse.catalogue([row], extra)


if __name__ == "__main__":
    unittest.main()
