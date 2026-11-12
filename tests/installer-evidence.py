#!/usr/bin/env python3
"""Privacy, durable-batch ordering and actual installer outcome boundaries."""
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/boottrace/installer-evidence.py'
LIB = ROOT / 'overlay/usr/local/libexec/daemonarchy-installer'
spec = importlib.util.spec_from_file_location('evidence', TOOL)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)
ATTEMPT = str(uuid.uuid4())


def row(event, sequence=1, **fields):
    return evidence.project(dict(event=event, **fields), ATTEMPT, sequence)


class EvidenceTests(unittest.TestCase):
    def test_projection_drops_answers_output_and_performance_exit(self):
        for event in ('sample', 'exit', 'op_begin', 'error', 'password', 'pkg_event', 'download'):
            self.assertIsNone(row(event, status=0, output='secret', password='secret'))
        data = evidence.canonical(row('phase_begin', name='base', password='secret', output='secret'))
        self.assertNotIn(b'secret', data)
        with self.assertRaises(ValueError):row('phase_begin', name='password=secret')
        with self.assertRaises(ValueError):row('installed_package', name='https://user:secret@host/pkg', version='1')
        with self.assertRaises(ValueError):row('target', device='gpt/private-user-label')

    def test_known_facts_and_strict_field_types(self):
        for event, fields in [('artifact', dict(name='base', sha256='a'*64)),
                              ('target', dict(device='nda0p3', identity_sha256='b'*64)),
                              ('installed_package', dict(name='tmux', version='3.8_1,1')),
                              ('installer_result', dict(status=37))]:
            evidence.validate(row(event, **fields))
        for status in (True, -1, 256, '0'):
            with self.assertRaises(ValueError):row('installer_result', status=status)
        bad = dict(row('trace_start'), password='secret')
        with self.assertRaises(ValueError):evidence.validate(bad)

    def test_safe_prepare_replaces_leaf_symlink_without_touching_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = root/'private'; target.write_text('keep me')
            link = root/'trace'; link.symlink_to(target)
            evidence.replace_private(link, b'fresh')
            self.assertFalse(link.is_symlink())
            self.assertEqual(target.read_text(), 'keep me')
            self.assertEqual(link.stat().st_mode & 0o777, 0o600)

    def test_inventory_keeps_numeric_versions_and_fits_runtime_package_budget(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'DAEMONARCHY_TRACE_START_US':'1'}):
            path = Path(temp)/'trace'
            evidence.replace_private(path, b'')
            entries = ''.join(f'package-{index} 20261110\n' for index in range(1500)).encode()
            evidence.inventory(path, entries, 'finish')
            rows = [json.loads(line) for line in path.read_bytes().splitlines()]
            projected = [evidence.project(item, ATTEMPT, index+1) for index,item in enumerate(rows)]
            self.assertEqual(rows[0]['version'], '20261110')
            self.assertEqual(projected[-1]['count'], 1500)
            self.assertLess(sum(len(evidence.canonical(item)) for item in projected), 520192 - 32768)
            before = path.read_bytes()
            with self.assertRaises(ValueError):evidence.inventory(path, b'name https://user:password@host\n', 'finish')
            self.assertEqual(path.read_bytes(), before)

    def test_batches_refuse_symlink_public_file_extra_fields_and_gaps(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'batch'
            data = evidence.canonical(row('trace_start'))
            evidence.replace_private(path, data)
            self.assertEqual(evidence.batch(path), data)
            link = Path(temp)/'link'; link.symlink_to(path)
            with self.assertRaises(OSError):evidence.batch(link)
            path.chmod(0o644)
            with self.assertRaises(ValueError):evidence.batch(path)
            evidence.replace_private(path, data + evidence.canonical(row('phase_begin', 3, name='base')))
            with self.assertRaises(ValueError):evidence.batch(path)
            evidence.replace_private(path, evidence.canonical(dict(row('trace_start'), secret='password')))
            with self.assertRaises(ValueError):evidence.batch(path)

    def test_append_retry_preserves_prefix_and_refuses_replay_gap_and_post_result(self):
        first = evidence.canonical(row('trace_start'))
        next_batch = evidence.canonical(row('phase_begin', 2, name='base'))
        prefix = b'installer=started\n'
        written = evidence.append_batch(prefix, first)
        self.assertEqual(evidence.append_batch(written, first), written)
        written = evidence.append_batch(written, next_batch)
        self.assertTrue(written.startswith(prefix))
        with self.assertRaises(ValueError):evidence.append_batch(written, first)
        with self.assertRaises(ValueError):evidence.append_batch(written, evidence.canonical(row('installer_result', 4, status=0)))
        written = evidence.append_batch(written, evidence.canonical(row('installer_result', 3, status=37)))
        with self.assertRaises(ValueError):evidence.append_batch(written, evidence.canonical(row('phase_begin', 4, name='base')))

    def test_real_exit_handler_keeps_export_failure_after_performance_close_zero(self):
        engine = (LIB/'install').read_text()
        begin = engine.index('trace_closed=false')
        functions = engine[begin:engine.index("trap 'exit 130' INT", begin)]
        for outcome in (0, 37):
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/'trace'
                program = '''set -euo pipefail
source "$1/install-trace"
install_evidence_tool=$2
trace_sampler_pid=; geli_debug_saved=; cuda_setup_started=false; diagnostics_ready=false
TARGET=/unused-evidence-test
umount() { :; }
trace_init "$3"
trace_event installed_package name test-data version 20261110
'''+functions+'''\ntrace_close 0
zpool() { return "$4"; }
zpool export zroot "$4"
'''
                # Keep the stub's exit status explicit; no disk operation runs.
                program = program.replace('zpool() { return "$4"; }', 'zpool() { return '+str(outcome)+'; }')
                result = subprocess.run(['bash','-c',program,'test',str(LIB),str(TOOL),str(path),str(outcome)], capture_output=True)
                self.assertEqual(result.returncode, outcome, result.stderr.decode())
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                package = next(x for x in rows if x['event']=='installed_package')
                self.assertEqual(package['version'], '20261110')
                evidence.project(package, ATTEMPT, 2)
                self.assertEqual([x['status'] for x in rows if x['event']=='exit'], [0])
                self.assertEqual([x['status'] for x in rows if x['event']=='installer_result'], [outcome])

    def test_entry_handler_records_failure_before_configuration_or_abi_reads(self):
        engine=(LIB/'install').read_text()
        prefix=engine[:engine.index('ABI=$(cat')]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace'
            prefix=prefix.replace('/tmp/daemonarchy-install-trace.jsonl',str(path))
            result=subprocess.run(['bash','-c',prefix+'\nexit 23\n',str(LIB/'install')],capture_output=True)
            self.assertEqual(result.returncode,23,result.stderr.decode())
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(rows[0]['event'],'trace_start')
            self.assertEqual(rows[-1]['event'],'installer_result')
            self.assertEqual(rows[-1]['status'],23)

    @unittest.skipUnless(hasattr(select, 'kqueue'), 'requires native kqueue worker')
    def test_native_terminal_drain_has_a_real_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            before=time.monotonic()
            self.assertFalse(evidence.drain(temp, timeout=0.02))
            self.assertLess(time.monotonic()-before, 1)
            evidence.replace_private(Path(temp)/'result.json', b'{"status":"recorded","events_written":2}\n')
            self.assertTrue(evidence.drain(temp, timeout=0.02))

    @unittest.skipUnless(hasattr(select, 'kqueue'), 'requires native kqueue worker')
    def test_native_background_reader_completion_and_producer_loss(self):
        for interrupted in (False, True):
            with tempfile.TemporaryDirectory() as temp:
                state = Path(temp); trace = state/'trace'
                source = dict(event='trace_start', password='must-not-leak')
                evidence.replace_private(trace, evidence.canonical(source))
                producer = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
                info = trace.stat()
                evidence.replace_private(state/'input.json', evidence.canonical(dict(attempt=ATTEMPT,device=info.st_dev,inode=info.st_ino,producer_pid=producer.pid)))
                if not interrupted:
                    with trace.open('ab') as stream:stream.write(evidence.canonical(dict(event='installer_result', status=37)))
                program = '''import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('e',sys.argv[1]);e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
def deliver(state,data):
 with (state/'delivered').open('ab') as out:out.write(data)
e.follow(sys.argv[2],sys.argv[3],deliver)
'''
                worker = subprocess.Popen([sys.executable,'-c',program,str(TOOL),str(trace),str(state)], stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                producer.communicate(b'', timeout=5)
                _, error = worker.communicate(timeout=15)
                self.assertEqual(worker.returncode, 0, error.decode())
                delivered = (state/'delivered').read_bytes()
                self.assertNotIn(b'must-not-leak', delivered)
                last = json.loads(delivered.splitlines()[-1])
                self.assertEqual(last['kind'], 'interrupted' if interrupted else 'result')
                if not interrupted:self.assertEqual(last['status'], 37)


if __name__ == '__main__':
    unittest.main()
