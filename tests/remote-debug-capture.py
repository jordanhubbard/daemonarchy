#!/usr/bin/env python3
"""Prove the controller retains final remote output when its transport dies."""
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

receiver = Path(__file__).resolve().parents[1] / 'scripts/capture-remote-debug.py'
with tempfile.TemporaryDirectory(prefix='daemonarchy-capture-test-') as temporary:
    work = Path(temporary)
    wrapper = work / 'ssh-wrapper'
    wrapper.write_text('#!/bin/sh\n[ "$1" = "daemonarchy-debug observe" ] || exit 8\n'
                       'printf "last kernel message before reset\\n"\nkill -KILL $$\n')
    wrapper.chmod(0o700)
    result = subprocess.run([sys.executable, str(receiver), '--ssh-wrapper', str(wrapper),
                             '--output', str(work / 'evidence'), '--duration', '5'], check=False)
    assert result.returncode == 1
    evidence = work / 'evidence'
    assert evidence.stat().st_mode & 0o777 == 0o700
    logs = list(evidence.glob('*.log'))
    assert len(logs) == 1 and b'last kernel message before reset' in logs[0].read_bytes()
    assert logs[0].stat().st_mode & 0o777 == 0o600
    events = [json.loads(row) for row in next(evidence.glob('*.jsonl')).read_text().splitlines()]
    assert events[0]['event'] == 'ssh-process-started'
    assert events[-1]['event'] == 'connection-closed' and events[-1]['ssh_exit_status'] != 0
    wrapper.write_text('#!/bin/sh\nexec sleep 20\n')
    result = subprocess.run([sys.executable, str(receiver), '--ssh-wrapper', str(wrapper),
                             '--output', str(work / 'bounded'), '--duration', '1'], check=False)
    assert result.returncode == 0
    events = [json.loads(row) for row in next((work / 'bounded').glob('*.jsonl')).read_text().splitlines()]
    assert events[-1]['event'] == 'duration-reached'
    wrapper.write_text('#!/bin/sh\nprintf "transport-pid=%s\\n" "$$"\nexec sleep 20\n')
    receiver_process = subprocess.Popen([sys.executable, str(receiver), '--ssh-wrapper', str(wrapper),
                                         '--output', str(work / 'signal'), '--duration', '20'])
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        files = list((work / 'signal').glob('*.log'))
        if files and b'transport-pid=' in files[0].read_bytes():
            break
        time.sleep(0.05)
    else:
        raise AssertionError('No live transport PID captured')
    transport = int(files[0].read_text().split('transport-pid=')[1].splitlines()[0])
    receiver_process.send_signal(signal.SIGTERM)
    assert receiver_process.wait(timeout=7) == 0
    try:
        os.kill(transport, 0)
    except ProcessLookupError:
        pass
    else:
        raise AssertionError('Receiver signal left its SSH transport alive')
print('PASS: final output survives transport death; private files and finite capture')
