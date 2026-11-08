#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Run a separately selected Pi 4 U-Boot/FDT hwtrace control on regular images.

The source must be built with boottrace_capture_acpi="NO" in loader.conf. This
profile bypasses VideoCore/EEPROM and does not qualify Pi 5, PCIe or networking.
No physical device or original input is written. A fresh writable image and
qcow2 overlay retain the private run, diagnostics and readback evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys

ANSI = re.compile(rb"\x1b\[[0-?]*[ -/]*[@-~]")
MACHINES = {"raspi4b": 2 << 30, "raspi4b-4g": 4 << 30, "raspi4b-8g": 8 << 30}
CHECKS = {
    "uboot": "U-Boot ",
    "freebsd_loader": "FreeBSD/arm64 EFI loader",
    "four_cpus": "FreeBSD/SMP: Multiprocessor System Detected: 4 CPUs",
    "native_sd": "mmcsd0:",
    "sd_root": "Trying to mount root from ufs:/dev/gpt/HWTROOT [ro]",
    "init": "Daemonarchy hardware trace: init reached; saving diagnostics",
    "capture_saved": "Saved to DATRACE DUMPS/0001",
    "synced": "All buffers synced.",
    "reset": "Resetting system",
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def regular(path):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"input must be a regular file: {path}")
    return path.resolve()


def checked(path, expected):
    path = regular(path)
    if digest(path) != expected.lower():
        raise ValueError(f"SHA-256 mismatch: {path}")
    return path


def data_offset(image):
    with image.open("rb") as stream:
        stream.seek(512)
        header = stream.read(92)
        if header[:8] != b"EFI PART":
            raise ValueError("image must contain GPT")
        lba, count, size = struct.unpack_from("<QII", header, 72)
        if not 1 <= count <= 4096 or not 128 <= size <= 4096:
            raise ValueError("invalid GPT entry bounds")
        stream.seek(lba * 512)
        for _ in range(count):
            entry = stream.read(size)
            if len(entry) != size:
                raise ValueError("truncated GPT entries")
            if entry[56:128].decode("utf-16-le").rstrip("\0") == "DATRACE":
                start, end = struct.unpack_from("<QQ", entry, 32)
                if start <= end and (end + 1) * 512 <= image.stat().st_size:
                    return start * 512
    raise ValueError("bounded DATRACE partition not found")


def memory_options(parser):
    parser.add_argument("--machine", choices=MACHINES, default="raspi4b",
                        help="explicit BCM2711 model; the default remains 2 GiB")
    parser.add_argument("--memory-min-bytes", type=int,
                        help="minimum required guest hw.physmem, not a firmware setting")
    parser.add_argument("--memory-max-bytes", type=int,
                        help="maximum permitted guest hw.physmem, not a firmware setting")


def validate_memory_options(args):
    low, high = args.memory_min_bytes, args.memory_max_bytes
    if any(value is not None and value < 0 for value in (low, high)):
        raise ValueError("guest memory bounds must be nonnegative byte counts")
    if low is not None and high is not None and low > high:
        raise ValueError("guest memory minimum exceeds its maximum")
    if low is not None and low > MACHINES[args.machine]:
        raise ValueError("guest memory minimum exceeds configured model RAM")


def physical_memory(text):
    matches = re.findall(r"^hw\.physmem:[ \t]*([0-9]+)[ \t]*$", text, re.MULTILINE)
    return int(matches[0]) if len(matches) == 1 else None


def memory_checks(text, low=None, high=None):
    if low is None and high is None:
        return {}
    actual = physical_memory(text)
    return {"guest_physical_memory_bounds": actual is not None and
            (low is None or actual >= low) and (high is None or actual <= high)}


def assess(serial, dumps, memory_min=None, memory_max=None, boot_checks=None):
    checks = {key: value in serial for key, value in
              (CHECKS if boot_checks is None else boot_checks).items()}
    dmesg = (dumps / "dmesg.txt").read_text(errors="replace")
    checks["storage_io_clean"] = not any(marker in serial or marker in dmesg
        for marker in ("g_vfs_done():", "CAM status: CCB request completed with an error",
                       "Retries exhausted", "I/O error", "Error indicated:",
                       "Controller timeout"))
    checks["no_ownership_warning"] = "_secure_path:" not in serial
    checks["fdt_profile"] = 'boottrace_capture_acpi="NO"' in (
        dumps / "kenv.txt").read_text(errors="replace")
    capture = (dumps / "capture.log").read_text(errors="replace")
    probes = ("dmesg", "kenv", "sysctl", "kldstat", "pciconf", "devinfo", "usbconfig")
    checks["completed_probes"] = all(f"finish {name}.txt status=0" in capture for name in probes)
    checks["done_marker"] = bool((dumps / "done.txt").read_bytes().strip())
    sysctl = (dumps / "sysctl.txt").read_text(errors="replace")
    checks["smp_active"] = "kern.smp.active: 1" in sysctl and "kern.smp.cpus: 4" in sysctl
    checks["page_size"] = "hw.pagesize: 4096" in sysctl
    checks.update(memory_checks(sysctl, memory_min, memory_max))
    return checks


def run(args, control_hook=None):
    validate_memory_options(args)
    image = checked(args.image, args.image_sha256)
    uboot = checked(args.uboot, args.uboot_sha256)
    dtb = checked(args.dtb, args.dtb_sha256)
    qemu, qimg = regular(args.qemu), regular(args.qemu_img)
    compatible = subprocess.check_output(["fdtget", "-t", "s", str(dtb), "/", "compatible"], text=True)
    if "brcm,bcm2711" not in compatible:
        raise ValueError("input FDT must describe BCM2711")
    # Existing files/directories/symlinks are refused before any mutation.
    args.output.mkdir(mode=0o700)
    output = args.output.resolve()
    control = output / "control.img"
    shutil.copyfile(image, control)
    queue = output / "queue.txt"
    queue.write_text("[pi4-simulator-uboot-fdt]\nhw.ncpu=4\n")
    if control_hook is not None:
        control_hook.prepare(control, queue, output)
    stick = Path(__file__).resolve().parents[1] / "boottrace/stick.py"
    subprocess.run([sys.executable, str(stick), "queue", str(control), str(queue)], check=True)
    if control_hook is not None:
        control_hook.validate_image(control)
    profile_dtb = output / "pi4-uboot.dtb"
    shutil.copyfile(dtb, profile_dtb)
    # The existing Linux fixture uses pl011-axi. Both U-Boot and FreeBSD bind
    # the actual modeled PL011 through the older, compatible standard binding.
    for node, prop, values in (
        ("/chosen", "stdout-path", ["/soc/serial@7e201000:115200n8"]),
        ("/aliases", "serial0", ["/soc/serial@7e201000"]),
        ("/aliases", "serial1", ["/soc/serial@7e215040"]),
        ("/soc/serial@7e201000", "compatible", ["arm,pl011", "arm,primecell"]),
        ("/soc/serial@7e201000", "status", ["okay"]),
    ):
        subprocess.run(["fdtput", "-t", "s", str(profile_dtb), node, prop, *values], check=True)
    if control_hook is not None:
        control_hook.configure_dtb(profile_dtb)
    overlay = output / "disk.qcow2"
    virtual_size = (control.stat().st_size if getattr(control_hook, "exact_disk_size", False)
                    else 1 << max(29, (control.stat().st_size - 1).bit_length()))
    subprocess.run([str(qimg), "create", "-f", "qcow2", "-F", "raw", "-b", str(control),
                    str(overlay), str(virtual_size)], check=True)
    command = [str(qemu), "-machine", args.machine, "-accel", "tcg", "-kernel", str(uboot),
               "-dtb", str(profile_dtb), "-drive", f"if=sd,format=qcow2,file={overlay}",
               "-display", "none", "-serial", f"file:{output / 'serial.log'}",
               "-serial", f"file:{output / 'uart1.log'}", "-monitor", "none", "-nic", "none",
               "-no-reboot", "-d", "guest_errors,unimp", "-D", str(output / "guest-errors.log")]
    if control_hook is not None:
        command = control_hook.configure_command(command)
    manifest = dict(schema="daemonarchy/pi4-simulator@1",
                    profile=getattr(control_hook, "profile", "uboot-fdt"), command=command,
                    machine=args.machine, model_ram_bytes=MACHINES[args.machine],
                    guest_memory_bounds=dict(min_bytes=args.memory_min_bytes,
                                             max_bytes=args.memory_max_bytes),
                    harness_sha256=digest(Path(__file__).resolve()),
                    inputs={str(p): digest(p) for p in (image, uboot, dtb, qemu, qimg)},
                    profile_dtb_sha256=digest(profile_dtb), virtual_size=virtual_size,
                    limitations=["VideoCore/EEPROM bypassed", "partial BCM2711 model",
                                 "not Pi 5/RP1", "no physical PCIe/network/full-RAM acceptance"])
    if control_hook is not None:
        manifest["network_profile"] = control_hook.identity()
    result = output / "result.json"
    result.write_text(json.dumps(manifest, indent=2) + "\n")
    with (output / "qemu.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            manifest["exit_code"] = (control_hook.wait(process, args.timeout)
                if control_hook is not None else process.wait(timeout=args.timeout))
        except subprocess.TimeoutExpired:
            manifest["error"] = "QEMU deadline expired; retained partial evidence"
            raise RuntimeError(manifest["error"])
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            serial = ANSI.sub(b"", (output / "serial.log").read_bytes()).decode(errors="replace")
            (output / "serial-clean.txt").write_text(serial)
            result.write_text(json.dumps(manifest, indent=2) + "\n")
    readback = output / "readback.img"
    subprocess.run([str(qimg), "convert", "-f", "qcow2", "-O", "raw", str(overlay), str(readback)], check=True)
    spec = f"{readback}@@{data_offset(readback)}"
    dumps = output / "dumps"
    dumps.mkdir()
    subprocess.run(["mcopy", "-s", "-i", spec, "::/DUMPS/0001", str(dumps)], check=True)
    manifest["checks"] = assess(serial, dumps / "0001", args.memory_min_bytes,
                                args.memory_max_bytes, getattr(control_hook, "boot_checks", None))
    if control_hook is not None:
        manifest["checks"].update(control_hook.assess(dumps / "0001"))
        manifest["network_result"] = control_hook.report
    manifest["guest_physical_memory_bytes"] = physical_memory(
        (dumps / "0001/sysctl.txt").read_text(errors="replace"))
    manifest["source_unchanged"] = digest(image) == args.image_sha256.lower()
    manifest["diagnostics"] = {str(p.relative_to(dumps)): digest(p) for p in sorted(dumps.rglob("*")) if p.is_file()}
    manifest["ok"] = (manifest["exit_code"] == 0 and manifest["source_unchanged"] and
                      all(manifest["checks"].values()))
    result.write_text(json.dumps(manifest, indent=2) + "\n")
    if not manifest["ok"]:
        raise RuntimeError(f"bootstrap checks incomplete: {manifest['checks']}")
    description = getattr(control_hook, "success_description",
                          "four-CPU SD boot, init, durable collection and clean reset")
    print(f"PASS: Pi 4 U-Boot/FDT {description}: {result}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    memory_options(parser)
    for name in ("image", "uboot", "dtb"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--qemu-img", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if not 10 <= args.timeout <= 3600:
        parser.error("timeout must be between 10 and 3600 seconds")
    try:
        run(args)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
