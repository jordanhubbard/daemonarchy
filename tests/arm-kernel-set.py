#!/usr/bin/env python3
"""Reject incomplete, foreign and unsafe kernel closures before root assembly."""
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("kernel_set", ROOT / "scripts/check-arm-kernel-set.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def elf(machine=183, module=False):
    data = bytearray(128)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<HH", data, 16, 1 if module else 2, machine)
    if not module:
        data += b"\0FreeBSD 16.0-CURRENT #0 test\0"
    return bytes(data)


class KernelSet(unittest.TestCase):
    def inspect(self, entries):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kernel.txz"
            with tarfile.open(path, "w:xz") as archive:
                for name, data in entries:
                    if isinstance(name, tarfile.TarInfo):
                        member = name
                    else:
                        member = tarfile.TarInfo(name)
                        member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            return checker.inspect(path)

    def valid(self):
        return [("./boot/kernel/kernel", elf()), ("./boot/kernel/geom_uzip.ko", elf(module=True))]

    def test_valid_archive_selects_exact_kernel(self):
        self.assertEqual(self.inspect(self.valid()), hashlib.sha256(elf()).hexdigest())
        entries = self.valid()
        shared = bytearray(elf(module=True))
        struct.pack_into("<H", shared, 16, 3)
        entries[1] = (entries[1][0], bytes(shared))
        self.assertEqual(self.inspect(entries), hashlib.sha256(elf()).hexdigest())

    def test_bare_kernel_or_missing_modules_cannot_replace_a_closure(self):
        with self.assertRaisesRegex(ValueError, "GEOM UZIP"):
            self.inspect(self.valid()[:1])
        with self.assertRaisesRegex(ValueError, "AArch64 ELF64 kernel"):
            self.inspect(self.valid()[1:])

    def test_foreign_kernel_and_modules_are_refused(self):
        for entries in ([("boot/kernel/kernel", elf(62)), self.valid()[1]],
                        [self.valid()[0], ("boot/kernel/geom_uzip.ko", elf(62, module=True))]):
            with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, "AArch64 ELF64"):
                self.inspect(entries)

    def test_ordinary_elf_cannot_stand_in_for_freebsd_kernel(self):
        entries = self.valid()
        entries[0] = (entries[0][0], elf(module=True))
        with self.assertRaisesRegex(ValueError, "FreeBSD 16"):
            self.inspect(entries)

    def test_duplicate_aliases_and_outside_paths_are_refused(self):
        for name in ("boot/kernel/kernel", "boot/kernel/../../etc/rc", "/boot/kernel/new", "etc/rc.conf"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.inspect(self.valid() + [(name, elf())])

    def test_links_devices_and_directory_modules_are_refused(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.DIRTYPE):
            member = tarfile.TarInfo("boot/kernel/geom_uzip.ko")
            member.type = kind
            member.linkname = "/etc/passwd"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.inspect(self.valid()[:1] + [(member, b"")])

    def test_native_dtb_debug_and_module_alias_layout_is_supported(self):
        alias = tarfile.TarInfo("boot/kernel/if_alias.ko")
        alias.type = tarfile.SYMTYPE
        alias.linkname = "geom_uzip.ko"
        entries = self.valid() + [("boot/dtb/board.dtb", b"board fixture"),
                                 ("usr/lib/debug/boot/kernel/kernel.debug", b"debug fixture"),
                                 (alias, b"")]
        self.assertEqual(self.inspect(entries), hashlib.sha256(elf()).hexdigest())
        alias.linkname = "missing.ko"
        with self.assertRaisesRegex(ValueError, "inspected regular module"):
            self.inspect(entries)


if __name__ == "__main__":
    unittest.main()
