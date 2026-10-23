"""Signed archive and offline-tree failure checks; native BE tests are separate."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "maintenance", Path(__file__).resolve().parents[1] / "maintenance.py")
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


class Maintenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = tempfile.TemporaryDirectory()
        cls.keys = Path(cls.material.name)
        cls.key, cls.cert = cls.keys / "key", cls.keys / "cert.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "1", "-subj", "/CN=Disposable bundle test/",
                        "-keyout", str(cls.key), "-out", str(cls.cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        cls.material.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.bundle, self.sig = self.work / "bundle.txz", self.work / "bundle.sig"
        self.contents = {name: name.encode() for name in maintenance.MANAGED}
        self.contents["boot/manifest"] = b"kernel.secure/kernel sha256=" + hashlib.sha256(
            self.contents["boot/kernel.secure/kernel"]).hexdigest().encode() + b"\n"
        self.contents["boot/runtime.manifest"] = b"/boot/kernel.secure/kernel sha256=" + hashlib.sha256(
            self.contents["boot/kernel.secure/kernel"]).hexdigest().encode() + b"\n"
        self.metadata = dict(schema=1, loader_protocol=1, base_source=maintenance.BASE,
                             osversion=1600028, stock_kernel_sha256=hashlib.sha256(b"stock").hexdigest(),
                             files={name: hashlib.sha256(data).hexdigest()
                                    for name, data in self.contents.items()})

    def archive(self, extra=None):
        contents = dict(self.contents, **{"bundle.json": json.dumps(self.metadata).encode()})
        contents.update(extra or {})
        with tarfile.open(self.bundle, "w:xz") as archive:
            for name, data in contents.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(self.key),
                        "-out", str(self.sig), str(self.bundle)], check=True)

    def unpack(self):
        destination = self.work / "staged"
        destination.mkdir()
        metadata = maintenance.unpack(self.bundle, self.sig, self.cert, destination)
        return destination, metadata

    def target(self):
        target = self.work / "target"
        (target / "boot/kernel").mkdir(parents=True)
        (target / "boot/kernel/kernel").write_bytes(b"stock")
        return target

    def test_signed_offline_install_and_verify(self):
        self.archive()
        source, metadata = self.unpack()
        target = self.target()
        maintenance.install(target, source, metadata)
        maintenance.verify_tree(target, metadata)
        (target / "boot/kernel.secure/kernel").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            maintenance.verify_tree(target, metadata)

    def test_selected_macbook_source_and_osversion(self):
        self.metadata["base_source"] = "02984cfbe95c063f130ae20d7ea6ed520df88a8f"
        self.metadata["osversion"] = 1600029
        self.archive()
        _, metadata = self.unpack()
        self.assertEqual(metadata["osversion"], 1600029)

    def test_selected_macbook_source_rejects_old_osversion(self):
        self.metadata["base_source"] = "02984cfbe95c063f130ae20d7ea6ed520df88a8f"
        self.archive()
        with self.assertRaisesRegex(ValueError, "Unsupported boot bundle"):
            self.unpack()

    def test_altered_archive_fails_before_extraction(self):
        self.archive()
        with self.bundle.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaises(subprocess.CalledProcessError):
            self.unpack()
        self.assertEqual(list((self.work / "staged").iterdir()), [])

    def test_install_into_mountpoint_under_private_staging_directory(self):
        self.archive()
        source, metadata = self.unpack()
        target = source / "mounted-be"
        (target / "boot/kernel").mkdir(parents=True)
        (target / "boot/kernel/kernel").write_bytes(b"stock")
        maintenance.install(target, source, metadata)
        maintenance.verify_tree(target, metadata)

    def test_signed_archive_path_escape(self):
        self.archive({"../../outside": b"escape"})
        with self.assertRaisesRegex(ValueError, "unexpected paths"):
            self.unpack()

    def test_signed_wrong_snapshot(self):
        self.metadata["base_source"] = "0" * 40
        self.archive()
        with self.assertRaisesRegex(ValueError, "snapshot"):
            self.unpack()

    def test_digest_mismatch(self):
        self.contents["boot/loader.efi"] = b"changed after hashing"
        self.archive()
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.unpack()

    def test_target_snapshot_mismatch_preserves_target(self):
        self.archive()
        source, metadata = self.unpack()
        target = self.target()
        (target / "boot/kernel/kernel").write_bytes(b"another snapshot")
        with self.assertRaisesRegex(ValueError, "snapshot"):
            maintenance.install(target, source, metadata)
        self.assertFalse((target / "boot/loader.efi").exists())

    def test_target_directory_escape(self):
        self.archive()
        source, metadata = self.unpack()
        target = self.target()
        outside = self.work / "outside"
        outside.mkdir()
        (target / "boot/kernel.secure").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            maintenance.install(target, source, metadata)
        self.assertEqual(list(outside.iterdir()), [])

    def test_unsigned_installed_module_prevents_activation_validation(self):
        self.archive()
        source, metadata = self.unpack()
        target = self.target()
        maintenance.install(target, source, metadata)
        (target / "boot/modules").mkdir()
        (target / "boot/modules/extra.ko").write_bytes(b"unsigned")
        with self.assertRaisesRegex(ValueError, "absent from the signed inventory"):
            maintenance.verify_tree(target, metadata)

    def test_optional_signed_firmware_is_required_on_macbook_target(self):
        payloads = {name: name.encode() for name in maintenance.APPLE_BCM4364}
        self.contents["boot/manifest"] += "".join(
            f"{name.removeprefix('boot/')} sha256={hashlib.sha256(data).hexdigest()}\n"
            for name, data in sorted(payloads.items())).encode()
        self.contents["boot/runtime.manifest"] += "".join(
            f"/{name} sha256={hashlib.sha256(data).hexdigest()}\n"
            for name, data in sorted(payloads.items())).encode()
        self.metadata["files"]["boot/manifest"] = hashlib.sha256(
            self.contents["boot/manifest"]).hexdigest()
        self.metadata["files"]["boot/runtime.manifest"] = hashlib.sha256(
            self.contents["boot/runtime.manifest"]).hexdigest()
        self.archive()
        source, metadata = self.unpack()
        target = self.target()
        maintenance.install(target, source, metadata)
        maintenance.verify_tree(target, metadata)
        with self.assertRaisesRegex(ValueError, "Required MacBook firmware is missing"):
            maintenance.verify_tree(target, metadata, require_apple_bcm4364=True)
        for name, data in payloads.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "provenance"):
            maintenance.verify_tree(target, metadata, require_apple_bcm4364=True)
        provenance = target / "var/db/daemonarchy/firmware/provenance.json"
        provenance.parent.mkdir(parents=True)
        provenance.write_text(json.dumps({
            "schema": "daemonarchy/apple-recovery-firmware@1",
            "model": "MacBookPro16,1",
            "pci_device": "14e4:4464",
            "apple_subsystem": "106b:07bf",
            "recovery_image_sha256": maintenance.APPLE_IMAGE_SHA256,
            "files": {name.removeprefix("boot/firmware/"): hashlib.sha256(data).hexdigest()
                      for name, data in payloads.items()},
        }))
        maintenance.verify_tree(target, metadata, require_apple_bcm4364=True)
        (target / next(iter(payloads))).write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "Signed fingerprint mismatch"):
            maintenance.verify_tree(target, metadata, require_apple_bcm4364=True)

    def test_unsigned_macbook_firmware_prevents_validation(self):
        self.archive()
        source, metadata = self.unpack()
        target = self.target()
        maintenance.install(target, source, metadata)
        path = target / "boot/firmware/brcmfmac4364b3-pcie.bin"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"unsigned")
        with self.assertRaisesRegex(ValueError, "absent from the signed inventory"):
            maintenance.verify_tree(target, metadata)


if __name__ == "__main__":
    unittest.main()
