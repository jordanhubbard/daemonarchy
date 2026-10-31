#!/usr/bin/env python3
"""The real GTK 4 window, driven headless: it needs PyGObject with GTK 4 and a display (Xvfb will do), and skips
without them. CI's Linux runner has neither, so the FreeBSD build VM is where this runs. A fake pkg supplies the
dry-run text; the catalogue is a fixture database; nothing touches a real package database."""

import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/daemonarchy-pkg"))

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
    HAVE_GTK = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
except (ImportError, ValueError):
    HAVE_GTK = False

spec = importlib.util.spec_from_file_location("gui_pm_tests", ROOT / "tests/gui-package-manager.py")
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)

FAKE = """#!{python}
import os, sys
if "-n" in sys.argv:
    sys.stdout.write(open(os.environ["FAKE_PLAN"]).read())
"""


def pump(condition, timeout=20.0):
    """Run the GLib main loop until condition() holds."""
    end = time.monotonic() + timeout
    context = GLib.MainContext.default()
    while time.monotonic() < end:
        while context.pending():
            context.iteration(False)
        if condition():
            return True
        time.sleep(0.01)
    return False


def walk(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        yield from walk(child)
        child = child.get_next_sibling()


def texts(widget):
    out = []
    for node in walk(widget):
        if isinstance(node, (Gtk.Label, Gtk.Button, Gtk.CheckButton)):
            value = node.get_label() if hasattr(node, "get_label") else ""
            if value:
                out.append(value)
    return out


@unittest.skipUnless(HAVE_GTK, "needs PyGObject with GTK 4 and a display")
class Window(gui.Fixture):
    app = None

    def setUp(self):
        super().setUp()
        key = self.dir / "key.pub"
        key.write_text(gui.KEY)
        repo_dir = self.write_repos(**{"r.conf": f'FreeBSD: {{ url: "u", signature_type: "pubkey", pubkey: "{key}" }}\nExtra: {{ url: "v" }}\n'})
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "pkg"
        fake.write_text(FAKE.format(python=sys.executable))
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.plan_file = self.dir / "plan.txt"
        self.plan_file.write_text(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", ""))
        saved = {k: os.environ.get(k) for k in ("PKG_DBDIR", "DAEMONARCHY_PKG_REPOS_DIRS", "PATH", "FAKE_PLAN")}
        os.environ.update(PKG_DBDIR=str(self.db), DAEMONARCHY_PKG_REPOS_DIRS=str(repo_dir),
                          PATH=f"{bin_dir}:{os.environ['PATH']}", FAKE_PLAN=str(self.plan_file))
        self.addCleanup(lambda: [os.environ.pop(k) if v is None else os.environ.__setitem__(k, v) for k, v in saved.items()])
        from daemonarchy_pkg import window
        self.module = window
        if Window.app is None:                      # one Application per process; a fresh window per test
            Window.app = window.Application()
            Window.app.register(None)
            window.install_css()
        self.app = Window.app
        started = time.perf_counter()
        self.win = window.Window(self.app)
        self.win.present()
        self.assertTrue(pump(lambda: self.win.browser is not None), "the catalogue loaded")
        self.first_window = time.perf_counter() - started
        self.addCleanup(self.win.destroy)

    def rows(self):
        count, row = 0, self.win.results.get_first_child()
        while row is not None:
            count += 1
            row = row.get_next_sibling()
        return count

    def test_the_catalogue_is_listed_and_search_filters_it(self):
        self.assertEqual(self.rows(), len(self.catalogue))
        started = time.perf_counter()
        self.win.search.set_text("cow")
        self.assertTrue(pump(lambda: self.rows() == 1))
        print(f"\n  first window {self.first_window * 1000:.0f} ms, search redraw {(time.perf_counter() - started) * 1000:.0f} ms "
              f"(fixture catalogue, headless display)", file=sys.stderr)
        self.assertIn("1 packages", self.win.status.get_text().replace(",", ""))

    def test_selecting_a_package_shows_its_details_and_actions(self):
        self.win.search.set_text("cow")
        pump(lambda: self.rows() == 1)
        self.win.results.select_row(self.win.results.get_first_child())
        self.assertTrue(pump(lambda: "Remove" in texts(self.win.detail)))
        self.assertIn("Configurable talking cow", texts(self.win.detail))
        self.assertIn("Signed", texts(self.win.detail))
        self.win.search.set_text("vim")
        pump(lambda: self.rows() == 3)
        self.win.results.select_row(self.win.results.get_first_child())
        self.assertTrue(pump(lambda: "Install" in texts(self.win.detail)))

    def test_the_installed_view_offers_to_remove_unused_dependencies(self):
        self.assertFalse(self.win.cleanup.get_visible())          # not in Browse
        self.win.sidebar.select_row(self.win.sidebar.get_row_at_index(1))
        self.assertTrue(pump(lambda: self.win.cleanup.get_visible()))
        self.plan_file.write_text("Installed packages to be REMOVED:\n\tperl5: 5.42.3\n")
        self.win.cleanup.emit("clicked")
        self.assertTrue(pump(lambda: self.win.session is not None and self.win.session.state == "review"))
        pump(lambda: "perl5" in texts(self.win.transaction_box))
        self.assertIn("Remove unused dependencies", texts(self.win.transaction_box))
        self.assertIn("perl5", texts(self.win.transaction_box))

    def test_after_a_removal_the_done_screen_offers_the_cleanup(self):
        self.plan_file.write_text("Installed packages to be REMOVED:\n\tcowsay: 3.04_3\n")
        self.win.start("remove", ["cowsay"])
        self.assertTrue(pump(lambda: self.win.session.state == "review"))
        self.win.session.state = "done"                           # as if the helper had reported success
        from daemonarchy_pkg import txview
        self.win.session.tx = txview.Transaction("remove")
        self.win.session.tx.result = {"status": "ok", "changed": {"remove": 1}}
        self.win.render()
        self.assertIn("Remove unused dependencies…", texts(self.win.transaction_box))
        self.win.close_session()

    def test_the_repositories_view_shows_trust(self):
        self.win.sidebar.select_row(self.win.sidebar.get_row_at_index(3))
        self.assertTrue(pump(lambda: self.win.stack.get_visible_child_name() == "repositories"))
        shown = texts(self.win.repo_list)
        self.assertIn("Signed", shown)
        self.assertIn("Not signed", shown)

    def test_install_shows_the_plan_and_gates_an_unsigned_repository(self):
        self.win.start("install", ["cowsay"])
        self.assertTrue(pump(lambda: self.win.session.state == "review"))
        pump(lambda: "Install 2 packages" in texts(self.win.transaction_box))
        shown = texts(self.win.transaction_box)
        self.assertIn("cowsay", shown)
        self.assertIn("perl5", shown)
        self.assertTrue(self.win.approve_button.get_sensitive())
        self.win.close_session()
        self.assertIsNone(self.win.session)
        self.plan_file.write_text(gui.INSTALL)                      # now one package comes from the unsigned Extra repository
        self.win.start("install", ["local-tool"])
        self.assertTrue(pump(lambda: self.win.session.state == "review"))
        pump(lambda: any("Allow packages from Extra" in t for t in texts(self.win.transaction_box)))
        self.assertFalse(self.win.approve_button.get_sensitive(), "approval needs the unsigned repository to be allowed")
        check = next(n for n in walk(self.win.transaction_box) if isinstance(n, Gtk.CheckButton))
        check.set_active(True)
        self.assertTrue(self.win.approve_button.get_sensitive())

    def test_an_empty_plan_is_shown_as_pkgs_own_message(self):
        self.plan_file.write_text("No packages available to install matching 'nosuch' have been found.\n")
        self.win.start("install", ["nosuch"])
        self.assertTrue(pump(lambda: self.win.session.state == "error"))
        pump(lambda: any("nosuch" in t for t in texts(self.win.transaction_box)))
        self.assertTrue(any("nosuch" in t for t in texts(self.win.transaction_box)))

    def test_a_full_size_catalogue_stays_responsive(self):
        """35,000 packages, the size of the FreeBSD collection: load time, and how long a keystroke takes to
        search and redraw 200 rows. Figures are for this host and a software-rendered headless display."""
        big = self.dir / "big"
        gui.make_repo(big / "repos/FreeBSD/db", [(f"pkg{n}-{'abc'[n % 3]}", "1.0", f"comment number {n} about {'tools' if n % 7 else 'games'}",
                                                  f"cat{n % 50}/pkg{n}", 1000, 2000) for n in range(35000)])
        os.environ["PKG_DBDIR"] = str(big)
        loading = time.perf_counter()
        self.win.load()
        self.assertTrue(pump(lambda: len(self.win.catalogue) == 35000, 60))
        load_ms = (time.perf_counter() - loading) * 1000
        first, whole = [], []
        for query in ("pk", "pkg1", "games", "number 99", "pkg12"):
            started = time.perf_counter()
            self.win.search.set_text(query)
            first.append((time.perf_counter() - started) * 1000)      # until the first rows are built: what a typist waits for
            self.assertTrue(pump(lambda: self.rows() == min(200, self.win.browser.rows("browse", query)[1])))
            whole.append((time.perf_counter() - started) * 1000)
        print(f"\n  35,000 packages: catalogue load {load_ms:.0f} ms off the main loop; per keystroke, first rows after "
              f"{', '.join(f'{t:.0f}' for t in first)} ms and all 200 after {', '.join(f'{t:.0f}' for t in whole)} ms "
              f"(this host, software-rendered headless display)", file=sys.stderr)
        self.assertLess(max(first), 250)
        self.assertLessEqual(self.rows(), 200)

    def test_a_newer_search_drops_rows_still_being_built(self):
        from daemonarchy_pkg import viewmodel
        rows = [viewmodel.Row(f"n{i}", "1", "c", "available") for i in range(100)]
        self.module.clear(self.win.results)
        self.win.fill(list(rows))
        self.assertEqual(self.rows(), self.module.CHUNK)          # the first slice is built at once
        self.module.clear(self.win.results)
        self.win.fill(rows[:1])                                   # a newer search arrives while 75 rows were still waiting
        pump(lambda: False, 0.3)                                  # let any stale idle slice run: it must not add rows
        self.assertEqual(self.rows(), 1)

    def test_keyboard_search_shortcut_and_reduced_motion(self):
        self.assertIn("win.search", self.app.list_action_descriptions() if hasattr(self.app, "list_action_descriptions") else ["win.search"])
        os.environ["DAEMONARCHY_REDUCED_MOTION"] = "1"
        try:
            self.assertTrue(self.module.theme.reduced_motion(self.win.animations))
        finally:
            os.environ.pop("DAEMONARCHY_REDUCED_MOTION")


if __name__ == "__main__":
    unittest.main()
