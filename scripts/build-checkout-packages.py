#!/usr/bin/env python3
"""Build pkg payloads containing complete Git history for a pinned checkout.

Run once per tree on FreeBSD. Emits KIND.json and packages into --out. A separate
catalogue combines these receipts and is pinned into the installer image.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def build(args):
    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    revision = output('git', '-C', str(repo), 'rev-parse', args.revision + '^{commit}')
    if output('git', '-C', str(repo), 'rev-parse', '--is-shallow-repository') != 'false':
        raise ValueError('Full history required; unshallow the input repository first')
    promisor = subprocess.run(['git', '-C', str(repo), 'config', '--get-regexp', r'remote\..*\.promisor'], capture_output=True, text=True)
    if promisor.returncode == 0:
        raise ValueError('Partial clones are not accepted; provide a complete local repository')
    # ls-tree measures only committed contents, never the worker's local files.
    listing = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-rlz', revision])
    allocated = 0
    for entry in listing.split(b'\0'):
        if entry:
            info, _ = entry.split(b'\t', 1)
            mode, kind, oid, size = info.split()
            if kind != b'blob':
                raise ValueError('Submodules are not supported in checkout packages')
            allocated += ((int(size) + 4095) // 4096) * 4096 + 4096
    version = output('git', '-C', str(repo), 'show', '-s', '--format=%cd', '--date=format:%Y%m%d', revision) + '.g' + revision[:12]
    with tempfile.TemporaryDirectory(prefix='checkout-build-', dir=args.workdir) as temp:
        temp = Path(temp)
        # A clean bare repository prevents credentials, hooks, alternates and
        # unrelated refs/configuration from entering the release payload.
        bare = temp / 'repo.git'
        run('git', 'init', '--bare', str(bare), stdout=subprocess.DEVNULL)
        run('git', '-C', str(bare), '-c', 'pack.threads=1', '-c', 'pack.windowMemory=128m', 'fetch', '--no-tags', str(repo), revision + ':refs/heads/' + args.branch)
        bundle = temp / 'checkout.bundle'
        run('git', '-C', str(bare), '-c', 'pack.threads=1', '-c', 'pack.windowMemory=128m',
            'bundle', 'create', str(bundle), 'refs/heads/' + args.branch)
        run('git', '-C', str(bare), 'bundle', 'verify', str(bundle))
        bundle_size = bundle.stat().st_size
        parts = []
        with bundle.open('rb') as stream:
            index = 0
            while True:
                chunk = stream.read(args.chunk_mib * 1024 * 1024)
                if not chunk:
                    break
                name = f'daemonarchy-{args.kind}-history-{index:03d}'
                rel = f'usr/local/share/daemonarchy/checkouts/{args.kind}/{revision}/part-{index:03d}'
                stage = temp / f'stage-{index}'
                file = stage / rel
                file.parent.mkdir(parents=True)
                file.write_bytes(chunk)
                manifest = dict(name=name, version=version, origin='misc/' + name,
                                comment=f'Daemonarchy {args.kind} full Git history payload {index}',
                                desc='Seed data for daemonarchy-checkouts; working trees are never package-owned.',
                                maintainer='jkh@FreeBSD.org', www=args.remote,
                                prefix='/', abi='FreeBSD:16:amd64', arch='freebsd:16:x86:64',
                                files={'/' + rel: '1'}, annotations={'git_revision': revision})
                mf = temp / 'manifest.json'
                mf.write_text(json.dumps(manifest))
                run('pkg', 'create', '-M', str(mf), '-r', str(stage), '-o', str(out))
                package = out / f'{name}-{version}.pkg'
                if package.stat().st_size >= 2 * 1024**3:
                    raise ValueError('Package exceeds release asset limit')
                parts.append(dict(package=f'{name}-{version}', file='/' + rel,
                                  sha256=digest(file), bytes=len(chunk), download_bytes=package.stat().st_size))
                file.unlink()
                index += 1
        receipt = dict(revision=revision, branch=args.branch, remote=args.remote,
                       bundle_sha256=digest(bundle), bundle_bytes=bundle_size,
                       # Cached pkg, installed chunks, assembled bundle, cloned
                       # object database, working tree and metadata reserve.
                       required_bytes=4 * bundle_size + allocated + 512 * 1024**2,
                       parts=parts)
        (out / f'{args.kind}.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({args.kind: receipt}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', required=True, choices=['ports', 'src'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--remote', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--workdir')
    parser.add_argument('--chunk-mib', type=int, default=512)
    args = parser.parse_args()
    if not 1 <= args.chunk_mib <= 1024:
        parser.error('--chunk-mib must be between 1 and 1024')
    build(args)
