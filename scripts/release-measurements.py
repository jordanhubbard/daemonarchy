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


def content_identity(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()
    )


def validate_scopes(run):
    pool = run.get("worker_pool")
    require(
        isinstance(pool, dict)
        and pool.get("schema") == "daemonarchy/measured-worker-pool@1",
        "actual worker/resource pool descriptor required",
    )
    require(
        content_identity(pool) == run.get("worker_pool_identity"),
        "worker pool identity does not bind actual resources",
    )
    for field in ("catalogue_identity", "admission_policy_identity"):
        identity(pool.get(field))
    workers = pool.get("workers")
    require(
        isinstance(workers, list) and workers, "worker pool requires explicit workers"
    )
    worker_map = {}
    for worker in workers:
        require(isinstance(worker, dict), "worker descriptor must be an object")
        name = worker.get("worker_id")
        require(
            isinstance(name, str) and name and name not in worker_map,
            "worker pool ID missing or duplicated",
        )
        worker_map[name] = worker
        for field in (
            "worker_identity",
            "physical_host_identity",
            "capability_contract_identity",
            "allocation_identity",
        ):
            identity(worker.get(field))
        require(
            type(worker.get("slots")) is int and 1 <= worker["slots"] <= 256,
            "worker pool slots invalid",
        )
        resources = worker.get("resources")
        require(
            isinstance(resources, dict)
            and set(resources)
            == {"cpu_millis", "memory_mib", "disk_mib", "network_mbps"},
            "complete actual worker resource budget required",
        )
        for amount in resources.values():
            count(amount)
    observations = run.get("worker_observations")
    require(
        isinstance(observations, list) and len(observations) == len(worker_map),
        "fresh catalogue/observation parent-host bindings required",
    )
    observed = set()
    for observation in observations:
        require(isinstance(observation, dict), "worker observation must be an object")
        name = observation.get("worker_id")
        require(
            name in worker_map and name not in observed,
            "worker observation missing or duplicate",
        )
        observed.add(name)
        worker = worker_map[name]
        for field in ("worker_identity", "physical_host_identity"):
            require(
                observation.get(field) == worker[field],
                "observed physical parent or worker differs",
            )
        require(
            observation.get("catalogue_identity") == pool["catalogue_identity"],
            "observation catalogue differs",
        )
        for field in ("observation_identity", "parent_host_binding_receipt_identity"):
            identity(observation.get(field))
        capacity = observation.get("available_resources")
        require(
            isinstance(capacity, dict) and set(capacity) == set(worker["resources"]),
            "actual observed resource capacity missing",
        )
        for field, budget in worker["resources"].items():
            require(
                count(capacity[field]) >= budget,
                "observed worker capacity is below allocated budget",
            )
    gates = run.get("gate_scope")
    require(
        isinstance(gates, dict)
        and gates.get("schema") == "daemonarchy/measured-gate-scope@1",
        "actual gate scope required",
    )
    require(
        content_identity(gates) == run.get("gate_scope_identity"),
        "gate identity does not bind actual requirements",
    )
    requirements = gates.get("requirements")
    require(
        isinstance(requirements, list) and requirements, "gate requirements missing"
    )
    names = set()
    for item in requirements:
        name = item.get("gate")
        require(
            isinstance(name, str) and name and name not in names,
            "gate requirement missing or duplicated",
        )
        names.add(name)
        identity(item.get("policy_identity"))
        identity(item.get("target_identity"))
    require(
        names <= set(run.get("gates", {})),
        "measurement omits selected gates",
    )
    if run.get("baseline_kind") == "normalized":
        require(
            gates.get("waivers") == [],
            "waived historical scope cannot normalize a speedup",
        )
    mode = run.get("execution_mode")
    require(mode in {"single-machine", "distributed"}, "actual execution mode required")
    used = set()
    for row in run.get("actions", []):
        require(isinstance(row, dict), "action observation must be an object")
        require(
            row.get("worker_id") in worker_map,
            "action ran outside the measured worker pool",
        )
        if row.get("disposition") != "reused":
            used.add(worker_map[row["worker_id"]]["physical_host_identity"])
    require(
        mode != "distributed" or len(used) >= 2,
        "distributed work requires two physical hosts, not merely worker or VM IDs",
    )
    require(
        mode != "single-machine" or len(used) <= 1,
        "single-machine observation used multiple physical hosts",
    )
    return worker_map


def verify_worker_bindings(
    run, *, plan, policy, resolver, locators, current_state, expected_project_authority
):
    """Authenticate actual pool/parent-host observations through LitAI evidence.

    Plan/policy must come from the coordinator's independently pinned verifier
    configuration. This does not trust a serialized `verified` flag or worker ID.
    """
    from literate_ai.application.evidence_verification import verify_run_evidence_graph
    from literate_ai.contracts import ContentIdentity, canonical_json_bytes
    from literate_ai.contracts.blobs import BlobRef
    from literate_ai.security.evidence.plan import EvidenceVerificationPlan
    from literate_ai.security.evidence.records import PlatformRun

    validate_scopes(run)
    require(
        isinstance(plan, EvidenceVerificationPlan)
        and isinstance(expected_project_authority, ContentIdentity),
        "independent trusted worker-binding plan required",
    )
    require(
        plan.project_authority == expected_project_authority,
        "worker bindings select another current authority",
    )
    subject = {
        "schema": "daemonarchy/measured-worker-bindings@1",
        "worker_pool": run["worker_pool"],
        "worker_observations": run["worker_observations"],
    }
    content = canonical_json_bytes(subject)
    reference = BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )
    root = next(
        (
            requirement
            for requirement in plan.requirements
            if requirement.envelope == plan.root
        ),
        None,
    )
    require(
        root is not None
        and root.expectation.predicate_type == PlatformRun.SCHEMA
        and root.expectation.subject == reference,
        "trusted worker proof does not bind actual pool/observations",
    )
    require(
        {
            "check/catalogue-binding",
            "check/observed-parent-host",
            "check/resource-capacity",
        }
        <= set(dict(root.artifacts)),
        "trusted parent-host/resource checks missing",
    )
    return verify_run_evidence_graph(
        plan.root,
        requirements=plan.requirements,
        policy=policy,
        resolver=resolver,
        locators=locators,
        current_state=current_state,
    )


def validate_attempts(row, *, required=False):
    """Account for every retained attempt; completeness needs trusted inventory proof."""
    attempts = row.get("attempts")
    if attempts is None:
        require(not required, "authenticated complete attempt inventory required")
        return
    require(isinstance(attempts, list), "attempt inventory must be a list")
    if row.get("disposition") == "reused":
        require(not attempts, "reused payload cannot hide executed attempts")
        return
    require(bool(attempts), "executed action lacks attempt inventory")
    requests = set()
    for number, attempt in enumerate(attempts, 1):
        require(attempt.get("number") == number, "attempt inventory is not contiguous")
        request = identity(attempt.get("request_identity"))
        require(request not in requests, "duplicate attempt request")
        requests.add(request)
        for field in ("terminal_receipt_identity", "command_identity"):
            identity(attempt.get(field))
        require(
            isinstance(attempt.get("worker_id"), str) and attempt["worker_id"],
            "attempt worker missing",
        )
        status = attempt.get("status")
        require(
            status in {"exited", "timed-out", "interrupted", "launch-failed"},
            "attempt observation status missing",
        )
        code = attempt.get("exit_status")
        require(code is None or type(code) is int, "invalid attempt exit status")
        require(
            number < len(attempts) or (status == "exited" and code == 0),
            "completed action has no successful terminal attempt",
        )
        require(
            number == len(attempts) or status != "exited" or code != 0,
            "successful attempt cannot be silently retried",
        )
        for field in ("wall_time_ns", "cache_read_bytes", "cache_write_bytes"):
            count(attempt.get(field))
    for field in ("wall_time_ns", "cache_read_bytes", "cache_write_bytes"):
        require(
            row.get(field) == sum(attempt[field] for attempt in attempts),
            "action omits cumulative attempt cost: " + field,
        )


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
    validate_scopes(run)
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
        require(
            count(row.get("wall_time_ns")) <= elapsed,
            "run elapsed is shorter than an included action",
        )
        validate_attempts(row)
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
    pool = {worker["worker_id"]: worker for worker in run["worker_pool"]["workers"]}
    observations = {item["worker_id"]: item for item in run["worker_observations"]}
    rows = []
    for action in run["actions"]:
        if action["disposition"] == "reused":
            continue  # Cache admission remains owned by the exact cache receipt.
        rows.extend(
            {**action, **attempt} for attempt in action.get("attempts", [dict()])
        )
    for row in rows:
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
            and record.get("status") == row.get("status", "exited")
            and record.get("exit_status") == row.get("exit_status", 0),
            "terminal worker command status differs",
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
        worker = pool[row["worker_id"]]
        observation = observations[row["worker_id"]]
        for field in ("worker_identity", "physical_host_identity"):
            require(
                context.get(field) == worker[field],
                "terminal command physical parent/worker differs",
            )
        for field in ("observation_identity", "parent_host_binding_receipt_identity"):
            require(
                context.get(field) == observation[field],
                "terminal command observation/host binding differs",
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
        "numeric_target_met": None if target is None else ratio >= target,
        "target_met": None,
        "qualification_blockers": [
            "authenticated complete attempt and action inventory",
            "trusted current gates, timing and cache accounting",
            "authenticated physical worker/resource bindings",
        ],
        "cache_read_bytes": sum(
            row["cache_read_bytes"] for row in candidate["actions"]
        ),
        "cache_write_bytes": sum(
            row["cache_write_bytes"] for row in candidate["actions"]
        ),
    }


def verify_measurement(
    run, *, plan, policy, resolver, locators, current_state, expected_project_authority
):
    """Verify full observation and all-attempt coverage with independently pinned trust."""
    from literate_ai.application.evidence_verification import verify_run_evidence_graph
    from literate_ai.contracts import ContentIdentity, canonical_json_bytes
    from literate_ai.contracts.blobs import BlobRef
    from literate_ai.security.evidence.plan import EvidenceVerificationPlan
    from literate_ai.security.evidence.records import PlatformRun

    validate(run)
    for row in run["actions"]:
        validate_attempts(row, required=True)
    require(
        isinstance(plan, EvidenceVerificationPlan)
        and isinstance(expected_project_authority, ContentIdentity)
        and plan.project_authority == expected_project_authority,
        "independently pinned current measurement authority required",
    )
    content = canonical_json_bytes(run)
    reference = BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )
    root = next(
        (item for item in plan.requirements if item.envelope == plan.root), None
    )
    require(
        root is not None
        and root.expectation.predicate_type == PlatformRun.SCHEMA
        and root.expectation.subject == reference,
        "trusted measurement proof does not bind complete observation",
    )
    require(
        {
            "check/complete-attempt-inventory",
            "check/complete-action-inventory",
            "check/current-gates",
            "check/timing",
            "check/cache-accounting",
            "check/catalogue-binding",
            "check/observed-parent-host",
            "check/resource-capacity",
        }
        <= set(dict(root.artifacts)),
        "trusted measurement coverage checks missing",
    )
    return verify_run_evidence_graph(
        plan.root,
        requirements=plan.requirements,
        policy=policy,
        resolver=resolver,
        locators=locators,
        current_state=current_state,
    )


def compare_authenticated(
    baseline, candidate, *, baseline_verifier, candidate_verifier
):
    """Admit targets only after both complete measurements pass actual trust checks."""
    result = compare(baseline, candidate)
    verify_measurement(baseline, **baseline_verifier)
    verify_measurement(candidate, **candidate_verifier)
    result["measurement_authentication"] = "verified-current-evidence-graphs"
    result["qualification_blockers"] = []
    result["target_met"] = result["numeric_target_met"]
    return result


def recover_historical_phases(path, *, release_source=None):
    """Recover reported per-stage observations without normalizing old outcomes."""
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    require(
        value.get("schema") == "daemonarchy/native-traced-build-checkpoint@1",
        "unsupported retained historical observation format",
    )
    original = value.get("original_run")
    require(
        isinstance(original, dict) and isinstance(original.get("phases"), list),
        "retained stage observations unavailable",
    )
    phases = []
    for phase in original["phases"]:
        elapsed = phase.get("elapsed_seconds")
        require(
            type(elapsed) in {int, float} and math.isfinite(elapsed) and elapsed >= 0,
            "invalid historical phase elapsed time",
        )
        require(
            type(phase.get("exit")) is int, "historical terminal status unavailable"
        )
        phases.append(
            {
                "name": phase["name"],
                "reported_elapsed_seconds": elapsed,
                "terminal_exit_status": phase["exit"],
                "reported_log_sha256": phase.get("log_sha256"),
                "started_utc": None,
                "terminal_utc": None,
            }
        )
    revision = original.get("source_revision")
    if release_source is not None:
        require(
            isinstance(release_source, str)
            and re.fullmatch("[0-9a-f]{40}", release_source),
            "exact release source revision required",
        )
    return {
        "schema": "daemonarchy/historical-stage-observation-recovery@1",
        "source_evidence_identity": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "source_evidence_name": path.name,
        "source_revision": revision,
        "expected_release_source": release_source,
        "matches_release_source": None
        if release_source is None
        else revision == release_source,
        "baseline_kind": "historical-observation",
        "comparison_eligible": False,
        "original_status": original.get("status"),
        "phase_observations": phases,
        "worker_pool_identity": None,
        "gate_scope_identity": None,
        "normalization_blockers": [
            "reported historical phases lack retained started/terminal UTC pairs",
            "equivalent complete product/worker/resource/gate scope is not established",
            "original failed/retried/waived work cannot normalize a clean critical path",
        ],
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
        "--recover-historical",
        type=Path,
        help="read a retained traced-build checkpoint without normalizing it",
    )
    parser.add_argument(
        "--release-source",
        help="exact expected release source commit for historical comparison",
    )
    parser.add_argument(
        "--observations-root",
        type=Path,
        help="reopen candidate worker observations and logs",
    )
    args = parser.parse_args()
    try:
        if args.recover_historical is not None:
            print(
                json.dumps(
                    recover_historical_phases(
                        args.recover_historical, release_source=args.release_source
                    ),
                    sort_keys=True,
                    indent=2,
                )
            )
            return 0
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
