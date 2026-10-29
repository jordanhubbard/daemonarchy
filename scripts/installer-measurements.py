#!/usr/bin/env python3
"""Bind terminal installer diagnostics to an exact, comparable measurement.

This observer never runs an installation and never turns timing into acceptance.
It records terminal success or failure, exact input/target context, stage timing,
package progress, and measured pkg fetch bytes from an existing diagnostic bundle.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


SCHEMA = "daemonarchy/installer-measurement@1"
CONTEXT_SCHEMA = "daemonarchy/installer-measurement-context@1"
IDENTITY = re.compile(r"sha256:[0-9a-f]{64}\Z")
STEP = re.compile(r"^@@step ([a-z][a-z0-9-]{0,31}) ([0-9]+)$")
PACKAGE_TOTAL = re.compile(
    r"^Number of packages to be (fetched|installed|upgraded|reinstalled): ([0-9]+)$"
)
EXTRACT = re.compile(r"^\[\s*([0-9]+)/([0-9]+)\] Extracting ")
REQUIRED_COMPLETE_STEPS = {"partition", "base", "loader", "config", "fetch", "packages", "finish"}
MAX_LOG_BYTES = 64 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_identity(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return digest(encoded)


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, member in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = member
    return value


def exact_identity(value: object, name: str) -> str:
    require(isinstance(value, str) and IDENTITY.fullmatch(value), f"{name} identity missing")
    return value


def nonnegative(value: object, name: str) -> int:
    require(type(value) is int and value >= 0, f"{name} must be a nonnegative integer")
    return value


def timestamp(value: str, name: str) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), f"{name} must be UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"invalid {name}") from error
    require(parsed.tzinfo == timezone.utc, f"{name} must be UTC")
    return parsed


def read_small(path: Path, limit: int = 1024 * 1024) -> bytes:
    require(path.is_file() and not path.is_symlink(), f"missing regular input: {path.name}")
    require(path.stat().st_size <= limit, f"input exceeds byte limit: {path.name}")
    return path.read_bytes()


def load_context(path: Path) -> dict:
    raw = read_small(path)
    try:
        context = json.loads(raw, object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid measurement context") from error
    require(isinstance(context, dict) and context.get("schema") == CONTEXT_SCHEMA,
            "invalid measurement context schema")
    require(set(context) == {"schema", "image", "selection", "target"},
            "measurement context fields differ")

    image = context["image"]
    require(isinstance(image, dict) and set(image) == {"identity", "release", "size_bytes"},
            "complete image context required")
    exact_identity(image["identity"], "image")
    require(isinstance(image["release"], str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", image["release"]),
            "semantic release required")
    nonnegative(image["size_bytes"], "image size")

    selection = context["selection"]
    require(isinstance(selection, dict) and set(selection) == {
        "catalogue_identity", "download_bytes", "identity", "package_count"
    }, "complete package selection context required")
    exact_identity(selection["identity"], "package selection")
    exact_identity(selection["catalogue_identity"], "package catalogue")
    nonnegative(selection["package_count"], "package count")
    nonnegative(selection["download_bytes"], "package download bytes")

    target = context["target"]
    require(isinstance(target, dict) and set(target) == {
        "cache_mode", "kind", "link_mbps", "link_measurement", "machine_class",
        "storage", "worker_identity", "worker_id"
    }, "complete target context required")
    require(target["kind"] in {"physical", "virtual"}, "invalid target kind")
    require(target["cache_mode"] in {"network", "iso", "attached", "mixed"},
            "invalid package cache mode")
    for name in ("machine_class", "storage", "worker_id"):
        require(isinstance(target[name], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", target[name]),
                f"invalid target {name}")
    exact_identity(target["worker_identity"], "worker")
    require(target["link_measurement"] in {"measured", "unknown"},
            "invalid link measurement state")
    if target["link_measurement"] == "measured":
        require(nonnegative(target["link_mbps"], "link speed") > 0,
                "measured link speed must be positive")
    else:
        require(target["link_mbps"] is None, "unknown link speed must be null")
    return context


def diagnostic_value(directory: Path, name: str) -> str:
    raw = read_small(directory / name, 4096)
    try:
        value = raw.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise ValueError(f"invalid diagnostic {name}") from error
    require(value, f"empty diagnostic {name}")
    return value


def parse_log(raw: bytes) -> dict:
    require(len(raw) <= MAX_LOG_BYTES, "installer log exceeds byte limit")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("installer log is not UTF-8") from error

    steps: list[tuple[str, int]] = []
    names: set[str] = set()
    package_totals: dict[tuple[str, str], int] = {}
    package_total_events: list[dict] = []
    current_step = None
    extracted_current = extracted_total = 0
    fetch_archives = fetch_bytes = 0
    completed_fetch_archives = completed_fetch_bytes = 0
    fetch_attempts = 0
    for line in lines:
        match = STEP.fullmatch(line)
        if match:
            name, epoch = match.group(1), int(match.group(2))
            require(name not in names, "installer step repeated")
            require(not steps or epoch >= steps[-1][1], "installer step clock moved backward")
            names.add(name)
            steps.append((name, epoch))
            current_step = name
            continue
        match = PACKAGE_TOTAL.fullmatch(line)
        if match:
            action, total = match.group(1), int(match.group(2))
            require(current_step is not None, "package total precedes installer step")
            key = (current_step, action)
            require(key not in package_totals or package_totals[key] == total,
                    f"declared {action} package total changed within {current_step}")
            if key not in package_totals:
                package_total_events.append({"step": current_step, "action": action,
                                             "packages": total})
            package_totals[key] = total
            continue
        match = EXTRACT.match(line)
        if match:
            current, total = int(match.group(1)), int(match.group(2))
            require(0 < current <= total, "invalid package extraction position")
            if total > extracted_total or (total == extracted_total and current > extracted_current):
                extracted_current, extracted_total = current, total
            continue
        if line.startswith("@@fetch "):
            try:
                event = json.loads(
                    line[len("@@fetch "):], object_pairs_hook=unique_object
                )
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ValueError("invalid pkg fetch event") from error
            require(isinstance(event, dict) and set(event) == {
                "schema", "archives", "bytes", "file", "file_bytes", "file_total"
            } and event.get("schema") == "daemonarchy/pkg-fetch@1",
                    "invalid pkg fetch event schema")
            archives = nonnegative(event.get("archives"), "fetch archive count")
            amount = nonnegative(event.get("bytes"), "fetch byte count")
            file_bytes = nonnegative(event.get("file_bytes"), "fetch current byte count")
            file_total = nonnegative(event.get("file_total"), "fetch current byte total")
            require(file_bytes <= file_total and file_bytes <= amount,
                    "invalid pkg fetch current-file counters")
            require(isinstance(event.get("file"), str) and len(event["file"]) <= 80,
                    "invalid pkg fetch file")
            if fetch_attempts == 0:
                fetch_attempts = 1
            elif archives < fetch_archives or amount < fetch_bytes:
                completed_fetch_archives += fetch_archives
                completed_fetch_bytes += fetch_bytes
                fetch_attempts += 1
            fetch_archives, fetch_bytes = archives, amount

    require(steps, "installer log has no timestamped steps")
    return {
        "steps": steps,
        "step_names": names,
        "declared_package_totals": package_total_events,
        "extracted_packages": extracted_current,
        "extraction_total": extracted_total,
        "reported_fetch_attempts": fetch_attempts,
        "reported_fetch_archives": completed_fetch_archives + fetch_archives,
        "reported_fetch_bytes": completed_fetch_bytes + fetch_bytes,
    }


def measure(diagnostics: Path, log: Path, context_path: Path) -> dict:
    require(diagnostics.is_dir() and not diagnostics.is_symlink(), "diagnostics directory missing")
    context = load_context(context_path)
    raw_log = read_small(log, MAX_LOG_BYTES)
    parsed = parse_log(raw_log)

    status = diagnostic_value(diagnostics, "status")
    require(status in {"complete", "failed"}, "installer diagnostics are not terminal")
    try:
        exit_status = int(diagnostic_value(diagnostics, "exit-code"))
    except ValueError as error:
        raise ValueError("invalid installer exit status") from error
    require(0 <= exit_status <= 255, "invalid installer exit status")
    require((status == "complete") == (exit_status == 0), "installer status and exit disagree")
    started = timestamp(diagnostic_value(diagnostics, "started-utc"), "diagnostic start")
    updated = timestamp(diagnostic_value(diagnostics, "updated-utc"), "diagnostic completion")
    require(updated >= started, "diagnostic clock moved backward")

    steps = parsed.pop("steps")
    step_names = parsed.pop("step_names")
    first_epoch = steps[0][1]
    started_epoch = int(started.timestamp())
    completed_epoch = int(updated.timestamp())
    require(first_epoch >= started_epoch, "first installer step precedes diagnostic start")
    require(completed_epoch >= steps[-1][1], "completion precedes final installer step")
    if status == "complete":
        require(REQUIRED_COMPLETE_STEPS <= step_names, "complete install omits required stages")

    phases = []
    for index, (name, epoch) in enumerate(steps):
        end = steps[index + 1][1] if index + 1 < len(steps) else completed_epoch
        phases.append({"name": name, "started_epoch": epoch, "elapsed_seconds": end - epoch})

    result = {
        "schema": SCHEMA,
        "context": context,
        "context_identity": content_identity(context),
        "log_identity": digest(raw_log),
        "status": status,
        "exit_status": exit_status,
        "complete": status == "complete",
        "diagnostic_started_utc": started.isoformat().replace("+00:00", "Z"),
        "diagnostic_completed_utc": updated.isoformat().replace("+00:00", "Z"),
        "wall_time_seconds": completed_epoch - started_epoch,
        "unattributed_start_seconds": first_epoch - started_epoch,
        "phase_span_seconds": completed_epoch - first_epoch,
        "phases": phases,
        "package_observations": parsed,
        "context_quality": {
            "link_condition_known": context["target"]["link_measurement"] == "measured",
        },
        "limitations": (
            "Timing and progress observation only; this record grants no installation, "
            "package, lifecycle, hardware, or release acceptance."
        ),
    }
    result["identity"] = content_identity(result)
    return result


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    write_new(args.output, measure(args.diagnostics, args.log, args.context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
