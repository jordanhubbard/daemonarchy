#!/usr/bin/env python3
"""The graphical installer's logic without a display: backend protocol,
answer fields, error routing and measured progress from the install log."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT/'overlay/usr/local/libexec/daemonarchy-installer'
loader = importlib.machinery.SourceFileLoader('live_installer', str(LIB/'live-installer'))
spec = importlib.util.spec_from_loader('live_installer', loader)
gui = importlib.util.module_from_spec(spec)
loader.exec_module(gui)
BACKEND = (LIB/'live-backend').read_text()
BACKEND_FIELDS = set(re.findall(r'^\s*(?:field|flag) (\w+)', BACKEND, re.M))
BACKEND_ERRORS = set(re.findall(r'invalid (\w+) ', BACKEND)) - {'"$1"'}


def runner(stdout='', returncode=0, stderr=''):
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    return run, calls


def answers(**changes):
    value = dict(keyboard='us', username='alice', password='pw', password_confirmation='pw',
                 full_name='', email_address='', hostname='', timezone='UTC', ssh_enable=False,
                 install_ports=True, install_src=False, encrypt_installation=True, disk='ada0',
                 disk_snapshot='a'*64, install_mode='whole_disk', partition_index='2', efi_index='1',
                 confirm_partition='ada0p2', free_start='1000', install_size_mib='30000')
    value.update(changes)
    return value


class BackendProtocolTests(unittest.TestCase):
    def test_requests_run_through_sudo_without_a_password_prompt(self):
        run, calls = runner('{"ok": true, "disks": []}\n')
        reply = gui.Backend(run).call('partitions', 'ada0')
        self.assertEqual(reply['disks'], [])
        self.assertEqual(calls[0][0], ('sudo', '-n', str(LIB/'live-backend'), 'partitions', 'ada0'))

    def test_failures_carry_the_field_to_revisit(self):
        run, _ = runner('{"ok": false, "field": "username", "message": "Username is reserved for system"}', 1)
        with self.assertRaises(gui.BackendError) as caught:
            gui.Backend(run).call('write-conf', data='{}')
        self.assertEqual((caught.exception.field, str(caught.exception)), ('username', 'Username is reserved for system'))
        self.assertEqual(gui.page_for('username'), 'account')

    def test_unparseable_or_unsuccessful_replies_are_errors(self):
        for stdout, code in (('not json', 0), ('{"ok": false}', 0), ('{"ok": true}', 1), ('', 0)):
            run, _ = runner(stdout, code, 'sudo: a password is required')
            with self.assertRaises(gui.BackendError):
                gui.Backend(run).call('facts')

    def test_text_steps_are_fixed(self):
        command = gui.Backend(runner()[0]).terminal_command('network')
        self.assertEqual(command[-2:], ['terminal-step', 'network'])
        self.assertIn('sudo', command)
        with self.assertRaises(ValueError):
            gui.Backend(runner()[0]).terminal_command('shell')


class AnswerTests(unittest.TestCase):
    def test_request_fields_are_exactly_what_the_backend_reads(self):
        for mode in ('whole_disk', 'partition', 'free_space'):
            request = gui.build_request(answers(install_mode=mode))
            self.assertLessEqual(set(request), BACKEND_FIELDS, mode)
            for key in ('ssh_enable', 'install_ports', 'install_src', 'encrypt_installation'):
                self.assertIs(type(request[key]), bool)
            for key, value in request.items():
                if type(value) is not bool:
                    self.assertIs(type(value), str, key)
        whole = gui.build_request(answers())
        self.assertFalse({'partition_index', 'efi_index', 'confirm_partition', 'free_start'} & set(whole))
        partition = gui.build_request(answers(install_mode='partition'))
        self.assertEqual((partition['partition_index'], partition['confirm_partition']), ('2', 'ada0p2'))
        free = gui.build_request(answers(install_mode='free_space'))
        self.assertEqual((free['free_start'], free['install_size_mib']), ('1000', '30000'))
        self.assertNotIn('partition_index', free)

    def test_every_backend_error_routes_to_a_screen(self):
        self.assertTrue(BACKEND_ERRORS)
        for name in BACKEND_ERRORS:
            self.assertIn(name, gui.FIELD_PAGES, name)
            self.assertIn(gui.page_for(name), gui.PAGES)
        self.assertEqual(gui.page_for(None), 'review')

    def test_confirmation_names_what_is_erased(self):
        self.assertIn('All partitions and data on ada0 will be destroyed.', gui.confirmation_text(answers()))
        self.assertIn('ada0p2 will be erased', gui.confirmation_text(answers(install_mode='partition')))
        self.assertIn('30000 MiB', gui.confirmation_text(answers(install_mode='free_space')))


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = Path(self.dir.name)/'install.log'
        self.status = Path(self.dir.name)/'install.status'
        self.log.write_text('')

    def tearDown(self):
        self.dir.cleanup()

    def write(self, *rows):
        with self.log.open('a') as stream:
            stream.write(''.join(row + '\n' for row in rows))

    def metric(self, current):
        return '@@progress ' + json.dumps(dict(schema='daemonarchy/installer-progress@1', phase='base',
                                                  label='Release archives expanded', current=current,
                                                  total=3, unit='archives'))

    def test_measured_counters_only_and_no_premature_completion(self):
        model = gui.InstallProgress(self.log, self.status)
        view = model.poll()
        self.assertFalse(view['done'])
        self.assertIsNone(view['fraction'])
        self.write('@@phase base', self.metric(1))
        view = model.poll()
        self.assertEqual(view['title'], 'Installing FreeBSD')
        self.assertAlmostEqual(view['fraction'], 1/3)
        self.write(self.metric(3))
        view = model.poll()
        self.assertEqual(view['fraction'], 1)
        self.assertFalse(view['done'])
        self.assertNotIn('Daemonarchy is installed.', view['title'])

    def test_result_file_decides_success(self):
        model = gui.InstallProgress(self.log, self.status)
        self.write('@@phase base', self.metric(3), 'Daemonarchy is installed.')
        self.status.write_text('0\n')
        view = model.poll()
        self.assertTrue(view['done'] and view['succeeded'])
        self.assertEqual(view['title'], 'Daemonarchy is installed.')

    def test_failure_shows_recent_log_lines(self):
        model = gui.InstallProgress(self.log, self.status)
        self.write('@@phase disk', 'gpart: Device busy')
        self.status.write_text('1\n')
        view = model.poll()
        self.assertTrue(view['done'])
        self.assertFalse(view['succeeded'])
        self.assertIn('gpart: Device busy', view['recent'])
        self.assertIn('exit 1', view['title'])

    def test_invalid_progress_is_not_reported_as_clean_success(self):
        model = gui.InstallProgress(self.log, self.status)
        self.write('@@phase base', self.metric(2), self.metric(1))
        self.status.write_text('0\n')
        view = model.poll()
        self.assertTrue(view['done'])
        self.assertFalse(view['succeeded'])


if __name__ == '__main__':
    unittest.main()
