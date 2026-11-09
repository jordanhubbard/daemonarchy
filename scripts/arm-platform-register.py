#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Validate and summarize the 1.6 platform inventory, without qualifying hardware."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "docs/roadmap/arm-platforms.json"
FEATURES = (
    "boot", "all_cpus", "memory_dma", "storage", "display", "input",
    "network", "audio", "power", "installer", "installed_boot", "update", "recovery",
)
IDENTITY = (
    "model", "soc", "board_revision", "ram", "firmware", "boot_chain", "abi", "storage",
)
# Scope from release-1.6.0.md. Changes require the operator scope decision
# required there, with a corresponding review of this list and the register.
REQUIRED = {
    "SPARK-001": {"rtx-spark-n1x"},
    "SPARK-002": {"dgx-spark-fe", "asus-ascent-gx10"},
    "APPLE-001": {"apple-m1-mini", "apple-m1-macbook", "apple-m2-mini",
                  "apple-m2-pro-mini", "apple-m2-macbook", "apple-m3", "apple-m4",
                  "apple-a18-pro", "apple-m5", "apple-emerging"},
    "RPI-001": {"pi4b", "pi400", "cm4"},
    "RPI-002": {"pi5-c1", "pi5-d0", "cm5", "pi500"},
    "SBC-001": {"rock5b", "orange-pi5", "orange-pi5-plus", "rk3399", "rk356x",
                "orion-o6", "allwinner", "amlogic", "imx8", "mnt-reform"},
    "QUALCOMM-001": {"thinkpad-x13s", "snapdragon-x-elite", "snapdragon-x-plus"},
    "ARM-007": {"ampere-altra", "aws-graviton", "arm-cloud-additional",
                "qemu-hvf", "qemu-kvm", "qemu-tcg", "utm", "vmware-fusion"},
    "ARM-008": {"pi3", "pi-zero2", "armv7", "beaglebone", "pi-armv6", "pi-zero-armv6"},
}
STATES = {"unknown", "blocked", "failed", "passed"}


def validate(register, root=ROOT):
    """Check inventory consistency. Evidence references are not execution receipts."""
    problems = []
    if register.get("schema") != "daemonarchy/arm-platform-register@1":
        problems.append("unsupported register schema")
    if register.get("release") != "1.6.0":
        problems.append("register must describe release 1.6.0")
    profiles = register.get("profiles")
    if not isinstance(profiles, list):
        return problems + ["profiles must be a list"]
    seen = set()
    for index, row in enumerate(profiles):
        label = f"profiles[{index}]"
        if not isinstance(row, dict):
            problems.append(label + ": expected an object")
            continue
        name = row.get("id")
        if not isinstance(name, str) or not name or name in seen:
            problems.append(label + ": missing or duplicate id")
            continue
        seen.add(name)
        label = name
        work = row.get("work_item")
        if not isinstance(work, str) or work not in REQUIRED:
            problems.append(label + ": unknown platform work item")
        if row.get("kind") not in ("physical", "vm", "cloud"):
            problems.append(label + ": expected physical, vm or cloud kind")
        if row.get("role") not in ("desktop", "server", "feasibility"):
            problems.append(label + ": invalid intended role")
        for field in ("scope_name", "owner", "discovery_needed"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                problems.append(label + ": missing " + field)
        hardware = row.get("hardware")
        if (not isinstance(hardware, dict) or hardware.get("state") not in (
                "unallocated", "available", "unavailable")
                or not isinstance(hardware.get("note"), str) or not hardware["note"].strip()):
            problems.append(label + ": hardware allocation needs state and note")
        identity = row.get("identity", {})
        if not isinstance(identity, dict) or set(identity) != set(IDENTITY):
            problems.append(label + ": incomplete identity fields")
        elif any(value is not None and (not isinstance(value, str) or not value.strip())
                 for value in identity.values()):
            problems.append(label + ": identity values must be nonempty strings or null")
        refs = row.get("sources")
        if not isinstance(refs, list) or not refs:
            problems.append(label + ": missing source references")
        else:
            for ref in refs:
                if not isinstance(ref, str):
                    problems.append(label + ": invalid source reference")
                    continue
                path = (root / ref.split("#", 1)[0]).resolve()
                if not path.is_relative_to(root.resolve()) or not path.is_file():
                    problems.append(label + ": source reference is not a repository file: " + ref)
        features = row.get("features")
        if not isinstance(features, dict) or set(features) != set(FEATURES):
            problems.append(label + ": feature matrix is incomplete")
            continue
        for feature, result in features.items():
            if (not isinstance(result, dict) or not isinstance(result.get("state"), str)
                    or result["state"] not in STATES):
                problems.append(label + "/" + feature + ": invalid result state")
                continue
            if not isinstance(result.get("note"), str) or not result["note"].strip():
                problems.append(label + "/" + feature + ": missing result explanation")
            # The initial register deliberately cannot promote results from
            # reports or bootstrap experiments into final-image acceptance.
            # Add a reviewed receipt admission contract before admitting passes.
            if result["state"] == "passed":
                problems.append(label + "/" + feature + ": final-image receipt admission is not implemented")
    for work, names in REQUIRED.items():
        for name in sorted(names):
            matching = [row for row in profiles if isinstance(row, dict) and row.get("id") == name]
            if not matching:
                problems.append("missing required scope row: " + name)
            elif matching[0].get("work_item") != work:
                problems.append(name + ": required work item is " + work)
    return problems


def summary(register):
    counts = {state: 0 for state in sorted(STATES)}
    missing = {}
    for row in register["profiles"]:
        missing[row["id"]] = [field for field in IDENTITY if row["identity"][field] is None]
        for result in row["features"].values():
            counts[result["state"]] += 1
    return dict(release=register["release"], profiles=len(register["profiles"]),
                feature_states=counts, unresolved_identity=missing,
                qualification="not established; inventory validation only")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=DEFAULT)
    args = parser.parse_args()
    try:
        register = json.loads(args.register.read_text())
        if not isinstance(register, dict):
            raise ValueError("register must be an object")
        problems = validate(register)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    if problems:
        parser.exit(1, "\n".join(problems) + "\n")
    print(json.dumps(summary(register), indent=2))


if __name__ == "__main__":
    main()
