"""Authoring safety checks; real firmware/kernel checks use runtime serial logs."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "sign_boot_tree", Path(__file__).resolve().parents[1] / "sign-boot-tree.py")
signer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signer)


class SigningGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = tempfile.TemporaryDirectory(prefix="signing-guard-keys-")
        cls.keys = Path(cls.material.name)
        for name in ("first", "other"):
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-days", "1", "-subj", "/CN=Disposable authoring guard test/",
                "-keyout", str(cls.keys / (name + ".key")),
                "-out", str(cls.keys / (name + ".pem")),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (cls.keys / (name + ".key")).chmod(0o600)

    @classmethod
    def tearDownClass(cls):
        cls.material.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="signing-guard-tree-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "image"
        (self.root / "boot/kernel").mkdir(parents=True)
        (self.root / "boot/kernel/kernel").write_bytes(b"non-executable fixture")
        (self.root / "boot/manifest").write_bytes(b"unchanged")
        self.args = argparse.Namespace(
            root=self.root, loader=self.keys / "not-a-loader",
            key=self.keys / "first.key", certificate=self.keys / "first.pem",
            kernel_path="kernel/kernel", module_inventory=None, build_receipt=None)

    def reject(self, reason):
        with self.assertRaisesRegex(ValueError, reason):
            signer.sign(self.args)
        self.assertEqual((self.root / "boot/manifest").read_bytes(), b"unchanged")

    def test_running_root(self):
        self.args.root = Path("/")
        self.reject("running root")

    def test_symlink_root(self):
        alias = Path(self.temp.name) / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        self.args.root = alias
        self.reject("must not be a symlink")

    def test_key_inside_image(self):
        # A harmless placeholder proves rejection occurs before key parsing.
        self.args.key = self.root / "key"
        self.args.key.write_bytes(b"not a private key")
        self.args.key.chmod(0o600)
        self.reject("outside the image")

    def test_readable_key(self):
        self.args.key = Path(self.temp.name) / "readable.key"
        self.args.key.write_bytes(b"not a private key")
        self.args.key.chmod(0o644)
        self.reject("group or other")

    def test_private_material_in_certificate_input(self):
        self.args.certificate = Path(self.temp.name) / "bad.pem"
        self.args.certificate.write_bytes(b"-----BEGIN PRIVATE KEY-----\nfixture")
        self.reject("public material only")

    def test_mismatched_certificate(self):
        self.args.certificate = self.keys / "other.pem"
        self.reject("does not match")

    def test_symlink_file_escape(self):
        outside = Path(self.temp.name) / "outside"
        outside.write_bytes(b"outside the image")
        (self.root / "boot/escape").symlink_to(outside)
        self.reject("regular files inside /boot")

    def test_symlink_directory_escape(self):
        (self.root / "boot/modules").symlink_to(self.keys, target_is_directory=True)
        self.reject("Symlinked boot directories")

    def test_verification_disable_file(self):
        (self.root / "boot/loader.ve.off").touch()
        self.reject("Verification-control files")

    def test_inventory_path_escape(self):
        self.args.module_inventory = Path(self.temp.name) / "modules.json"
        self.args.module_inventory.write_text(json.dumps(dict(
            schema=1, osversion=1600028,
            modules={"/boot/modules/../../escape.ko": "a" * 64})))
        self.reject("Invalid signed module inventory entry")

    def test_inventory_bad_fingerprint(self):
        self.args.module_inventory = Path(self.temp.name) / "modules.json"
        self.args.module_inventory.write_text(json.dumps(dict(
            schema=1, osversion=1600028, modules={"/boot/modules/driver.ko": "invalid"})))
        self.reject("Invalid signed module inventory entry")

    def test_inventory_wrong_snapshot(self):
        self.args.module_inventory = Path(self.temp.name) / "modules.json"
        self.args.module_inventory.write_text(json.dumps(dict(
            schema=1, osversion=1600027, modules={})))
        self.reject("Unsupported release module inventory")

    def test_build_receipt_required(self):
        self.reject("matching kernel/loader build receipt is required")

    def test_esp_excluded(self):
        (self.root / "boot/efi/EFI/Microsoft").mkdir(parents=True)
        (self.root / "boot/efi/EFI/Microsoft/bootmgfw.efi").write_bytes(b"other OS")
        self.assertEqual(sorted(name for name, _ in signer.inventory(self.root)),
                         ["kernel/kernel", "manifest"])

    def test_private_firmware_hash_enters_both_signed_manifests_without_bytes(self):
        self.args.loader = Path(self.temp.name) / "loader_lua.efi"
        self.args.loader.write_bytes(b"disposable unsigned loader fixture")
        patches = Path(signer.__file__).resolve().parent / "patches"
        receipt = {
            "schema": 1,
            "loader_options": [
                "WITH_LOADER_VERIEXEC=yes", "WITH_LOADER_EFI_SECUREBOOT=yes",
                "WITH_LOADER_VERIEXEC_PASS_MANIFEST=yes", "VE_SELF_TESTS=yes",
                "WITHOUT_LOADER_VERIEXEC_TESTING=yes",
                "WITHOUT_LOADER_VERIEXEC_VECTX=yes",
            ],
            "kernel_sha256": signer.digest(self.root / "boot/kernel/kernel"),
            "unsigned_loader_sha256": signer.digest(self.args.loader),
            "trust_anchor_sha256": signer.digest(self.args.certificate),
            "source_patch_sha256": signer.digest(patches / "module-policy.patch"),
            "loader_patch_sha256": signer.digest(patches / "loader-rootpool.patch"),
            "optional_verification_patch_sha256": signer.digest(
                patches / "efi-optional-verification.patch"),
            "cd9660_patch_sha256": signer.digest(patches / "cd9660-verification.patch"),
        }
        self.args.build_receipt = Path(self.temp.name) / "build.json"
        self.args.build_receipt.write_text(json.dumps(receipt))
        original_run = signer.run

        def test_run(*command, **kwargs):
            if command[0] == "uefisign":
                shutil.copyfile(command[-1], command[command.index("-o") + 1])
                return subprocess.CompletedProcess(command, 0)
            return original_run(*command, **kwargs)

        fingerprint = "a" * 64
        with patch.object(signer, "optional_apple_firmware",
                          return_value={"firmware/test-board.bin": fingerprint}), \
                patch.object(signer, "run", side_effect=test_run):
            signer.sign(self.args)
        self.assertIn(f"firmware/test-board.bin sha256={fingerprint}\n",
                      (self.root / "boot/manifest").read_text())
        self.assertIn(f"/boot/firmware/test-board.bin sha256={fingerprint}\n",
                      (self.root / "boot/runtime.manifest").read_text())
        self.assertFalse((self.root / "boot/firmware/test-board.bin").exists())


if __name__ == "__main__":
    unittest.main()
