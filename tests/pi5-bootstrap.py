#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Reject wrong board and architecture inputs before staging Pi 5 boot media."""
import hashlib
import json
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pi5_bootstrap", ROOT / "tools/hwtrace/pi5-bootstrap.py")
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class Inputs(unittest.TestCase):
    def test_wrong_elf_architecture_and_endianness_are_rejected(self):
        data = bytearray(64)
        data[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", data, 18, 183)
        self.assertTrue(bootstrap.elf_aarch64(data))
        struct.pack_into("<H", data, 18, 62)
        self.assertFalse(bootstrap.elf_aarch64(data))
        struct.pack_into("<H", data, 18, 183)
        data[5] = 2
        self.assertFalse(bootstrap.elf_aarch64(data))

    def test_efi_mz_alone_is_insufficient(self):
        self.assertFalse(bootstrap.pe_aarch64(b"MZ" + bytes(300)))
        data = bytearray(128)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 60, 64)
        data[64:68] = b"PE\0\0"
        struct.pack_into("<H", data, 68, 0xaa64)
        struct.pack_into("<H", data, 88, 0x20b)
        self.assertTrue(bootstrap.pe_aarch64(data))
        struct.pack_into("<H", data, 68, 0x8664)
        self.assertFalse(bootstrap.pe_aarch64(data))

    def test_hash_mismatch_and_device_input_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input"
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                bootstrap.checked(path, "0" * 64, 20)
        with self.assertRaisesRegex(ValueError, "bounded regular"):
            bootstrap.regular(Path("/dev/null"), 100)

    @unittest.skipUnless(shutil.which("dtc") and shutil.which("fdtget"), "device-tree tools unavailable")
    def test_pi4_and_other_pi5_board_cannot_supply_pi500_fdt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "board.dtb"
            for compatible, soc, accepted in (("raspberrypi,4-model-b", "brcm,bcm2711", False),
                                              ("raspberrypi,5-model-b", "brcm,bcm2712", False),
                                              ("raspberrypi,500", "brcm,bcm2712", True)):
                source = f'/dts-v1/; / {{ compatible = "{compatible}", "{soc}"; }};'
                subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(path)],
                               input=source.encode(), check=True)
                if accepted:
                    self.assertEqual(bootstrap.validate_dtb(path, "pi500"), [compatible, soc])
                else:
                    with self.assertRaisesRegex(ValueError, "does not match"):
                        bootstrap.validate_dtb(path, "pi500")

    def test_truncated_fdt_is_rejected_before_tool_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "board.dtb"
            path.write_bytes(struct.pack(">II", 0xd00dfeed, 4096) + bytes(32))
            with self.assertRaisesRegex(ValueError, "invalid FDT size"):
                bootstrap.validate_dtb(path, "pi500")


class MemoryProfiles(unittest.TestCase):
    def bundle(self, root, cap="3G", legacy=False):
        loader, queue = bootstrap.memory_inputs(cap, "pi500")
        (root / "boot").mkdir()
        (root / "boot/loader.conf.local").write_bytes(loader)
        if not legacy:
            (root / "queue.txt").write_bytes(queue)
        manifest = {"schema": "daemonarchy/pi5-bootstrap-bundle@1", "board": "pi500", "files": {}}
        if not legacy:
            manifest["memory_profile"] = bootstrap.memory_profile(cap)
        for path in root.rglob("*"):
            if path.is_file():
                data = path.read_bytes()
                manifest["files"][path.relative_to(root).as_posix()] = {
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        self.save(root, manifest)
        return manifest

    def save(self, root, manifest):
        (root / "manifest.json").write_text(json.dumps(manifest))

    def rehash(self, root, manifest, name):
        data = (root / name).read_bytes()
        manifest["files"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        self.save(root, manifest)

    def test_default_and_uncapped_config_queue_are_distinct(self):
        for cap in bootstrap.MEMORY_CAPS:
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.bundle(root, cap)
                verified = bootstrap.verify_bundle(root, cap)
                self.assertFalse(verified["memory_profile"]["runtime_memory_verified"])
                loader = (root / "boot/loader.conf.local").read_text()
                self.assertEqual('hw.physmem="3G"' in loader, cap == "3G")
                queue = (root / "queue.txt").read_text()
                self.assertIn("hw.physmem=3G" if cap == "3G" else "unset hw.physmem", queue)
                with self.assertRaisesRegex(ValueError, "requested cap"):
                    bootstrap.verify_bundle(root, "none" if cap == "3G" else "3G")

    def test_historical_v1_bundle_defaults_only_to_three_gib(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.bundle(root, legacy=True)
            bootstrap.verify_bundle(root)
            bootstrap.verify_bundle(root, "3G")
            with self.assertRaisesRegex(ValueError, "requested cap"):
                bootstrap.verify_bundle(root, "none")

    def test_config_tamper_rejected_even_with_rehashed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.bundle(root, "none")
            with (root / "boot/loader.conf.local").open("ab") as stream:
                stream.write(b'hw.physmem="3G"\n')
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                bootstrap.verify_bundle(root)
            self.rehash(root, manifest, "boot/loader.conf.local")
            with self.assertRaisesRegex(ValueError, "loader configuration conflicts"):
                bootstrap.verify_bundle(root)

    def test_queue_tamper_rejected_even_with_rehashed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.bundle(root, "none")
            (root / "queue.txt").write_text("[mismatch]\nhw.physmem=3G\n")
            self.rehash(root, manifest, "queue.txt")
            with self.assertRaisesRegex(ValueError, "queue conflicts"):
                bootstrap.verify_bundle(root)

    def test_metadata_downgrade_cannot_make_uncapped_bundle_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.bundle(root, "none")
            del manifest["memory_profile"]
            self.save(root, manifest)
            with self.assertRaisesRegex(ValueError, "loader configuration conflicts"):
                bootstrap.verify_bundle(root)

    def test_profile_cannot_claim_base_or_runtime_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.bundle(root)
            manifest["memory_profile"]["runtime_memory_verified"] = True
            self.save(root, manifest)
            with self.assertRaisesRegex(ValueError, "profile metadata"):
                bootstrap.verify_bundle(root)

    def test_untracked_files_and_member_traversal_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.bundle(root)
            (root / "untracked").write_text("mismatch")
            with self.assertRaisesRegex(ValueError, "file inventory"):
                bootstrap.verify_bundle(root)
            (root / "untracked").unlink()
            manifest["files"]["../elsewhere"] = {"bytes": 0, "sha256": "0" * 64}
            self.save(root, manifest)
            with self.assertRaisesRegex(ValueError, "member path"):
                bootstrap.verify_bundle(root)

    def test_selected_queue_file_must_match_exact_profile_bound_bytes(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as external:
            root, selected = Path(tmp), Path(external) / "queue.txt"
            self.bundle(root, "none")
            selected.write_bytes((root / "queue.txt").read_bytes())
            bootstrap.verify_bundle(root, "none", selected)
            selected.write_text("[different]\nhw.ncpu=4\nhw.physmem=3G\n")
            with self.assertRaisesRegex(ValueError, "selected queue file"):
                bootstrap.verify_bundle(root, "none", selected)
            selected.write_bytes((root / "queue.txt").read_bytes() + b"# added\n")
            with self.assertRaisesRegex(ValueError, "selected queue file"):
                bootstrap.verify_bundle(root, "none", selected)

    def test_external_base_audit_is_bound_but_never_claimed_tool_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.bundle(root, "none")
            kernel = b"fixture kernel, not native execution"
            (root / "boot/kernel").mkdir()
            (root / "boot/kernel/kernel").write_bytes(kernel)
            self.rehash(root, manifest, "boot/kernel/kernel")
            kernel_sha = hashlib.sha256(kernel).hexdigest()
            receipt = {"schema": "daemonarchy/pi5-base-profile-audit@1", "memory_cap": "none",
                       "image_sha256": "1" * 64, "kernel_sha256": kernel_sha,
                       "loader_conf_sha256": "2" * 64, "loader_conf_local_sha256": "3" * 64}
            data = json.dumps(receipt).encode()
            (root / "base-profile-audit.json").write_bytes(data)
            self.rehash(root, manifest, "base-profile-audit.json")
            manifest["base_profile_audit"] = bootstrap.base_audit_record(data, "none", kernel_sha)
            self.save(root, manifest)
            result = bootstrap.verify_bundle(root, "none")
            self.assertFalse(result["base_profile_audit"]["ufs_verified_by_this_tool"])
            self.assertEqual(result["memory_profile"]["base_ufs_profile"], "independent-readback-required")
            for cap, digest in (("3G", kernel_sha), ("none", "0" * 64)):
                with self.assertRaisesRegex(ValueError, "disagrees"):
                    bootstrap.base_audit_record(data, cap, digest)
            receipt["loader_conf_sha256"] = "missing"
            with self.assertRaisesRegex(ValueError, "readback identities"):
                bootstrap.base_audit_record(json.dumps(receipt).encode(), "none", kernel_sha)

    def test_external_base_audit_can_record_confirmed_absent_local_config(self):
        receipt = {"schema": "daemonarchy/pi5-base-profile-audit@1", "memory_cap": "none",
                   "image_sha256": "1" * 64, "kernel_sha256": "2" * 64,
                   "loader_conf_sha256": "3" * 64, "loader_conf_local_exists": False,
                   "loader_conf_local_sha256": None}
        record = bootstrap.base_audit_record(json.dumps(receipt).encode(), "none", "2" * 64)
        self.assertFalse(record["ufs_verified_by_this_tool"])
        for exists, digest in ((True, None), (False, "4" * 64)):
            receipt.update(loader_conf_local_exists=exists, loader_conf_local_sha256=digest)
            with self.assertRaises(ValueError):
                bootstrap.base_audit_record(json.dumps(receipt).encode(), "none", "2" * 64)

    def test_cli_validation_accepts_legacy_and_refuses_explicit_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.bundle(root, legacy=True)
            command = ["python3", str(ROOT / "tools/hwtrace/pi5-bootstrap.py"), "--verify-bundle", str(root)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)["base_ufs_verified"])
            refused = subprocess.run(command + ["--memory-cap", "none"], capture_output=True, text=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("requested cap", refused.stderr)

    def test_malformed_profile_and_symlink_member_refuse_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.bundle(root)
            manifest["memory_profile"] = []
            self.save(root, manifest)
            with self.assertRaisesRegex(ValueError, "invalid bundle memory profile"):
                bootstrap.verify_bundle(root)
            manifest["memory_profile"] = bootstrap.memory_profile("3G")
            self.save(root, manifest)
            data = (root / "queue.txt").read_bytes()
            (root / "queue.txt").unlink()
            (root / "other").write_bytes(data)
            (root / "queue.txt").symlink_to(root / "other")
            with self.assertRaisesRegex(ValueError, "symlink"):
                bootstrap.verify_bundle(root)

    def test_queue_is_accepted_by_actual_trace_queue_parser(self):
        spec = importlib.util.spec_from_file_location("stick", ROOT / "tools/boottrace/stick.py")
        stick = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stick)
        for cap in bootstrap.MEMORY_CAPS:
            _, queue = bootstrap.memory_inputs(cap, "pi500")
            experiments = stick.parse_experiments(queue.decode())
            self.assertEqual(len(experiments), 1)
            self.assertIn("hw.physmem=3G" if cap == "3G" else "unset hw.physmem", experiments[0]["lines"])


if __name__ == "__main__":
    unittest.main()
