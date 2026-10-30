#!/usr/bin/env python3
"""Turn a release build pipeline's step markers into a build-timing baseline record (PERF-001).

  build-timing-record.py PIPELINE_OUT --label L --host H --revision SHA --jobs N
                         [--ncpu N] [--incremental yes|no] [--world-log FILE]
                         [--note TEXT]... [--extra NAME=START,END]...

PIPELINE_OUT is the output of a pipeline that prints `== <step> <UTC timestamp>` as it
enters each step and `pipeline-exit=<status>` at the end (scripts of the pipeline-rev2
kind). Each step's duration is the gap to the next marker. `--world-log` adds the make
"World built in N seconds" figure; `--extra` adds a separately timed phase such as an ISO
build (`iso=2026-10-30T05:27:23Z,2026-10-30T05:54:04Z`). The record states what it is and
what it is not: one run, on one machine, incremental or clean as declared; it is a
baseline to compare later runs against, not a performance claim. Reads only the files given.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

SCHEMA = "daemonarchy/build-timing-baseline@1"
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def parse_time(text):
    return datetime.strptime(text, STAMP).replace(tzinfo=timezone.utc)


def steps_from(text):
    marks = [(m.group(1), parse_time(m.group(2))) for m in re.finditer(r"(?m)^== (\S+) (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\s*$", text)]
    if not marks:
        raise ValueError("no '== step timestamp' markers found")
    exit_match = re.search(r"(?m)^pipeline-exit=(\d+)\s*$", text)
    steps = []
    for (name, start), following in zip(marks, marks[1:] + [None]):
        row = {"step": name, "start": start.strftime(STAMP)}
        if following:
            row["end"] = following[1].strftime(STAMP)
            row["seconds"] = int((following[1] - start).total_seconds())
        steps.append(row)
    return steps, int(exit_match.group(1)) if exit_match else None


def build_record(text, args):
    steps, exit_status = steps_from(text)
    closed = [s for s in steps if "seconds" in s]
    record = {
        "schema": SCHEMA,
        "label": args.label,
        "host": args.host,
        "revision": args.revision,
        "make_jobs": args.jobs,
        "ncpu": args.ncpu,
        "incremental": args.incremental,
        "pipeline_exit": exit_status,
        "steps": steps,
        "total_seconds": sum(s["seconds"] for s in closed),
        "notes": args.note,
        "limits": ["One run on one machine; not a repeated measurement.",
                   "A step's duration is the gap between marker timestamps, so it includes everything that step ran."],
    }
    world = re.search(r"World built in (\d+) seconds", Path(args.world_log).read_text()) if args.world_log else None
    if world:
        record["world_build_seconds"] = int(world.group(1))
    extras = []
    for item in args.extra:
        name, _, span = item.partition("=")
        start, _, end = span.partition(",")
        extras.append({"step": name, "start": start, "end": end,
                       "seconds": int((parse_time(end) - parse_time(start)).total_seconds())})
    if extras:
        record["separate_phases"] = extras
    if args.incremental == "yes":
        record["limits"].append("Incremental: the object tree from earlier builds was reused; a clean build takes longer.")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pipeline_out")
    parser.add_argument("--label", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--ncpu", type=int)
    parser.add_argument("--incremental", choices=("yes", "no"), default="no")
    parser.add_argument("--world-log")
    parser.add_argument("--note", action="append", default=[])
    parser.add_argument("--extra", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        record = build_record(Path(args.pipeline_out).read_text(), args)
    except (ValueError, OSError) as error:
        print(f"build-timing-record: {error}", file=sys.stderr)
        return 1
    json.dump(record, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
