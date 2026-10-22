#!/usr/bin/env python3
"""Compare native pkg dry-run resolution with a pinned catalogue graph.

Run on FreeBSD as root using a fresh private case. Only copied metadata and the
case's empty database are written. This does not install or fetch packages,
authenticate an unsigned repository, or issue a lifecycle/release receipt.
"""

import argparse
from contextlib import ExitStack, closing
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import sqlite3
import stat
import subprocess
import sys
import time


SPEC = importlib.util.spec_from_file_location("package_dag", Path(__file__).with_name("package-dag.py"))
dag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dag)
SCHEMA = "daemonarchy/native-package-plan@1"
MAX_OUTPUT = 16 * 1024 * 1024
NAME = r"[A-Za-z0-9_+.-]+"
COMMAND_ENVIRONMENT = {"PATH": "/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin",
                       "LC_ALL": "C", "LANG": "C"}


def read_json(path, pin, limit=dag.MAX_CATALOGUE):
    result = dag.decode(dag.read_pinned(path, pin, limit))
    if not isinstance(result, dict):
        raise ValueError("expected a JSON object")
    return result


def parse_plan(output, expected, repository_ids):
    """Accept only a complete new-install section with exact package versions."""
    header = re.findall(r"^The following (\d+) package\(s\) will be affected \(of 0 checked\):$", output, re.M)
    counts = re.findall(r"^Number of packages to be installed: (\d+)$", output, re.M)
    if len(header) != 1 or len(counts) != 1 or int(header[0]) != len(expected) or int(counts[0]) != len(expected):
        raise ValueError("native plan count/empty-database header mismatch")
    if output.count("New packages to be INSTALLED:\n") != 1:
        raise ValueError("missing or repeated native install section")
    # No removals, upgrades, downgrades or reinstalls belong in a fresh database.
    if re.search(r"^(?:Installed|New) packages to be (?!INSTALLED:).+$", output, re.M):
        raise ValueError("unexpected native package action")
    section = output.split("New packages to be INSTALLED:\n", 1)[1].split("\n\n", 1)[0]
    proposed = {}
    for line in section.splitlines():
        match = re.fullmatch(r"\t(" + NAME + r"): ([^\s\[\]]+)(?: \[([^\[\]\s]+)\])?", line)
        if not match or match[1] in proposed:
            raise ValueError("malformed or duplicate native plan entry")
        name, version, repository = match.groups()
        if repository is None:
            if len(repository_ids) != 1:
                raise ValueError("native plan omitted ambiguous repository identity")
            repository = next(iter(repository_ids))
        proposed[name] = dict(version=version, repository=repository)
    if proposed != expected:
        missing = sorted(set(expected) - set(proposed))
        extra = sorted(set(proposed) - set(expected))
        changed = sorted(n for n in set(proposed) & set(expected) if proposed[n] != expected[n])
        raise ValueError(f"native plan differs from graph: missing={missing[:10]}, extra={extra[:10]}, changed={changed[:10]}")
    return proposed


def imported_metadata(database, graph_packages):
    """Check identity and declared edges actually loaded by the native solver."""
    with closing(sqlite3.connect(database.absolute().as_uri() + "?mode=ro", uri=True)) as connection:
        for name, expected in graph_packages.items():
            rows = connection.execute(
                "SELECT id,version,origin,arch,cksum,path,pkgsize,flatsize FROM packages WHERE name=?", (name,)).fetchall()
            if len(rows) != 1:
                raise ValueError(f"native repository missing or ambiguous package: {name}")
            row = rows[0]
            identity = (expected["version"], expected["origin"], expected["abi"],
                        expected["archive_checksum"]["value"], expected["archive_path"],
                        expected["download_bytes"], expected["installed_bytes"])
            if tuple(row[1:]) != identity:
                raise ValueError(f"native imported package identity differs: {name}")
            deps = connection.execute("SELECT name,origin,version FROM deps WHERE package_id=?", (row[0],)).fetchall()
            observed = {dep: dict(origin=origin, version=version) for dep, origin, version in deps}
            if len(observed) != len(deps) or observed != expected["dependencies"]:
                raise ValueError(f"native imported dependencies differ: {name}")


def empty_database(path):
    with closing(sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)) as connection:
        count = connection.execute("SELECT count(*) FROM packages").fetchone()[0]
    if count != 0:
        raise ValueError("dry-run changed the private installed package database")


def step_output(stdout, stderr, code, name):
    if stdout.stat().st_size > MAX_OUTPUT or stderr.stat().st_size > MAX_OUTPUT:
        raise ValueError(f"native command output exceeds budget: {name}")
    output, errors = stdout.read_text(), stderr.read_text()
    if code != 0 or errors:
        raise ValueError(f"native command refused ({name}, exit {code}); retained stdout/stderr")
    return output


def run_step(command, args, case, name, timeout=120):
    stdout, stderr = case / f"{name}.stdout", case / f"{name}.stderr"
    with stdout.open("xb") as out, stderr.open("xb") as err:
        process = subprocess.Popen(command + args, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, cwd=case, start_new_session=True,
                                   env=COMMAND_ENVIRONMENT)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            raise
    return step_output(stdout, stderr, code, name)


def run_parallel_steps(steps, *, workers, timeout, on_complete=None, on_event=None):
    """Own a bounded set of native commands under one common deadline.

    The iterator prepares one task only when a child slot is available. Completion
    validation runs in this coordinator before further work is scheduled. Callers
    must provide isolated mutable state for every concurrent command.
    """
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("native worker count must be one to sixteen")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("native parallel deadline must be finite and positive")
    started = time.monotonic()
    deadline = started + timeout
    tasks, active = iter(steps), []
    exhausted = False
    completed = peak = 0
    checking_name = None
    signalled = set()

    def event(state, name):
        if on_event is not None:
            on_event(state, name, len(active), time.monotonic() - started)

    def stop_group(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    try:
        while active or not exhausted:
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired("parallel native commands", timeout)
            while not exhausted and len(active) < workers:
                try:
                    command, args, case, name = next(tasks)
                except StopIteration:
                    exhausted = True
                    break
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired("parallel native commands", timeout)
                handles = ExitStack()
                stdout, stderr = case / f"{name}.stdout", case / f"{name}.stderr"
                try:
                    out = handles.enter_context(stdout.open("xb"))
                    err = handles.enter_context(stderr.open("xb"))
                    process = subprocess.Popen(command + args, stdin=subprocess.DEVNULL,
                                               stdout=out, stderr=err, cwd=case,
                                               start_new_session=True, env=COMMAND_ENVIRONMENT)
                except BaseException:
                    handles.close()
                    raise
                active.append((process, handles, stdout, stderr, name))
                peak = max(peak, len(active))
                checking_name = name
                event("started", name)
                checking_name = None
            for item in list(active):
                process, handles, stdout, stderr, name = item
                checking_name = name
                if stdout.stat().st_size > MAX_OUTPUT or stderr.stat().st_size > MAX_OUTPUT:
                    raise ValueError(f"native command output exceeds budget: {name}")
                code = process.poll()
                if code is None:
                    checking_name = None
                    continue
                handles.close()
                output = step_output(stdout, stderr, code, name)
                if on_complete is not None:
                    on_complete(name, output)
                active.remove(item)
                completed += 1
                event("verified", name)
                checking_name = None
            if active:
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    except BaseException:
        try:
            event("failed", checking_name)
        except BaseException:
            pass  # A broken journal must not prevent child cleanup.
        # Signal every owned group before waiting for any one child. This also
        # catches descendants of a failed command whose leader already exited.
        for process, _handles, _out, _err, _name in active:
            try:
                stop_group(process)
                signalled.add(process.pid)
            except OSError:
                pass  # Cleanup below still attempts to reap every owned child.
        raise
    finally:
        cleanup_error = None
        for item in list(active):
            process, handles, _out, _err, name = item
            try:
                try:
                    if process.poll() is None and process.pid not in signalled:
                        stop_group(process)
                finally:
                    # A signal error must not skip reaping a child that has
                    # already exited or is completing an earlier kill request.
                    process.wait(timeout=5)
                active.remove(item)
                if name != checking_name:
                    event("cancelled", name)
            except BaseException as error:
                cleanup_error = cleanup_error or error
            finally:
                handles.close()
        if cleanup_error is not None:
            raise cleanup_error
    return dict(commands=completed, peak_active=peak, seconds=time.monotonic() - started)


def install_signal_handlers():
    def interrupted(signum, _frame):
        raise InterruptedError(f"native plan interrupted by signal {signum}")
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)


def prepare(config_path, config_pin, selection_name, case):
    config = read_json(config_path, config_pin, dag.MAX_LINE)
    if config["schema"] != "daemonarchy/native-package-plan-inputs@1":
        raise ValueError("unsupported native plan input schema")
    graph = read_json(config_path.parent / config["graph"]["path"], config["graph"]["sha256"])
    if graph["schema"] != dag.SCHEMA or graph["installation_authorized"] is not False:
        raise ValueError("expected a non-authorizing pinned catalogue graph")
    selected = graph["selections"][selection_name]
    if not selected["roots"] or any(not re.fullmatch(NAME, n) or n.startswith("-") for n in selected["roots"]):
        raise ValueError("invalid native root package name")
    if sum(len(n.encode()) + 1 for n in selected["roots"]) > 65536:
        raise ValueError("native root argument budget exceeded")
    expected = {n: dict(version=graph["packages"][n]["version"], repository=graph["packages"][n]["repository"])
                for n in selected["packages"]}
    if not expected or len(expected) != len(selected["packages"]):
        raise ValueError("invalid or duplicate graph selection")
    executable = Path(config["pkg"]["path"])
    if not executable.is_absolute():
        raise ValueError("pkg executable path must be absolute")
    dag.read_pinned(executable, config["pkg"]["sha256"], 128 * 1024 * 1024)
    info = executable.stat()
    if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError("pkg executable must be root-owned and not writable by others")
    repositories = config["repositories"]
    ids = [r["id"] for r in repositories]
    graph_ids = [c["id"] for c in graph["catalogues"]]
    if not 1 <= len(ids) <= 16 or len(set(ids)) != len(ids) or set(ids) != set(graph_ids):
        raise ValueError("repository identities do not match pinned graph")
    staged = {}
    for repository in repositories:
        rid = repository["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", rid):
            raise ValueError("invalid native repository ID")
        if set(repository["files"]) != {"meta.conf", "packagesite.pkg", "data.pkg"}:
            raise ValueError("expected exact repository metadata inventory")
        staged[rid] = {name: dag.read_pinned(config_path.parent / value["path"], value["sha256"], 32 * 1024 * 1024)
                       for name, value in repository["files"].items()}
    if not case.is_absolute() or case.exists() or case.is_symlink():
        raise ValueError("case must be a fresh absolute directory")
    case.mkdir(mode=0o700)
    for name in ("db", "cache", "repos", "repository"):
        (case / name).mkdir(mode=0o700)
    for rid, files in staged.items():
        target = case / "repository" / rid
        target.mkdir(mode=0o700)
        for name, data in files.items():
            (target / name).write_bytes(data)
        # This explicitly scoped development probe uses frozen, locally copied
        # metadata. It does not claim repository signature authentication.
        (case / "repos" / f"{rid}.conf").write_text(
            f'{rid}: {{url: {json.dumps(target.as_uri())}, signature_type: "none", enabled: yes}};\n')
    pkg_config = dict(PKG_DBDIR=str(case / "db"), PKG_CACHEDIR=str(case / "cache"),
                      REPO_AUTOUPDATE=False, PKG_ENABLE_PLUGINS=False, ABI=graph["abi"], OSVERSION=graph["osversion"])
    (case / "pkg.conf").write_text(json.dumps(pkg_config))
    return config, graph, selected, expected, executable, set(ids)


def observe(config_path, config_pin, selection_name, case):
    if platform.system() != "FreeBSD" or os.geteuid() != 0:
        raise ValueError("native plan requires FreeBSD root and isolated scratch state")
    config, graph, selected, expected, executable, ids = prepare(config_path, config_pin, selection_name, case)
    command = [str(executable), "-C", str(case / "pkg.conf"), "-R", str(case / "repos")]
    version = run_step(command, ["--version"], case, "version", timeout=10).strip()
    run_step(command, ["update", "-f"], case, "update")
    # Public pkg shell creates the otherwise absent empty local SQLite file.
    # A dry-run with updates disabled requires that file to exist beforehand.
    if run_step(command, ["shell", "SELECT 1;"], case, "initialize", timeout=10) != "1\n":
        raise ValueError("native private database initialization failed")
    for rid in sorted(ids):
        candidates = [case / "db" / "repos" / rid / "db", case / "db" / f"repo-{rid}.sqlite"]
        databases = [p for p in candidates if p.is_file()]
        if len(databases) != 1:
            raise ValueError("unsupported native repository database layout")
        imported_metadata(databases[0], {n: graph["packages"][n] for n in expected if expected[n]["repository"] == rid})
    output = run_step(command, ["install", "-nUy", "--", *selected["roots"]], case, "plan")
    proposed = parse_plan(output, expected, ids)
    empty_database(case / "db" / "local.sqlite")
    if any((case / "cache").iterdir()):
        raise ValueError("dry-run unexpectedly populated package cache")
    dag.read_pinned(executable, config["pkg"]["sha256"], 128 * 1024 * 1024)
    result = dict(schema=SCHEMA, input_sha256=config_pin, graph_sha256=config["graph"]["sha256"],
                  selection=selection_name, os=platform.system(), release=platform.release(),
                  pkg_version=version, pkg_sha256=config["pkg"]["sha256"],
                  native_plan_matches_graph=True, installed_packages_after=0, package_cache_empty=True,
                  repository_signatures_qualified=False, installation_authorized=False,
                  packages=proposed, observed_version_edges=selected["version_resolution_required"])
    (case / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--case", type=Path, required=True)
    args = parser.parse_args()
    install_signal_handlers()
    try:
        result = observe(args.config.absolute(), args.sha256, args.selection, args.case)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(f"native package plan refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps({k: result[k] for k in ("schema", "selection", "native_plan_matches_graph", "installation_authorized")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
