#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Stage owned boot-trace helpers on a complete live root without changing its inode metadata."""
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
MODULES = ('stick.py','boot-medium.py','fat-volume.py','observe-medium.py',
           'capture-medium.py','session-log.py')


def checked_path(root, relative):
    path = root / relative
    for current in [path] + list(path.parents):
        if current == root.parent:
            break
        if current.is_symlink():
            raise ValueError('symlink in live trace staging path')
        if current.exists() and current != path and not current.is_dir():
            raise ValueError('non-directory trace staging parent')
    return path


def stage(root,source=SOURCE):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('regular live root directory required')
    original=root.stat()
    abi=checked_path(root,'usr/local/share/daemonarchy-installer/ABI')
    if abi.is_symlink() or not abi.is_file():
        raise ValueError('regular live-root ABI marker required')
    selected=abi.read_text().strip()
    machines={'FreeBSD:16:amd64':62,'FreeBSD:16:aarch64':183}
    if selected not in machines:
        raise ValueError('supported live-root ABI required')
    for relative in ('usr/local/bin/python3.12','bin/timeout','usr/bin/lockf','usr/sbin/daemon'):
        command=checked_path(root,relative)
        if command.is_symlink() or not command.is_file() or not os.access(command,os.X_OK):
            raise ValueError('live-root trace prerequisite missing: '+relative)
    with (root/'usr/local/bin/python3.12').open('rb') as stream:
        header=stream.read(20)
    if (len(header)!=20 or header[:7]!=b'\x7fELF\x02\x01\x01' or
            struct.unpack_from('<H',header,18)[0]!=machines[selected]):
        raise ValueError('live-root Python ABI mismatch')
    entries=[(source/'tools/boottrace'/name,
              Path('usr/local/libexec/daemonarchy-boottrace')/name) for name in MODULES]
    entries += [(source/'tools/boottrace/daemonarchy_trace',Path('etc/rc.d/daemonarchy_trace')),
                (source/'overlay/usr/local/libexec/daemonarchy-installer/boot-trace',
                 Path('usr/local/libexec/daemonarchy-installer/boot-trace'))]
    # Validate the complete write set before changing the staging tree.
    for src,relative in entries:
        if src.is_symlink() or not src.is_file() or src.stat().st_size>262144:
            raise ValueError('bounded regular trace source required: '+str(src))
        destination=checked_path(root,relative)
        if destination.exists() and not destination.is_file():
            raise ValueError('regular trace staging destination required')
        if destination.exists() and destination.stat().st_nlink != 1:
            raise ValueError('multiply linked trace staging destination')
    records=[]
    for src,relative in entries:
        destination=root/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        data=src.read_bytes()
        # Replace the entry rather than truncating a retained inode. A repeat
        # stage must also work when the previous helper is read-only.
        fd, temporary = tempfile.mkstemp(prefix='.trace-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                os.fchmod(stream.fileno(), 0o555)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        records.append(dict(path=str(relative),sha256=hashlib.sha256(data).hexdigest()))
    after=root.stat()
    if (original.st_uid,original.st_gid,stat.S_IMODE(original.st_mode)) != (
            after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)):
        raise ValueError('live root inode metadata changed')
    return dict(schema='daemonarchy/live-trace-stage@1',files=records,
                root_metadata_preserved=True,runtime_capture_qualified=False)


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: stage-live-trace.py LIVE_ROOT')
    try:
        print(json.dumps(stage(Path(sys.argv[1])),sort_keys=True))
    except (ValueError,OSError) as error:
        raise SystemExit('stage-live-trace: '+str(error))
