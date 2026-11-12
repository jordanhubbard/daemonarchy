#!/usr/bin/env python3
"""Independently inspect pinned packed ARM media; static identity, no runtime admission."""
import argparse
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import re
import stat
import subprocess
import sys
import zlib


def inspect(image, expected, version):
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("trusted raw SHA-256 and X.Y.Z installer version required")
    before = image.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("regular nonsymlink image required")
    spec = importlib.util.spec_from_file_location("packed_master_arm", Path(__file__).with_name("assemble-arm-media.py"))
    assembler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(assembler)
    if assembler.digest(image) != expected:
        raise ValueError("raw image differs from its trusted pin")
    identities = assembler.inspect_installer(image, 'bsdtar', 'mtype', expected_version=version)
    if 'packed_root' not in identities:
        raise ValueError("packed RAM-root installer required")
    after = image.lstat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or assembler.digest(image) != expected):
        raise ValueError("raw image changed during inspection")
    return dict(schema='daemonarchy/packed-installer-inspection@1',
                image=dict(bytes=before.st_size, sha256=expected), installer_version=version,
                identities=identities, static_content=True, native_python_import=False,
                boot_install_desktop_hardware_qualified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.image, args.sha256, args.version), sort_keys=True))
    except (OSError, ValueError, subprocess.SubprocessError, lzma.LZMAError, zlib.error) as exc:
        print(f'check-packed-installer: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
