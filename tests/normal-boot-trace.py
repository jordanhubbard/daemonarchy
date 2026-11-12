#!/usr/bin/env python3
"""Normal record readback, corruption, retention and read-only extraction."""
import argparse
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stick', ROOT / 'tools/boottrace/stick.py')
stick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stick)


def record(version=1, **changes):
    values = dict(image_id='01234567-89ab-cdef-0123-456789abcdef',
                  archive_sha256='ab' * 32, trace_partition='fedcba98-7654-3210-fedc-ba9876543210',
                  session='0001', phase='loader-ready', identity='declared-archive',
                  early_kernel_backend='not-enabled')
    if version in (3, 4):
        values.update(boot_nonce=bytes(range(32)).hex(), boot_identity='firmware-rng')
    values.update(changes)
    body = (f'Daemonarchy normal boot trace v{version}\n' +
            ''.join(f'{key}={value}\n' for key, value in values.items())).encode()
    return stick.padded(body + f'sum={stick.fnv1a(body):08x}\n'.encode(), stick.SLOT_SIZE)


def staged_record(later=None, version=2, **changes):
    primary = record(version=version, **changes)[:stick.NORMAL_STAGE_SIZE]
    if later is None:
        later = b'\n' * stick.NORMAL_STAGE_SIZE
    return primary + later + b'\n' * (stick.SLOT_SIZE - 2 * stick.NORMAL_STAGE_SIZE)


def userspace_bank(phase='init-ready', content=b'bounded kernel console\n', **changes):
    values = dict(phase=phase,
                  content_kind={'init-ready': 'kernel-console', 'installer': 'installer-events'}[phase],
                  content_bytes=str(len(content)), content_sha256=hashlib.sha256(content).hexdigest(),
                  content_truncated='no', content_base64=base64.b64encode(content).decode('ascii'))
    values.update(changes)
    return record(version=4, **values)[:stick.NORMAL_STAGE_SIZE]


def userspace_slot(init=None, installer=None):
    blank = b'\n' * stick.NORMAL_STAGE_SIZE
    return (record(version=4)[:stick.NORMAL_STAGE_SIZE] +
            record(version=4, phase='pre-exit')[:stick.NORMAL_STAGE_SIZE] +
            (blank if init is None else init) + (blank if installer is None else installer))


class Normal(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.volume = self.root / 'volume'
        (self.volume / 'NORMAL').mkdir(parents=True)

    def test_v4_empty_later_banks_keep_loader_and_preexit_results(self):
        value = stick.normal_record(userspace_slot())
        self.assertEqual(value['schema'], 'daemonarchy/normal-boot-trace@4')
        self.assertEqual(value['pre_exit']['status'], 'recorded')
        self.assertEqual(value['init']['status'], 'not-recorded')
        self.assertEqual(value['installer']['status'], 'not-recorded')

    def test_v4_bounded_content_identity_and_independent_stages(self):
        content = b'kernel console\nwith binary \x00\xff bytes'
        events = b'{"event":"phase_begin","phase":"base"}\n'
        value = stick.normal_record(userspace_slot(
            userspace_bank(content=content), userspace_bank('installer', events, content_truncated='yes')))
        for key, expected in (('init', content), ('installer', events)):
            bank = value[key]
            self.assertEqual(bank['status'], 'recorded')
            self.assertEqual(base64.b64decode(bank['record']['content_base64']), expected)
            self.assertEqual(bank['record']['content_sha256'], hashlib.sha256(expected).hexdigest())
            self.assertEqual(int(bank['record']['content_bytes']), len(expected))
        self.assertEqual(value['installer']['record']['content_truncated'], 'yes')

    def test_v4_wrong_or_oversized_content_and_replayed_identity_preserve_other_banks(self):
        faults = [dict(content_bytes='2049'), dict(content_bytes='00'),
                  dict(content_bytes='-1'), dict(content_bytes='3'),
                  dict(content_sha256='00' * 32), dict(content_base64='!invalid'),
                  dict(content_base64='YQ==\t'), dict(content_truncated='unknown'),
                  dict(content_kind='arbitrary-command'), dict(phase='installer'),
                  dict(boot_nonce=bytes(range(1, 33)).hex()), dict(session='0002'),
                  dict(archive_sha256='cd' * 32),
                  dict(trace_partition='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')]
        for fault in faults:
            with self.subTest(fault=fault):
                bad = userspace_bank(**fault) if fault.get('phase') != 'installer' else userspace_bank('installer')
                value = stick.normal_record(userspace_slot(bad, userspace_bank('installer')))
                self.assertEqual(value['phase'], 'loader-ready')
                self.assertEqual(value['pre_exit']['status'], 'recorded')
                self.assertEqual(value['init']['status'], 'unreadable')
                self.assertEqual(value['installer']['status'], 'recorded')

    def test_v4_torn_installer_write_preserves_init_and_readonly_raw_extraction(self):
        bad = bytearray(userspace_bank('installer')); bad[100] ^= 1
        slot = userspace_slot(userspace_bank(), bytes(bad))
        (self.volume / 'NORMAL/0001.TXT').write_bytes(slot)
        before = hashlib.sha256(slot).hexdigest()
        output = self.root / 'extracted'
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            stick.cmd_normal(argparse.Namespace(target=str(self.volume), out=str(output)))
        result = json.loads(stdout.getvalue())
        row = result['records'][0]
        self.assertEqual(row['status'], 'partial')
        self.assertEqual(row['record']['init']['status'], 'recorded')
        self.assertEqual(row['record']['installer']['status'], 'unreadable')
        self.assertFalse(result['volume_modified'])
        self.assertEqual((output / '0001.TXT').read_bytes(), slot)
        self.assertEqual(hashlib.sha256((self.volume / 'NORMAL/0001.TXT').read_bytes()).hexdigest(), before)

    def test_v4_content_limit_and_legacy_reserved_space_remain_enforced(self):
        maximum = userspace_bank(content=b'x' * 2048)
        self.assertEqual(stick.normal_record(userspace_slot(maximum))['init']['status'], 'recorded')
        oversized = userspace_bank(content=b'x' * 2049)
        self.assertEqual(stick.normal_record(userspace_slot(oversized))['init']['status'], 'unreadable')
        # Old v3 slots do not silently adopt a new use of their reserved space.
        legacy = staged_record(version=3)
        legacy = legacy[:2 * stick.NORMAL_STAGE_SIZE] + maximum + legacy[3 * stick.NORMAL_STAGE_SIZE:]
        with self.assertRaisesRegex(ValueError, 'reserved'):
            stick.normal_record(legacy)

    def test_empty_is_distinct_from_a_record_and_short_or_partial_data(self):
        self.assertIsNone(stick.normal_record(stick.padded(stick.NORMAL_EMPTY, stick.SLOT_SIZE)))
        for data in (b'', record()[:-1], stick.padded(b'partial write', stick.SLOT_SIZE)):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                stick.normal_record(data)

    def test_valid_record_preserves_declared_scope_and_session(self):
        value = stick.normal_record(record())
        self.assertEqual((value['phase'], value['identity'], value['session']),
                         ('loader-ready', 'declared-archive', '0001'))
        self.assertEqual(value['early_kernel_backend'], 'not-enabled')

    def test_changed_bytes_or_padding_cannot_pass_as_a_record(self):
        original = record()
        for index in (0, 100, stick.SLOT_SIZE - 1):
            data = bytearray(original)
            data[index] ^= 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                stick.normal_record(data)

    def test_correct_checksum_does_not_admit_foreign_schema_or_invalid_fields(self):
        for changes in (dict(image_id='invalid'), dict(session='0033'), dict(session='0000'),
                        dict(archive_sha256='invalid'), dict(phase='kernel-qualified'),
                        dict(extra='unsupported')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                stick.normal_record(record(**changes))

    def test_extraction_preserves_corrupt_slots_and_never_changes_volume(self):
        files = {'0001.TXT': record(), '0002.TXT': stick.padded(b'partial', stick.SLOT_SIZE),
                 '0003.TXT': stick.padded(stick.NORMAL_EMPTY, stick.SLOT_SIZE)}
        for name, data in files.items():
            (self.volume / 'NORMAL' / name).write_bytes(data)
        output = self.root / 'returned'
        with contextlib.redirect_stdout(io.StringIO()):
            stick.cmd_normal(argparse.Namespace(target=str(self.volume), out=str(output)))
        result = json.loads((output / 'normal.json').read_text())
        self.assertFalse(result['volume_modified'])
        self.assertEqual((result['initialized_slots'], result['empty_slots']), (3, 1))
        self.assertEqual([r['status'] for r in result['records']], ['recorded', 'unreadable'])
        for name, data in files.items():
            self.assertEqual((self.volume / 'NORMAL' / name).read_bytes(), data)
            self.assertEqual((output / name).read_bytes(), data)
        self.assertEqual(result['records'][0]['sha256'], hashlib.sha256(files['0001.TXT']).hexdigest())
        with self.assertRaises(FileExistsError):
            stick.cmd_normal(argparse.Namespace(target=str(self.volume), out=str(output)))

    def test_output_inside_volume_is_refused_before_creation(self):
        output = self.volume / 'returned'
        with self.assertRaisesRegex(ValueError, 'outside'):
            stick.cmd_normal(argparse.Namespace(target=str(self.volume), out=str(output)))
        self.assertFalse(output.exists())


    def test_v2_keeps_the_primary_checkpoint_before_preexit(self):
        value = stick.normal_record(staged_record())
        self.assertEqual(value['schema'], 'daemonarchy/normal-boot-trace@2')
        self.assertEqual(value['phase'], 'loader-ready')
        self.assertEqual(value['pre_exit']['status'], 'not-recorded')
        self.assertEqual(value['early_kernel_backend'], 'not-enabled')

    def test_v2_decodes_an_independently_bound_preexit_checkpoint(self):
        later = record(version=2, phase='pre-exit')[:stick.NORMAL_STAGE_SIZE]
        value = stick.normal_record(staged_record(later))
        self.assertEqual(value['pre_exit']['status'], 'recorded')
        self.assertEqual(value['pre_exit']['record']['phase'], 'pre-exit')
        self.assertEqual(value['pre_exit']['sha256'], hashlib.sha256(later).hexdigest())

    def test_v2_preserves_primary_when_later_data_is_partial_foreign_or_corrupt(self):
        for later in (stick.padded(b'partial', stick.NORMAL_STAGE_SIZE),
                      record(version=2, phase='pre-exit', session='0002')[:stick.NORMAL_STAGE_SIZE],
                      record(version=1)[:stick.NORMAL_STAGE_SIZE],
                      record(version=2, phase='kernel-qualified')[:stick.NORMAL_STAGE_SIZE]):
            with self.subTest(data=later[:50]):
                value = stick.normal_record(staged_record(later))
                self.assertEqual(value['phase'], 'loader-ready')
                self.assertEqual(value['pre_exit']['status'], 'unreadable')

    def test_v2_rejects_damaged_primary_and_unknown_reserved_writes(self):
        for offset in (0, 100, stick.NORMAL_STAGE_SIZE - 1, stick.SLOT_SIZE - 1):
            data = bytearray(staged_record())
            data[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                stick.normal_record(data)

    def test_v2_extraction_retains_both_banks_and_reports_partial_later_stage(self):
        data = staged_record(stick.padded(b'partial', stick.NORMAL_STAGE_SIZE))
        (self.volume / 'NORMAL/0001.TXT').write_bytes(data)
        output = self.root / 'v2-returned'
        with contextlib.redirect_stdout(io.StringIO()):
            stick.cmd_normal(argparse.Namespace(target=str(self.volume), out=str(output)))
        result = json.loads((output / 'normal.json').read_text())
        self.assertEqual(result['records'][0]['status'], 'partial')
        self.assertEqual(result['records'][0]['record']['phase'], 'loader-ready')
        self.assertEqual((output / '0001.TXT').read_bytes(), data)
        self.assertEqual((self.volume / 'NORMAL/0001.TXT').read_bytes(), data)

    def test_v3_nonce_is_shared_across_independent_banks(self):
        later = record(version=3, phase='pre-exit')[:stick.NORMAL_STAGE_SIZE]
        value = stick.normal_record(staged_record(later, version=3))
        self.assertEqual(value['schema'], 'daemonarchy/normal-boot-trace@3')
        self.assertEqual(value['boot_nonce'], bytes(range(32)).hex())
        self.assertEqual(value['pre_exit']['record']['boot_nonce'], value['boot_nonce'])

    def test_v3_reports_missing_rng_without_a_fabricated_nonce(self):
        changes = dict(boot_nonce='unavailable', boot_identity='unavailable')
        later = record(version=3, phase='pre-exit', **changes)[:stick.NORMAL_STAGE_SIZE]
        value = stick.normal_record(staged_record(later, version=3, **changes))
        self.assertEqual(value['boot_identity'], 'unavailable')
        self.assertEqual(value['pre_exit']['status'], 'recorded')

    def test_v3_correct_checksums_cannot_admit_bad_identity_metadata(self):
        for changes in [dict(boot_nonce='00' * 32), dict(boot_nonce='ab' * 32),
                        dict(boot_nonce='0A' * 32), dict(boot_nonce='short'),
                        dict(boot_nonce='unavailable'), dict(boot_identity='unavailable')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                stick.normal_record(staged_record(version=3, **changes))

    def test_v3_foreign_boot_nonce_keeps_the_earlier_bank(self):
        later = record(version=3, phase='pre-exit',
                       boot_nonce=bytes(reversed(range(32))).hex())[:stick.NORMAL_STAGE_SIZE]
        value = stick.normal_record(staged_record(later, version=3))
        self.assertEqual(value['boot_nonce'], bytes(range(32)).hex())
        self.assertEqual(value['pre_exit']['status'], 'unreadable')

    def test_v3_cannot_mix_a_legacy_later_bank(self):
        later = record(version=2, phase='pre-exit')[:stick.NORMAL_STAGE_SIZE]
        value = stick.normal_record(staged_record(later, version=3))
        self.assertEqual(value['pre_exit']['status'], 'unreadable')

    def test_v3_partial_export_preserves_exact_slot_and_boot_identity(self):
        data = staged_record(stick.padded(b'partial later write', stick.NORMAL_STAGE_SIZE),
                             version=3)
        (self.volume / 'NORMAL/0001.TXT').write_bytes(data)
        output = self.root / 'v3-export'
        with contextlib.redirect_stdout(io.StringIO()):
            stick.cmd_normal(argparse.Namespace(target=str(self.volume), out=str(output)))
        value = json.loads((output / 'normal.json').read_text())['records'][0]
        self.assertEqual(value['status'], 'partial')
        self.assertEqual(value['record']['boot_identity'], 'firmware-rng')
        self.assertEqual((output / '0001.TXT').read_bytes(), data)
        self.assertEqual((self.volume / 'NORMAL/0001.TXT').read_bytes(), data)

    def test_legacy_experiment_reset_does_not_erase_normal_sessions(self):
        path = self.volume / 'NORMAL/0001.TXT'
        path.write_bytes(record())
        experiments = self.root / 'experiments'
        experiments.write_text('[explicit-experiment]\nnormal_test=YES\n')
        with contextlib.redirect_stdout(io.StringIO()):
            stick.main(['init', str(self.volume)])
            stick.main(['queue', str(self.volume), str(experiments), '--reset-traces'])
        self.assertEqual(path.read_bytes(), record())


if __name__ == '__main__':
    unittest.main()
