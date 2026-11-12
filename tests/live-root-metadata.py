#!/usr/bin/env python3
"""Archive root admission and native extraction regression controls."""
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('metadata', ROOT / 'scripts/live-root-metadata.py')
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


def archive(path, entries):
    with tarfile.open(path, 'w') as output:
        for mode, uid, gid, kind in entries:
            entry = tarfile.TarInfo('.')
            entry.type = kind
            entry.mode, entry.uid, entry.gid = mode, uid, gid
            output.addfile(entry)


class RootMetadata(unittest.TestCase):
    def test_invalid_archive_root_preserves_staging(self):
        cases = ([], [(0o700, 0, 0, tarfile.DIRTYPE)],
                 [(0o755, 1001, 0, tarfile.DIRTYPE)],
                 [(0o4755, 0, 0, tarfile.DIRTYPE)],
                 [(0o755, 0, 0, tarfile.REGTYPE)],
                 [(0o755, 0, 0, tarfile.DIRTYPE), (0o700, 0, 0, tarfile.DIRTYPE)])
        for entries in cases:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as directory:
                base = Path(directory); target = base / 'world'; target.mkdir(mode=0o700)
                source = base / 'world.tar'; archive(source, entries)
                before = target.stat()
                with self.assertRaises(ValueError):
                    metadata.restore(source, target)
                after = target.stat()
                self.assertEqual((after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)),
                                 (before.st_uid, before.st_gid, stat.S_IMODE(before.st_mode)))

    def test_symlink_inputs_and_staging_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); target = base / 'world'; target.mkdir()
            source = base / 'world.tar'; archive(source, [(0o755, 0, 0, tarfile.DIRTYPE)])
            alias = base / 'source-link'; alias.symlink_to(source)
            stage = base / 'stage-link'; stage.symlink_to(target, target_is_directory=True)
            for selected, destination in ((alias, target), (source, stage)):
                with self.assertRaises(ValueError):
                    metadata.restore(selected, destination)

    @unittest.skipUnless(os.geteuid() == 0, 'root required for exact archive ownership restoration')
    def test_native_extraction_restores_final_root_mode_and_group(self):
        for mode in (0o555, 0o755):
            with self.subTest(mode=oct(mode)), tempfile.TemporaryDirectory() as directory:
                base = Path(directory); target = base / 'world'; target.mkdir(mode=0o700)
                source = base / 'world.tar'
                archive(source, [(0o700, 0, 0, tarfile.DIRTYPE), (mode, 0, 1002, tarfile.DIRTYPE)])
                subprocess.run(['tar', '-xpf', str(source), '-C', str(target)], check=True,
                               capture_output=True)
                result = metadata.restore(source, target)
                self.assertEqual(result, dict(uid=0, gid=1002, mode=format(mode, '04o')))
                current = target.stat()
                self.assertEqual((current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode)),
                                 (0, 1002, mode))
                # A service user needs search permission to use the mounted root.
                self.assertEqual(stat.S_IMODE(current.st_mode) & 0o005, 0o005)


if __name__ == '__main__':
    unittest.main()
