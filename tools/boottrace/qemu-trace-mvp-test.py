#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
"""QEMU/OVMF checks of the hardware trace image's network hand-over.

Needs an image built with -S (serial) and -K (a TEST public key; never a
real operator key) and the matching private key here.  Scenarios:

  handover   queue one normal experiment; it reaches init, hands over
             (DHCP on QEMU user networking, sshd on 2222), the baked key logs
             in, another key is refused, the host key matches the build's,
             hwtrace-continue ends the hold, the loop stops, and the stick
             carries ADDRESS.TXT and DUMPS/<id>/network.txt
  hang       the first experiment hangs (debug.boottrace.test_hang), the
             second is normal: the trace is filed INCOMPLETE, then hand-over
  bounded    hwtrace.hold=20: with nobody connecting the boot reboots on its
             own and the loop stops (the stick cannot wedge)
  nokey      an image without keys never starts sshd and reboots as before

usage: qemu-trace-mvp-test.py SCENARIO IMAGE --workdir DIR --key PRIVATE_KEY
            [--other-key PRIVATE_KEY] [--hostkey FILE]
Each scenario works on its own copy of IMAGE.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
STICK = HERE / "stick.py"


def qmp(path, command):
    s = socket.socket(socket.AF_UNIX)
    s.connect(path)
    f = s.makefile("rw")
    f.readline()
    for cmd in ({"execute": "qmp_capabilities"}, {"execute": command}):
        f.write(json.dumps(cmd) + "\n")
        f.flush()
        f.readline()
    s.close()


class Vm:
    def __init__(self, image, work, port, accel="kvm", code="/usr/share/OVMF/OVMF_CODE_4M.fd",
                 vars_src="/usr/share/OVMF/OVMF_VARS_4M.fd"):
        self.work, self.port = Path(work), port
        self.log = self.work / "serial.log"
        self.sock = str(self.work / "qmp.sock")
        shutil.copy(vars_src, self.work / "vars.fd")
        for p in (self.log, Path(self.sock)):
            p.unlink(missing_ok=True)
        self.proc = subprocess.Popen([
            "nice", "-n", "15", "qemu-system-x86_64", "-machine", "q35", "-accel", accel,
            "-cpu", "host" if accel == "kvm" else "max", "-smp", "2", "-m", "2048",
            "-drive", f"if=pflash,format=raw,readonly=on,file={code}",
            "-drive", f"if=pflash,format=raw,file={self.work / 'vars.fd'}",
            "-drive", f"if=none,id=stick,format=raw,file={image}",
            "-device", "ide-hd,drive=stick,bus=ide.0",
            "-netdev", f"user,id=n0,hostfwd=tcp:127.0.0.1:{port}-:2222",
            "-device", "e1000,netdev=n0",
            "-display", "none", "-serial", f"file:{self.log}",
            "-qmp", f"unix:{self.sock},server=on,wait=off"])
        self.seen = 0

    def text(self):
        return self.log.read_bytes().decode("latin-1") if self.log.exists() else ""

    def wait(self, needle, timeout, silence=None, from_start=False):
        """Wait for needle in new output; reset a boot silent for `silence` s."""
        end = time.monotonic() + timeout
        last, change = 0, time.monotonic()
        while time.monotonic() < end:
            text = self.text()
            if needle in (text if from_start else text[self.seen:]):
                return True
            if len(text) != last:
                last, change = len(text), time.monotonic()
            elif silence and time.monotonic() - change > silence:
                print(f"  silent {silence}s: resetting the machine", flush=True)
                qmp(self.sock, "system_reset")
                self.seen = len(self.text())
                change = time.monotonic()
            time.sleep(2)
        return False

    def wait_port(self, timeout):
        """Wait until the forwarded sshd answers (the console banner does not
        reach the serial line, so the SSH banner is the signal)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=5) as s:
                    s.settimeout(5)
                    if s.recv(16).startswith(b"SSH-"):
                        return True
            except OSError:
                pass
            time.sleep(3)
        return False

    def stop(self):
        try:
            qmp(self.sock, "quit")
        except OSError:
            self.proc.kill()
        self.proc.wait()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ssh(args, key, cmd, known=None, timeout=60):
    return run(["ssh", "-p", str(args.port), "-i", key, "-o", "BatchMode=yes",
                "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=15",
                "-o", f"UserKnownHostsFile={known or os.devnull}",
                "-o", "StrictHostKeyChecking=" + ("yes" if known else "no"),
                "root@127.0.0.1", cmd], timeout=timeout)


def mdump(image, path):
    # Read a file from the DATRACE partition through stick.py's volume layer.
    sys.path.insert(0, str(HERE))
    import importlib.util
    spec = importlib.util.spec_from_file_location("stick", STICK)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Volume(str(image)).read(path)


def queue(image, text, work):
    q = Path(work) / "queue.txt"
    q.write_text(text)
    r = run([sys.executable, str(STICK), "queue", str(image), str(q)])
    assert r.returncode == 0, r.stderr


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        check.failed = True


check.failed = False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenario", choices=("handover", "hang", "bounded", "nokey"))
    ap.add_argument("image")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--key", help="private key matching the image's baked public key")
    ap.add_argument("--other-key", help="a private key the image does not trust")
    ap.add_argument("--hostkey", help="OUT.img.hostkey from the build (-H)")
    ap.add_argument("--port", type=int, default=22291)
    ap.add_argument("--accel", default="kvm")
    args = ap.parse_args()
    work = Path(args.workdir) / args.scenario
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    image = work / "stick.img"
    shutil.copy(args.image, image)
    normal = "[normal]\nread-conf /boot/d/1\n"
    qs = {"handover": normal,
          "hang": "[hang]\ndebug.boottrace.test_hang=attimer0\n\n[normal]\nread-conf /boot/d/1\n",
          "bounded": "[normal]\nread-conf /boot/d/1\nhwtrace.hold=20\n",
          "nokey": normal}
    queue(image, qs[args.scenario], work)
    vm = Vm(image, work, args.port, accel=args.accel)
    try:
        if args.scenario == "hang":
            check(vm.wait("Hardware trace: booting experiment 0001", 240),
                  "experiment 0001 started")
            check(vm.wait("Hardware trace: booting experiment 0002", 400, silence=90),
                  "after the hang the loop moved to experiment 0002")
        if args.scenario == "nokey":
            check(vm.wait("HARDWARE TRACE: STOPPED", 400),
                  "the boot reached init and the loop stopped, as before")
            check("0001 reached init" in vm.text(), "loader reports experiment 0001 reached init")
            check(not vm.wait_port(10), "no sshd without a key")
            check(ssh(args, args.key or "/dev/null", "true", timeout=20).returncode != 0,
                  "nothing listens on 2222")
        elif args.scenario == "bounded":
            check(vm.wait_port(300), "sshd answers on 2222")
            t0 = time.monotonic()
            check(vm.wait("HARDWARE TRACE: STOPPED", 200), "the hold ended by itself and the loop stopped")
            print(f"  held about {time.monotonic() - t0:.0f} s after the banner", flush=True)
            check(not vm.wait_port(5), "sshd is gone after the reboot")
        else:
            check(vm.wait_port(300), "sshd answers on 2222")
            known = work / "known_hosts"
            scan = run(["ssh-keyscan", "-p", str(args.port), "-t", "ed25519", "127.0.0.1"])
            known.write_text(scan.stdout)
            fp = run(["ssh-keygen", "-lf", str(known)]).stdout.split()
            if args.hostkey:
                want = Path(args.hostkey).read_text().strip()
                check(len(fp) > 1 and fp[1] == want, f"host key {fp[1:2]} is the one built (-H)")
            r = ssh(args, args.key, "echo logged-in; kenv -q hwtrace.hold; ls /var/hwtrace; ifconfig -a | head -3; dmesg | head -2",
                    known=str(known))
            print(r.stdout, r.stderr, flush=True)
            check(r.returncode == 0 and "logged-in" in r.stdout, "baked key logs in as root")
            if args.other_key:
                r = ssh(args, args.other_key, "true", known=str(known))
                check(r.returncode != 0 and "Permission denied" in r.stderr, "another key is refused")
            r = ssh(args, args.key, "pciconf -l | head -3; netstat -rn | head -3; hwtrace-continue", known=str(known))
            check(r.returncode == 0, "probe tools run, hwtrace-continue accepted")
            check(vm.wait("HARDWARE TRACE: STOPPED", 200), "hold ended on request; the loop stopped")
    finally:
        vm.stop()
    # What the stick now carries.
    if args.scenario != "nokey":
        addr = mdump(image, "ADDRESS.TXT")
        check(addr is not None and b"address=" in addr, "ADDRESS.TXT on the stick")
        ids = {"hang": "0002"}.get(args.scenario, "0001")
        net = mdump(image, f"DUMPS/{ids}/network.txt")
        check(net is not None and b"state=listening" in net, f"DUMPS/{ids}/network.txt: listening")
        check(mdump(image, f"DUMPS/{ids}/dmesg.txt") is not None, "diagnostics saved as before")
    if args.scenario == "hang":
        trace = (mdump(image, "TRACES/0001.TXT") or b"").decode("latin-1")
        check("INCOMPLETE" in trace, "the hung boot was filed as an INCOMPLETE trace")
    st = run([sys.executable, str(STICK), "status", str(image)])
    print(st.stdout.strip(), flush=True)
    print("RESULT:", "FAIL" if check.failed else "PASS", args.scenario, flush=True)
    sys.exit(1 if check.failed else 0)


if __name__ == "__main__":
    main()
