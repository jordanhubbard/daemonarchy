#!/usr/bin/env python3
"""Exercise exact live loader selection and refusal before mutation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/test-loader.py'
spec = importlib.util.spec_from_file_location('test_loader', SCRIPT)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


class TestLoader(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.selection = {'schema': 'daemonarchy/test-loader@1',
                          'scope': 'live-image-only', 'source_revision': 'a' * 40,
                          'files': {}}
        for name, data in [('loader.efi', b'candidate EFI'), ('loader.lua', b'candidate Lua')]:
            (self.bundle / name).write_bytes(data)
            self.selection['files'][name] = {'sha256': hashlib.sha256(data).hexdigest(),
                                            'bytes': len(data)}
        self.write_selection()
        self.world = self.root / 'world'
        (self.world / 'boot/lua').mkdir(parents=True)
        (self.world / 'boot/loader.efi').write_bytes(b'original EFI')
        (self.world / 'boot/lua/loader.lua').write_bytes(b'original Lua')
        self.installer_set = self.world / 'usr/freebsd-dist/base.txz'
        self.installer_set.parent.mkdir(parents=True)
        self.installer_set.write_bytes(b'unchanged installer set')

    def write_selection(self):
        (self.bundle / 'selection.json').write_text(json.dumps(self.selection))

    def unchanged(self):
        self.assertEqual((self.world / 'boot/loader.efi').read_bytes(), b'original EFI')
        self.assertEqual((self.world / 'boot/lua/loader.lua').read_bytes(), b'original Lua')

    def test_exact_live_payload_preserves_sets_and_does_not_enable_debug(self):
        staged = self.root / 'staged'
        loader.prepare(self.bundle, staged)
        loader.install(staged, self.world)
        self.assertEqual((self.world / 'boot/loader.efi').read_bytes(), b'candidate EFI')
        self.assertEqual((self.world / 'boot/lua/loader.lua').read_bytes(), b'candidate Lua')
        self.assertEqual(self.installer_set.read_bytes(), b'unchanged installer set')
        self.assertFalse((self.world / 'boot/debug.key').exists())
        self.assertFalse((self.world / 'boot/loader.conf').exists())
        with self.assertRaises(FileExistsError):
            loader.prepare(self.bundle, staged)

    def test_tampered_lua_refuses_before_either_file_changes(self):
        (self.bundle / 'loader.lua').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            loader.install(self.bundle, self.world)
        self.unchanged()

    def test_readonly_hardlinked_jail_files_remain_unchanged(self):
        cached = self.root / 'cached-loader.efi'
        original = self.world / 'boot/loader.efi'
        original.chmod(0o555)
        os.link(original, cached)
        loader.install(self.bundle, self.world)
        self.assertEqual(cached.read_bytes(), b'original EFI')
        self.assertEqual(original.read_bytes(), b'candidate EFI')
        self.assertEqual(original.stat().st_mode & 0o777, 0o555)

    def test_signed_bundle_conflict_refuses_before_mutation(self):
        (self.world / 'usr/local/share/daemonarchy-installer/secureboot').mkdir(parents=True)
        with self.assertRaises(ValueError):
            loader.install(self.bundle, self.world)
        self.unchanged()

    def test_input_and_destination_aliases_refuse(self):
        efi = self.bundle / 'loader.efi'
        efi.rename(self.bundle / 'actual.efi')
        efi.symlink_to('actual.efi')
        with self.assertRaises(ValueError):
            loader.install(self.bundle, self.world)
        self.unchanged()
        efi.unlink()
        efi.write_bytes((self.bundle / 'actual.efi').read_bytes())
        (self.world / 'boot/lua').rename(self.world / 'boot/actual-lua')
        (self.world / 'boot/lua').symlink_to('actual-lua', target_is_directory=True)
        with self.assertRaises(ValueError):
            loader.install(self.bundle, self.world)
        self.unchanged()

    def test_extra_destination_or_missing_source_identity_refuses(self):
        for mutation in ['extra', 'revision', 'scope']:
            selection = json.loads(json.dumps(self.selection))
            if mutation == 'extra':
                selection['files']['../loader.conf'] = {}
            elif mutation == 'revision':
                del selection['source_revision']
            else:
                selection['scope'] = 'installed-system'
            (self.bundle / 'selection.json').write_text(json.dumps(selection))
            with self.assertRaises(ValueError):
                loader.install(self.bundle, self.world)
            self.unchanged()


if __name__ == '__main__':
    unittest.main()
