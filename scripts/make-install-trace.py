#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Append initialized trace storage to an EFI-only hybrid ISO on FreeBSD.

Uses native makefs/mkimg, without mounting filesystems or accessing devices.
The input remains immutable; output and work paths must be fresh. This prepares
storage only: the presence of a partition does not establish boot capture.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import uuid
import zlib

SECTOR = 512
SYSTEM_AREA = 32768
EFI = uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_gpt(path, lba=1):
    """Validate the selected GPT header/table before trusting any offsets."""
    size = path.stat().st_size
    if size % SECTOR:
        raise ValueError('image is not sector aligned')
    with path.open('rb') as stream:
        stream.seek(lba * SECTOR)
        header = bytearray(stream.read(SECTOR))
        if len(header) != SECTOR or header[:8] != b'EFI PART':
            raise ValueError('missing GPT header')
        revision, length, crc = struct.unpack_from('<III', header, 8)
        if revision != 0x10000 or not 92 <= length <= SECTOR:
            raise ValueError('invalid GPT header size/revision')
        struct.pack_into('<I', header, 16, 0)
        if zlib.crc32(header[:length]) != crc:
            raise ValueError('GPT header checksum mismatch')
        current, backup, first, last = struct.unpack_from('<4Q', header, 24)
        table_lba, count, entry_size, table_crc = struct.unpack_from('<QIII', header, 72)
        if (current != lba or backup >= size // SECTOR or backup == current or
                first > last or last >= size // SECTOR or not 1 <= count <= 128 or
                entry_size != 128 or table_lba < 2 or
                table_lba * SECTOR + count * entry_size > size):
            raise ValueError('invalid GPT bounds')
        stream.seek(table_lba * SECTOR)
        table = stream.read(count * entry_size)
    if zlib.crc32(table) != table_crc:
        raise ValueError('GPT table checksum mismatch')
    entries = []
    for offset in range(0, len(table), entry_size):
        entry = table[offset:offset + entry_size]
        if entry[:16] == bytes(16):
            continue
        start, end = struct.unpack_from('<QQ', entry, 32)
        if not first <= start <= end <= last:
            raise ValueError('GPT partition outside usable range')
        if any(start <= other['end'] and end >= other['start'] for other in entries):
            raise ValueError('overlapping GPT partitions')
        entries.append(dict(type=entry[:16], start=start, end=end))
    return dict(current=current, backup=backup, first=first, last=last,
                table_lba=table_lba, table=table, guid=bytes(header[56:72]), entries=entries)


def copy_range(source, dest, offset, count):
    source.seek(offset)
    dest.seek(offset)
    while count:
        block = source.read(min(count, 1 << 20))
        if not block:
            raise ValueError('short image read')
        dest.write(block)
        count -= len(block)


def read_identity(path):
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > 256:
        raise ValueError('regular bounded installation trace identity required')
    with path.open('rb') as stream:
        data = stream.read(257)
    match = re.fullmatch(
        rb'Daemonarchy installation trace identity v1\n'
        rb'image_id=([0-9a-f-]{36})\narchive_sha256=([0-9a-f]{64})\n'
        rb'mode=observe-only\n', data)
    if match is None or str(uuid.UUID(match[1].decode())) != match[1].decode():
        raise ValueError('invalid installation trace identity')
    return data, dict(image_id=match[1].decode(), archive_sha256=match[2].decode())


def assemble(image, output, work, stick_path, size_mib=256, identity_path=None):
    if not stat.S_ISREG(image.lstat().st_mode):
        raise ValueError('input must be a regular nonsymlink image')
    if output.exists() or output.is_symlink() or work.exists() or work.is_symlink():
        raise ValueError('output and work must not exist')
    if not 256 <= size_mib <= 4096:
        raise ValueError('trace size must be 256..4096 MiB')
    gpt = read_gpt(image)
    if len(gpt['entries']) != 1 or gpt['entries'][0]['type'] != EFI:
        raise ValueError('requires an EFI-only hybrid ISO with one ESP')
    if gpt['table_lba'] * SECTOR + len(gpt['table']) > SYSTEM_AREA:
        raise ValueError('GPT table extends into ISO payload')
    with image.open('rb') as stream:
        stream.seek(SYSTEM_AREA)
        if stream.read(7) != b'\x01CD001\x01':
            raise ValueError('input has no ISO9660 primary volume descriptor')
    spec = importlib.util.spec_from_file_location('stick', stick_path)
    stick = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stick)
    identity = digest(image)
    original_size = image.stat().st_size
    identity_data, declared = None, None
    if identity_path is not None:
        identity_data, declared = read_identity(identity_path)
        members = subprocess.check_output(['tar', '-tf', str(image)],
                                          text=True, timeout=120).splitlines()
        matches = [m for m in members if m.removeprefix('./') == 'boot/trace-id']
        if len(matches) != 1 or subprocess.check_output(
                ['tar', '-xOf', str(image), matches[0]], timeout=60) != identity_data:
            raise ValueError('trace identity differs from the actual boot filesystem')
    start = ((original_size + (1 << 20) - 1) // (1 << 20)) * (1 << 20)
    work.mkdir(mode=0o700)
    data = work / 'data'
    data.mkdir()
    stick.cmd_init(argparse.Namespace(target=str(data)))
    if identity_data is not None:
        (data / 'INSTALL.ID').write_bytes(identity_data)
        (data / 'NORMAL').mkdir()
        for slot in range(1, stick.NORMAL_SLOTS + 1):
            (data / 'NORMAL' / f'{slot:04d}.TXT').write_bytes(
                stick.padded(stick.NORMAL_EMPTY, stick.SLOT_SIZE))
    (data / 'INSTALL.JSON').write_text(json.dumps(dict(
        schema=1, mode='observe-only', payload_sha256=identity,
        payload_bytes=original_size, declared_identity=declared,
        automatic_capture_qualified=False), indent=2) + '\n')
    fat = work / 'trace.fat'
    subprocess.run(['makefs', '-t', 'msdos', '-s', f'{size_mib}m', '-o',
                    'fat_type=32,sectors_per_cluster=4,volume_label=DATRACE', str(fat), str(data)],
                   check=True)
    if not fat.is_file() or fat.stat().st_size != size_mib * (1 << 20):
        raise ValueError('makefs did not create the expected FAT32 image')
    esp = gpt['entries'][0]
    layout = work / 'layout.img'
    subprocess.run(['mkimg', '-s', 'gpt', '-f', 'raw', '-p',
                    f"efi::{(esp['end'] - esp['start'] + 1) * SECTOR}:{esp['start'] * SECTOR}",
                    '-p', f'ms-basic-data/DATRACE:={fat}:{start}', '-o', str(layout)], check=True)
    primary = read_gpt(layout)
    backup = read_gpt(layout, primary['backup'])
    if (primary['backup'] != layout.stat().st_size // SECTOR - 1 or
            backup['backup'] != 1 or primary['guid'] != backup['guid'] or
            primary['table'] != backup['table'] or len(primary['entries']) != 2 or
            primary['entries'][0]['start'] != esp['start'] or
            primary['entries'][0]['end'] != esp['end'] or
            primary['entries'][1]['start'] * SECTOR != start):
        raise ValueError('assembled GPT does not match the requested layout')
    # O_EXCL creation prevents replacing any existing output. All ISO bytes
    # after its 32 KiB system area remain unchanged, including the embedded ESP.
    with output.open('xb') as dest, image.open('rb') as source, layout.open('rb') as native:
        shutil.copyfileobj(source, dest, 1 << 20)
        dest.truncate(layout.stat().st_size)
        # Retain boot code/disk signature; update protective MBR and both GPTs.
        copy_range(native, dest, 446, SYSTEM_AREA - 446)
        copy_range(native, dest, start, layout.stat().st_size - start)
    stick.write_map(str(output))
    mapping = stick.check_map(str(output))
    normal_slots = stick.NORMAL_SLOTS if identity_data is not None else 0
    if len(mapping['files']) != stick.SLOTS + 1 + normal_slots:
        raise ValueError('incomplete raw trace map')
    read_gpt(output)
    read_gpt(output, primary['backup'])
    # Compare every payload byte, not just files exposed by an ISO reader.
    with image.open('rb') as source, output.open('rb') as dest:
        source.seek(SYSTEM_AREA)
        dest.seek(SYSTEM_AREA)
        while block := source.read(1 << 20):
            if dest.read(len(block)) != block:
                raise ValueError('original ISO payload was changed')
    if digest(image) != identity:
        raise ValueError('input changed during assembly')
    return dict(schema=1, input_sha256=identity, output_sha256=digest(output),
                output_bytes=output.stat().st_size, trace_start_lba=start // SECTOR,
                mapped_files=len(mapping['files']), normal_boot_slots=normal_slots,
                declared_identity=declared, automatic_capture_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('--size-mib', type=int, default=256)
    parser.add_argument('--identity', type=Path,
                        help='Matched boot/trace-id for separate normal-boot slots')
    args = parser.parse_args()
    stick = Path(__file__).resolve().parents[1] / 'tools/boottrace/stick.py'
    try:
        result = assemble(args.image, args.output, args.work, stick, args.size_mib,
                          args.identity)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'make-install-trace: {error}\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
