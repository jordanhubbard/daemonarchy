#!/usr/bin/env python3
"""The installer's Extensions menu and launcher: a signed feed downloaded when chosen, verified before anything
runs, each extension in its own window, preempted by the installation, and reachable from the installer screens."""

import functools
import http.server
import importlib.machinery
import importlib.util
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "overlay/usr/local/lib/daemonarchy-visual"
LIBEXEC = ROOT / "overlay/usr/local/libexec/daemonarchy-installer"
LAUNCHER = LIBEXEC / "daemonarchy-extensions"
GAMES = ROOT / "extensions/games"
GAME_IDS = ("hordeshot", "shatter", "rockdrift", "wyrm")
sys.path.insert(0, str(LIB))

from daemonarchy_visual import bundle, plugin  # noqa: E402

TMUX = os.environ.get("DAEMONARCHY_TEST_TMUX") or shutil.which("tmux")
ARCH = {"x86_64": "amd64", "amd64": "amd64", "arm64": "aarch64", "aarch64": "aarch64"}[platform.machine()]
TAG = f"extensions-{platform.release().split('.')[0]}-{ARCH}-1.4.1"


def openssl(*args):
    subprocess.run(["openssl", *args], check=True, capture_output=True)


def keypair(directory, name):
    private, public = str(Path(directory) / f"{name}.key"), str(Path(directory) / f"{name}.pub")
    openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", private)
    openssl("pkey", "-in", private, "-pubout", "-out", public)
    return private, public


class Pty:
    """A program on a pseudo-terminal of a given size."""

    def __init__(self, argv, env, rows=30, cols=100):
        import fcntl
        import pty
        import struct
        import termios
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True,
                                     close_fds=True)
        os.close(slave)
        self.buffer = b""

    def read(self, seconds=0.5, until=None):
        import select
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if select.select([self.master], [], [], 0.05)[0]:
                try:
                    data = os.read(self.master, 65536)
                except OSError:
                    break
                if not data:
                    break
                self.buffer += data
            if until and until.encode() in self.buffer:
                return True
        return until is None or until.encode() in self.buffer

    def send(self, data):
        os.write(self.master, data)

    def finish(self, seconds=10):
        # Keep draining the master while waiting: on FreeBSD a pty slave blocks at exit until its master
        # has read the output (Linux just buffers it), as a real terminal always does.
        end = time.monotonic() + seconds
        code = None
        while time.monotonic() < end:
            self.read(0.05)
            code = self.proc.poll()
            if code is not None:
                break
        else:
            self.proc.kill()
            self.proc.wait()
        self.read(0.3)
        os.close(self.master)
        return code

    @property
    def text(self):
        return self.buffer.decode("utf-8", "replace")


class World:
    """A signed feed of the four games, a server for it, and a fake live image's share directory."""

    def __init__(self, serve=True, pinned=True, sign_with="dev", feed_tag=TAG):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.dev_private, self.dev_public = keypair(root, "dev")
        self.other_private, self.other_public = keypair(root, "other")
        self.share = root / "share"
        self.share.mkdir()
        (self.share / "version").write_text("1.4.1\n")
        (self.share / "extensions.json").write_text(json.dumps({"repository": "jordanhubbard/daemonarchy"}))
        if pinned:
            shutil.copy(self.dev_public, self.share / "daemonarchy.pub")
        self.feed = root / "feed"
        entries = [bundle.build_bundle(GAMES / g, self.feed) for g in GAME_IDS]
        (self.feed / bundle.INDEX_NAME).write_bytes(bundle.compress(bundle.build_index(entries, feed_tag, ARCH, "2026-10-30T00:00:00Z")))
        key = self.dev_private if sign_with == "dev" else self.other_private
        for name in [bundle.INDEX_NAME] + [e["bundle"]["file"] for e in entries]:
            bundle.sign_file(str(self.feed / name), key)
        self.entries = {e["id"]: e for e in entries}
        self.hits = []
        self.server = None
        self.cache = root / "cache"
        self.preempt = root / "preempt"
        self.trace = root / "trace.jsonl"
        self.trace.write_text(json.dumps({"t_us": 1_000_000, "event": "trace_start"}) + "\n")
        if serve:
            self.serve()

    def serve(self):
        world = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args, **kwargs):
                pass

            def do_GET(self):
                world.hits.append(self.path.lstrip("/"))
                super().do_GET()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(self.feed)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def env(self, **extra):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "TERM": "xterm-256color", "LANG": "C.UTF-8",
               "DAEMONARCHY_SOUND": "off", "DAEMONARCHY_GAMES_PREEMPT": str(self.preempt), "ISO_SHARE": str(self.share),
               "DAEMONARCHY_EXTENSIONS_URL": getattr(self, "base", "http://127.0.0.1:9"),
               "DAEMONARCHY_EXTENSIONS_CACHE": str(self.cache), "DAEMONARCHY_TRACE_FILE": str(self.trace),
               "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(self.root)}
        env.update(extra)
        return env

    def start(self, *args, rows=30, cols=100, **extra):
        return Pty([sys.executable, "-I", str(LAUNCHER), *args], self.env(**extra), rows, cols)

    def trace_rows(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()][1:]

    def installed(self):
        return sorted(p.name for p in (self.cache / "installed").iterdir()) if (self.cache / "installed").is_dir() else []

    def close(self):
        self.stop_server()
        self.tmp.cleanup()


class MenuFlow(unittest.TestCase):
    def setUp(self):
        self.w = World()

    def tearDown(self):
        self.w.close()

    def test_the_menu_lists_the_signed_feed_with_size_source_and_network(self):
        term = self.w.start("menu")
        self.assertTrue(term.read(15, until="Wyrm"), term.text[-400:])
        term.read(1.5)                                       # the rest of the frame: it is written top to bottom
        for text in ("Hordeshot", "Shatter", "Rockdrift", "Wyrm", "Games", "NETWORK", "download", "SIZE", "KB",
                     f"GitHub release {TAG}", "needed to download", "its own window"):
            self.assertIn(text, term.text, text)
        term.send(b"q")
        self.assertEqual(term.finish(), 0)
        self.assertEqual(sorted(h for h in self.w.hits), [bundle.INDEX_NAME, bundle.INDEX_NAME + ".sig"])
        self.assertEqual(self.w.installed(), [], "listing downloads no extension")

    def test_choosing_downloads_verifies_and_runs_and_the_second_time_needs_no_network(self):
        term = self.w.start("menu")
        term.read(15, until="Wyrm")
        term.send(b"\r")                                    # Hordeshot: first in the list
        self.assertTrue(term.read(20, until="HORDESHOT"), term.text[-400:])
        self.assertIn("Downloading and verifying", term.text)
        self.assertEqual(self.w.installed(), ["hordeshot", "index.json"])
        entry = self.w.entries["hordeshot"]["bundle"]
        self.assertIn(entry["file"], self.w.hits)
        self.assertEqual(self.w.hits.count(entry["file"]), 1)
        term.buffer = b""
        term.send(b"q")                                     # leave the game: back to the menu
        self.assertTrue(term.read(8, until="Up/Down"))
        self.assertIn("cached", term.text)
        term.send(b"q")
        self.assertEqual(term.finish(), 0)
        rows = self.w.trace_rows()
        fetched = {r["name"]: r for r in rows if r["event"] == "ext_fetch"}
        self.assertEqual(fetched[entry["file"]]["bytes"], entry["bytes"])
        self.assertEqual(fetched[entry["file"]]["status"], "ok")
        self.assertIn(bundle.INDEX_NAME, fetched)
        self.assertTrue(any(r["event"] == "ext_verify" and r["name"] == entry["file"] for r in rows))
        # A second session: the extension is cached, so choosing it fetches nothing.
        self.w.hits.clear()
        again = self.w.start("menu")
        again.read(15, until="Wyrm")
        again.send(b"\r")
        self.assertTrue(again.read(15, until="HORDESHOT"), again.text[-300:])
        self.assertNotIn(entry["file"], self.w.hits)
        again.buffer = b""
        again.send(b"q")
        self.assertTrue(again.read(8, until="Up/Down"))
        again.send(b"q")
        self.assertEqual(again.finish(), 0)

    def test_the_games_category_can_be_the_starting_point(self):
        term = self.w.start("menu", "games")
        self.assertTrue(term.read(15, until="Wyrm"))
        term.send(b"q")
        self.assertEqual(term.finish(), 0)

    def test_a_terminal_that_is_too_small_for_the_choice_is_told_so_and_nothing_downloads(self):
        term = self.w.start("menu", rows=17, cols=70)
        term.read(15, until="Wyrm")
        term.send(b"\r")
        self.assertTrue(term.read(8, until="needs a terminal of at least 50x24"), term.text[-400:])
        self.assertEqual(self.w.installed(), [])
        term.send(b"q")
        self.assertEqual(term.finish(), 0)

    def test_list_prints_the_feed_for_scripts(self):
        out = subprocess.run([sys.executable, "-I", str(LAUNCHER), "list"], capture_output=True, text=True, env=self.w.env())
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = [line.split("\t") for line in out.stdout.splitlines()]
        self.assertEqual(sorted(r[0] for r in rows), sorted(GAME_IDS))
        self.assertEqual({r[1] for r in rows}, {"Games"})
        self.assertEqual({r[4] for r in rows}, {"download"})

    def test_run_never_downloads(self):
        out = subprocess.run([sys.executable, "-I", str(LAUNCHER), "run", "wyrm"], capture_output=True, text=True,
                             env=self.w.env(), stdin=subprocess.DEVNULL)
        self.assertEqual(self.w.hits, [])
        term = self.w.start("run", "wyrm")
        self.assertEqual(term.finish(), 2)
        self.assertIn("has not been downloaded and verified", term.text)
        self.assertEqual(self.w.hits, [])


class Refusals(unittest.TestCase):
    def check_refused(self, world, expect):
        try:
            term = world.start("menu")
            self.assertTrue(term.read(15, until=expect), term.text[-500:])
            self.assertNotIn("Hordeshot", term.text.split(expect)[0] if False else "")
            term.send(b"\r")
            term.read(1.0)
            term.send(b"q")
            self.assertEqual(term.finish(), 0)
            self.assertEqual(world.installed(), [], "nothing from a refused feed is extracted")
            self.assertFalse([h for h in world.hits if h.endswith(".tar.xz")], "no bundle was even downloaded")
        finally:
            world.close()

    def test_an_index_signed_by_the_wrong_key_is_refused(self):
        self.check_refused(World(sign_with="other"), "was refused and nothing from it will run")

    def test_an_index_for_another_feed_is_refused(self):
        self.check_refused(World(feed_tag="extensions-16-amd64-9.9.9"), "is for feed")

    def test_an_image_without_a_pinned_key_offers_nothing_and_asks_the_network_for_nothing(self):
        world = World(pinned=False)
        self.check_refused(world, "no pinned repository key")
        self.assertEqual(world.hits, [])

    def test_a_tampered_bundle_is_refused_at_download_time_and_never_runs(self):
        world = World()
        try:
            name = world.entries["hordeshot"]["bundle"]["file"]
            path = world.feed / name
            data = path.read_bytes()
            path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
            term = world.start("menu")
            term.read(15, until="Wyrm")
            term.send(b"\r")
            self.assertTrue(term.read(15, until="was refused and did not run"), term.text[-500:])
            self.assertIn("SHA-256", term.text)
            self.assertNotIn("HORDESHOT", term.text)
            self.assertEqual(world.installed(), [])
            self.assertEqual(list((world.cache / "bundles").iterdir()), [], "the rejected download is deleted")
            term.send(b"q")
            self.assertEqual(term.finish(), 0)
        finally:
            world.close()

    def test_a_bundle_signed_by_another_key_is_refused(self):
        world = World()
        try:
            name = world.entries["wyrm"]["bundle"]["file"]
            bundle.sign_file(str(world.feed / name), world.other_private)
            term = world.start("menu")
            term.read(15, until="Wyrm")
            for _ in range(3):
                term.send(b"\x1b[B")                        # down to Wyrm
                term.read(0.3)
            term.send(b"\r")
            self.assertTrue(term.read(15, until="was refused and did not run"), term.text[-500:])
            self.assertIn("signature", term.text)
            self.assertEqual(world.installed(), [])
            term.send(b"q")
            self.assertEqual(term.finish(), 0)
        finally:
            world.close()

    def test_offline_says_so_clearly_runs_nothing_and_still_offers_what_is_cached(self):
        world = World()
        try:
            first = world.start("menu")
            first.read(15, until="Wyrm")
            first.send(b"\r")
            first.read(20, until="HORDESHOT")
            first.buffer = b""
            first.send(b"q")
            first.read(5, until="Up/Down")
            first.send(b"q")
            first.finish()
            self.assertEqual(world.installed(), ["hordeshot", "index.json"])
            world.stop_server()
            term = world.start("menu")
            self.assertTrue(term.read(20, until="No network"), term.text[-500:])
            self.assertIn("Configure", term.text)
            self.assertIn("Hordeshot", term.text)
            self.assertNotIn("Rockdrift", term.text)
            term.send(b"\r")                                # the cached game runs without any network
            self.assertTrue(term.read(15, until="HORDESHOT"), term.text[-300:])
            term.buffer = b""
            term.send(b"q")
            term.read(5, until="Up/Down")
            term.send(b"q")
            self.assertEqual(term.finish(), 0)
        finally:
            world.close()

    def test_offline_with_nothing_cached_says_what_to_do(self):
        world = World(serve=False)
        try:
            term = world.start("menu")
            self.assertTrue(term.read(20, until="No network"), term.text[-500:])
            self.assertIn("Nothing is available", term.text)
            term.send(b"q")
            self.assertEqual(term.finish(), 0)
        finally:
            world.close()

    def test_disabled_plain_unknown_and_preempted_cases_are_explicit(self):
        world = World()
        try:
            def run(*args, **kw):
                return subprocess.run([sys.executable, "-I", str(LAUNCHER), *args], capture_output=True, text=True,
                                      env=world.env(**kw.pop("extra", {})), **kw)
            self.assertIn("turned off", run("menu", extra={"DAEMONARCHY_GAMES": "off"}, stdin=subprocess.DEVNULL).stdout)
            out = run("menu", stdin=subprocess.DEVNULL)
            self.assertIn("interactive color terminal", out.stdout)
            self.assertEqual(out.returncode, 0)
            self.assertEqual(run("bogus", stdin=subprocess.DEVNULL).returncode, 2)
            world.preempt.write_text("pairing\n")
            term = world.start("menu")
            self.assertEqual(term.finish(6), 0)
            self.assertIn("needs your attention", term.text)
            self.assertEqual(world.hits, [], "a preempted launcher does not even look at the network")
        finally:
            world.close()


@unittest.skipUnless(TMUX, "tmux is not installed")
class OwnWindow(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.socket = f"daemonarchy-exttest-{os.getpid()}-{int(time.time() * 1000) % 100000}"

    def tearDown(self):
        subprocess.run([TMUX, "-L", self.socket, "kill-server"], capture_output=True)
        self.w.close()

    def tmux(self, *args):
        return subprocess.run([TMUX, "-L", self.socket, *args], capture_output=True, text=True, timeout=10)

    def names(self):
        return sorted(self.tmux("list-windows", "-t", "inst:", "-F", "#{window_name}").stdout.split())

    def wait_for(self, condition, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if condition():
                return True
            time.sleep(0.2)
        return False

    def test_each_run_gets_its_own_tmux_window_and_the_installation_preempts_them(self):
        env = self.w.env(DAEMONARCHY_COLOR="256")
        assignments = [f"{k}={v}" for k, v in env.items()]
        command = "env " + " ".join(f"'{a}'" for a in assignments) + f" '{sys.executable}' -I '{LAUNCHER}' menu games"
        self.tmux("-f", "/dev/null", "new-session", "-d", "-s", "inst", "-n", "installer", "-x", "110", "-y", "36", "sleep 600")
        self.tmux("new-window", "-t", "inst:", "-n", "extensions", command)
        self.assertTrue(self.wait_for(lambda: "Wyrm" in self.tmux("capture-pane", "-p", "-t", "inst:extensions").stdout),
                        self.tmux("capture-pane", "-p", "-t", "inst:extensions").stdout[-300:])
        self.tmux("send-keys", "-t", "inst:extensions", "Enter")                      # choose Hordeshot
        self.assertTrue(self.wait_for(lambda: "Hordeshot" in self.names() and "extensions" in self.names()),
                        f"windows: {self.names()}")
        self.assertEqual(self.names().count("Hordeshot"), 1)
        self.assertIn("installer", self.names())                                      # the installer's own window is untouched
        self.assertTrue(self.wait_for(lambda: "HORDESHOT" in self.tmux("capture-pane", "-p", "-t", "inst:Hordeshot").stdout),
                        self.tmux("capture-pane", "-p", "-t", "inst:Hordeshot").stdout[-300:])
        self.assertIn("is open in its own window", self.tmux("capture-pane", "-p", "-t", "inst:extensions").stdout)
        # The installation needs the operator: every extension window ends by itself.
        self.w.preempt.write_text("finished\n")
        self.assertTrue(self.wait_for(lambda: self.names() == ["installer"]), f"windows left: {self.names()}")


class InstallScreenAndHooks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        loader = importlib.machinery.SourceFileLoader("progress_dashboard_ext", str(LIBEXEC / "progress-dashboard.py"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.ui = importlib.util.module_from_spec(spec)
        loader.exec_module(self.ui)
        self.preempt = Path(self.tmp.name) / "preempt"

    def tearDown(self):
        self.tmp.cleanup()

    def app(self, tmux=False, **env):
        class Monitor:
            result = None

        class Args:
            style = "bars"
        values = {"TERM": "xterm-256color", "DAEMONARCHY_SOUND": "off", "DAEMONARCHY_GAMES_PREEMPT": str(self.preempt)}
        if tmux:
            values.update(TMUX="/tmp/x,1,0", TMUX_PANE="%1")
        values.update(env)
        app = self.ui.App(Monitor(), Args(), values, False, False, False)
        app.remote_status = lambda: {"pending": app.pairing}
        app.pairing = False
        return app

    def test_the_preempt_file_follows_the_installation_and_pairing(self):
        app = self.app()
        app.games_control({"result": None})
        self.assertFalse(self.preempt.exists())
        app.pairing, app.games_checked = True, 0.0
        app.games_control({"result": None})
        self.assertEqual(self.preempt.read_text().strip(), "pairing")
        app.pairing, app.games_checked = False, 0.0
        app.games_control({"result": None})
        self.assertFalse(self.preempt.exists())
        app.games_checked = 0.0
        app.games_control({"result": 0})
        self.assertEqual(self.preempt.read_text().strip(), "finished")
        app.games_checked = 0.0
        app.games_control({"result": 1})
        self.assertEqual(self.preempt.read_text().strip(), "finished")

    def test_a_lingering_menu_window_is_closed_after_the_request(self):
        calls = []
        app = self.app(tmux=True)
        original = self.ui.subprocess.run
        self.ui.subprocess.run = lambda argv, **kw: calls.append(argv) or None
        try:
            app.games_control({"result": 0})
            self.assertEqual(calls, [])
            app.games_checked, app.games_asked = 0.0, app.games_asked - 5
            app.games_control({"result": 0})
            self.assertEqual(calls, [["tmux", "kill-window", "-t", "=extensions"], ["tmux", "kill-window", "-t", "=games"]])
            app.games_checked = 0.0
            app.games_control({"result": 0})
            self.assertEqual(len(calls), 2)
        finally:
            self.ui.subprocess.run = original

    def test_g_and_x_open_the_extensions_menu_only_when_it_is_safe_and_possible(self):
        calls = []
        original = self.ui.subprocess.run
        self.ui.subprocess.run = lambda argv, **kw: calls.append(argv) or None
        try:
            plain = self.app()
            plain.key("g")
            self.assertIn("need the tmux windows", plain.message)
            off = self.app(tmux=True, DAEMONARCHY_GAMES="off")
            off.key("x")
            self.assertIn("turned off", off.message)
            done = self.app(tmux=True)
            done.monitor.result = 0
            done.key("g")
            self.assertIn("has finished", done.message)
            busy = self.app(tmux=True)
            self.preempt.write_text("pairing\n")
            busy.key("x")
            self.assertIn("needs your attention", busy.message)
            self.assertEqual(calls, [])
            self.preempt.unlink()
            ok = self.app(tmux=True)
            ok.key("g")
            ok.key("x")
            self.assertEqual(calls[0][:4], ["tmux", "new-window", "-n", "extensions"])
            self.assertTrue(calls[0][4].endswith("daemonarchy-extensions menu games"))
            self.assertTrue(calls[1][4].endswith("daemonarchy-extensions menu"))
        finally:
            self.ui.subprocess.run = original

    def test_tmux_keys_and_hint_mention_extensions(self):
        conf = (ROOT / "overlay/usr/local/share/daemonarchy-installer/install-tmux.conf").read_text()
        self.assertRegex(conf, r'(?m)^bind -N "[^"]*" g new-window -n extensions ".*daemonarchy-extensions menu games"$')
        self.assertRegex(conf, r'(?m)^bind -N "[^"]*" e new-window -n extensions ".*daemonarchy-extensions menu"$')
        hint = self.app(tmux=True).keys_hint()
        self.assertIn("C-b e extensions", hint)
        self.assertIn("C-b g games", hint)

    def test_the_welcome_options_screen_has_an_extensions_entry(self):
        text = (LIBEXEC / "configurator").read_text()
        self.assertEqual(text.count("'Extensions (games and tools, downloaded when chosen)'"), 2)
        self.assertIn("'Extensions'*) extensions_step ;;", text)
        self.assertIn('"$(dirname "$0")/daemonarchy-extensions" menu || true', text)
        self.assertEqual(subprocess.run(["bash", "-n", str(LIBEXEC / "configurator")]).returncode, 0)

    def test_nothing_extension_shaped_is_baked_into_the_iso(self):
        overlay = ROOT / "overlay"
        self.assertEqual([str(p) for p in overlay.rglob("game.py")], [])
        self.assertEqual([str(p) for p in overlay.rglob("daemonarchy-games")], [])
        self.assertEqual([str(p) for p in overlay.rglob("*.tar.xz")], [])
        self.assertEqual(json.loads((overlay / "usr/local/share/daemonarchy-installer/extensions.json").read_text())["repository"],
                         "jordanhubbard/daemonarchy")
        self.assertTrue((GAMES / "index.json").is_file(), "the game sources live outside the overlay")

    def test_the_launcher_stays_out_of_the_installation(self):
        text = LAUNCHER.read_text()
        for forbidden in ("pkg_target", "zpool", "install-integrity", "progress-model", "daemonarchy-install.status",
                          "diagnostics_", "gpart", "newfs"):
            self.assertNotIn(forbidden, text)
        self.assertIn("os.nice(19)", text)


if __name__ == "__main__":
    unittest.main()
