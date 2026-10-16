#!/usr/bin/env python3
"""Check actual firmware/loader rejection evidence from disposable ISO guests."""
import argparse
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("firmware-rejection", "kernel-rejection"))
parser.add_argument("log", type=Path)
args = parser.parse_args()
log = args.log.read_text(errors="replace").replace("\r", "").replace("\b", "")
if args.mode == "firmware-rejection":
    required = [r"Access Denied -- rejected probably by Secure Boot"]
    forbidden = [r"FreeBSD/amd64 EFI loader", r"@@phase"]
else:
    required = [r"SecureBoot: 1, SetupMode: 0",
                r"Verified /boot/[^\n]*manifest signed by",
                r"Unverified /boot/kernel\.secure/kernel: ([0-9a-f]{64}) != ([0-9a-f]{64})",
                r"Failed to load kernel 'kernel\.secure'"]
    forbidden = [r"@@phase", r"Mounting root from", r"^FreeBSD 16\.0-CURRENT"]
errors = [f"missing: {pattern}" for pattern in required if not re.search(pattern, log, re.M)]
errors += [f"unexpected: {pattern}" for pattern in forbidden if re.search(pattern, log, re.M)]
if args.mode == "kernel-rejection":
    hashes = re.search(required[2], log)
    if hashes and hashes[1] == hashes[2]:
        errors.append("reported kernel digests are equal")
if errors:
    parser.exit(1, "\n".join(errors) + "\n")
print(f"PASS {args.mode}: rejected before userland")
