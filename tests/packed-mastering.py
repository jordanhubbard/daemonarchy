#!/usr/bin/env python3
"""Real ISO/GPT/FAT/UZIP/UFS2 parser controls with synthetic, nonbootable payloads."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ram = load('packed_test_ufs', ROOT / 'scripts/arm-ram-inspect.py')
checker = load('packed_test_checker', ROOT / 'scripts/check-packed-installer.py')
codec = load('packed_test_codec', ROOT / 'scripts/split-media.py')
TOOLS = ('bsdtar', 'ifind', 'icat', 'istat', 'xorriso', 'mformat', 'mmd', 'mcopy', 'mtype')


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def image_fixture(work, missing=False, fixture_name=None):
    work.mkdir()
    image_root = work / 'iso-root'
    (image_root / 'boot/kernel').mkdir(parents=True)
    (image_root / 'boot/lua').mkdir()
    fixture = ROOT / 'tests/fixtures/arm-ram' / (fixture_name or ('master-missing-sqlite.uzip' if missing else 'master-complete.uzip'))
    raw = work / 'root.ufs'
    ram.unpack_root(fixture, raw)
    root = ram.UFS(raw)
    for name in ['boot/kernel/kernel', 'boot/loader.efi', 'boot/lua/loader.lua']:
        (image_root / name).write_bytes(root.read(name))
    (image_root / 'boot/mfsroot.uzip').write_bytes(fixture.read_bytes())
    (image_root / 'boot/loader.conf.local').write_text('mfsroot_load=YES\nmfsroot_type=md_image\nmfsroot_name="/boot/mfsroot.uzip"\ngeom_uzip_load=YES\nvfs.root.mountfrom="ufs:/dev/md0.uzip"\n')
    esp = work / 'esp.img'
    with esp.open('xb') as stream: stream.truncate(8 << 20)
    run('mformat', '-i', str(esp), '::')
    run('mmd', '-i', str(esp), '::/EFI', '::/EFI/BOOT')
    run('mcopy', '-i', str(esp), str(image_root / 'boot/loader.efi'), '::/EFI/BOOT/BOOTAA64.EFI')
    image = work / 'daemonarchy-1.6.0-aarch64.iso'
    run('xorriso', '-as', 'mkisofs', '-R', '-V', 'PARSERFIXTURE', '-o', str(image), str(image_root))
    # Supply real primary/backup GPTs and an appended FAT ESP. The tiny payloads
    # remain synthetic; this file is deliberately not a bootable OS fixture.
    first = (image.stat().st_size + 511) // 512
    last = first + esp.stat().st_size // 512 - 1
    end = last + 33
    table = bytearray(128 * 128)
    table[:16] = uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le
    table[16:32] = uuid.UUID('83b973b2-6504-49cb-a8df-90fde97789cc').bytes_le
    struct.pack_into('<QQ', table, 32, first, last)

    def header(current, backup, entries):
        block = bytearray(512)
        block[:8] = b'EFI PART'
        struct.pack_into('<IIIIQQQQ', block, 8, 0x10000, 92, 0, 0, current, backup, 34, end - 33)
        block[56:72] = uuid.UUID('066079de-dbe7-4f10-b502-bf5d0f7c280c').bytes_le
        struct.pack_into('<QIII', block, 72, entries, 128, 128, zlib.crc32(table))
        struct.pack_into('<I', block, 16, zlib.crc32(block[:92]))
        return block

    with image.open('r+b') as stream:
        stream.seek(first * 512)
        stream.write(esp.read_bytes())
        stream.truncate((end + 1) * 512)
        stream.seek(446)
        stream.write(struct.pack('<B3sB3sII', 0, b'\0\x02\0', 0xee, b'\xff' * 3, 1, end))
        stream.seek(510)
        stream.write(b'\x55\xaa')
        for offset, data in [(512, header(1, end, 2)), (1024, table),
                             ((end - 32) * 512, table), (end * 512, header(end, 1, end - 32))]:
            stream.seek(offset)
            stream.write(data)
    return image


@unittest.skipUnless(all(shutil.which(tool) for tool in TOOLS), 'ISO/FAT and Sleuth Kit tools required')
class PackedMastering(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="packed master's ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.image = image_fixture(self.root / 'fixture')
        self.pin = hashlib.sha256(self.image.read_bytes()).hexdigest()

    def test_full_independent_inspection_keeps_runtime_unqualified(self):
        record = checker.inspect(self.image, self.pin, '1.6.0')
        self.assertEqual(record['image']['sha256'], self.pin)
        self.assertTrue(record['static_content'])
        self.assertFalse(record['native_python_import'])
        self.assertFalse(record['boot_install_desktop_hardware_qualified'])
        self.assertIn('usr/local/lib/libsqlite3.so.0', record['identities']['packed_root']['files'])

    def test_stale_version_and_wrong_raw_pin_refused(self):
        for pin, version in [(self.pin, '1.6.1'), ('0' * 64, '1.6.0')]:
            with self.subTest(version=version), self.assertRaises(ValueError):
                checker.inspect(self.image, pin, version)

    def test_missing_sqlite_and_outer_esp_loader_mismatch_refused(self):
        image = image_fixture(self.root / 'missing', missing=True)
        with self.assertRaisesRegex(ValueError, '_sqlite3'):
            checker.inspect(image, hashlib.sha256(image.read_bytes()).hexdigest(), '1.6.0')
        esp = self.root / 'fixture/esp.img'
        wrong = self.root / 'foreign-loader'
        wrong.write_bytes(b'foreign loader')
        run('mcopy', '-o', '-i', str(esp), str(wrong), '::/EFI/BOOT/BOOTAA64.EFI')
        with self.image.open('r+b') as stream:
            assembler = load('fixture_assembler', ROOT / 'scripts/assemble-arm-media.py')
            stream.seek(assembler.esp_offset(self.image))
            stream.write(esp.read_bytes())
        with self.assertRaisesRegex(ValueError, 'removable-media EFI'):
            checker.inspect(self.image, hashlib.sha256(self.image.read_bytes()).hexdigest(), '1.6.0')

    def master(self, *, split=True, stale_cache=False, static=True):
        work = self.root / 'work'
        work.mkdir()
        commit = 'a' * 40
        product = work / ('product-' + commit[:12])
        product.mkdir()
        (product / 'VERSION').write_text('1.6.0\n')
        env = dict(os.environ, WORK=str(work), MAIN_COMMIT=commit, RELEASE='1.6.0', ARCH='aarch64')
        if split:
            directory = self.root / 'parts'
            result = codec.pack(self.image, self.pin, directory, 1 << 20)
            env.update(MEDIA_MANIFEST=str(directory / result['manifest']), MEDIA_MANIFEST_SHA256=result['sha256'])
        else:
            import lzma
            directory = work / ('out-' + commit[:12])
            directory.mkdir()
            iso = directory / self.image.name
            iso.write_bytes(self.image.read_bytes() + (b'unapproved cached bytes' if stale_cache else b''))
            compressed = directory / (iso.name + '.xz')
            compressed.write_bytes(lzma.compress(self.image.read_bytes()))
            compressed.with_name(compressed.name + '.sha256').write_text(hashlib.sha256(compressed.read_bytes()).hexdigest() + '  ' + compressed.name + '\n')
            env.update(MEDIA_MANIFEST='', MEDIA_MANIFEST_SHA256='')
        return subprocess.run(['bash', str(ROOT / 'scripts/master-release.sh'), 'inspect' if static else 'verify'], env=env,
                              capture_output=True, text=True), work

    def test_master_routes_split_packed_image_to_real_inspector(self):
        result, work = self.master()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reports = list(work.glob('master-inspect.*/packed-inspection.json'))
        self.assertEqual(len(reports), 1)
        self.assertFalse(json.loads(reports[0].read_text())['native_python_import'])
        self.assertIn('inspect:xz-parts@1:', (work / 'master-state.tsv').read_text())

    def test_single_file_packed_path_uses_same_inspection(self):
        result, work = self.master(split=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(list(work.glob('master-inspect.*/packed-inspection.json'))), 1)

    def test_cached_raw_image_cannot_differ_from_verified_compressed_stream(self):
        result, work = self.master(split=False, stale_cache=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('trusted pin', result.stderr)
        self.assertFalse((work / 'master-state.tsv').exists())

    def test_internal_symlink_escape_and_cycle_refused(self):
        for label, message in [('master-escaping-sqlite', 'escapes'), ('master-sqlite-loop', 'loop')]:
            image = image_fixture(self.root / label, fixture_name=label + '.uzip')
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, message):
                checker.inspect(image, hashlib.sha256(image.read_bytes()).hexdigest(), '1.6.0')

    @unittest.skipIf(sys.platform.startswith('freebsd') and os.geteuid() == 0,
                     'requires a controller without native root execution')
    def test_native_verify_unrun_never_records_success(self):
        result, work = self.master(static=False)
        self.assertEqual(result.returncode, 77, result.stdout + result.stderr)
        self.assertIn('no verify success recorded', result.stderr)
        self.assertFalse((work / 'master-state.tsv').exists())

    def test_symlink_image_refused(self):
        link = self.root / 'link.iso'
        link.symlink_to(self.image)
        with self.assertRaisesRegex(ValueError, 'nonsymlink'):
            checker.inspect(link, self.pin, '1.6.0')


if __name__ == '__main__':
    unittest.main()
