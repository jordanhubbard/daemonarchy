#!/usr/bin/env python3
"""Package-closure integrity and dependency controls; native pkg runs separately."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('closure', ROOT / 'scripts/arm-package-closure.py')
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)


class Closure(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = dict(schema=closure.SCHEMA, root='omarchy', packages=[])
        self.metadata = {}
        for name, deps in [('omarchy', ['library']), ('library', [])]:
            path = self.base / (name + '.pkg')
            path.write_bytes(('fixture bytes for ' + name).encode())
            row = dict(name=name, version='1.0_1', abi='FreeBSD:16:aarch64',
                       path=str(path), bytes=path.stat().st_size,
                       sha256=closure.digest(path), dependencies=deps)
            self.data['packages'].append(row)
            self.metadata[path] = {key: row[key] for key in ('name', 'version', 'abi', 'dependencies')}
        self.root_hash = self.data['packages'][0]['sha256']
        self.manifest = self.base / 'closure.json'
        mock = patch.object(closure, 'metadata', side_effect=lambda p: self.metadata[p])
        mock.start()
        self.addCleanup(mock.stop)

    def verify(self):
        self.manifest.write_text(json.dumps(self.data))
        return closure.verify(self.manifest, closure.digest(self.manifest), self.root_hash)

    def test_complete_closure_stages_exact_bytes_without_private_paths(self):
        result = self.verify()
        staged = self.base / 'staged'
        public = closure.stage(result, staged)
        self.assertEqual(len(list(staged.glob('*.pkg'))), 2)
        self.assertNotIn(str(self.base), json.dumps(public))
        for row in result['packages']:
            self.assertEqual(closure.digest(staged / (row['name'] + '-' + row['version'] + '.pkg')),
                             row['sha256'])

    def test_changed_manifest_refused(self):
        self.manifest.write_text(json.dumps(self.data))
        with self.assertRaisesRegex(ValueError, 'manifest checksum'):
            closure.verify(self.manifest, '0' * 64, self.root_hash)

    def test_changed_archive_refused(self):
        Path(self.data['packages'][1]['path']).write_bytes(b'changed bytes')
        with self.assertRaisesRegex(ValueError, 'archive checksum/size'):
            self.verify()

    def test_missing_dependency_refused(self):
        self.data['packages'].pop()
        with self.assertRaisesRegex(ValueError, 'missing dependency'):
            self.verify()

    def test_unrelated_package_refused(self):
        self.data['packages'][0]['dependencies'] = []
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            self.verify()

    def test_duplicate_name_refused(self):
        self.data['packages'].append(dict(self.data['packages'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.verify()

    def test_foreign_abi_refused(self):
        self.data['packages'][1]['abi'] = 'FreeBSD:16:amd64'
        with self.assertRaisesRegex(ValueError, 'foreign package ABI'):
            self.verify()

    def test_native_root_required_and_arch_independent_dependency_allowed(self):
        row = self.data['packages'][1]
        row['abi'] = 'FreeBSD:16:*'
        self.metadata[Path(row['path'])]['abi'] = row['abi']
        self.verify()
        self.data['packages'][0]['abi'] = 'FreeBSD:16:*'
        with self.assertRaisesRegex(ValueError, 'native AArch64'):
            self.verify()

    def test_symlink_archive_refused(self):
        path = Path(self.data['packages'][1]['path'])
        moved = self.base / 'target'
        path.rename(moved)
        path.symlink_to(moved)
        with self.assertRaisesRegex(ValueError, 'nonsymlink'):
            self.verify()

    def test_archive_metadata_must_match_declared_identity_and_edges(self):
        path = Path(self.data['packages'][0]['path'])
        self.metadata[path] = dict(self.metadata[path], version='2.0')
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.verify()
        self.metadata[path]['version'] = '1.0_1'
        self.metadata[path]['dependencies'] = []
        with self.assertRaisesRegex(ValueError, 'dependencies mismatch'):
            self.verify()

    def test_staging_detects_changes_after_preflight(self):
        result = self.verify()
        Path(self.data['packages'][1]['path']).write_bytes(b'changed after verification')
        with self.assertRaisesRegex(ValueError, 'changed while staging'):
            closure.stage(result, self.base / 'staged')

    def test_root_must_match_separate_package_pin(self):
        self.root_hash = '0' * 64
        with self.assertRaisesRegex(ValueError, 'pinned Omarchy'):
            self.verify()

    def test_cycle_refused_before_staging(self):
        self.data['packages'][1]['dependencies'] = ['omarchy']
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            self.verify()

    def test_install_upgrades_dependencies_before_their_users_in_one_pkg_writer(self):
        data = self.verify()
        staged, root = (self.base / name for name in ('staged', 'root'))
        repositories = root / 'ram-no-repos'
        closure.stage(data, staged)
        root.mkdir()
        repositories.mkdir()
        (root / 'ram-packages').mkdir()
        for path in staged.glob('*.pkg'):
            (root / 'ram-packages' / path.name).hardlink_to(path)
        with patch.object(closure.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '')) as run:
            closure.install(data, staged, root, repositories)
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertEqual(command[-2:], ['/ram-packages/library-1.0_1.pkg',
                                       '/ram-packages/omarchy-1.0_1.pkg'])
        self.assertEqual(command[1:3], ['-c', str(root)])
        self.assertIn('REPOS_DIR=/ram-no-repos', command)

    def test_install_refuses_staged_change_without_invoking_pkg(self):
        data = self.verify()
        staged, root = (self.base / name for name in ('staged', 'root'))
        repositories = root / 'ram-no-repos'
        closure.stage(data, staged)
        root.mkdir()
        repositories.mkdir()
        (staged / 'library-1.0_1.pkg').write_bytes(b'changed')
        with patch.object(closure.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'staged archive changed'):
                closure.install(data, staged, root, repositories)
        run.assert_not_called()

    def test_successful_pkg_exit_does_not_hide_failed_package_script(self):
        data = self.verify()
        staged, root = (self.base / name for name in ('staged', 'root'))
        closure.stage(data, staged)
        root.mkdir()
        repositories = root / 'ram-no-repos'
        repositories.mkdir()
        (root / 'ram-packages').mkdir()
        for path in staged.glob('*.pkg'):
            (root / 'ram-packages' / path.name).hardlink_to(path)
        def pkg_success_with_failed_script(command, **kwargs):
            kwargs['stdout'].write('pkg: POST-INSTALL script failed\n')
            return subprocess.CompletedProcess(command, 0)
        with patch.object(closure.subprocess, 'run', side_effect=pkg_success_with_failed_script), patch.object(closure.sys, 'stdout', io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'script failed despite successful pkg exit'):
                closure.install(data, staged, root, repositories)


if __name__ == '__main__':
    unittest.main()
