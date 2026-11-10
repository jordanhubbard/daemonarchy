#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Restore the archive root inode without inheriting staging permissions."""
import json
import os
from pathlib import Path
import stat
import sys
import tarfile


def restore(archive, root):
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('Regular live-root archive required')
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Regular live-root staging directory required')
    root_entry = None
    # Select the final explicit root entry, including an appended repair header.
    with tarfile.open(archive, 'r|*') as source:
        for entry in source:
            if entry.name.rstrip('/') == '.':
                if not entry.isdir():
                    raise ValueError('Live-root archive root entry must be a directory')
                root_entry = entry
    if root_entry is None:
        raise ValueError('Explicit live-root archive directory entry is required')
    if root_entry.uid != 0 or root_entry.gid < 0 or root_entry.mode not in (0o555, 0o755):
        raise ValueError('Live-root inode must be root-owned and mode 0555 or 0755')
    os.chown(root, root_entry.uid, root_entry.gid)
    os.chmod(root, root_entry.mode)
    current = root.stat()
    if (current.st_uid, current.st_gid, stat.S_IMODE(current.st_mode)) != (
            root_entry.uid, root_entry.gid, root_entry.mode):
        raise ValueError('Live-root metadata restoration failed')
    return dict(uid=current.st_uid, gid=current.st_gid,
                mode=format(stat.S_IMODE(current.st_mode), '04o'))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: live-root-metadata.py world.tar extracted-root')
    print(json.dumps(restore(Path(sys.argv[1]), Path(sys.argv[2])), sort_keys=True))
