#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Relay an inspection to an operator-selected root-only guest Unix socket.

Use an SSH remote Unix-socket forward to the worker owner's inspection socket.
Never forward QMP. This stdlib-only client grants no allocation or admission.
"""

import argparse
import ctypes
import json
import os
from pathlib import Path
import socket
import stat
import sys
import time

LIMIT = 65536


def exchange(endpoint, request, *, expected_uid):
    if not endpoint.is_absolute() or endpoint.resolve(strict=True) != endpoint:
        raise ValueError("canonical operator socket required")
    before = endpoint.lstat()
    if (
        not stat.S_ISSOCK(before.st_mode)
        or before.st_uid != expected_uid
        or before.st_mode & 0o077
    ):
        raise ValueError("private operator socket required")
    if not request or len(request) > LIMIT:
        raise ValueError("inspection request budget exceeded")
    json.loads(request)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
        channel.settimeout(20)
        channel.connect(str(endpoint))
        function = ctypes.CDLL(None, use_errno=True).getpeereid
        function.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
        ]
        function.restype = ctypes.c_int
        uid, gid = ctypes.c_uint(), ctypes.c_uint()
        if (
            function(channel.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0
            or uid.value != expected_uid
        ):
            raise ValueError("inspection socket peer identity refused")
        channel.sendall(request.rstrip(b"\n") + b"\n")
        response = b""
        deadline = time.monotonic() + 20
        while b"\n" not in response:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("inspection deadline exceeded")
            channel.settimeout(remaining)
            block = channel.recv(min(4096, LIMIT + 1 - len(response)))
            if not block:
                raise ValueError("incomplete inspection response")
            response += block
            if len(response) > LIMIT:
                raise ValueError("inspection response budget exceeded")
    after = endpoint.lstat()
    stamp = lambda v: (v.st_dev, v.st_ino, v.st_uid, v.st_gid, v.st_mode)
    if stamp(before) != stamp(after):
        raise ValueError("inspection endpoint changed")
    response = response.split(b"\n", 1)[0]
    json.loads(response)
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith("freebsd") or os.geteuid() != 0:
        raise ValueError("FreeBSD root inspection client required")
    request = sys.stdin.buffer.read(LIMIT + 1)
    sys.stdout.buffer.write(exchange(args.socket, request, expected_uid=0) + b"\n")


if __name__ == "__main__":
    main()
