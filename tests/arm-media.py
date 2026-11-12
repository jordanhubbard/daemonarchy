#!/usr/bin/env python3
"""Check wrong-board and damaged-input refusal without writing a device."""
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
import unittest
import uuid
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("arm_media", ROOT / "scripts/assemble-arm-media.py")
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


def fdt(board, nested=False):
    value = (board + "\0apple,t6020\0").encode()
    begin = struct.pack(">I", 1) + bytes(4)
    prop = struct.pack(">III", 3, len(value), 0) + value
    prop += bytes(-len(prop) % 4)
    tree = begin + (begin if nested else b"") + prop
    tree += struct.pack(">I", 2) * (2 if nested else 1) + struct.pack(">I", 9)
    strings = b"compatible\0"
    return (struct.pack(">10I", 0xd00dfeed, 56 + len(tree) + len(strings),
                        56, 56 + len(tree), 40, 17, 16, 0, len(strings), len(tree))
            + bytes(16) + tree + strings)


class MediaInputs(unittest.TestCase):
    def test_ram_bootstrap_does_not_ignore_later_unquoted_overrides(self):
        config = ('mfsroot_load="YES"\nmfsroot_type=md_image\n'
                  'mfsroot_name="/boot/mfsroot.uzip"\ngeom_uzip_load=YES\n'
                  'vfs.root.mountfrom="ufs:/dev/md0.uzip"\n')
        media.check_ram_bootstrap(config)
        for suffix in ('mfsroot_load=NO\n', "mfsroot_load='NO'\n", 'mfsroot_load+=NO\n'):
            with self.assertRaises(ValueError):
                media.check_ram_bootstrap(config + suffix)

    def test_nested_or_foreign_compatible_cannot_enroll_the_mini(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bootstrap.zip"
            for blob in (fdt("apple,j475c"), fdt("apple,j474s", nested=True)):
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr("esp/m1n1/boot.bin", b"stage2" + blob)
                with self.assertRaises(ValueError):
                    media.apple_bootstrap(archive)
            blob = fdt("apple,j474s")
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("esp/m1n1/boot.bin", b"stage2" + blob)
            payload, board = media.apple_bootstrap(archive)
            self.assertEqual(payload[board["offset"]:], blob)

    def test_out_of_bounds_fdt_does_not_supply_a_board_identity(self):
        blob = bytearray(fdt("apple,j474s"))
        struct.pack_into(">I", blob, 12, len(blob) + 4)
        with self.assertRaises(ValueError):
            media.compatible(blob)

    def test_gpt_tampering_and_partition_only_input_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "disk.img"
            raw = bytearray(128 * 512)
            table = bytearray(128)
            table[:16] = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b").bytes_le
            struct.pack_into("<QQ", table, 32, 40, 100)
            header = bytearray(512)
            header[:8] = b"EFI PART"
            struct.pack_into("<III", header, 8, 0x10000, 92, 0)
            struct.pack_into("<QIII", header, 72, 2, 1, 128, zlib.crc32(table))
            struct.pack_into("<I", header, 16, zlib.crc32(header[:92]))
            raw[512:1024] = header
            raw[1024:1152] = table
            image.write_bytes(raw)
            self.assertEqual(media.esp_offset(image), 40 * 512)
            raw[1030] ^= 1
            image.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "table checksum"):
                media.esp_offset(image)
            image.write_bytes(raw[40 * 512:])
            with self.assertRaisesRegex(ValueError, "hybrid GPT"):
                media.esp_offset(image)

    @unittest.skipUnless(os.environ.get("DAEMONARCHY_APPLE_BOOTSTRAP_ZIP"),
                         "published bootstrap asset not supplied")
    def test_published_bootstrap_has_the_actual_m2_pro_mini_dtb(self):
        payload, board = media.apple_bootstrap(Path(os.environ["DAEMONARCHY_APPLE_BOOTSTRAP_ZIP"]))
        blob = payload[board["offset"]:board["offset"] + board["bytes"]]
        self.assertIn("apple,j474s", media.compatible(blob))
        self.assertIn("apple,t6020", media.compatible(blob))


if __name__ == "__main__":
    unittest.main()
