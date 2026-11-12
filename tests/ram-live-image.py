#!/usr/bin/env python3
"""Exercise RAM image authoring refusals without replacing existing evidence."""
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'scripts/make-ram-iso.sh'

class Preflight(unittest.TestCase):
    def invoke(self, source, output, work, *extra):
        return subprocess.run(['sh', str(BUILDER), str(source), 'RAMTEST',
                               str(output), str(work), *extra], capture_output=True, text=True)

    def test_existing_artifacts_and_dangling_links_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'world.tar'
            source.write_bytes(b'retained input bytes')
            for kind in ('output', 'work', 'manifest', 'dangling'):
                with self.subTest(kind=kind):
                    output, work = root / (kind + '.iso'), root / (kind + '-stage')
                    sentinel = (Path(str(output) + '.ram.json') if kind == 'manifest'
                                else work if kind == 'work' else output)
                    if kind == 'dangling':
                        sentinel.symlink_to(root / 'missing')
                    elif kind == 'work':
                        sentinel.mkdir()
                        (sentinel / 'previous-failure').write_text('preserve')
                    else:
                        sentinel.write_bytes(b'previous evidence')
                    before = sorted(x.name for x in root.iterdir())
                    result = self.invoke(source, output, work)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('Preserve existing image evidence', result.stderr)
                    self.assertEqual(sorted(x.name for x in root.iterdir()), before)
                    self.assertEqual(source.read_bytes(), b'retained input bytes')
                    if kind == 'dangling':
                        self.assertTrue(sentinel.is_symlink())
                    elif kind != 'work':
                        self.assertEqual(sentinel.read_bytes(), b'previous evidence')

    def test_missing_and_symlink_sources_do_not_allocate_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'world.tar'
            source.write_bytes(b'input')
            alias = root / 'alias'; alias.symlink_to(source)
            for target in (root / 'absent', alias):
                result = self.invoke(target, root / 'image.iso', root / 'stage')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('regular nonsymlink', result.stderr)
                self.assertFalse((root / 'stage').exists())
                self.assertFalse((root / 'image.iso').exists())
            self.assertEqual(source.read_bytes(), b'input')

    def test_wrong_architecture_mode_refuses_before_output_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'world.tar'; source.write_bytes(b'input')
            for args in (('BOOTAA64.EFI', 'bios'), ('BOOTX64.EFI', 'unknown'), ('foreign', 'efi')):
                result = self.invoke(source, root / 'image.iso', root / 'stage', *args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(sorted(x.name for x in root.iterdir()), ['world.tar'])

@unittest.skipUnless(platform.system() == 'FreeBSD' and os.geteuid() == 0,
                     'native archive admission requires allocated FreeBSD root')
class NativeAdmission(unittest.TestCase):
    def test_bad_inputs_and_root_inode_cannot_author_a_filesystem(self):
        for fault in ('abi', 'elf', 'hook', 'root-mode', 'root-owner', 'root-missing', 'root-last'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); world = root / 'input'; world.mkdir()
                world.chmod(0o755)
                if fault == 'root-mode':
                    world.chmod(0o700)
                if fault == 'root-owner':
                    os.chown(world, 1001, 1001)
                for name in ('etc/fstab', 'etc/rc.conf', 'boot/loader.efi', 'boot/kernel/kernel',
                             'boot/kernel/geom_uzip.ko', 'boot/lua/local.lua',
                             'boot/lua/brand-daemonarchy.lua', 'bin/sh', 'usr/freebsd-dist/base.txz',
                             'usr/freebsd-dist/kernel.txz', 'usr/freebsd-dist/MANIFEST',
                             'usr/local/libexec/daemonarchy-installer/install', 'var/db/pkg/local.sqlite'):
                    if fault == 'hook' and name == 'boot/lua/local.lua':
                        continue
                    p = world / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'incomplete fixture')
                share = world / 'usr/local/share/daemonarchy-installer'
                (share / 'repo/All').mkdir(parents=True)
                (share / 'ABI').write_text('FreeBSD:16:aarch64' if fault == 'abi' else 'FreeBSD:16:amd64')
                archive = root / 'world.tar'
                with tarfile.open(archive, 'w') as out:
                    if fault == 'root-last':
                        old_root = out.gettarinfo(world, arcname='.')
                        old_root.mode = 0o700
                        out.addfile(old_root)
                    if fault == 'root-missing':
                        for child in world.iterdir():
                            out.add(child, arcname=child.name)
                    else:
                        out.add(world, arcname='.')
                result = subprocess.run(['sh', str(BUILDER), str(archive), 'RAMREFUSE',
                                         str(root / 'out.iso'), str(root / 'stage'), 'BOOTX64.EFI', 'bios'],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                expected = {'abi': 'ABI does not match', 'elf': 'Wrong native ELF',
                            'hook': 'Regular installer payload required: boot/lua/local.lua',
                            'root-mode': 'Live-root inode must be root-owned',
                            'root-owner': 'Live-root inode must be root-owned',
                            'root-missing': 'Explicit live-root archive directory entry is required',
                            'root-last': 'Wrong native ELF'}[fault]
                self.assertIn(expected, result.stderr)
                self.assertFalse((root / 'out.iso').exists())
                self.assertFalse((root / 'stage/mfsroot').exists())
                if fault in ('abi', 'elf', 'hook', 'root-last'):
                    self.assertEqual((root / 'stage/world').stat().st_mode & 0o7777, 0o755)
                    self.assertEqual((root / 'stage/world').stat().st_uid, 0)

if __name__ == '__main__':
    unittest.main()
