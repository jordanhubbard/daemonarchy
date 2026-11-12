#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Project public installer facts and relay bounded batches to the boot medium.

The performance trace is an input, never a payload. In particular its `exit`
event precedes pool export and cannot establish an installation result.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import select
import stat
import subprocess
import sys
import tempfile
import time
import uuid

SCHEMA = 'daemonarchy/installer-evidence@1'
LIMIT = 32768
PHASES = ('disk', 'base', 'loader', 'config', 'fetch', 'install', 'user',
          'checkouts', 'cuda', 'finish')
PACKAGE_EVENTS = ('INFO_INSTALL_BEGIN', 'INFO_INSTALL_FINISHED',
                  'INFO_EXTRACT_BEGIN', 'INFO_EXTRACT_FINISHED',
                  'INFO_UPGRADE_BEGIN', 'INFO_UPGRADE_FINISHED',
                  'INFO_EXTRACT', 'INSTALLED_SNAPSHOT')
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+,\-]{0,159}\Z')
DISK = re.compile(r'[a-z][a-z0-9]{0,30}[0-9](?:p[0-9]+)?\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


def canonical(row):
    return json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode() + b'\n'


def validate(row):
    if not isinstance(row, dict) or row.get('schema') != SCHEMA:
        raise ValueError('installer evidence schema required')
    attempt = row.get('attempt')
    if not isinstance(attempt, str) or str(uuid.UUID(attempt)) != attempt:
        raise ValueError('canonical installer attempt required')
    sequence = row.get('sequence')
    if type(sequence) is not int or not 1 <= sequence <= 0xffffffff:
        raise ValueError('installer event sequence required')
    kind = row.get('kind')
    fields = {'schema', 'attempt', 'sequence', 'kind'}
    if kind == 'phase':
        fields |= {'name', 'boundary'}
        if row.get('name') not in PHASES or row.get('boundary') not in ('begin', 'end'):
            raise ValueError('fixed installer phase required')
    elif kind == 'artifact':
        fields |= {'name', 'sha256'}
        if row.get('name') not in ('base', 'kernel', 'lib32'):
            raise ValueError('release archive name required')
        if row.get('sha256') is not None and (not isinstance(row['sha256'], str) or not DIGEST.fullmatch(row['sha256'])):
            raise ValueError('archive digest required')
    elif kind == 'target':
        fields |= {'device', 'identity_sha256'}
        if not isinstance(row.get('device'), str) or not DISK.fullmatch(row['device']):
            raise ValueError('canonical target device required')
        if row.get('identity_sha256') is not None and (not isinstance(row['identity_sha256'], str) or not DIGEST.fullmatch(row['identity_sha256'])):
            raise ValueError('target identity digest required')
    elif kind == 'target-partition':
        fields |= {'device', 'mode', 'uuid'}
        if (not isinstance(row.get('device'), str) or not DISK.fullmatch(row['device']) or
                row.get('mode') not in ('whole_disk', 'partition', 'free_space')):
            raise ValueError('selected target partition required')
        if row.get('uuid') is not None and (not isinstance(row['uuid'], str) or str(uuid.UUID(row['uuid'])) != row['uuid']):
            raise ValueError('canonical target partition UUID required')
    elif kind in ('package', 'download'):
        fields |= {'name'}
        if not isinstance(row.get('name'), str) or not TOKEN.fullmatch(row['name']):
            raise ValueError('public package identifier required')
        if kind == 'package':
            fields |= {'event', 'version'}
            if row.get('event') not in PACKAGE_EVENTS:
                raise ValueError('package boundary required')
            if row.get('version') is not None and (not isinstance(row['version'], str) or not TOKEN.fullmatch(row['version'])):
                raise ValueError('public package version required')
        else:
            fields |= {'bytes'}
            if type(row.get('bytes')) is not int or not 0 <= row['bytes'] < 2**63:
                raise ValueError('observed download size required')
    elif kind == 'result':
        fields |= {'status'}
        if type(row.get('status')) is not int or not 0 <= row['status'] <= 255:
            raise ValueError('actual installer exit status required')
    elif kind == 'inventory':
        fields |= {'status', 'count'}
        if (row.get('status') not in ('recorded', 'unavailable') or
                type(row.get('count')) is not int or not 0 <= row['count'] <= 100000):
            raise ValueError('observed package inventory required')
    elif kind not in ('started', 'interrupted'):
        raise ValueError('unsupported installer evidence kind')
    if set(row) != fields:
        raise ValueError('unexpected installer evidence fields')
    return row


def project(source, attempt, sequence):
    """Discard unknown events/fields; recognized facts still undergo validation."""
    if not isinstance(source, dict):
        raise ValueError('installer trace row must be an object')
    event = source.get('event')
    row = dict(schema=SCHEMA, attempt=attempt, sequence=sequence)
    if event == 'trace_start':
        row['kind'] = 'started'
    elif event in ('phase_begin', 'phase_end'):
        row.update(kind='phase', name=source.get('name'), boundary=event[6:])
    elif event == 'artifact':
        row.update(kind='artifact', name=source.get('name'), sha256=source.get('sha256') or None)
    elif event == 'target':
        row.update(kind='target', device=source.get('device'), identity_sha256=source.get('identity_sha256') or None)
    elif event == 'target_partition':
        row.update(kind='target-partition', device=source.get('device'), mode=source.get('mode'), uuid=source.get('uuid') or None)
    elif event == 'installed_package':
        row.update(kind='package', name=source.get('name'), event='INSTALLED_SNAPSHOT', version=source.get('version'))
    elif event == 'package_inventory':
        row.update(kind='inventory', status=source.get('status'), count=source.get('count'))
    elif event == 'installer_result':
        row.update(kind='result', status=source.get('status'))
    else:
        return None
    return validate(row)


def read_private(path, limit, expected=None, with_info=False):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > limit):
            raise ValueError('bounded private regular input required')
        if expected is not None and (info.st_dev, info.st_ino) != tuple(expected):
            raise ValueError('installer input inode changed')
        content = os.read(fd, limit + 1)
        if len(content) > limit:
            raise ValueError('installer input exceeds limit')
        return (content, info) if with_info else content
    finally:
        os.close(fd)


def batch(path):
    data = read_private(path, LIMIT)
    rows = data.splitlines(keepends=True)
    if not rows:
        raise ValueError('nonempty installer batch required')
    previous = None
    for index, line in enumerate(rows):
        row = validate(json.loads(line))
        if canonical(row) != line:
            raise ValueError('canonical installer event required')
        if previous and (row['attempt'] != previous['attempt'] or row['sequence'] != previous['sequence'] + 1):
            raise ValueError('contiguous single-attempt batch required')
        previous = row
        if row['kind'] in ('result', 'interrupted') and index != len(rows) - 1:
            raise ValueError('facts after installer terminal result')
    return data


def append_batch(previous, content):
    """Refuse missing/replayed batches; a durable last-batch retry is idempotent."""
    rows = [validate(json.loads(line)) for line in content.splitlines()]
    if not rows:
        raise ValueError('nonempty evidence batch required')
    for left, right in zip(rows, rows[1:]):
        if (left['attempt'] != right['attempt'] or right['sequence'] != left['sequence'] + 1 or
                left['kind'] in ('result', 'interrupted')):
            raise ValueError('noncontiguous installer facts')
    if previous.endswith(content):
        return previous
    seen = None
    for line in previous.splitlines():
        try:
            old = json.loads(line)
        except (ValueError, UnicodeError):
            continue  # Preserve the older constant --event fixture records.
        if isinstance(old, dict) and old.get('attempt') == rows[0]['attempt']:
            seen = validate(old)
    expected = seen['sequence'] + 1 if seen else 1
    if (rows[0]['sequence'] != expected or (not seen and rows[0]['kind'] != 'started') or
            (seen and seen['kind'] in ('result', 'interrupted'))):
        raise ValueError('installer batch sequence or terminal boundary mismatch')
    return previous + content


def replace_private(path, content):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.installer-evidence-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def inventory(path, data, phase):
    """One native producer process for a bounded name/version DB snapshot."""
    if len(data) > 524288 or phase not in PHASES + ('none',):
        raise ValueError('bounded package inventory required')
    rows = []
    now = time.time_ns() // 1000
    started = os.environ.get('DAEMONARCHY_TRACE_START_US', '')
    if not re.fullmatch(r'[0-9]{1,20}', started):
        raise ValueError('installer timer origin required')
    since = now - int(started)
    for line in data.decode('ascii').splitlines():
        if not line.strip():
            continue
        pair = line.split()
        if len(pair) != 2 or any(not TOKEN.fullmatch(value) for value in pair):
            raise ValueError('public package name/version pair required')
        rows.append(canonical(dict(event='installed_package', name=pair[0], version=pair[1],
                                   t_us=now, since_start_us=since, phase=phase, source='installer-package-inventory')))
    rows.append(canonical(dict(event='package_inventory', status='recorded', count=len(rows),
                               t_us=now, since_start_us=since, phase=phase, source='installer-package-inventory')))
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_nlink != 1:
            raise ValueError('private performance trace required')
        content = b''.join(rows)
        if os.write(fd, content) != len(content):
            raise OSError('partial package inventory append')
    finally:
        os.close(fd)


def start(path, producer_pid):
    if not sys.platform.startswith('freebsd') or os.geteuid() != 0:
        return
    selected = subprocess.run(['/bin/kenv', '-q', 'daemonarchy.trace.capture'], capture_output=True, timeout=5)
    if selected.returncode or selected.stdout.strip() != b'saved':
        return
    # Validate the producer before starting a privileged reader.
    _, info = read_private(path, 8192, with_info=True)
    state = Path(tempfile.mkdtemp(prefix='daemonarchy-installer-evidence.', dir='/var/run'))
    if type(producer_pid) is not int or producer_pid <= 0:
        raise ValueError('installer producer required')
    replace_private(state / 'input.json', canonical(dict(attempt=str(uuid.uuid4()), device=info.st_dev,
                                                       inode=info.st_ino, producer_pid=producer_pid)))
    subprocess.run(['/usr/sbin/daemon', '-p', str(state / 'pid'), '-o', str(state / 'worker.log'),
                    '/bin/timeout', '-k', '5', '86400', '/usr/local/bin/python3.12',
                    str(Path(__file__).resolve()), 'follow', str(path), str(state)], check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(state)


def submit(state, content):
    target = state / 'batch.jsonl'
    replace_private(target, content)
    # The native wrapper retains its lock, transfer bound and admission guards.
    result = subprocess.run(['/usr/local/libexec/daemonarchy-installer/boot-trace',
                             'installer', '--events-file', str(target)],
                            capture_output=True, timeout=130)
    if result.returncode:
        raise ValueError('native installer capture unavailable')
    receipt = json.loads(result.stdout)
    if not receipt.get('writes_admitted') or not receipt.get('full_log_retention'):
        raise ValueError('native installer capture not admitted')


def follow(path, state, deliver=submit):
    """Incremental bounded reader; only the background job waits for device I/O."""
    state = Path(state)
    metadata = json.loads(read_private(state / 'input.json', 4096))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    sequence = written = 0
    pending = b''
    buffered = b''
    finished = False
    last = time.monotonic()
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or
                info.st_mode & 0o077 or info.st_nlink != 1 or
                (info.st_dev, info.st_ino) != (metadata['device'], metadata['inode'])):
            raise ValueError('private producer inode required')
        with closing(select.kqueue()) as queue:
            watch = select.kevent(fd, filter=select.KQ_FILTER_VNODE, flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                                 fflags=select.KQ_NOTE_WRITE | select.KQ_NOTE_RENAME | select.KQ_NOTE_DELETE)
            queue.control([watch], 0, 0)
            gone = False
            try:
                process = select.kevent(metadata['producer_pid'], filter=select.KQ_FILTER_PROC,
                                        flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                                        fflags=select.KQ_NOTE_EXIT)
                queue.control([process], 0, 0)
            except ProcessLookupError:
                gone = True
            while True:
                chunk = os.read(fd, 65536)
                if chunk:
                    buffered += chunk
                    while b'\n' in buffered:
                        line, buffered = buffered.split(b'\n', 1)
                        if len(line) > 8192:
                            raise ValueError('installer row exceeds limit')
                        row = project(json.loads(line), metadata['attempt'], sequence + 1)
                        if row is None:
                            continue
                        if finished:
                            raise ValueError('installer facts after terminal result')
                        encoded = canonical(row)
                        if pending and len(pending) + len(encoded) > LIMIT:
                            deliver(state, pending)
                            written = sequence
                            pending = b''
                            last = time.monotonic()
                        sequence += 1
                        pending += encoded
                        finished = row['kind'] == 'result'
                    if len(buffered) > 8192:
                        raise ValueError('unterminated installer row exceeds limit')
                if not chunk and gone and not finished:
                    if pending and len(pending) + 256 > LIMIT:
                        deliver(state, pending)
                        written = sequence
                        pending = b''
                    sequence += 1
                    pending += canonical(validate(dict(schema=SCHEMA, attempt=metadata['attempt'],
                                                       sequence=sequence, kind='interrupted')))
                    finished = True
                if pending and (finished or time.monotonic() - last >= 5):
                    deliver(state, pending)
                    written = sequence
                    pending = b''
                    last = time.monotonic()
                if finished:
                    break
                if not chunk:
                    current = os.lstat(path)
                    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                        raise ValueError('installer producer replaced its input')
                    events = queue.control(None, 2, max(0.01, 5 - (time.monotonic() - last)) if pending else 30)
                    gone = gone or any(event.filter == select.KQ_FILTER_PROC for event in events)
        replace_private(state / 'result.json', canonical(dict(status='recorded', events_written=written)))
    except (OSError, ValueError, subprocess.SubprocessError):
        replace_private(state / 'result.json', canonical(dict(status='unavailable', events_written=written)))
        raise
    finally:
        os.close(fd)


def drain(state, timeout=120):
    state = Path(state)
    info = state.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('private installer state required')
    deadline = time.monotonic() + timeout
    fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        with closing(select.kqueue()) as queue:
            watch = select.kevent(fd, filter=select.KQ_FILTER_VNODE, flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                                 fflags=select.KQ_NOTE_WRITE)
            queue.control([watch], 0, 0)
            while True:
                try:
                    result = json.loads(read_private(state / 'result.json', 4096))
                    return result.get('status') == 'recorded'
                except FileNotFoundError:
                    pass
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                queue.control(None, 1, remaining)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'start', 'follow', 'drain', 'inventory'))
    parser.add_argument('path')
    parser.add_argument('state', nargs='?')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            replace_private(args.path, b'')
        elif args.command == 'start':
            start(args.path, int(args.state) if args.state else 0)
        elif args.command == 'follow':
            if args.state is None:
                raise ValueError('installer state required')
            follow(args.path, args.state)
        elif args.command == 'inventory':
            inventory(args.path, sys.stdin.buffer.read(524289), args.state or 'none')
        elif not drain(args.path):
            return 1
    except (OSError, ValueError, subprocess.SubprocessError):
        # No raw input or exception text may flow back into the installer UI.
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
