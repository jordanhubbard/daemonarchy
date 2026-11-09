#!/usr/bin/env python3
"""Make tiny synthetic UFS2 fixtures on FreeBSD; these are not bootable images."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import platform
import struct
import subprocess
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert platform.system() == 'FreeBSD'
args.work.mkdir(mode=0o700)
args.output.mkdir(mode=0o700)
root = args.work / 'root'


def write(path, data):
    selected = root / path
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_bytes(data)


kernel = bytearray(96)
kernel[:6] = b'\x7fELF\x02\x01'
struct.pack_into('<H', kernel, 18, 183)
kernel += b'FreeBSD 16.0-CURRENT #0 synthetic test fixture\0'
loader = bytearray(256)
loader[:2] = b'MZ'
struct.pack_into('<I', loader, 60, 128)
loader[128:132] = b'PE\0\0'
struct.pack_into('<H', loader, 132, 0xaa64)
struct.pack_into('<H', loader, 152, 0x20b)
write('boot/kernel/kernel', kernel)
module = bytearray(64)
module[:6] = b'\x7fELF\x02\x01'
struct.pack_into('<HH', module, 16, 1, 183)
write('boot/kernel/geom_uzip.ko', module)
write('boot/loader.efi', loader)
write('boot/lua/loader.lua', b'-- Synthetic parser fixture, not a loader\n')
write('usr/local/libexec/daemonarchy-installer/install', b'#!/bin/sh\nexit 1 # Synthetic fixture, never install\n')
write('usr/local/share/daemonarchy-installer/ABI', b'FreeBSD:16:aarch64\n')
archives = {}
for name, members in [('base.txz', [('bin/sh', b'synthetic shell, not executable\n')]),
                      ('kernel.txz', [('boot/kernel/kernel', kernel), ('boot/kernel/geom_uzip.ko', module)])]:
    content = io.BytesIO()
    with tarfile.open(fileobj=content, mode='w:xz') as archive:
        for member, data in members:
            info = tarfile.TarInfo(member)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    archives[name] = content.getvalue()
    write('usr/freebsd-dist/' + name, archives[name])
write('usr/freebsd-dist/MANIFEST', ''.join(
    name + '\t' + hashlib.sha256(data).hexdigest() + '\t1\tfixture\n'
    for name, data in archives.items()).encode())
outer = {name: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
         for name, data in [('boot/kernel/kernel', kernel), ('boot/loader.efi', loader)]}
(args.output / 'outer.json').write_text(json.dumps(outer, indent=2) + '\n')
for label in ('complete', 'missing-installer'):
    if label == 'missing-installer':
        (root / 'usr/local/libexec/daemonarchy-installer/install').unlink()
    image = args.work / (label + '.ufs')
    subprocess.run(['makefs', '-t', 'ffs', '-B', 'little', '-o', 'version=2', '-T', '0',
                    '-s', '16m', str(image), str(root)], check=True)
    subprocess.run(['mkuzip', '-o', str(args.output / (label + '.uzip')), str(image)], check=True)
