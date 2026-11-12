#!/usr/bin/env python3
"""Exercise real XZ transport, semantic tampering and exclusive output publication."""
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/split-media.py'
spec = importlib.util.spec_from_file_location('split_media', SCRIPT)
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


class SplitMediaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.image = self.root / 'candidate-aarch64.iso'
        self.data = bytes(range(256)) * 4 + b'end-of-image'
        self.image.write_bytes(self.data)
        self.raw_hash = hashlib.sha256(self.data).hexdigest()
        self.directory = self.root / 'parts'
        self.result = media.pack(self.image, self.raw_hash, self.directory, 257)
        self.manifest = self.directory / self.result['manifest']
        self.expected = self.result['sha256']
        self.record = media.load_manifest(self.manifest, self.expected)
        self.output = self.root / 'joined.iso'

    def save(self, value=None, raw=None):
        if raw is None:
            raw = json.dumps(self.record if value is None else value).encode()
        encoded = lzma.compress(raw)
        self.manifest.write_bytes(encoded)
        self.expected = hashlib.sha256(encoded).hexdigest()
        self.manifest.with_name(self.manifest.name + '.sha256').write_text(f'{self.expected}  {self.manifest.name}\n')

    def rejected(self):
        with self.assertRaises((ValueError, OSError, lzma.LZMAError)):
            media.join(self.manifest, self.expected, self.output)
        self.assertFalse(self.output.exists(), 'unchecked image must never receive its final name')
        self.assertEqual(self.image.read_bytes(), self.data)

    def replace_part(self, contents):
        part = self.record['parts'][0]
        (self.directory / part['name']).write_bytes(contents)
        part['bytes'] = len(contents)
        part['sha256'] = hashlib.sha256(contents).hexdigest()
        self.save()

    def test_cli_roundtrip_and_trusted_pin(self):
        verified = subprocess.run([sys.executable, str(SCRIPT), 'verify', str(self.manifest),
                                   '--sha256', self.expected], capture_output=True, text=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(json.loads(verified.stdout)['image']['sha256'], self.raw_hash)
        joined = subprocess.run([sys.executable, str(SCRIPT), 'join', str(self.manifest),
                                '--sha256', self.expected, '--out', str(self.output)], capture_output=True, text=True)
        self.assertEqual(joined.returncode, 0, joined.stderr)
        self.assertEqual(self.output.read_bytes(), self.data)
        self.assertTrue(all(p['bytes'] < media.ASSET_LIMIT for p in self.result['parts']))

    def test_deterministic_parts_and_manifest(self):
        other = self.root / 'second'
        result = media.pack(self.image, self.raw_hash, other, 257)
        self.assertEqual(result, self.result)
        self.assertEqual({p.name: p.read_bytes() for p in other.iterdir()},
                         {p.name: p.read_bytes() for p in self.directory.iterdir()})

    def test_wrong_raw_pin_preserves_failed_pack_without_manifest(self):
        output = self.root / 'wrong-pin'
        with self.assertRaises(ValueError):
            media.pack(self.image, '0' * 64, output, 257)
        self.assertTrue(list(output.iterdir()))
        self.assertFalse(list(output.glob('*.parts.json.xz')))

    def test_existing_pack_directory_is_untouched(self):
        sentinel = self.directory / 'sentinel'
        sentinel.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            media.pack(self.image, self.raw_hash, self.directory)
        self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_existing_joined_image_is_untouched(self):
        self.output.write_bytes(b'keep')
        with self.assertRaises(ValueError):
            media.join(self.manifest, self.expected, self.output)
        self.assertEqual(self.output.read_bytes(), b'keep')

    def test_racing_output_is_never_overwritten(self):
        original = os.link
        def raced(source, destination):
            Path(destination).write_bytes(b'other writer')
            return original(source, destination)
        with patch.object(media.os, 'link', side_effect=raced):
            with self.assertRaises(FileExistsError):
                media.join(self.manifest, self.expected, self.output)
        self.assertEqual(self.output.read_bytes(), b'other writer')

    def test_changed_compressed_part(self):
        part = self.directory / self.record['parts'][0]['name']
        changed = bytearray(part.read_bytes())
        changed[len(changed) // 2] ^= 1
        part.write_bytes(changed)
        self.rejected()

    def test_missing_part(self):
        (self.directory / self.record['parts'][0]['name']).unlink()
        self.rejected()

    def test_unlisted_part(self):
        (self.directory / media.part_name(self.image.name, 9)).write_bytes(b'extra')
        self.rejected()

    def test_part_symlink(self):
        part = self.directory / self.record['parts'][0]['name']
        original = self.root / 'original-part'
        part.rename(original)
        part.symlink_to(original)
        self.rejected()
        self.assertTrue(original.exists())

    def test_source_symlink(self):
        alias = self.root / 'alias.iso'
        alias.symlink_to(self.image)
        with self.assertRaises((ValueError, OSError)):
            media.pack(alias, self.raw_hash, self.root / 'symlink-output')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO unavailable')
    def test_fifo_is_refused_without_opening_or_blocking(self):
        fifo = self.root / 'pipe.iso'
        os.mkfifo(fifo)
        result = subprocess.run([sys.executable, str(SCRIPT), 'pack', str(fifo), '--sha256', self.raw_hash,
                                 '--out', str(self.root / 'fifo-output')], capture_output=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)

    def test_wrong_manifest_pin(self):
        self.expected = '0' * 64
        self.rejected()

    def test_duplicate_manifest_key(self):
        self.save(raw=(json.dumps(self.record)[:-1] + ',"schema":"' + media.SCHEMA + '"}').encode())
        self.rejected()

    def test_unknown_manifest_field(self):
        self.record['unreviewed'] = True
        self.save()
        self.rejected()

    def test_unknown_schema(self):
        self.record['schema'] = 'future-format'
        self.save()
        self.rejected()

    def test_reordered_parts(self):
        self.record['parts'].reverse()
        self.save()
        self.rejected()

    def test_unsafe_image_name(self):
        self.record['image']['name'] = '../outside.iso'
        self.save()
        self.rejected()

    def test_part_path_escape(self):
        self.record['parts'][0]['name'] = '../outside.xz'
        self.save()
        self.rejected()

    def test_part_geometry_and_boolean_counts(self):
        for value in [True, 1, 0, -1]:
            with self.subTest(value=value):
                self.record['parts'][0]['raw_bytes'] = value
                self.save()
                self.rejected()

    def test_oversize_asset(self):
        for size in [media.ASSET_LIMIT, media.ASSET_LIMIT + 1]:
            with self.subTest(size=size):
                self.record['parts'][0]['bytes'] = size
                self.save()
                self.rejected()

    def test_truncated_validly_pinned_xz(self):
        part = self.directory / self.record['parts'][0]['name']
        self.replace_part(part.read_bytes()[:-1])
        self.rejected()

    def test_concatenated_xz_stream_is_refused(self):
        part = self.directory / self.record['parts'][0]['name']
        self.replace_part(part.read_bytes() + lzma.compress(b'hidden'))
        self.rejected()

    def test_expansion_beyond_declared_part(self):
        self.replace_part(lzma.compress(b'x' * 1024))
        self.rejected()

    def test_raw_part_digest(self):
        self.record['parts'][0]['raw_sha256'] = '0' * 64
        self.save()
        self.rejected()

    def test_whole_image_digest(self):
        self.record['image']['sha256'] = '0' * 64
        self.save()
        self.rejected()

    def test_checksum_sidecar(self):
        self.manifest.with_name(self.manifest.name + '.sha256').write_text('wrong\n')
        self.rejected()

    def test_bounded_expanded_manifest(self):
        self.save(raw=b' ' * (media.MANIFEST_LIMIT + 1))
        self.rejected()

    def test_too_many_parts(self):
        with self.assertRaises(ValueError):
            media.pack(self.image, self.raw_hash, self.root / 'too-many', 1)

    def test_empty_image(self):
        empty = self.root / 'empty.iso'
        empty.touch()
        with self.assertRaises(ValueError):
            media.pack(empty, hashlib.sha256(b'').hexdigest(), self.root / 'empty-output')


if __name__ == '__main__':
    unittest.main(verbosity=2)
