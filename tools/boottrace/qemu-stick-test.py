#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
"""Drive a hardware-trace stick through several boots under QEMU/OVMF.

The stick is attached as a USB disk and OVMF keeps its variables in a
persistent vars file.  The harness plays the part of the MSI firmware:
a boot that goes silent (spin with interrupts disabled) is reset after
--silence seconds; a boot that reaches a login prompt is reset after a
short pause (an operator rebooting); a triple fault resets by itself.
It stops when the loader prints the STOPPED banner or after --boots.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--vars", required=True, help="persistent OVMF vars file")
    ap.add_argument("--code", default="/usr/share/OVMF/OVMF_CODE_4M.fd")
    ap.add_argument("--log", required=True)
    ap.add_argument("--boots", type=int, default=8)
    ap.add_argument("--silence", type=float, default=120)
    ap.add_argument("--accel", default="tcg",
                    help="tcg (default; multi-threaded) or kvm")
    ap.add_argument("--cpu", default="max",
                    help="CPU model (x86 TCG on an arm64 host: Westmere)")
    ap.add_argument("--memory", default="2048")
    ap.add_argument("--bus", choices=("usb", "ahci"), default="usb",
                    help="attach the stick as a USB disk (default) or SATA")
    ap.add_argument("--qemu-arg", action="append", default=[],
                    metavar="ARG",
                    help="extra QEMU argument, repeatable (e.g. "
                         "--qemu-arg=-acpitable --qemu-arg=file=t.aml)")
    args = ap.parse_args()
    if not os.path.exists(args.vars):
        sys.exit("create the vars file first (copy OVMF_VARS)")
    sock = args.log + ".qmp"
    for p in (sock, args.log):
        if os.path.exists(p):
            os.unlink(p)
    qemu = subprocess.Popen([
        "qemu-system-x86_64", "-machine", "q35,smm=on",
        "-accel", args.accel + (",thread=multi" if args.accel == "tcg" else ""),
        "-cpu", args.cpu, "-smp", "2", "-m", args.memory,
        "-drive", f"if=pflash,format=raw,readonly=on,file={args.code}",
        "-drive", f"if=pflash,format=raw,file={args.vars}",
        "-drive", f"if=none,id=stick,format=raw,file={args.image}",
        *(["-device", "qemu-xhci,id=xhci",
           "-device", "usb-storage,bus=xhci.0,drive=stick,removable=on"]
          if args.bus == "usb" else ["-device", "ide-hd,drive=stick,bus=ide.0"]),
        "-display", "none", "-serial", f"file:{args.log}",
        "-qmp", f"unix:{sock},server=on,wait=off", "-net", "none",
        *args.qemu_arg])
    boots, last_size, last_change = 1, 0, time.monotonic()
    seen = 0
    try:
        while qemu.poll() is None:
            time.sleep(2)
            text = Path(args.log).read_bytes().decode("latin-1") if os.path.exists(args.log) else ""
            new = text[seen:]
            if len(text) != last_size:
                last_size, last_change = len(text), time.monotonic()
            if "HARDWARE TRACE: STOPPED" in new:
                time.sleep(5)
                print(f"loader stopped after {boots} boots", flush=True)
                break
            # Count firmware restarts (a triple fault resets by itself).
            reset_reason = None
            if "login:" in new:
                reset_reason = "reached login"
            elif time.monotonic() - last_change > args.silence:
                reset_reason = f"silent for {args.silence:.0f} s"
            if "Hardware trace: running the next" in new and \
                    text.count("Hardware trace: running the next") > boots:
                boots = text.count("Hardware trace: running the next")
                print(f"boot {boots} started", flush=True)
            if reset_reason:
                print(f"resetting: {reset_reason}", flush=True)
                seen = len(text)
                if boots >= args.boots:
                    break
                qmp(sock, "system_reset")
                last_change = time.monotonic()
                continue
    finally:
        try:
            qmp(sock, "quit")
        except OSError:
            qemu.kill()
        qemu.wait()


if __name__ == "__main__":
    main()
