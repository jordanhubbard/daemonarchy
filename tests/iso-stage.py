#!/usr/bin/env python3
"""I preserve failed staging and isolate simultaneous authoring attempts."""
import concurrent.futures
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ISOStage(unittest.TestCase):
    def allocate(self, parent):
        return subprocess.run(['sh', '-c', '. "$1"; iso_stage_create', 'stage-test',
                               str(ROOT / 'scripts/iso-stage.sh')],
                              env={**os.environ, 'ISO_STAGE_PARENT': str(parent)},
                              text=True, capture_output=True)

    def test_concurrent_attempts_preserve_prior_and_failed_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            previous = parent / 'daemonarchy-iso-stage'
            previous.mkdir()
            sentinel = previous / 'failure-evidence'
            sentinel.write_bytes(b'prior failure evidence')
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(self.allocate, [parent, parent]))
            for result in results:
                self.assertEqual(result.returncode, 0, result.stderr)
            stages = [Path(result.stdout.strip()) for result in results]
            self.assertNotEqual(stages[0], stages[1])
            for stage in stages:
                self.assertEqual(stage.parent, parent)
                self.assertEqual(stat.S_IMODE(stage.stat().st_mode), 0o700)
            (stages[0] / 'partial-product').write_bytes(b'failed attempt')
            subsequent = self.allocate(parent)
            self.assertEqual(subsequent.returncode, 0, subsequent.stderr)
            self.assertEqual(sentinel.read_bytes(), b'prior failure evidence')
            self.assertEqual((stages[0] / 'partial-product').read_bytes(), b'failed attempt')

    def fresh_outputs(self, *paths):
        return subprocess.run(
            ['sh', '-c', '. "$1"; shift; iso_stage_require_fresh_outputs "$@"',
             'fresh-test', str(ROOT / 'scripts/iso-stage.sh'), *map(str, paths)],
            text=True, capture_output=True)

    def test_fresh_outputs_check_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.fresh_outputs(root / 'image.iso', root / 'image.iso.sha256',
                                        root / 'image.iso.xz')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(root.iterdir()), [])

    def test_existing_files_directories_and_links_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / 'previous.iso'
            sentinel.write_bytes(b'previous published or failed image')
            (root / 'stage').mkdir()
            (root / 'alias').symlink_to(sentinel)
            (root / 'dangling').symlink_to(root / 'absent')
            for existing in [sentinel, root / 'stage', root / 'alias', root / 'dangling']:
                with self.subTest(existing=existing.name):
                    before = sorted(p.name for p in root.iterdir())
                    result = self.fresh_outputs(root / 'new.iso', existing)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('Preserve existing image evidence', result.stderr)
                    self.assertEqual(sentinel.read_bytes(), b'previous published or failed image')
                    self.assertEqual(sorted(p.name for p in root.iterdir()), before)

    def test_invalid_parent_refuses_without_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'file').write_text('preserve')
            (root / 'alias').symlink_to(root, target_is_directory=True)
            before = sorted(p.name for p in root.iterdir())
            for parent in ('relative-path', root / 'absent', root / 'file', root / 'alias'):
                result = self.allocate(parent)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
            self.assertEqual(sorted(p.name for p in root.iterdir()), before)

if __name__ == '__main__':
    unittest.main()
