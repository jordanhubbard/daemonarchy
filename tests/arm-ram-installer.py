#!/usr/bin/env python3
"""Native input/refusal controls using actual pinned build inputs; no image build."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--builder', type=Path, required=True)
parser.add_argument('--inputs', type=Path, required=True,
                    help='JSON with world/kernel_set/package/closure path and sha256 pairs')
parser.add_argument('--work', type=Path, required=True)
args = parser.parse_args()
assert platform.system() == 'FreeBSD' and os.geteuid() == 0
args.work.mkdir(mode=0o700)
inputs = json.loads(args.inputs.read_text())
base = [inputs[key][item] for key in ('world', 'kernel_set', 'package')
        for item in ('path', 'sha256')]
closure = [inputs['closure'][item] for item in ('path', 'sha256')]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def refuse(label, selected, message, occupied=None):
    output, work = args.work / (label + '.iso'), args.work / (label + '-work')
    sentinel = occupied(output, work) if occupied else None
    result = subprocess.run(['sh', str(args.builder), *selected, str(output), str(work), *closure],
                            text=True, capture_output=True)
    (args.work / (label + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode != 0 and message in result.stderr, (label, result)
    if sentinel:
        assert sentinel.read_text() == 'preserve me\n', label
    else:
        assert not output.exists() and not work.exists(), label
    assert not Path(str(output) + '.manifest.json').exists(), label
    print('PASS:', label, flush=True)


bad_hash = list(base)
bad_hash[1] = '0' * 64
refuse('wrong-digest', bad_hash, 'Input checksum mismatch')

isolated = args.work / 'isolated-builder'
isolated.mkdir()
copy = isolated / 'make-arm-ram-installer.sh'
copy.write_bytes(args.builder.read_bytes())
original = args.builder
args.builder = copy
refuse('missing-iso-helper', base, 'co-located EFI ISO builder is missing')
args.builder = original

with tarfile.open(inputs['kernel_set']['path']) as archive:
    member, = [m for m in archive if Path(m.name).as_posix() == 'boot/kernel/kernel']
    data = bytearray(archive.extractfile(member).read())


def kernel_fixture(label, kernel):
    path = args.work / (label + '.txz')
    # Retain the actual native modules while changing only the selected kernel.
    with tarfile.open(inputs['kernel_set']['path']) as source, tarfile.open(path, 'w:xz') as output:
        for member in source:
            if Path(member.name).as_posix() == 'boot/kernel/kernel':
                member.size = len(kernel)
                output.addfile(member, io.BytesIO(kernel))
            else:
                output.addfile(member, source.extractfile(member) if member.isfile() else None)
    return path


data[18:20] = (62).to_bytes(2, 'little')
wrong_machine = kernel_fixture('wrong-machine', data)
selected = list(base)
selected[2:4] = [str(wrong_machine), digest(wrong_machine)]
refuse('wrong-machine', selected, 'AArch64 ELF64 kernel is required')

selected = list(base)
ordinary_elf = kernel_fixture('ordinary-elf', Path('/usr/bin/true').read_bytes())
selected[2:4] = [str(ordinary_elf), digest(ordinary_elf)]
refuse('ordinary-elf-is-not-kernel', selected, 'FreeBSD 16 kernel is required')

manifest = args.work / 'wrong-abi.json'
manifest.write_text(json.dumps(dict(name='omarchy', version='0-test', origin='x11-wm/omarchy',
    comment='ABI refusal fixture', desc='No payload or scripts', maintainer='qa@example.invalid',
    www='https://example.invalid', prefix='/usr/local', abi='FreeBSD:16:amd64',
    arch='FreeBSD:16:amd64', files={})))
packages = args.work / 'packages'
packages.mkdir()
subprocess.run(['pkg', 'create', '-M', str(manifest), '-o', str(packages)], check=True)
package, = packages.glob('*.pkg')
selected = list(base)
selected[4:6] = [str(package), digest(package)]
refuse('wrong-package-abi', selected, 'Omarchy package for FreeBSD:16:aarch64')


def occupy_output(output, work):
    output.write_text('preserve me\n')
    return output


def occupy_work(output, work):
    work.mkdir()
    marker = work / 'sentinel'
    marker.write_text('preserve me\n')
    return marker


refuse('existing-output', base, 'must not exist', occupy_output)
refuse('existing-work', base, 'must not exist', occupy_work)
print('PASS: all seven native refusal cases; no mounts, installation or output replacement')
