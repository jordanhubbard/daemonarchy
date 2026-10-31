#!/usr/bin/env python3
"""The login-to-desktop recorder: parsing, milestones, deltas, rotation and installer wiring."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBEXEC = ROOT / "overlay/usr/local/libexec/daemonarchy-installer"
RC = ROOT / "overlay/usr/local/share/daemonarchy-installer/login-trace/daemonarchy_login_trace"

loader = importlib.machinery.SourceFileLoader("login_trace", str(LIBEXEC / "login-trace"))
spec = importlib.util.spec_from_loader(loader.name, loader)
trace = importlib.util.module_from_spec(spec)
loader.exec_module(trace)

SDDM = 219
USER = 1001


def row(comm, uid, args="", pid=100, ppid=1):
    return dict(pid=pid, ppid=ppid, uid=uid, comm=comm, args=args or comm)


class ParseTests(unittest.TestCase):
    def test_ps_rows_split_into_fields_and_junk_is_skipped(self):
        text = ("  PID  PPID  UID COMMAND         COMMAND\n"
                "  6425     1   219 Hyprland        /usr/local/bin/Hyprland --watchdog-fd 4\n"
                "  7065  7061  1001 Hyprland        Hyprland --watchdog-fd 4\n"
                "garbage line\n"
                "     1     0     0 init            /sbin/init\n")
        rows = trace.parse_ps(text)
        self.assertEqual([r["comm"] for r in rows], ["Hyprland", "Hyprland", "init"])
        self.assertEqual(rows[0]["uid"], 219)
        self.assertEqual(rows[1]["args"], "Hyprland --watchdog-fd 4")


class RecorderTests(unittest.TestCase):
    def test_greeter_and_user_sessions_are_told_apart(self):
        rec = trace.Recorder(SDDM)
        rec.observe([row("sddm", 0), row("Hyprland", SDDM),
                     row("sddm-helper", 0, "sddm-helper --socket /x --id 0 --start start-hyprland --user sddm --greeter")], 1_000_000)
        self.assertEqual(set(rec.events), {"sddm", "greeter_compositor", "greeter_ready"})
        self.assertNotIn("user_compositor", rec.events)
        rec.observe([row("sddm-helper", 0, "sddm-helper --socket /x --id 1 --start uwsm start --user jkh")], 2_000_000)
        self.assertEqual(rec.events["login"], 2_000_000)

    def test_full_login_gives_deltas_from_the_login_in_milliseconds(self):
        rec = trace.Recorder(SDDM)
        rec.mark("boot", 0)
        rec.observe([row("sddm-helper", 0, "sddm-helper --id 1 --start uwsm start --user jkh")], 10_000_000)
        rec.observe([row("ck-launch-sessi", USER, "ck-launch-session -- /usr/local/libexec/omarchy/compat/uwsm start")], 10_100_000)
        rec.observe([row("dbus-run-sessio", USER, "dbus-run-session -- uwsm start")], 13_000_000)
        rec.observe([row("Hyprland", USER)], 13_050_000)
        rec.observe([row("Hyprland", USER), row("quickshell", USER)], 14_000_000, wayland_socket=True)
        self.assertFalse(rec.done())
        rec.observe([row("Hyprland", USER), row("Xwayland", USER)], 15_000_000)
        rec.observe([], 20_000_000, monitor_ready=True)
        self.assertTrue(rec.done())
        out = rec.record(0, True)
        self.assertEqual(out["schema"], "daemonarchy/login-trace@1")
        self.assertTrue(out["complete"])
        self.assertEqual(out["since_login_ms"]["ck_launch_session"], 100)
        self.assertEqual(out["since_login_ms"]["dbus_run_session"], 3000)
        self.assertEqual(out["since_login_ms"]["user_compositor"], 3050)
        self.assertEqual(out["since_login_ms"]["monitor_ready"], 10000)
        self.assertNotIn("login", out["since_login_ms"])
        self.assertNotIn("boot", out["since_login_ms"])
        self.assertEqual(list(out["since_login_ms"]), sorted(out["since_login_ms"], key=out["since_login_ms"].get))

    def test_first_sighting_wins(self):
        rec = trace.Recorder(SDDM)
        rec.observe([row("Hyprland", USER)], 5)
        rec.observe([row("Hyprland", USER)], 9)
        self.assertEqual(rec.events["user_compositor"], 5)

    def test_the_sddm_user_is_never_a_user_session(self):
        rec = trace.Recorder(SDDM)
        rec.observe([row("quickshell", SDDM), row("Xwayland", SDDM)], 1)
        self.assertEqual(rec.events, {})

    def test_no_command_line_reaches_the_record(self):
        rec = trace.Recorder(SDDM)
        rec.observe([row("sddm-helper", 0, "sddm-helper --start uwsm --user jkh secret-token-12345")], 1)
        self.assertNotIn("secret-token", json.dumps(rec.record(0, False)))


class WriteTests(unittest.TestCase):
    def test_records_append_and_the_file_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "trace.jsonl")
            for i in range(trace.KEEP_LINES + 25):
                trace.write({"n": i}, path)
            lines = Path(path).read_text().splitlines()
            self.assertEqual(len(lines), trace.KEEP_LINES)
            self.assertEqual(json.loads(lines[-1]), {"n": trace.KEEP_LINES + 24})


class WiringTests(unittest.TestCase):
    def test_rc_script_parses_and_installer_installs_both_files(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(RC)]).returncode, 0)
        text = RC.read_text()
        self.assertIn("# BEFORE: sddm", text)
        # The recorder runs under /usr/local/bin/python3.12, whose libpython is found only
        # through the loader hints that /etc/rc.d/ldconfig builds. Both scripts require only
        # FILESYSTEMS, so without this rcorder may start the recorder first and python3.12
        # fails with "libpython3.12.so.1.0 not found" (seen on an MSI Raider 18 HX at boot).
        self.assertRegex(text, r"(?m)^# REQUIRE: .*\bldconfig\b")
        self.assertIn('daemonarchy_login_trace_enable:="YES"', text)
        installer = (LIBEXEC / "install").read_text()
        self.assertIn('"$TARGET/usr/local/libexec/daemonarchy-login-trace"', installer)
        self.assertIn('"$TARGET/usr/local/etc/rc.d/daemonarchy_login_trace"', installer)
        self.assertTrue((LIBEXEC / "login-trace").stat().st_mode & 0o100)


if __name__ == "__main__":
    unittest.main()
