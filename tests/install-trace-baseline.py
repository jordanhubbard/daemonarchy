#!/usr/bin/env python3
"""Baseline records and run comparison built from installer traces."""

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("baseline", str(ROOT / "scripts/install-trace-baseline.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
tool = importlib.util.module_from_spec(spec)
loader.exec_module(tool)


def trace(fetch_s, install_s, status=0, finish=True, workers=1):
    rows = [{"t_us": 1_000_000, "since_start_us": 0, "event": "trace_start", "phase": "none"}]
    clock = 1_000_000

    def add(event, **fields):
        nonlocal clock
        clock += fields.pop("advance", 1000)
        rows.append({"t_us": clock, "since_start_us": clock - 1_000_000, "event": event, "phase": "none", **fields})

    add("op_end", op="zpool_create", status=0, dur_us=500_000, phase="disk")
    add("phase_end", name="disk", dur_us=2_000_000)
    for n in range(4):
        add("download", name=f"p{n}-1", bytes=4 * 2**20, dur_us=int(fetch_s * 1e6 / 4 * workers), worker=n % workers)
    add("phase_end", name="fetch", dur_us=int(fetch_s * 1e6))
    add("phase_end", name="install", dur_us=int(install_s * 1e6))
    if finish:
        add("phase_end", name="finish", dur_us=1_000_000)
    add("exit", status=status, dur_us=int((2 + fetch_s + install_s + 1) * 1e6))
    return rows


def write(directory, name, rows):
    path = Path(directory) / name
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


class BaselineTests(unittest.TestCase):
    def test_build_records_context_digest_and_completeness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "t.jsonl", trace(100, 10))
            record = tool.build(path, tool.parse_context(["kind=virtual", "machine=qemu", "link=1 MiB/s"]), "2026-10-30T00:00:00Z")
        self.assertEqual(record["schema"], "daemonarchy/install-baseline@1")
        self.assertEqual(len(record["trace"]["sha256"]), 64)
        self.assertTrue(record["completeness"]["complete_install"])
        self.assertFalse(record["acceptance"]["installation_acceptance_granted"])
        self.assertEqual({p["phase"] for p in record["summary"]["phases"]}, {"disk", "fetch", "install", "finish"})

    def test_context_accepts_only_known_keys_and_plain_values(self):
        for bad in (["kind=virtual", "password=x"], ["kind=virtual", "note=$(rm -rf /)"], ["machine=x"], ["kind=maybe"]):
            with self.assertRaises(ValueError):
                tool.parse_context(bad)

    def test_failed_run_is_marked_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = tool.build(write(tmp, "t.jsonl", trace(10, 0, status=1, finish=False)), {"kind": "physical"})
        self.assertFalse(record["completeness"]["complete_install"])
        self.assertEqual(record["completeness"]["terminal_status"], 1)

    def test_compare_reports_deltas_and_flags_regressions(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ["kind=virtual", "machine=qemu"]
            base = tool.build(write(tmp, "a.jsonl", trace(100, 10)), tool.parse_context(ctx))
            fast = tool.build(write(tmp, "b.jsonl", trace(20, 10, workers=4)), tool.parse_context(ctx + ["workers=4"]))
            slow = tool.build(write(tmp, "c.jsonl", trace(100, 30)), tool.parse_context(ctx))
        better = tool.compare(base, fast)
        self.assertEqual(better["phases"]["fetch"]["delta_s"], -80.0)
        self.assertEqual(better["phases"]["fetch"]["delta_pct"], -80.0)
        self.assertEqual(better["regressions"], [])
        self.assertTrue(any("workers differs" in w for w in better["warnings"]))
        worse = tool.compare(base, slow)
        self.assertTrue(any(r.startswith("phases install") for r in worse["regressions"]))
        self.assertIn("REGRESSION", tool.render(worse))

    def test_compare_accepts_raw_traces_and_gates_on_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = write(tmp, "a.jsonl", trace(100, 10)), write(tmp, "b.jsonl", trace(100, 30))
            self.assertEqual(tool.main(["compare", str(a), str(b)]), 0)
            self.assertEqual(tool.main(["compare", str(a), str(b), "--fail-on-regression"]), 1)
            self.assertEqual(tool.main(["compare", str(a), str(a), "--fail-on-regression"]), 0)

    def test_a_raw_trace_can_be_labelled_so_the_next_run_compares_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = ["kind=physical", "machine=MSI", "link=wired", "cache_mode=network", "workers=1"]
            baseline = tool.build(write(tmp, "a.jsonl", trace(100, 10)), tool.parse_context(ctx))
            path = write(tmp, "b.jsonl", trace(20, 10, workers=4))
            base = Path(tmp) / "base.json"
            base.write_text(json.dumps(baseline))
            candidate = ["kind=physical", "machine=MSI", "link=wired", "cache_mode=network", "workers=16"]
            out = tool.compare(tool.load_record(base), tool.load_record(path, candidate))
            self.assertEqual([w for w in out["warnings"] if "differs" in w], ["context workers differs ('1' vs '16'): not an equivalent comparison"])
            self.assertEqual(tool.main(["compare", str(base), str(path), "--candidate-context", *candidate, "--json"]), 0)
            with self.assertRaises(SystemExit):
                tool.main(["compare", str(base), str(path), "--candidate-context", "password=x"])

    def test_comparison_warns_when_a_run_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            full = tool.build(write(tmp, "a.jsonl", trace(10, 10)), {"kind": "physical"})
            part = tool.build(write(tmp, "b.jsonl", trace(10, 0, status=1, finish=False)), {"kind": "physical"})
        self.assertTrue(any("not a complete install" in w for w in tool.compare(full, part)["warnings"]))


class CuratedRecordTests(unittest.TestCase):
    def test_every_record_matches_its_trace_and_grants_nothing(self):
        import hashlib
        import lzma
        directory = ROOT / "verification/install-baselines"
        records = sorted(directory.glob("*-development.json"))
        self.assertTrue(records)
        for record_path in records:
            record = json.loads(record_path.read_text())
            self.assertEqual(record["schema"], "daemonarchy/install-baseline@1", record_path.name)
            trace = directory / (record_path.name[: -len("-development.json")] + ".trace.jsonl.xz")
            data = lzma.open(trace).read()
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["trace"]["sha256"], record_path.name)
            self.assertEqual(len(data), record["trace"]["bytes"], record_path.name)
            self.assertFalse(record["acceptance"]["installation_acceptance_granted"])
            self.assertTrue(set(record["context"]) <= set(tool.CONTEXT_KEYS))
            text = data.decode()
            for secret in ("password", "psk", "passphrase"):
                self.assertNotIn(secret, text.lower(), f"{record_path.name} mentions {secret}")


if __name__ == "__main__":
    unittest.main()
