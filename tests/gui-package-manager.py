#!/usr/bin/env python3
"""daemonarchy-pkg's toolkit-free layers: repository trust, the searchable catalogue, plans and their
identity, and the engine shared with the installer. The dry-run texts are what pkg prints (the headings
and line shapes parallel-fetch already parses); the databases are built here with pkg's table layout."""

import contextlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/daemonarchy-pkg"))

from daemonarchy_pkg import catalogue, cli, engine, plan, repos  # noqa: E402

KEY = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkq\n-----END PUBLIC KEY-----\n"

INSTALL = """Updating repositories...
Checking integrity... done (0 conflicting)
The following 3 package(s) will be affected (of 0 checked):

New packages to be INSTALLED:
\tcowsay: 3.04_3 [FreeBSD]
\tperl5: 5.42.0 [FreeBSD]
\tlocal-tool: 1.0 [Extra]

Number of packages to be installed: 3

1 MiB to be downloaded.
"""

UPGRADE = """Checking for upgrades (2 candidates): 100%
Processing candidates (2 candidates): 100%
The following 3 package(s) will be affected (of 0 checked):

Installed packages to be UPGRADED:
\tcurl: 8.10.0 -> 8.11.0 [FreeBSD]

Installed packages to be REINSTALLED:
\topenssl-3.0.15 (direct dependency changed: ca_root_nss)

Installed packages to be DOWNGRADED:
\tzsh: 5.9_1 -> 5.9 [FreeBSD]

Number of packages to be upgraded: 1
"""

REMOVE = """Checking integrity... done (0 conflicting)
Deinstallation has been requested for the following 1 packages (of 0 packages in the universe):

Installed packages to be REMOVED:
\tcowsay: 3.04_3

Number of packages to be removed: 1

The operation will free 71 KiB.
"""


def make_repo(path, packages, categories=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE packages (id INTEGER PRIMARY KEY, origin TEXT, name TEXT, version TEXT, "
                   "comment TEXT, www TEXT, maintainer TEXT, pkgsize INTEGER, flatsize INTEGER)")
        db.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("CREATE TABLE pkg_categories (package_id INTEGER, category_id INTEGER)")
        for number, (name, version, comment, origin, pkgsize, flatsize) in enumerate(packages, 1):
            db.execute("INSERT INTO packages VALUES (?,?,?,?,?,?,?,?,?)",
                       (number, origin, name, version, comment, "https://example.org", "ports@example.org",
                        pkgsize, flatsize))
            for category in (categories or {}).get(name, origin.split("/")[0:1]):
                row = db.execute("SELECT id FROM categories WHERE name=?", (category,)).fetchone()
                category_id = row[0] if row else db.execute("INSERT INTO categories (name) VALUES (?)",
                                                            (category,)).lastrowid
                db.execute("INSERT INTO pkg_categories VALUES (?,?)", (number, category_id))


def make_local(path, packages):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE packages (id INTEGER PRIMARY KEY, origin TEXT, name TEXT, version TEXT, "
                   "comment TEXT, flatsize INTEGER, automatic INTEGER)")
        for number, (name, version, comment, origin, flatsize, automatic) in enumerate(packages, 1):
            db.execute("INSERT INTO packages VALUES (?,?,?,?,?,?,?)",
                       (number, origin, name, version, comment, flatsize, automatic))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "db"
        make_repo(self.db / "repos/FreeBSD/db", [
            ("cowsay", "3.04_3", "Configurable talking cow", "games/cowsay", 40960, 72704),
            ("perl5", "5.42.0", "Practical Extraction and Report Language", "lang/perl5", 15 << 20, 60 << 20),
            ("curl", "8.11.0", "Command line tool for transferring data with URL syntax", "ftp/curl", 3 << 20, 9 << 20),
            ("zsh", "5.9", "The Z shell", "shells/zsh", 4 << 20, 14 << 20),
            ("vim", "9.1", "Improved version of the vi editor", "editors/vim", 9 << 20, 40 << 20),
            ("vim-tiny", "9.1", "Vim without the extras", "editors/vim-tiny", 2 << 20, 8 << 20),
            ("gvim", "9.1", "vim with a window", "editors/vim", 11 << 20, 52 << 20),
        ])
        make_repo(self.db / "repos/Extra/db", [("local-tool", "1.0", "An extra repository's tool", "misc/local-tool", 1000, 2000)])
        make_local(self.db / "local.sqlite", [
            ("curl", "8.10.0", "Command line tool for transferring data with URL syntax", "ftp/curl", 9 << 20, 0),
            ("cowsay", "3.04_3", "Configurable talking cow", "games/cowsay", 72704, 0),
            ("zsh", "5.9_1", "The Z shell", "shells/zsh", 14 << 20, 1),
        ])
        self.catalogue = catalogue.Catalogue.load(str(self.db))

    def write_repos(self, **files):
        directory = self.dir / "repos.d"
        directory.mkdir(exist_ok=True)
        for name, text in files.items():
            (directory / name).write_text(text)
        return directory


class Repositories(Fixture):
    def test_signed_by_pubkey_with_fingerprint(self):
        key = self.dir / "key.pub"
        key.write_text(KEY)
        directory = self.write_repos(**{"Daemonarchy.conf": f'Daemonarchy: {{\n  url: "https://x/y",\n  signature_type: "pubkey",\n'
                                                            f'  pubkey: "{key}",\n  priority: 5\n  enabled: yes\n}}\n'})
        [repo] = repos.read([directory])
        self.assertEqual((repo.name, repo.trust, repo.priority, repo.enabled), ("Daemonarchy", "signed", 5, True))
        self.assertEqual(len(repo.fingerprint), 64)
        self.assertTrue(repo.signed)

    def test_unsigned_and_broken_are_not_trusted(self):
        directory = self.write_repos(**{
            "a.conf": 'Plain: { url: "http://x", enabled: yes }\n',
            "b.conf": 'Keyless: { url: "http://x", signature_type: "pubkey", pubkey: "/nonexistent/key" }\n',
            "c.conf": 'Odd: { url: "http://x", signature_type: "magic" }\n'})
        trust = {r.name: (r.trust, r.problem) for r in repos.read([directory])}
        self.assertEqual(trust["Plain"][0], "unsigned")
        self.assertEqual(trust["Keyless"][0], "broken")
        self.assertIn("cannot be read", trust["Keyless"][1])
        self.assertEqual(trust["Odd"][0], "unsigned")
        self.assertIn("magic", trust["Odd"][1])

    def test_fingerprints_directory(self):
        prints = self.dir / "fp"
        (prints / "trusted").mkdir(parents=True)
        directory = self.write_repos(**{"a.conf": f'F: {{ url: "u", signature_type: "fingerprints", fingerprints: "{prints}" }}\n'})
        self.assertEqual(repos.read([directory])[0].trust, "broken")      # no trusted fingerprint yet
        (prints / "trusted/one").write_text("function: sha256\nfingerprint: \"abc\"\n")
        self.assertEqual(repos.read([directory])[0].trust, "signed")

    def test_later_file_merges_over_earlier_and_can_disable(self):
        system, local = self.dir / "sys", self.dir / "local"
        system.mkdir()
        local.mkdir()
        (system / "FreeBSD.conf").write_text('FreeBSD: { url: "pkg+http://p/${ABI}/latest", signature_type: "none", enabled: yes }\n')
        (local / "FreeBSD.conf").write_text("FreeBSD: { enabled: no }\n")
        [repo] = repos.read([system, local])
        self.assertFalse(repo.enabled)
        self.assertEqual(repo.url, "pkg+http://p/${ABI}/latest")        # merged, not replaced

    def test_comments_quotes_and_order(self):
        directory = self.write_repos(**{"a.conf": '# a comment\nLow: { url: "u1" priority: 1 } // trailing\n'
                                                  'High: {\n  url: "u2"; priority: 10;\n}\n'})
        self.assertEqual([r.name for r in repos.read([directory])], ["High", "Low"])     # higher priority first


class Catalog(Fixture):
    def test_loads_repositories_and_installed(self):
        self.assertEqual(self.catalogue.repos, ["Extra", "FreeBSD"])
        self.assertEqual(self.catalogue.problems, [])
        cow = self.catalogue.entries["cowsay"]
        self.assertEqual((cow.installed, cow.offer("FreeBSD").version, cow.category), ("3.04_3", "3.04_3", "games"))
        self.assertTrue(self.catalogue.entries["zsh"].automatic)
        self.assertEqual([e.name for e in self.catalogue.installed()], ["cowsay", "curl", "zsh"])

    def test_search_ranks_exact_then_prefix_then_substring_then_comment(self):
        names = [e.name for e in self.catalogue.search("vim")]
        self.assertEqual(names[0], "vim")
        self.assertEqual(set(names[:3]), {"vim", "vim-tiny", "gvim"})
        self.assertEqual(names[2], "gvim")                      # name contains it, after the prefix match
        self.assertEqual([e.name for e in self.catalogue.search("cow")], ["cowsay"])
        self.assertEqual([e.name for e in self.catalogue.search("talking cow")], ["cowsay"])   # every word, in the comment
        self.assertEqual(self.catalogue.search("zzzz"), [])

    def test_search_filters(self):
        self.assertEqual([e.name for e in self.catalogue.search("", installed=True)], ["cowsay", "curl", "zsh"])
        self.assertNotIn("cowsay", [e.name for e in self.catalogue.search("", installed=False)])
        self.assertEqual([e.name for e in self.catalogue.search("", category="shells")], ["zsh"])
        self.assertIn(("games", 1), self.catalogue.categories())

    def test_an_unreadable_database_is_reported_not_hidden(self):
        (self.db / "repos/Broken").mkdir()
        (self.db / "repos/Broken/db").write_text("this is not a database")
        loaded = catalogue.Catalogue.load(str(self.db))
        self.assertEqual(len(loaded.problems), 1)
        self.assertIn("Broken", loaded.problems[0][0])
        self.assertIn("cowsay", loaded.entries)

    def test_missing_columns_do_not_break_loading(self):
        bare = self.dir / "bare"
        (bare / "repos/R").mkdir(parents=True)
        with sqlite3.connect(bare / "repos/R/db") as db:
            db.execute("CREATE TABLE packages (name TEXT, version TEXT)")
            db.execute("INSERT INTO packages VALUES ('a', '1')")
        loaded = catalogue.Catalogue.load(str(bare), local=False)
        self.assertEqual(loaded.entries["a"].offer().version, "1")

    def test_search_is_fast_over_a_full_catalogue(self):
        # The full FreeBSD collection is about 35,000 packages; the interactive budget is one frame.
        path = self.dir / "big/repos/Big/db"
        make_repo(path, [(f"pkg{n}-{'abc'[n % 3]}", "1.0", f"comment number {n} about {'tools' if n % 7 else 'games'}",
                          f"cat{n % 50}/pkg{n}", 1000, 2000) for n in range(35000)])
        big = catalogue.Catalogue.load(str(self.dir / "big"), local=False)
        self.assertEqual(len(big), 35000)
        started = time.perf_counter()
        for query in ("pk", "games", "pkg1234", "number 99 tools"):
            big.search(query, limit=50)
        per_search = (time.perf_counter() - started) / 4 * 1000
        print(f"\n  search over 35,000 packages: {per_search:.1f} ms each (this host)", file=sys.stderr)
        self.assertLess(per_search, 100)        # a generous bound for a slow CI worker; the figure above is the record


class Plans(Fixture):
    def trusted(self):
        key = self.dir / "key.pub"
        key.write_text(KEY)
        directory = self.write_repos(**{"r.conf": f'FreeBSD: {{ url: "u", signature_type: "pubkey", pubkey: "{key}" }}\n'
                                                  'Extra: { url: "v" }\n'})
        return repos.read([directory])

    def test_install_plan_items_bytes_and_repositories(self):
        result = plan.from_text("install", ["cowsay"], INSTALL, self.catalogue, self.trusted())
        self.assertEqual([(i.kind, i.name, i.version, i.repo) for i in result.items],
                         [("install", "cowsay", "3.04_3", "FreeBSD"), ("install", "perl5", "5.42.0", "FreeBSD"),
                          ("install", "local-tool", "1.0", "Extra")])
        self.assertEqual(result.download_bytes, 40960 + (15 << 20) + 1000)             # exact catalogue bytes, not "1 MiB"
        self.assertFalse(result.approximate)
        self.assertEqual(result.counts(), {"install": 3})

    def test_a_plan_from_an_unsigned_repository_needs_confirmation(self):
        result = plan.from_text("install", ["local-tool"], INSTALL, self.catalogue, self.trusted())
        self.assertTrue(result.needs_confirmation)
        self.assertEqual([repo for repo, _ in result.untrusted], ["Extra"])
        safe = plan.from_text("install", ["cowsay"], INSTALL.replace("local-tool: 1.0 [Extra]", "curl: 8.11.0 [FreeBSD]"),
                              self.catalogue, self.trusted())
        self.assertFalse(safe.needs_confirmation)

    def test_a_repository_unknown_to_the_configuration_is_untrusted(self):
        result = plan.from_text("install", ["x"], INSTALL, self.catalogue, [])
        self.assertEqual({repo for repo, _ in result.untrusted}, {"FreeBSD", "Extra"})

    def test_upgrade_reinstall_downgrade(self):
        result = plan.from_text("upgrade", [], UPGRADE, self.catalogue)
        self.assertEqual([(i.kind, i.name, i.previous, i.version) for i in result.items],
                         [("upgrade", "curl", "8.10.0", "8.11.0"), ("reinstall", "openssl", "", "3.0.15"),
                          ("downgrade", "zsh", "5.9_1", "5.9")])

    def test_remove_plan_frees_the_installed_size(self):
        result = plan.from_text("remove", ["cowsay"], REMOVE, self.catalogue)
        self.assertEqual([(i.kind, i.name) for i in result.items], [("remove", "cowsay")])
        self.assertEqual(result.download_bytes, 0)
        self.assertEqual(result.installed_bytes, -72704)
        self.assertFalse(result.approximate)                  # the installed size is exact; nothing is downloaded
        self.assertFalse(result.needs_confirmation)           # removing needs no repository

    def test_without_a_catalogue_the_sizes_are_pkgs_rounded_text_and_say_so(self):
        result = plan.from_text("install", ["cowsay"], INSTALL)
        self.assertTrue(result.approximate)
        self.assertEqual(result.download_bytes, 1 << 20)

    def test_output_captured_from_a_real_pkg(self):
        # `pkg install -n -y -U doxygen` on the amd64 build VM (FreeBSD 16.0-CURRENT, pkg 2.x), 2026-10-31.
        captured = ("The following 2 package(s) will be affected (of 0 checked):\n\nNew packages to be INSTALLED:\n"
                    "\tdoxygen: 1.18.0,2 [Daemonarchy]\n\tgraphviz: 16.1.0_2 [FreeBSD-ports]\n\n"
                    "Number of packages to be installed: 2\n\nThe process will require 61 MiB more space.\n"
                    "11 MiB to be downloaded.\n")
        result = plan.from_text("install", ["doxygen"], captured)
        self.assertEqual([(i.name, i.version, i.repo) for i in result.items],
                         [("doxygen", "1.18.0,2", "Daemonarchy"), ("graphviz", "16.1.0_2", "FreeBSD-ports")])
        self.assertEqual((result.download_bytes, result.installed_bytes, result.approximate), (11 << 20, 61 << 20, True))

    def test_empty_plan_is_a_problem_not_silence(self):
        result = plan.from_text("install", ["nosuch"], "No packages available to install matching 'nosuch' have been found.\n")
        self.assertEqual(result.items, [])
        self.assertEqual(result.problems, ["pkg planned no changes"])

    def test_identity_is_stable_and_changes_with_anything_that_matters(self):
        first = plan.from_text("install", ["cowsay"], INSTALL, self.catalogue)
        again = plan.from_text("install", ["cowsay"], INSTALL, self.catalogue)
        self.assertEqual(first.identity, again.identity)
        self.assertEqual(len(first.identity), 64)
        reordered = INSTALL.replace("\tcowsay: 3.04_3 [FreeBSD]\n\tperl5: 5.42.0 [FreeBSD]\n",
                                    "\tperl5: 5.42.0 [FreeBSD]\n\tcowsay: 3.04_3 [FreeBSD]\n")
        self.assertEqual(plan.from_text("install", ["cowsay"], reordered, self.catalogue).identity, first.identity)
        for changed in (INSTALL.replace("5.42.0", "5.42.1"), INSTALL.replace("[Extra]", "[FreeBSD]"),
                        INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", "")):
            self.assertNotEqual(plan.from_text("install", ["cowsay"], changed, self.catalogue).identity, first.identity)
        self.assertNotEqual(plan.from_text("install", ["perl5"], INSTALL, self.catalogue).identity, first.identity)
        self.assertNotEqual(plan.from_text("upgrade", ["cowsay"], INSTALL, self.catalogue).identity, first.identity)

    def test_the_dry_run_command_is_the_one_the_helper_will_run(self):
        self.assertEqual(plan.command("install", ["a", "b"]), ["pkg", "install", "-n", "-y", "-U", "a", "b"])
        self.assertEqual(plan.command("remove", ["a"]), ["pkg", "delete", "-n", "-y", "a"])
        self.assertEqual(plan.command("upgrade", []), ["pkg", "upgrade", "-n", "-y", "-U"])
        with self.assertRaises(ValueError):
            plan.command("purge", [])

    def test_dry_run_uses_the_runner_and_sees_the_argv(self):
        seen = []
        result = plan.dry_run("remove", ["cowsay"], self.catalogue, runner=lambda argv: seen.append(argv) or REMOVE)
        self.assertEqual(seen, [["pkg", "delete", "-n", "-y", "cowsay"]])
        self.assertEqual(len(result.items), 1)


class SharedEngine(unittest.TestCase):
    def test_the_installers_own_modules_are_the_ones_loaded(self):
        fetch, progress = engine.load("parallel-fetch"), engine.load("progress-model")
        self.assertEqual(fetch.SCHEMA, "daemonarchy/pkg-fetch@1")
        self.assertEqual(progress.PLAN_SCHEMA, "daemonarchy/install-plan@1")
        self.assertTrue(str(Path(fetch.__file__)).endswith("daemonarchy-installer/parallel-fetch"))

    def test_a_missing_module_names_where_it_looked(self):
        with self.assertRaises(ImportError) as caught:
            engine.load("no-such-module")
        self.assertIn("no-such-module", str(caught.exception))

    def test_the_gui_plan_totals_equal_the_installers_plan_line(self):
        """The window's bytes must be the bytes the installer's @@plan line reports for the same plan."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)
            make_repo(db / "repos/FreeBSD/db", [("cowsay", "3.04_3", "c", "games/cowsay", 40960, 72704),
                                                 ("perl5", "5.42.0", "p", "lang/perl5", 15 << 20, 60 << 20)])
            found = catalogue.Catalogue.load(str(db), local=False)
        text = INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", "")
        ours = plan.from_text("install", ["cowsay"], text, found)
        fetch = engine.load("parallel-fetch")
        items = fetch.parse_plan(text)
        theirs = fetch.plan_summary(items, items, found.sizes(), text)
        self.assertEqual((ours.download_bytes, ours.installed_bytes), (theirs["download_bytes"], theirs["installed_bytes"]))
        progress = engine.load("progress-model").Progress()
        progress.plan_event(dict(theirs))        # and the progress model accepts that very line's contract
        self.assertEqual(progress.plan["download_bytes"], ours.download_bytes)


class Cli(Fixture):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_search(self):
        code, out, _ = self.run_cli("--dbdir", str(self.db), "search", "cow")
        self.assertEqual(code, 0)
        self.assertIn("cowsay", out)
        self.assertIn("installed 3.04_3", out)

    def test_repos_json(self):
        directory = self.write_repos(**{"a.conf": 'Plain: { url: "http://x" }\n'})
        code, out, _ = self.run_cli("--json", "--repos-dir", str(directory), "repos")
        self.assertEqual(json.loads(out)[0]["trust"], "unsigned")

    def test_plan_from_a_captured_dry_run(self):
        capture = self.dir / "dry-run.txt"
        capture.write_text(REMOVE)
        code, out, _ = self.run_cli("--json", "--dbdir", str(self.db), "--plan-text", str(capture), "plan", "remove", "cowsay")
        described = json.loads(out)
        self.assertEqual((code, described["action"], described["counts"]), (0, "remove", {"remove": 1}))
        self.assertEqual(len(described["identity"]), 64)

    def test_plan_needs_an_action_and_names(self):
        code, _, err = self.run_cli("--dbdir", str(self.db), "plan", "install")
        self.assertEqual(code, 2)
        self.assertIn("ACTION", err)


if __name__ == "__main__":
    unittest.main()
