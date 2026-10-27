#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
"""Manage the DATRACE volume of a Daemonarchy hardware-trace stick.

The loader's "Hardware trace" cycle files each boot's NVRAM trace as
TRACES/NNNN.TXT and boots the next QUEUE/NNNN.CNF; STATE.TXT holds the
next queue entry, the trace counter and the pending experiment.

TARGET is either a mounted directory (e.g. /media/$USER/DATRACE) or a disk
image / block device, in which case the GPT partition named DATRACE is
accessed with mtools (no mount or root needed for image files).

  stick.py add-partition IMAGE [--size-mib 256]   append + format DATRACE
  stick.py init TARGET                            create tag, state, dirs
  stick.py queue TARGET EXPERIMENTS [--reset-traces]
  stick.py status TARGET
  stick.py traces TARGET [--out DIR] [--all]

EXPERIMENTS: blocks headed "[name]", each line a loader setting
(name=value, unset name, read-conf /path).  Example:

    [legacy-off]
    read-conf /boot/d/1

    [no-hpet]
    read-conf /boot/d/1
    hint.hpet.0.disabled=1
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid

TAG = "Daemonarchy boottrace stick v1\n"
LABEL = "DATRACE"
BASIC_DATA = uuid.UUID("ebd0a0a2-b9e5-4433-87c0-68b6b72699c7")


def parse_experiments(text):
    experiments, current = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"\[([A-Za-z0-9_.-]{1,48})\]", line)
        if m:
            current = {"name": m.group(1), "lines": []}
            experiments.append(current)
            continue
        if current is None:
            raise ValueError("settings must follow an [experiment] header")
        if len(line) > 79 or any(not 32 <= ord(c) <= 126 for c in line):
            raise ValueError(f"line too long or not printable ASCII: {line!r}")
        if not (re.fullmatch(r"[\w.-]+\s*=.*", line) or
                re.fullmatch(r"unset\s+[\w.-]+", line) or
                re.fullmatch(r"read-conf\s+\S+", line)):
            raise ValueError(f"not name=value, unset or read-conf: {line!r}")
        current["lines"].append(line)
    if len(experiments) > 9999:
        raise ValueError("at most 9999 experiments")
    return experiments


def gpt_partition(image, name=LABEL):
    with open(image, "rb") as f:
        f.seek(512)
        hdr = f.read(92)
        if hdr[:8] != b"EFI PART":
            raise ValueError(f"{image}: no GPT")
        lba, count, size = struct.unpack_from("<QII", hdr, 72)
        f.seek(lba * 512)
        table = f.read(count * size)
    for i in range(count):
        e = table[i * size:(i + 1) * size]
        if e[:16] == bytes(16):
            continue
        first, last = struct.unpack_from("<QQ", e, 32)
        pname = e[56:128].decode("utf-16-le").rstrip("\0")
        if pname == name:
            return i + 1, first, last - first + 1
    raise ValueError(f"{image}: no GPT partition named {name}")


class Volume:
    """Directory or mtools-backed access to the DATRACE filesystem."""

    def __init__(self, target):
        self.dir = Path(target) if Path(target).is_dir() else None
        if self.dir is None:
            _, first, _ = gpt_partition(target)
            self.spec = f"{target}@@{first * 512}"

    def _m(self, *args, data=None):
        env = dict(os.environ, MTOOLS_SKIP_CHECK="1", MTOOLS_NO_VFAT="0")
        return subprocess.run(args, input=data, capture_output=True, env=env)

    def read(self, path):
        if self.dir:
            p = self.dir / path
            return p.read_bytes() if p.exists() else None
        r = self._m("mtype", "-i", self.spec, "::/" + path)
        return r.stdout if r.returncode == 0 else None

    def write(self, path, data):
        if self.dir:
            p = self.dir / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return
        with tempfile.NamedTemporaryFile() as t:
            t.write(data)
            t.flush()
            r = self._m("mcopy", "-o", "-i", self.spec, t.name, "::/" + path)
            if r.returncode:
                raise OSError(r.stderr.decode())

    def mkdir(self, path):
        if self.dir:
            (self.dir / path).mkdir(exist_ok=True)
        else:
            self._m("mmd", "-i", self.spec, "::/" + path)

    def listdir(self, path):
        if self.dir:
            p = self.dir / path
            return sorted(x.name.upper() for x in p.iterdir()) if p.exists() else []
        r = self._m("mdir", "-b", "-i", self.spec, "::/" + path)
        return sorted(Path(l.strip()).name.upper() for l in r.stdout.decode().splitlines()
                      if l.strip())

    def remove(self, path):
        if self.dir:
            (self.dir / path).unlink(missing_ok=True)
        else:
            self._m("mdel", "-i", self.spec, "::/" + path)


def read_state(vol):
    raw = (vol.read("STATE.TXT") or b"").decode("ascii", "replace")
    state = dict(l.split("=", 1) for l in raw.splitlines() if "=" in l)
    return {"next": int(state.get("next") or 1), "traces": int(state.get("traces") or 0),
            "pending": state.get("pending", "")}


def write_state(vol, state):
    vol.write("STATE.TXT", ("next=%d\ntraces=%d\npending=%s\n" % (
        state["next"], state["traces"], state["pending"])).encode())


def cmd_add_partition(args):
    image = args.image
    _, size_mib = None, args.size_mib
    try:
        gpt_partition(image)
        sys.exit(f"{image} already has a {LABEL} partition")
    except ValueError:
        pass
    with open(image, "ab") as f:
        f.truncate(os.path.getsize(image) + size_mib * 1024 * 1024)
    subprocess.run(["sgdisk", "-e", image], check=True, capture_output=True)
    subprocess.run(["sgdisk", "-n", "0:0:0", "-t", "0:0700", "-c", "0:" + LABEL, image],
                   check=True, capture_output=True)
    num, first, count = gpt_partition(image)
    with tempfile.TemporaryDirectory() as d:
        fs = os.path.join(d, "fat.img")
        with open(fs, "wb") as f:
            f.truncate(count * 512)
        subprocess.run(["mkfs.fat", "-F", "32", "-n", LABEL, fs], check=True,
                       capture_output=True)
        with open(fs, "rb") as src, open(image, "r+b") as dst:
            dst.seek(first * 512)
            shutil.copyfileobj(src, dst, 1 << 20)
    print(f"{image}: partition {num} {LABEL}, {count * 512 // 1048576} MiB FAT32")


def cmd_init(args):
    vol = Volume(args.target)
    vol.write("DATRACE.TAG", TAG.encode())
    vol.mkdir("QUEUE")
    vol.mkdir("TRACES")
    write_state(vol, {"next": 1, "traces": 0, "pending": ""})
    print("initialized; empty queue")


def cmd_queue(args):
    vol = Volume(args.target)
    if (vol.read("DATRACE.TAG") or b"") != TAG.encode():
        sys.exit("not an initialized DATRACE volume; run init first")
    experiments = parse_experiments(Path(args.experiments).read_text())
    for name in vol.listdir("QUEUE"):
        vol.remove("QUEUE/" + name)
    state = read_state(vol)
    if args.reset_traces:
        for name in vol.listdir("TRACES"):
            vol.remove("TRACES/" + name)
        state["traces"] = 0
    for i, e in enumerate(experiments, 1):
        body = "# experiment: %s\n%s\n" % (e["name"], "\n".join(e["lines"]))
        vol.write("QUEUE/%04d.CNF" % i, body.encode())
    state.update(next=1, pending="")
    write_state(vol, state)
    print(f"queued {len(experiments)} experiments; traces continue after "
          f"{state['traces']}")


def cmd_status(args):
    vol = Volume(args.target)
    state = read_state(vol)
    queued = [n for n in vol.listdir("QUEUE") if n.endswith(".CNF")]
    print(f"next experiment: {state['next']:04d} of {len(queued)}; "
          f"pending: {state['pending'] or '-'}; traces filed: {state['traces']}")


def summarize(text):
    exp = re.search(r"^experiment: (.*)$", text, re.M)
    status = re.search(r"^Status: (.*)$", text, re.M)
    last = re.search(r"^Last step: (.*)$", text, re.M)
    nv = re.search(r"^nvram: (.*)$", text, re.M)
    return (exp.group(1) if exp else "?",
            status.group(1) if status else (nv.group(1) if nv else "?"),
            last.group(1) if last else "")


def cmd_traces(args):
    vol = Volume(args.target)
    names = [n for n in vol.listdir("TRACES") if n.endswith(".TXT")]
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
    for name in names:
        text = vol.read("TRACES/" + name).decode("utf-8", "replace")
        exp, status, last = summarize(text)
        print(f"{name}: experiment {exp}\n    {status}\n    last step: {last}")
        if args.all:
            print(text)
        if args.out:
            (Path(args.out) / name).write_text(text)
    if not names:
        print("no traces filed")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add-partition")
    p.add_argument("image")
    p.add_argument("--size-mib", type=int, default=256)
    p.set_defaults(func=cmd_add_partition)
    for name, func in (("init", cmd_init), ("status", cmd_status)):
        p = sub.add_parser(name)
        p.add_argument("target")
        p.set_defaults(func=func)
    p = sub.add_parser("queue")
    p.add_argument("target")
    p.add_argument("experiments")
    p.add_argument("--reset-traces", action="store_true",
                   help="delete filed traces and restart numbering")
    p.set_defaults(func=cmd_queue)
    p = sub.add_parser("traces")
    p.add_argument("target")
    p.add_argument("--out")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_traces)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
