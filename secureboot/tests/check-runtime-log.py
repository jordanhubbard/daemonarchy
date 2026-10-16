#!/usr/bin/env python3
"""Check retained serial evidence from the disposable native test guest."""
import argparse
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("valid", "preload-rejection", "missing-handoff",
                                    "uefi-off", "bios-normal"))
parser.add_argument("log", type=Path)
parser.add_argument("--kernel-path", default="kernel/kernel",
                    choices=("kernel/kernel", "kernel.secure/kernel"))
args = parser.parse_args()
log = args.log.read_text(errors="replace").replace("\r", "")

required = [
    r"SecureBoot: 1, SetupMode: 0",
    r"Testing hash: sha256\s+Passed",
    r"Testing hash: sha384\s+Passed",
    r"Testing verify certificate:[^\n]+Passed",
    rf"Verified /boot/{re.escape(args.kernel_path)}",
]
if args.mode == "uefi-off":
    required = [r"SecureBoot: 0, SetupMode: [01]",
                r"DAEMONARCHY_PROFILE_UEFI_OFF_STOCK_KERNEL_PASS"]
    forbidden = [r"panic:", r"UNEXPECTED_POLICY", r"DAEMONARCHY_MODULE_POLICY_STATE="]
elif args.mode == "bios-normal":
    required = [r"DAEMONARCHY_PROFILE_BIOS_STOCK_KERNEL_PASS"]
    forbidden = [r"panic:", r"UNEXPECTED_POLICY", r"DAEMONARCHY_MODULE_POLICY_STATE="]
elif args.mode in ("valid", "preload-rejection"):
    required += [
        r"Verified /boot/runtime\.manifest signed by",
        r"DAEMONARCHY_MODULE_POLICY_STATE=loaded active enforce locked",
        r"DAEMONARCHY_MODULE_POLICY_TRUSTED_LOAD_UNLOAD_PASS",
        r"mac_veriexec: rejected unverified kernel module",
        r"PASS unsigned-module: errno=8",
        r"PASS protected-module-write: errno=1",
        r"PASS kernel-memory-write: errno=1",
        r"PASS locked-policy-load: errno=1",
        r"DAEMONARCHY_MODULE_POLICY_USER_PROGRAM_PASS",
        r"DAEMONARCHY_MODULE_POLICY_ALL_PASS",
    ]
    if args.mode == "preload-rejection":
        required += [r"DAEMONARCHY_PRELOAD_GENERIC_REJECTED",
                     r"DAEMONARCHY_PRELOAD_RAW_REJECTED"]
    forbidden = [r"panic:", r"(?:^|\n)FAIL ", r"UNEXPECTEDLY_LOADED"]
else:
    required += [r"panic: mac_veriexec: verified manifest handoff is required"]
    forbidden = [r"DAEMONARCHY_MODULE_POLICY_USERLAND"]

errors = [f"missing: {pattern}" for pattern in required
          if not re.search(pattern, log)]
errors += [f"unexpected: {pattern}" for pattern in forbidden
           if re.search(pattern, log)]
if errors:
    parser.exit(1, "\n".join(errors) + "\n")
print(f"PASS {args.mode}: firmware, loader and kernel evidence present")
