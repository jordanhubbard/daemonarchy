#!/usr/bin/env python3
"""CLOOP integrity controls; real UFS2 contents are checked separately."""
import importlib.util
import json
import lzma
from pathlib import Path
import struct
import shutil
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ram_inspect', ROOT / 'scripts/arm-ram-inspect.py')
ram = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ram)


def packed(path, blocks, codec='V'):
    cluster = len(blocks[0])
    start = 136 + 8 * (len(blocks) + 1)
    offsets, content, previous = [], b'', {}
    for block in blocks:
        if not any(block):
            offsets.append(start + len(content))
        elif block in previous:
            offsets.append(previous[block])
        else:
            offsets.append(start + len(content))
            previous[block] = offsets[-1]
            content += zlib.compress(block) if codec == 'V' else lzma.compress(block)
    offsets.append(start + len(content))
    magic = (b'#!/bin/sh\n#' + codec.encode() + (b'2' if codec == 'V' else b'3') + b'.0 Format\n').ljust(128, b'\0')
    path.write_bytes(magic + struct.pack('>II', cluster, len(blocks)) +
                     struct.pack('>' + 'Q' * len(offsets), *offsets) + content)


class Cloop(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.input, self.output = self.base / 'root.uzip', self.base / 'root.ufs'

    def test_zlib_and_lzma_zero_clusters_and_backward_references(self):
        blocks = [b'A' * 512, bytes(512), b'A' * 512, b'B' * 512]
        for codec in ('V', 'L'):
            packed(self.input, blocks, codec)
            result = ram.unpack_root(self.input, self.output)
            self.assertEqual(self.output.read_bytes(), b''.join(blocks))
            self.assertEqual(result['expanded_bytes'], 2048)
            self.output.unlink()

    def test_existing_output_and_symlink_input_preserved(self):
        packed(self.input, [b'A' * 512])
        self.output.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            ram.unpack_root(self.input, self.output)
        self.assertEqual(self.output.read_bytes(), b'preserve')
        link = self.base / 'link'
        link.symlink_to(self.input)
        with self.assertRaisesRegex(ValueError, 'nonsymlink'):
            ram.unpack_root(link, self.base / 'another-output')

    def test_bad_geometry_and_budget_refused_before_output(self):
        packed(self.input, [b'A' * 512])
        with self.assertRaisesRegex(ValueError, 'budget'):
            ram.unpack_root(self.input, self.output, max_bytes=511)
        data = bytearray(self.input.read_bytes())
        struct.pack_into('>I', data, 128, 513)
        self.input.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'geometry'):
            ram.unpack_root(self.input, self.output)
        self.assertFalse(self.output.exists())

    def test_truncated_and_outside_offset_tables_refused(self):
        packed(self.input, [b'A' * 512])
        original = self.input.read_bytes()
        self.input.write_bytes(original[:140])
        with self.assertRaisesRegex(ValueError, 'truncated'):
            ram.unpack_root(self.input, self.output)
        data = bytearray(original)
        struct.pack_into('>Q', data, 136, len(data) + 1)
        self.input.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'outside'):
            ram.unpack_root(self.input, self.output)
        self.assertFalse(self.output.exists())

    def test_decoded_size_must_match_declared_cluster(self):
        packed(self.input, [b'A' * 1024])
        data = bytearray(self.input.read_bytes())
        struct.pack_into('>I', data, 128, 512)
        self.input.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'declared size'):
            ram.unpack_root(self.input, self.output)

    def test_native_short_final_cluster_is_zero_padded(self):
        for codec in ('V', 'L'):
            packed(self.input, [b'A' * 1024, b'B' * 512], codec)
            result = ram.unpack_root(self.input, self.output)
            self.assertEqual(self.output.read_bytes(), b'A' * 1024 + b'B' * 512 + bytes(512))
            self.assertEqual(result['zero_padded_bytes'], 512)
            self.output.unlink()

    def test_short_nonfinal_cluster_refused(self):
        packed(self.input, [b'A' * 512, b'B' * 1024])
        data = bytearray(self.input.read_bytes())
        struct.pack_into('>I', data, 128, 1024)
        self.input.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'declared size'):
            ram.unpack_root(self.input, self.output)

    def test_unknown_codec_and_damaged_stream_refused(self):
        packed(self.input, [b'A' * 512])
        data = bytearray(self.input.read_bytes())
        data[11] = ord('Q')
        self.input.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            ram.unpack_root(self.input, self.output)
        data[11] = ord('V')
        data[-1] ^= 1
        self.input.write_bytes(data)
        with self.assertRaises(zlib.error):
            ram.unpack_root(self.input, self.output)


@unittest.skipUnless(all(shutil.which(tool) for tool in ('ifind', 'icat', 'istat')),
                     'Sleuth Kit is required for actual UFS2 inspection')
class UFSFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name) / 'root.ufs'
        self.fixtures = ROOT / 'tests/fixtures/arm-ram'
        self.outer = json.loads((self.fixtures / 'outer.json').read_text())

    def test_complete_native_ufs2_fixture_contains_the_installer_and_matched_set(self):
        ram.unpack_root(self.fixtures / 'complete.uzip', self.raw)
        result = ram.inspect_root(self.raw, self.outer)
        self.assertEqual(result['boot/kernel/kernel'], self.outer['boot/kernel/kernel'])
        self.assertGreater(result['usr/freebsd-dist/kernel.txz']['bytes'], 0)

    def test_missing_inner_installer_refused(self):
        ram.unpack_root(self.fixtures / 'missing-installer.uzip', self.raw)
        with self.assertRaisesRegex(ValueError, 'daemonarchy-installer/install'):
            ram.inspect_root(self.raw, self.outer)

    def test_outer_kernel_mismatch_refused(self):
        ram.unpack_root(self.fixtures / 'complete.uzip', self.raw)
        self.outer['boot/kernel/kernel']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'differs from the outer ISO'):
            ram.inspect_root(self.raw, self.outer)

    def test_foreign_inner_abi_refused(self):
        ram.unpack_root(self.fixtures / 'complete.uzip', self.raw)
        original = self.raw.read_bytes()
        old, new = b'FreeBSD:16:aarch64\n', b'FreeBSD:16:amd64__\n'
        self.assertEqual(original.count(old), 1)
        self.assertEqual(len(old), len(new))
        self.raw.write_bytes(original.replace(old, new))
        with self.assertRaisesRegex(ValueError, 'ABI mismatch'):
            ram.inspect_root(self.raw, self.outer)

    def test_inner_install_archive_manifest_tampering_refused(self):
        ram.unpack_root(self.fixtures / 'complete.uzip', self.raw)
        manifest = ram.UFS(self.raw).read('usr/freebsd-dist/MANIFEST')
        old = manifest.splitlines()[0].split(b'\t')[1]
        original = self.raw.read_bytes()
        self.assertEqual(original.count(old), 1)
        self.raw.write_bytes(original.replace(old, b'0' * 64))
        with self.assertRaisesRegex(ValueError, 'does not match MANIFEST'):
            ram.inspect_root(self.raw, self.outer)


if __name__ == '__main__':
    unittest.main()
