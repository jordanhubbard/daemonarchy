"""What the window shows and does, without a toolkit, so it is tested without a display.

`Browser` answers "which packages, in which view, for this query" and "what is this package"; `Session`
is one install, upgrade or remove from the plan the user reviews to the result; `launch` runs the
root helper and delivers its lines. window.py only draws these and calls them.
"""
from dataclasses import dataclass, field
import os
import signal
import subprocess
import threading

from . import plan as plan_module, theme, transaction, txview

VIEWS = ('browse', 'installed', 'updates', 'repositories')


@dataclass
class Row:
    name: str
    version: str
    comment: str
    badge: str              # installed, update or available
    category: str = ''
    trust: str = ''         # trust of the repository that would supply it: signed, unsigned, broken or ''


@dataclass
class Detail:
    name: str
    comment: str
    origin: str
    category: str
    www: str
    maintainer: str
    installed: str
    version: str
    download_bytes: int
    installed_bytes: int
    offers: list = field(default_factory=list)      # (repository, version, trust)
    actions: list = field(default_factory=list)     # of install, upgrade, remove
    unavailable: str = ''                           # why there is nothing to install, when so


class Browser:
    def __init__(self, catalogue, repositories=(), upgrades=()):
        self.catalogue = catalogue
        self.trust = {r.name: r.trust for r in repositories if r.enabled}
        self.enabled = [r for r in repositories if r.enabled]
        self.repositories = list(repositories)
        self.upgrades = set(upgrades)       # package names the planner (`pkg upgrade -n`) says will change

    def badge(self, entry):
        if entry.installed:
            return 'update' if entry.name in self.upgrades else 'installed'
        return 'available'

    def supplier(self, entry):
        """The repository pkg would take this package from: the first enabled repository that offers it."""
        for offer in entry.offers:
            if not self.trust or offer.repo in self.trust:
                return offer
        return None

    def row(self, entry):
        offer = self.supplier(entry)
        trust = self.trust.get(offer.repo, 'broken') if offer and self.trust else ''
        return Row(entry.name, entry.installed or (offer.version if offer else ''), entry.comment, self.badge(entry),
                   entry.category, trust)

    def rows(self, view, query='', limit=200):
        """(rows, total matching) for a view and a search."""
        if view == 'installed':
            found = self.catalogue.search(query, limit=10 ** 9, installed=True)
        elif view == 'updates':
            found = [e for e in self.catalogue.search(query, limit=10 ** 9, installed=True) if e.name in self.upgrades]
        else:
            found = self.catalogue.search(query, limit=10 ** 9)
        return [self.row(e) for e in found[:limit]], len(found)

    def detail(self, name):
        entry = self.catalogue.entries.get(name)
        if entry is None:
            return None
        offer = self.supplier(entry)
        actions, unavailable = [], ''
        if entry.installed:
            actions.append('remove')
            if entry.name in self.upgrades:
                actions.insert(0, 'upgrade')
        elif offer:
            actions.append('install')
        else:
            unavailable = 'no enabled repository offers this package'
        return Detail(entry.name, entry.comment, entry.origin, entry.category, entry.www, entry.maintainer,
                      entry.installed, offer.version if offer else '', offer.pkgsize if offer else 0,
                      offer.flatsize if offer else entry.installed_flatsize,
                      [(o.repo, o.version, self.trust.get(o.repo, 'unknown')) for o in entry.offers], actions, unavailable)

    def repository_rows(self):
        return [r.describe() for r in self.repositories]


def launch(argv, on_line, on_exit):
    """Run argv, calling on_line for each output line and on_exit(code) at the end, both from a reader
    thread. The handle's terminate() asks the process to stop."""
    child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace',
                             bufsize=1, start_new_session=True)

    def read():
        for line in child.stdout:
            on_line(line.rstrip('\n'))
        on_exit(child.wait())

    thread = threading.Thread(target=read, daemon=True)
    thread.start()

    class Handle:
        def __init__(self):
            self.thread = thread

        def terminate(self):
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except OSError:
                pass

    return Handle()


class Session:
    """One change to the system, from review to result. States: planning, review, running, done, failed,
    refused, cancelled, error."""

    def __init__(self, action, names, planner, helper=None, elevate=None, clock=None):
        self.action, self.names = action, list(names)
        self.planner = planner                   # planner(action, names) -> Plan
        self.helper = helper or transaction.helper_path()
        self.elevate = elevate or transaction.elevate
        self.clock = clock
        self.state, self.plan, self.error = 'planning', None, ''
        self.allowed = set()
        self.tx, self.handle, self.lines = None, None, []
        self.exit_code, self.cancelled = None, False

    # -- review
    def make_plan(self):
        try:
            self.plan = self.planner(self.action, self.names)
        except (OSError, subprocess.SubprocessError) as problem:
            self.state, self.error = 'error', f'pkg could not be asked for a plan: {problem}'
            return self.state
        self.allowed = set()
        self.state = 'review' if self.plan.items else 'error'
        if not self.plan.items:
            self.error = (self.plan.problems or ['pkg planned no changes'])[0]
        return self.state

    def allow(self, repo, yes=True):
        (self.allowed.add if yes else self.allowed.discard)(repo)

    def pending_trust(self):
        """Repositories the plan takes packages from that the user has not yet accepted."""
        return [(repo, why) for repo, why in (self.plan.untrusted if self.plan else []) if repo not in self.allowed]

    def can_approve(self):
        return self.state == 'review' and bool(self.plan and self.plan.items) and not self.pending_trust()

    def helper_argv(self):
        argv = [self.helper, self.action, '--identity', self.plan.identity]
        for repo in sorted(self.allowed):
            argv += ['--allow-unsigned', repo]
        return argv + self.names

    # -- run
    def approve(self, start=launch):
        """Start the helper as root. `start(argv, on_line, on_exit)` is launch, or a stand-in in tests."""
        if not self.can_approve():
            raise RuntimeError('this plan cannot be approved yet')
        argv = self.elevate(self.helper_argv())
        if argv is None:
            self.state, self.error = 'error', 'administrator rights are needed and sudo is not available'
            return False
        self.tx = txview.Transaction(self.action, **({'clock': self.clock} if self.clock else {}))
        self.lines, self.exit_code, self.state = [], None, 'running'
        self.handle = start(argv, self.feed, self.exited)
        return True

    def feed(self, line):
        self.lines.append(line)
        self.lines = self.lines[-200:]
        self.tx.feed(line)
        if self.tx.state in ('done', 'failed', 'refused'):
            self.state = self.tx.state

    def exited(self, code):
        self.exit_code = code
        if self.state == 'running':
            # The helper ended without its @@result: sudo refused or its prompt was cancelled, or it was killed.
            tail = [l for l in self.lines if l.strip()][-1:] or ['the helper ended without saying why']
            self.state = 'cancelled' if self.cancelled else 'failed'
            self.error = '' if self.cancelled else f'the helper exited {code}: {tail[0]}'

    def can_cancel(self):
        """Cancelling is safe while archives are downloading; once pkg is installing, stopping it could leave
        the system half-changed, so the window does not offer it."""
        return self.state == 'running' and self.tx is not None and self.tx.phase in ('start', 'fetch') \
            and self.handle is not None

    def cancel(self):
        if not self.can_cancel():
            return False
        self.cancelled = True
        self.handle.terminate()
        return True

    # -- result
    def retry(self):
        """Back to planning: the plan is computed again, so a changed catalogue is reviewed, not assumed."""
        self.state, self.error, self.tx, self.handle, self.cancelled = 'planning', '', None, None, False
        return self.make_plan()

    def view(self):
        return self.tx.view() if self.tx else None


def title(action, names):
    if action == 'autoremove':
        return 'Remove unused dependencies'
    shown = ', '.join(names[:3]) + (f' and {len(names) - 3} more' if len(names) > 3 else '')
    return f"{theme.LABEL.get(action, action.title())} {shown}".strip()
