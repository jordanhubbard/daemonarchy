#!/usr/bin/env python3
"""Independent raw GPT corruption controls for boot-medium observations."""
import importlib.util
from pathlib import Path
import struct
import unittest
import uuid
import zlib

spec = importlib.util.spec_from_file_location('medium', Path(__file__).resolve().parents[1] / 'tools/boottrace/boot-medium.py')
medium = importlib.util.module_from_spec(spec); spec.loader.exec_module(medium)
GUID = 'fedcba98-7654-3210-fedc-ba9876543210'


def fixture():
    table = bytearray(16384)
    table[:16] = uuid.UUID(medium.BASIC_DATA).bytes_le
    table[16:32] = uuid.UUID(GUID).bytes_le
    struct.pack_into('<QQQ', table, 32, 2048, 3071, 0)
    table[56:128] = 'DATRACE'.ljust(36, '\0').encode('utf-16-le')
    return table


def disk(table=None, expanded=False):
    table = fixture() if table is None else table
    image = bytearray((16384 if expanded else 8192)*512)
    for lba, other, entries in ((1,8191,2),(8191,1,8159)):
        header = bytearray(512)
        struct.pack_into('<8sIIIIQQQQ', header, 0, b'EFI PART', 0x10000, 92, 0, 0, lba, other, 34, 8158)
        header[56:72] = uuid.UUID('01234567-89ab-cdef-0123-456789abcdef').bytes_le
        struct.pack_into('<QIII', header, 72, entries, 128, 128, zlib.crc32(table))
        struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
        image[lba*512:(lba+1)*512] = header
        image[entries*512:entries*512+len(table)] = table
    return image


def selection(image):
    return dict(sector_bytes=512, disk_bytes=len(image), partition_uuid=GUID,
                start_lba=2048, sectors=1024, device='/dev/vtbd0p1')


def check(image, chosen=None):
    return medium.validate_gpt(lambda off,n: bytes(image[off:off+n]), chosen or selection(image))


class RawGPT(unittest.TestCase):
    def test_both_copies_and_expanded_medium(self):
        for expanded in (False, True):
            result = check(disk(expanded=expanded))
            self.assertEqual(result['backup_at_disk_end'], not expanded)
            self.assertFalse(result['writes_admitted'])
            self.assertEqual(result['partition_index'], 1)

    def test_header_and_table_corruption_in_either_copy(self):
        for offset in (512, 512+16, 512+40, 1024+60, 8191*512+16, 8159*512+20):
            image = disk(); image[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): check(image)

    def test_rechecks_raw_provider_identity(self):
        for key,value in (('partition_uuid',str(uuid.uuid4())),('start_lba',2049),
                          ('sectors',1025),('device','/dev/vtbd0p2')):
            image = disk(); chosen = selection(image); chosen[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): check(image, chosen)

    def test_valid_crc_does_not_admit_wrong_type_name_attributes_or_range(self):
        for offset in (0,32,48,56):
            table = fixture(); table[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError): check(disk(table))

    def test_duplicate_uuid_and_overlapping_other_partition(self):
        for duplicate in (True, False):
            table = fixture(); table[128:256] = table[:128]
            if not duplicate:
                table[144:160] = uuid.UUID('abcdef01-2345-6789-abcd-ef0123456789').bytes_le
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError): check(disk(table))

    def test_short_reads_and_resource_bounds(self):
        image = disk()
        with self.assertRaises(ValueError):
            medium.validate_gpt(lambda off,n: bytes(image[off:off+n-1]), selection(image))
        header = bytearray(image[512:1024])
        struct.pack_into('<I', header, 80, 4097)
        struct.pack_into('<I', header, 16, 0)
        struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
        image[512:1024] = header
        calls = []
        def read(off,n):
            calls.append(n); return bytes(image[off:off+n])
        with self.assertRaises(ValueError): medium.validate_gpt(read, selection(image))
        self.assertEqual(calls, [512])

    def test_crc_valid_backup_disagreement(self):
        image = disk()
        header = bytearray(image[8191*512:8192*512]); header[56] ^= 1
        struct.pack_into('<I', header, 16, 0)
        struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
        image[8191*512:8192*512] = header
        with self.assertRaises(ValueError): check(image)


if __name__ == '__main__':
    unittest.main()
