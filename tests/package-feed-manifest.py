#!/usr/bin/env python3
"""The application feed is staged for the safe uploader: checked, hard-linked, manifested."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manifest = load("manifest", "package-feed-manifest.py")
uploader = load("uploader", "package-feed-upload.py")
ZSTD = b"\x28\xb5\x2f\xfd"


def make_feed(directory, packages=("a-1.pkg", "b-2.pkg"), plain=()):
    directory.mkdir(parents=True)
    for name in packages:
        (directory / name).write_bytes(ZSTD + name.encode())
    for name in ("packagesite.pkg", "data.pkg"):
        (directory / name).write_bytes(ZSTD + name.encode())
    for name in ("meta", "meta.conf"):
        (directory / name).write_text("version = 2;\n")
    for name in plain:
        (directory / name).write_bytes(b"not compressed")


class FeedManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.feed = self.tmp / "feed"
        self.out = self.tmp / "out"

    def test_manifest_lists_every_asset_and_uploader_orders_packages_first(self):
        make_feed(self.feed)
        result = manifest.stage(self.feed, "packages-16-amd64-1.4.1", self.out, "Daemonarchy packages (amd64)")
        self.assertEqual({a["name"] for a in result["assets"]},
                         {"a-1.pkg", "b-2.pkg", "meta", "meta.conf", "packagesite.pkg", "data.pkg"})
        saved = json.loads((self.out / "packages-16-amd64-1.4.1.manifest.json").read_text())
        self.assertEqual(saved["title"], "Daemonarchy packages (amd64)")
        packages, catalogue = uploader.upload_order(saved)
        self.assertEqual(packages, ["a-1.pkg", "b-2.pkg"])
        self.assertEqual(catalogue[-2:], ["packagesite.pkg", "data.pkg"])
        self.assertEqual(os.stat(self.feed / "a-1.pkg").st_ino, os.stat(self.out / "packages-16-amd64-1.4.1" / "a-1.pkg").st_ino)

    def test_refuses_uncompressed_packages_bad_tags_and_a_second_staging(self):
        make_feed(self.feed, plain=("c-3.pkg",))
        with self.assertRaises(SystemExit):
            manifest.stage(self.feed, "packages-16-amd64-1.4.1", self.out)
        (self.feed / "c-3.pkg").write_bytes(ZSTD)
        for bad in ("packages-16-amd64", "latest", "packages-16-amd64-1.4"):
            with self.assertRaises(SystemExit):
                manifest.stage(self.feed, bad, self.out)
        manifest.stage(self.feed, "packages-16-amd64-1.4.1", self.out)
        with self.assertRaises(SystemExit):
            manifest.stage(self.feed, "packages-16-amd64-1.4.1", self.out)

    def test_refuses_a_feed_without_its_catalogue(self):
        make_feed(self.feed)
        (self.feed / "data.pkg").unlink()
        with self.assertRaises(SystemExit):
            manifest.stage(self.feed, "packages-16-amd64-1.4.1", self.out)


if __name__ == "__main__":
    unittest.main()
