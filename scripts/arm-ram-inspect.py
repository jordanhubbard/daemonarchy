#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Read packed ARM installer roots without mounting filesystems or devices.

CLOOP layout follows FreeBSD sys/geom/uzip/g_uzip_cloop.h and g_uzip.c.
Sleuth Kit supplies the read-only UFS2 inode and file readers. Processing
budgets constrain inspection work, not target hardware RAM or CPU discovery.
"""
import argparse
from array import array
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zlib

MAX_ROOT_BYTES = 64 << 30
MAX_BLOCKS = 4 << 20
MAX_CLUSTER = 1 << 20


def unpack_root(source, destination, max_bytes=MAX_ROOT_BYTES):
    if not stat.S_ISREG(source.lstat().st_mode):
        raise ValueError('regular nonsymlink UZIP input required')
    size = source.stat().st_size
    with source.open('rb') as image:
        header = image.read(136)
        if len(header) != 136 or header[:11] != b'#!/bin/sh\n#':
            raise ValueError('invalid UZIP header')
        codec, version = chr(header[11]).upper(), chr(header[12])
        minimum = {'V': '2', 'L': '3'}.get(codec)
        if minimum is None or version not in ('2', '3', '4') or version < minimum:
            raise ValueError('unsupported UZIP codec/version')
        cluster, count = struct.unpack_from('>II', header, 128)
        if (not cluster or cluster % 512 or cluster > MAX_CLUSTER or
                not 1 <= count <= MAX_BLOCKS or cluster * count > max_bytes):
            raise ValueError('UZIP geometry exceeds inspection budget')
        table_end = 136 + (count + 1) * 8
        if table_end > size:
            raise ValueError('truncated UZIP offset table')
        offsets = array('Q')
        offsets.frombytes(image.read((count + 1) * 8))
        if sys.byteorder == 'little':
            offsets.byteswap()
        if offsets[-1] == 0 and version < '4':
            offsets[-1] = size
        if any(not table_end <= offset <= size for offset in offsets):
            raise ValueError('UZIP cluster offset outside payload')
        if shutil.disk_usage(destination.parent).free < cluster * count:
            raise ValueError('insufficient scratch space for expanded RAM root')
        # Zero-length entries describe zero clusters. Earlier compressed data
        # may be reused by a later entry; only an already established extent
        # can be referenced. Keep extents, never a cache of expanded blocks.
        extents = {}
        high = offsets[0] - 1
        checksum = hashlib.sha256()
        zeros = bytes(cluster)
        padding = 0
        with destination.open('xb') as output:
            for index in range(count):
                start = offsets[index]
                if start < high:
                    if start not in extents:
                        raise ValueError('invalid UZIP backward reference')
                    length = extents[start]
                else:
                    following = index + 1
                    while following <= count and offsets[following] <= high:
                        following += 1
                    if following > count:
                        raise ValueError('UZIP cluster has no end offset')
                    length = offsets[following] - start
                    if length < 0 or length > cluster * 2 + 512:
                        raise ValueError('invalid UZIP compressed cluster extent')
                    high = start + length - 1
                    if length:
                        extents[start] = length
                if length == 0:
                    block = zeros
                else:
                    image.seek(start)
                    packed = image.read(length)
                    if len(packed) != length:
                        raise ValueError('truncated UZIP cluster')
                    if codec == 'V':
                        decoder = zlib.decompressobj()
                        block = decoder.decompress(packed, cluster + 1)
                        remainder = decoder.unused_data
                    else:
                        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 << 20)
                        block = decoder.decompress(packed, max_length=cluster + 1)
                        remainder = decoder.unused_data if decoder.eof else b''
                    short_last = (index == count - 1 and 0 < len(block) < cluster and
                                  len(block) % 512 == 0)
                    if ((len(block) != cluster and not short_last) or not decoder.eof or
                            (remainder and (len(remainder) >= 512 or any(remainder)))):
                        raise ValueError('UZIP cluster %d does not decode to its declared size' % index)
                    # mkuzip encodes the short final read as-is. The logical
                    # block device is cluster-rounded; make its tail explicit.
                    if short_last:
                        padding = cluster - len(block)
                        block += bytes(padding)
                checksum.update(block)
                if block == zeros:
                    output.seek(cluster, 1)
                else:
                    output.write(block)
            output.truncate(cluster * count)
    return dict(format='ufs-geom-uzip', codec='zlib' if codec == 'V' else 'lzma',
                cluster_bytes=cluster, expanded_bytes=cluster * count,
                expanded_sha256=checksum.hexdigest(), zero_padded_bytes=padding)


class UFS:
    def __init__(self, image, ifind='ifind', icat='icat', istat='istat'):
        self.image, self.ifind, self.icat, self.istat = image, ifind, icat, istat

    def file(self, path):
        # No filesystem path supplied by the image is used as a host path.
        try:
            inode = subprocess.check_output([self.ifind, '-f', 'ufs2', '-n', path,
                                             str(self.image)], text=True, timeout=60).strip()
        except subprocess.CalledProcessError as error:
            raise ValueError('cannot locate required RAM root file: ' + path) from error
        if not re.fullmatch('[0-9]+', inode):
            raise ValueError('RAM root requires exactly one inode for ' + path)
        info = subprocess.check_output([self.istat, '-f', 'ufs2', str(self.image), inode],
                                       text=True, timeout=60)
        if (not re.search(r'^Allocated\s*$', info, re.MULTILINE) or
                not re.search(r'^mode:\s+[r-]', info, re.MULTILINE | re.IGNORECASE)):
            raise ValueError('RAM root requires an allocated regular file: ' + path)
        size = re.search(r'^size:\s+(\d+)\s*$', info, re.MULTILINE | re.IGNORECASE)
        if size is None or not 0 < int(size[1]) <= MAX_ROOT_BYTES:
            raise ValueError('invalid RAM root file size: ' + path)
        return inode, int(size[1])

    def read(self, path, limit=1 << 20):
        inode, size = self.file(path)
        if size > limit:
            raise ValueError('RAM root metadata exceeds inspection budget: ' + path)
        data = subprocess.check_output([self.icat, '-f', 'ufs2', str(self.image), inode], timeout=60)
        if len(data) != size:
            raise ValueError('incomplete RAM root file: ' + path)
        return data

    def identity(self, path, inspect=None):
        inode, size = self.file(path)
        if shutil.disk_usage(self.image.parent).free < size:
            raise ValueError('insufficient scratch space for RAM file inspection')
        with tempfile.TemporaryDirectory(dir=self.image.parent) as directory:
            selected = Path(directory) / 'payload'
            with selected.open('xb') as output:
                subprocess.run([self.icat, '-f', 'ufs2', str(self.image), inode],
                               stdout=output, stderr=subprocess.PIPE, check=True, timeout=180)
            if selected.stat().st_size != size:
                raise ValueError('cannot read complete RAM root file: ' + path)
            with selected.open('rb') as output:
                checksum = hashlib.file_digest(output, 'sha256').hexdigest()
            if inspect is not None:
                inspect(selected)
        return dict(bytes=size, sha256=checksum)


def inspect_root(image, outer, ifind='ifind', icat='icat', istat='istat'):
    root = UFS(image, ifind, icat, istat)
    identities = {}
    required = ('boot/kernel/kernel', 'boot/loader.efi', 'boot/lua/loader.lua',
                'usr/freebsd-dist/base.txz', 'usr/freebsd-dist/kernel.txz',
                'usr/local/libexec/daemonarchy-installer/install')
    def kernel_set(path):
        spec = importlib.util.spec_from_file_location(
            'arm_kernel_set', Path(__file__).with_name('check-arm-kernel-set.py'))
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        if checker.inspect(path) != outer['boot/kernel/kernel']['sha256']:
            raise ValueError('packed installation kernel set differs from the outer ISO')
    for name in required:
        identities[name] = root.identity(name, kernel_set if name.endswith('/kernel.txz') else None)
    for name in required[:2]:
        if identities[name]['sha256'] != outer[name]['sha256']:
            raise ValueError('packed RAM boot set differs from the outer ISO: ' + name)
    if root.read('usr/local/share/daemonarchy-installer/ABI').strip() != b'FreeBSD:16:aarch64':
        raise ValueError('packed RAM installer ABI mismatch')
    manifest = root.read('usr/freebsd-dist/MANIFEST').decode('utf-8')
    for name in ('base.txz', 'kernel.txz'):
        rows = [line.split('\t') for line in manifest.splitlines() if line.split('\t')[0] == name]
        if len(rows) != 1 or len(rows[0]) < 2 or rows[0][1] != identities['usr/freebsd-dist/' + name]['sha256']:
            raise ValueError('packed installer archive does not match MANIFEST: ' + name)
    return identities


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compressed', type=Path)
    parser.add_argument('expanded', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(unpack_root(args.compressed, args.expanded)))
    except (ValueError, OSError, lzma.LZMAError, zlib.error) as error:
        parser.exit(1, f'arm-ram-inspect: {error}\n')
