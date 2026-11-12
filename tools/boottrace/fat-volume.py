#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Bounded read-only FAT32 allocation and trace-map observation."""
import hashlib
import re
import struct

MAX_READ = 16 * 1024 * 1024
MAX_CLUSTERS = 1024 * 1024


def validate_fat(read_at, selection, selected_path=None):
    """Observe one selected partition; does not open devices or admit writes."""
    start, size = selection['start_lba'] * 512, selection['sectors'] * 512
    budget = MAX_READ

    def read(offset, length):
        nonlocal budget
        if offset < 0 or length < 0 or offset + length > size or length > budget:
            raise ValueError('FAT read outside partition or observation budget')
        budget -= length
        data = read_at(start + offset, length)
        if not isinstance(data, bytes) or len(data) != length:
            raise ValueError('short FAT read')
        return data

    boot = read(0, 512)
    bps, spc, reserved, copies = struct.unpack_from('<HBHB', boot, 11)
    total, fatsz, flags, version, root, info, backup = struct.unpack_from('<IIHHIHH', boot, 32)
    if (boot[510:512] != b'\x55\xaa' or boot[82:90] != b'FAT32   ' or
            bps != 512 or spc not in (1,2,4,8,16,32,64,128) or
            reserved < 3 or copies != 2 or not fatsz or total * bps != size or
            boot[17:21] != bytes(4) or boot[22:24] != bytes(2) or
            flags != 0 or version != 0 or not 0 < backup < reserved or
            not 0 < info < reserved or backup == info):
        raise ValueError('unsupported FAT32 geometry')
    data_off = (reserved + copies * fatsz) * bps
    cluster_bytes = bps * spc
    count = (size - data_off) // cluster_bytes
    if not 65525 <= count <= MAX_CLUSTERS or fatsz * bps < (count+2) * 4:
        raise ValueError('invalid or excessive FAT32 cluster count')
    if read(backup * bps, bps) != boot:
        raise ValueError('FAT boot-sector copies disagree')
    fat = read(reserved*bps, fatsz*bps)
    if read((reserved+fatsz)*bps, fatsz*bps) != fat:
        raise ValueError('FAT allocation copies disagree')

    def entry(c):
        return struct.unpack_from('<I', fat, c*4)[0] & 0x0fffffff

    if entry(0) != 0x0fffff00 | boot[21] or entry(1) != 0x0fffffff:
        raise ValueError('FAT dirty, error-marked or invalid reserved entries')
    owners, files = {}, {}

    def chain(first, owner):
        result, c = [], first
        while True:
            if not 2 <= c < count + 2 or c in owners:
                raise ValueError('FAT cycle, cross-link or invalid cluster')
            owners[c] = owner
            result.append(c)
            following = entry(c)
            if following >= 0x0ffffff8:
                return result
            c = following

    def offset(c):
        return data_off + (c-2) * cluster_bytes

    queue = [('', root, root)]
    entries_seen = 0
    while queue:
        path, first, parent = queue.pop()
        clusters = chain(first, path or '/')
        directory = b''.join(read(offset(c), cluster_bytes) for c in clusters)
        names, long_entries = set(), []
        for at in range(0, len(directory), 32):
            e = directory[at:at+32]
            entries_seen += 1
            if entries_seen > 16384:
                raise ValueError('FAT directory entry budget exceeded')
            if e[0] == 0:
                if long_entries:
                    raise ValueError('incomplete FAT long name')
                break
            if e[0] == 0xe5:
                long_entries = []
                continue
            if e[11] == 0x0f:
                long_entries.append(e)
                if len(long_entries) > 20:
                    raise ValueError('excessive FAT long name')
                continue
            if long_entries:
                checksum = 0
                for byte in e[:11]:
                    checksum = (((checksum & 1) << 7) + (checksum >> 1) + byte) & 255
                for i, part in enumerate(long_entries):
                    ordinal = len(long_entries)-i
                    if (part[0] != ordinal | (0x40 if i == 0 else 0) or
                            part[12] != 0 or part[13] != checksum or part[26:28] != bytes(2)):
                        raise ValueError('invalid FAT long name sequence')
                long_entries = []
            try:
                name = e[:8].decode('ascii').rstrip()
                extension = e[8:11].decode('ascii').rstrip()
            except UnicodeDecodeError as error:
                raise ValueError('unsupported FAT short name') from error
            name += '.' + extension if extension else ''
            if name in names:
                raise ValueError('duplicate FAT short name')
            names.add(name)
            if e[11] & 8:
                if path or e[11] & ~0x28:
                    raise ValueError('invalid FAT volume label')
                continue
            cluster = (struct.unpack_from('<H',e,20)[0] << 16) | struct.unpack_from('<H',e,26)[0]
            length = struct.unpack_from('<I',e,28)[0]
            if name in ('.','..'):
                if not path or e[11] != 16 or length or cluster != (first if name == '.' else (0 if parent == root else parent)):
                    raise ValueError('invalid FAT parent directory')
                continue
            if not re.fullmatch(r'[A-Z0-9_~!-]{1,8}(?:\.[A-Z0-9_~!-]{1,3})?',name):
                raise ValueError('unsupported FAT short name')
            child = path + '/' + name if path else name
            if e[11] & 16:
                if length or len(queue) >= 1024 or path.count('/') >= 8:
                    raise ValueError('invalid or excessive FAT directory')
                queue.append((child,cluster,first))
            else:
                allocated = chain(cluster,child) if length else []
                if not length and cluster or len(allocated) != (length+cluster_bytes-1)//cluster_bytes:
                    raise ValueError('FAT file allocation does not match size')
                files[child] = (allocated,length)
        if long_entries:
            raise ValueError('incomplete FAT long name')
    for c in range(2,count+2):
        if entry(c) and c not in owners:
            raise ValueError('unowned FAT allocation')

    def extent(path):
        if path not in files:
            raise ValueError('required FAT file missing: '+path)
        clusters,length = files[path]
        if not clusters or clusters != list(range(clusters[0],clusters[0]+len(clusters))):
            raise ValueError('trace-map file must be preallocated and contiguous')
        return offset(clusters[0]),length

    expected = {'STATE.TXT':512}
    expected.update({'TRACES/%04d.TXT'%i:16384 for i in range(1,201)})
    expected.update({'NORMAL/%04d.TXT'%i:16384 for i in range(1,33)})
    for path in files:
        if re.fullmatch(r'ACPI/(?:[A-Z0-9]{4}\.BIN|INDEX\.TXT)',path):
            expected[path] = files[path][1]
    observed = {}
    for path,length in expected.items():
        off,actual = extent(path)
        if actual != length or not 0 < length <= 16384 or off % 512:
            raise ValueError('wrong trace-map file size')
        observed[path] = (off,length)
    # The producer orders STATE, TRACES, ACPI, NORMAL.
    ordered = ['STATE.TXT'] + sorted(p for p in expected if p.startswith('TRACES/'))
    ordered += sorted(p for p in expected if p.startswith('ACPI/'))
    ordered += sorted(p for p in expected if p.startswith('NORMAL/'))
    body = 'Daemonarchy DATRACE block map v1\npart_lba=%d\npart_sectors=%d\ndata_off=%d\n' % (selection['start_lba'],selection['sectors'],data_off)
    body += ''.join('file=%s off=%d size=%d\n' % (p,*observed[p]) for p in ordered)
    checksum = 2166136261
    for byte in body.encode():
        checksum = ((checksum ^ byte) * 16777619) & 0xffffffff
    expected_map = (body+'sum=%08x\n'%checksum).encode()
    map_off,map_size = extent('SLOTS.MAP')
    if map_size != 16384 or read(map_off,map_size) != expected_map.ljust(map_size,b'\n'):
        raise ValueError('trace map does not match actual FAT allocations')
    selected = {'selected_extent': extent(selected_path), 'identity_extent': extent('INSTALL.ID')} if selected_path is not None else {}
    if selected_path is not None:
        selected['log_extents'] = None
        if any(path.startswith('USPACE/') for path in files):
            for session in range(1,33):
                for extension in ('KRN','INS'):
                    _,length = extent('USPACE/%04d.%s'%(session,extension))
                    if length != 1<<20:
                        raise ValueError('wrong preallocated userspace log size')
            session = selected_path.rsplit('/',1)[-1].split('.')[0]
            if re.fullmatch('[0-9]{4}',session) is None:
                raise ValueError('invalid userspace log session')
            selected['log_extents'] = {
                kind:extent('USPACE/'+session+'.'+extension)
                for kind,extension in (('kernel-console','KRN'),('installer-events','INS'))}
    return dict(**selected, schema='daemonarchy/boot-medium-fat-observation@1',
                map_sha256=hashlib.sha256(expected_map).hexdigest(),
                fat_sha256=hashlib.sha256(fat).hexdigest(),
                mapped_files=len(observed), allocated_clusters=len(owners),
                read_only=True,writes_admitted=False)
