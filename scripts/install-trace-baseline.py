#!/usr/bin/env python3
"""Curate installer traces into baseline records and compare runs against them.

  install-trace-baseline.py build TRACE.jsonl --context key=value... [--output FILE]
  install-trace-baseline.py compare BASELINE CANDIDATE [--threshold PCT] [--json]
                                    [--fail-on-regression]

`build` turns a trace (docs/install-trace.md) into a baseline record,
schema daemonarchy/install-baseline@1: the trace's SHA-256 and size, the
context it was measured in, how far the run got, and the summary that
scripts/install-trace-summary.py computes (phases, operations, downloads,
I/O per phase, network probes). The raw trace is not embedded; keep it beside
the record and the digest binds them.

`compare` takes two records or raw traces and reports, per phase and per
operation, the baseline and candidate seconds, the difference and the change in
percent, then the download totals (throughput, mean concurrency). It warns when
the two runs were not measured in comparable contexts and never grants
acceptance: a record from a failed or partial run says so in `completeness`.
With --fail-on-regression it exits 1 when a phase or operation that took at
least a second in the baseline got more than THRESHOLD percent slower
(default 10).

Context keys: kind (physical, virtual, benchmark), machine, storage, link,
image, cache_mode, workers, note. Values are short plain text; nothing else is
accepted, so a record cannot carry a credential or a path by accident.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

SCHEMA = "daemonarchy/install-baseline@1"
CONTEXT_KEYS = ("kind", "machine", "storage", "link", "image", "cache_mode", "workers", "note")
VALUE = re.compile(r"^[A-Za-z0-9 ._:/+,()=-]{1,160}$")
COMPARABLE = ("kind", "machine", "storage", "link", "cache_mode", "workers")

_spec = importlib.util.spec_from_file_location("install_trace_summary", Path(__file__).with_name("install-trace-summary.py"))
summary_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(summary_module)


def parse_context(items):
    context = {}
    for item in items:
        key, _, value = item.partition("=")
        if key not in CONTEXT_KEYS:
            raise ValueError(f"unknown context key {key!r}; allowed: {', '.join(CONTEXT_KEYS)}")
        if not VALUE.match(value):
            raise ValueError(f"context value for {key} must be short plain text")
        context[key] = value
    if context.get("kind") not in ("physical", "virtual", "benchmark"):
        raise ValueError("context kind must be physical, virtual or benchmark")
    return context


def build(trace_path, context, recorded_utc=None):
    data = Path(trace_path).read_bytes()
    rows = summary_module.load(trace_path)
    summary = summary_module.summarise(rows)
    phases = [p["phase"] for p in summary["phases"]]
    exits = [r for r in rows if r["event"] == "exit"]
    return {
        "schema": SCHEMA,
        "recorded_utc": recorded_utc or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "trace": {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "events": len(rows)},
        "context": context,
        "completeness": {
            "terminal_status": exits[-1]["status"] if exits else None,
            "phases_seen": phases,
            "complete_install": bool(exits and exits[-1]["status"] == 0 and "finish" in phases),
        },
        "summary": summary,
        "acceptance": {"equivalent_link_baseline": False, "installation_acceptance_granted": False},
    }


def load_record(path):
    text = Path(path).read_text()
    try:
        record = json.loads(text)
        if isinstance(record, dict) and record.get("schema") == SCHEMA:
            return record
    except json.JSONDecodeError:
        pass
    return build(path, {"kind": "benchmark", "note": "raw trace"})


def by_name(rows, key):
    totals = defaultdict(lambda: [0.0, 0])
    for row in rows:
        totals[row[key]][0] += row["s"]
        totals[row[key]][1] += 1
    return {name: dict(s=round(s, 3), count=count) for name, (s, count) in totals.items()}


def delta(base, cand):
    change = round(cand - base, 3)
    percent = round(100 * change / base, 1) if base else None
    return dict(baseline_s=base, candidate_s=cand, delta_s=change, delta_pct=percent)


def compare(baseline, candidate, threshold=10.0):
    a, b = baseline["summary"], candidate["summary"]
    warnings = []
    for key in COMPARABLE:
        x, y = baseline["context"].get(key), candidate["context"].get(key)
        if x != y:
            warnings.append(f"context {key} differs ({x!r} vs {y!r}): not an equivalent comparison")
    for label, record in (("baseline", baseline), ("candidate", candidate)):
        if not record["completeness"]["complete_install"]:
            warnings.append(f"{label} is not a complete install (phases: {', '.join(record['completeness']['phases_seen']) or 'none'})")
    result = {"warnings": warnings, "total": delta(a["total_s"], b["total_s"])}
    phases_a, phases_b = {p["phase"]: p["s"] for p in a["phases"]}, {p["phase"]: p["s"] for p in b["phases"]}
    result["phases"] = {n: delta(phases_a.get(n, 0.0), phases_b.get(n, 0.0)) for n in sorted(set(phases_a) | set(phases_b))}
    ops_a, ops_b = by_name(a["operations"], "op"), by_name(b["operations"], "op")
    result["operations"] = {n: delta(ops_a.get(n, {"s": 0.0})["s"], ops_b.get(n, {"s": 0.0})["s"])
                            for n in sorted(set(ops_a) | set(ops_b))}
    da, db = a["downloads"], b["downloads"]
    result["downloads"] = {
        "archives": (da["count"], db["count"]),
        "mib_per_s": (da.get("mean_mib_per_s"), db.get("mean_mib_per_s")),
        "mean_concurrency": (da.get("mean_concurrency"), db.get("mean_concurrency")),
        "wall_s": (da.get("wall_s"), db.get("wall_s")),
    }
    regressions = [f"{kind} {name}: {row['baseline_s']}s -> {row['candidate_s']}s ({row['delta_pct']:+}%)"
                   for kind in ("phases", "operations") for name, row in result[kind].items()
                   if row["baseline_s"] >= 1.0 and row["delta_pct"] is not None and row["delta_pct"] > threshold]
    result["regressions"] = regressions
    return result


def render(result):
    lines = [f"warning: {w}" for w in result["warnings"]]
    t = result["total"]
    lines.append(f"total: {t['baseline_s']} s -> {t['candidate_s']} s ({t['delta_pct']:+}%)" if t["delta_pct"] is not None
                 else f"total: {t['baseline_s']} s -> {t['candidate_s']} s")
    for kind in ("phases", "operations"):
        lines.append(f"{kind}:")
        for name, row in sorted(result[kind].items(), key=lambda kv: -abs(kv[1]["delta_s"])):
            pct = f"{row['delta_pct']:+}%" if row["delta_pct"] is not None else "new"
            lines.append(f"  {name:<30} {row['baseline_s']:>9} -> {row['candidate_s']:>9}  {row['delta_s']:+9.3f} s  {pct}")
    d = result["downloads"]
    lines.append(f"downloads: archives {d['archives'][0]} -> {d['archives'][1]}, MiB/s {d['mib_per_s'][0]} -> {d['mib_per_s'][1]}, "
                 f"concurrency {d['mean_concurrency'][0]} -> {d['mean_concurrency'][1]}, wall {d['wall_s'][0]} -> {d['wall_s'][1]} s")
    lines.extend(f"REGRESSION {r}" for r in result["regressions"])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("trace")
    b.add_argument("--context", nargs="+", required=True, metavar="KEY=VALUE")
    b.add_argument("--output")
    c = sub.add_parser("compare")
    c.add_argument("baseline")
    c.add_argument("candidate")
    c.add_argument("--threshold", type=float, default=10.0)
    c.add_argument("--json", action="store_true")
    c.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "build":
        try:
            record = build(args.trace, parse_context(args.context))
        except ValueError as error:
            sys.exit(str(error))
        text = json.dumps(record, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(text)
        else:
            sys.stdout.write(text)
        return 0
    result = compare(load_record(args.baseline), load_record(args.candidate), args.threshold)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 1 if args.fail_on_regression and result["regressions"] else 0


if __name__ == "__main__":
    sys.exit(main())
