#!/usr/bin/env python3
"""daemonarchy-pkg's transaction: the root helper's refusals and its event stream, and the window's view of that
stream. A fake pkg stands in for the package manager (dry-run text, fetch into a cache, install and delete lines);
the real parallel-fetch and progress-model run unchanged."""

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/daemonarchy-pkg"))
sys.path.insert(0, str(ROOT / "tests"))

from daemonarchy_pkg import catalogue, engine, plan, repos, transaction, txview  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("gui_pm_tests", ROOT / "tests/gui-package-manager.py")
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)

FAKE = r'''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
state = os.environ["FAKE_STATE"]
log = open(os.path.join(state, "calls"), "a")
log.write(" ".join(args) + "\n")
log.close()
cache = os.path.join(state, "cache")
def text(name):
    return open(os.path.join(state, name)).read()
if args[:1] == ["rquery"]:
    sys.exit(0)
if args[:2] == ["config", "PKG_DBDIR"]:
    print(os.path.join(state, "db")); sys.exit(0)
if args[:2] == ["config", "PKG_CACHEDIR"]:
    print(cache); sys.exit(0)
if "-n" in args:                       # a dry run: install, upgrade or delete
    sys.stdout.write(text("plan.txt")); sys.exit(0)
if args[:3] == ["fetch", "-y", "-U"]:
    for i in args[3:]:
        time.sleep(0.05)
        if i in os.environ.get("FAKE_DETERMINISTIC", "").split():
            print(f"pkg: No packages matching '{i}' have been found in the repositories"); sys.exit(1)
        real = os.path.join(cache, f"{i}~2$abc.pkg")
        open(real, "wb").write(b"x" * 1000)
        link = os.path.join(cache, f"{i}.pkg")
        if not os.path.lexists(link):
            os.symlink(os.path.basename(real), link)
    sys.exit(0)
names = [l.split(":")[0].strip() for l in text("plan.txt").splitlines() if l.startswith("\t")]
if args[0] == "install":
    if os.environ.get("FAKE_INSTALL_FAILS"):
        print("pkg: the install failed"); sys.exit(1)
    for n, name in enumerate(names, 1):
        print(f"[{n}/{len(names)}] Installing {name}...")
        print(f"[{n}/{len(names)}] Extracting {name}: .......... done")
    sys.exit(0)
if args[0] == "delete":
    for n, name in enumerate(names, 1):
        print(f"[{n}/{len(names)}] Deinstalling {name}-1.0...")
        print(f"[{n}/{len(names)}] Deleting files for {name}-1.0: .......... done")
    sys.exit(0)
sys.exit(2)
'''


class Fixture(gui.Fixture):
    def setUp(self):
        super().setUp()
        self.state = self.dir / "state"
        (self.state / "cache").mkdir(parents=True)
        (self.state / "db").symlink_to(self.db)
        self.fake = self.state / "pkg"
        self.fake.write_text(FAKE.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))   # a host may have only python3.12
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        os.environ["FAKE_STATE"] = str(self.state)
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in ("FAKE_STATE", "FAKE_DETERMINISTIC", "FAKE_INSTALL_FAILS")])
        key = self.dir / "key.pub"
        key.write_text(gui.KEY)
        self.repo_dir = self.write_repos(**{"r.conf": f'FreeBSD: {{ url: "https://pkg.FreeBSD.org/x", signature_type: "pubkey", pubkey: "{key}" }}\n'
                                                      'Extra: { url: "https://extra.example/y" }\n'})

    def set_plan(self, text):
        (self.state / "plan.txt").write_text(text)

    def calls(self):
        path = self.state / "calls"
        return path.read_text().splitlines() if path.exists() else []

    def approved(self, action, names):
        """The identity the window would have shown: planned with the same catalogue, repositories and pkg."""
        found = catalogue.Catalogue.load(str(self.db))
        return plan.dry_run(action, names, found, repos.read([self.repo_dir]), pkg=(str(self.fake),))

    def go(self, action, names, identity, **kw):
        out = io.StringIO()
        code = transaction.run(action, names, identity, pkg=(str(self.fake),), out=out, dbdir=str(self.db),
                               repos_dirs=[str(self.repo_dir)], **kw)
        return code, out.getvalue().splitlines()


SAFE_INSTALL = gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", "")


class Helper(Fixture):
    def test_install_runs_the_plan_and_reports_in_the_installers_vocabulary(self):
        self.set_plan(SAFE_INSTALL)
        approved = self.approved("install", ["cowsay"])
        code, lines = self.go("install", ["cowsay"], approved.identity)
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[-1][:9], "@@result ")
        done = json.loads(lines[-1][9:])
        self.assertEqual((done["status"], done["identity"]), ("ok", approved.identity))
        self.assertLess(lines.index("@@phase fetch"), lines.index("@@phase install"))
        planned = next(json.loads(l[7:]) for l in lines if l.startswith("@@plan "))
        self.assertEqual((planned["schema"], planned["packages"], planned["archives"]), ("daemonarchy/install-plan@1", 2, 2))
        self.assertEqual(planned["download_bytes"], 40960 + (15 << 20))
        self.assertTrue(any(l.startswith("@@fetch ") for l in lines))
        self.assertIn("[2/2] Extracting perl5: .......... done", lines)
        verbs = [c.split()[0] for c in self.calls()]
        self.assertIn("fetch", verbs)                                    # parallel-fetch's pkg processes
        self.assertEqual(self.calls()[-1], "install -y -U cowsay")       # then the install, from the cache

    def test_the_window_view_of_that_stream_ends_complete(self):
        self.set_plan(SAFE_INSTALL)
        approved = self.approved("install", ["cowsay"])
        _code, lines = self.go("install", ["cowsay"], approved.identity)
        tx = txview.Transaction("install")
        for line in lines:
            tx.feed(line)
        view = tx.view()
        self.assertEqual((view["state"], view["percent"], view["stage_count"]), ("done", 100.0, 2))
        self.assertEqual((view["packages"]["done"], view["packages"]["total"]), (2, 2))
        self.assertEqual(view["bytes"]["done"], view["bytes"]["total"])

    def test_a_changed_plan_is_refused_and_nothing_runs(self):
        self.set_plan(SAFE_INSTALL)
        approved = self.approved("install", ["cowsay"])
        self.set_plan(SAFE_INSTALL.replace("5.42.0", "5.42.1"))             # the catalogue moved after approval
        before = len(self.calls())
        code, lines = self.go("install", ["cowsay"], approved.identity)
        self.assertEqual(code, 3)
        refused = json.loads(lines[-1][9:])
        self.assertEqual((refused["status"], refused["reason"]), ("refused", "plan-changed"))
        self.assertNotEqual(refused["identity"], approved.identity)
        later = [c for c in self.calls()[before:] if not c.startswith(("install -n", "config"))]
        self.assertEqual(later, [], "nothing may fetch or install after a refusal")

    def test_an_unsigned_repository_needs_to_be_named(self):
        self.set_plan(gui.INSTALL)                                            # includes local-tool from Extra
        approved = self.approved("install", ["local-tool"])
        self.assertTrue(approved.needs_confirmation)
        code, lines = self.go("install", ["local-tool"], approved.identity)
        refused = json.loads(lines[-1][9:])
        self.assertEqual((code, refused["reason"], refused["repositories"]), (4, "unsigned-repository", ["Extra"]))
        self.assertFalse([c for c in self.calls() if c.startswith(("fetch", "install -y"))])
        # naming a different repository does not allow this one
        out = io.StringIO()
        code = transaction.run("install", ["local-tool"], approved.identity, allow_unsigned=["FreeBSD"], pkg=(str(self.fake),),
                               out=out, dbdir=str(self.db), repos_dirs=[str(self.repo_dir)])
        self.assertEqual(code, 4)
        code = transaction.run("install", ["local-tool"], approved.identity, allow_unsigned=["Extra"], pkg=(str(self.fake),),
                               out=io.StringIO(), dbdir=str(self.db), repos_dirs=[str(self.repo_dir)])
        self.assertEqual(code, 0)

    def test_a_failed_install_is_reported_as_failed(self):
        self.set_plan(SAFE_INSTALL)
        approved = self.approved("install", ["cowsay"])
        os.environ["FAKE_INSTALL_FAILS"] = "1"
        code, lines = self.go("install", ["cowsay"], approved.identity)
        self.assertEqual(code, 1)
        failed = json.loads(lines[-1][9:])
        self.assertEqual((failed["status"], failed["reason"]), ("failed", "pkg"))
        tx = txview.Transaction("install")
        for line in lines:
            tx.feed(line)
        self.assertEqual(tx.view()["state"], "failed")

    def test_a_download_that_cannot_succeed_stops_before_the_install(self):
        self.set_plan(SAFE_INSTALL)
        approved = self.approved("install", ["cowsay"])
        os.environ["FAKE_DETERMINISTIC"] = "perl5-5.42.0"
        code, lines = self.go("install", ["cowsay"], approved.identity)
        self.assertEqual(code, 5)
        self.assertEqual(json.loads(lines[-1][9:])["reason"], "download")
        self.assertFalse([c for c in self.calls() if c.startswith("install -y")])

    def test_retry_replans_and_reuses_archives_already_fetched(self):
        self.set_plan(SAFE_INSTALL)
        approved = self.approved("install", ["cowsay"])
        os.environ["FAKE_INSTALL_FAILS"] = "1"
        self.go("install", ["cowsay"], approved.identity)
        os.environ.pop("FAKE_INSTALL_FAILS")
        fetches = len([c for c in self.calls() if c.startswith("fetch")])
        code, lines = self.go("install", ["cowsay"], self.approved("install", ["cowsay"]).identity)
        self.assertEqual(code, 0, lines)
        self.assertEqual(len([c for c in self.calls() if c.startswith("fetch")]), fetches, "cached archives are not fetched again")

    def test_remove(self):
        self.set_plan(gui.REMOVE)
        approved = self.approved("remove", ["cowsay"])
        code, lines = self.go("remove", ["cowsay"], approved.identity)
        self.assertEqual(code, 0, lines)
        self.assertNotIn("@@phase fetch", lines)
        self.assertEqual(self.calls()[-1], "delete -y cowsay")
        tx = txview.Transaction("remove")
        for line in lines:
            tx.feed(line)
        view = tx.view()
        self.assertEqual((view["state"], view["stage_count"], view["packages"]["done"], view["packages"]["total"]),
                         ("done", 1, 1, 1))

    def test_an_empty_plan_is_not_run(self):
        self.set_plan("No packages available to install matching 'nosuch' have been found.\n")
        approved = self.approved("install", ["nosuch"])
        code, lines = self.go("install", ["nosuch"], approved.identity)
        refused = json.loads(lines[-1][9:])
        self.assertEqual((code, refused["reason"]), (3, "nothing-to-do"))
        self.assertIn("nosuch", refused["detail"])                    # pkg's own words, not a generic message


class RootSafety(unittest.TestCase):
    """The helper runs as root on arguments a user chose."""

    def test_arguments_that_are_not_plain_names_are_refused(self):
        for bad in (["install", "-fy", "--identity", "0" * 64], ["install", "../x", "--identity", "0" * 64],
                    ["install", "ok", "--identity", "nothex"], ["install", "ok", "--identity", "0" * 64, "--allow-unsigned", "-x"],
                    ["install", "ok", "--identity", "0" * 64, "--workers", "99"], ["install", "--identity", "0" * 64]):
            with self.subTest(bad=bad), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                transaction.main(bad, io.StringIO())
            self.assertEqual(caught.exception.code, 2)

    def test_the_helper_takes_no_option_that_redirects_it(self):
        for option in ("--dbdir", "--repos-dir", "--pkg"):
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                transaction.main(["install", "ok", "--identity", "0" * 64, option, "/tmp/x"], io.StringIO())

    def test_root_ignores_the_engine_directory_a_user_names(self):
        saved = os.environ.get("DAEMONARCHY_PKG_ENGINE")
        os.environ["DAEMONARCHY_PKG_ENGINE"] = "/tmp/attacker"
        try:
            real = os.geteuid
            os.geteuid = lambda: 1000
            try:
                self.assertEqual(engine.search_path()[0], Path("/tmp/attacker"))     # a user's own run may use it
            finally:
                os.geteuid = real
            real = os.geteuid
            os.geteuid = lambda: 0
            try:
                self.assertNotIn(Path("/tmp/attacker"), engine.search_path())
            finally:
                os.geteuid = real
        finally:
            if saved is None:
                os.environ.pop("DAEMONARCHY_PKG_ENGINE")
            else:
                os.environ["DAEMONARCHY_PKG_ENGINE"] = saved

    def test_elevation(self):
        which = lambda name: "/usr/local/bin/sudo"
        self.assertEqual(transaction.elevate(["h", "x"], env={}, euid=0, which=which), ["h", "x"])
        self.assertEqual(transaction.elevate(["h", "x"], env={"SUDO_ASKPASS": "/a"}, euid=1000, which=which),
                         ["/usr/local/bin/sudo", "-A", "h", "x"])
        self.assertEqual(transaction.elevate(["h"], env={}, euid=1000, which=which), ["/usr/local/bin/sudo", "-n", "h"])
        self.assertIsNone(transaction.elevate(["h"], env={}, euid=1000, which=lambda name: None))


class View(unittest.TestCase):
    """The window's numbers while a transaction is under way, with a controlled clock."""

    def setUp(self):
        self.now = 1000.0
        self.tx = txview.Transaction("install", clock=lambda: self.now)

    def feed(self, *lines):
        for line in lines:
            self.tx.feed(line)

    def fetch(self, archives, received, total_file=1000):
        return "@@fetch " + json.dumps(dict(schema="daemonarchy/pkg-fetch@1", archives=archives, bytes=received,
                                            file="f", file_bytes=0, file_total=total_file), separators=(",", ":"))

    def test_nothing_is_shown_as_known_before_it_is(self):
        view = self.tx.view()
        self.assertEqual((view["state"], view["percent"], view["eta"], view["bytes"]["total"]), ("running", None, None, None))

    def test_download_progress_is_measured_and_the_estimate_says_what_it_rests_on(self):
        self.feed("@@phase fetch", '@@plan {"schema":"daemonarchy/install-plan@1","packages":10,"archives":10,'
                  '"download_bytes":100000000,"installed_bytes":300000000}')
        for second, received in enumerate(range(0, 30_000_001, 3_000_000)):
            self.now = 1000.0 + second * 3
            self.feed(self.fetch(second, received))
        view = self.tx.view()
        self.assertEqual((view["bytes"]["done"], view["bytes"]["total"], view["bytes"]["exact"]), (30_000_000, 100_000_000, True))
        self.assertAlmostEqual(view["bytes"]["rate"], 1_000_000, delta=1)
        self.assertEqual(view["stage"], "Download")
        self.assertEqual((view["stage_index"], view["stage_count"]), (1, 2))
        self.assertIsNotNone(view["percent"])
        self.assertLess(view["percent"], 99.0)
        self.assertIn("measured download rate", view["eta_basis"])
        self.assertIn("baseline", view["eta_basis"])                       # the install's share is not measured yet
        self.assertAlmostEqual(view["eta"], 70 + 10 * 152 / 1217, delta=0.5)

    def test_install_counts_extracted_packages_once(self):
        self.feed("@@phase fetch", '@@plan {"schema":"daemonarchy/install-plan@1","packages":3,"archives":3,'
                  '"download_bytes":3000,"installed_bytes":9000}', self.fetch(3, 3000), "@@phase install")
        self.feed("[1/3] Installing a-1...", "[1/3] Extracting a-1: .......... done", "[1/3] Extracting a-1: .......... done",
                  "[2/3] Installing b-1...")
        view = self.tx.view()
        self.assertEqual((view["packages"]["done"], view["packages"]["total"], view["stage"]), (1, 3, "Install"))
        self.assertLess(view["percent"], 100.0)
        self.feed("@@result " + json.dumps(dict(schema=transaction.RESULT_SCHEMA, status="ok", exit=0)))
        self.assertEqual((self.tx.view()["state"], self.tx.view()["percent"]), ("done", 100.0))

    def test_percent_never_exceeds_99_until_the_result(self):
        self.feed("@@phase install", '@@plan {"schema":"daemonarchy/install-plan@1","packages":1,"archives":0,'
                  '"download_bytes":0,"installed_bytes":10}', "[1/1] Extracting a-1: .......... done")
        self.assertLess(self.tx.view()["percent"], 100.0)

    def test_an_unreadable_result_is_a_failure_not_success(self):
        self.feed("@@result {broken")
        self.assertEqual(self.tx.view()["state"], "failed")

    def test_a_refusal_is_its_own_state(self):
        self.feed("@@result " + json.dumps(dict(schema=transaction.RESULT_SCHEMA, status="refused", exit=3, reason="plan-changed")))
        self.assertEqual(self.tx.view()["state"], "refused")


if __name__ == "__main__":
    unittest.main()
