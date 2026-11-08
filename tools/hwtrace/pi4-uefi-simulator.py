#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Boot a fresh Pi 4 UEFI/PCIe/USB diagnostic control using regular files only.

Requires uConsole's connected BCM2711 PCIe/xHCI profile. This bypasses the
VideoCore/EEPROM chain and does not qualify physical Pi 4 or BCM2712/RP1.
Kernel completion requires fresh offline diagnostics, not UART text or exit 0.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time
import uuid


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


TOOLS = Path(__file__).resolve().parent
sim = module("pi4_fdt_control", TOOLS / "pi4-simulator.py")
stick = module("pi4_usb_stick", TOOLS.parent / "boottrace/stick.py")
acpi = module("pi4_usb_acpi", TOOLS / "acpi-summary.py")
PROBES = ("dmesg", "kenv", "sysctl", "kldstat", "pciconf", "devinfo", "usbconfig")


class QMP:
    """Bounded QMP over child pipes; no socket-creation polling or fixed waits."""
    def __init__(self, process):
        self.process = process
        self.events = []
        self.buffer = b""
        self.selector = selectors.DefaultSelector()
        self.selector.register(process.stdout, selectors.EVENT_READ)
        greeting = self.read(time.monotonic() + 10)
        if "QMP" not in greeting:
            raise RuntimeError(f"invalid QMP greeting: {greeting}")
        self.command("qmp_capabilities")

    def close(self):
        self.selector.close()

    def read(self, deadline):
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise TimeoutError("QMP observation deadline expired")
            block = os.read(self.process.stdout.fileno(), 65536)
            if not block:
                raise RuntimeError("QEMU closed QMP before completing observation")
            self.buffer += block
            if len(self.buffer) > 1024 * 1024:
                raise RuntimeError("QMP response exceeds observation bound")
        line, self.buffer = self.buffer.split(b"\n", 1)
        return json.loads(line)

    def command(self, name, arguments=None):
        request = {"execute": name}
        if arguments is not None:
            request["arguments"] = arguments
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + 10
        while True:
            reply = self.read(deadline)
            if "event" in reply:
                self.events.append(reply)
            elif "error" in reply:
                raise RuntimeError(f"QMP {name}: {reply['error']}")
            elif "return" in reply:
                return reply["return"]

    def wait_for_stop(self, timeout):
        deadline = time.monotonic() + timeout
        state = self.command("query-status")
        while state["status"] not in ("shutdown", "paused", "guest-panicked"):
            event = self.read(deadline)
            if "event" not in event:
                continue
            self.events.append(event)
            if event["event"] in ("SHUTDOWN", "STOP", "GUEST_PANICKED"):
                state = self.command("query-status")
        return state


def values(text):
    return dict(line.split(": ", 1) for line in text.splitlines() if ": " in line)


def assess(serial, dumps, snapshot, label):
    dmesg = (dumps / "dmesg.txt").read_text(errors="replace")
    kenv = (dumps / "kenv.txt").read_text(errors="replace")
    capture = (dumps / "capture.log").read_text(errors="replace")
    scalars = values((dumps / "sysctl.txt").read_text(errors="replace"))
    return {
        "efi_loader": "FreeBSD/arm64 EFI loader" in serial,
        "loader_acpi_readback": "loader ACPI capture saved and read back" in serial,
        "acpi_four_enabled_cpus": snapshot.get("topology", {}).get("enabled") == 4,
        "kernel_acpi": "acpi0:" in dmesg,
        "native_xhci": "xhci0:" in dmesg,
        "native_usb_storage": "umass0:" in dmesg and "da0:" in dmesg,
        "ufs_root": "Trying to mount root from ufs:/dev/gpt/HWTROOT [ro]" in dmesg,
        "four_active_cpus": scalars.get("kern.smp.cpus") == "4" and
                            scalars.get("kern.smp.active") == "1",
        "page_size": scalars.get("hw.pagesize") == "4096",
        "acpi_profile": 'boottrace_capture_acpi="YES"' in kenv,
        "fresh_run_label": f'boottrace_label="{label}"' in kenv,
        "queue_experiment": 'boottrace_q_id="0001"' in kenv,
        "all_probes_complete": all(f"finish {name}.txt status=0" in capture for name in PROBES),
        "done_marker": bool((dumps / "done.txt").read_bytes().strip()),
        "no_ownership_warning": "_secure_path:" not in dmesg,
        "storage_io_clean": not any(marker in dmesg for marker in (
            "g_vfs_done():", "CAM status: CCB request completed with an error",
            "Retries exhausted", "I/O error")),
    }


def run(args):
    image = sim.checked(args.image, args.image_sha256)
    firmware = sim.checked(args.firmware, args.firmware_sha256)
    qemu = sim.checked(args.qemu, args.qemu_sha256)
    qimg = sim.regular(args.qemu_img)
    if stick.Volume(str(image)).listdir("DUMPS"):
        raise ValueError("source DUMPS must be empty; refuse stale diagnostic evidence")
    args.output.mkdir(mode=0o700)
    output = args.output.resolve()
    result = output / "result.json"
    manifest = dict(schema="daemonarchy/pi4-uefi-usb-simulator@1", profile="uefi-usb",
                    inputs={str(p): sim.digest(p) for p in (image, firmware, qemu, qimg)},
                    limitations=["VideoCore/EEPROM bypassed", "partial BCM2711 model",
                                 "not Pi 5/RP1 or physical/full-RAM qualification"], ok=False)

    def save():
        result.write_text(json.dumps(manifest, indent=2) + "\n")

    save()
    process, qmp = None, None
    try:
        control = output / "control.img"
        shutil.copyfile(image, control)
        label = "uefi-usb-" + uuid.uuid4().hex[:16]
        queue = output / "queue.txt"
        queue.write_text('[pi4-uefi-usb]\nhw.ncpu=4\nboottrace_label="' + label + '"\n')
        subprocess.run([sys.executable, str(TOOLS.parent / "boottrace/stick.py"), "queue",
                        str(control), str(queue), "--reset-traces"], check=True)
        manifest.update(label=label, epoch=stick.read_state(stick.Volume(str(control)))["epoch"])
        overlay = output / "disk.qcow2"
        subprocess.run([str(qimg), "create", "-f", "qcow2", "-F", "raw", "-b", str(control),
                        str(overlay)], check=True)
        # A USB disk keeps the exact source geometry; unlike SD it needs no
        # power-of-two capacity rounding. qemu-xhci is a real PCI endpoint.
        command = [str(qemu), "-machine", "raspi4b", "-accel", "tcg",
                   "-global", "arm_gic.has-security-extensions=on",
                   "-global", "bcm2838-pcie-disconnected.connected-xhci=on",
                   "-blockdev", json.dumps({"driver": "qcow2", "node-name": "stick",
                       "file": {"driver": "file", "filename": str(overlay)}}),
                   "-device", "usb-storage,bus=bcm-xhci.0,drive=stick",
                   "-device", f"loader,file={firmware},addr=0,cpu-num=0,force-raw=on",
                   "-display", "none", "-serial", f"file:{output / 'uart0.log'}",
                   "-serial", f"file:{output / 'uart1.log'}", "-monitor", "none",
                   "-qmp", "stdio", "-nic", "none", "-no-reboot", "-no-shutdown",
                   "-d", "guest_errors,unimp", "-D", str(output / "guest-errors.log")]
        for cpu in range(1, 4):
            command.extend(["-device", f"loader,addr=0x1000,cpu-num={cpu}"])
        if args.debug_control:
            # The relative name keeps the bind address short even when the
            # private output directory has a long absolute path.
            command.extend(["-qmp", "unix:qmp.sock,server=on,wait=off"])
            manifest["control_socket"] = str(output / "qmp.sock")
        manifest["command"] = command
        save()
        with (output / "qemu.log").open("wb") as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=log, bufsize=0, cwd=output)
            manifest["pid"] = process.pid
            save()
            qmp = QMP(process)
            manifest["stop_state"] = qmp.wait_for_stop(args.timeout)
            qmp.command("screendump", {"filename": str(output / "screen.ppm")})
            manifest["events"] = list(qmp.events)
            qmp.command("quit")
            manifest["exit_code"] = process.wait(timeout=10)
        readback = output / "readback.img"
        subprocess.run([str(qimg), "convert", "-f", "qcow2", "-O", "raw", str(overlay),
                        str(readback)], check=True)
        volume = stick.Volume(str(readback))
        snapshot = acpi.summary(volume)
        (output / "acpi-summary.json").write_text(json.dumps(snapshot, indent=2) + "\n")
        if snapshot["epoch"] != manifest["epoch"]:
            raise ValueError("ACPI snapshot belongs to another queue generation")
        dumps = output / "dumps"
        dumps.mkdir()
        subprocess.run(["mcopy", "-s", "-i", volume.spec, "::/DUMPS/0001", str(dumps)], check=True)
        serial = "\n".join(sim.ANSI.sub(b"", (output / f"uart{n}.log").read_bytes()).decode(
                          errors="replace") for n in (0, 1))
        (output / "serial-clean.txt").write_text(serial)
        checks = assess(serial, dumps / "0001", snapshot, label)
        checks["guest_reset_observed"] = any(e.get("event") == "SHUTDOWN" and
            e.get("data", {}).get("reason") == "guest-reset" for e in manifest["events"])
        checks["natural_observed_stop"] = manifest["stop_state"]["status"] == "shutdown"
        checks["qemu_clean_exit"] = manifest["exit_code"] == 0
        manifest["checks"] = checks
        manifest["diagnostics"] = {str(p.relative_to(dumps)): sim.digest(p)
                                   for p in sorted(dumps.rglob("*")) if p.is_file()}
        manifest["ok"] = all(checks.values())
        if not manifest["ok"]:
            raise RuntimeError(f"USB bootstrap checks incomplete: {checks}")
    except BaseException as error:
        manifest["error"] = str(error)
        raise
    finally:
        if process is not None and process.poll() is None:
            if qmp is not None:
                try:
                    qmp.command("screendump", {"filename": str(output / "partial-screen.ppm")})
                    qmp.command("quit")
                except (OSError, ValueError, RuntimeError, TimeoutError):
                    process.terminate()
            else:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        if qmp is not None:
            manifest.setdefault("events", list(qmp.events))
            qmp.close()
        manifest["source_unchanged"] = sim.digest(image) == args.image_sha256.lower()
        manifest["ok"] = manifest["ok"] and manifest["source_unchanged"]
        save()
    if not manifest["ok"]:
        raise RuntimeError("bootstrap evidence or original-image integrity check failed")
    print(f"PASS: Pi 4 UEFI/PCIe/USB kernel/init/ACPI/offline diagnostics: {result}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "firmware", "qemu"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--qemu-img", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--debug-control", action="store_true",
                        help="add a private QMP socket for live inspection")
    args = parser.parse_args()
    if not 10 <= args.timeout <= 3600:
        parser.error("timeout must be between 10 and 3600 seconds")
    try:
        run(args)
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
