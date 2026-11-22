#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Add regular files to a fresh image root without replacing builder outputs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys


def apply_overlay(source, target):
    source, target = Path(source), Path(target)
    if source.is_symlink() or not source.is_dir():
        raise ValueError("overlay must be a real directory")
    if target.is_symlink() or not target.is_dir():
        raise ValueError("target must be a real directory")
    entries = sorted(source.rglob("*"))
    # Validate the whole selection before copying anything. In particular, an
    # existing rescue symlink must never redirect a write outside this root.
    for path in entries:
        relative = path.relative_to(source)
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError(f"overlay contains a nonregular node: {relative}")
        if mode & (stat.S_ISUID | stat.S_ISGID):
            raise ValueError(f"overlay contains a privileged mode: {relative}")
        dest = target / relative
        for parent in [dest, *dest.parents]:
            if parent == target:
                break
            if parent.is_symlink():
                raise ValueError(f"destination crosses a symlink: {relative}")
        if dest.exists() and not (stat.S_ISDIR(mode) and dest.is_dir()):
            raise ValueError(f"overlay would replace an existing node: {relative}")
    records = {}
    for path in entries:
        relative = path.relative_to(source)
        dest = target / relative
        if path.is_dir():
            if not dest.exists():
                dest.mkdir(mode=stat.S_IMODE(path.stat().st_mode))
            continue
        # The builder owns this fresh staging root; never follow or replace an
        # existing final node, even if the source selection changes meanwhile.
        with path.open("rb") as src, dest.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        os.chmod(dest, stat.S_IMODE(path.stat().st_mode))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise ValueError(f"overlay readback differs: {relative}")
        records[str(relative)] = {"sha256": digest, "bytes": dest.stat().st_size}
    return records


if __name__ == "__main__":
    print(json.dumps(apply_overlay(*sys.argv[1:]), sort_keys=True))
