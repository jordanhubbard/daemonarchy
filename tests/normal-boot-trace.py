#!/usr/bin/env python3
"""Normal record readback, corruption, retention and read-only extraction."""
import argparse
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
    if version == 3:
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


class Normal(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.volume = self.root / 'volume'
        (self.volume / 'NORMAL').mkdir(parents=True)

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
