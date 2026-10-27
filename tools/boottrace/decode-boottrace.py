#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
"""Decode a Daemonarchy reset-surviving boot trace.

Input is one of:
  * a raw record (the variable's data bytes),
  * a Linux efivarfs file (4-byte attribute prefix + data),
  * an EDK2/OVMF variable store such as a QEMU OVMF_VARS file
    (--vars); every stored copy is counted and the live one is decoded.

The record layout is sys/sys/daemonarchy_boottrace.h in daemonarchy-src.
"""

import argparse
import json
import struct
import sys
import uuid

VARNAME = "DaemonarchyBootTrace"
GUID = uuid.UUID("9262df38-e448-4c99-bdd0-e70eada0faa1")
MAGIC = b"DBTRACE1"
HEADER = struct.Struct("<8sHHHHIIIIIIIIIIII64s")
CRUMB = struct.Struct("<IIHHII76s")
KINDS = {1: "sysinit", 2: "probe", 3: "attach", 4: "hook", 5: "event",
         6: "panic", 7: "complete"}
STATUS = {1: "INCOMPLETE: the kernel never reached init (hang or reset)",
          2: "complete: the kernel reached init",
          3: "PANIC: the kernel panicked"}
FLAGS = {0x1: "loader-seen", 0x2: "budget-exhausted", 0x4: "write-error",
         0x8: "fine-window", 0x10: "test-armed", 0x20: "saved-to-usb"}
AUTH_VAR_GUID = uuid.UUID("aaf32c78-947b-439a-a180-2e144ec37792")
VAR_GUID = uuid.UUID("ddcf3616-3275-4164-98b6-fe85707ffe7d")
VAR_HDR = struct.Struct("<HBBIQ16sIII16s")   # authenticated, 60 bytes
VAR_HDR_PLAIN = struct.Struct("<HBBIII16s")  # 32 bytes


def cstr(raw):
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace")


def decode(data):
    if len(data) < HEADER.size:
        raise ValueError("record shorter than its header")
    (magic, version, header_size, crumb_size, crumb_count, record_size,
     seq, status, flags, steps, resume_from, msg_len, uptime_ms,
     nv_left_kb, budget_writes, nv_used_kb, _res, kernel) = HEADER.unpack_from(data)
    if magic != MAGIC or version != 1:
        raise ValueError("not a version 1 boot trace record")
    need = header_size + crumb_count * crumb_size + msg_len
    if header_size < HEADER.size or crumb_size < CRUMB.size or need > len(data):
        raise ValueError("record sizes are inconsistent")
    crumbs = []
    for i in range(crumb_count):
        index, ms, kind, cpu, a, b, text = CRUMB.unpack_from(
            data, header_size + i * crumb_size)
        crumbs.append({"index": index, "ms": ms, "kind": KINDS.get(kind, "?"),
                       "cpu": cpu, "subsystem": a, "order": b,
                       "text": cstr(text)})
    off = header_size + crumb_count * crumb_size
    messages = data[off:off + msg_len].decode("utf-8", "replace")
    return {"seq": seq, "status": status, "status_text": STATUS.get(status, "unknown"),
            "flags": flags,
            "flag_names": [n for bit, n in FLAGS.items() if flags & bit],
            "steps": steps, "resume_from": resume_from,
            "uptime_ms": uptime_ms, "nv_left_kb": nv_left_kb,
            "budget_writes": budget_writes, "nv_used_kb": nv_used_kb,
            "kernel": cstr(kernel),
            "record_size": record_size, "crumbs": crumbs,
            "messages": messages}


def crumb_line(c):
    line = "#%u %u.%03us cpu%u %s: %s" % (c["index"], c["ms"] // 1000,
                                          c["ms"] % 1000, c["cpu"], c["kind"],
                                          c["text"])
    if c["kind"] == "sysinit":
        line += " [sub 0x%x order 0x%x]" % (c["subsystem"], c["order"])
    return line


def report(rec):
    out = ["Daemonarchy boot trace (EFI variable %s, write #%u)" % (VARNAME, rec["seq"]),
           "Status: " + rec["status_text"]]
    if rec["crumbs"]:
        out.append("Last step: " + crumb_line(rec["crumbs"][-1]))
    out.append("Kernel: " + rec["kernel"])
    out.append("Steps seen: %u, last write at %.3fs, NVRAM free at start %u KiB, "
               "%u KiB written, budget %u full writes, flags %s" % (
                   rec["steps"], rec["uptime_ms"] / 1000, rec["nv_left_kb"],
                   rec["nv_used_kb"], rec["budget_writes"],
                   ",".join(rec["flag_names"]) or "none"))
    if rec["resume_from"] == 0xFFFFFFFF:
        out.append("Persisted: coarse steps only (zoom in with debug.boottrace.from=N)")
    else:
        out.append("Persisted: every step from #%u" % rec["resume_from"])
    out.append("Recent steps (oldest first):")
    out.extend("  " + crumb_line(c) for c in rec["crumbs"])
    out.append("Last kernel messages:")
    out.extend("  " + l for l in rec["messages"].rstrip("\n").split("\n"))
    return "\n".join(out) + "\n"


def scan_vars(blob):
    """Return (copies, live_data) for the trace in an EDK2 variable store."""
    guid_bytes = GUID.bytes_le
    name = (VARNAME + "\0").encode("utf-16-le")
    for store_guid, hdr in ((AUTH_VAR_GUID, VAR_HDR), (VAR_GUID, VAR_HDR_PLAIN)):
        at = blob.find(store_guid.bytes_le)
        if at < 0:
            continue
        size = struct.unpack_from("<I", blob, at + 16)[0]
        pos, end = at + 28, min(len(blob), at + size)
        copies, live = 0, None
        while pos + hdr.size <= end:
            fields = hdr.unpack_from(blob, pos)
            if fields[0] != 0x55AA:
                break
            state = fields[1]
            name_size, data_size, vendor = fields[-3], fields[-2], fields[-1]
            nstart = pos + hdr.size
            if vendor == guid_bytes and blob[nstart:nstart + name_size] == name:
                copies += 1
                if state in (0x3F, 0x3E):
                    live = blob[nstart + name_size:nstart + name_size + data_size]
            pos = (nstart + name_size + data_size + 3) & ~3
        return copies, live
    raise ValueError("no EDK2 variable store found")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--vars", action="store_true",
                    help="path is an EDK2/OVMF variable store")
    ap.add_argument("--efivarfs", action="store_true",
                    help="path is a Linux efivarfs file (attribute prefix)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with open(args.path, "rb") as f:
        blob = f.read()
    copies = None
    if args.vars:
        copies, blob = scan_vars(blob)
        if blob is None:
            print("no live %s variable (%d stored copies)" % (VARNAME, copies))
            return 3
    elif args.efivarfs:
        blob = blob[4:]
    rec = decode(blob)
    if args.json:
        rec["stored_copies"] = copies
        json.dump(rec, sys.stdout, indent=1)
        print()
    else:
        sys.stdout.write(report(rec))
        if copies is not None:
            print("(variable store holds %d copies of the trace)" % copies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
