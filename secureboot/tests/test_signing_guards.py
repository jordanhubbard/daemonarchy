"""Authoring safety checks; real firmware/kernel checks use runtime serial logs."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

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
            key=self.keys / "first.key", certificate=self.keys / "first.pem")

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

    def test_esp_excluded(self):
        (self.root / "boot/efi/EFI/Microsoft").mkdir(parents=True)
        (self.root / "boot/efi/EFI/Microsoft/bootmgfw.efi").write_bytes(b"other OS")
        self.assertEqual(sorted(name for name, _ in signer.inventory(self.root)),
                         ["kernel/kernel", "manifest"])


if __name__ == "__main__":
    unittest.main()
