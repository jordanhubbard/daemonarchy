#!/usr/bin/env python3
"""Authenticate a frozen pkg catalogue and verify fetched package archives.

The finite loopback origin preserves pkg's repository URL identity. Metadata is
pinned locally, while payloads come from an allowlisted HTTPS publisher or an
offline directory. Native pkg verifies the catalogue's public-key signature and
archive checksums. No packages are installed and no release receipt is issued.
"""

import argparse
from contextlib import closing
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import quote, unquote, urlsplit


SPEC = importlib.util.spec_from_file_location("native_package_plan", Path(__file__).with_name("native-package-plan.py"))
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
dag = native.dag
SCHEMA = "daemonarchy/signed-package-snapshot@1"
PARALLEL_SCHEMA = "daemonarchy/signed-package-snapshot@2"


def fetch_policy(config):
    schema = config["schema"]
    if schema == "daemonarchy/signed-package-snapshot-inputs@1":
        if "fetch_workers" in config or "fetch_batch_packages" in config:
            raise ValueError("parallel fetch options require signed snapshot inputs version 2")
        return None
    if schema != "daemonarchy/signed-package-snapshot-inputs@2":
        raise ValueError("unsupported signed snapshot input schema")
    workers, batch = config["fetch_workers"], config.get("fetch_batch_packages", 32)
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("fetch workers must be one to sixteen")
    if type(batch) is not int or not 1 <= batch <= 128:
        raise ValueError("fetch batch packages must be one to 128")
    return workers, batch


def fetch_batches(packages, maximum):
    """Balance signed download sizes without changing the selected inventory."""
    import heapq

    count = (len(packages) + maximum - 1) // maximum
    groups = [[] for _ in range(count)]
    heap = [(0, n) for n in range(count)]
    for name in sorted(packages, key=lambda n: (-packages[n]["download_bytes"], n)):
        size, index = heapq.heappop(heap)
        groups[index].append(name)
        if len(groups[index]) < maximum:
            heapq.heappush(heap, (size + packages[name]["download_bytes"], index))
    for group in groups:
        if sum(len(n.encode()) + 1 for n in group) > 65536:
            raise ValueError("native fetch argument budget exceeded")
    paths = sorted(row["archive_path"] for row in packages.values())
    if any(b.startswith(a + "/") for a, b in zip(paths, paths[1:])):
        raise ValueError("signed archive paths conflict as files and directories")
    return [tuple(sorted(group)) for group in groups]


def parallel_fetch(executable, pkg_config, packages, database, database_pin, case,
                   rid, policy, timeout, input_pin):
    """Fetch into independent native state and publish only verified batches."""
    workers, maximum = policy
    batches = fetch_batches(packages, maximum)
    source_database = case / "db"
    database_relative = database.relative_to(source_database)
    database_bytes = 0
    for path in source_database.rglob("*"):
        info = path.lstat()
        if stat.S_ISREG(info.st_mode):
            database_bytes += info.st_size
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError("private native database contains a link or special file")
    total = sum(row["download_bytes"] for row in packages.values())
    retained_budget = len(batches) * (database_bytes + 2 * native.MAX_OUTPUT)
    if shutil.disk_usage(case).free < total + retained_budget + 2 * 1024**3:
        raise ValueError("parallel fetch exceeds retained database/log budget or disk reserve")
    parallel = case / "parallel"
    parallel.mkdir(mode=0o700)
    destination = case / "payloads"
    destination.mkdir(mode=0o700)
    jobs, verified = {}, {}
    verified_bytes = 0
    sequence = 0
    phase_started = time.monotonic()
    journal_path = case / "events.jsonl"

    with journal_path.open("x", encoding="utf-8") as journal:
        def event(state, name, active, _elapsed):
            nonlocal sequence
            sequence += 1
            entry = dict(schema="daemonarchy/package-progress-event@1", sequence=sequence,
                         input_sha256=input_pin, repository_database_sha256=database_pin,
                         phase="download", state=state, batch=name,
                         packages=list(jobs[name][1]) if name in jobs else [],
                         elapsed_seconds=time.monotonic() - phase_started,
                         configured_workers=workers, active_workers=active,
                         verified_packages=len(verified), total_packages=len(packages),
                         verified_bytes=verified_bytes,
                         total_bytes=total)
            journal.write(json.dumps(entry, sort_keys=True) + "\n")
            journal.flush()
            os.fsync(journal.fileno())

        def tasks():
            for index, names in enumerate(batches):
                if hashlib.sha256(database.read_bytes()).hexdigest() != database_pin:
                    raise ValueError("authenticated catalogue changed before native fetch")
                name = f"fetch-{index:06d}"
                job = parallel / name
                job.mkdir(mode=0o700)
                shutil.copytree(source_database, job / "db")
                copied = job / "db" / database_relative
                if hashlib.sha256(copied.read_bytes()).hexdigest() != database_pin:
                    raise ValueError("native fetch database clone differs from authenticated input")
                (job / "cache").mkdir(mode=0o700)
                (job / "pkg.conf").write_text(json.dumps(dict(
                    pkg_config, PKG_DBDIR=str(job / "db"), PKG_CACHEDIR=str(job / "cache"))))
                jobs[name] = job, {n: packages[n] for n in names}
                command = [str(executable), "-C", str(job / "pkg.conf"), "-R", str(case / "repos")]
                args = ["fetch", "-Uy", "-r", rid, "-o", str(job / "payloads"), "--", *names]
                yield command, args, job, name

        def complete(name, _output):
            nonlocal verified_bytes
            job, selected = jobs[name]
            observed = verify_payload_files(job / "payloads", selected)
            copied = job / "db" / database_relative
            if hashlib.sha256(copied.read_bytes()).hexdigest() != database_pin:
                raise ValueError("authenticated catalogue clone changed during native fetch")
            native.empty_database(job / "db" / "local.sqlite")
            if any((job / "cache").iterdir()):
                raise ValueError("native fetch populated a cache outside its selected payloads")
            for package, row in observed.items():
                target = destination / row["archive_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive hard links retain the original batch's evidence and
                # never overwrite an already published path.
                os.link(job / "payloads" / row["archive_path"], target)
                verified[package] = row
                verified_bytes += row["download_bytes"]

        try:
            execution = native.run_parallel_steps(tasks(), workers=workers, timeout=timeout,
                                                  on_complete=complete, on_event=event)
            final = verify_payload_files(destination, packages)
            if final != verified:
                raise ValueError("published payloads changed after native batch verification")
            if hashlib.sha256(database.read_bytes()).hexdigest() != database_pin:
                raise ValueError("authenticated source catalogue changed during parallel fetch")
        except BaseException:
            try:
                event("failed", None, 0, time.monotonic() - phase_started)
            except BaseException:
                pass  # Preserve the failure even when its journal cannot be written.
            raise
    return dict(**execution, requested_workers=workers, batches=len(batches),
                retained_database_bytes=database_bytes * len(batches),
                maximum_retained_log_bytes=2 * native.MAX_OUTPUT * len(batches),
                progress=dict(path="events.jsonl", events=sequence,
                              sha256=hashlib.sha256(journal_path.read_bytes()).hexdigest()))


def https_url(value):
    value = dag.text(value, "HTTPS publisher")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
        raise ValueError("publisher must be HTTPS without credentials, query or fragment")
    parsed.port  # Reject invalid explicit ports.
    return value.rstrip("/")


def archive_path(value):
    value = dag.text(value, "archive path")
    if (value.startswith("/") or any(p in ("", ".", "..") for p in value.split("/"))
            or any(c in value for c in "\\%?#") or not value.endswith((".pkg", ".txz", ".tbz", ".tzst"))):
        raise ValueError("unsafe archive path")
    return value


def public_key_bytes(value):
    lines = value.strip().splitlines()
    if (not lines or lines[0] != b"-----BEGIN PUBLIC KEY-----"
            or lines[-1] != b"-----END PUBLIC KEY-----" or b"PRIVATE KEY" in value):
        raise ValueError("expected a PEM public key; private material is not accepted")
    return value


class FrozenOrigin:
    def __init__(self, metadata, source):
        self.metadata = metadata
        self.source = source
        self.payloads = {}
        self.offline_requests = 0
        self.redirect_requests = 0
        self.counter_lock = threading.Lock()
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                parsed = urlsplit(self.path)
                name = unquote(parsed.path.lstrip("/"))
                if parsed.query or parsed.fragment:
                    self.send_error(404)
                    return
                if name in owner.metadata:
                    data = owner.metadata[name]
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif name in owner.payloads:
                    def unavailable():
                        if "url" not in owner.source:
                            self.send_error(404)
                            return
                        with owner.counter_lock:
                            owner.redirect_requests += 1
                        self.send_response(302)
                        self.send_header("Location", owner.source["url"] + "/" + quote(name, safe="/"))
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                    if "directory" not in owner.source:
                        unavailable()
                        return
                    path = Path(owner.source["directory"]) / name
                    try:
                        stream = os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb")
                        info = os.fstat(stream.fileno())
                        if not stat.S_ISREG(info.st_mode) or info.st_size != owner.payloads[name]:
                            stream.close()
                            raise ValueError("offline archive size/type differs")
                    except (OSError, ValueError):
                        unavailable()
                        return
                    with owner.counter_lock:
                        owner.offline_requests += 1
                    with stream:
                        self.send_response(200)
                        self.send_header("Content-Length", str(info.st_size))
                        self.end_headers()
                        try:
                            shutil.copyfileobj(stream, self.wfile, 1024 * 1024)
                        except (BrokenPipeError, ConnectionResetError, TimeoutError):
                            pass  # The native consumer records/rejects its failed transfer.
                else:
                    self.send_error(404)

            def setup(self):
                super().setup()
                self.connection.settimeout(10)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"


def inventory(database):
    result = {}
    with closing(sqlite3.connect(database.absolute().as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute("SELECT name,version,origin,arch,cksum,path,pkgsize,flatsize FROM packages").fetchall()
    if not 1 <= len(rows) <= dag.MAX_PACKAGES:
        raise ValueError("empty or oversized signed catalogue")
    paths = set()
    for name, version, origin, abi, checksum, path, download, installed in rows:
        if name in result or not re.fullmatch(native.NAME, name) or name.startswith("-"):
            raise ValueError("duplicate or unsafe signed package name")
        path = archive_path(path)
        if path in paths:
            raise ValueError("duplicate signed archive path")
        paths.add(path)
        dag.archive_checksum(checksum)
        if dag.size(download) == 0:
            raise ValueError("empty signed package archive")
        result[name] = dict(version=dag.text(version, "version"), origin=dag.text(origin, "origin"),
                            abi=dag.text(abi, "ABI"), archive_checksum=checksum, archive_path=path,
                            download_bytes=download, installed_bytes=dag.size(installed))
    return result


def verify_payload_files(directory, packages):
    expected = {row["archive_path"] for row in packages.values()}
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != expected:
        raise ValueError("fetched archive inventory differs from signed catalogue selection")
    result = {}
    for name, row in packages.items():
        path = directory / row["archive_path"]
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size != row["download_bytes"]:
                raise ValueError(f"fetched archive size/type differs: {name}")
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        result[name] = dict(**row, sha256=checksum)
    return result


def verify(config_path, config_pin, case):
    if platform.system() != "FreeBSD" or os.geteuid() != 0:
        raise ValueError("signed snapshot verification requires FreeBSD root and isolated scratch state")
    config = native.read_json(config_path, config_pin, dag.MAX_LINE)
    policy = fetch_policy(config)
    abi, osversion = config["abi"], config["osversion"]
    if (not isinstance(abi, str) or not re.fullmatch(r"FreeBSD:[0-9]+:[A-Za-z0-9_]+", abi)
            or type(osversion) is not int or not 1000000 <= osversion <= 9999999
            or osversion // 100000 != int(abi.split(":")[1])):
        raise ValueError("expected a concrete FreeBSD ABI and matching OSVERSION")
    executable = Path(config["pkg"]["path"])
    if not executable.is_absolute():
        raise ValueError("pkg executable must have an absolute path")
    dag.read_pinned(executable, config["pkg"]["sha256"], 128 * 1024 * 1024)
    info = executable.stat()
    if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError("pkg executable must be root-owned and not writable by others")
    repo = config["repository"]
    rid = repo["id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", rid):
        raise ValueError("invalid repository ID")
    if set(repo["metadata"]) != {"meta.conf", "packagesite.pkg", "data.pkg"}:
        raise ValueError("expected exact three-file metadata inventory")
    metadata = {name: dag.read_pinned(config_path.parent / row["path"], row["sha256"], 32 * 1024 * 1024)
                for name, row in repo["metadata"].items()}
    key = public_key_bytes(dag.read_pinned(config_path.parent / repo["public_key"]["path"], repo["public_key"]["sha256"], 65536))
    source = dict(repo["payload_source"])
    if not source or set(source) - {"url", "directory"}:
        raise ValueError("select an HTTPS publisher, offline directory, or both for seed reuse")
    if "url" in source:
        source["url"] = https_url(source["url"])
    if "directory" in source:
        source["directory"] = str((config_path.parent / source["directory"]).absolute())
        if not Path(source["directory"]).is_dir():
            raise ValueError("offline payload directory is unavailable")
    maximum = dag.size(config["maximum_download_bytes"])
    timeout = config["fetch_timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("fetch timeout must be one to 3600 seconds")
    if config["packages"] != "all" and (not isinstance(config["packages"], list) or not config["packages"]):
        raise ValueError("select all packages or a nonempty package-name list")
    if not case.is_absolute() or case.exists() or case.is_symlink():
        raise ValueError("case must be a fresh absolute directory")
    case.mkdir(mode=0o700)
    for name in ("db", "cache", "repos", "metadata"):
        (case / name).mkdir(mode=0o700)
    for name, data in metadata.items():
        (case / "metadata" / name).write_bytes(data)
    (case / "public.pem").write_bytes(key)
    (case / "inputs.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    pkg_config = dict(PKG_DBDIR=str(case / "db"), PKG_CACHEDIR=str(case / "cache"), REPO_AUTOUPDATE=False,
                      PKG_ENABLE_PLUGINS=False, ABI=config["abi"], OSVERSION=config["osversion"])
    (case / "pkg.conf").write_text(json.dumps(pkg_config))
    command = [str(executable), "-C", str(case / "pkg.conf"), "-R", str(case / "repos")]
    started = time.monotonic()
    with FrozenOrigin(metadata, source) as origin:
        (case / "repos" / "snapshot.conf").write_text(rid + ": " + json.dumps(
            dict(url=origin.url, signature_type="pubkey", pubkey=str(case / "public.pem"), enabled=True)))
        version = native.run_step(command, ["--version"], case, "version", timeout=10).strip()
        native.run_step(command, ["update", "-f", "-r", rid], case, "authenticate")
        authenticated = time.monotonic()
        candidates = [case / "db" / "repos" / rid / "db", case / "db" / f"repo-{rid}.sqlite"]
        databases = [path for path in candidates if path.is_file()]
        if len(databases) != 1:
            raise ValueError("unsupported native repository database layout")
        packages = inventory(databases[0])
        database_pin = hashlib.sha256(databases[0].read_bytes()).hexdigest()
        selected = config["packages"]
        if selected != "all":
            if len(set(selected)) != len(selected) or any(name not in packages for name in selected):
                raise ValueError("missing or duplicate selected package")
            packages = {name: packages[name] for name in selected}
        total = sum(row["download_bytes"] for row in packages.values())
        if total > maximum or shutil.disk_usage(case).free < total + 2 * 1024**3:
            raise ValueError("signed payload selection exceeds download budget or disk reserve")
        origin.payloads = {row["archive_path"]: row["download_bytes"] for row in packages.values()}
        if native.run_step(command, ["shell", "SELECT 1;"], case, "initialize", timeout=10) != "1\n":
            raise ValueError("private package database initialization failed")
        if policy is None:
            args = ["fetch", "-Uy", "-r", rid, "-o", str(case / "payloads")]
            args += ["-a"] if selected == "all" else ["--", *selected]
            native.run_step(command, args, case, "fetch-verify", timeout=timeout)
            execution = None
        else:
            execution = parallel_fetch(executable, pkg_config, packages, databases[0],
                                       database_pin, case, rid, policy, timeout, config_pin)
        fetched = time.monotonic()
        verified = verify_payload_files(case / "payloads", packages)
        if hashlib.sha256(databases[0].read_bytes()).hexdigest() != database_pin:
            raise ValueError("frozen authenticated catalogue database changed during fetch")
        native.empty_database(case / "db" / "local.sqlite", allow_pristine_template=policy is not None)
        if any((case / "cache").iterdir()):
            raise ValueError("unexpected private cache files outside fetched payloads")
        transfers = dict(offline_requests=origin.offline_requests, https_redirects=origin.redirect_requests)
    dag.read_pinned(executable, config["pkg"]["sha256"], 128 * 1024 * 1024)
    result = dict(schema=SCHEMA if policy is None else PARALLEL_SCHEMA,
                  input_sha256=config_pin, repository_id=rid,
                  public_key_sha256=repo["public_key"]["sha256"],
                  metadata_sha256={name: value["sha256"] for name, value in repo["metadata"].items()},
                  pkg_version=version, pkg_sha256=config["pkg"]["sha256"], os=platform.system(), release=platform.release(),
                  repository_signature_verified=True, payload_checksums_verified=True,
                  verified_all_catalogue_payloads=selected == "all", packages=verified,
                  download_bytes=total, installed_packages_after=0, private_cache_empty=True,
                  dependency_plan_qualified=False, installation_authorized=False, lifecycle_receipt=None,
                  transfer_requests=transfers,
                  seconds=dict(authentication=authenticated - started, fetch_verify=fetched - authenticated,
                               total=time.monotonic() - started))
    if execution is not None:
        result["fetch_execution"] = dict(execution, state="completed")
        pending = case / ".result.pending.json"
        with pending.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Publication is the completion boundary. The progress journal never
        # independently declares that this guarded result has been accepted.
        os.link(pending, case / "result.json")
    else:
        (case / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--case", type=Path, required=True)
    args = parser.parse_args()
    native.install_signal_handlers()
    try:
        result = verify(args.config.absolute(), args.sha256, args.case)
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(f"signed package snapshot refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps({k: result[k] for k in ("schema", "repository_signature_verified", "payload_checksums_verified", "installation_authorized")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
