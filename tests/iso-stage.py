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
