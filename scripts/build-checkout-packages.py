#!/usr/bin/env python3
"""Build pkg payloads containing a shallow Git working tree for a pinned checkout.

Run once per tree on FreeBSD. Emits KIND.json and packages into --out. A separate
catalogue combines these receipts and is pinned into the installer image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tarfile
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
    if (out / f'{args.kind}.json').exists():
        raise ValueError('Receipt already exists; use a fresh output directory for a new build')
    revision = output('git', '-C', str(repo), 'rev-parse', args.revision + '^{commit}')
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
        # Fetch only the selected ancestry into an empty, template-free repo.
        # Never copy worker config, hooks, credentials, reflogs or alternates.
        checkout = temp / 'checkout'
        template = temp / 'empty-template'
        template.mkdir()
        run('git', 'init', '--template=' + str(template), str(checkout), stdout=subprocess.DEVNULL)
        run('git', '-C', str(checkout), '-c', 'pack.threads=1', '-c', 'pack.windowMemory=128m',
            'fetch', '--depth=' + str(args.depth), '--no-tags', str(repo), revision)
        run('git', '-C', str(checkout), 'checkout', '-b', args.branch, 'FETCH_HEAD')
        run('git', '-C', str(checkout), 'remote', 'add', 'origin', args.remote)
        run('git', '-C', str(checkout), 'config', 'remote.origin.fetch', '+refs/heads/' + args.branch + ':refs/remotes/origin/' + args.branch)
        run('git', '-C', str(checkout), 'config', 'branch.' + args.branch + '.remote', 'origin')
        run('git', '-C', str(checkout), 'config', 'branch.' + args.branch + '.merge', 'refs/heads/' + args.branch)
        run('git', '-C', str(checkout), 'update-ref', 'refs/remotes/origin/' + args.branch, revision)
        (checkout / '.git/FETCH_HEAD').unlink()
        # Remove local paths from the initial fetch's reflog and transient files.
        shutil.rmtree(checkout / '.git/logs', ignore_errors=True)
        run('git', '-C', str(checkout), 'fsck', '--connectivity-only')
        if output('git', '-C', str(checkout), 'rev-parse', '--is-shallow-repository') != 'true':
            raise ValueError('Expected a shallow checkout')
        archive = temp / 'checkout.tar.gz'
        def ownership(info):
            info.uid = info.gid = 0
            info.uname, info.gname = 'root', 'wheel'
            return info
        with tarfile.open(archive, 'w:gz', compresslevel=6, dereference=False) as tar:
            tar.add(checkout, arcname='.', filter=ownership)
        archive_size = archive.stat().st_size
        expanded = sum(p.lstat().st_size for p in checkout.rglob('*') if p.is_file() and not p.is_symlink())
        parts = []
        with archive.open('rb') as stream:
            index = 0
            while True:
                chunk = stream.read(args.chunk_mib * 1024 * 1024)
                if not chunk:
                    break
                name = f'daemonarchy-{args.kind}-checkout-{index:03d}'
                rel = f'usr/local/share/daemonarchy/checkouts/{args.kind}/{revision}/part-{index:03d}'
                stage = temp / f'stage-{index}'
                file = stage / rel
                file.parent.mkdir(parents=True)
                file.write_bytes(chunk)
                manifest = dict(name=name, version=version, origin='misc/' + name,
                                comment=f'Daemonarchy {args.kind} shallow Git checkout payload {index}',
                                desc='Seed data for daemonarchy-checkouts; working trees are never package-owned.',
                                maintainer='jkh@FreeBSD.org', www=args.remote,
                                prefix='/', abi='FreeBSD:16:amd64', arch='freebsd:16:x86:64',
                                files={'/' + rel: {'sum': '1', 'uname': 'root', 'gname': 'wheel', 'perm': '0644'}}, annotations={'git_revision': revision})
                mf = temp / 'manifest.json'
                mf.write_text(json.dumps(manifest))
                run('pkg', 'create', '-l', '1', '-M', str(mf), '-r', str(stage), '-o', str(out))
                package = out / f'{name}-{version}.pkg'
                if package.stat().st_size >= 2 * 1024**3:
                    raise ValueError('Package exceeds release asset limit')
                parts.append(dict(package=f'{name}-{version}', file='/' + rel,
                                  sha256=digest(file), bytes=len(chunk), download_bytes=package.stat().st_size))
                file.unlink()
                index += 1
        receipt = dict(revision=revision, branch=args.branch, remote=args.remote, depth=args.depth,
                       archive_sha256=digest(archive), archive_bytes=archive_size,
                       expanded_bytes=expanded,
                       # Cached pkg, installed seed parts, assembled archive,
                       # extracted contents and filesystem/metadata reserve.
                       required_bytes=3 * archive_size + expanded + allocated + 512 * 1024**2,
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
    parser.add_argument('--depth', type=int, default=1)
    parser.add_argument('--chunk-mib', type=int, default=512)
    args = parser.parse_args()
    if not 1 <= args.chunk_mib <= 1024:
        parser.error('--chunk-mib must be between 1 and 1024')
    if not 1 <= args.depth <= 100:
        parser.error('--depth must be between 1 and 100')
    build(args)
