"""daemonarchy-pkg without a window: the same layers the window uses, as text.

  daemonarchy-pkg search WORDS...            packages matching, best first
  daemonarchy-pkg repos                      configured repositories and whether each is signed
  daemonarchy-pkg plan ACTION [NAME...]      the dry run as a plan with its identity
                                             (ACTION: install, upgrade, remove)
  daemonarchy-pkg gui                        the window (the default when a display is available)

Options: --json for machine output; --dbdir DIR for pkg's database directory; --repos-dir DIR
(repeatable) for repository configuration; --plan-text FILE to plan from a captured dry run
instead of running pkg.
"""
import argparse
import json
import os
import sys

from . import catalogue as catalogue_module, plan as plan_module, repos as repos_module


def build_parser():
    parser = argparse.ArgumentParser(prog='daemonarchy-pkg', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--dbdir')
    parser.add_argument('--repos-dir', action='append')
    parser.add_argument('--plan-text')
    parser.add_argument('command', nargs='?', default='gui', choices=('gui', 'search', 'repos', 'plan'))
    parser.add_argument('words', nargs='*')
    return parser


def show(args, value, text):
    print(json.dumps(value, indent=2, sort_keys=True) if args.json else text)


def main(argv=None, out=None):
    args = build_parser().parse_args(argv)
    repositories = repos_module.read(tuple(args.repos_dir) if args.repos_dir else repos_module.DEFAULT_DIRS)
    if args.command == 'gui':
        if not (os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY')):
            print('daemonarchy-pkg: no display; use search, repos or plan', file=sys.stderr)
            return 2
        from . import window
        return window.main()
    if args.command == 'repos':
        rows = [r.describe() for r in repositories]
        show(args, rows, '\n'.join(
            f"{r['name']:<16} {'on ' if r['enabled'] else 'off'} {r['trust']:<8} {r['signature_type']:<12} "
            f"{r['fingerprint'] or '-':<16} {r['url']}" + (f"  ({r['problem']})" if r['problem'] else '')
            for r in rows))
        return 0
    found = catalogue_module.Catalogue.load(args.dbdir)
    for path, message in found.problems:
        print(f'daemonarchy-pkg: {path}: {message}', file=sys.stderr)
    if args.command == 'search':
        entries = found.search(' '.join(args.words), limit=50)
        rows = [dict(name=e.name, installed=e.installed, available=[o.version for o in e.offers], comment=e.comment)
                for e in entries]
        show(args, rows, '\n'.join(
            f"{r['name']:<32} {('installed ' + r['installed']) if r['installed'] else '':<24} {r['comment']}"
            for r in rows))
        return 0
    action, names = (args.words[0] if args.words else ''), args.words[1:]
    if action not in plan_module.ACTIONS or (action != 'upgrade' and not names):
        print('daemonarchy-pkg: plan ACTION NAME... (ACTION: install, upgrade, remove)', file=sys.stderr)
        return 2
    runner = (lambda argv: open(args.plan_text, encoding='utf-8', errors='replace').read()) if args.plan_text else None
    plan = plan_module.dry_run(action, names, found, repositories, runner=runner)
    lines = [f'{plan.action} {" ".join(plan.requested)}'.rstrip(), f'identity {plan.identity}']
    lines += [f'  {i.kind:<9} {i.name} {i.previous + " -> " if i.previous else ""}{i.version}'
              + (f' [{i.repo}]' if i.repo else '') for i in plan.items]
    lines.append((f"download {plan_module.size_text(plan.download_bytes)}, " if plan.to_fetch() else '')
                 + f"installed size change {plan_module.size_text(plan.installed_bytes)}"
                 + (' (sizes approximate)' if plan.approximate else ''))
    lines += [f'  NOT SIGNED: {repo}: {why}' for repo, why in plan.untrusted]
    lines += [f'  problem: {p}' for p in plan.problems]
    show(args, plan.describe(), '\n'.join(lines))
    return 1 if plan.problems and not plan.items else 0
