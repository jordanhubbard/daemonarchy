"""Every package in the enabled repositories and on the system, held in memory and searchable.

pkg keeps one sqlite database per repository ($PKG_DBDIR/repos/NAME/db, filled by `pkg update`)
and one for the installed packages ($PKG_DBDIR/local.sqlite). They are opened read-only, once,
and indexed, so a keystroke is a substring scan of one list and never a `pkg search` process.
Column sets differ a little between pkg releases, so only columns that exist are selected, and
an unreadable database leaves its repository out and is reported, not hidden.
"""
from dataclasses import dataclass, field
import os
import sqlite3

DEFAULT_DBDIR = '/var/db/pkg'


@dataclass
class Offer:
    """One repository's copy of a package."""
    repo: str
    version: str
    pkgsize: int = 0
    flatsize: int = 0


@dataclass
class Entry:
    name: str
    comment: str = ''
    origin: str = ''
    www: str = ''
    maintainer: str = ''
    categories: tuple = ()
    offers: list = field(default_factory=list)
    installed: str = ''             # installed version, '' when absent
    installed_flatsize: int = 0
    automatic: bool = False

    @property
    def category(self):
        return self.categories[0] if self.categories else (self.origin.split('/')[0] if '/' in self.origin else '')

    def offer(self, repo=None):
        for candidate in self.offers:
            if repo is None or candidate.repo == repo:
                return candidate
        return None


def columns(db, table):
    return {row[1] for row in db.execute(f'PRAGMA table_info({table})')}


def rows(db, wanted):
    """Dicts for the wanted columns of `packages` that this database has; missing ones are absent."""
    have = columns(db, 'packages')
    chosen = [c for c in wanted if c in have]
    for row in db.execute(f'SELECT {", ".join(chosen)} FROM packages'):
        yield dict(zip(chosen, row))


def category_map(db):
    try:
        return {pid: tuple(names.split('\x1f')) for pid, names in db.execute(
            'SELECT pc.package_id, group_concat(c.name, char(31)) FROM pkg_categories pc '
            'JOIN categories c ON c.id = pc.category_id GROUP BY pc.package_id')}
    except sqlite3.Error:
        return {}


class Catalogue:
    def __init__(self):
        self.entries = {}       # name -> Entry
        self.problems = []      # (database, message): a database that could not be read
        self.repos = []         # repository names that were read
        self._index = []        # [(entry, lowercase name, lowercase comment)], rebuilt by finish()

    @classmethod
    def load(cls, dbdir=None, repos=None, local=True):
        """Read the repository databases (all that exist, or just `repos`) and the installed one."""
        dbdir = dbdir or os.environ.get('PKG_DBDIR') or DEFAULT_DBDIR
        found = cls()
        base = os.path.join(dbdir, 'repos')
        try:
            names = sorted(os.listdir(base)) if repos is None else list(repos)
        except OSError:
            names = []
        for name in names:
            found.read_repository(name, os.path.join(base, name, 'db'))
        if local:
            found.read_local(os.path.join(dbdir, 'local.sqlite'))
        found.finish()
        return found

    @staticmethod
    def open(path):
        return sqlite3.connect(f'file:{path}?mode=ro', uri=True)

    def entry(self, name):
        if name not in self.entries:
            self.entries[name] = Entry(name)
        return self.entries[name]

    def read_repository(self, repo, path):
        try:
            with self.open(path) as db:
                cats = category_map(db)
                for row in rows(db, ('id', 'name', 'version', 'comment', 'origin', 'www', 'maintainer',
                                     'pkgsize', 'flatsize')):
                    entry = self.entry(row['name'])
                    entry.comment = entry.comment or row.get('comment') or ''
                    entry.origin = entry.origin or row.get('origin') or ''
                    entry.www = entry.www or row.get('www') or ''
                    entry.maintainer = entry.maintainer or row.get('maintainer') or ''
                    entry.categories = entry.categories or cats.get(row.get('id'), ())
                    entry.offers.append(Offer(repo, row.get('version') or '', int(row.get('pkgsize') or 0),
                                              int(row.get('flatsize') or 0)))
            self.repos.append(repo)
        except (sqlite3.Error, OSError) as error:
            self.problems.append((path, str(error)))

    def read_local(self, path):
        try:
            with self.open(path) as db:
                for row in rows(db, ('name', 'version', 'comment', 'origin', 'www', 'flatsize', 'automatic')):
                    entry = self.entry(row['name'])
                    entry.installed = row.get('version') or ''
                    entry.installed_flatsize = int(row.get('flatsize') or 0)
                    entry.automatic = bool(row.get('automatic'))
                    entry.comment = entry.comment or row.get('comment') or ''
                    entry.origin = entry.origin or row.get('origin') or ''
                    entry.www = entry.www or row.get('www') or ''
        except (sqlite3.Error, OSError) as error:
            self.problems.append((path, str(error)))

    def finish(self):
        for entry in self.entries.values():
            entry.offers.sort(key=lambda o: o.repo)
        self._index = sorted(((e, e.name.lower(), e.comment.lower()) for e in self.entries.values()),
                             key=lambda item: item[1])

    def __len__(self):
        return len(self.entries)

    def installed(self):
        return sorted((e for e in self.entries.values() if e.installed), key=lambda e: e.name)

    def search(self, query, limit=200, installed=None, category=None):
        """Entries whose name or comment contain every word of the query, best first: the exact name,
        then names that start with the word, then names containing it, then comments. `installed`
        True/False limits to installed/not installed; `category` to one category."""
        words = query.lower().split()
        scored = []
        for entry, name, comment in self._index:
            if installed is not None and bool(entry.installed) != installed:
                continue
            if category and category not in entry.categories and entry.category != category:
                continue
            score = 0
            for word in words:
                if name == word:
                    score += 100
                elif name.startswith(word):
                    score += 50
                elif word in name:
                    score += 25
                elif word in comment:
                    score += 5
                else:
                    break
            else:
                scored.append((-score, name, entry))
        scored.sort(key=lambda item: item[:2])
        return [entry for _, _, entry in scored[:limit]]

    def categories(self):
        counts = {}
        for entry in self.entries.values():
            counts[entry.category] = counts.get(entry.category, 0) + 1
        return sorted((c, n) for c, n in counts.items() if c)

    def sizes(self):
        """{(repo, name-version): (archive bytes, installed bytes)} in parallel-fetch's shape."""
        return {(offer.repo, f'{entry.name}-{offer.version}'): (offer.pkgsize, offer.flatsize)
                for entry in self.entries.values() for offer in entry.offers}
