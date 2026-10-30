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

    def record(self, certificate, version="1.3.1", iso=None, isos=None, architectures=None,
               hwtrace=None):
        isos = isos or [iso or f"daemonarchy-{version}-amd64.iso"]
        if hwtrace is not None:
            isos = isos + [f"daemonarchy-hwtrace-{version}-amd64.img.xz"]
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
        if hwtrace is not None:
            record["hwtrace"] = hwtrace
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


class ClosureFeeds(ReleaseAssetNames):
    CERT = "daemonarchy-1.4.1.pem"
    ISO = "daemonarchy-1.4.1-amd64.iso.xz"

    def feed(self, tag="packages-16-amd64-1.4.1-upstream", extra=None, drop=()):
        names = ["bash-5.3.9.pkg", "meta", "meta.conf", "data.pkg", "packagesite.pkg"]
        assets = {n: [10, "sha256:" + "d" * 64] for n in names if n not in drop}
        assets.update(extra or {})
        return {"tag": tag, "assets": assets}

    def write(self, feeds="unset"):
        record = self.record(self.CERT, "1.4.1", self.ISO)
        if feeds != "unset":
            record["closure_feeds"] = feeds
        self.path.write_text(json.dumps(record) + "\n")
        return record

    def test_141_requires_closure_feeds(self):
        self.write()
        with self.assertRaisesRegex(ValueError, "must record the closure feeds"):
            assets.read_record(self.path)

    def test_140_and_earlier_need_none(self):
        self.record("daemonarchy-1.4.0.pem", "1.4.0", "daemonarchy-1.4.0-amd64.iso.xz")
        assets.read_record(self.path)

    def test_valid_closure_feed_is_accepted(self):
        self.write([self.feed()])
        record, _ = assets.read_record(self.path)
        self.assertEqual(list(assets.closure_feeds(record)), ["packages-16-amd64-1.4.1-upstream"])

    def test_bad_feeds_are_refused(self):
        cases = {
            "tag": [self.feed(tag="latest")],
            "duplicate": [self.feed(), self.feed()],
            "raw payload": [self.feed(extra={"bash.txz": [1, "sha256:" + "d" * 64]})],
            "raw iso": [self.feed(extra={"image.iso": [1, "sha256:" + "d" * 64]})],
            "no catalogue": [self.feed(drop=("data.pkg",))],
            "no meta.conf": [self.feed(drop=("meta.conf",))],
            "wrong architecture": [self.feed(tag="packages-16-aarch64-1.4.1-upstream")],
            "bad digest": [self.feed(extra={"zstd-1.pkg": [1, "sha256:zz"]})],
            "empty": [],
        }
        for label, feeds in cases.items():
            self.write(feeds)
            with self.subTest(label), self.assertRaises(ValueError):
                assets.read_record(self.path)

    def test_published_check_pages_through_hundreds_of_assets(self):
        names = [f"p{n}-1.pkg" for n in range(250)] + ["data.pkg", "meta", "meta.conf"]
        feed = {"tag": "packages-16-amd64-1.4.1-upstream", "assets": {n: [5, "sha256:" + "e" * 64] for n in names}}
        self.write([feed])
        record, _ = assets.read_record(self.path)
        listing = [{"name": n, "size": 5, "digest": "sha256:" + "e" * 64, "state": "uploaded"} for n in names]
        pages = []

        def fake(path):
            if path.startswith("releases/tags/"):
                return {"tag_name": feed["tag"], "draft": False, "id": 7}
            page = int(path.rsplit("page=", 1)[1])
            pages.append(page)
            return listing[(page - 1) * 100: page * 100]

        original = assets.github
        try:
            assets.github = fake
            assets.verify_published_closure(record, {"id": 99})
            self.assertEqual(pages, [1, 2, 3])
            listing[3]["state"] = "starter"
            with self.assertRaisesRegex(ValueError, "incomplete"):
                assets.verify_published_closure(record, {"id": 99})
            listing[3]["state"] = "uploaded"
            with self.assertRaisesRegex(ValueError, "non-latest"):
                assets.verify_published_closure(record, {"id": 7})
        finally:
            assets.github = original

    def test_staged_feed_must_match_and_hold_no_private_key(self):
        feed = self.feed()
        base = Path(self.temporary.name) / "closure"
        shard = base / feed["tag"]
        shard.mkdir(parents=True)
        for name in list(feed["assets"]):
            content = b"x" * 10
            (shard / name).write_bytes(content)
            feed["assets"][name] = [len(content), "sha256:" + hashlib.sha256(content).hexdigest()]
        self.write([feed])
        record, _ = assets.read_record(self.path)
        feeds = assets.closure_feeds(record)
        subprocess = __import__("subprocess")
        original = subprocess.run
        try:   # data.pkg/packagesite.pkg here are not real archives: stub tar to an empty readable member
            assets.subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a, 0, b"", b"")
            assets.verify_closure_directory(feeds, base)
            (shard / "extra.pkg").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "differ from the record"):
                assets.verify_closure_directory(feeds, base)
            (shard / "extra.pkg").unlink()
            (shard / "meta.conf").write_bytes(b"-----BEGIN PRIVATE KEY-----")
            with self.assertRaisesRegex(ValueError, "size or type differs|digest differs"):
                assets.verify_closure_directory(feeds, base)
        finally:
            assets.subprocess.run = original
        with self.assertRaisesRegex(ValueError, "pass --closure-assets"):
            assets.verify_closure_directory(feeds, None)


class HardwareTraceImage(ReleaseAssetNames):
    def test_140_may_publish_hwtrace_image(self):
        self.record("daemonarchy-1.4.0.pem", "1.4.0", "daemonarchy-1.4.0-amd64.iso.xz",
                    hwtrace=["amd64"])
        record, _ = assets.read_record(self.path)
        self.assertEqual(assets.hwtrace_assets(record),
                         ["daemonarchy-hwtrace-1.4.0-amd64.img.xz"])

    def test_hwtrace_image_without_declaration_refused(self):
        record = self.record("daemonarchy-1.4.0.pem", "1.4.0", "daemonarchy-1.4.0-amd64.iso.xz",
                             hwtrace=["amd64"])
        del record["hwtrace"]
        self.path.write_text(json.dumps(record) + "\n")
        with self.assertRaisesRegex(ValueError, "incomplete or unexpected"):
            assets.read_record(self.path)

    def test_hwtrace_before_140_or_other_arch_refused(self):
        self.record("daemonarchy-1.3.1.pem", hwtrace=["amd64"])
        with self.assertRaisesRegex(ValueError, "predates hardware trace"):
            assets.read_record(self.path)
        self.record("daemonarchy-1.4.0.pem", "1.4.0", "daemonarchy-1.4.0-amd64.iso.xz",
                    hwtrace=["aarch64"])
        with self.assertRaisesRegex(ValueError, "listed as"):
            assets.read_record(self.path)


if __name__ == "__main__":
    unittest.main()
