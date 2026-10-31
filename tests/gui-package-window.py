#!/usr/bin/env python3
"""daemonarchy-pkg's window logic without a toolkit: the colours, which packages each view lists, and the state
machine of one change from review to result. The GTK drawing is exercised by tests/gui-package-gtk.py."""

import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/daemonarchy-pkg"))

from daemonarchy_pkg import plan, repos, theme, transaction, viewmodel  # noqa: E402

spec = importlib.util.spec_from_file_location("gui_pm_tests", ROOT / "tests/gui-package-manager.py")
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)


class Theme(unittest.TestCase):
    def test_the_fallback_palette_is_the_sdks(self):
        sdk = theme.sdk_palette()
        self.assertIsNotNone(sdk, "the SDK is in the checkout")
        for name, value in theme.FALLBACK.items():
            self.assertEqual(getattr(sdk, name), value, name)
        self.assertEqual(theme.tokens(), theme.FALLBACK)

    def test_every_kind_has_a_chip_style_and_a_label(self):
        text = theme.css()
        for kind in (*theme.KIND, *theme.TRUST, *theme.BADGE):
            self.assertIn(f".chip-{kind} ", text, kind)
            self.assertIn(kind, theme.LABEL, kind)        # colour is never the only carrier of meaning

    def test_text_colours_are_legible_on_the_window_surfaces(self):
        tokens = theme.tokens()
        for background in (theme.BACKGROUND, theme.SURFACE, theme.RAISED):
            for name in ("WHITE", "GRAY", "CYAN", "GREEN", "RED", "YELLOW", "ORANGE"):
                self.assertGreaterEqual(theme.contrast(tokens[name], background), 4.5, (name, background))

    def test_the_selected_sidebar_row_keeps_white_text_legible_across_the_gradient(self):
        for stop in theme.tokens()["LOGO"]:
            self.assertGreaterEqual(theme.contrast((255, 255, 255), stop), 3.0, stop)     # large bold text on a gradient

    def test_contrast_function(self):
        self.assertAlmostEqual(theme.contrast((0, 0, 0), (255, 255, 255)), 21.0, places=1)
        self.assertAlmostEqual(theme.contrast((9, 9, 9), (9, 9, 9)), 1.0, places=2)

    def test_reduced_motion(self):
        self.assertTrue(theme.reduced_motion(None, env={"DAEMONARCHY_REDUCED_MOTION": "1"}))
        self.assertFalse(theme.reduced_motion(None, env={"DAEMONARCHY_REDUCED_MOTION": "0"}))
        self.assertTrue(theme.reduced_motion(False, env={}))      # GTK's gtk-enable-animations is off
        self.assertFalse(theme.reduced_motion(True, env={}))
        self.assertFalse(theme.reduced_motion(None, env={}))

    def test_css_is_self_contained(self):
        text = theme.css()
        self.assertEqual(text.count("{"), text.count("}"))
        self.assertNotIn("url(", text)                            # nothing fetched, no private images


class Fixture(gui.Fixture):
    def setUp(self):
        super().setUp()
        key = self.dir / "key.pub"
        key.write_text(gui.KEY)
        self.repositories = repos.read([self.write_repos(**{
            "r.conf": f'FreeBSD: {{ url: "u", signature_type: "pubkey", pubkey: "{key}", priority: 5 }}\n'
                      'Extra: { url: "v" }\nOff: { url: "w", enabled: no }\n'})])
        self.browser = viewmodel.Browser(self.catalogue, self.repositories, upgrades={"curl"})


class Browsing(Fixture):
    def test_views_and_badges(self):
        rows, total = self.browser.rows("browse", "")
        self.assertEqual(total, len(self.catalogue))
        badges = {r.name: r.badge for r in rows}
        self.assertEqual((badges["curl"], badges["cowsay"], badges["vim"]), ("update", "installed", "available"))
        installed, count = self.browser.rows("installed", "")
        self.assertEqual(([r.name for r in installed], count), (["cowsay", "curl", "zsh"], 3))
        updates, _ = self.browser.rows("updates", "")
        self.assertEqual([r.name for r in updates], ["curl"])
        self.assertEqual([r.name for r in self.browser.rows("installed", "cow")[0]], ["cowsay"])

    def test_limit_reports_the_true_total(self):
        rows, total = self.browser.rows("browse", "", limit=2)
        self.assertEqual((len(rows), total), (2, len(self.catalogue)))

    def test_rows_say_which_repository_would_supply_them_and_whether_it_is_signed(self):
        by_name = {r.name: r for r in self.browser.rows("browse", "")[0]}
        self.assertEqual(by_name["vim"].trust, "signed")
        self.assertEqual(by_name["local-tool"].trust, "unsigned")        # only the Extra repository has it

    def test_a_disabled_repository_does_not_supply_packages(self):
        make = gui.make_repo
        make(self.db / "repos/Off/db", [("only-off", "1", "from the disabled repository", "misc/only-off", 1, 1)])
        loaded = gui.catalogue.Catalogue.load(str(self.db))
        browser = viewmodel.Browser(loaded, self.repositories)
        detail = browser.detail("only-off")
        self.assertEqual(detail.actions, [])
        self.assertIn("no enabled repository", detail.unavailable)

    def test_detail_actions(self):
        self.assertEqual(self.browser.detail("vim").actions, ["install"])
        self.assertEqual(self.browser.detail("cowsay").actions, ["remove"])
        self.assertEqual(self.browser.detail("curl").actions, ["upgrade", "remove"])
        self.assertIsNone(self.browser.detail("nosuch"))
        vim = self.browser.detail("vim")
        self.assertEqual((vim.version, vim.download_bytes, vim.installed_bytes), ("9.1", 9 << 20, 40 << 20))
        self.assertEqual(vim.offers, [("FreeBSD", "9.1", "signed")])

    def test_repository_rows_carry_trust(self):
        rows = {r["name"]: r for r in self.browser.repository_rows()}
        self.assertEqual((rows["FreeBSD"]["trust"], rows["Extra"]["trust"], rows["Off"]["enabled"]), ("signed", "unsigned", False))


class Fake:
    """A stand-in for launch(): records the argv and lets the test play the helper's lines."""

    def __init__(self):
        self.argv, self.terminated = None, False

    def __call__(self, argv, on_line, on_exit):
        self.argv, self.on_line, self.on_exit = argv, on_line, on_exit
        return self

    def terminate(self):
        self.terminated = True


class Sessions(Fixture):
    def planner(self, text):
        return lambda action, names: plan.from_text(action, names, text, self.catalogue, self.repositories)

    def session(self, text=gui.INSTALL, action="install", names=("local-tool",), **kw):
        session = viewmodel.Session(action, names, self.planner(text), helper="/h", elevate=lambda argv: ["sudo", "-A", *argv], **kw)
        session.make_plan()
        return session

    def result(self, status, code, **fields):
        return "@@result " + json.dumps(dict(schema=transaction.RESULT_SCHEMA, status=status, exit=code, **fields))

    def test_a_signed_plan_can_be_approved_and_runs_the_helper_with_its_identity(self):
        session = self.session(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", ""), names=["cowsay"])
        self.assertEqual((session.state, session.can_approve(), session.pending_trust()), ("review", True, []))
        fake = Fake()
        self.assertTrue(session.approve(fake))
        self.assertEqual(fake.argv, ["sudo", "-A", "/h", "install", "--identity", session.plan.identity, "cowsay"])
        self.assertEqual(session.state, "running")

    def test_an_unsigned_repository_blocks_approval_until_it_is_named(self):
        session = self.session()
        self.assertFalse(session.can_approve())
        self.assertEqual([r for r, _ in session.pending_trust()], ["Extra"])
        with self.assertRaises(RuntimeError):
            session.approve(Fake())
        session.allow("Extra")
        self.assertTrue(session.can_approve())
        session.allow("Extra", False)
        self.assertFalse(session.can_approve())
        session.allow("Extra")
        fake = Fake()
        session.approve(fake)
        self.assertEqual(fake.argv[-5:], ["--identity", session.plan.identity, "--allow-unsigned", "Extra", "local-tool"])

    def test_the_stream_drives_the_state_to_done(self):
        session = self.session(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", ""), names=["cowsay"])
        fake = Fake()
        session.approve(fake)
        for line in ("@@phase fetch", "@@phase install", "[1/2] Extracting cowsay-3.04_3: .......... done", self.result("ok", 0, changed={"install": 2})):
            fake.on_line(line)
        fake.on_exit(0)
        self.assertEqual(session.state, "done")
        self.assertEqual(session.view()["percent"], 100.0)

    def test_failure_and_refusal_states(self):
        for status, code, state in (("failed", 1, "failed"), ("refused", 3, "refused")):
            session = self.session(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", ""), names=["cowsay"])
            fake = Fake()
            session.approve(fake)
            fake.on_line(self.result(status, code))
            fake.on_exit(code)
            self.assertEqual(session.state, state)

    def test_a_helper_that_dies_without_a_result_is_a_failure_with_its_last_words(self):
        session = self.session(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", ""), names=["cowsay"])
        fake = Fake()
        session.approve(fake)
        fake.on_line("sudo: no password was provided")
        fake.on_exit(1)
        self.assertEqual(session.state, "failed")
        self.assertIn("no password was provided", session.error)

    def test_cancel_is_offered_only_while_downloading(self):
        session = self.session(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", ""), names=["cowsay"])
        self.assertFalse(session.can_cancel())            # not running yet
        fake = Fake()
        session.approve(fake)
        fake.on_line("@@phase fetch")
        self.assertTrue(session.can_cancel())
        fake.on_line("@@phase install")
        self.assertFalse(session.can_cancel(), "stopping pkg mid-install could leave the system half changed")
        self.assertFalse(session.cancel())
        self.assertFalse(fake.terminated)

    def test_cancel_during_the_download_ends_cancelled_not_failed(self):
        session = self.session(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", ""), names=["cowsay"])
        fake = Fake()
        session.approve(fake)
        fake.on_line("@@phase fetch")
        self.assertTrue(session.cancel())
        self.assertTrue(fake.terminated)
        fake.on_exit(-15)
        self.assertEqual((session.state, session.error), ("cancelled", ""))

    def test_retry_plans_again_and_shows_a_changed_plan(self):
        texts = [gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", "")]
        session = viewmodel.Session("install", ["cowsay"], lambda a, n: plan.from_text(a, n, texts[0], self.catalogue, self.repositories),
                                    helper="/h", elevate=lambda argv: argv)
        session.make_plan()
        first = session.plan.identity
        fake = Fake()
        session.approve(fake)
        fake.on_line(self.result("refused", 3, reason="plan-changed"))
        texts[0] = texts[0].replace("5.42.0", "5.42.1")           # the catalogue moved
        self.assertEqual(session.retry(), "review")
        self.assertNotEqual(session.plan.identity, first)
        self.assertEqual((session.tx, session.cancelled), (None, False))

    def test_no_sudo_is_a_clear_error_not_a_hang(self):
        session = viewmodel.Session("install", ["cowsay"], self.planner(gui.INSTALL.replace("\tlocal-tool: 1.0 [Extra]\n", "")),
                                    helper="/h", elevate=lambda argv: None)
        session.make_plan()
        self.assertFalse(session.approve(Fake()))
        self.assertEqual(session.state, "error")
        self.assertIn("sudo", session.error)

    def test_an_empty_plan_and_a_failing_planner_are_errors(self):
        empty = self.session("Nothing to do.\n", names=["x"])
        self.assertEqual((empty.state, empty.error), ("error", "Nothing to do."))

        def broken(action, names):
            raise OSError("pkg: not found")
        failing = viewmodel.Session("install", ["x"], broken)
        self.assertEqual(failing.make_plan(), "error")
        self.assertIn("not found", failing.error)

    def test_titles(self):
        self.assertEqual(viewmodel.title("remove", ["a", "b"]), "Remove a, b")
        self.assertEqual(viewmodel.title("install", list("abcde")), "Install a, b, c and 2 more")
        self.assertEqual(viewmodel.title("autoremove", []), "Remove unused dependencies")


class Launch(unittest.TestCase):
    def test_lines_and_exit_status_are_delivered(self):
        import threading
        lines, done, event = [], [], threading.Event()
        handle = viewmodel.launch([sys.executable, "-c", "print('one'); print('two'); raise SystemExit(3)"], lines.append,
                                  lambda code: (done.append(code), event.set()))
        self.assertTrue(event.wait(20))
        handle.thread.join(5)
        self.assertEqual((lines, done), (["one", "two"], [3]))

    def test_terminate_stops_a_running_process(self):
        import threading
        done, event = [], threading.Event()
        handle = viewmodel.launch([sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"],
                                  lambda line: None, lambda code: (done.append(code), event.set()))
        handle.terminate()
        self.assertTrue(event.wait(20))
        self.assertNotEqual(done[0], 0)


class Packaging(unittest.TestCase):
    DESKTOP = ROOT / "apps/daemonarchy-pkg/share/applications/daemonarchy-pkg.desktop"

    def entry(self):
        fields = {}
        for line in self.DESKTOP.read_text().splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                fields[key] = value
        return fields

    def test_the_desktop_entry_is_launchable_from_the_apps_menu(self):
        entry = self.entry()
        self.assertEqual(self.DESKTOP.read_text().splitlines()[0], "[Desktop Entry]")
        self.assertEqual((entry["Type"], entry["Terminal"], entry["Name"]), ("Application", "false", "Packages"))
        self.assertEqual(entry["Exec"], "daemonarchy-pkg gui")
        self.assertTrue((ROOT / "apps/daemonarchy-pkg/bin" / entry["Exec"].split()[0]).is_file())
        self.assertIn("PackageManager", entry["Categories"])
        self.assertTrue(entry["Categories"].endswith(";"))
        self.assertEqual(entry["StartupWMClass"], "org.daemonarchy.Pkg")        # the GTK application id

    def test_the_application_id_matches_the_window_source(self):
        self.assertIn("application_id='org.daemonarchy.Pkg'", (ROOT / "apps/daemonarchy-pkg/daemonarchy_pkg/window.py").read_text())

    def test_the_helper_is_found_by_path_not_by_search(self):
        helper = Path(transaction.helper_path())
        self.assertTrue(helper.is_absolute())
        self.assertEqual(helper.name, "daemonarchy-pkg-helper")
        self.assertTrue(helper.is_file())

    def test_the_launchers_are_executable_and_start_with_a_shebang(self):
        for name in ("daemonarchy-pkg", "daemonarchy-pkg-helper"):
            path = ROOT / "apps/daemonarchy-pkg/bin" / name
            self.assertTrue(path.stat().st_mode & 0o111, name)
            self.assertTrue(path.read_text().startswith("#!/usr/bin/env python3"), name)


class Refresh(unittest.TestCase):
    def test_the_helper_has_a_refresh_action_that_takes_no_arguments(self):
        import contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            for bad in (["refresh", "x"], ["refresh", "--identity", "0" * 64]):
                with self.subTest(bad=bad), self.assertRaises(SystemExit) as caught:
                    transaction.main(bad, io.StringIO())
                self.assertEqual(caught.exception.code, 2)

    def test_refresh_reports_in_the_same_vocabulary(self):
        import stat
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "pkg"
            fake.write_text(f"#!{sys.executable}\nimport sys\nprint('Updating FreeBSD repository catalogue...')\n"
                            "sys.exit(int(__import__('os').environ.get('FAKE_FAIL', '0')))\n")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            out = io.StringIO()
            self.assertEqual(transaction.refresh((str(fake),), out), 0)
            self.assertEqual(json.loads(out.getvalue().splitlines()[-1][9:])["status"], "ok")
            import os
            os.environ["FAKE_FAIL"] = "1"
            try:
                out = io.StringIO()
                self.assertEqual(transaction.refresh((str(fake),), out), 1)
                self.assertEqual(json.loads(out.getvalue().splitlines()[-1][9:])["reason"], "refresh")
            finally:
                os.environ.pop("FAKE_FAIL")


if __name__ == "__main__":
    unittest.main()
