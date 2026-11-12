#!/usr/bin/env python3
"""Split authoring/current controls on scratch records; no release qualification."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


legacy = module("prepare_fixture", "tests/release-prepare-fill.py")
legacy.VERSION = "1.6.0"
legacy.FEEDS = {flag: tag.replace("1.5.0", "1.6.0") for flag, tag in legacy.FEEDS.items()}
current_tool = module("split_current", "scripts/release-current.py")
helper = current_tool.media_helpers()
docs = module("split_docs", "tests/docs-release-sync.py")


class SplitFlow(unittest.TestCase):
    prepare = legacy.PrepareAndFill.prepare
    fill = legacy.PrepareAndFill.fill
    trace_tokens = legacy.PrepareAndFill.trace_tokens

    def setUp(self):
        legacy.PrepareAndFill.setUp(self)
        template = """# Planned 1.6.0
Raw @@AARCH64_ISO_RAW_BYTES@@ bytes @@AARCH64_ISO_RAW_SHA256@@
Manifest @@AARCH64_ISO_MANIFEST@@ @@AARCH64_ISO_MANIFEST_BYTES@@ @@AARCH64_ISO_MANIFEST_SHA256@@
Download @@AARCH64_ISO_DOWNLOAD_BYTES@@ bytes
@@AARCH64_ISO_PARTS_TABLE@@
"""
        (self.root / "release/templates/release-1.6.0.md").write_text(template)
        (self.root / "README.md").write_text(template)
        self.logical = "daemonarchy-1.6.0-aarch64.iso.xz"
        (self.assets / self.logical).unlink()
        (self.assets / (self.logical + ".sha256")).unlink()
        raw = Path(self.tmp.name) / self.logical.removesuffix(".xz")
        self.raw = bytes(range(256)) * 5
        raw.write_bytes(self.raw)
        packed_dir = Path(self.tmp.name) / "parts"
        self.packed = helper.split_verifier().pack(raw, hashlib.sha256(self.raw).hexdigest(), packed_dir, 313)
        for path in packed_dir.iterdir():
            path.rename(self.assets / path.name)
        self.pin = self.packed["sha256"]
        self.selection = ("--split-image", "aarch64=" + self.pin)
        self.prepare()

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def records(self):
        return (json.loads((self.root / "release/current.json").read_text()),
                json.loads((self.root / "verification/release-1.6.0.json").read_text()))

    def test_fill_typed_identity_parts_and_unambiguous_prose(self):
        self.fill(*self.selection)
        current, record = self.records()
        transport = record["image_transports"][self.logical]
        self.assertEqual(transport["raw_image"], [len(self.raw), "sha256:" + hashlib.sha256(self.raw).hexdigest()])
        self.assertNotIn(self.logical, record["assets"])
        self.assertEqual(current["assets"], record["assets"])
        selected = next(i for i in current["images"] if i["type"] == "installer" and i["arch"] == "aarch64")
        self.assertEqual(selected["transport"]["logical_asset"], self.logical)
        self.assertEqual(selected["asset"], self.packed["manifest"])
        self.assertEqual(current_tool.images("1.6.0", record["assets"], record),
                         sorted(current["images"], key=lambda i: i["asset"]))
        prose = (self.root / "README.md").read_text()
        self.assertNotIn("@@", prose)
        self.assertIn(hashlib.sha256(self.raw).hexdigest(), prose)
        for part in self.packed["parts"]:
            self.assertIn(part["name"], prose)
            self.assertIn(part["sha256"], prose)
        helper.read_record(self.root / "verification/release-1.6.0.json")
        self.assertEqual(current["published_at"], "TODO")
        self.assertIn("unverified", record["evidence_status"])

    def test_dry_run_keeps_all_prepared_files(self):
        before = self.snapshot()
        self.fill(*self.selection, "--dry-run")
        self.assertEqual(before, self.snapshot())

    def test_missing_wrong_or_duplicate_pin_refuses_before_writes(self):
        before = self.snapshot()
        for args in [(), ("--split-image", "aarch64=" + "0" * 64),
                     self.selection + self.selection, ("--split-image", "unknown=" + self.pin)]:
            with self.subTest(args=args):
                self.assertNotEqual(self.fill(*args, check=False).returncode, 0)
                self.assertEqual(before, self.snapshot())

    def test_ambiguous_old_tokens_refuse_before_writes(self):
        (self.root / "README.md").write_text("@@AARCH64_ISO_SHA256@@")
        before = self.snapshot()
        result = self.fill(*self.selection, check=False)
        self.assertIn("explicit manifest/raw/parts tokens", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_extra_asset_or_symlink_refuses_before_writes(self):
        before = self.snapshot()
        extra = self.assets / "unexpected"
        extra.write_bytes(b"extra")
        self.assertNotEqual(self.fill(*self.selection, check=False).returncode, 0)
        extra.unlink()
        path = self.assets / "daemonarchy-1.6.0.pem"
        data = path.read_bytes()
        path.unlink()
        target = Path(self.tmp.name) / "certificate"
        target.write_bytes(data)
        path.symlink_to(target)
        self.assertIn("regular file", self.fill(*self.selection, check=False).stderr)
        self.assertEqual(before, self.snapshot())

    def test_corrupt_part_refuses_before_writes(self):
        before = self.snapshot()
        part = self.assets / self.packed["parts"][0]["name"]
        part.write_bytes(b"corrupt")
        self.assertNotEqual(self.fill(*self.selection, check=False).returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_current_requires_approved_record_and_exact_published_map(self):
        self.fill(*self.selection)
        _, record = self.records()
        with patch.object(current_tool, "ROOT", self.root):
            self.assertEqual(current_tool.approved_record("1.6.0", record["assets"]), record)
            wrong = copy.deepcopy(record["assets"])
            wrong[self.packed["manifest"]][0] += 1
            with self.assertRaises(SystemExit):
                current_tool.approved_record("1.6.0", wrong)
            (self.root / "verification/release-1.6.0.json").unlink()
            with self.assertRaises(SystemExit):
                current_tool.approved_record("1.6.0", record["assets"])
        with self.assertRaises(SystemExit):
            current_tool.images("1.6.0", record["assets"])

    def test_orphan_or_competing_published_parts_are_refused(self):
        self.fill(*self.selection)
        _, record = self.records()
        with self.assertRaises(SystemExit):
            current_tool.images("1.6.0", {"daemonarchy-1.6.0-amd64.iso.part0001.xz": [1, "sha256:" + "0" * 64]})
        record["assets"][self.logical] = [1, "sha256:" + "0" * 64]
        record["assets"][self.logical + ".sha256"] = [1, "sha256:" + "0" * 64]
        with self.assertRaises(SystemExit):
            current_tool.images("1.6.0", record["assets"], record)

    def test_check_published_rejects_changed_raw_identity(self):
        self.fill(*self.selection)
        current, record = self.records()
        current["published_at"] = "2026-11-10T00:00:00Z"
        release = {"tagName": current["tag"], "publishedAt": current["published_at"],
                   "assets": [{"name": name, "size": value[0], "digest": value[1]} for name, value in current["assets"].items()]}
        with patch.object(current_tool, "ROOT", self.root), patch.object(current_tool, "published", return_value=release):
            self.assertEqual(current_tool.check_published(current), [])
            selected = next(i for i in current["images"] if "transport" in i)
            selected["transport"]["raw_image"][1] = "sha256:" + "0" * 64
            self.assertIn("transports", " ".join(current_tool.check_published(current)))

    def test_published_update_preserves_previous_transport(self):
        self.fill(*self.selection)
        current, _ = self.records()
        next_version = "1.6.1"
        (self.root / f"docs/release-{next_version}.md").write_text("Planned release")
        name = f"daemonarchy-{next_version}-amd64.iso.xz"
        release = {"tagName": "daemonarchy-" + next_version, "name": "next", "url": "https://example.invalid",
                   "publishedAt": "2026-11-10T00:00:00Z",
                   "assets": [{"name": n, "size": 1, "digest": "sha256:" + "1" * 64} for n in [name, name + ".sha256"]]}
        selected = next(i for i in current["images"] if i["type"] == "installer" and "transport" in i)
        # Make the split installer the retained primary image; both arches are still recorded.
        current["images"].remove(selected)
        current["images"].insert(0, selected)
        args = SimpleNamespace(osversion=1600029, application_feed="fixture", checkout_feed="fixture")
        with patch.object(current_tool, "ROOT", self.root), patch.object(current_tool, "published", return_value=release):
            updated = current_tool.update(current, release["tagName"], args)
        self.assertEqual(updated["previous_releases"][0]["image_transport"], selected["transport"])

    def audit_prose(self, text, current):
        root = Path(self.tmp.name) / "docs-audit"
        root.mkdir(exist_ok=True)
        (root / "README.md").write_text(text)
        return docs.audit(root, current)

    def test_docs_accept_exact_part_table_and_raw_identity(self):
        self.fill(*self.selection)
        current, _ = self.records()
        text = (self.root / "README.md").read_text()
        self.assertEqual(self.audit_prose(text, current), [])
        raw_name = self.logical.removesuffix(".xz")
        self.assertEqual(self.audit_prose(f"{raw_name} {len(self.raw):,} bytes {hashlib.sha256(self.raw).hexdigest()}", current), [])

    def test_docs_reject_another_current_parts_hash_or_wrong_size(self):
        self.fill(*self.selection)
        current, _ = self.records()
        first, second = self.packed["parts"][:2]
        text = f"{first['name']} {first['bytes']:,} bytes {second['sha256']}"
        self.assertTrue(self.audit_prose(text, current))
        text = f"{first['name']} {first['bytes'] + 1:,} bytes {first['sha256']}"
        self.assertTrue(self.audit_prose(text, current))

    def test_docs_reject_unpublished_monolith_and_old_split_checksum(self):
        self.fill(*self.selection)
        current, _ = self.records()
        url = f"https://github.com/jordanhubbard/daemonarchy/releases/download/{current['tag']}/{self.logical}"
        self.assertTrue(self.audit_prose(url, current))
        self.assertTrue(self.audit_prose("daemonarchy-1.5.0-aarch64.iso.part0001.xz.sha256", current))

    def test_reused_current_digest_is_not_automatically_stale(self):
        self.fill(*self.selection)
        current, _ = self.records()
        part = self.packed["parts"][0]
        current["previous_releases"].append({"version": "1.5.1", "image": ["older.iso.xz", part["bytes"], "sha256:" + part["sha256"]]})
        self.assertEqual(self.audit_prose(f"{part['name']} {part['bytes']:,} bytes {part['sha256']}", current), [])


if __name__ == "__main__":
    unittest.main()
