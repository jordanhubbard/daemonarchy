#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Own one disposable QEMU worker and expose bounded read-only inspections.

Operator configuration and policy live in a private case directory. Inspection
requests cannot select paths, execute commands, allocate or control the VM.
The guest still runs trusted privileged code; this is not a containment sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import signal
import socket
import stat
import subprocess
import time

REQUEST = "urn:literate-ai:schema:v1:retained-allocation-inspection-request"
RESPONSE = "urn:literate-ai:schema:v1:retained-allocation-inspection-response"
LIMIT = 65536


def unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def encoded(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def identity(value):
    return "sha256:" + hashlib.sha256(encoded(value)).hexdigest()


def digest(path):
    value = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stamp = lambda v: (
        v.st_dev,
        v.st_ino,
        v.st_mode,
        v.st_size,
        v.st_mtime_ns,
        v.st_ctime_ns,
    )
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("regular digest input required")
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
        after = os.fstat(stream.fileno())
    if stamp(before) != stamp(after) or stamp(after) != stamp(path.lstat()):
        raise ValueError("digest input changed during read")
    return value.hexdigest()


def node(path):
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_nlink != 1
    ):
        raise ValueError("owned single-link regular file required")
    return info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode


def private_json(path):
    if path.resolve(strict=True) != path:
        raise ValueError("canonical configuration path required")
    parent = path.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise ValueError("private owned configuration directory required")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_nlink != 1
            or before.st_mode & 0o077
            or before.st_size > LIMIT
        ):
            raise ValueError("private owned configuration file required")
        content = stream.read(LIMIT + 1)
        after = os.fstat(stream.fileno())
    stamp = lambda v: (
        v.st_dev,
        v.st_ino,
        v.st_mode,
        v.st_uid,
        v.st_gid,
        v.st_nlink,
        v.st_size,
        v.st_mtime_ns,
        v.st_ctime_ns,
    )
    if (
        len(content) > LIMIT
        or stamp(before) != stamp(after)
        or stamp(after) != stamp(path.lstat())
        or stamp(parent) != stamp(path.parent.stat())
    ):
        raise ValueError("configuration changed during read")
    return json.loads(content, object_pairs_hook=unique)


def publish(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


class Lines:
    def __init__(self, channel, deadline):
        self.channel, self.deadline, self.pending = channel, deadline, b""

    def read(self):
        while b"\n" not in self.pending:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("total request deadline exceeded")
            self.channel.settimeout(remaining)
            block = self.channel.recv(min(4096, LIMIT + 1 - len(self.pending)))
            if not block:
                raise ValueError("incomplete protocol line")
            self.pending += block
            if len(self.pending) > LIMIT:
                raise ValueError("protocol line budget exceeded")
        line, self.pending = self.pending.split(b"\n", 1)
        return line


def qmp(endpoint, commands):
    """Call only commands chosen by this supervisor, never wire-supplied names."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
        channel.settimeout(3)
        channel.connect(str(endpoint))
        stream = Lines(channel, time.monotonic() + 3)

        def read():
            return json.loads(stream.read(), object_pairs_hook=unique)

        if "QMP" not in read():
            raise ValueError("QMP greeting missing")
        values = []
        for command in ("qmp_capabilities", *commands):
            nonce = secrets.token_hex(16)
            channel.sendall(encoded({"execute": command, "id": nonce}) + b"\n")
            for _ in range(32):
                response = read()
                if response.get("id") == nonce:
                    if "error" in response or "return" not in response:
                        raise ValueError("QMP command refused")
                    values.append(response["return"])
                    break
            else:
                raise ValueError("QMP event budget exceeded")
        return values[1:]


class QemuWorker:
    def __init__(self, configuration):
        self.configuration = configuration
        self.config = private_json(configuration)
        required = {
            "schema",
            "qemu_binary",
            "ssh_port",
            "maximum_runtime_seconds",
            "workspace_prefix",
            "memory_mib",
            "cpus",
            "accelerator",
            "cpu",
        }
        if (
            set(self.config) != required
            or self.config["schema"] != "daemonarchy/qemu-worker-config@1"
        ):
            raise ValueError("invalid worker configuration")
        for key, minimum, maximum in (
            ("ssh_port", 1024, 65535),
            ("maximum_runtime_seconds", 1, 21600),
            ("memory_mib", 256, 65536),
            ("cpus", 1, 64),
        ):
            if (
                type(self.config[key]) is not int
                or not minimum <= self.config[key] <= maximum
            ):
                raise ValueError("worker resource bound invalid: " + key)
        if self.config["accelerator"] not in ("tcg,thread=multi", "hvf", "kvm"):
            raise ValueError("unsupported accelerator selection")
        if (
            not isinstance(self.config["cpu"], str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.config["cpu"]) is None
        ):
            raise ValueError("invalid CPU selection")
        prefix = self.config["workspace_prefix"]
        if (
            not isinstance(prefix, str)
            or not prefix.startswith("/")
            or prefix == "/"
            or str(PurePosixPath(prefix)) != prefix
            or ".." in PurePosixPath(prefix).parts
            or "\\" in prefix
            or any(ord(c) < 32 for c in prefix)
        ):
            raise ValueError("invalid guest workspace prefix")
        self.root = configuration.parent
        if any(c in str(self.root) for c in ",:\n\r\0"):
            raise ValueError("case path contains QEMU option delimiters")
        if (
            not isinstance(self.config["qemu_binary"], str)
            or not Path(self.config["qemu_binary"]).is_absolute()
        ):
            raise ValueError("absolute QEMU executable selection required")
        self.binary = Path(self.config["qemu_binary"]).resolve(strict=True)
        self.image_tool = self.binary.with_name("qemu-img")
        if not self.binary.is_file() or not os.access(self.binary, os.X_OK):
            raise ValueError("QEMU executable missing")
        self.disk, self.seed = self.root / "guest.qcow2", self.root / "cidata.iso"
        self.nodes = {p: node(p) for p in (self.disk, self.seed)}
        self.image_info = json.loads(
            subprocess.check_output(
                [str(self.image_tool), "info", "--output=json", str(self.disk)],
                timeout=15,
            )
        )
        if (
            self.image_info.get("format") != "qcow2"
            or "backing-filename" in self.image_info
        ):
            raise ValueError("standalone qcow2 image required")
        self.binary_sha256, self.seed_sha256 = digest(self.binary), digest(self.seed)
        self.image_tool_sha256 = digest(self.image_tool)
        self.initial_disk_sha256 = digest(self.disk)
        self.script = Path(__file__).resolve(strict=True)
        self.script_sha256 = digest(self.script)
        self.qmp_endpoint, self.endpoint = (
            self.root / "qmp.sock",
            self.root / "inspection.sock",
        )
        if any(len(os.fsencode(p)) > 100 for p in (self.qmp_endpoint, self.endpoint)):
            raise ValueError("Unix socket path exceeds portable budget")
        for name in (
            "started.json",
            "terminal.json",
            "qemu.log",
            "console.log",
            "qmp.sock",
            "inspection.sock",
            "inspections.jsonl",
        ):
            if (self.root / name).exists() or (self.root / name).is_symlink():
                raise ValueError("preserve existing worker session: " + name)
        self.process = None
        self.interrupted = False
        self.started = None
        self.allocation_identity = None
        self.seen = set()
        self.revoked = False
        self.inspections = 0

    def command(self):
        return [
            str(self.binary),
            "-machine",
            "q35",
            "-accel",
            self.config["accelerator"],
            "-cpu",
            self.config["cpu"],
            "-smp",
            str(self.config["cpus"]),
            "-m",
            str(self.config["memory_mib"]),
            "-boot",
            "c",
            "-drive",
            "file=" + str(self.disk) + ",if=virtio,format=qcow2",
            "-drive",
            "file=" + str(self.seed) + ",media=cdrom,readonly=on",
            "-netdev",
            "user,id=n0,hostfwd=tcp:127.0.0.1:" + str(self.config["ssh_port"]) + "-:22",
            "-device",
            "virtio-net-pci,netdev=n0",
            "-display",
            "none",
            "-monitor",
            "none",
            "-serial",
            "file:" + str(self.root / "console.log"),
            "-qmp",
            "unix:" + str(self.qmp_endpoint) + ",server=on,wait=off",
            "-no-reboot",
        ]

    def require_current(self):
        if (
            self.revoked
            or self.process is None
            or self.process.poll() is not None
            or time.monotonic() - self.started >= self.config["maximum_runtime_seconds"]
        ):
            raise ValueError("allocation ended or expired")
        if (
            private_json(self.configuration) != self.config
            or digest(self.binary) != self.binary_sha256
            or digest(self.script) != self.script_sha256
            or digest(self.seed) != self.seed_sha256
            or any(node(p) != v for p, v in self.nodes.items())
        ):
            raise ValueError("allocation configuration or input identity changed")

    def inspect(self, request):
        if (
            not isinstance(request, dict)
            or set(request)
            != {
                "schema",
                "nonce",
                "worker_identity",
                "plan_identity",
                "policy_identity",
                "minimum_remaining_seconds",
            }
            or request["schema"] != REQUEST
        ):
            raise ValueError("inspection request shape invalid")
        policy = private_json(self.root / "inspection-policy.json")
        if (
            not isinstance(policy, dict)
            or set(policy)
            != {"schema", "worker_identity", "plan_identity", "policy_identity"}
            or policy["schema"] != "daemonarchy/qemu-worker-inspection-policy@1"
        ):
            raise ValueError("reviewed operator policy missing")
        for key in ("worker_identity", "plan_identity", "policy_identity"):
            if (
                not isinstance(policy[key], str)
                or re.fullmatch("sha256:[0-9a-f]{64}", policy[key]) is None
                or request[key] != policy[key]
            ):
                raise ValueError("inspection context not selected by operator")
        nonce = request["nonce"]
        if (
            not isinstance(nonce, str)
            or re.fullmatch("[0-9a-f]{64}", nonce) is None
            or nonce in self.seen
            or len(self.seen) >= 8192
        ):
            raise ValueError("inspection challenge refused")
        minimum = request["minimum_remaining_seconds"]
        if type(minimum) is not int or not 1 <= minimum <= 86400:
            raise ValueError("inspection duration invalid")
        self.seen.add(nonce)
        try:
            self.require_current()
            status, blocks = qmp(self.qmp_endpoint, ("query-status", "query-block"))
            if status.get("running") is not True or status.get("status") != "running":
                raise ValueError("QEMU worker is not running")
            inserted = [v["inserted"] for v in blocks if "inserted" in v]
            devices = {v["file"]: v for v in inserted}
            if (
                len(inserted) != 2
                or set(devices) != {str(self.disk), str(self.seed)}
                or devices[str(self.disk)]["drv"] != "qcow2"
                or devices[str(self.seed)]["ro"] is not True
            ):
                raise ValueError("QEMU devices differ from owned allocation")
            self.require_current()
            remaining = math.floor(
                self.config["maximum_runtime_seconds"]
                - (time.monotonic() - self.started)
            )
            if remaining < minimum:
                raise ValueError("insufficient allocation lifetime")
        except BaseException:
            self.revoked = True
            raise
        response = {
            "schema": RESPONSE,
            "request_identity": identity(request),
            "allocation_identity": self.allocation_identity,
            "workspace_prefix": self.config["workspace_prefix"],
            "remaining_seconds": remaining,
            "disposable": True,
        }
        descriptor = os.open(
            self.root / "inspections.jsonl",
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as log:
            log.write(
                encoded(
                    {
                        "schema": "daemonarchy/owned-qemu-inspection@1",
                        "request_identity": identity(request),
                        "response_identity": identity(response),
                        "allocation_identity": self.allocation_identity,
                        "child_pid": self.process.pid,
                        "qmp_running": True,
                        "attached_images_match": True,
                        "remaining_seconds": remaining,
                    }
                )
                + b"\n"
            )
            log.flush()
            os.fsync(log.fileno())
        self.inspections += 1
        return response

    def run(self):
        self.started = time.monotonic()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.endpoint))
        self.endpoint.chmod(0o600)
        server.listen(2)
        server.settimeout(0.25)
        reason = "child-exit"
        try:
            with (self.root / "qemu.log").open("xb") as log:
                self.process = subprocess.Popen(
                    self.command(),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    env={
                        "PATH": os.defpath,
                        "HOME": str(self.root),
                        "LANG": "C",
                        "LC_ALL": "C",
                    },
                )
                facts = {
                    "schema": "daemonarchy/owned-qemu-worker-session@1",
                    "supervisor_pid": os.getpid(),
                    "pid": self.process.pid,
                    "session_nonce": secrets.token_hex(32),
                    "configuration_identity": identity(self.config),
                    "qemu_sha256": self.binary_sha256,
                    "supervisor_sha256": self.script_sha256,
                    "image_tool_sha256": self.image_tool_sha256,
                    "initial_disk_sha256": self.initial_disk_sha256,
                    "seed_sha256": self.seed_sha256,
                    "maximum_runtime_seconds": self.config["maximum_runtime_seconds"],
                    "physical_worker": False,
                }
                self.allocation_identity = identity(facts)
                publish(
                    self.root / "started.json",
                    {**facts, "allocation_identity": self.allocation_identity},
                )
                while self.process.poll() is None:
                    if self.interrupted:
                        reason = "supervisor-interrupted"
                        break
                    if (
                        time.monotonic() - self.started
                        >= self.config["maximum_runtime_seconds"]
                    ):
                        reason = "declared-runtime-budget-exceeded"
                        break
                    try:
                        connection, _ = server.accept()
                    except socket.timeout:
                        continue
                    with connection:
                        connection.settimeout(3)
                        try:
                            deadline = min(
                                time.monotonic() + 3,
                                self.started + self.config["maximum_runtime_seconds"],
                            )
                            line = Lines(connection, deadline).read()
                            response = self.inspect(
                                json.loads(line, object_pairs_hook=unique)
                            )
                        except (
                            ValueError,
                            KeyError,
                            TypeError,
                            OSError,
                            subprocess.SubprocessError,
                        ):
                            response = {"error": "allocation.inspection-refused"}
                        try:
                            connection.sendall(encoded(response) + b"\n")
                        except OSError:
                            pass
        except BaseException:
            reason = "supervisor-interrupted"
            raise
        finally:
            server.close()
            self.endpoint.unlink(missing_ok=True)
            if self.process is not None and self.process.poll() is None:
                try:
                    qmp(self.qmp_endpoint, ("system_powerdown",))
                except (OSError, ValueError):
                    pass
                try:
                    self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
            publish(
                self.root / "terminal.json",
                {
                    "schema": "daemonarchy/owned-qemu-worker-terminal@1",
                    "reason": reason,
                    "exit_code": self.process.returncode if self.process else None,
                    "seconds": round(time.monotonic() - self.started, 3),
                    "successful_inspections": self.inspections,
                    "inspection_revoked": self.revoked,
                },
            )
        return 130 if self.interrupted else self.process.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "posix":
        raise ValueError("POSIX supervisor host required")

    controller = None

    def interrupted(_signum, _frame):
        if controller is None:
            raise KeyboardInterrupt  # Construction has not launched an owned child.
        controller.interrupted = True
        controller.revoked = True

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, interrupted)
    controller = QemuWorker(args.config)
    return controller.run()


if __name__ == "__main__":
    raise SystemExit(main())
