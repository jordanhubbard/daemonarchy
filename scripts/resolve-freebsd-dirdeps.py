#!/usr/bin/env python3
"""Observe native directory dependencies at a clean pinned FreeBSD source tree.

This evaluates trusted Makefiles, with explicit acknowledgement, as an
unprivileged native process. It requests variables only, never a build target.
Observations are not a canonical Component catalog or a complete action graph.
"""

import argparse
import hashlib
import heapq
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import signal
import subprocess
import tempfile
import time


VARIABLES = ("DIRDEPS", "_build_dirs", "_build_all_dirs", ".MAKE.MAKEFILES", "TARGET_SPEC")
SUPPORTED_CONTEXTS = {"amd64", "host", "host32", "common"}
KNOWN_CONTEXTS = SUPPORTED_CONTEXTS | {
    "arm", "arm64", "aarch64", "i386", "riscv", "riscv64", "powerpc", "powerpc64",
}
MAX_QUERY_BYTES = 4 * 1024 * 1024


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], timeout=60)


def relative(value):
    p = PurePosixPath(value)
    if (not value or not p.parts or p.is_absolute() or p.as_posix() != value
            or any(x in (".", "..") for x in p.parts)
            or not re.fullmatch(r"[A-Za-z0-9_+.,/-]+", value)):
        raise ValueError("unsupported native directory name")
    return value


def clean_source(repo, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("select a full source commit")
    if git(repo, "rev-parse", "HEAD").decode().strip() != revision:
        raise ValueError("source checkout differs from selected revision")
    if Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo:
        raise ValueError("native source must name the repository root")
    if any(entry and not entry.startswith(b"H ")
           for entry in git(repo, "ls-files", "-v", "-z").split(b"\0")):
        raise ValueError("native source has hidden index flags or unmerged inputs")
    if git(repo, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"):
        raise ValueError("native evaluation requires a clean tree, including ignored inputs")
    names = git(repo, "ls-tree", "-r", "--name-only", "-z", revision).decode().split("\0")
    return frozenset(name for name in names if name)


def declaration(names, unit, context):
    relative(unit)
    if context not in SUPPORTED_CONTEXTS:
        return None
    for name in (f"{unit}/Makefile.depend.{context}", f"{unit}/Makefile.depend"):
        if name in names:
            return name
    return None


def source_directories(names):
    directories = set()
    for name in names:
        parent = PurePosixPath(name).parent
        while parent.parts and parent.as_posix() not in directories:
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def parse_observation(stdout, repo, unit, names, expected_context="amd64", directories=None):
    lines = stdout.decode("utf-8", errors="strict").splitlines()
    if len(lines) != len(VARIABLES):
        raise ValueError("native variable query returned ambiguous framing")
    values = dict(zip(VARIABLES, lines))
    if values["TARGET_SPEC"] != expected_context:
        raise ValueError("native query selected another target context")
    targets = []
    unqualified = []
    if directories is None:
        directories = source_directories(names)
    direct_targets = set(values["_build_dirs"].split())
    for token in sorted(direct_targets | set(values["_build_all_dirs"].split())):
        prefix = str(repo) + "/"
        if not token.startswith(prefix):
            raise ValueError("native dependency target escaped source tree")
        target = token[len(prefix):]
        relative(target)
        path, separator, context = target.rpartition(".")
        # Extra-directory targets need not be target-qualified. A dot in a
        # directory such as gnu/usr.bin/cc/cc is not a machine separator.
        if (target in directories or not separator or "/" in context
                or context.split(",")[0] not in KNOWN_CONTEXTS):
            unqualified.append({"target": target, "reason": "no-established-target-context"})
            continue
        relative(path)
        relative(context)
        targets.append({"unit": path, "context": context,
                        "declaration": declaration(names, path, context),
                        "kind": "directory-dependency" if token in direct_targets else "extra-directory-target",
                        "self": path == unit and context == values["TARGET_SPEC"]})
    includes = []
    for token in values[".MAKE.MAKEFILES"].split():
        if token == "/dev/null":
            continue
        path = Path(token) if token.startswith("/") else repo / unit / token
        path = path.absolute()
        if not path.is_relative_to(repo):
            raise ValueError("native query included an undeclared external Makefile")
        name = path.relative_to(repo).as_posix()
        if (name not in names or path.resolve(strict=True) != path
                or path.is_symlink() or not path.is_file()):
            raise ValueError("native query included an untracked or redirected Makefile")
        includes.append(name)
    if not targets or not values["TARGET_SPEC"]:
        raise ValueError("native query produced no qualified directory targets")
    return {"directory_references": values["DIRDEPS"].split(),
            "qualified_targets": sorted(targets, key=lambda x: (x["unit"], x["context"])),
            "all_directory_targets": values["_build_all_dirs"].split(),
            "consulted_makefiles": sorted(set(includes)),
            "unqualified_targets": unqualified,
            "target_spec": values["TARGET_SPEC"]}


def query_limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_QUERY_BYTES, MAX_QUERY_BYTES))


def directory_graph(records):
    """Order observed directory edges, retaining cycles and unresolved nodes."""
    edges = {((r["unit"], r["context"]), (t["unit"], t["context"]))
             for r in records.values() for t in r.get("qualified_targets", []) if not t["self"]}
    remaining = {node: 0 for node in records}
    consumers = {node: [] for node in records}
    for consumer, provider in sorted(edges):
        if provider not in records:
            raise ValueError("directory graph omitted a referenced node")
        remaining[consumer] += 1
        consumers[provider].append(consumer)
    ready = [node for node, count in remaining.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for consumer in consumers[node]:
            remaining[consumer] -= 1
            if remaining[consumer] == 0:
                heapq.heappush(ready, consumer)
    unresolved = sorted(node for node, record in records.items() if record["status"] != "observed")
    unqualified = [{"consumer": node, **target} for node, record in sorted(records.items())
                   for target in record.get("unqualified_targets", [])]
    return {"directory_edges": len(edges), "acyclic": len(order) == len(records),
            "unresolved_nodes": unresolved, "cyclic_or_cycle_dependent_nodes": sorted(set(records) - set(order)),
            "unqualified_targets": unqualified,
            "observed_directory_closure_resolved": not unresolved and not unqualified and len(order) == len(records),
            "dependency_first_order": order}


def bounded_query(argv, env, timeout):
    # A regular file bounds retained memory; poll output size as well as time.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        child = subprocess.Popen(argv, env=env, stdout=out, stderr=err,
                                 start_new_session=True, preexec_fn=query_limits)
        started = time.monotonic()
        try:
            while child.poll() is None:
                if time.monotonic() - started > timeout:
                    raise ValueError("native query exceeded its deadline")
                if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > MAX_QUERY_BYTES:
                    raise ValueError("native query exceeded its output budget")
                time.sleep(0.02)
            if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > MAX_QUERY_BYTES:
                raise ValueError("native query exceeded its output budget")
            out.seek(0)
            err.seek(0)
            return child.returncode, out.read(), err.read()
        finally:
            # Also reap descendants left behind by a parent that already exited.
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if child.poll() is None:
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait()
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def collect(repo, revision, units, output, *, acknowledged, timeout=20, maximum=5000):
    if not acknowledged:
        raise ValueError("native Makefile evaluation requires --acknowledge-evaluation")
    if platform.system() != "FreeBSD" or platform.machine() not in ("amd64", "x86_64") or os.geteuid() == 0:
        raise ValueError("use an unprivileged native amd64 FreeBSD worker")
    if timeout < 1 or maximum < 1 or maximum > 10000:
        raise ValueError("invalid native observation bounds")
    repo = repo.resolve(strict=True)
    output = output.absolute()
    if output.is_relative_to(repo) or repo.is_relative_to(output):
        raise ValueError("observation output must be outside source tree and its ancestors")
    if output.parent.resolve(strict=True) != output.parent:
        raise ValueError("observation output parent must be direct")
    names = clean_source(repo, revision)
    directories = source_directories(names)
    config = "tools/daemonarchy/src.conf"
    if config not in names:
        raise ValueError("selected source omits reviewed native configuration")
    pending = {(relative(unit), "amd64") for unit in units}
    if not pending:
        pending = {(str(PurePosixPath(n).parent), "amd64") for n in names
                   if PurePosixPath(n).name in ("Makefile.depend", "Makefile.depend.amd64")}
    output.mkdir(mode=0o700)  # Exclusive; never overwrite prior evidence.
    for name in ("home", "tmp", "obj", "queries"):
        (output / name).mkdir()
    env = {"PATH": "/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin",
           "HOME": str(output / "home"), "TMPDIR": str(output / "tmp"),
           "MAKEOBJDIRPREFIX": str(output / "obj"), "LC_ALL": "C", "TZ": "UTC"}
    records = {}
    started = time.monotonic()
    while pending:
        if time.monotonic() - started > 600:
            raise ValueError("native observation exceeded its total ten-minute deadline")
        unit, context = min(pending)
        pending.remove((unit, context))
        if (unit, context) in records:
            continue
        if len(records) >= maximum:
            raise ValueError("native directory closure exceeded its node budget")
        selected = declaration(names, unit, context)
        record = {"unit": unit, "context": context, "declaration": selected}
        records[(unit, context)] = record
        if selected is None:
            record["status"] = "missing-or-unsupported-declaration"
            with (output / "records.jsonl").open("a") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
            continue
        argv = ["/usr/bin/make", "-m", str(repo / "share/mk"), "-C", str(repo / unit),
                "-f", PurePosixPath(selected).name]
        for variable in VARIABLES:
            argv += ["-V", variable]
        argv += [f"SRCTOP={repo}", "TARGET=amd64", "TARGET_ARCH=amd64", f"MACHINE={context}",
                 "MACHINE_ARCH=amd64", "UPDATE_DEPENDFILE=no", ".MAKE.MODE=normal",
                 "__MAKE_CONF=/dev/null", "SRC_ENV_CONF=/dev/null", f"SRCCONF={repo / config}"]
        try:
            code, stdout, stderr = bounded_query(argv, env, timeout)
            key = hashlib.sha256(json.dumps([unit, context]).encode()).hexdigest()
            query_paths = {"stdout": f"queries/{key}.stdout", "stderr": f"queries/{key}.stderr"}
            for kind, content in (("stdout", stdout), ("stderr", stderr)):
                with (output / query_paths[kind]).open("xb") as stream:
                    stream.write(content)
            record.update(exit=code, stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                          stderr_sha256=hashlib.sha256(stderr).hexdigest(),
                          stderr=stderr.decode(errors="replace"), query_argv=argv,
                          query_output=query_paths)
            if code:
                record["status"] = "query-failed"
            else:
                record.update(parse_observation(stdout, repo, unit, names, context, directories), status="observed")
                pending.update((t["unit"], t["context"]) for t in record["qualified_targets"]
                               if (t["unit"], t["context"]) not in records)
        except InterruptedError:
            raise
        except (ValueError, OSError) as error:
            record.update(status="query-rejected", error=str(error))
        # Durable progress survives controller/transport loss. Never an acceptance receipt.
        with (output / "records.jsonl").open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        (output / "progress.json").write_text(json.dumps({"observed": len(records), "pending": len(pending)}))
    clean_source(repo, revision)
    report = {"schema": "daemonarchy/native-dirdeps-observation@1", "revision": revision,
              "make_sha256": digest(Path("/usr/bin/make")), "configuration_sha256": digest(repo / config),
              "producer_sha256": digest(Path(__file__)), "platform": platform.platform(),
              "target": "amd64", "seeds": sorted(units),
              "state": "observation-only", "complete_action_graph": False,
              "canonical_components_registered": 0, "qualified_packages": 0,
              "directory_graph": directory_graph(records),
              "limitations": ["Directory metadata may be stale or omit compilation inputs",
                              "amd64/host/host32/common contexts only; other variants remain visible as unsupported",
                              "No compilation, per-unit packages, canonical locks or acceptance receipts"],
              "records": [records[k] for k in sorted(records)]}
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (output / "observation.json").write_bytes(encoded)
    print(json.dumps({"records": len(records), "unresolved": sum(r["status"] != "observed" for r in records.values()),
                      "unqualified_targets": len(report["directory_graph"]["unqualified_targets"]),
                      "directory_closure_resolved": report["directory_graph"]["observed_directory_closure_resolved"],
                      "sha256": hashlib.sha256(encoded).hexdigest(), "state": report["state"]}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unit", action="append", default=[], help="Seed a closure; default: all amd64 declarations")
    parser.add_argument("--acknowledge-evaluation", action="store_true")
    args = parser.parse_args()
    try:
        report = collect(args.repo, args.revision, args.unit, args.output,
                         acknowledged=args.acknowledge_evaluation)
        return int(not report["directory_graph"]["observed_directory_closure_resolved"])
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"native-dirdeps: {error}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    def interrupted(signum, frame):
        raise InterruptedError(f"native observation interrupted by signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    raise SystemExit(main())
