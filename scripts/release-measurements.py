#!/usr/bin/env python3
"""Validate observed release measurements; never execute a build or infer acceptance."""

from __future__ import annotations

import argparse
import hashlib
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
import json
import math
import re
from pathlib import Path

SCHEMA = "daemonarchy/release-measurement@1"
SCENARIOS = {
    "clean",
    "unchanged",
    "compatible-update",
    "changed-input",
    "package-only",
    "iso-only",
}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(value):
    require(
        isinstance(value, str) and DIGEST.fullmatch(value),
        "missing exact content identity",
    )
    return value


def count(value):
    require(
        type(value) is int and value >= 0, "measurement must be a nonnegative integer"
    )
    return value


def validate(run):
    require(run.get("schema") == SCHEMA, "unsupported measurement schema")
    require(run.get("scenario") in SCENARIOS, "unknown measurement scenario")
    require(
        run.get("baseline_kind") in {"normalized", "historical-observation"},
        "baseline kind required",
    )
    for field in (
        "selection_identity",
        "gate_scope_identity",
        "worker_pool_identity",
        "observation_identity",
    ):
        identity(run.get(field))
    require(run.get("complete") is True, "incomplete release critical path")
    elapsed = count(run.get("wall_time_ns"))
    require(elapsed > 0, "zero elapsed measurement")
    rows = run.get("actions")
    require(isinstance(rows, list) and rows, "per-action measurements required")
    seen = set()
    action_ids = set()
    for row in rows:
        require(
            isinstance(row.get("action_id"), str)
            and row["action_id"]
            and row["action_id"] not in action_ids,
            "missing or duplicate action obligation",
        )
        action_ids.add(row["action_id"])
        key = identity(row.get("action_key"))
        require(key not in seen, "duplicate action execution key")
        seen.add(key)
        require(
            row.get("kind")
            in {
                "compile",
                "test",
                "package",
                "sign",
                "iso",
                "qualification",
                "publish-check",
            },
            "unknown action kind",
        )
        require(
            row.get("disposition") in {"executed", "reused", "requalified"},
            "unsuccessful action in completed measurement",
        )
        require(
            isinstance(row.get("reason"), str) and row["reason"].strip(),
            "missing invalidation or reuse reason",
        )
        for field in ("receipt_identity", "output_identity", "input_identity"):
            identity(row.get(field))
        count(row.get("wall_time_ns"))
        count(row.get("cache_read_bytes"))
        count(row.get("cache_write_bytes"))
        require(
            isinstance(row.get("worker_id"), str) and row["worker_id"],
            "worker observation missing",
        )
        require(
            row.get("disposition") != "reused" or row["cache_write_bytes"] == 0,
            "reuse cannot claim a new cache output",
        )
        require(
            not (
                run["scenario"] == "unchanged"
                and row["kind"] == "compile"
                and row["disposition"] == "executed"
            ),
            "unchanged run compiled a payload",
        )
        require(
            not (
                run["scenario"] == "compatible-update"
                and row.get("origin") in {"www/chromium", "www/chromium-cef", "www/cef"}
                and row["kind"] == "compile"
                and row["disposition"] == "executed"
            ),
            "compatible update recompiled browser payload",
        )
        if run["scenario"] in {"package-only", "iso-only"}:
            require(
                not (row["kind"] == "compile" and row["disposition"] == "executed"),
                "packaging-only run compiled payloads",
            )
        if run["scenario"] == "iso-only":
            require(
                not (
                    row["kind"] in {"package", "sign"}
                    and row["disposition"] == "executed"
                ),
                "ISO-only run changed a package/signature envelope",
            )
    gates = run.get("gates")
    require(
        isinstance(gates, dict)
        and {
            "build",
            "package",
            "sign",
            "iso",
            "native",
            "fresh-install",
            "upgrade",
            "rollback",
        }
        <= set(gates),
        "missing required acceptance gates",
    )
    for receipt in gates.values():
        identity(receipt)
    return run


def verify_observations(run, root):
    """Reopen retained worker command observations without promoting receipts."""
    validate(run)
    root = Path(root).resolve(strict=True)
    for row in run["actions"]:
        if row["disposition"] == "reused":
            continue  # Cache admission remains owned by the exact cache receipt.
        relative = row.get("observation_path")
        require(isinstance(relative, str), "terminal observation path missing")
        parts = Path(relative).parts
        require(
            parts
            and not Path(relative).is_absolute()
            and all(part not in {".", ".."} for part in parts),
            "observation path escapes retained evidence",
        )
        path = root
        for part in parts:
            path /= part
            require(not path.is_symlink(), "observation path traverses a link")
        record = json.loads(path.read_text())
        body = {key: value for key, value in record.items() if key != "identity"}
        expected = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
        require(
            record.get("identity") == expected == row.get("terminal_receipt_identity"),
            "terminal observation identity differs",
        )
        require(
            record.get("schema") == "daemonarchy/raw-action-observation@1"
            and record.get("status") == "exited"
            and record.get("exit_status") == 0,
            "terminal worker command failed or timed out",
        )
        require(
            record.get("command_identity") == row.get("command_identity"),
            "worker command differs",
        )
        identity(record.get("command_identity"))
        require(
            record.get("wall_time_ns") == row["wall_time_ns"]
            and record.get("started_utc")
            and record.get("ended_utc"),
            "command timing does not bind action observation",
        )
        context = record.get("context")
        require(isinstance(context, dict), "exact worker context missing")
        for field in ("action_key", "input_identity", "worker_id"):
            require(
                context.get(field) == row.get(field),
                "action observation context differs: " + field,
            )
        for field in ("selection_identity", "worker_pool_identity"):
            require(
                context.get(field) == run.get(field),
                "run observation context differs: " + field,
            )
        identity(context.get("worker_identity"))
        require(
            set(record.get("logs", {})) == {"stdout.log", "stderr.log"},
            "terminal command logs missing",
        )
        for name, expected_log in record["logs"].items():
            log = path.parent / name
            require(
                not log.is_symlink() and log.is_file(), "terminal log missing or linked"
            )
            with log.open("rb") as stream:
                require(
                    "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
                    == expected_log,
                    "terminal command log changed",
                )
    return True


def compare(baseline, candidate):
    baseline, candidate = validate(baseline), validate(candidate)
    require(
        baseline["baseline_kind"] == candidate["baseline_kind"] == "normalized",
        "historical observations cannot normalize a speedup",
    )
    require(baseline["scenario"] == "clean", "comparison baseline must be clean")
    for field in (
        "gate_scope_identity",
        "worker_pool_identity",
        "measurement_scope_identity",
    ):
        identity(baseline.get(field))
        require(baseline.get(field) == candidate.get(field), f"inequivalent {field}")
    # The scope binds the complete selected product/output obligations, while the
    # selection identity may change for the update under measurement.
    require(
        {row["action_id"] for row in baseline["actions"]}
        == {row["action_id"] for row in candidate["actions"]},
        "comparison omits action obligations",
    )
    prior = {row["action_id"]: row for row in baseline["actions"]}
    if candidate["scenario"] != "clean":
        for row in candidate["actions"]:
            previous = prior[row["action_id"]]
            if (
                row["kind"] == "compile"
                and row["disposition"] == "executed"
                and row["action_key"] == previous["action_key"]
            ):
                identity(row.get("reuse_refusal_identity"))
            if (
                row["disposition"] in {"reused", "requalified"}
                and row["action_key"] == previous["action_key"]
            ):
                require(
                    row["output_identity"] == previous["output_identity"],
                    "unchanged action key substituted payload bytes",
                )
    ratio = baseline["wall_time_ns"] / candidate["wall_time_ns"]
    require(math.isfinite(ratio), "invalid measured speedup")
    target = {"unchanged": 10, "compatible-update": 4}.get(candidate["scenario"])
    return {
        "schema": "daemonarchy/release-measurement-comparison@1",
        "baseline_observation": baseline["observation_identity"],
        "candidate_observation": candidate["observation_identity"],
        "speedup": ratio,
        "measurement_authentication": "not-established-by-structural-validator",
        "required_speedup": target,
        "target_met": None if target is None else ratio >= target,
        "cache_read_bytes": sum(
            row["cache_read_bytes"] for row in candidate["actions"]
        ),
        "cache_write_bytes": sum(
            row["cache_write_bytes"] for row in candidate["actions"]
        ),
    }


def observe(argv, output_root, *, timeout_seconds, context=None):
    """Run one explicit command in a finite supervisor, retaining failures.

    This raw observation is not a successful release measurement or receipt.
    Aggregate it only after native action/output and acceptance admission.
    """
    require(
        argv and all(isinstance(x, str) and x for x in argv),
        "explicit command required",
    )
    require(
        type(timeout_seconds) is int and timeout_seconds > 0,
        "positive timeout required",
    )
    if context is not None:
        for field in (
            "action_key",
            "input_identity",
            "selection_identity",
            "worker_pool_identity",
            "worker_identity",
        ):
            identity(context.get(field))
        require(
            isinstance(context.get("worker_id"), str) and context["worker_id"],
            "worker context missing",
        )
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic_ns()
    started_utc = datetime.now(timezone.utc).isoformat()
    status, code = "launch-failed", None
    process = None

    def stop_owned():
        if process is not None:
            try:
                if os.name != "nt":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            return process.wait()
        return None

    try:
        with (
            (root / "stdout.log").open("xb") as stdout,
            (root / "stderr.log").open("xb") as stderr,
        ):
            process = subprocess.Popen(
                argv, stdout=stdout, stderr=stderr, start_new_session=os.name != "nt"
            )
            try:
                code = process.wait(timeout=timeout_seconds)
                status = "exited"
            except subprocess.TimeoutExpired:
                status = "timed-out"
                code = stop_owned()
    except BaseException:
        if process is not None:
            status = "interrupted"
            code = stop_owned()
        raise
    finally:
        elapsed = time.monotonic_ns() - started
        record = {
            "schema": "daemonarchy/raw-action-observation@1",
            "command_identity": "sha256:"
            + hashlib.sha256(
                json.dumps(argv, separators=(",", ":")).encode()
            ).hexdigest(),
            "status": status,
            "exit_status": code,
            "wall_time_ns": elapsed,
            "complete": False,
            "started_utc": started_utc,
            "ended_utc": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "logs": {},
        }
        for name in ("stdout.log", "stderr.log"):
            path = root / name
            if path.is_file():
                with path.open("rb") as stream:
                    record["logs"][name] = (
                        "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
                    )
        record["identity"] = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
        (root / "observation.json").write_text(
            json.dumps(record, sort_keys=True, indent=2) + "\n"
        )
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurement", type=Path, nargs="?")
    parser.add_argument(
        "--observe", type=Path, help="new isolated directory for raw command evidence"
    )
    parser.add_argument(
        "--context",
        type=Path,
        help="exact action, selection and worker identities for raw observation",
    )
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--command", nargs=argparse.REMAINDER)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument(
        "--observations-root",
        type=Path,
        help="reopen candidate worker observations and logs",
    )
    args = parser.parse_args()
    try:
        if args.observe is not None:
            result = observe(
                args.command,
                args.observe,
                timeout_seconds=args.timeout_seconds,
                context=None
                if args.context is None
                else json.loads(args.context.read_text()),
            )
            print(json.dumps(result, sort_keys=True, indent=2))
            return (
                0 if result["status"] == "exited" and result["exit_status"] == 0 else 1
            )
        require(
            args.measurement is not None and args.command is None,
            "measurement or explicit observation required",
        )
        run = json.loads(args.measurement.read_text())
        if args.observations_root is not None:
            verify_observations(run, args.observations_root)
        result = (
            compare(json.loads(args.baseline.read_text()), run)
            if args.baseline
            else validate(run)
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 1 if result.get("target_met") is False else 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(2, f"measurement refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
