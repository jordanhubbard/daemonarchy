#!/usr/bin/env python3
"""Summarise an installer trace (docs/install-trace.md) for a person or an LLM.

  install-trace-summary.py TRACE.jsonl [--top N] [--json]

Reads daemonarchy/install-trace@1 JSON lines and reports: total and per-phase
time, every timed operation, the slowest package downloads and unpacks,
download throughput against time, network/disk/CPU utilisation per phase,
network probe timings and device events. It reads only the trace.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys


def load(path):
    rows = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            print(f"{path}:{number}: skipped unreadable line", file=sys.stderr)
            continue
        if isinstance(row, dict) and isinstance(row.get("t_us"), int):
            rows.append(row)
    rows.sort(key=lambda r: r["t_us"])
    return rows


def seconds(us):
    return round(us / 1e6, 3)


def summarise(rows, top=10):
    out = {"events": len(rows)}
    exits = [r for r in rows if r["event"] == "exit"]
    out["total_s"] = seconds(exits[-1]["dur_us"]) if exits else seconds(rows[-1]["t_us"] - rows[0]["t_us"]) if rows else 0
    out["exit_status"] = exits[-1]["status"] if exits else None
    phases = [(r["name"], r["dur_us"], r["t_us"] - r["dur_us"], r["t_us"]) for r in rows if r["event"] == "phase_end"]
    out["phases"] = [{"phase": n, "s": seconds(d)} for n, d, _s, _e in phases]
    out["operations"] = sorted(({"op": r["op"], "phase": r.get("phase"), "s": seconds(r["dur_us"]), "status": r["status"]}
                                for r in rows if r["event"] == "op_end"), key=lambda r: -r["s"])
    downloads = [r for r in rows if r["event"] == "download"]
    out["downloads"] = {
        "count": len(downloads), "bytes": sum(r["bytes"] for r in downloads),
        "busy_s": seconds(sum(r["dur_us"] for r in downloads)),
        "slowest": [{"name": r["name"], "bytes": r["bytes"], "s": seconds(r["dur_us"])}
                    for r in sorted(downloads, key=lambda r: -r["dur_us"])[:top]],
    }
    if downloads:
        span = max(r["t_us"] for r in downloads) - min(r["t_us"] - r["dur_us"] for r in downloads)
        out["downloads"]["wall_s"] = seconds(span)
        out["downloads"]["mean_mib_per_s"] = round(out["downloads"]["bytes"] / 2**20 / max(span / 1e6, 1e-6), 2)
        out["downloads"]["mean_concurrency"] = round(sum(r["dur_us"] for r in downloads) / max(span, 1), 2)
    # pkg's begin/finish events: pair by (type root, name) to time each unpack.
    open_events, unpacks = {}, []
    for r in rows:
        if r["event"] != "pkg_event":
            continue
        root = r["type"].replace("_BEGIN", "").replace("_FINISHED", "").replace("_END", "")
        key = (root, r["name"])
        if r["type"].endswith("BEGIN") or key not in open_events and not r["type"].endswith(("FINISHED", "END")):
            open_events[key] = r["t_us"]
        elif key in open_events:
            unpacks.append({"type": root, "name": r["name"], "s": seconds(r["t_us"] - open_events.pop(key))})
    plans = [r for r in rows if r["event"] == "install_plan"]
    if plans:
        out["plan"] = {k: plans[0][k] for k in ("packages", "archives", "download_bytes", "installed_bytes", "approximate")
                       if k in plans[0]}
    out["pkg_events"] = {"count": sum(1 for r in rows if r["event"] == "pkg_event"),
                         "slowest_timed": sorted(unpacks, key=lambda u: -u["s"])[:top]}
    per_phase = defaultdict(lambda: defaultdict(float))
    for r in rows:
        ph = r.get("phase") or "none"
        if r["event"] == "net_sample":
            per_phase[ph]["rx_mib"] += r["d_ibytes"] / 2**20
            per_phase[ph]["tx_mib"] += r["d_obytes"] / 2**20
        elif r["event"] == "disk_sample":
            per_phase[ph]["disk_read_mib"] += r["d_read_kib"] / 1024
            per_phase[ph]["disk_write_mib"] += r["d_write_kib"] / 1024
        elif r["event"] == "cpu_sample":
            per_phase[ph]["cpu_samples"] += 1
            per_phase[ph]["cpu_idle_sum"] += r["idle"]
    out["io_by_phase"] = {ph: {k: round(v, 1) for k, v in vals.items() if k != "cpu_idle_sum"} |
                          ({"cpu_busy_pct": round(100 - vals["cpu_idle_sum"] / vals["cpu_samples"], 1)} if vals.get("cpu_samples") else {})
                          for ph, vals in per_phase.items()}
    out["net_probes"] = [{k: v for k, v in r.items() if k in ("host", "dns_us", "connect_us", "tls_us", "first_byte_us", "status", "error")}
                         for r in rows if r["event"] == "net_probe"]
    out["device_events"] = [{"s": seconds(r["since_start_us"]), **{k: v for k, v in r.items() if k in ("kind", "device", "system", "subsystem", "type")}}
                            for r in rows if r["event"] == "device_event"][:200]
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("trace")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = summarise(load(args.trace), args.top)
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"{summary['events']} events, {summary['total_s']} s, exit status {summary['exit_status']}")
    print("phases: " + ", ".join(f"{p['phase']} {p['s']}s" for p in summary["phases"]))
    for op in summary["operations"][:args.top]:
        print(f"  op {op['op']:<28} {op['s']:>9}s  status {op['status']}  ({op['phase']})")
    d = summary["downloads"]
    print(f"downloads: {d['count']} archives, {d['bytes'] / 2**20:.0f} MiB, busy {d['busy_s']} s"
          + (f", wall {d['wall_s']} s, {d['mean_mib_per_s']} MiB/s, mean concurrency {d['mean_concurrency']}" if d["count"] else ""))
    for r in d["slowest"][:args.top]:
        print(f"  slowest {r['name']:<40} {r['bytes'] / 2**20:8.1f} MiB {r['s']:>8}s")
    for ph, vals in summary["io_by_phase"].items():
        print(f"io {ph}: " + ", ".join(f"{k}={v}" for k, v in vals.items()))
    for p in summary["net_probes"]:
        print("probe " + " ".join(f"{k}={v}" for k, v in p.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
