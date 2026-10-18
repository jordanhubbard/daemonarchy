#!/usr/bin/env python3
"""Passive devd broadcast capture; no daemon replacement or event consumption."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import socket
import sys
import time


def main(socket_path='/var/run/devd.seqpacket.pipe'):
    state, generation, directory, parent = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), int(sys.argv[4])
    os.umask(0o077)
    path = directory / 'events.log'
    previous = directory / 'events.previous.log'
    for item in (path, previous, directory / 'events.lock'):
        if item.is_symlink():
            raise RuntimeError('Refusing symlinked event log')
    lock = (directory / 'events.lock').open('a')
    # A previous collector's child notices parent exit within one second.
    deadline = time.monotonic() + 4
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise RuntimeError('Another event reader is still active')
            time.sleep(0.1)

    def record(kind, **values):
        row = (json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                               session=generation, kind=kind, **values)) + '\n').encode()
        if path.exists() and path.stat().st_size + len(row) > 4 * 1024 * 1024:
            path.replace(previous)
        with path.open('ab', buffering=0) as output:
            output.write(row)

    def active():
        try:
            return os.getppid() == parent and (state / 'active').is_file() and (state / 'generation').read_text().strip() == generation
        except FileNotFoundError:
            return False

    try:
        while active():
            connection = None
            try:
                connection = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
                connection.settimeout(1)
                connection.connect(socket_path)
                record('devd-connected')
                while active():
                    try:
                        data = connection.recv(65536)
                    except socket.timeout:
                        continue
                    if not data:
                        record('devd-disconnected')
                        break
                    record('devd-event', message=data.decode(errors='replace'))
            except (OSError, AttributeError) as error:
                record('devd-unavailable', reason=str(error))
            finally:
                if connection is not None:
                    connection.close()
            # A restarted devd can be reattached without restarting pairing.
            for _ in range(5):
                if not active():
                    return
                time.sleep(1)
    finally:
        lock.close()


if __name__ == '__main__':
    main()
