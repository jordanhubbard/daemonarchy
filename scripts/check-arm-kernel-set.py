#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Inspect a complete kernel set before a private ARM installer assembly."""
import argparse
import hashlib
from pathlib import PurePosixPath
import re
import struct
import tarfile


def inspect(path):
    names = set()
    modules = set()
    aliases = {}
    kernel = None
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            raw = member.name
            name = PurePosixPath(raw)
            if (name.is_absolute() or ".." in name.parts
                    or not (member.isdir() or member.isfile() or member.issym())):
                raise ValueError("kernel set contains an unsafe member: " + raw)
            normalized = name.as_posix()
            if normalized == "." and member.isdir():
                continue
            trees = ("boot/kernel", "boot/dtb", "usr/lib/debug/boot/kernel", "usr/lib/debug/boot/dtb")
            parents = {"boot", "usr", "usr/lib", "usr/lib/debug", "usr/lib/debug/boot"}
            if not any(normalized == tree or normalized.startswith(tree + "/") for tree in trees):
                if not member.isdir() or normalized not in parents:
                    raise ValueError("kernel set contains a member outside its kernel/DTB trees: " + raw)
            if normalized in names:
                raise ValueError("kernel set contains a duplicate member: " + normalized)
            names.add(normalized)
            if member.issym():
                # FreeBSD's if_igb/if_igbv aliases point to if_em. Admit only
                # same-directory aliases to real, inspected kernel modules.
                target = PurePosixPath(member.linkname)
                if (not normalized.startswith("boot/kernel/") or not normalized.endswith(".ko")
                        or target.is_absolute() or len(target.parts) != 1
                        or target.name in {".", ".."} or not target.name.endswith(".ko")):
                    raise ValueError("unsafe kernel module alias: " + raw)
                aliases[normalized] = (name.parent / target).as_posix()
                continue
            if normalized.endswith(".ko"):
                if not member.isfile() or member.size < 64:
                    raise ValueError("invalid kernel module: " + raw)
                header = archive.extractfile(member).read(64)
                elf_type, machine = struct.unpack_from("<HH", header, 16)
                if (header[:6] != b"\x7fELF\x02\x01"
                        or machine != 183 or elf_type not in (1, 3)):
                    raise ValueError("an AArch64 ELF64 module is required: " + raw)
                modules.add(normalized)
            if normalized == "boot/kernel/kernel":
                if not member.isfile() or not 64 <= member.size <= 512 * 1024 * 1024:
                    raise ValueError("invalid kernel file in set")
                kernel = archive.extractfile(member).read()
    if any(target not in modules for target in aliases.values()):
        raise ValueError("kernel module alias must target an inspected regular module")
    if (kernel is None or kernel[:6] != b"\x7fELF\x02\x01"
            or struct.unpack_from("<H", kernel, 18)[0] != 183):
        raise ValueError("an AArch64 ELF64 kernel is required in the set")
    versions = set(re.findall(rb"FreeBSD ([0-9]+\.[^\0 \t\r\n]*) #[0-9]+", kernel))
    if len(versions) != 1 or not next(iter(versions)).startswith(b"16."):
        raise ValueError("a FreeBSD 16 kernel is required in the set")
    if "boot/kernel/geom_uzip.ko" not in modules:
        raise ValueError("kernel set must include its GEOM UZIP module")
    return hashlib.sha256(kernel).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel_set")
    args = parser.parse_args()
    try:
        print(inspect(args.kernel_set))
    except (OSError, ValueError, tarfile.TarError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
