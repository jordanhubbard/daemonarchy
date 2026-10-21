#!/usr/bin/env python3
"""Stage an exact, opt-in live-image loader; never alter installer sets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


def checked_bundle(bundle):
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError('test loader bundle must be a nonsymlink directory')
    manifest = bundle / 'selection.json'
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 16384:
        raise ValueError('missing or invalid test loader selection')
    selection = json.loads(manifest.read_text())
    if (not isinstance(selection, dict)
            or selection.get('schema') != 'daemonarchy/test-loader@1'
            or selection.get('scope') != 'live-image-only'
            or not re.fullmatch(r'[0-9a-f]{40}', selection.get('source_revision', ''))
            or set(selection.get('files', {})) != {'loader.efi', 'loader.lua'}):
        raise ValueError('invalid test loader selection schema or scope')
    payloads = {}
    for name, identity in selection['files'].items():
        path = bundle / name
        limit = 4 * 1024 * 1024 if name == 'loader.efi' else 256 * 1024
        if (path.is_symlink() or not path.is_file()
                or not 0 < path.stat().st_size <= limit):
            raise ValueError('invalid test loader file: ' + name)
        data = path.read_bytes()
        if identity != {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}:
            raise ValueError('test loader identity mismatch: ' + name)
        payloads[name] = data
    return selection, payloads


def prepare(bundle, destination):
    selection, payloads = checked_bundle(bundle)
    destination.mkdir(mode=0o700)  # A fresh path is required; preserve failed attempts.
    for name, data in payloads.items():
        (destination / name).write_bytes(data)
    (destination / 'selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    shutil.copyfile(__file__, destination / 'install.py')


def install(bundle, root):
    selection, payloads = checked_bundle(bundle)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('live root must be an existing nonsymlink directory')
    # Signed maintenance can replace the loader. Refuse either ordering.
    if (root / 'usr/local/share/daemonarchy-installer/secureboot').exists():
        raise ValueError('test loader cannot be combined with a Secure Boot bundle')
    destinations = {'loader.efi': root / 'boot/loader.efi',
                    'loader.lua': root / 'boot/lua/loader.lua'}
    for path in destinations.values():
        if path.is_symlink() or not path.is_file():
            raise ValueError('expected regular live boot file: ' + str(path))
        if any(parent.is_symlink() for parent in path.parents
               if parent == root or root in parent.parents):
            raise ValueError('symlink in live boot path')
    # All inputs and destinations are checked before changing either boot file.
    for name, path in destinations.items():
        # Image roots may share hardlinks with a cached jail. Replace the inode
        # rather than writing through it, preserving the original boot mode.
        descriptor, temporary = tempfile.mkstemp(prefix='.test-loader-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(payloads[name])
                os.fchmod(stream.fileno(), path.stat().st_mode & 0o777)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(json.dumps({'test_loader': selection, 'debug_enabled': False}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    for name, target in [('prepare', '--destination'), ('install', '--root')]:
        command = sub.add_parser(name)
        command.add_argument('--bundle', required=True, type=Path)
        command.add_argument(target, required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.operation == 'prepare':
            prepare(args.bundle, args.destination)
        else:
            install(args.bundle, args.root)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('test loader refused: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
