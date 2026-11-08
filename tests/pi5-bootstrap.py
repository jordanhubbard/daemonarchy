#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Reject wrong board and architecture inputs before staging Pi 5 boot media."""
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


if __name__ == "__main__":
    unittest.main()
