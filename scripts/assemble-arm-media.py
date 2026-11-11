#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Assemble pinned ARM installer media into a new directory of regular files.

The input is a complete aarch64 hybrid installer ISO, not a hwtrace image.
Apple additionally needs its existing OS stub and owned ESP; this tool creates
the stage-2 files but does not enroll an OS or change any disk or boot policy.
Assembly checks do not establish hardware boot, installation or desktop support.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import uuid
import zipfile
import zlib


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked(path, expected):
    path = path.resolve(strict=True)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("regular input file required")
    if digest(path) != expected:
        raise ValueError("checksum mismatch: " + path.name)
    return path


def compatible(data):
    """Read a complete bounded FDT, returning its root compatible strings."""
    if len(data) < 40:
        raise ValueError("short FDT")
    magic, total, structure, strings, reserve, version, last, cpu, ns, nt = struct.unpack_from(
        ">10I", data)
    if (magic != 0xd00dfeed or not 40 <= total <= len(data)
            or version != 17 or last > 17
            or not 40 <= structure < structure + nt <= total
            or not 40 <= strings < strings + ns <= total
            or not 40 <= reserve <= total - 16):
        raise ValueError("invalid FDT bounds")
    pos, end, depth, result = structure, structure + nt, -1, None
    while pos + 4 <= end:
        token = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if token == 1:
            terminator = data.find(b"\0", pos, end)
            if terminator < 0 or depth >= 128:
                raise ValueError("invalid FDT node")
            pos = (terminator + 4) & ~3
            depth += 1
        elif token == 2:
            depth -= 1
            if depth < -1:
                raise ValueError("unbalanced FDT")
        elif token == 3:
            if depth < 0 or pos + 8 > end:
                raise ValueError("invalid FDT property")
            length, name = struct.unpack_from(">II", data, pos)
            pos += 8
            if pos + length > end or name >= ns:
                raise ValueError("FDT property outside block")
            terminator = data.find(b"\0", strings + name, strings + ns)
            if terminator < 0:
                raise ValueError("unterminated FDT property name")
            if depth == 0 and data[strings + name:terminator] == b"compatible":
                value = data[pos:pos + length]
                if not value.endswith(b"\0"):
                    raise ValueError("unterminated compatible property")
                result = value[:-1].decode("ascii").split("\0")
            pos = (pos + length + 3) & ~3
        elif token == 4:
            continue
        elif token == 9 and depth == -1 and result:
            return result
        else:
            raise ValueError("invalid FDT structure")
    raise ValueError("incomplete FDT")


def apple_bootstrap(path):
    # Asahi publishes both a direct ESP ZIP and a CI ZIP containing that ZIP.
    # Read only the named member: never extract arbitrary archive paths.
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if names.count("esp/m1n1/boot.bin") > 1:
            raise ValueError("ambiguous Apple stage-2 member")
        if "esp/m1n1/boot.bin" not in names:
            nested = [item for item in archive.infolist() if item.filename.endswith(".zip")]
            if len(nested) != 1 or nested[0].file_size > 32 * 1024 * 1024:
                raise ValueError("expected one bounded ESP ZIP")
            archive_data = archive.read(nested[0])
        else:
            archive_data = None
            member = archive.getinfo("esp/m1n1/boot.bin")
            if member.file_size > 16 * 1024 * 1024:
                raise ValueError("oversized Apple stage 2")
            payload = archive.read(member)
    if archive_data is not None:
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            if archive.namelist().count("esp/m1n1/boot.bin") != 1:
                raise ValueError("expected exactly one Apple stage-2 member")
            member = archive.getinfo("esp/m1n1/boot.bin")
            if member.file_size > 16 * 1024 * 1024:
                raise ValueError("oversized Apple stage 2")
            payload = archive.read(member)
    selected = []
    offset = 0
    while True:
        offset = payload.find(b"\xd0\x0d\xfe\xed", offset)
        if offset < 0:
            break
        if offset + 40 <= len(payload):
            size = struct.unpack_from(">I", payload, offset + 4)[0]
            if 40 <= size <= 1024 * 1024 and offset + size <= len(payload):
                blob = payload[offset:offset + size]
                try:
                    board = compatible(blob)
                except (ValueError, UnicodeError):
                    board = []
                if "apple,j474s" in board and "apple,t6020" in board:
                    selected.append(dict(offset=offset, bytes=size, compatible=board,
                                         sha256=hashlib.sha256(blob).hexdigest()))
        offset += 4
    if len(selected) != 1:
        raise ValueError("stage 2 must contain exactly one M2 Pro Mac mini / J474s DTB")
    return payload, selected[0]


def esp_offset(image):
    with image.open("rb") as stream:
        stream.seek(512)
        header = bytearray(stream.read(512))
        if len(header) != 512 or header[:8] != b"EFI PART":
            raise ValueError("installer requires a hybrid GPT/EFI boot path")
        length, checksum = struct.unpack_from("<II", header, 12)
        if not 92 <= length <= 512:
            raise ValueError("invalid GPT header length")
        struct.pack_into("<I", header, 16, 0)
        if zlib.crc32(header[:length]) != checksum:
            raise ValueError("invalid GPT header checksum")
        lba, count, stride, checksum = struct.unpack_from("<QIII", header, 72)
        if (not 1 <= count <= 4096 or not 128 <= stride <= 4096
                or lba * 512 + count * stride > image.stat().st_size):
            raise ValueError("invalid GPT table bounds")
        stream.seek(lba * 512)
        table = stream.read(count * stride)
        if zlib.crc32(table) != checksum:
            raise ValueError("invalid GPT table checksum")
    offsets = []
    for index in range(count):
        entry = table[index * stride:(index + 1) * stride]
        if entry[:16] != uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b").bytes_le:
            continue
        first, last = struct.unpack_from("<QQ", entry, 32)
        if not 34 <= first <= last or (last + 1) * 512 > image.stat().st_size:
            raise ValueError("EFI partition outside image")
        offsets.append(first * 512)
    if len(offsets) != 1:
        raise ValueError("installer requires exactly one EFI System Partition")
    return offsets[0]


def inspect_installer(image, tar, mtype):
    with image.open("rb") as stream:
        stream.seek(16 * 2048)
        if stream.read(7) != b"\x01CD001\x01":
            raise ValueError("installer must be an uncompressed ISO9660 image")
    members = subprocess.check_output([tar, "-tf", str(image)], text=True).splitlines()
    required = ("boot/kernel/kernel", "boot/loader.efi", "boot/lua/loader.lua",
                "usr/freebsd-dist/base.txz", "usr/freebsd-dist/kernel.txz",
                "usr/local/libexec/daemonarchy-installer/install")
    selected = {}
    for name in required:
        matches = [item for item in members if item.removeprefix("./") == name]
        if len(matches) != 1:
            raise ValueError("installer requires exactly one " + name)
        selected[name] = matches[0]
    identities = {}
    for name in required[:2]:
        data = subprocess.check_output([tar, "-xOf", str(image), selected[name]])
        if name.endswith("kernel"):
            valid = (len(data) >= 64 and data[:6] == b"\x7fELF\x02\x01"
                     and struct.unpack_from("<H", data, 18)[0] == 183)
        else:
            pe = struct.unpack_from("<I", data, 60)[0] if len(data) >= 64 else len(data)
            valid = (data[:2] == b"MZ" and pe + 26 <= len(data)
                     and data[pe:pe + 4] == b"PE\0\0"
                     and struct.unpack_from("<H", data, pe + 4)[0] == 0xaa64
                     and struct.unpack_from("<H", data, pe + 24)[0] == 0x20b)
        if not valid:
            raise ValueError(name + " is not an aarch64 kernel/EFI loader")
        identities[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if name.endswith("kernel"):
            versions = set(re.findall(rb"FreeBSD ([0-9]+\.[0-9]+[^\0 \t\r\n]*) #[0-9]+", data))
            if len(versions) != 1 or not next(iter(versions)).startswith(b"16."):
                raise ValueError("installer requires a FreeBSD 16 kernel")
            identities[name]["version"] = next(iter(versions)).decode("ascii")
    loader = subprocess.check_output(
        [mtype, "-i", str(image) + "@@" + str(esp_offset(image)), "::/EFI/BOOT/BOOTAA64.EFI"])
    if hashlib.sha256(loader).hexdigest() != identities["boot/loader.efi"]["sha256"]:
        raise ValueError("removable-media EFI loader differs from the installer boot set")
    return identities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("rtx-spark-n1x", "apple-m2-pro-mini"), required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--installer-sha256", required=True)
    parser.add_argument("--bootstrap-zip", type=Path)
    parser.add_argument("--bootstrap-sha256")
    parser.add_argument("--tar", default="tar", help="libarchive tar with ISO9660 support")
    parser.add_argument("--mtype", default="mtype", help="mtools read-only FAT reader")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    apple = args.platform == "apple-m2-pro-mini"
    if apple != bool(args.bootstrap_zip and args.bootstrap_sha256):
        parser.error("Apple requires both bootstrap ZIP and hash; RTX uses its UEFI firmware")
    if not apple and (args.bootstrap_zip or args.bootstrap_sha256):
        parser.error("Apple bootstrap inputs do not belong in RTX media")
    image = checked(args.installer, args.installer_sha256)
    identities = inspect_installer(image, args.tar, args.mtype)
    payload = board = bootstrap = None
    if apple:
        bootstrap = checked(args.bootstrap_zip, args.bootstrap_sha256)
        payload, board = apple_bootstrap(bootstrap)
        if digest(bootstrap) != args.bootstrap_sha256:
            raise ValueError("bootstrap changed during inspection")
    # Refuse existing outputs, symlinks and devices. All input checks precede it.
    args.output.mkdir(mode=0o700)
    target = args.output / ("daemonarchy-" + args.platform + ".iso")
    with target.open("xb") as stream, image.open("rb") as source:
        shutil.copyfileobj(source, stream)
    if digest(target) != args.installer_sha256 or digest(image) != args.installer_sha256:
        raise ValueError("installer changed during assembly")
    files = {target.name: dict(bytes=target.stat().st_size, sha256=digest(target))}
    if apple:
        boot = args.output / "owned-esp/m1n1/boot.bin"
        boot.parent.mkdir(parents=True)
        boot.write_bytes(payload)
        files[boot.relative_to(args.output).as_posix()] = dict(
            bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    instructions = (
        "Select the complete installer ISO as removable media in the target's UEFI firmware.\n"
        if not apple else
        "This stage 2 is for the M2 Pro Mac mini (J474s/T6020). It requires an already enrolled OS stub and its own matching ESP.\n"
        "Stage owned-esp/m1n1/boot.bin only in that OS-owned ESP after verifying ownership. Keep macOS and its Recovery environment.\n"
        "Boot that OS stub with the full installer ISO on removable media. Initial enrollment requires a separate host-local Recovery operation.\n")
    (args.output / "README.txt").write_text(
        instructions + "\nThese are development candidates. Assembly is verified; physical boot, installation, desktop and recovery acceptance remain open.\n")
    manifest = dict(schema="daemonarchy/arm-installer-media@1", platform=args.platform,
                    abi="FreeBSD:16:aarch64", installer_sha256=args.installer_sha256,
                    embedded=identities, files=files, apple_dtb=board,
                    bootstrap_sha256=args.bootstrap_sha256 if apple else None,
                    qualification=dict(assembly=True, physical_boot=False,
                                       installation=False, desktop=False, recovery=False))
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
