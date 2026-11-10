#!/usr/bin/env python3
"""Prepare bounded XZ parts of immutable media; no release or boot admission."""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

SCHEMA = 'daemonarchy/split-media@1'
ASSET_LIMIT = 2 << 30
PART_LIMIT = 1 << 30
MAX_PARTS = 64
MANIFEST_LIMIT = 1 << 20
MEM_LIMIT = 128 << 20
BUFFER = 256 << 10
HEX = re.compile(r'[0-9a-f]{64}\Z')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(?:iso|img)\Z')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected), 'unexpected or missing manifest fields')


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'invalid byte count')


def digest(value):
    require(isinstance(value, str) and HEX.fullmatch(value), 'invalid SHA-256')


def regular(path):
    require(stat.S_ISREG(path.lstat().st_mode), 'media inputs must be regular files')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    stream = os.fdopen(fd, 'rb')
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        stream.close()
        raise ValueError('media inputs must be regular files')
    return stream


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate manifest key')
        result[key] = value
    return result


def part_name(name, index):
    return f'{name}.part{index:04d}.xz'


def decode(stream, limit):
    """Exactly one XZ stream, bounded dictionary and bounded output chunks."""
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=MEM_LIMIT)
    total = 0
    while not decoder.eof:
        data = stream.read(BUFFER) if decoder.needs_input else b''
        require(data or not decoder.needs_input, 'truncated XZ stream')
        block = decoder.decompress(data, max_length=min(BUFFER, limit - total + 1))
        total += len(block)
        require(total <= limit, 'expanded XZ payload exceeds declared size')
        if block:
            yield block
    require(not decoder.unused_data and not stream.read(1), 'trailing or concatenated XZ data')


def load_manifest(path, expected):
    digest(expected)
    with regular(path) as stream:
        require(os.fstat(stream.fileno()).st_size <= MANIFEST_LIMIT, 'compressed manifest too large')
        raw = stream.read(MANIFEST_LIMIT + 1)
    require(hashlib.sha256(raw).hexdigest() == expected, 'manifest SHA-256 mismatch')
    # BytesIO keeps the separately pinned metadata read bounded.
    import io
    decoded = b''.join(decode(io.BytesIO(raw), MANIFEST_LIMIT))
    record = json.loads(decoded, object_pairs_hook=unique)
    keys(record, ['schema', 'image', 'part_raw_bytes', 'parts'])
    require(record['schema'] == SCHEMA, 'unsupported split-media schema')
    image = record['image']
    keys(image, ['name', 'bytes', 'sha256'])
    require(isinstance(image['name'], str) and NAME.fullmatch(image['name']), 'unsafe image name')
    integer(image['bytes'], 1, MAX_PARTS * PART_LIMIT)
    digest(image['sha256'])
    require(path.name == image['name'] + '.parts.json.xz', 'manifest filename mismatch')
    width = record['part_raw_bytes']
    integer(width, 1, PART_LIMIT)
    count = (image['bytes'] + width - 1) // width
    require(isinstance(record['parts'], list) and 1 <= count <= MAX_PARTS
            and len(record['parts']) == count, 'incorrect part count')
    for index, part in enumerate(record['parts'], 1):
        keys(part, ['name', 'bytes', 'sha256', 'raw_bytes', 'raw_sha256'])
        require(part['name'] == part_name(image['name'], index), 'noncanonical or reordered part name')
        integer(part['bytes'], 1, ASSET_LIMIT - 1)
        digest(part['sha256'])
        digest(part['raw_sha256'])
        require(type(part['raw_bytes']) is int
                and part['raw_bytes'] == min(width, image['bytes'] - (index - 1) * width), 'incorrect part geometry')
    checksum = path.with_name(path.name + '.sha256')
    with regular(checksum) as stream:
        require(stream.read(512) == f'{expected}  {path.name}\n'.encode(), 'manifest checksum sidecar mismatch')
    expected_names = {p['name'] for p in record['parts']} | {path.name, checksum.name}
    actual_names = {p.name for p in path.parent.iterdir() if p.name.startswith(image['name'] + '.part')}
    require(actual_names == expected_names, 'missing or unexpected media part files')
    return record


class HashingReader:
    def __init__(self, stream):
        self.stream, self.hash, self.bytes = stream, hashlib.sha256(), 0

    def read(self, amount):
        block = self.stream.read(amount)
        self.hash.update(block)
        self.bytes += len(block)
        return block


def stream_record(directory, record, destination=None):
    image_hash = hashlib.sha256()
    for part in record['parts']:
        raw_hash = hashlib.sha256()
        amount = 0
        with regular(directory / part['name']) as stream:
            require(os.fstat(stream.fileno()).st_size == part['bytes'], 'compressed part size mismatch')
            reader = HashingReader(stream)
            for block in decode(reader, part['raw_bytes']):
                amount += len(block)
                raw_hash.update(block)
                image_hash.update(block)
                if destination is not None:
                    destination.write(block)
            require(reader.bytes == part['bytes'] and reader.hash.hexdigest() == part['sha256'],
                    'compressed part SHA-256 mismatch')
        require(amount == part['raw_bytes'] and raw_hash.hexdigest() == part['raw_sha256'], 'raw part identity mismatch')
    require(image_hash.hexdigest() == record['image']['sha256'], 'complete raw-image SHA-256 mismatch')
    return record


def stream_image(path, expected, destination=None):
    return stream_record(path.parent, load_manifest(path, expected), destination)


def pack(image, expected, output, width=PART_LIMIT):
    digest(expected)
    require(NAME.fullmatch(image.name), 'unsafe image name')
    integer(width, 1, PART_LIMIT)
    with regular(image) as source:
        before = os.fstat(source.fileno())
        require(0 < before.st_size <= width * MAX_PARTS, 'image exceeds bounded part count')
        output.mkdir(mode=0o700)  # Exclusive reservation; never replace existing artifacts.
        record = {'schema': SCHEMA, 'image': {'name': image.name, 'bytes': before.st_size, 'sha256': expected},
                  'part_raw_bytes': width, 'parts': []}
        overall = hashlib.sha256()
        for index in range(1, (before.st_size + width - 1) // width + 1):
            name = part_name(image.name, index)
            raw_hash, compressed_hash = hashlib.sha256(), hashlib.sha256()
            amount = min(width, before.st_size - (index - 1) * width)
            compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, check=lzma.CHECK_SHA256, preset=6)
            with (output / name).open('xb') as target:
                remaining = amount
                while remaining:
                    block = source.read(min(BUFFER, remaining))
                    require(block, 'source image truncated while packing')
                    remaining -= len(block)
                    raw_hash.update(block)
                    overall.update(block)
                    compressed = compressor.compress(block)
                    target.write(compressed)
                    compressed_hash.update(compressed)
                compressed = compressor.flush()
                target.write(compressed)
                compressed_hash.update(compressed)
                target.flush()
                os.fsync(target.fileno())
            size = (output / name).stat().st_size
            require(size < ASSET_LIMIT, 'compressed part exceeds existing asset limit')
            record['parts'].append({'name': name, 'bytes': size, 'sha256': compressed_hash.hexdigest(),
                                    'raw_bytes': amount, 'raw_sha256': raw_hash.hexdigest()})
        after = os.fstat(source.fileno())
        require(not source.read(1) and (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
                'source image changed while packing')
        require(overall.hexdigest() == expected, 'source image SHA-256 mismatch')
    # Decode and verify every produced part before writing an admissible manifest.
    stream_record(output, record)
    raw = (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode()
    require(len(raw) <= MANIFEST_LIMIT, 'manifest too large')
    compressed = lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_SHA256, preset=6)
    manifest = output / (image.name + '.parts.json.xz')
    with manifest.open('xb') as target:
        target.write(compressed)
        target.flush()
        os.fsync(target.fileno())
    manifest_hash = hashlib.sha256(compressed).hexdigest()
    manifest.with_name(manifest.name + '.sha256').write_text(f'{manifest_hash}  {manifest.name}\n')
    load_manifest(manifest, manifest_hash)
    return {'manifest': manifest.name, 'sha256': manifest_hash, 'image': record['image'], 'parts': record['parts']}


def join(path, expected, output):
    require(not output.exists() and not output.is_symlink(), 'output already exists')
    with tempfile.NamedTemporaryFile(prefix='.' + output.name + '.', dir=output.parent, delete=False) as target:
        temporary = Path(target.name)
        # Failure retains a private partial file; never publish an unchecked image.
        record = stream_image(path, expected, target)
        target.flush()
        os.fsync(target.fileno())
    os.link(temporary, output)  # Atomic, exclusive final name, even if another writer races.
    temporary.unlink()
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    create = sub.add_parser('pack')
    create.add_argument('image', type=Path)
    create.add_argument('--sha256', required=True, help='trusted complete raw-image SHA-256')
    create.add_argument('--out', required=True, type=Path)
    create.add_argument('--part-bytes', type=int, default=PART_LIMIT)
    for name in ['verify', 'join']:
        command = sub.add_parser(name)
        command.add_argument('manifest', type=Path)
        command.add_argument('--sha256', required=True, help='trusted compressed manifest SHA-256')
        if name == 'join':
            command.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'pack':
            result = pack(args.image, args.sha256, args.out, args.part_bytes)
        elif args.operation == 'join':
            result = join(args.manifest, args.sha256, args.out)
        else:
            result = stream_image(args.manifest, args.sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, lzma.LZMAError) as exc:
        print(f'split-media: {exc}; incomplete outputs are retained and are not admitted media', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
