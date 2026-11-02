#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""DRAFT: re-observe the sealed installer image independently of the build.

Reads the images build-iso.sh produced (--images) and checks, with an implementation
separate from build-iso.sh and scripts/master-release.sh verify:

  sidecar-iso / sidecar-xz   sha256 of each file equals its .sha256 sidecar
  xz-roundtrip               the .xz decompresses (stdlib lzma) to the raw ISO's sha256
  budget-raw / budget-xz     under scripts/check-image-size.sh's 3.5 GiB / 2 GiB limits
  iso9660                    primary volume descriptor "CD001" is present
  image-version              ./usr/local/share/daemonarchy-installer/version == VERSION
  image-abi / image-tag      ABI and package-repository-tag files match the expectation
  live-sqlite3               the live root's Python carries _sqlite3 (listing via bsdtar)

It never boots the image, installs it, signs anything, or reads a key.  It is STATIC
image acceptance; VM/QEMU and physical acceptance are not performed here (UNKNOWN: no
retained action defines them).  Exit status is nonzero when any check fails; the report
is written regardless.
"""
import argparse
import hashlib
import json
import lzma
import subprocess
import sys
from pathlib import Path

RAW_LIMIT = 3758096384
XZ_LIMIT = 2147483648


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_xz(path):
    h = hashlib.sha256()
    with lzma.open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sidecar(path):
    side = Path(str(path) + ".sha256")
    if not side.is_file():
        return None
    fields = side.read_text().split()
    return fields[0] if fields else None


def member(iso, name):
    r = subprocess.run(["bsdtar", "-xOf", str(iso), name], capture_output=True, timeout=600)
    return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--images", required=True)
    ap.add_argument("--version-file", required=True)
    ap.add_argument("--arch", default="amd64")
    ap.add_argument("--expect-abi", default="FreeBSD:16:amd64")
    ap.add_argument("--expect-tag", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    version = Path(args.version_file).read_text().strip()
    images = Path(args.images)
    iso = images / ("daemonarchy-%s-%s.iso" % (version, args.arch))
    xz = Path(str(iso) + ".xz")
    results = []

    def check(cid, ok, detail=""):
        results.append({"id": cid, "ok": bool(ok), "detail": detail})

    present = iso.is_file() and xz.is_file()
    check("present", present, "%s and %s" % (iso.name, xz.name))
    if present:
        raw = sha256_file(iso)
        check("sidecar-iso", sidecar(iso) == raw, raw)
        check("sidecar-xz", sidecar(xz) == sha256_file(xz))
        check("xz-roundtrip", sha256_xz(xz) == raw)
        check("budget-raw", iso.stat().st_size < RAW_LIMIT, str(iso.stat().st_size))
        check("budget-xz", xz.stat().st_size < XZ_LIMIT, str(xz.stat().st_size))
        with open(iso, "rb") as f:
            f.seek(0x8000)
            pvd = f.read(7)
        check("iso9660", pvd == b"\x01CD001\x01", repr(pvd))
        check("image-version", (member(iso, "./usr/local/share/daemonarchy-installer/version") or "")
              .split(" (")[0] == version, version)
        check("image-abi", member(iso, "./usr/local/share/daemonarchy-installer/ABI") == args.expect_abi)
        check("image-tag", member(iso, "./usr/local/share/daemonarchy-installer/package-repository-tag")
              == args.expect_tag)
        listing = subprocess.run(["bsdtar", "-tf", str(iso)], capture_output=True, text=True, timeout=600)
        check("live-sqlite3", listing.returncode == 0 and "_sqlite3" in listing.stdout)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"schema": "daemonarchy/image-acceptance@1", "version": version,
                               "results": results}, indent=1) + "\n")
    failed = [r["id"] for r in results if not r["ok"]]
    if failed:
        print("image acceptance failed: " + ", ".join(failed), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
