#!/usr/bin/env python3
"""Offline Apple BCM4364 sources with fixture bytes; no Apple firmware is used.

The fixture replaces the pinned hashes with synthetic payloads and a fake 7-Zip
that only lists and streams. Native APFS/7-Zip behaviour on the MacBook remains
a separate hardware check.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "apple_import", ROOT / "scripts/import-apple-bcm4364-firmware.py")
importer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(importer)

FAKE_7Z = r'''#!/usr/bin/env python3
import hashlib, json, os, sys
table = json.load(open(os.environ["FAKE7Z_TABLE"]))
with open(os.environ["FAKE7Z_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
def entries(archive):
    if archive in table:
        return table[archive]
    if os.path.isfile(archive):
        with open(archive, "rb") as stream:
            return table.get("sha256:" + hashlib.sha256(stream.read()).hexdigest(), {})
    return {}
args = sys.argv[1:]
if args[:3] == ["l", "-slt", "-ba"] and len(args) == 4:
    for member in entries(args[3]):
        print("Path = " + member)
        print("Size = 1")
        print()
    sys.exit(0)
if args[:2] == ["x", "-so"] and len(args) == 4:
    source = entries(args[2]).get(args[3])
    if source is None:
        sys.exit(2)
    with open(source, "rb") as stream:
        sys.stdout.buffer.write(stream.read())
    sys.exit(0)
sys.exit(7)
'''


class OfflineFirmwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payloads = {name: ("fixture " + name).encode() * 3 for name in importer.FILES}
        files = {name: (source, len(self.payloads[name]), hashlib.sha256(self.payloads[name]).hexdigest())
                 for name, (source, _, _) in importer.FILES.items()}
        self.image = self.write("pinned.dmg", b"pinned recovery image fixture")
        patches = [mock.patch.object(importer, "FILES", files),
                   mock.patch.object(importer, "IMAGE_BYTES", self.image.stat().st_size),
                   mock.patch.object(importer, "IMAGE_SHA256", self.sha(self.image)),
                   mock.patch.object(importer, "INTERNAL_IMAGE_LIMIT", 1024 * 1024)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        (bin_dir / "7z").write_text(FAKE_7Z)
        (bin_dir / "7z").chmod(0o755)
        self.table, self.log = self.root / "table.json", self.root / "7z.log"
        env = {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
               "FAKE7Z_TABLE": str(self.table), "FAKE7Z_LOG": str(self.log)}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        self.stage = self.root / "stage"

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def firmware_members(self, prefix, payloads=None):
        payloads = payloads or self.payloads
        members = {}
        for name, (source, _, _) in importer.FILES.items():
            members[prefix + "/" + source] = str(self.write("members/" + prefix + "/" + source, payloads[name]))
        return members

    def run_import(self, *args):
        argv = ["import", *args, "--model", "MacBookPro16,1", "--destination", str(self.stage)]
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(stderr):
            status = importer.main()
        return status, stderr.getvalue()

    def provenance(self):
        importer.verify_stage(self.stage, "MacBookPro16,1")
        for name, data in self.payloads.items():
            self.assertEqual((self.stage / name).read_bytes(), data)
        return json.loads((self.stage / "provenance.json").read_text())

    def internal(self, table):
        self.table.write_text(json.dumps(table))
        with mock.patch.object(importer, "read_only_device", lambda device: None):
            return self.run_import("--internal-disk", "/dev/nda0p2")

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_pre_extracted_files_from_second_media(self):
        media = self.root / "usb/firmware"
        for name, data in self.payloads.items():
            self.write("usb/firmware/" + name, data)
        self.write("usb/firmware/README", b"extra files on the stick are ignored")
        self.assertEqual(self.run_import("--files", str(media))[0], 0)
        record = self.provenance()
        self.assertEqual(record["source_kind"], "verified-files")
        self.assertEqual(record["recovery_image_sha256"], importer.IMAGE_SHA256)
        self.assertNotIn("source_image_sha256", record)

    def test_pre_extracted_files_refuse_changed_bytes_or_symlinks(self):
        media = self.root / "usb"
        for name, data in self.payloads.items():
            self.write("usb/" + name, data)
        name = next(iter(self.payloads))
        (media / name).write_bytes(b"x" * len(self.payloads[name]))
        status, error = self.run_import("--files", str(media))
        self.assertEqual(status, 1)
        self.assertIn("hash changed", error)
        self.assertFalse(self.stage.exists())
        (media / name).unlink()
        (media / name).symlink_to(self.write("elsewhere", self.payloads[name]))
        self.assertEqual(self.run_import("--files", str(media))[0], 1)
        self.assertFalse(self.stage.exists())

    def test_internal_recovery_image_matching_the_pin(self):
        inner = self.firmware_members("macOS Base System/usr/share/firmware/wifi/C-4364__s-B3")
        status, error = self.internal({
            "/dev/nda0p2": {"Recovery/1234/BaseSystem.dmg": str(self.image),
                            "Recovery/1234/BaseSystem.chunklist": str(self.image)},
            "sha256:" + self.sha(self.image): inner})
        self.assertEqual(status, 0, error)
        record = self.provenance()
        self.assertEqual(record["source_kind"], "internal-apfs")
        self.assertEqual(record["source_image_sha256"], importer.IMAGE_SHA256)
        self.assertTrue(record["source_image_pinned"])
        self.assertIn("Recovery/1234/BaseSystem.dmg", record["source"])
        # Only listing and streaming touch the device: no extraction to disk,
        # update, delete or rename command is ever issued.
        for command in self.commands():
            self.assertIn(command[:2], (["l", "-slt"], ["x", "-so"]))

    def test_internal_recovery_of_another_build_is_accepted_only_by_file_pins(self):
        other = self.write("other.dmg", b"newer macOS recovery image")
        inner = self.firmware_members("macOS Base System/usr/share/firmware/wifi/C-4364__s-B3")
        status, error = self.internal({"/dev/nda0p2": {"Recovery/9/BaseSystem.dmg": str(other)},
                                       "sha256:" + self.sha(other): inner})
        self.assertEqual(status, 0, error)
        record = self.provenance()
        self.assertEqual(record["source_image_sha256"], self.sha(other))
        self.assertFalse(record["source_image_pinned"])
        # The selected-board identity remains the pinned image's file hashes.
        self.assertEqual(record["recovery_image_sha256"], importer.IMAGE_SHA256)

    def test_internal_changed_recovery_falls_back_to_system_volume_files(self):
        changed = {name: b"different board files" for name in self.payloads}
        other = self.write("other.dmg", b"recovery with other firmware")
        system = self.firmware_members("Macintosh HD/usr/share/firmware/wifi/C-4364__s-B3")
        device = {"Recovery/9/BaseSystem.dmg": str(other), **system}
        status, error = self.internal({
            "/dev/nda0p2": device,
            "sha256:" + self.sha(other): self.firmware_members(
                "macOS Base System/usr/share/firmware/wifi/C-4364__s-B3", changed)})
        self.assertEqual(status, 0, error)
        record = self.provenance()
        self.assertEqual(record["source"],
                         "internal APFS volume Macintosh HD/usr/share/firmware/wifi/C-4364__s-B3")
        self.assertNotIn("source_image_sha256", record)

    def test_internal_disk_without_matching_files_refuses_without_stage(self):
        status, error = self.internal({"/dev/nda0p2": {"Macintosh HD/Users/readme": str(self.image)}})
        self.assertEqual(status, 1)
        self.assertIn("no macOS recovery image", error)
        self.assertFalse(self.stage.exists())
        changed = {name: b"different board files" for name in self.payloads}
        status, error = self.internal({"/dev/nda0p2": self.firmware_members(
            "Macintosh HD/usr/share/firmware/wifi/C-4364__s-B3", changed)})
        self.assertEqual(status, 1)
        self.assertIn("no internal source matched", error)
        self.assertFalse(self.stage.exists())

    def test_internal_image_copy_is_bounded(self):
        large = self.write("large.dmg", b"x" * (importer.INTERNAL_IMAGE_LIMIT + 1))
        status, error = self.internal({"/dev/nda0p2": {"Recovery/1/BaseSystem.dmg": str(large)}})
        self.assertEqual(status, 1)
        self.assertIn("size bound", error)
        self.assertFalse(self.stage.exists())

    def test_internal_source_must_be_a_device_node(self):
        importer.read_only_device(Path("/dev/null"))
        for path in (self.image, Path("relative/disk")):
            with self.assertRaises(ValueError):
                importer.read_only_device(path)
        link = self.root / "dev-link"
        link.symlink_to("/dev/null")
        with self.assertRaises(ValueError):
            importer.read_only_device(link)
        self.assertTrue(stat.S_ISCHR(os.stat("/dev/null").st_mode))

    def test_stage_rejects_unknown_source_kind_or_malformed_observed_hash(self):
        media = self.root / "usb"
        for name, data in self.payloads.items():
            self.write("usb/" + name, data)
        self.assertEqual(self.run_import("--files", str(media))[0], 0)
        manifest = self.stage / "provenance.json"
        original = json.loads(manifest.read_text())
        for change in ({"source_kind": "network-share"}, {"source_image_sha256": "abc"},
                       {"source_image_pinned": "yes"}):
            manifest.write_text(json.dumps(dict(original, **change)))
            with self.assertRaises(ValueError):
                importer.verify_stage(self.stage, "MacBookPro16,1")

    def test_sources_are_mutually_exclusive(self):
        with mock.patch.object(sys, "argv", ["import", "--files", "/a", "--download", "--model",
                                             "MacBookPro16,1", "--destination", str(self.stage)]), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                importer.main()


if __name__ == "__main__":
    unittest.main()
