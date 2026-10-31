"""A pkg dry run as a plan: what changes, how many bytes, from which repository, and an identity.

The text of `pkg install|upgrade|delete -n` is the planner's answer; this does not solve
dependencies itself. It turns that text into an object the window can show before anything
happens, and gives it an identity: the SHA-256 of the canonical plan. The privileged helper
recomputes the plan and runs only if the identity is the one the user approved, so what runs is
what was shown. Download and installed bytes are the exact catalogue figures the installer's
`@@plan` line carries (parallel-fetch's plan_summary), not pkg's rounded text.
"""
from dataclasses import dataclass, field
import hashlib
import json
import os
import re
import subprocess

from . import engine

SCHEMA = 'daemonarchy/gui-plan@1'
ACTIONS = ('install', 'upgrade', 'remove', 'autoremove')
VERBS = {'install': 'install', 'upgrade': 'upgrade', 'remove': 'delete', 'autoremove': 'autoremove'}
# Removing never fetches: no catalogue update flag, no download stage. autoremove is pkg's own list of automatic
# packages nothing depends on any more, planned and run like any other removal.
REMOVALS = ('remove', 'autoremove')
# Section heading -> what happens to the packages under it.
SECTIONS = (('New packages to be INSTALLED', 'install'), ('Installed packages to be UPGRADED', 'upgrade'),
            ('Installed packages to be REINSTALLED', 'reinstall'), ('Installed packages to be DOWNGRADED', 'downgrade'),
            ('Installed packages to be REMOVED', 'remove'))
LINE = re.compile(r'^\t([^\s:]+): (?:(\S+) -> )?(\S+?)(?: \[([^\]]+)\])?\s*$')
REINSTALL = re.compile(r'^\t(\S+)-([^-\s]+?)(?: \(.*\))?\s*$')
FREE = re.compile(r'^The operation will free ([0-9.]+) (KiB|MiB|GiB|TiB)', re.M)
UNIT = dict(KiB=1 << 10, MiB=1 << 20, GiB=1 << 30, TiB=1 << 40)


@dataclass(frozen=True)
class Item:
    kind: str           # install, upgrade, reinstall, downgrade, remove
    name: str
    version: str        # the version after the change (the one removed, for a removal)
    previous: str = ''  # the installed version it replaces, for upgrades and downgrades
    repo: str = ''

    @property
    def id(self):
        return f'{self.name}-{self.version}'


@dataclass
class Plan:
    action: str
    requested: tuple
    items: list = field(default_factory=list)
    download_bytes: int = 0
    installed_bytes: int = 0        # change in installed size: positive grows, negative frees
    approximate: bool = False       # sizes are pkg's rounded text, not the catalogue
    untrusted: list = field(default_factory=list)   # (repository, why) the plan would take packages from
    problems: list = field(default_factory=list)
    text: str = field(default='', repr=False, compare=False)   # pkg's dry-run output, which parallel-fetch reads

    @property
    def identity(self):
        canonical = dict(schema=SCHEMA, action=self.action, requested=sorted(self.requested),
                         items=sorted([i.kind, i.name, i.version, i.previous, i.repo] for i in self.items),
                         download_bytes=self.download_bytes, installed_bytes=self.installed_bytes)
        return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    @property
    def needs_confirmation(self):
        """True when packages would come from a repository that is not verified by a signature."""
        return bool(self.untrusted)

    def counts(self):
        counts = {}
        for item in self.items:
            counts[item.kind] = counts.get(item.kind, 0) + 1
        return counts

    def to_fetch(self):
        return [i for i in self.items if i.kind in ('install', 'upgrade', 'reinstall', 'downgrade')]

    def describe(self):
        return dict(schema=SCHEMA, identity=self.identity, action=self.action, requested=list(self.requested),
                    counts=self.counts(), download_bytes=self.download_bytes, installed_bytes=self.installed_bytes,
                    approximate=self.approximate, untrusted=self.untrusted, problems=self.problems,
                    items=[dict(kind=i.kind, name=i.name, version=i.version, previous=i.previous, repo=i.repo)
                           for i in self.items])


def parse_items(text):
    """The Items a dry run lists, in the order pkg prints them."""
    items, kind = [], None
    for line in text.splitlines():
        if not line.startswith('\t'):
            stripped = line.strip()
            kind = None
            if stripped.endswith(':'):
                for heading, what in SECTIONS:
                    if stripped.startswith(heading):
                        kind = what
            continue
        if not kind:
            continue
        match = LINE.match(line)
        if match:
            name, previous, version, repo = match.groups()
            items.append(Item(kind, name, version, previous or '', repo or ''))
            continue
        match = REINSTALL.match(line)
        if match and kind == 'reinstall':
            items.append(Item(kind, match.group(1), match.group(2)))
    return items


def from_text(action, requested, text, catalogue=None, repositories=(), cached=lambda identifier: False):
    """The Plan for a dry run's output. `catalogue` supplies exact bytes and the repository pkg left
    off a line (it does when only one is configured); `repositories` (repos.read()) says which are signed."""
    requested = tuple(requested)
    plan = Plan(action, requested, text=text)
    items = parse_items(text)
    if catalogue is not None:
        items = [fill_repo(i, catalogue) for i in items]
    plan.items = items
    wanted = [dict(id=i.id, name=i.name, version=i.version, repo=i.repo) for i in plan.to_fetch()]
    fetch = [i for i in wanted if not cached(i['id'])]
    sizes = catalogue.sizes() if catalogue is not None else {}
    summary = engine.load('parallel-fetch').plan_summary(wanted, fetch, sizes, text)
    plan.approximate = bool(summary.get('approximate')) and bool(wanted)      # a removal downloads nothing
    plan.download_bytes = summary.get('download_bytes', 0)
    plan.installed_bytes = summary.get('installed_bytes', 0)
    freed = freed_bytes(text, plan, catalogue)
    if freed:
        plan.installed_bytes -= freed
    if not plan.items:
        said = [line.strip() for line in text.splitlines() if line.strip()]
        plan.problems.append(said[-1] if said else 'pkg planned no changes')   # pkg's own reason, when it gave one
    by_name = {r.name: r for r in repositories}
    for repo in sorted({i.repo for i in plan.items if i.kind != 'remove' and i.repo}):
        known = by_name.get(repo)
        if known is None:
            plan.untrusted.append((repo, 'a repository this system is not configured with'))
        elif not known.signed:
            plan.untrusted.append((repo, known.problem or 'unsigned'))
    return plan


def fill_repo(item, catalogue):
    if item.repo or item.kind == 'remove':
        return item
    entry = catalogue.entries.get(item.name)
    offer = None
    if entry is not None:
        offer = next((o for o in entry.offers if o.version == item.version), None) or entry.offer()
    return Item(item.kind, item.name, item.version, item.previous, offer.repo if offer else '')


def freed_bytes(text, plan, catalogue):
    """Bytes a removal frees: the installed sizes when known, else pkg's rounded 'will free' line."""
    removed = [i for i in plan.items if i.kind == 'remove']
    if not removed:
        return 0
    if catalogue is not None and all(catalogue.entries.get(i.name) and catalogue.entries[i.name].installed_flatsize
                                     for i in removed):
        return sum(catalogue.entries[i.name].installed_flatsize for i in removed)
    match = FREE.search(text)
    if match:
        plan.approximate = True
        return int(float(match.group(1)) * UNIT[match.group(2)])
    return 0


def command(action, names, pkg=('pkg',)):
    """The dry-run command for an action; the helper runs the same one with the real verb."""
    if action not in ACTIONS:
        raise ValueError(f'unknown action {action!r}')
    flags = ['-n', '-y'] + (['-U'] if action not in REMOVALS else [])
    return [*pkg, VERBS[action], *flags, *names]


def dry_run(action, names, catalogue=None, repositories=(), pkg=('pkg',), runner=None, timeout=300):
    """Ask pkg what the action would do. `runner(argv)` returns the text; the default runs pkg
    with a C locale so the headings above are what it prints."""
    argv = command(action, names, pkg)
    if runner is None:
        def runner(argv):
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                                  env=dict(os.environ, LANG='C', LC_ALL='C'))
            text = done.stdout + done.stderr
            if done.returncode and not text.strip():
                text = f'pkg exited {done.returncode} without a message'
            return text
    plan = from_text(action, names, runner(argv), catalogue, repositories)
    return plan


def size_text(count):
    """Bytes as the installer prints them (MiB/GiB with one decimal)."""
    for unit, size in (('GiB', 1 << 30), ('MiB', 1 << 20), ('KiB', 1 << 10)):
        if abs(count) >= size:
            return f'{count / size:.1f} {unit}'
    return f'{count} B'
