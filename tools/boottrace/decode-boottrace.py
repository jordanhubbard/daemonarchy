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
Breadcrumbs are a ring of variables DBTStep00..DBTStepNN sorted by their
sequence number; kernels before the ring wrote one DBTStep variable, which
is still read.  DBTLoader is the hardware-trace stick loader's
self-report.
"""

import argparse
import json
import os
import struct
import sys
import uuid

VARNAME = "DaemonarchyBootTrace"
STEP_VARNAME = "DBTStep"
RING_MAX = 64
RING_NAMES = ["%s%02d" % (STEP_VARNAME, i) for i in range(RING_MAX)]
STEP = struct.Struct("<IIIIIHH40s")
LOADER_VARNAME = "DBTLoader"
LOADER = struct.Struct("<8s14I64s")
LOADER_STEPS = ["none", "found stick", "read STATE.TXT", "filed trace",
                "chose experiment", "wrote STATE.TXT", "verified STATE.TXT",
                "booting", "stopped"]
LOADER_FLAGS = {0x1: "running", 0x2: "NOT-PERSISTING", 0x4: "repeat-stop",
                0x8: "block-map", 0x10: "block-map-rejected", 0x20: "test-drop"}
LOADER_METHODS = {0: "-", 1: "raw blocks (SLOTS.MAP)", 2: "firmware FAT driver"}
LOADER_VERIFY = {0: "-", 1: "ok", 2: "MISMATCH", 3: "read error", 4: "skipped (test drop)"}
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
         0x8: "fine-window", 0x10: "test-armed", 0x20: "saved-to-usb", 0x40: "thinned",
         0x80: "strided", 0x100: "runtime-reclaim"}
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
     nv_left_kb, budget_writes, nv_used_kb, step_writes, kernel) = HEADER.unpack_from(data)
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
            "step_writes": step_writes,
            "kernel": cstr(kernel),
            "record_size": record_size, "crumbs": crumbs,
            "messages": messages}


def decode_step(data):
    if data is None or len(data) < STEP.size:
        return None
    seq, index, a, b, ms, kind, cpu, text = STEP.unpack_from(data)
    return {"seq": seq, "index": index, "ms": ms, "kind": KINDS.get(kind, "?"),
            "cpu": cpu, "subsystem": a, "order": b, "text": cstr(text)}


def decode_ring(blobs):
    """Breadcrumbs from any number of slot variables, oldest first."""
    steps = [decode_step(b) for b in blobs]
    return sorted((s for s in steps if s and s["seq"]), key=lambda s: s["seq"])


def decode_loader(data):
    if data is None or len(data) < LOADER.size:
        return None
    f = LOADER.unpack_from(data)
    if f[0] != b"DBTLDR01":
        return None
    keys = ("epoch", "cycle", "step", "flags", "method", "write_status", "verify",
            "next", "traces", "pending", "repeat", "stick_next", "stick_traces",
            "stick_pending")
    rec = dict(zip(keys, f[1:15]))
    rec["text"] = cstr(f[15])
    return rec


def loader_report(l):
    step = LOADER_STEPS[l["step"]] if l["step"] < len(LOADER_STEPS) else "?"
    flags = ",".join(n for bit, n in LOADER_FLAGS.items() if l["flags"] & bit) or "none"
    out = ["Loader self-report (EFI variable %s): cycle %u (epoch %u) reached '%s'; "
           "stick via %s; flags %s" % (LOADER_VARNAME, l["cycle"], l["epoch"], step,
                                       LOADER_METHODS.get(l["method"], "?"), flags)]
    if l["step"] >= 5:
        out.append("  wrote next=%u traces=%u pending=%04u, status %u, read-back %s" % (
            l["next"], l["traces"], l["pending"], l["write_status"],
            LOADER_VERIFY.get(l["verify"], "?")))
    out.append("  had read next=%u traces=%u pending=%04u; repeat %u; %s" % (
        l["stick_next"], l["stick_traces"], l["stick_pending"], l["repeat"], l["text"]))
    return "\n".join(out) + "\n"


def step_line(s):
    return "b%u " % s["seq"] + crumb_line(s)


def crumb_line(c):
    line = "#%u %u.%03us cpu%u %s: %s" % (c["index"], c["ms"] // 1000,
                                          c["ms"] % 1000, c["cpu"], c["kind"],
                                          c["text"])
    if c["kind"] == "sysinit":
        line += " [sub 0x%x order 0x%x]" % (c["subsystem"], c["order"])
    return line


def report(rec, step=None):
    """step: the newest breadcrumb (dict) or the whole ring (list)."""
    as_ring = isinstance(step, list)
    ring = step if as_ring else ([step] if step else [])
    step = ring[-1] if ring else None
    out = ["Daemonarchy boot trace (EFI variable %s, write #%u)" % (VARNAME, rec["seq"]),
           "Status: " + rec["status_text"]]
    newest = rec["crumbs"][-1]["index"] if rec["crumbs"] else 0
    if step and step["index"] > newest and rec["status"] == 1:
        out.append("Last step: " + crumb_line(step))
        out.append("      (breadcrumb #%u; the full record below is from step #%u)"
                   % (step["seq"], rec["steps"]))
    elif rec["crumbs"]:
        out.append("Last step: " + crumb_line(rec["crumbs"][-1]))
    out.append("Kernel: " + rec["kernel"])
    out.append("Steps seen: %u, last full write at %.3fs, NVRAM free at start %u KiB, "
               "%u KiB written, %u breadcrumbs (budget ~%u), flags %s" % (
                   rec["steps"], rec["uptime_ms"] / 1000, rec["nv_left_kb"],
                   rec["nv_used_kb"], rec["step_writes"], rec["budget_writes"],
                   ",".join(rec["flag_names"]) or "none"))
    if rec["resume_from"] == 0xFFFFFFFF:
        out.append("Persisted: coarse before debug.boottrace.from_sub, every step after it")
    else:
        out.append("Persisted: every step from #%u" % rec["resume_from"])
    if rec["flags"] & 0x80:
        out.append("NOTE: the NVRAM budget ran low; near the end only every %uth step was "
                   "persisted." % (1 << ((rec["flags"] >> 16) & 0xFF)))
    out.append("Recent steps (oldest first):")
    out.extend("  " + crumb_line(c) for c in rec["crumbs"])
    if as_ring and ring:
        out.append("NVRAM breadcrumb ring, %u newest (oldest first):" % len(ring))
        out.extend("  " + step_line(s) for s in ring)
    out.append("Last kernel messages:")
    out.extend("  " + l for l in rec["messages"].rstrip("\n").split("\n"))
    return "\n".join(out) + "\n"


def scan_vars(blob, varname=VARNAME):
    """Return (copies, live_data) for a trace variable in an EDK2 store."""
    guid_bytes = GUID.bytes_le
    name = (varname + "\0").encode("utf-16-le")
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
    ap.add_argument("--step", action="append", default=[],
                    help="breadcrumb file (raw, or efivarfs with --efivarfs); repeat "
                    "for each ring slot.  With --efivarfs the DBTStep* and DBTLoader "
                    "files next to PATH are read automatically")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    with open(args.path, "rb") as f:
        blob = f.read()
    copies, loader, raws = None, None, []
    for path in args.step:
        with open(path, "rb") as f:
            raw = f.read()
        raws.append(raw[4:] if args.efivarfs else raw)
    if args.vars:
        raws += [scan_vars(blob, n)[1] for n in [STEP_VARNAME] + RING_NAMES]
        loader = decode_loader(scan_vars(blob, LOADER_VARNAME)[1])
        copies, blob = scan_vars(blob)
    elif args.efivarfs:
        blob = blob[4:]
        if not args.step:
            d = os.path.dirname(os.path.abspath(args.path))
            for n in [STEP_VARNAME] + RING_NAMES + [LOADER_VARNAME]:
                p = os.path.join(d, "%s-%s" % (n, GUID))
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        data = f.read()[4:]
                    if n == LOADER_VARNAME:
                        loader = decode_loader(data)
                    else:
                        raws.append(data)
    ring = decode_ring(raws)
    if blob is None:
        print("no live %s variable (%d stored copies)" % (VARNAME, copies))
        if loader:
            sys.stdout.write(loader_report(loader))
        return 3
    rec = decode(blob)
    if args.json:
        rec["stored_copies"] = copies
        rec["breadcrumb"] = ring[-1] if ring else None
        rec["ring"] = ring
        rec["loader"] = loader
        json.dump(rec, sys.stdout, indent=1)
        print()
    else:
        sys.stdout.write(report(rec, ring))
        if loader:
            sys.stdout.write(loader_report(loader))
        if copies is not None:
            print("(variable store holds %d copies of the trace)" % copies)
    return 0


if __name__ == "__main__":
    sys.exit(main())
