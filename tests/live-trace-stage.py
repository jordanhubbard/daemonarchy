#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Admission and preservation controls for default live-media tracing."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage_trace', REPO/'scripts/stage-live-trace.py')
stager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stager)


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'root'
        self.root.mkdir(mode=0o755)
        self.source = self.base/'source'
        for relative in ['tools/boottrace/'+name for name in stager.MODULES] + [
                'tools/boottrace/daemonarchy_trace',
                'overlay/usr/local/libexec/daemonarchy-installer/boot-trace']:
            dst = self.source/relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO/relative, dst)
        abi = self.root/'usr/local/share/daemonarchy-installer/ABI'
        abi.parent.mkdir(parents=True)
        abi.write_text('FreeBSD:16:amd64\n')
        for relative in ('usr/local/bin/python3.12','bin/timeout','usr/bin/lockf','usr/sbin/daemon'):
            dst = self.root/relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            header = bytearray(20)
            header[:7] = b'\x7fELF\x02\x01\x01'
            header[18:20] = (62).to_bytes(2,'little')
            dst.write_bytes(header)
            dst.chmod(0o555)
        self.root_before = self.metadata()

    def metadata(self):
        s = self.root.stat()
        return s.st_uid, s.st_gid, stat.S_IMODE(s.st_mode)

    def stage(self):
        return stager.stage(self.root, self.source)

    def refuse(self, message):
        with self.assertRaisesRegex(ValueError, message):
            self.stage()
        self.assertEqual(self.metadata(), self.root_before)
        self.assertFalse((self.root/'etc/rc.d/daemonarchy_trace').exists())

    def test_both_abis_exact_payloads_root_metadata_and_idempotence(self):
        for abi, machine in [('amd64',62),('aarch64',183)]:
            with self.subTest(abi=abi):
                (self.root/'usr/local/share/daemonarchy-installer/ABI').write_text('FreeBSD:16:'+abi)
                py = self.root/'usr/local/bin/python3.12'
                py.chmod(0o755)
                data = bytearray(py.read_bytes())
                data[18:20] = machine.to_bytes(2,'little')
                py.write_bytes(data)
                result = self.stage()
                self.assertEqual(len(result['files']), 8)
                for entry in result['files']:
                    path = self.root/entry['path']
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o555)
                self.assertEqual(self.metadata(), self.root_before)
                self.assertFalse(result['runtime_capture_qualified'])
                self.assertEqual(result, self.stage())

    def test_missing_prerequisite_refuses_before_writes(self):
        (self.root/'bin/timeout').unlink()
        self.refuse('prerequisite missing')

    def test_nonexecutable_prerequisite(self):
        (self.root/'usr/bin/lockf').chmod(0o444)
        self.refuse('prerequisite missing')

    def test_wrong_abi_and_elf(self):
        marker = self.root/'usr/local/share/daemonarchy-installer/ABI'
        marker.write_text('FreeBSD:15:amd64')
        self.refuse('supported live-root ABI')
        marker.write_text('FreeBSD:16:aarch64')
        self.refuse('Python ABI mismatch')
        marker.write_text('FreeBSD:16:amd64')
        py = self.root/'usr/local/bin/python3.12'
        py.chmod(0o755)
        py.write_bytes(b'#!not ELF')
        self.refuse('Python ABI mismatch')

    def test_symlinked_input_ancestor(self):
        local = self.root/'usr/local'
        outside = self.base/'outside'
        local.rename(outside)
        local.symlink_to(outside, target_is_directory=True)
        self.refuse('symlink')
        self.assertFalse((outside/'libexec').exists())

    def test_late_symlink_destination_validated_before_any_write(self):
        dst = self.root/'etc/rc.d'
        dst.mkdir(parents=True)
        outside = self.base/'outside'
        outside.write_text('preserve')
        (dst/'daemonarchy_trace').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.stage()
        self.assertEqual(outside.read_text(), 'preserve')
        self.assertFalse((self.root/'usr/local/libexec').exists())

    def test_hardlinked_destination_preserved(self):
        dst = self.root/'usr/local/libexec/daemonarchy-boottrace'
        dst.mkdir(parents=True)
        outside = self.base/'outside'
        outside.write_text('preserve')
        os.link(outside, dst/'stick.py')
        self.refuse('multiply linked')
        self.assertEqual(outside.read_text(), 'preserve')

    def test_invalid_final_source_leaves_tree_unchanged(self):
        src = self.source/'overlay/usr/local/libexec/daemonarchy-installer/boot-trace'
        src.write_bytes(b'x'*262145)
        self.refuse('bounded regular')
        self.assertFalse((self.root/'usr/local/libexec').exists())

    def test_nondirectory_destination_parent(self):
        (self.root/'etc').write_text('preserve')
        self.refuse('non-directory')
        self.assertEqual((self.root/'etc').read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main(verbosity=2)
