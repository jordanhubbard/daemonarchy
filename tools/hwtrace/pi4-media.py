#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Create a Pi 4B UEFI discovery image from an aarch64 hwtrace image.

Writes a NEW regular image file only, never a device. Firmware ZIP identity must
be supplied explicitly. EEPROM and its boot order are not changed. This creates
a diagnostic candidate; it does not qualify full RAM, DMA or the desktop.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("firmware_zip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--firmware-sha256", required=True)
    args = parser.parse_args()
    if not stat.S_ISREG(args.source.stat().st_mode):
        parser.error("source must be a regular image file")
    if digest(args.firmware_zip) != args.firmware_sha256:
        parser.error("firmware checksum mismatch")
    with args.source.open("rb") as stream:
        stream.seek(512)
        header = stream.read(92)
        if header[:8] != b"EFI PART":
            parser.error("source is not GPT")
        lba, count, stride = struct.unpack_from("<QII", header, 72)
        if not 1 <= count <= 4096 or not 128 <= stride <= 4096:
            parser.error("invalid GPT entry layout")
        stream.seek(lba * 512)
        entry = stream.read(stride)
        if entry[:16] != bytes.fromhex("28732ac11ff8d211ba4b00a0c93ec93b"):
            parser.error("first partition is not the EFI System Partition")
        offset = struct.unpack_from("<Q", entry, 32)[0] * 512
        if offset < 1024 or offset >= args.source.stat().st_size:
            parser.error("invalid ESP offset")
    # Exclusive creation also refuses an existing file, symlink or device.
    with args.output.open("xb") as out, args.source.open("rb") as src:
        shutil.copyfileobj(src, out)
    target = f"{args.output}@@{offset}"
    members = []
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(args.firmware_zip) as archive:
        total = 0
        names = set(archive.namelist())
        if not {"RPI_EFI.fd", "config.txt", "start4.elf", "fixup4.dat",
                "bcm2711-rpi-4-b.dtb"} <= names:
            parser.error("firmware ZIP is missing Pi 4 boot inputs")
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                parser.error("invalid firmware ZIP member")
            total += info.file_size
            if total > 32 * 1024 * 1024:
                parser.error("firmware ZIP exceeds ESP budget")
            destination = Path(tmp).joinpath(*path.parts)
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(info))
                members.append(dict(path=info.filename, sha256=digest(destination)))
        # Preserve the upstream firmware settings and license files verbatim.
        for child in sorted(Path(tmp).iterdir()):
            subprocess.run(["mcopy", "-s", "-o", "-i", target, str(child), "::/"], check=True)
        loader = subprocess.check_output(["mtype", "-i", target, "::/EFI/BOOT/BOOTAA64.EFI"])
        if loader[:2] != b"MZ":
            parser.error("ESP lacks an aarch64 EFI loader")
        for member in members:
            data = subprocess.check_output(["mtype", "-i", target, "::/" + member["path"]])
            if hashlib.sha256(data).hexdigest() != member["sha256"]:
                parser.error("firmware readback mismatch")
    with tempfile.TemporaryDirectory() as tmp:
        queue = Path(tmp) / "pi4-queue.txt"
        queue.write_text("[pi4-uefi-acpi-baseline]\nhw.ncpu=4\n")
        stick = Path(__file__).resolve().parents[1] / "boottrace/stick.py"
        subprocess.run([sys.executable, str(stick), "queue", str(args.output),
                        str(queue)], check=True)
    manifest = dict(schema="daemonarchy/pi4-discovery-media@1", model="Raspberry Pi 4B",
                    source_sha256=digest(args.source), firmware_zip_sha256=digest(args.firmware_zip),
                    output_sha256=digest(args.output), firmware_files=members,
                    limitations=["physical boot pending", "UEFI defaults to 3 GiB RAM cap",
                                 "EEPROM USB/ESP boot support must be inventoried",
                                 "Pi 400 and CM4 need separate qualification"])
    args.output.with_suffix(args.output.suffix + ".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Created {args.output}; read back every firmware file; physical acceptance pending")


if __name__ == "__main__":
    main()
