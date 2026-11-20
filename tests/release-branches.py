#!/usr/bin/env python3
"""Exercise release-forwarding policy against real disposable Git histories."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('branches', Path(__file__).resolve().parents[1] / 'scripts/check-release-branches.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseBranches(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.commit('base', 'base')
        self.git('branch', 'release/1.6')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE, text=True).strip()

    def commit(self, name, message):
        (self.repo / name).write_text(message)
        self.git('add', name)
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def inspect(self):
        return module.inspect(self.repo, 'refs/heads/', 'release/1.6')

    def test_contained_release(self):
        self.assertTrue(self.inspect()['ok'])

    def test_missing_ordinary_change(self):
        self.git('switch', '-q', 'release/1.6')
        commit = self.commit('fix', 'Fix shared behavior')
        report = self.inspect()
        self.assertFalse(report['ok'])
        self.assertEqual(report['branches'][0]['missing'], [commit])

    def test_patch_equivalent_backport(self):
        self.git('switch', '-q', 'release/1.6')
        commit = self.commit('fix', 'Release fix')
        self.git('switch', '-q', 'main')
        self.commit('other', 'Advance main independently')
        self.git('cherry-pick', commit)
        self.assertTrue(self.inspect()['ok'])
        self.assertEqual(self.inspect()['branches'][0]['patch_equivalent'], [commit])

    def test_documented_release_only_workaround(self):
        self.git('switch', '-q', 'release/1.6')
        self.commit('workaround', 'Keep old ABI for 1.6\n\nDaemonarchy-Release-Only: 1.6\nDaemonarchy-No-Forward-Port: Temporary ABI workaround; next release uses the new ABI.')
        report = self.inspect()
        self.assertTrue(report['ok'])
        self.assertEqual(len(report['branches'][0]['exceptions']), 1)

    def test_invalid_exception_is_rejected(self):
        self.git('switch', '-q', 'release/1.6')
        self.commit('workaround', 'Workaround\n\nDaemonarchy-Release-Only: 1.5\nDaemonarchy-No-Forward-Port: This release is incompatible with future ABI selections.')
        with self.assertRaisesRegex(ValueError, 'invalid release-only'):
            self.inspect()

    def test_generic_workaround_message_is_not_an_exception(self):
        self.git('switch', '-q', 'release/1.6')
        self.commit('workaround', 'Temporary workaround')
        self.assertFalse(self.inspect()['ok'])

    def test_missing_required_branch(self):
        self.git('branch', '-D', 'release/1.6')
        with self.assertRaisesRegex(ValueError, 'must both exist'):
            self.inspect()

    def test_historical_release_tip_also_checked(self):
        self.git('switch', '-qc', 'release/1.5.1')
        self.commit('fix', 'Fix old release and main')
        self.assertFalse(self.inspect()['ok'])

    def test_divergent_shallow_history_is_refused(self):
        self.git('switch', '-q', 'release/1.6')
        self.commit('fix', 'Release-only tip needing comparison')
        self.git('switch', '-q', 'main')
        self.commit('other', 'Independent main change')
        with tempfile.TemporaryDirectory() as destination:
            self.git('clone', '--depth=1', '--no-single-branch', self.repo.as_uri(), destination)
            with self.assertRaisesRegex(ValueError, 'shallow repository refused'):
                module.inspect(destination, 'refs/remotes/origin/', 'release/1.6')

    def test_identical_tips_need_no_older_history(self):
        with tempfile.TemporaryDirectory() as destination:
            self.git('clone', '--depth=1', '--no-single-branch', self.repo.as_uri(), destination)
            self.assertTrue(module.inspect(destination, 'refs/remotes/origin/', 'release/1.6')['ok'])

    def test_remote_divergence_requires_local_patch_audit(self):
        pages = [[{'name': 'main', 'commit': {'sha': 'a' * 40}},
                  {'name': 'release/1.6', 'commit': {'sha': 'b' * 40}}]]
        import json
        with patch.object(module.subprocess, 'check_output', side_effect=[
                json.dumps(pages), json.dumps({'status': 'diverged'})]):
            self.assertFalse(module.github_contained('daemonarchy', 'release/1.6')['ok'])

    def test_unique_merge_resolution_is_not_hidden_by_cherry(self):
        self.git('switch', '-qc', 'topic')
        topic = self.commit('shared', 'topic')
        self.git('switch', '-q', 'release/1.6')
        release = self.commit('shared', 'release')
        conflict = subprocess.run(['git', '-C', str(self.repo), 'merge', 'topic'], capture_output=True)
        self.assertEqual(conflict.returncode, 1)
        self.commit('shared', 'Unique merge resolution')
        self.git('switch', '-q', 'main')
        self.git('merge', '--ff-only', topic)
        # Simulate a separate patch-equivalent forward port of the release side.
        conflict = subprocess.run(['git', '-C', str(self.repo), 'merge', release], capture_output=True)
        self.assertEqual(conflict.returncode, 1)
        self.commit('shared', 'Different resolution on main')
        report = self.inspect()
        self.assertFalse(report['ok'])
        self.assertTrue(report['branches'][0]['unresolved_merge_commits'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
