#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Read-only GEOM selection for a correlated v4 boot session; never opens devices."""
import hashlib
import re
import uuid
import xml.etree.ElementTree as ET

MAX_XML = 1024 * 1024
MAX_NODES = 16384
BASIC_DATA = 'ebd0a0a2-b9e5-4433-87c0-68b6b72699c7'


def text(element, name, optional=False):
    children = element.findall(name)
    if optional and not children:
        return None
    if len(children) != 1 or list(children[0]):
        raise ValueError('missing or duplicate GEOM field: ' + name)
    return (children[0].text or '').strip()


def number(element, name):
    value = text(element, name)
    if re.fullmatch(r'0|[1-9][0-9]{0,19}', value) is None or int(value) > 2**64 - 1:
        raise ValueError('invalid GEOM integer: ' + name)
    return int(value)


def canonical_uuid(value):
    if not isinstance(value, str):
        raise ValueError('canonical nonzero UUID required')
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise ValueError('canonical nonzero UUID required') from error
    if str(parsed) != value or parsed.int == 0:
        raise ValueError('canonical nonzero UUID required')
    return value


def reference(element, name, expected=None):
    matches = element.findall(name)
    if len(matches) != 1 or set(matches[0].attrib) != {'ref'}:
        raise ValueError('invalid GEOM reference: ' + name)
    value = matches[0].get('ref')
    if expected is not None and value != expected:
        raise ValueError('GEOM owner reference mismatch')
    return value


def resolve_partition(data, partition_uuid):
    """Select one direct GPT/DISK candidate; this does not admit a write."""
    canonical_uuid(partition_uuid)
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML:
        raise ValueError('bounded GEOM XML required')
    if data.endswith(b'\0'):
        data = data[:-1]
    if b'\0' in data or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('unsafe GEOM XML')
    try:
        mesh = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError('incomplete or malformed GEOM XML') from error
    if mesh.tag != 'mesh':
        raise ValueError('GEOM mesh required')
    elements = list(mesh.iter())
    if len(elements) > MAX_NODES:
        raise ValueError('GEOM node budget exceeded')
    definitions = {}
    for node in elements:
        if 'id' in node.attrib:
            identity = node.get('id')
            if not identity or identity in definitions:
                raise ValueError('duplicate or empty GEOM identity')
            definitions[identity] = node
    for node in elements:
        if 'ref' in node.attrib and node.get('ref') not in definitions:
            raise ValueError('dangling GEOM reference')
    providers, candidates = {}, []
    for klass in mesh.findall('class'):
        if not klass.get('id'):
            raise ValueError('missing GEOM class identity')
        class_name = text(klass, 'name')
        for geom in klass.findall('geom'):
            if not geom.get('id'):
                raise ValueError('missing GEOM geometry identity')
            reference(geom, 'class', klass.get('id'))
            for provider in geom.findall('provider'):
                if not provider.get('id'):
                    raise ValueError('missing GEOM provider identity')
                reference(provider, 'geom', geom.get('id'))
                providers[provider.get('id')] = (class_name, geom, provider)
                raw_uuid = text(provider, 'config/rawuuid', optional=True)
                if raw_uuid is not None and raw_uuid.lower() == partition_uuid:
                    candidates.append((class_name, geom, provider))
    if not candidates:
        raise ValueError('boot partition UUID is missing or ambiguous')

    def parent_of(owner):
        consumers = owner.findall('consumer')
        if len(consumers) != 1 or not consumers[0].get('id'):
            raise ValueError('one boot-medium consumer required')
        reference(consumers[0], 'geom', owner.get('id'))
        parent = providers.get(reference(consumers[0], 'provider'))
        if parent is None:
            raise ValueError('missing parent provider')
        return parent

    resolved = []
    for class_name, geom, provider in candidates:
        if (class_name != 'PART' or text(geom, 'config/scheme') != 'GPT' or
                text(geom, 'config/modified') != 'false'):
            raise ValueError('unmodified GPT partition required')
        state = text(geom, 'config/state')
        if state not in ('OK', 'CORRUPT'):
            raise ValueError('unknown GPT state')
        canonical_uuid(text(provider, 'config/rawuuid'))
        if (text(provider, 'config/rawtype') != BASIC_DATA or
                text(provider, 'config/type') != 'ms-basic-data' or
                text(provider, 'config/label') != 'DATRACE'):
            raise ValueError('selected UUID is not the declared trace partition')
        parent = parent_of(geom)
        if text(geom, 'name') != text(parent[2], 'name'):
            raise ValueError('partition parent name mismatch')
        direct = parent[0] == 'DISK'
        visited = set()
        # GEOM can taste the identical GPT again through an ISO LABEL provider.
        # Collapse only proven zero-offset, whole-provider LABEL aliases.
        while parent[0] == 'LABEL':
            _, label_geom, label = parent
            if label.get('id') in visited or len(visited) >= 8:
                raise ValueError('cyclic or excessive LABEL aliases')
            visited.add(label.get('id'))
            upstream = parent_of(label_geom)
            if (text(label_geom, 'name') != text(upstream[2], 'name') or
                    number(label, 'config/offset') != 0 or
                    number(label, 'config/secoffset') != 0 or
                    number(label, 'mediasize') != number(upstream[2], 'mediasize') or
                    number(label, 'config/length') != number(label, 'mediasize') or
                    number(label, 'sectorsize') != number(upstream[2], 'sectorsize') or
                    number(label, 'config/seclength') * number(label, 'sectorsize') != number(label, 'mediasize')):
                raise ValueError('LABEL is not an identical whole-provider alias')
            parent = upstream
        if parent[0] != 'DISK':
            raise ValueError('direct DISK parent required')
        _, disk_geom, disk = parent
        disk_name = text(disk, 'name')
        if (re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}', disk_name) is None or
                text(disk_geom, 'name') != disk_name or disk_geom.findall('consumer')):
            raise ValueError('unsafe or non-root DISK identity')
        index, entries = number(provider, 'config/index'), number(geom, 'config/entries')
        if (not 1 <= index <= entries <= 4096 or
                text(provider, 'name') != text(geom, 'name') + 'p' + str(index)):
            raise ValueError('partition and disk identity mismatch')
        sector = number(provider, 'sectorsize')
        if sector != 512 or number(disk, 'sectorsize') != sector:
            raise ValueError('unsupported boot-medium sector size')
        start, end = number(provider, 'config/start'), number(provider, 'config/end')
        first, last = number(geom, 'config/first'), number(geom, 'config/last')
        size, disk_size = number(provider, 'mediasize'), number(disk, 'mediasize')
        if (not 34 <= first <= start <= end <= last <= disk_size // sector - 34 or
                disk_size % sector or size != (end-start+1) * sector or
                number(provider, 'config/offset') != start * sector or
                number(provider, 'config/length') != size):
            raise ValueError('inconsistent GPT/provider geometry')
        key = (disk.get('id'), index, start, end, first, last, entries, state, sector, size, disk_size)
        value = dict(schema='daemonarchy/boot-medium-selection@1',
                     device='/dev/' + disk_name + 'p' + str(index), disk='/dev/' + disk_name,
                     partition_uuid=partition_uuid, start_lba=start, sectors=end-start+1,
                     sector_bytes=sector, disk_bytes=disk_size, gpt_state=state,
                     geom_sha256=hashlib.sha256(data).hexdigest(), read_only=True,
                     writes_admitted=False, raw_gpt_and_fat_validation_required=True)
        resolved.append((key, value, direct))
    if len({item[0] for item in resolved}) != 1:
        raise ValueError('boot partition UUID is missing or ambiguous')
    direct = [item[1] for item in resolved if item[2]]
    if len(direct) != 1:
        raise ValueError('one canonical direct GPT provider required')
    return dict(direct[0], equivalent_aliases=len(resolved)-1)


def identity(record):
    if not isinstance(record, dict):
        raise ValueError('normal record identity required')
    if (record.get('identity') != 'declared-archive' or
            record.get('early_kernel_backend') != 'not-enabled'):
        raise ValueError('declared normal identity required')
    selected = {}
    for key in ('image_id', 'archive_sha256', 'trace_partition', 'session',
                'boot_nonce', 'boot_identity'):
        value = record.get(key)
        if not isinstance(value, str):
            raise ValueError('missing normal identity: ' + key)
        selected[key] = value
    canonical_uuid(selected['image_id'])
    canonical_uuid(selected['trace_partition'])
    if (re.fullmatch('[0-9a-f]{64}', selected['archive_sha256']) is None or
            re.fullmatch('[0-9]{4}', selected['session']) is None or
            not 1 <= int(selected['session']) <= 32 or
            re.fullmatch('[0-9a-f]{64}', selected['boot_nonce']) is None or
            len(set(bytes.fromhex(selected['boot_nonce']))) < 2 or
            selected['boot_identity'] != 'firmware-rng'):
        raise ValueError('fresh correlated v4 identity required')
    return selected


def bind_session(data, kenv, record):
    """Correlate a fresh topology snapshot without granting raw device access."""
    if (not isinstance(kenv, dict) or not isinstance(record, dict) or
            record.get('schema') != 'daemonarchy/normal-boot-trace@4' or
            record.get('phase') != 'loader-ready'):
        raise ValueError('v4 parent and kernel environment required')
    selected = identity(record)
    selection = resolve_partition(data, selected['trace_partition'])
    later = record.get('pre_exit', {})
    if (not isinstance(later, dict) or later.get('status') != 'recorded' or
            identity(later.get('record')) != selected or
            later['record'].get('schema') != 'daemonarchy/normal-boot-trace@4' or
            later['record'].get('phase') != 'pre-exit'):
        raise ValueError('matching completed pre-exit checkpoint required')
    expected = {'daemonarchy.trace.partition': selected['trace_partition'],
                'daemonarchy.trace.session': selected['image_id'] + '-' + selected['session'],
                'daemonarchy.trace.boot_nonce': selected['boot_nonce'],
                'daemonarchy.trace.capture': 'saved'}
    if any(kenv.get(key) != value for key, value in expected.items()):
        raise ValueError('kernel/session/partition identity mismatch')
    return dict(selection, session=expected['daemonarchy.trace.session'],
                boot_nonce_sha256=hashlib.sha256(selected['boot_nonce'].encode()).hexdigest(),
                archive_sha256=selected['archive_sha256'], session_correlated=True)


def validate_gpt(read_at, selection):
    """Validate bounded raw GPT observations. read_at(offset, length) is read-only."""
    import struct
    import zlib

    sector = selection['sector_bytes']
    size = selection['disk_bytes']
    if sector != 512 or size % sector or size < 68 * sector:
        raise ValueError('unsupported raw disk geometry')
    limit = size // sector

    def read(offset, length):
        if offset < 0 or length < 0 or offset + length > size:
            raise ValueError('GPT read outside disk')
        data = read_at(offset, length)
        if not isinstance(data, bytes) or len(data) != length:
            raise ValueError('short GPT read')
        return data

    def header(lba):
        raw = read(lba * sector, sector)
        signature, revision, length, checksum, reserved = struct.unpack_from('<8sIIII', raw)
        if signature != b'EFI PART' or revision != 0x10000 or length != 92 or reserved:
            raise ValueError('unsupported GPT header')
        checked = bytearray(raw[:length])
        checked[16:20] = bytes(4)
        if zlib.crc32(checked) != checksum:
            raise ValueError('GPT header checksum mismatch')
        current, backup, first, last = struct.unpack_from('<QQQQ', raw, 24)
        disk_guid = str(uuid.UUID(bytes_le=raw[56:72]))
        canonical_uuid(disk_guid)
        table_lba, count, stride, table_crc = struct.unpack_from('<QIII', raw, 72)
        if (current != lba or not 1 <= backup < limit or backup == current or
                not 34 <= first <= last < limit - 1 or
                not 1 <= count <= 4096 or stride != 128):
            raise ValueError('invalid or unsupported GPT geometry')
        table_sectors = (count * stride + sector - 1) // sector
        if (table_lba < 2 or table_lba + table_sectors > limit or
                not (table_lba + table_sectors <= first or table_lba > last) or
                table_lba <= current < table_lba + table_sectors or
                table_lba <= backup < table_lba + table_sectors):
            raise ValueError('GPT table overlaps usable space or headers')
        table = read(table_lba * sector, count * stride)
        if zlib.crc32(table) != table_crc:
            raise ValueError('GPT table checksum mismatch')
        return dict(current=current, backup=backup, first=first, last=last,
                    disk_guid=disk_guid, table_lba=table_lba,
                    count=count, table_sectors=table_sectors, table=table)

    primary = header(1)
    # Expanded USB media may retain the original backup location. Validate that
    # explicit pair without repairing it or claiming writable-device admission.
    backup = header(primary['backup'])
    if (backup['backup'] != 1 or
            any(primary[key] != backup[key] for key in
                ('first', 'last', 'disk_guid', 'count', 'table')) or
            primary['table_lba'] + primary['table_sectors'] > primary['first'] or
            backup['table_lba'] <= primary['last'] or
            backup['table_lba'] + backup['table_sectors'] > backup['current']):
        raise ValueError('GPT copies disagree or overlap')
    partitions, guids, selected = [], set(), []
    for index in range(primary['count']):
        entry = primary['table'][index*128:(index+1)*128]
        if entry[:16] == bytes(16):
            if entry != bytes(128):
                raise ValueError('nonempty unused GPT entry')
            continue
        type_guid = str(uuid.UUID(bytes_le=entry[:16]))
        part_guid = str(uuid.UUID(bytes_le=entry[16:32]))
        canonical_uuid(part_guid)
        if part_guid in guids:
            raise ValueError('duplicate GPT partition UUID')
        guids.add(part_guid)
        first, last, attributes = struct.unpack_from('<QQQ', entry, 32)
        if not primary['first'] <= first <= last <= primary['last']:
            raise ValueError('partition outside GPT usable bounds')
        if any(first <= prior_last and last >= prior_first for prior_first, prior_last in partitions):
            raise ValueError('overlapping GPT partitions')
        partitions.append((first, last))
        if part_guid == selection['partition_uuid']:
            try:
                name = entry[56:128].decode('utf-16-le')
            except UnicodeDecodeError as error:
                raise ValueError('invalid GPT trace name') from error
            if (name != 'DATRACE'.ljust(36, '\0') or type_guid != BASIC_DATA or
                    attributes != 0 or first != selection['start_lba'] or
                    last - first + 1 != selection['sectors'] or
                    not selection['device'].endswith('p' + str(index+1))):
                raise ValueError('raw GPT and selected provider disagree')
            selected.append(index+1)
    if len(selected) != 1:
        raise ValueError('raw GPT trace identity missing or ambiguous')
    return dict(schema='daemonarchy/boot-medium-gpt-observation@1',
                partition_uuid=selection['partition_uuid'], partition_index=selected[0],
                disk_guid=primary['disk_guid'], backup_lba=primary['backup'],
                backup_at_disk_end=primary['backup'] == limit-1,
                table_sha256=hashlib.sha256(primary['table']).hexdigest(),
                read_only=True, writes_admitted=False,
                fat_and_map_validation_required=True)


def require_idle(data, selection, own_reader=False):
    """Refuse active consumers anywhere below the physical boot disk."""
    current = resolve_partition(data, selection['partition_uuid'])
    for key in ('device','disk','partition_uuid','start_lba','sectors','sector_bytes','disk_bytes','gpt_state'):
        if current[key] != selection[key]:
            raise ValueError('boot-medium topology changed')
    mesh = ET.fromstring(data.rstrip(b'\0'))
    geoms, providers = [], {}
    for klass in mesh.findall('class'):
        for geom in klass.findall('geom'):
            geoms.append((text(klass,'name'),geom))
            for provider in geom.findall('provider'):
                providers[provider.get('id')] = provider
    disks = [p for kind,g in geoms if kind == 'DISK' for p in g.findall('provider')
             if '/dev/'+text(p,'name') == selection['disk']]
    if len(disks) != 1:
        raise ValueError('canonical physical disk missing')
    disk_id = disks[0].get('id')
    reachable = {disk_id}
    for _ in range(len(geoms)+1):
        added = {p.get('id') for _,g in geoms
                 if any(reference(c,'provider') in reachable for c in g.findall('consumer'))
                 for p in g.findall('provider')}
        if added <= reachable:
            break
        reachable |= added
    else:
        raise ValueError('unbounded GEOM descendants')
    expected_disk_mode = 'r1w0e0' if own_reader else 'r0w0e0'
    for identity in reachable:
        expected = expected_disk_mode if identity == disk_id else 'r0w0e0'
        if text(providers[identity],'mode') != expected:
            raise ValueError('boot disk or descendant provider is busy')
    for kind,geom in geoms:
        for consumer in geom.findall('consumer'):
            if reference(consumer,'provider') not in reachable:
                continue
            own = (own_reader and kind == 'DEV' and
                   '/dev/'+text(geom,'name') == selection['disk'])
            if text(consumer,'mode') != ('r1w0e0' if own else 'r0w0e0'):
                raise ValueError('boot disk has an active consumer')
    return current


if __name__ == '__main__':
    raise SystemExit('Import this read-only policy module; device I/O is not implemented.')
