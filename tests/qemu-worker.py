"""Controller tests with a fake QMP process, not actual VM qualification."""

import importlib.util
import ctypes
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qemu_worker", ROOT / "native/qemu-worker.py"
)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)
CLIENT_SPEC = importlib.util.spec_from_file_location(
    "worker_client", ROOT / "native/inspect-worker-allocation.py"
)
client = importlib.util.module_from_spec(CLIENT_SPEC)
CLIENT_SPEC.loader.exec_module(client)

FAKE_QEMU = """#!/usr/bin/env python3
import json,os,pathlib,socket,sys
args=sys.argv
root=pathlib.Path(args[args.index('-qmp')+1].split(':',1)[1].split(',')[0]).parent
endpoint=root/'qmp.sock'
server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(str(endpoint));server.listen(2)
while True:
 channel,_=server.accept()
 with channel:
  channel.sendall(b'{"QMP":{}}\\n')
  with channel.makefile('rwb',buffering=0) as stream:
   while True:
    line=stream.readline()
    if not line:break
    request=json.loads(line);name=request['execute']
    if name=='system_powerdown':
     (root/'powerdown-seen').write_text('requested')
     if not (root/'hold-powerdown').exists():sys.exit(0)
    if name=='query-status':value={'running':True,'status':'running'}
    elif name=='query-block':
     value=[{'inserted':{'file':str(root/'guest.qcow2'),'drv':'qcow2','ro':False}},
            {'inserted':{'file':str(root/'cidata.iso'),'drv':'raw','ro':True}}]
     if (root/'foreign-disk').exists():value[0]['inserted']['file']='foreign'
    else:value={}
    stream.write((json.dumps({'id':request['id'],'return':value})+'\\n').encode())
"""


class QemuWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dqw-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)
        self.binary = self.root / "qemu-system-x86_64"
        self.binary.write_text(FAKE_QEMU)
        self.binary.chmod(0o700)
        image_tool = self.root / "qemu-img"
        image_tool.write_text('#!/usr/bin/env python3\nprint(\'{"format":"qcow2"}\')\n')
        image_tool.chmod(0o700)
        for name in ("guest.qcow2", "cidata.iso"):
            (self.root / name).write_bytes(b"fake fixture input")
        self.config = self.root / "worker.json"
        worker.publish(
            self.config,
            {
                "schema": "daemonarchy/qemu-worker-config@1",
                "qemu_binary": str(self.binary),
                "ssh_port": 22230,
                "maximum_runtime_seconds": 10,
                "workspace_prefix": "/var/tmp/retained-native",
                "memory_mib": 256,
                "cpus": 1,
                "accelerator": "tcg,thread=multi",
                "cpu": "Westmere",
            },
        )
        self.policy = {
            "schema": "daemonarchy/qemu-worker-inspection-policy@1",
            "worker_identity": "sha256:" + "1" * 64,
            "plan_identity": "sha256:" + "2" * 64,
            "policy_identity": "sha256:" + "3" * 64,
        }
        worker.publish(self.root / "inspection-policy.json", self.policy)
        self.process = None

    def start(self):
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "native/qemu-worker.py"),
                "--config",
                str(self.config),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail(self.process.communicate()[1].decode())
            if (self.root / "qmp.sock").exists():
                return
            time.sleep(0.01)
        self.fail("fake QMP worker did not start")

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.communicate(timeout=45)

    def request(self, **changes):
        return {
            "schema": worker.REQUEST,
            "nonce": secrets.token_hex(32),
            **{k: v for k, v in self.policy.items() if k != "schema"},
            "minimum_remaining_seconds": 1,
            **changes,
        }

    def exchange(self, request):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
            channel.settimeout(5)
            channel.connect(str(self.root / "inspection.sock"))
            channel.sendall(worker.encoded(request) + b"\n")
            return json.loads(worker.Lines(channel, time.monotonic() + 5).read())

    def test_fresh_inspections_bind_same_owned_child_and_replay_refuses(self):
        self.start()
        request = self.request()
        first = self.exchange(request)
        second = self.exchange(self.request())
        self.assertEqual(first["request_identity"], worker.identity(request))
        self.assertEqual(first["allocation_identity"], second["allocation_identity"])
        self.assertEqual(first["workspace_prefix"], "/var/tmp/retained-native")
        self.assertEqual(
            self.exchange(request), {"error": "allocation.inspection-refused"}
        )
        self.assertIn("allocation_identity", self.exchange(self.request()))
        self.stop()
        terminal = json.loads((self.root / "terminal.json").read_text())
        self.assertEqual(terminal["successful_inspections"], 3)
        self.assertFalse((self.root / "inspection.sock").exists())

    def test_unselected_context_and_control_fields_cannot_inspect_or_control(self):
        self.start()
        for request in (
            self.request(plan_identity="sha256:" + "0" * 64),
            self.request(execute="quit"),
            self.request(minimum_remaining_seconds=True),
        ):
            self.assertEqual(
                self.exchange(request), {"error": "allocation.inspection-refused"}
            )
        self.assertIsNone(self.process.poll())
        self.assertIn("allocation_identity", self.exchange(self.request()))

    def test_qmp_device_drift_permanently_revokes_inspection(self):
        self.start()
        self.assertIn("allocation_identity", self.exchange(self.request()))
        (self.root / "foreign-disk").touch()
        self.assertEqual(
            self.exchange(self.request()), {"error": "allocation.inspection-refused"}
        )
        (self.root / "foreign-disk").unlink()
        self.assertEqual(
            self.exchange(self.request()), {"error": "allocation.inspection-refused"}
        )

    def test_failed_child_propagates_status_and_no_inspection_can_succeed(self):
        self.binary.write_text("#!/usr/bin/env python3\nraise SystemExit(7)\n")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "native/qemu-worker.py"),
                "--config",
                str(self.config),
            ],
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 7)
        self.assertEqual(
            json.loads((self.root / "terminal.json").read_text())["exit_code"], 7
        )
        self.assertFalse((self.root / "inspection.sock").exists())

    def test_runtime_budget_stops_owned_process_and_preserves_terminal(self):
        value = worker.private_json(self.config)
        value["maximum_runtime_seconds"] = 1
        self.config.write_bytes(worker.encoded(value))
        self.start()
        self.process.communicate(timeout=5)
        terminal = json.loads((self.root / "terminal.json").read_text())
        self.assertEqual(terminal["reason"], "declared-runtime-budget-exceeded")
        self.assertEqual(terminal["exit_code"], 0)

    def test_insufficient_lifetime_permanently_revokes_inspection(self):
        self.start()
        self.assertIn("allocation_identity", self.exchange(self.request()))
        self.assertEqual(
            self.exchange(self.request(minimum_remaining_seconds=86400)),
            {"error": "allocation.inspection-refused"},
        )
        self.assertEqual(
            self.exchange(self.request()), {"error": "allocation.inspection-refused"}
        )

    def test_configuration_drift_refuses_even_after_original_bytes_return(self):
        self.start()
        self.assertIn("allocation_identity", self.exchange(self.request()))
        original = self.config.read_bytes()
        value = json.loads(original)
        value["memory_mib"] = 512
        self.config.write_bytes(worker.encoded(value))
        self.assertEqual(
            self.exchange(self.request()), {"error": "allocation.inspection-refused"}
        )
        self.config.write_bytes(original)
        self.assertEqual(
            self.exchange(self.request()), {"error": "allocation.inspection-refused"}
        )

    def test_repeated_termination_during_cleanup_reaps_owned_child(self):
        import signal

        (self.root / "hold-powerdown").touch()
        self.start()
        child_pid = json.loads((self.root / "started.json").read_text())["pid"]
        try:
            self.process.terminate()
            deadline = time.monotonic() + 5
            while not (self.root / "powerdown-seen").exists():
                if self.process.poll() is not None or time.monotonic() >= deadline:
                    self.fail("supervisor did not reach owned cleanup")
                time.sleep(0.01)
            for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                os.kill(self.process.pid, signum)
            with self.assertRaises(subprocess.TimeoutExpired):
                self.process.wait(timeout=0.3)
            os.kill(child_pid, signal.SIGTERM)
            self.assertNotEqual(self.process.wait(timeout=5), 0)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
            terminal = json.loads((self.root / "terminal.json").read_text())
            self.assertEqual(terminal["reason"], "supervisor-interrupted")
            self.assertFalse((self.root / "inspection.sock").exists())
        finally:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def test_private_configuration_and_old_session_are_required(self):
        self.config.chmod(0o644)
        with self.assertRaises(ValueError):
            worker.QemuWorker(self.config)
        self.config.chmod(0o600)
        (self.root / "started.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "preserve existing"):
            worker.QemuWorker(self.config)

    def test_total_socket_deadline_cannot_be_extended_by_dripping_bytes(self):
        reader, writer = socket.socketpair()
        self.addCleanup(reader.close)
        self.addCleanup(writer.close)
        stop = threading.Event()

        def drip():
            while not stop.wait(0.01):
                try:
                    writer.sendall(b" ")
                except OSError:
                    return

        thread = threading.Thread(target=drip)
        thread.start()
        try:
            with self.assertRaises(TimeoutError):
                worker.Lines(reader, time.monotonic() + 0.08).read()
        finally:
            stop.set()
            thread.join(timeout=1)

    @unittest.skipUnless(
        hasattr(ctypes.CDLL(None), "getpeereid"), "requires POSIX getpeereid"
    )
    def test_relay_checks_actual_peer_and_preserves_protocol_binding(self):
        self.start()
        request = self.request()
        response = json.loads(
            client.exchange(
                self.root / "inspection.sock",
                worker.encoded(request),
                expected_uid=os.geteuid(),
            )
        )
        self.assertEqual(response["request_identity"], worker.identity(request))
        self.assertEqual(response["schema"], worker.RESPONSE)

    def test_relay_refuses_public_socket_before_connecting(self):
        self.start()
        endpoint = self.root / "inspection.sock"
        endpoint.chmod(0o666)
        with self.assertRaisesRegex(ValueError, "private operator socket"):
            client.exchange(
                endpoint, worker.encoded(self.request()), expected_uid=os.geteuid()
            )

    def test_relay_cli_refuses_wrong_platform_or_nonroot_before_path_access(self):
        if sys.platform.startswith("freebsd") and os.geteuid() == 0:
            self.skipTest("requires an ineligible platform or identity")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "native/inspect-worker-allocation.py"),
                "--socket",
                "/does/not/exist",
            ],
            capture_output=True,
            timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"FreeBSD root inspection client required", result.stderr)


if __name__ == "__main__":
    unittest.main()
