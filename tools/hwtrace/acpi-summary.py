#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Validate a loader ACPI snapshot and decode its CPU topology, offline.

TARGET is a hwtrace image/device or mounted DATRACE directory. Output contains
topology and hashes; raw table custody stays with the private target/capture.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct


def madt(data):
    if len(data) < 44 or data[:4] != b"APIC":
        raise ValueError("invalid MADT header")
    cpus, off = [], 44
    while off < len(data):
        if off + 2 > len(data):
            raise ValueError("truncated MADT subtable")
        kind, size = data[off:off + 2]
        if size < 2 or off + size > len(data):
            raise ValueError("invalid MADT subtable length")
        if kind == 11:
            if size < 76:
                raise ValueError("short GICC entry")
            uid, flags, parking = struct.unpack_from("<III", data, off + 8)
            mpidr = struct.unpack_from("<Q", data, off + 68)[0]
            cpus.append(dict(uid=uid, mpidr=f"0x{mpidr:x}", flags=flags,
                             enabled=bool(flags & 1), online_capable=bool(flags & 8),
                             parking_version=parking,
                             efficiency_class=data[off + 76] if size > 76 else None))
        off += size
    ids = [c["mpidr"] for c in cpus]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate GICC MPIDRs")
    return dict(gicc_entries=len(cpus), enabled=sum(c["enabled"] for c in cpus),
                online_capable=sum(c["online_capable"] for c in cpus), cpus=cpus)


def summary(volume):
    raw = volume.read("ACPI/INDEX.TXT")
    if not raw:
        raise ValueError("no loader ACPI index")
    index = raw.decode("ascii").rstrip("\n\0")
    header = re.fullmatch(r"Daemonarchy loader ACPI capture v1 epoch=(\d+)",
                          index.splitlines()[0])
    if not header:
        raise ValueError("incomplete or unknown ACPI capture")
    epoch = int(header[1])
    state = (volume.read("STATE.TXT") or b"").decode("ascii")
    if not re.search(rf"(?m)^epoch={epoch}$", state):
        raise ValueError("ACPI index belongs to a different queue epoch")
    result = dict(schema="daemonarchy/acpi-discovery@1", epoch=epoch, tables={})
    for line in index.splitlines()[1:]:
        m = re.fullmatch(r"(\w+) length=(\d+) fnv1a=([0-9a-f]{8}) write=(\d+) (.+)", line)
        if not m:
            raise ValueError("malformed ACPI index entry")
        name, size, checksum, status, outcome = m.groups()
        size = int(size)
        entry = result["tables"][name] = dict(length=size, status=outcome,
                                               write_status=int(status))
        if outcome != "captured" or int(status) != 0:
            continue
        if size < 20 or size > 16384:
            raise ValueError(f"invalid length for {name}")
        payload = volume.read(f"ACPI/{name}.BIN") or b""
        if len(payload) < size:
            raise ValueError(f"truncated {name}")
        payload = payload[:size]
        h = 2166136261
        for byte in payload:
            h = ((h ^ byte) * 16777619) & 0xffffffff
        if h != int(checksum, 16) or sum(payload) & 255:
            raise ValueError(f"hash/checksum mismatch for {name}")
        if name == "RSDP":
            if payload[:8] != b"RSD PTR " or sum(payload[:20]) & 255:
                raise ValueError("invalid RSDP")
        elif size < 36 or struct.unpack_from("<I", payload, 4)[0] != size:
            raise ValueError(f"invalid ACPI header length for {name}")
        entry["sha256"] = hashlib.sha256(payload).hexdigest()
        if name == "APIC":
            result["topology"] = madt(payload)
    if "topology" not in result:
        raise ValueError("no validated MADT CPU topology")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "boottrace/stick.py"
    spec = importlib.util.spec_from_file_location("stick", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        print(json.dumps(summary(module.Volume(args.target)), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f"ACPI capture rejected: {error}\n")


if __name__ == "__main__":
    main()
