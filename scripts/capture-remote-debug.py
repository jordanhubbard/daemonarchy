#!/usr/bin/env python3
"""Retain an approved SSH debug stream on the controller across target resets."""
import argparse
import datetime
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh-wrapper', required=True,
                        help='Executable SSH wrapper with the approved key and strict host pin')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=int, default=1800,
                        help='Finite capture duration in seconds (default: 1800)')
    args = parser.parse_args()
    if not 1 <= args.duration <= 86400:
        parser.error('duration must be between 1 and 86400 seconds')
    wrapper = Path(args.ssh_wrapper).absolute()
    if not wrapper.is_file() or not os.access(wrapper, os.X_OK):
        parser.error('SSH wrapper must be an executable file')
    os.umask(0o077)
    if args.output.is_symlink():
        parser.error('output directory must not be a symlink')
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.output.stat().st_uid != os.getuid():
        parser.error('output directory must belong to the current user')
    args.output.chmod(0o700)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    prefix = args.output / f'capture-{stamp}-{os.getpid()}'
    # Four 32-MiB parts bound one capture without deleting earlier evidence.
    part, size = 0, 0
    output = open(f'{prefix}.{part}.log', 'xb', buffering=0)
    events = open(f'{prefix}.jsonl', 'x', buffering=1)

    def event(name, **details):
        events.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                     event=name, **details)) + '\n')
        events.flush()
        os.fsync(events.fileno())

    process = subprocess.Popen([str(wrapper), 'daemonarchy-debug observe'],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    event('ssh-process-started', pid=process.pid, duration=args.duration)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + args.duration
    last_flush = last_data = time.monotonic()
    idle_reported = False
    reason = 'connection-closed'
    try:
        def stop_capture(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, stop_capture)
        signal.signal(signal.SIGHUP, stop_capture)
        while True:
            now = time.monotonic()
            if now >= deadline:
                reason = 'duration-reached'
                break
            ready = selector.select(min(1, deadline - now))
            if ready:
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    break
                if size + len(data) > 32 * 1024 * 1024:
                    os.fsync(output.fileno())
                    output.close()
                    part += 1
                    if part == 4:
                        reason = 'capture-size-limit'
                        break
                    output = open(f'{prefix}.{part}.log', 'xb', buffering=0)
                    size = 0
                output.write(data)
                size += len(data)
                last_data = now
                idle_reported = False
            if now - last_flush >= 1:
                os.fsync(output.fileno())
                last_flush = now
            if now - last_data >= 30 and not idle_reported:
                event('stream-idle', seconds=30)
                idle_reported = True
    except KeyboardInterrupt:
        reason = 'operator-stopped'
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        code = process.wait()
        if not output.closed:
            os.fsync(output.fileno())
            output.close()
        event(reason, ssh_exit_status=code, parts=min(part + 1, 4))
        events.close()
        process.stdout.close()
    print(f'Debug capture retained: {prefix}.*')
    if reason == 'connection-closed':
        print('Connection ended. Inspect the retained log; verify a fresh pairing fingerprint before reconnecting.')
    return 0 if reason in ('duration-reached', 'operator-stopped') or code == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
