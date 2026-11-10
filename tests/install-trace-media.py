#!/usr/bin/env python3
"""Input-integrity controls for native installation trace media assembly."""
import importlib.util
from pathlib import Path
import struct
import uuid
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trace_media', ROOT / 'scripts/make-install-trace.py')
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


def fixture(path):
    # Primary GPT fixture with an embedded ESP and ISO payload outside it.
    table = bytearray(16384)
    table[:16] = media.EFI
    table[16:32] = bytes(range(16))
    struct.pack_into('<QQ', table, 32, 2048, 4095)
    header = bytearray(512)
    header[:8] = b'EFI PART'
    struct.pack_into('<II', header, 8, 0x10000, 92)
    struct.pack_into('<4Q', header, 24, 1, 32767, 34, 32734)
    struct.pack_into('<QIII', header, 72, 2, 128, 128, zlib.crc32(table))
    struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
    with path.open('wb') as stream:
        stream.truncate(16 << 20)
        stream.seek(512)
        stream.write(header)
        stream.write(table)
        stream.seek(media.SYSTEM_AREA)
        stream.write(b'\x01CD001\x01')
        stream.seek(5 << 20)
        stream.write(b'installer data outside the GPT partition')


def gpt_table(path, table):
    """Replace a primary table and recompute both checksums."""
    with path.open('r+b') as stream:
        stream.seek(512)
        header = bytearray(stream.read(512))
        struct.pack_into('<I', header, 88, zlib.crc32(table))
        struct.pack_into('<I', header, 16, 0)
        struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
        stream.seek(512)
        stream.write(header)
        stream.write(table)


def bios_fixture(path, hole=False):
    fixture(path)
    table = bytearray(16384)
    first = 1 if hole else 0
    for index, kind, start, end in [(first, media.FREEBSD_BOOT, 34, 58),
                                    (first + 1, media.EFI, 80, 20559)]:
        off = index * 128
        table[off:off + 16] = kind
        table[off + 16:off + 32] = uuid.uuid4().bytes_le
        struct.pack_into('<QQQ', table, off + 32, start, end, 1 << 59)
        name = ('BIOS' if kind == media.FREEBSD_BOOT else 'ESP').encode('utf-16le')
        table[off + 56:off + 56 + len(name)] = name
    gpt_table(path, table)
    with path.open('r+b') as stream:
        stream.seek(34 * 512)
        stream.write(b'BIOS isoboot must survive'.ljust(25 * 512, b'!'))


def generated_layout(path, original):
    """Independent GPT fixture for native-generated placeholders and trace."""
    fixture(path)
    table = bytearray(16384)
    for index, entry in enumerate(original['entries']):
        off = index * 128
        table[off:off + 16] = entry['type']
        table[off + 16:off + 32] = uuid.uuid4().bytes_le
        struct.pack_into('<QQ', table, off + 32, entry['start'], entry['end'])
    off = len(original['entries']) * 128
    table[off:off + 16] = uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7').bytes_le
    table[off + 16:off + 32] = uuid.uuid4().bytes_le
    struct.pack_into('<QQ', table, off + 32, 24576, 28671)
    gpt_table(path, table)
    with path.open('r+b') as stream:
        stream.seek(512)
        backup = bytearray(stream.read(512))
        struct.pack_into('<QQ', backup, 24, 32767, 1)
        struct.pack_into('<Q', backup, 72, 32735)
        struct.pack_into('<I', backup, 16, 0)
        struct.pack_into('<I', backup, 16, zlib.crc32(backup[:92]))
        stream.seek(32735 * 512)
        stream.write(table)
        stream.seek(32767 * 512)
        stream.write(backup)


class Integrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.image = self.base / 'input.iso'
        fixture(self.image)
        self.original = media.digest(self.image)

    def assemble(self, **kwargs):
        return media.assemble(kwargs.pop('image', self.image),
                              self.base / 'output.iso', self.base / 'work',
                              ROOT / 'tools/boottrace/stick.py', **kwargs)

    def test_valid_primary_gpt(self):
        result = media.read_gpt(self.image)
        self.assertEqual(result['entries'], [dict(type=media.EFI, start=2048, end=4095)])

    def test_standard_bios_partition_inside_system_area_is_admitted(self):
        bios_fixture(self.image)
        parsed = media.read_gpt(self.image)
        self.assertEqual(media.admit_layout(parsed), ['freebsd-boot', 'efi'])
        self.assertLess((parsed['entries'][0]['end'] + 1) * 512, media.SYSTEM_AREA)

    def test_unknown_and_duplicate_boot_layouts_refused_before_mutation(self):
        for kind in (media.EFI, media.FREEBSD_BOOT, bytes(range(16))):
            bios_fixture(self.image)
            gpt = media.read_gpt(self.image)
            table = bytearray(gpt['table'])
            table[256:272] = kind
            table[272:288] = uuid.uuid4().bytes_le
            struct.pack_into('<QQ', table, 288, 22000, 23000)
            gpt_table(self.image, table)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'one ESP'):
                self.assemble()
            self.assertFalse((self.base / 'work').exists())

    def test_smaller_gpt_table_is_not_expanded_over_boot_code(self):
        bios_fixture(self.image)
        with self.image.open('r+b') as stream:
            stream.seek(512)
            header = bytearray(stream.read(512))
            stream.seek(1024)
            table = stream.read(512)
            struct.pack_into('<II', header, 80, 4, 128)
            struct.pack_into('<I', header, 88, zlib.crc32(table))
            struct.pack_into('<I', header, 16, 0)
            struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
            stream.seek(512)
            stream.write(header)
        with self.assertRaisesRegex(ValueError, '16 KiB'):
            self.assemble()
        self.assertFalse((self.base / 'work').exists())

    def test_original_partition_identity_attributes_and_holes_are_retained(self):
        for hole in (False, True):
            bios_fixture(self.image, hole)
            original = media.read_gpt(self.image)
            layout = self.base / ('layout-hole' if hole else 'layout')
            generated_layout(layout, original)
            primary, backup = media.retain_gpt_entries(layout, original)
            self.assertEqual(primary['table'], backup['table'])
            self.assertEqual(primary['guid'], original['guid'])
            for offset in range(0, len(original['table']), 128):
                if original['table'][offset:offset + 16] != bytes(16):
                    self.assertEqual(primary['table'][offset:offset + 128],
                                     original['table'][offset:offset + 128])
            self.assertEqual(len(primary['entries']), 3)

    def test_corrupt_header_refused_before_output_or_work(self):
        with self.image.open('r+b') as stream:
            # Change the GPT header's current LBA, leaving its checksum stale.
            stream.seek(512 + 24)
            stream.write(bytes(8))
        with self.assertRaisesRegex(ValueError, 'header checksum'):
            self.assemble()
        self.assertFalse((self.base / 'output.iso').exists())
        self.assertFalse((self.base / 'work').exists())

    def test_corrupt_table_refused(self):
        with self.image.open('r+b') as stream:
            stream.seek(1024 + 100)
            stream.write(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'table checksum'):
            self.assemble()

    def test_symlink_input_refused_and_target_preserved(self):
        link = self.base / 'link'
        link.symlink_to(self.image)
        with self.assertRaisesRegex(ValueError, 'nonsymlink'):
            self.assemble(image=link)
        self.assertEqual(media.digest(self.image), self.original)

    def test_existing_output_work_and_dangling_links_preserved(self):
        for name in ('output.iso', 'work'):
            path = self.base / name
            for dangling in (False, True):
                if dangling:
                    path.symlink_to(self.base / 'absent')
                else:
                    path.write_text('preserve me')
                with self.assertRaisesRegex(ValueError, 'must not exist'):
                    self.assemble()
                if dangling:
                    self.assertTrue(path.is_symlink())
                else:
                    self.assertEqual(path.read_text(), 'preserve me')
                path.unlink()
        self.assertEqual(media.digest(self.image), self.original)

    def test_small_or_excessive_volume_refused_before_mutation(self):
        for size in (64, 4097):
            with self.assertRaisesRegex(ValueError, '256..4096'):
                self.assemble(size_mib=size)
        self.assertEqual(media.digest(self.image), self.original)
        self.assertFalse((self.base / 'work').exists())

    def test_normal_identity_is_bounded_and_canonical(self):
        path = self.base / 'identity'
        data = (b'Daemonarchy installation trace identity v1\n'
                b'image_id=01234567-89ab-cdef-0123-456789abcdef\n'
                b'archive_sha256=' + b'ab' * 32 + b'\nmode=observe-only\n')
        path.write_bytes(data)
        actual, fields = media.read_identity(path)
        self.assertEqual(actual, data)
        self.assertEqual(fields['archive_sha256'], 'ab' * 32)
        for changed in (data + b'\n', data.replace(b'observe-only', b'experimentxx'),
                        data.replace(b'abcdef\narchive', b'Abcdef\narchive'), b'x' * 257):
            path.write_bytes(changed)
            with self.subTest(changed=changed[:40]), self.assertRaises(ValueError):
                media.read_identity(path)

    def test_normal_identity_symlink_is_refused(self):
        path, link = self.base / 'identity', self.base / 'identity-link'
        path.write_text('not a real identity')
        link.symlink_to(path)
        with self.assertRaisesRegex(ValueError, 'regular bounded'):
            media.read_identity(link)
        self.assertEqual(path.read_text(), 'not a real identity')


if __name__ == '__main__':
    unittest.main()
