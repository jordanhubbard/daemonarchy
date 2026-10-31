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

STATE.TXT and the TRACES/ slots are preallocated and contiguous.
SLOTS.MAP records where they live (byte offsets in the partition), so the
loader rewrites their sectors through EFI_BLOCK_IO instead of the
firmware FAT driver, whose writes did not reach the stick on the MSI
Raider.  This tool writes those files in place (raw through the map for
images and devices, without truncating on a mounted volume), so they never
move.

  stick.py add-partition IMAGE [--size-mib 256]   append + format DATRACE
  stick.py init TARGET                            create tag, state, dirs
  stick.py write-map IMAGE                        (re)write SLOTS.MAP
  stick.py check-map IMAGE                        verify SLOTS.MAP
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
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid

TAG = "Daemonarchy boottrace stick v1\n"
LABEL = "DATRACE"
# The loader rewrites these files in place and never allocates clusters
# (a firmware FAT cache may not reach the disk before the kernel writes).
SLOTS = 200
SLOT_SIZE = 16384
STATE_SIZE = 512
EMPTY = b"(empty trace slot)\n"
MAP_NAME = "SLOTS.MAP"
MAP_SIZE = 16384
MAP_TAG = "Daemonarchy DATRACE block map v1"


def padded(data, size):
    if len(data) > size:
        raise ValueError("content does not fit its preallocated file")
    return data + b"\n" * (size - len(data))
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


def fnv1a(data):
    h = 2166136261
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


class Fat32:
    """Read-only FAT32 walker over a partition of an image or device."""

    def __init__(self, f, part_off):
        self.f, self.part_off = f, part_off
        bs = self._pread(0, 512)
        (self.bps, self.spc, self.reserved, self.nfats) = struct.unpack_from("<HBHB", bs, 11)
        self.fatsz = struct.unpack_from("<I", bs, 36)[0]
        self.root = struct.unpack_from("<I", bs, 44)[0]
        total = struct.unpack_from("<H", bs, 19)[0] or struct.unpack_from("<I", bs, 32)[0]
        if bs[510:512] != b"\x55\xaa" or bs[82:87] != b"FAT32" or self.bps not in (
                512, 1024, 2048, 4096) or self.spc == 0 or self.fatsz == 0:
            raise ValueError("DATRACE is not a FAT32 volume")
        self.cluster = self.bps * self.spc
        self.data_off = (self.reserved + self.nfats * self.fatsz) * self.bps
        self.nclusters = (total * self.bps - self.data_off) // self.cluster
        self.fat = self._pread(self.reserved * self.bps, self.fatsz * self.bps)

    def _pread(self, off, size):
        self.f.seek(self.part_off + off)
        data = self.f.read(size)
        if len(data) != size:
            raise ValueError("short read")
        return data

    def next(self, c):
        return struct.unpack_from("<I", self.fat, c * 4)[0] & 0x0FFFFFFF

    def chain(self, first):
        out, c = [], first
        while 2 <= c < 0x0FFFFFF7:
            if c >= self.nclusters + 2 or len(out) > self.nclusters:
                raise ValueError("bad cluster chain")
            out.append(c)
            c = self.next(c)
        return out

    def offset(self, c):
        return self.data_off + (c - 2) * self.cluster

    def _entries(self, first):
        data = b"".join(self._pread(self.offset(c), self.cluster) for c in self.chain(first))
        for i in range(0, len(data), 32):
            e = data[i:i + 32]
            if e[0] == 0:
                return
            if e[0] == 0xE5 or e[11] == 0x0F or e[11] & 0x08:
                continue
            name = e[0:8].decode("ascii", "replace").rstrip()
            ext = e[8:11].decode("ascii", "replace").rstrip()
            clus = struct.unpack_from("<H", e, 20)[0] << 16 | struct.unpack_from("<H", e, 26)[0]
            yield (name + ("." + ext if ext else "")).upper(), e[11], clus, \
                struct.unpack_from("<I", e, 28)[0]

    def lookup(self, path):
        """(first cluster, size, is_dir) of a path such as TRACES/0001.TXT."""
        cur = self.root
        parts = [p for p in path.upper().split("/") if p]
        for i, part in enumerate(parts):
            for name, attr, clus, size in self._entries(cur):
                if name == part:
                    if i == len(parts) - 1:
                        return clus, size, bool(attr & 0x10)
                    cur = clus
                    break
            else:
                return None
        return None

    def listdir(self, path):
        hit = self.lookup(path)
        if hit is None or not hit[2]:
            return []
        return [n for n, attr, _, _ in self._entries(hit[0]) if not n.startswith(".")]

    def extent(self, path):
        """Byte offset of a contiguous, nonempty file and its size."""
        hit = self.lookup(path)
        if hit is None or hit[2]:
            raise ValueError(f"{path}: missing")
        first, size, _ = hit
        chain = self.chain(first)
        if chain != list(range(first, first + len(chain))):
            raise ValueError(f"{path}: not contiguous")
        if size == 0 or len(chain) * self.cluster < size:
            raise ValueError(f"{path}: not preallocated")
        return self.offset(first), size


def mapped_files(fat):
    names = ["STATE.TXT"] + ["TRACES/" + n for n in sorted(fat.listdir("TRACES"))
                             if re.fullmatch(r"\d{4}\.TXT", n)]
    return [(n,) + fat.extent(n) for n in names]


def make_map(part_lba, part_sectors, data_off, files):
    text = "%s\npart_lba=%d\npart_sectors=%d\ndata_off=%d\n" % (
        MAP_TAG, part_lba, part_sectors, data_off)
    text += "".join("file=%s off=%d size=%d\n" % f for f in files)
    return text + "sum=%08x\n" % fnv1a(text.encode())


def parse_map(text):
    """Mirror of the loader's bt_map_parse; raises ValueError."""
    if isinstance(text, bytes):
        text = text.decode("ascii")
    text = text.rstrip("\n\0")
    lines = text.split("\n")
    if lines[0] != MAP_TAG:
        raise ValueError("not a v1 block map")
    m = re.fullmatch(r"sum=([0-9a-f]{1,8})", lines[-1])
    body = text[:len(text) - len(lines[-1])]
    if not m or int(m.group(1), 16) != fnv1a(body.encode()):
        raise ValueError("block map checksum mismatch")
    out = {"files": {}}
    for line in lines[1:-1]:
        k = re.fullmatch(r"(part_lba|part_sectors|data_off)=(\d+)", line)
        f = re.fullmatch(r"file=([!-~]+) off=(\d+) size=(\d+)", line)
        if k:
            out[k.group(1)] = int(k.group(2))
        elif f and "\\" not in f.group(1):
            off, size = int(f.group(2)), int(f.group(3))
            if (off % 512 or off < out["data_off"] or not 0 < size <= MAP_SIZE
                    or off + size > out["part_sectors"] * 512):
                raise ValueError(f"extent outside the data area: {line}")
            for o, sz in out["files"].values():
                if off < o + sz and o < off + size:
                    raise ValueError(f"overlapping extents: {line}")
            out["files"][f.group(1).upper()] = (off, size)
        else:
            raise ValueError(f"bad block map line: {line!r}")
    if not out["files"] or not {"part_lba", "part_sectors", "data_off"} <= out.keys():
        raise ValueError("block map is missing fields")
    return out


def compute_map(image):
    """The map text for an image or device, from its GPT and FAT, and
    the extent of SLOTS.MAP itself."""
    _, first, count = gpt_partition(image)
    with open(image, "rb") as f:
        fat = Fat32(f, first * 512)
        files = mapped_files(fat)
        return make_map(first, count, fat.data_off, files), fat.extent(MAP_NAME)


def write_map(image):
    text, (off, size) = compute_map(image)
    if len(text) > size:
        raise ValueError(f"{MAP_NAME} is too small for the map")
    _, first, _ = gpt_partition(image)
    with open(image, "r+b") as f:
        f.seek(first * 512 + off)
        f.write(padded(text.encode(), size))
        f.flush()
        os.fsync(f.fileno())
    check_map(image)
    return text


def check_map(image):
    """Verify SLOTS.MAP against the FAT and return the parsed map."""
    text, (off, size) = compute_map(image)
    _, first, _ = gpt_partition(image)
    with open(image, "rb") as f:
        f.seek(first * 512 + off)
        stored = f.read(size)
    parsed = parse_map(stored)
    if stored.rstrip(b"\n") != text.rstrip("\n").encode():
        raise ValueError("SLOTS.MAP does not match the files on the volume")
    return parsed


class Volume:
    """Directory or mtools-backed access to the DATRACE filesystem."""

    def __init__(self, target):
        self.dir = Path(target) if Path(target).is_dir() else None
        self.map = None
        if self.dir is None:
            self.image = target
            _, first, _ = gpt_partition(target)
            self.part_off = first * 512
            self.spec = f"{target}@@{first * 512}"
            try:
                self.map = check_map(target)
            except ValueError as e:
                if self.read(MAP_NAME) is not None:
                    raise SystemExit(f"{target}: {MAP_NAME} is invalid ({e}); "
                                     "run write-map")

    def rewrite(self, path, data, size):
        """Replace a preallocated file's contents without moving it."""
        data = padded(data, size)
        if self.dir:
            p = self.dir / path
            if p.exists() and p.stat().st_size == size:
                with open(p, "r+b") as f:     # no truncation: same clusters
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
            else:
                self.write(path, data)
            return
        ext = self.map["files"].get(path.upper()) if self.map else None
        if ext is None:
            self.write(path, data)
            return
        if ext[1] != size:
            raise ValueError(f"{path}: SLOTS.MAP says {ext[1]} bytes, expected {size}")
        with open(self.image, "r+b") as f:
            f.seek(self.part_off + ext[0])
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

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
            "pending": state.get("pending", ""), "epoch": int(state.get("epoch") or 0)}


def new_epoch():
    """Queue generation; the loader's NVRAM self-report is tied to it."""
    return random.SystemRandom().randrange(1, 1 << 31)


def write_state(vol, state):
    text = "next=%d\ntraces=%d\npending=%s\n" % (
        state["next"], state["traces"], state["pending"])
    if state.get("epoch"):
        text += "epoch=%d\n" % state["epoch"]
    vol.rewrite("STATE.TXT", text.encode(), STATE_SIZE)


def empty_slots(vol):
    for i in range(1, SLOTS + 1):
        vol.rewrite("TRACES/%04d.TXT" % i, EMPTY, SLOT_SIZE)


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
    vol.mkdir("DUMPS")
    empty_slots(vol)
    write_state(vol, {"next": 1, "traces": 0, "pending": "", "epoch": new_epoch()})
    if vol.read(MAP_NAME) is None:
        vol.write(MAP_NAME, padded(b"(block map not written yet)\n", MAP_SIZE))
    if vol.dir is None:
        write_map(args.target)
        print("initialized: %d trace slots, empty queue, %s written" % (SLOTS, MAP_NAME))
    else:
        print("initialized: %d trace slots, empty queue; run write-map on the "
              "device for raw loader writes" % SLOTS)


def cmd_write_map(args):
    text = write_map(args.image)
    print(f"{args.image}: {MAP_NAME} lists {text.count('file=')} contiguous files")


def cmd_check_map(args):
    m = check_map(args.image)
    print(f"{args.image}: {MAP_NAME} ok, {len(m['files'])} files, partition at "
          f"sector {m['part_lba']}")


def cmd_queue(args):
    vol = Volume(args.target)
    if (vol.read("DATRACE.TAG") or b"") != TAG.encode():
        sys.exit("not an initialized DATRACE volume; run init first")
    experiments = parse_experiments(Path(args.experiments).read_text())
    for name in vol.listdir("QUEUE"):
        vol.remove("QUEUE/" + name)
    state = read_state(vol)
    if args.reset_traces:
        empty_slots(vol)
        state["traces"] = 0
    for i, e in enumerate(experiments, 1):
        body = "# experiment: %s\n%s\n" % (e["name"], "\n".join(e["lines"]))
        vol.write("QUEUE/%04d.CNF" % i, body.encode())
    state.update(next=1, pending="", epoch=new_epoch())
    write_state(vol, state)
    if vol.map is not None:
        check_map(args.target)
    print(f"queued {len(experiments)} experiments; traces continue after "
          f"{state['traces']}")


KEY_TYPES = ("ssh-", "ecdsa-", "sk-")


def cmd_keys(args):
    """Put public keys on the stick for the network debugger."""
    vol = Volume(args.target)
    if (vol.read("DATRACE.TAG") or b"") != TAG.encode():
        sys.exit("not an initialized DATRACE volume")
    lines = []
    for line in Path(args.keyfile).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "PRIVATE KEY" in line or not line.startswith(KEY_TYPES):
            sys.exit(f"{args.keyfile}: not a public key line: {line[:30]}...")
        lines.append(line)
    if not lines:
        sys.exit(f"{args.keyfile}: no public keys")
    old = [] if args.replace else [
        l for l in (vol.read("KEYS/authorized_keys") or b"").decode().splitlines()
        if l.strip()]
    merged = old + [l for l in lines if l not in old]
    vol.mkdir("KEYS")
    vol.write("KEYS/authorized_keys", ("\n".join(merged) + "\n").encode())
    print(f"KEYS/authorized_keys now holds {len(merged)} key(s)")


def cmd_network(args):
    """Show where the network debugger said to connect."""
    vol = Volume(args.target)
    addr = vol.read("ADDRESS.TXT")
    if addr is None:
        sys.exit("no ADDRESS.TXT: no boot has handed over to the debugger")
    sys.stdout.write(addr.decode("ascii", "replace"))
    pub = vol.read("KEYS/ssh_host_ed25519_key.pub")
    print("host key file on the stick: " + ("yes" if pub else "no"))


def cmd_status(args):
    vol = Volume(args.target)
    state = read_state(vol)
    queued = [n for n in vol.listdir("QUEUE") if n.endswith(".CNF")]
    print(f"next experiment: {state['next']:04d} of {len(queued)}; "
          f"pending: {state['pending'] or '-'}; traces filed: {state['traces']}; "
          f"epoch {state['epoch'] or '-'}")
    if vol.dir is None:
        print("block map: " + ("%d files, raw loader writes" % len(vol.map["files"])
                               if vol.map else "none (loader uses the FAT driver)"))


def summarize(text):
    """(experiment, status, last step, loader line) of a filed trace.

    Old traces have neither the breadcrumb ring nor the loader lines."""
    exp = re.search(r"^experiment: (.*)$", text, re.M)
    status = re.search(r"^Status: (.*)$", text, re.M)
    last = re.search(r"^Last step: (.*)$", text, re.M)
    nv = re.search(r"^nvram: (.*)$", text, re.M)
    loader = re.search(r"^loader now: (.*)$", text, re.M)
    return (exp.group(1) if exp else "?",
            status.group(1) if status else (nv.group(1) if nv else "?"),
            last.group(1) if last else "",
            loader.group(1) if loader else "")


def ring(text):
    """Breadcrumb ring lines of a filed trace, oldest first (new format)."""
    m = re.search(r"^NVRAM breadcrumb ring, \d+ newest \(oldest first\):\n((?:  .*\n)*)",
                  text, re.M)
    return [l.strip() for l in m.group(1).splitlines()] if m else []


def cmd_traces(args):
    vol = Volume(args.target)
    names = [n for n in vol.listdir("TRACES") if n.endswith(".TXT")]
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
    names = names[:read_state(vol)["traces"]] if len(names) >= SLOTS else names
    shown = 0
    for name in names:
        text = vol.read("TRACES/" + name).decode("utf-8", "replace").rstrip("\n") + "\n"
        if text.startswith(EMPTY.decode()):
            continue
        shown += 1
        exp, status, last, loader = summarize(text)
        print(f"{name}: experiment {exp}\n    {status}\n    last step: {last}")
        if loader:
            print(f"    loader: {loader}")
        if args.all:
            print(text)
        if args.out:
            (Path(args.out) / name).write_text(text)
    if not shown:
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
    for name, func in (("write-map", cmd_write_map), ("check-map", cmd_check_map)):
        p = sub.add_parser(name)
        p.add_argument("image")
        p.set_defaults(func=func)
    p = sub.add_parser("keys")
    p.add_argument("target")
    p.add_argument("keyfile")
    p.add_argument("--replace", action="store_true",
                   help="replace the keys instead of adding to them")
    p.set_defaults(func=cmd_keys)
    p = sub.add_parser("network")
    p.add_argument("target")
    p.set_defaults(func=cmd_network)
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
