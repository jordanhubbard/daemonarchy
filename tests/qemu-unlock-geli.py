#!/usr/bin/env python3
"""Unlock a disposable QEMU GELI test guest after detecting its real prompt.

BIOS bootcode asks before loader.conf can enable serial output. Read the VGA
text buffer through QMP in that case. Exit 2 means the prompt is not ready.
The fixed test password is read from stdin and is never logged.
"""
import errno
import json
import os
from pathlib import Path
import re
import socket
import sys
import time


def unlock(socket_path, mode, serial_log, password):
    if mode not in ("bios", "uefi"):
        raise ValueError("Expected bios or uefi")
    if not password or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789" for c in password):
        raise ValueError("Use a lowercase alphanumeric disposable test password")
    log = Path(serial_log)
    ready = log.exists() and b"GELI Passphrase for" in log.read_bytes()
    if not ready and mode == "uefi":
        return 2
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(5)
        path = Path(socket_path).resolve()
        previous = Path.cwd()
        try:
            os.chdir(path.parent)
            connection.connect(path.name)
        finally:
            os.chdir(previous)
        stream = connection.makefile("rwb", buffering=0)
        json.loads(stream.readline())

        def command(name, arguments=None):
            request = {"execute": name}
            if arguments is not None:
                request["arguments"] = arguments
            stream.write((json.dumps(request) + "\n").encode())
            while True:
                raw = stream.readline()
                if not raw:
                    raise RuntimeError("QMP connection closed")
                reply = json.loads(raw)
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                if "return" in reply:
                    return reply["return"]

        command("qmp_capabilities")
        if not ready:
            dump = command("human-monitor-command", {"command-line": "xp /4000bx 0xb8000"})
            cells = bytearray()
            for line in dump.splitlines():
                values = line.partition(":")[2]
                cells.extend(int(value, 16) for value in re.findall(r"0x([0-9a-fA-F]{2})(?![0-9a-fA-F])", values))
            ready = b"GELI Passphrase for" in bytes(cells[::2])
        if not ready:
            return 2
        for key in [*password, "ret"]:
            command("send-key", {"keys": [{"type": "qcode", "data": key}], "hold-time": 60})
            time.sleep(0.15)
    return 0


if __name__ == "__main__":
    try:
        status = unlock(*sys.argv[1:], sys.stdin.readline().rstrip("\n"))
    except OSError as error:
        if error.errno not in (errno.ENOENT, errno.ECONNREFUSED):
            raise
        status = 2
    sys.exit(status)
