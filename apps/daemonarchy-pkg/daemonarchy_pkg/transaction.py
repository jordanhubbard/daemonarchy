"""Run an approved plan as root, and say what happened in the installer's own event vocabulary.

  daemonarchy-pkg-helper ACTION --identity SHA256 [--allow-unsigned REPO]... NAME...

The window shows a plan and the user approves it by identity. This recomputes the plan from the
current catalogue and runs only if the identity is the same, so what runs is what was shown. A
plan that would take packages from a repository without a verified signature also needs that
repository named with --allow-unsigned. Then, for install and upgrade, the archives are fetched by
the installer's `parallel-fetch` (several pkg processes, each archive verified by pkg against the
signed catalogue, nothing installed) and pkg installs from the cache; a removal is one pkg run.

Everything goes to stdout as the install log's lines: `@@phase fetch` and `@@phase install`, the
`@@plan` line (daemonarchy/install-plan@1), parallel-fetch's `@@fetch` lines, and pkg's own
`[n/N] Installing` / `Extracting ... done` lines, which `progress-model` already understands. The
last line is always one `@@result {...}` (schema daemonarchy/gui-result@1) with the status and why.

Exit status: 0 done, 1 pkg failed (the packages may be partly changed: pkg's own transaction
rules apply), 3 refused because the plan changed or has nothing to do, 4 refused because a
repository is unsigned and was not allowed, 5 the download failed for a reason a retry will not fix.
Nothing has changed on the system for 3, 4 and 5; retry re-plans.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from . import catalogue as catalogue_module, engine, plan as plan_module, repos as repos_module

RESULT_SCHEMA = 'daemonarchy/gui-result@1'
OK, FAILED, REFUSED_PLAN, REFUSED_UNSIGNED, FETCH_FAILED = 0, 1, 3, 4, 5
# Connections per repository, from the installer's measurements: pkg.FreeBSD.org throttles beyond about
# four streams, while the Daemonarchy feeds on GitHub keep scaling.
FREEBSD_STREAMS, FEED_STREAMS = 4, 16
SAFE_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+,~-]{0,199}$')    # never starts with '-': no option injection
IDENTITY = re.compile(r'^[0-9a-f]{64}$')


def emit(out, line):
    out.write(line.rstrip('\n') + '\n')
    out.flush()


def result(out, status, code, **fields):
    emit(out, '@@result ' + json.dumps(dict(schema=RESULT_SCHEMA, status=status, exit=code, **fields),
                                       separators=(',', ':'), sort_keys=True))
    return code


def stream(argv, out, env=None):
    """Run argv, copying its output line by line as it arrives; its exit status."""
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace',
                          bufsize=1, env=env) as child:
        for line in child.stdout:
            emit(out, line)
        return child.wait()


def pkg_setting(pkg, name):
    try:
        done = subprocess.run([*pkg, 'config', name], capture_output=True, text=True, timeout=60)
        lines = done.stdout.strip().splitlines()
        return lines[-1] if lines else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def repo_streams(repositories):
    """--repo-workers arguments: FreeBSD's mirrors get four connections, everything else sixteen."""
    caps = []
    for repo in repositories:
        if repo.enabled and 'pkg.freebsd.org' in repo.url.lower():
            caps += ['--repo-workers', f'{repo.name}={FREEBSD_STREAMS}']
    return caps


def plan_line(plan, to_fetch):
    """The installer's @@plan line for what this transaction will do, so the progress counters use it."""
    packages = sum(1 for i in plan.items if i.kind != 'remove')
    if not packages:
        return None
    return '@@plan ' + json.dumps(dict(schema='daemonarchy/install-plan@1', packages=packages, archives=len(to_fetch),
                                       download_bytes=plan.download_bytes,
                                       installed_bytes=max(plan.installed_bytes, 0)), separators=(',', ':'))


def run(action, names, identity, allow_unsigned=(), pkg=('pkg',), out=None, dbdir=None,
        repos_dirs=repos_module.DEFAULT_DIRS, workers=16, python=sys.executable):
    out = out or sys.stdout
    names = list(names)
    repositories = repos_module.read(tuple(repos_dirs))
    found = catalogue_module.Catalogue.load(dbdir or catalogue_module.DEFAULT_DBDIR)     # never the environment's
    plan = plan_module.dry_run(action, names, found, repositories, pkg=tuple(pkg))
    if plan.identity != identity:
        return result(out, 'refused', REFUSED_PLAN, reason='plan-changed', identity=plan.identity,
                      detail='the plan is not the one that was approved; review it again')
    if not plan.items:
        return result(out, 'refused', REFUSED_PLAN, reason='nothing-to-do', identity=plan.identity,
                      detail=plan.problems[0] if plan.problems else 'pkg planned no changes')
    unallowed = [repo for repo, _why in plan.untrusted if repo not in set(allow_unsigned)]
    if unallowed:
        return result(out, 'refused', REFUSED_UNSIGNED, reason='unsigned-repository', identity=plan.identity,
                      repositories=unallowed, detail='packages would come from a repository without a verified signature')
    if action in ('install', 'upgrade'):
        code = fetch(plan, pkg, repositories, out, workers, python)
        if code:
            return result(out, 'failed', FETCH_FAILED if code == 3 else FAILED, reason='download', identity=plan.identity,
                          detail=f'the download did not complete (parallel-fetch exit {code})')
    emit(out, '@@phase install')
    verb = plan_module.VERBS[action]
    argv = [*pkg, verb, '-y'] + (['-U'] if action != 'remove' else []) + names
    code = stream(argv, out)
    if code:
        return result(out, 'failed', FAILED, reason='pkg', identity=plan.identity, detail=f'pkg {verb} exited {code}')
    return result(out, 'ok', OK, identity=plan.identity, changed=plan.counts())


def fetch(plan, pkg, repositories, out, workers, python):
    """Fetch every archive the plan needs into pkg's cache with the installer's pool; 0 when all are there."""
    to_fetch = plan.to_fetch()
    if not to_fetch:
        return 0
    emit(out, '@@phase fetch')
    line = plan_line(plan, to_fetch)
    if line:
        emit(out, line)
    cache = pkg_setting(pkg, 'PKG_CACHEDIR') or '/var/cache/pkg'
    tool = engine.path_of('parallel-fetch')
    with tempfile.TemporaryDirectory() as tmp:
        text = Path(tmp) / 'plan.txt'
        text.write_text(plan.text, encoding='utf-8')
        argv = [python, str(tool), '--plan', str(text), '--cache', cache, '--workers', str(workers),
                *repo_streams(repositories), '--', *pkg]
        code = stream(argv, out)
    # Exit 1 means some archives are still missing after the pool's retries; pkg install fetches those serially.
    return 0 if code in (0, 1) else code


def main(argv=None, out=None):
    import argparse
    parser = argparse.ArgumentParser(prog='daemonarchy-pkg-helper', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=plan_module.ACTIONS)
    parser.add_argument('names', nargs='*')
    parser.add_argument('--identity', required=True)
    parser.add_argument('--allow-unsigned', action='append', default=[])
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args(argv)
    if args.action != 'upgrade' and not args.names:
        parser.error('install and remove need package names')
    # This runs as root on arguments a user chose, so it takes nothing that points it somewhere else:
    # the pkg command, the database and the configuration directories are the system's, fixed here.
    # (Tests call run() with a fake pkg and fixture directories.)
    bad = [n for n in args.names + args.allow_unsigned if not SAFE_NAME.match(n)]
    if bad or not 1 <= args.workers <= 32 or not IDENTITY.match(args.identity):
        parser.error('refusing an argument that is not a plain package name, repository name or identity')
    return run(args.action, args.names, args.identity, args.allow_unsigned, ('pkg',), out, workers=args.workers)


def elevate(argv, env=None, euid=None, which=None):
    """The argv that runs `argv` as root: itself when already root, else `sudo -A` with the desktop's
    askpass (SUDO_ASKPASS), else `sudo -n` (passwordless sudo). None when neither is possible."""
    env = os.environ if env is None else env
    which = which or (lambda name: next((str(Path(d) / name) for d in env.get('PATH', '').split(':')
                                         if (Path(d) / name).is_file()), None))
    if (os.geteuid() if euid is None else euid) == 0:
        return list(argv)
    sudo = which('sudo')
    if not sudo:
        return None
    if env.get('SUDO_ASKPASS'):
        return [sudo, '-A', *argv]
    return [sudo, '-n', *argv]
