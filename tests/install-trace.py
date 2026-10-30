#!/usr/bin/env python3
"""The installer trace: sampler parsers on real FreeBSD output, pkg-events tracing, library output."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "overlay/usr/local/libexec/daemonarchy-installer"


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(LIB / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


sampler = load("install-trace-sampler")
events = load("pkg-events")

NETSTAT = """Name       Mtu Network         Address               Ipkts Ierrs Idrop       Ibytes     Opkts Oerrs       Obytes  Coll
re0       1500 <Link#1>        7c:57:58:5e:fb:fe   3341004     0     0   3691348460  11158235     0  15070644355     0
re0          - 10.11.100.0/23  10.11.101.233       1762763     -     -   1756916750  10524949     -  14880774384     -
lo0      65535 <Link#2>        lo0                    1751     0     0       786529      1719     0       779329     0
wlan0*    1500 <Link#3>        aa:bb:cc:dd:ee:ff      10     1     0         2048        20     2          4096     0
"""
IOSTAT = """                        extended device statistics
device           r/i         w/i         kr/i         kw/i qlen   tsvc_t/i      sb/i
nda0           368.0         0.0       7985.5          0.0    0        0.0       0.0
ada0       3483396.0    628931.0   95857793.5  104457180.5    0    29001.1   10990.8
pass0            0.0         0.0          0.0          0.0    0        0.0       0.0
"""


class SamplerTests(unittest.TestCase):
    def test_netstat_counters_without_addresses(self):
        nets = sampler.parse_netstat(NETSTAT)
        self.assertEqual(sorted(nets), ["re0", "wlan0"])
        self.assertEqual(nets["re0"]["ibytes"], 3691348460)
        self.assertEqual(nets["re0"]["obytes"], 15070644355)
        self.assertEqual(nets["wlan0"]["oerrs"], 2)
        self.assertNotIn("7c:57", json.dumps(nets))

    def test_iostat_devices(self):
        disks = sampler.parse_iostat(IOSTAT)
        self.assertEqual(sorted(disks), ["ada0", "nda0"])
        self.assertEqual(disks["ada0"]["writes"], 628931)
        self.assertEqual(disks["nda0"]["read_kib"], 7985)

    def test_devd_events_keep_only_names(self):
        self.assertEqual(sampler.parse_devd("+nda0 at pnpinfo vendor=0x1e0f handle=\\_SB_"), {"kind": "attach", "device": "nda0"})
        self.assertEqual(sampler.parse_devd("-ugen0.3 at port=2"), {"kind": "detach", "device": "ugen0.3"})
        row = sampler.parse_devd("!system=IFNET subsystem=re0 type=LINK_UP ssid=Secret")
        self.assertEqual(row, {"kind": "notify", "system": "IFNET", "subsystem": "re0", "type": "LINK_UP"})
        self.assertIsNone(sampler.parse_devd("?something odd"))

    def test_cpu_percent(self):
        self.assertEqual(sampler.cpu_percent([0, 0, 0, 0, 0], [10, 0, 10, 0, 80])["idle"], 80.0)

    def test_deltas_only_for_what_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace"
            trace = sampler.Trace(str(path), 0, now_us=iter(range(1000, 100000, 1000)).__next__)
            before = {"a": dict(ibytes=1, obytes=1), "b": dict(ibytes=5, obytes=5)}
            after = {"a": dict(ibytes=101, obytes=1), "b": dict(ibytes=5, obytes=5)}
            sampler.diff_rows(trace, "net_sample", after, before, 500, ("ibytes", "obytes"))
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual([r["name"] for r in rows], ["a"])
        self.assertEqual(rows[0]["d_ibytes"], 100)


class PkgEventsTraceTests(unittest.TestCase):
    def test_download_and_install_events_get_durations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace"
            ticks = iter(range(10_000_000, 99_000_000, 1_000_000))
            trace = events.Trace(str(path), 9_000_000, now_us=lambda: next(ticks))
            lines = []
            conv = events.Converter(lines.append, clock=lambda: 0.0, trace=trace)
            url = "https://example.invalid/All/tmux-3.8~2$abc.pkg"
            conv.event({"type": "INFO_FETCH_BEGIN", "data": {"url": url}})
            conv.event({"type": "INFO_PROGRESS_TICK", "data": {"current": 5, "total": 10}})
            conv.event({"type": "INFO_FETCH_FINISHED", "data": {"url": url}})
            conv.event({"type": "INFO_EXTRACT", "data": {"pkg": {"name": "tmux"}}})
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        download = next(r for r in rows if r["event"] == "download")
        self.assertEqual((download["name"], download["bytes"]), ("tmux-3.8", 10))
        self.assertGreater(download["dur_us"], 0)
        extract = next(r for r in rows if r["event"] == "pkg_event")
        self.assertEqual((extract["type"], extract["name"]), ("INFO_EXTRACT", "tmux"))
        self.assertFalse(any(r.get("type") == "INFO_PROGRESS_TICK" for r in rows))


def load_script(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(ROOT / "scripts" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class SummaryTests(unittest.TestCase):
    def test_summary_reports_phases_operations_downloads_and_io(self):
        summary = load_script("install-trace-summary.py")
        rows = [
            {"t_us": 1_000_000, "since_start_us": 0, "event": "trace_start", "phase": "none"},
            {"t_us": 2_000_000, "since_start_us": 1_000_000, "event": "op_end", "phase": "disk", "op": "zpool_create", "status": 0, "dur_us": 700_000},
            {"t_us": 3_000_000, "since_start_us": 2_000_000, "event": "phase_end", "phase": "disk", "name": "disk", "dur_us": 2_000_000},
            {"t_us": 4_000_000, "since_start_us": 3_000_000, "event": "download", "name": "a-1", "bytes": 2 * 2**20, "dur_us": 1_000_000},
            {"t_us": 4_500_000, "since_start_us": 3_500_000, "event": "download", "name": "b-1", "bytes": 2 * 2**20, "dur_us": 1_500_000},
            {"t_us": 4_100_000, "since_start_us": 3_100_000, "event": "net_sample", "phase": "fetch", "name": "re0", "d_ibytes": 4 * 2**20, "d_obytes": 0},
            {"t_us": 4_200_000, "since_start_us": 3_200_000, "event": "cpu_sample", "phase": "fetch", "idle": 90.0},
            {"t_us": 5_000_000, "since_start_us": 4_000_000, "event": "pkg_event", "type": "INFO_EXTRACT_BEGIN", "name": "tmux"},
            {"t_us": 5_250_000, "since_start_us": 4_250_000, "event": "pkg_event", "type": "INFO_EXTRACT_FINISHED", "name": "tmux"},
            {"t_us": 6_000_000, "since_start_us": 5_000_000, "event": "exit", "phase": "none", "status": 0, "dur_us": 5_000_000},
        ]
        result = summary.summarise(rows)
        self.assertEqual(result["total_s"], 5.0)
        self.assertEqual(result["phases"], [{"phase": "disk", "s": 2.0}])
        self.assertEqual(result["operations"][0]["op"], "zpool_create")
        self.assertEqual(result["downloads"]["count"], 2)
        self.assertEqual(result["downloads"]["slowest"][0]["name"], "b-1")
        self.assertGreater(result["downloads"]["mean_concurrency"], 1.0)
        self.assertEqual(result["io_by_phase"]["fetch"]["rx_mib"], 4.0)
        self.assertEqual(result["io_by_phase"]["fetch"]["cpu_busy_pct"], 10.0)
        self.assertEqual(result["pkg_events"]["slowest_timed"][0], {"type": "INFO_EXTRACT", "name": "tmux", "s": 0.25})


class LibraryTests(unittest.TestCase):
    def run_bash(self, script):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.jsonl"
            subprocess.run(["bash", "-c", f'source "{LIB}/install-trace"; trace_init "{trace}"; {script}'],
                           check=True, capture_output=True, text=True)
            return [json.loads(line) for line in trace.read_text().splitlines()]

    def test_phase_operation_and_exit_events(self):
        rows = self.run_bash('trace_phase disk; traced zpool_create true; trace_phase base; '
                             'traced bad false || true; trace_finish 0')
        kinds = [(r["event"], r.get("name") or r.get("op")) for r in rows]
        self.assertEqual(kinds[0][0], "trace_start")
        self.assertIn(("op_end", "zpool_create"), kinds)
        self.assertIn(("phase_end", "disk"), kinds)
        bad = next(r for r in rows if r["event"] == "op_end" and r["op"] == "bad")
        self.assertEqual(bad["status"], 1)
        self.assertEqual(rows[-1]["event"], "exit")
        self.assertTrue(all(isinstance(r["t_us"], int) and r["t_us"] > 1_700_000_000_000_000 for r in rows))
        self.assertEqual([r["phase"] for r in rows if r["event"] == "op_end"], ["disk", "base"])

    def test_values_cannot_break_the_line(self):
        rows = self.run_bash('trace_event note text $\'a"b\\\\c\\nd\'')
        self.assertEqual(rows[-1]["text"], 'a"b\\c d')


if __name__ == "__main__":
    unittest.main()
