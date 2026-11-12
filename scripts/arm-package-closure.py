#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Verify and stage an explicit native package closure for an ARM RAM image.

This development input format binds archive bytes and native pkg metadata. It
does not authenticate an upstream repository or admit release lifecycle inputs.
"""
import argparse
import graphlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

SCHEMA = 'daemonarchy/arm-package-closure@1'
PKG = '/usr/local/sbin/pkg'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path):
    if not path.is_absolute() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('absolute regular nonsymlink package inputs required')


def metadata(path):
    def query(fmt):
        return subprocess.check_output([PKG, 'query', '-F', str(path), fmt],
                                       text=True, timeout=30).strip()
    name, version, abi = query('%n %v %q').split()
    return dict(name=name, version=version, abi=abi,
                dependencies=sorted(filter(None, query('%dn').splitlines())))


def package_order(data):
    graph = {row['name']: sorted(row['dependencies'])
             for row in sorted(data['packages'], key=lambda row: row['name'])}
    try:
        return list(graphlib.TopologicalSorter(graph).static_order())
    except graphlib.CycleError as error:
        raise ValueError('cyclic package dependency closure') from error


def verify(manifest, manifest_hash, root_hash):
    regular(manifest)
    if digest(manifest) != manifest_hash:
        raise ValueError('package closure manifest checksum mismatch')
    data = json.loads(manifest.read_text())
    if data.get('schema') != SCHEMA or data.get('root') != 'omarchy':
        raise ValueError('expected an ARM Omarchy package closure')
    rows = data.get('packages')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 4096:
        raise ValueError('invalid package closure size')
    selected = {}
    for row in rows:
        name, version = row['name'], row['version']
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*', name) or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_,.-]*', version)):
            raise ValueError('unsafe package name/version')
        if name in selected:
            raise ValueError('duplicate package name in closure')
        if row['abi'] not in ('FreeBSD:16:aarch64', 'FreeBSD:16:*'):
            raise ValueError('foreign package ABI in closure')
        if not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('invalid package digest')
        dependencies = row['dependencies']
        if (not isinstance(dependencies, list) or
                not all(isinstance(dep, str) for dep in dependencies) or
                len(set(dependencies)) != len(dependencies)):
            raise ValueError('invalid package dependency list')
        selected[name] = row
    if 'omarchy' not in selected or selected['omarchy']['sha256'] != root_hash:
        raise ValueError('closure does not select the pinned Omarchy package')
    if selected['omarchy']['abi'] != 'FreeBSD:16:aarch64':
        raise ValueError('Omarchy requires the native AArch64 ABI')
    reachable, pending = set(), ['omarchy']
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        if name not in selected:
            raise ValueError('missing dependency in package closure: ' + name)
        reachable.add(name)
        pending.extend(selected[name]['dependencies'])
    if reachable != selected.keys():
        raise ValueError('package closure contains unrelated archives')
    package_order(data)
    for name, row in selected.items():
        path = Path(row['path'])
        regular(path)
        if (type(row['bytes']) is not int or row['bytes'] <= 0 or
                path.stat().st_size != row['bytes'] or digest(path) != row['sha256']):
            raise ValueError('package archive checksum/size mismatch: ' + name)
        actual = metadata(path)
        if any(actual[key] != row[key] for key in ('name', 'version', 'abi')):
            raise ValueError('package archive identity mismatch: ' + name)
        if actual['dependencies'] != sorted(row['dependencies']):
            raise ValueError('package archive dependencies mismatch: ' + name)
    return data


def public_record(data):
    return dict(schema=SCHEMA, root='omarchy', packages=[
        {key: row[key] for key in ('name', 'version', 'abi', 'bytes', 'sha256', 'dependencies')}
        for row in sorted(data['packages'], key=lambda row: row['name'])])


def stage(data, destination):
    destination.mkdir(mode=0o700)
    for row in data['packages']:
        path = destination / (row['name'] + '-' + row['version'] + '.pkg')
        with Path(row['path']).open('rb') as source, path.open('xb') as output:
            shutil.copyfileobj(source, output, 1 << 20)
        if digest(path) != row['sha256']:
            raise ValueError('package changed while staging: ' + row['name'])
    return public_record(data)


def check_installed(data, root):
    # Exact versions of every selected package are required even when pkg add
    # could otherwise retain a previously installed dependency by name alone.
    lines = subprocess.check_output([PKG, '-r', str(root), 'query', '-a', '%n %v %q'],
                                    text=True, timeout=60).splitlines()
    installed = {fields[0]: fields[1:] for fields in map(str.split, lines)}
    for row in data['packages']:
        if installed.get(row['name']) != [row['version'], row['abi']]:
            raise ValueError('installed closure identity mismatch: ' + row['name'])
    subprocess.run([PKG, '-r', str(root), 'check', '-dn', '-a'], check=True, timeout=120)


def install(data, staged, root, repositories):
    if not root.is_dir() or not repositories.is_dir() or any(repositories.iterdir()):
        raise ValueError('private root and empty repository directory required')
    selected = {row['name']: row for row in data['packages']}
    paths = []
    for name in package_order(data):
        row = selected[name]
        path = staged / (name + '-' + row['version'] + '.pkg')
        regular(path)
        if digest(path) != row['sha256']:
            raise ValueError('staged archive changed before installation: ' + name)
        in_root = root / 'ram-packages' / path.name
        regular(in_root)
        if digest(in_root) != row['sha256']:
            raise ValueError('chroot package view mismatch: ' + name)
        paths.append('/ram-packages/' + path.name)
    # One native pkg writer, with prerequisites upgraded before their users.
    # -r only redirects package files/database; arbitrary package scripts can
    # still use worker paths. -c confines scripts and their triggers as well.
    repository_path = '/' + str(repositories.relative_to(root))
    print('Installing %d verified packages inside the private chroot' % len(paths), flush=True)
    log = root.parent / 'pkg-install.log'
    opened = False
    script_failed = False
    try:
        with log.open('x') as output:
            opened = True
            result = subprocess.run([PKG, '-c', str(root), '-o', 'REPOS_DIR=' + repository_path,
                                     'add', '-f', *paths], stdout=output,
                                    stderr=subprocess.STDOUT, text=True, timeout=3600,
                                    env=dict(os.environ, ASSUME_ALWAYS_YES='yes'))
    finally:
        # Keep diagnostics on the worker even on timeout or controller loss.
        if opened:
            with log.open(errors='replace') as output:
                for line in output:
                    sys.stdout.write(line)
                    if re.search(r'pkg: (?:PRE|POST)-(?:INSTALL|DEINSTALL) script failed', line):
                        script_failed = True
            sys.stdout.flush()
    if result.returncode != 0:
        raise ValueError('native pkg installation failed with status %d' % result.returncode)
    if script_failed:
        raise ValueError('native package script failed despite successful pkg exit')


def refresh_repo(data, staged, repository):
    # The ISO's unsigned local repository can retain other installer packages,
    # but must not retain older versions of any selected runtime package.
    names = {row['name'] for row in data['packages']}
    for path in repository.glob('*.pkg'):
        if metadata(path)['name'] in names:
            path.unlink()
    for row in data['packages']:
        filename = row['name'] + '-' + row['version'] + '.pkg'
        path = repository / filename
        with (staged / filename).open('rb') as source, path.open('xb') as output:
            shutil.copyfileobj(source, output, 1 << 20)
        if digest(path) != row['sha256']:
            raise ValueError('local repository copy mismatch: ' + row['name'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('verify', 'stage', 'install', 'installed', 'repo'))
    parser.add_argument('manifest', type=Path)
    parser.add_argument('manifest_sha256')
    parser.add_argument('omarchy_sha256')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--repository', type=Path)
    args = parser.parse_args()
    try:
        data = verify(args.manifest, args.manifest_sha256, args.omarchy_sha256)
        if args.operation == 'stage':
            if args.destination is None:
                raise ValueError('--destination required')
            print(json.dumps(stage(data, args.destination), indent=2))
        elif args.operation == 'installed':
            if args.root is None:
                raise ValueError('--root required')
            check_installed(data, args.root)
        elif args.operation == 'install':
            if args.root is None or args.destination is None or args.repository is None:
                raise ValueError('--root, --destination and --repository required')
            install(data, args.destination, args.root, args.repository)
        elif args.operation == 'repo':
            if args.destination is None or args.repository is None:
                raise ValueError('--destination and --repository required')
            refresh_repo(data, args.destination, args.repository)
        else:
            print(json.dumps(dict(packages=len(data['packages']), verified=True)))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f'arm-package-closure: {error}\n')


if __name__ == '__main__':
    main()
