#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
"""Closed-loop boot experiments against a boottrace diagnostic stick.

The stick's loader (boottrace_loop="YES") starts the plain wired debug
console on every boot and waits briefly for this controller.  Each
iteration this script:

  1. pairs with the loader (waiting as long as the machine needs to reset
     and come back),
  2. runs "boottrace report" and files the previous boot's trace under the
     experiment that produced it,
  3. stops if that boot reached init ("complete") or the queue is empty,
  4. otherwise sends the next experiment's loader lines and boots it with
     "boot -v" (debug.boottrace=1 comes from the stick's loader.conf).

Experiments file: blocks introduced by "[name]"; every other non-blank,
non-comment line is a loader command, e.g.

    [legacy-off]
    read-conf /boot/d/1

    [no-hpet]
    read-conf /boot/d/1
    set hint.hpet.0.disabled=1

A block may end with its own "boot ..." line; otherwise "boot -v" is used.
This wraps loader-console.py from daemonarchy-src tools/daemonarchy.
Plain mode is unauthenticated: use it only on a trusted wired network.
"""

import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time


def load_console(path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("loader_console", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_experiments(text):
    experiments, current = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"\[([A-Za-z0-9_.-]{1,64})\]", line)
        if match:
            current = {"name": match.group(1), "lines": []}
            experiments.append(current)
        elif current is None:
            raise ValueError("loader lines must follow an [experiment] header")
        else:
            if len(line) > 255 or any(not 32 <= ord(c) <= 126 for c in line):
                raise ValueError(f"unsendable loader line: {line!r}")
            current["lines"].append(line)
    names = [e["name"] for e in experiments]
    if len(names) != len(set(names)):
        raise ValueError("experiment names must be unique")
    return experiments


def trace_body(text):
    if text is None:
        return None
    match = re.search(r"BOOTTRACE-BEGIN\r?\n(.*?)BOOTTRACE-END", text, re.S)
    return match.group(1).replace("\r\n", "\n") if match else None


def trace_status(body):
    if body is None:
        return "unavailable", ""
    status = re.search(r"^Status: (\S+)", body, re.M)
    last = re.search(r"^Last step: (.*)$", body, re.M)
    word = status.group(1).rstrip(":").lower() if status else "none"
    return word, last.group(1) if last else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="loader address (netdebug.ip on the stick)")
    ap.add_argument("experiments", type=Path)
    ap.add_argument("--out", type=Path, required=True,
                    help="new or existing results directory")
    ap.add_argument("--loader-console", type=Path,
                    default=Path(os.environ.get(
                        "DAEMONARCHY_LOADER_CONSOLE",
                        Path.home() / "Src/daemonarchy-src/tools/daemonarchy/loader-console.py")))
    ap.add_argument("--port", type=int, default=6668)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--wait", type=float, default=1800,
                    help="seconds to wait for each boot to reach the loader")
    ap.add_argument("--timeout", type=float, default=30,
                    help="seconds for each loader command")
    ap.add_argument("--continue-after-complete", action="store_true")
    args = ap.parse_args(argv)

    lc = load_console(args.loader_console)
    queue = parse_experiments(args.experiments.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    state_path = args.out / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        "iterations": [], "pending": None}
    done = {i["experiment"] for i in state["iterations"]}
    queue = [e for e in queue if e["name"] not in done and
             e["name"] != state.get("pending")]
    summary = args.out / "summary.tsv"

    def save_state():
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1) + "\n")
        tmp.replace(state_path)

    while True:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        print(f"[{stamp}] waiting up to {args.wait:.0f} s for the loader at {args.target}...",
              flush=True)
        client = lc.Console(args.target, args.port, bytes(32), bind=args.bind,
                            timeout=args.timeout, output=None, events=None, stage=None)
        try:
            end = time.monotonic() + args.wait
            while True:
                try:
                    client.pair()
                    break
                except TimeoutError:
                    if time.monotonic() >= end:
                        print("no loader answered; stopping", file=sys.stderr)
                        return 2
            report = client.command("boottrace report", capture=True)
            body = trace_body(report)
            status, last = trace_status(body)
            pending = state.get("pending") or "(before this run or default preset)"
            folder = args.out / re.sub(r"[^A-Za-z0-9_.-]", "_", pending)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"trace-{stamp}.txt").write_text(body or report or "")
            record = {"experiment": pending, "received": stamp, "status": status,
                      "last_step": last}
            state["iterations"].append(record)
            state["pending"] = None
            save_state()
            new = not summary.exists()
            with summary.open("a") as f:
                if new:
                    f.write("received\texperiment\tstatus\tlast_step\n")
                f.write(f"{stamp}\t{pending}\t{status}\t{last}\n")
            print(f"== {pending}: {status}; last step: {last}", flush=True)
            if status == "complete" and pending != "(before this run or default preset)" \
                    and not args.continue_after_complete:
                print(f"Experiment {pending} reached init; stopping.")
                return 0
            if not queue:
                print("Experiment queue is empty; the loader waits at its prompt.")
                return 0
            experiment = queue.pop(0)
            folder = args.out / experiment["name"]
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "settings.txt").write_text("\n".join(experiment["lines"]) + "\n")
            state["pending"] = experiment["name"]
            save_state()
            boot_line = "boot -v"
            for line in experiment["lines"]:
                if line.split()[0] == "boot":
                    boot_line = line
                    continue
                print(f"-> {line}", flush=True)
                out = client.command(line, capture=True)
                with (folder / "loader-output.txt").open("a") as f:
                    f.write(f"OK {line}\n{out or ''}")
            client.command("set debug.boottrace=1")
            print(f"-> {boot_line} (experiment {experiment['name']})", flush=True)
            client.send_line(boot_line)
            # Drain the remaining firmware output until handoff, briefly.
            end = time.monotonic() + 60
            while not client.handoff and time.monotonic() < end:
                client.receive(0.2)
        finally:
            client.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
