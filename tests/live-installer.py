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


class NetworkViewTests(unittest.TestCase):
    def status(self, **changes):
        value = dict(ok=True, online=False, error='fetch: Network is unreachable', mode='dhcp', via='em0', ssid='',
                     clock='2026-10-26 10:00:00 UTC', checked=True, primary='em0', alternatives=['em1'],
                     dns='', dns_source='', need='', failure='', clock_state='', clock_status='usable',
                     manual_clock=False, adapters=[],
                     reports={'discover': ['Wired adapters: em0, em1.'], 'dhcp': ['Primary connection: em0.'],
                              'wifi-prepare': [], 'wifi-join': [], 'dns': ['DNS answers through em0.'],
                              'clock': ['System time is usable.'], 'firmware': []})
        value.update(changes)
        return value

    def test_each_step_reports_in_pipeline_order(self):
        view = gui.network_view(self.status(online=True))
        self.assertEqual(view['findings'], ['Wired adapters: em0, em1.', 'Primary connection: em0.',
                                            'DNS answers through em0.', 'System time is usable.'])
        self.assertEqual(view['status'], 'Package repository reachable securely through em0.')
        self.assertEqual(view['alternatives'], ['em1'])
        self.assertFalse(view['manual_clock'] or view['clock_unusable'])

    def test_failures_and_needs_are_shown(self):
        view = gui.network_view(self.status(need='dns', failure='No DNS server answered a direct lookup.'))
        self.assertIn('No DNS server answered', view['status'])
        self.assertIn('Network is unreachable', view['status'])
        self.assertEqual(view['need'], 'dns')
        wifi = gui.network_view(self.status(need='wifi', mode='wifi', ssid='home', online=True, via='wlan0'))
        self.assertIn('Join a Wi-Fi network', wifi['status'])
        self.assertIn('wlan0 (home)', wifi['status'])

    def test_manual_clock_only_after_network_time_failed(self):
        wrong = gui.network_view(self.status(clock_state='wrong', clock_status='before-build', manual_clock=True))
        self.assertTrue(wrong['manual_clock'])
        unchecked = gui.network_view(self.status(clock_status='before-build'))
        self.assertFalse(unchecked['manual_clock'])
        self.assertTrue(unchecked['clock_unusable'])

    def test_network_page_requests_exist_in_the_backend(self):
        for command in ('network-check', 'network-status', 'network-primary', 'network-dns', 'network-dhcp',
                        'network-static', 'wifi-scan', 'wifi-join', 'clock-sync', 'clock-set'):
            self.assertIn(f"'{command}'", (LIB/'live-installer').read_text(), command)
            self.assertIn(f'  {command}) cmd_', BACKEND, command)


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


    def test_shared_model_feeds_stages_ticker_download_and_activity(self):
        self.assertIs(gui.InstallProgress, gui.model.InstallProgress)
        model = gui.InstallProgress(self.log, self.status)
        self.write('@@step partition 1000', '@@phase base', self.metric(1), '@@phase fetch',
                   'Fetching bash-5.2.37: .......... done', '@@phase install',
                   '[1/3] Installing bash-5.2.37...', '[2/3] Installing curl-8.11.1...')
        view = model.poll()
        for key in ('title', 'details', 'fraction', 'done', 'succeeded', 'recent',
                    'stages', 'ticker', 'fetch', 'activity'):
            self.assertIn(key, view)
        text = gui.stages_text(view)
        self.assertIn('Base sets', text)
        self.assertIn('Packages', text)
        self.assertIn('now', text.splitlines()[[r['key'] for r in view['stages']].index('packages')])
        self.assertIn('curl-8.11.1', gui.ticker_text(view))
        self.assertIn('2/3', gui.ticker_text(view))
        self.assertIsInstance(gui.activity_text(view), str)

    def test_activity_text_uses_measured_counters_only(self):
        view = dict(activity=dict(available=True, current=dict(
            cpu=0.5, disk_write=2 << 20, disk_read=0, net_rx=1 << 20, net_tx=0,
            memory=dict(total=8 << 30, used=2 << 30, arc=1 << 30))), target=dict(encrypted=True))
        text = gui.activity_text(view)
        self.assertIn('CPU  50%', text)
        self.assertIn('2.0 MB/s', text)
        self.assertIn('ARC 1.0 GiB', text)
        self.assertIn('GELI', text)
        self.assertEqual(gui.activity_text(dict(activity=dict(available=False, current={}, error=''))), '')


if __name__ == '__main__':
    unittest.main()
