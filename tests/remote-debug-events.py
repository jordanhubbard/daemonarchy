#!/usr/bin/env python3
"""Use a private broadcast-socket fixture; never send events to system devd."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

helper = Path(__file__).resolve().parents[1] / 'overlay/usr/local/libexec/daemonarchy-installer/debug-events.py'
with tempfile.TemporaryDirectory(prefix='daemonarchy-events-test-') as temporary:
    work = Path(temporary)
    state, logs = work / 'state', work / 'logs'
    state.mkdir()
    logs.mkdir()
    (state / 'active').touch()
    (state / 'generation').write_text('fixture-generation\n')
    server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    server.bind(str(work / 'fixture.socket'))
    server.listen(2)
    server.settimeout(10)
    code = f'import runpy,sys; runpy.run_path({str(helper)!r})["main"](sys.argv[5])'
    process = subprocess.Popen([sys.executable, '-c', code, str(state), 'fixture-generation',
                                str(logs), str(os.getpid()), str(work / 'fixture.socket')])

    def wait_events(count):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            path = logs / 'events.log'
            rows = [json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []
            if len([row for row in rows if row['kind'] == 'devd-event']) >= count:
                return rows
            assert process.poll() is None, 'event reader exited early'
            time.sleep(0.05)
        raise AssertionError('Device event was not retained')

    try:
        connection, _ = server.accept()
        connection.send(b'fixture-first-event\n')
        rows = wait_events(1)
        assert rows[-1]['message'] == 'fixture-first-event\n'
        connection.close()
        # A devd-like disconnect must reconnect while the session stays active.
        connection, _ = server.accept()
        connection.send(b'fixture-after-reconnect\n')
        rows = wait_events(2)
        assert sum(row['kind'] == 'devd-connected' for row in rows) == 2
        assert (logs / 'events.log').stat().st_mode & 0o777 == 0o600
        (state / 'generation').write_text('replacement-generation\n')
        assert process.wait(timeout=4) == 0
        connection.close()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
        server.close()
print('PASS: private device events, reconnect, permissions and generation exit')
