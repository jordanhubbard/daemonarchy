#!/usr/bin/env python3
"""Input-integrity controls for native installation trace media assembly."""
import importlib.util
from pathlib import Path
import struct
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
