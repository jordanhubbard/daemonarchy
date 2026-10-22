#!/usr/bin/env python3
"""Retain selection-specific dependency graphs from pinned pkg catalogues.

This read-only collector does not solve native pkg constraints or authorize
installation. Different recorded dependency versions remain explicit evidence
gaps until a native solver validates the selected package closure.
"""

import argparse
import hashlib
import heapq
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from urllib.parse import urlsplit


SCHEMA = "daemonarchy/package-dag@1"
SELECTION_SCHEMA = "daemonarchy/package-selection@1"
MAX_CATALOGUE = 256 * 1024 * 1024
MAX_LINE = 2 * 1024 * 1024
MAX_PACKAGES = 100000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=lambda value: fail(f"invalid JSON constant: {value}"))


def fail(message):
    raise ValueError(message)


def read_pinned(path, expected, limit):
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        fail("expected a lowercase SHA-256 pin")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            fail("input must be a regular file")
        data = stream.read(limit + 1)
    if len(data) > limit:
        fail("input exceeds byte budget")
    if digest(data) != expected:
        fail(f"input digest changed: {Path(path).name}")
    return data


def text(value, field):
    if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(c) < 32 for c in value):
        fail(f"invalid {field}")
    return value


def size(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        fail("invalid package size")
    return value


def archive_checksum(value):
    if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
        return dict(format="sha256-hex", value=value)
    # pkg records typed checksums as <type>$<encoded digest>. Preserve the
    # complete native representation; the type does not identify SHA-256 and
    # historical base32 encodings differ from standard z-base-32. Native pkg
    # must validate the checksum against the archive before installation.
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,2}\$(?:[a-z0-9]{52}|[a-z0-9]{64}|[a-z0-9]{103}|[a-z0-9]{128})", value):
        return dict(format="pkg-file-checksum", value=value)
    fail("missing or malformed package archive checksum")


def load_catalogue(config, base, abi, osversion):
    repository = text(config["id"], "repository ID")
    url = text(config["url"], "repository URL")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail("repository URL must be HTTPS without credentials, query or fragment")
    data = read_pinned(base / config["path"], config["sha256"], MAX_CATALOGUE)
    packages = {}
    for line in data.splitlines():
        if not line.strip():
            continue
        if len(line) > MAX_LINE or len(packages) >= MAX_PACKAGES:
            fail("catalogue exceeds record budget")
        row = decode(line)
        if not isinstance(row, dict):
            fail("catalogue record must be an object")
        name = text(row["name"], "package name")
        version = text(row["version"], "package version")
        origin = text(row["origin"], "package origin")
        package_abi = text(row["abi"], "package ABI")
        if package_abi not in (abi, abi.rsplit(":", 1)[0] + ":*"):
            fail(f"wrong package ABI: {name}")
        annotations = row.get("annotations", {})
        if not isinstance(annotations, dict):
            fail("package annotations must be an object")
        required_os = annotations.get("FreeBSD_version")
        if required_os is None:
            if not package_abi.endswith(":*"):
                fail(f"native package lacks FreeBSD_version: {name}")
        elif not isinstance(required_os, str) or not re.fullmatch(r"[0-9]{7}", required_os) or int(required_os) > osversion:
            fail(f"incompatible package FreeBSD_version: {name}")
        checksum = archive_checksum(row["sum"])
        path = text(row.get("repopath", row.get("path")), "package repository path")
        if any(c in path for c in ("\\", "?", "#", "%")) or path.startswith("/") or any(p in ("", ".", "..") for p in path.split("/")):
            fail("unsafe package repository path")
        if PurePosixPath(path).suffix not in (".pkg", ".txz", ".tbz", ".tzst"):
            fail("unsupported package archive path")
        deps = row.get("deps", {})
        if not isinstance(deps, dict):
            fail("dependencies must be an object")
        for dep, requirement in deps.items():
            text(dep, "dependency name")
            if not isinstance(requirement, dict):
                fail("dependency must bind origin and version")
            text(requirement["origin"], "dependency origin")
            text(requirement["version"], "dependency version")
        if name in packages:
            fail(f"ambiguous package name in repository: {name}")
        packages[name] = dict(name=name, version=version, origin=origin, abi=package_abi,
                              repository=repository, archive_path=path, archive_checksum=checksum,
                              download_bytes=size(row["pkgsize"]), installed_bytes=size(row["flatsize"]),
                              manifest_sha256=digest(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()),
                              annotations=annotations, dependencies=deps,
                              native_constraints={k: row[k] for k in ("options", "conflicts", "dep_formula", "provides", "requires", "shlibs_required", "shlibs_provided") if k in row})
    if not packages:
        fail("empty catalogue")
    return packages


def graph(roots, packages):
    if not isinstance(roots, list) or not roots or any(not isinstance(r, str) or r not in packages for r in roots):
        fail("selection roots must name available packages")
    selected = set()
    pending = list(roots)
    edges = []
    mismatches = []
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        for dep, requirement in sorted(packages[name]["dependencies"].items()):
            if dep not in packages:
                fail(f"missing dependency: {name} -> {dep}")
            candidate = packages[dep]
            if candidate["origin"] != requirement["origin"]:
                fail(f"dependency origin conflict: {name} -> {dep}")
            edge = dict(package=name, dependency=dep,
                        declared_version=requirement["version"], selected_version=candidate["version"])
            edges.append(edge)
            if requirement["version"] != candidate["version"]:
                mismatches.append(edge)
            pending.append(dep)
    remaining = {name: len(packages[name]["dependencies"]) for name in selected}
    consumers = {name: [] for name in selected}
    for edge in edges:
        consumers[edge["dependency"]].append(edge["package"])
    ready = [name for name in selected if remaining[name] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for consumer in consumers[name]:
            remaining[consumer] -= 1
            if remaining[consumer] == 0:
                heapq.heappush(ready, consumer)
    if len(order) != len(selected):
        fail("dependency cycle: " + ", ".join(sorted(n for n, count in remaining.items() if count)))
    return dict(roots=sorted(set(roots)), packages=sorted(selected), dependency_first_order=order,
                edges=sorted(edges, key=lambda e: (e["package"], e["dependency"])),
                version_resolution_required=sorted(mismatches, key=lambda e: (e["package"], e["dependency"])),
                download_bytes=sum(packages[n]["download_bytes"] for n in selected),
                installed_bytes=sum(packages[n]["installed_bytes"] for n in selected))


def collect(path, pin):
    config = decode(read_pinned(path, pin, MAX_LINE))
    if config["schema"] != SELECTION_SCHEMA:
        fail("unsupported selection schema")
    abi = text(config["abi"], "target ABI")
    if not re.fullmatch(r"FreeBSD:[0-9]+:[A-Za-z0-9_]+", abi):
        fail("expected a concrete FreeBSD ABI")
    osversion = config["osversion"]
    if type(osversion) is not int or not 1000000 <= osversion <= 9999999 or osversion // 100000 != int(abi.split(":")[1]):
        fail("OSVERSION must match the selected FreeBSD ABI")
    catalogues = config["catalogues"]
    if not isinstance(catalogues, list) or not 1 <= len(catalogues) <= 16:
        fail("expected one to sixteen catalogues")
    by_repo = {}
    candidates = {}
    count = 0
    for catalogue in catalogues:
        repository = catalogue["id"]
        if repository in by_repo:
            fail("duplicate repository ID")
        loaded = load_catalogue(catalogue, path.parent, abi, osversion)
        count += len(loaded)
        if count > MAX_PACKAGES:
            fail("combined catalogues exceed package budget")
        by_repo[repository] = loaded
        for name, package in loaded.items():
            candidates.setdefault(name, []).append(package)
    bindings = config.get("repositories", {})
    if not isinstance(bindings, dict) or set(bindings) - set(candidates):
        fail("unknown explicit repository binding")
    packages = {}
    for name, alternatives in candidates.items():
        if name in bindings:
            alternatives = [p for p in alternatives if p["repository"] == bindings[name]]
        if len(alternatives) != 1:
            fail(f"explicit repository binding required: {name}")
        packages[name] = alternatives[0]
    selections = config["selections"]
    if not isinstance(selections, dict) or not selections or len(selections) > 256:
        fail("expected one to 256 selections")
    graphs = {text(name, "selection name"): graph(roots, packages) for name, roots in sorted(selections.items())}
    included = set().union(*(g["packages"] for g in graphs.values()))
    return dict(schema=SCHEMA, selection_sha256=pin, abi=abi, osversion=osversion,
                state="catalogue-graph", installation_authorized=False, native_solver_qualified=False,
                catalogues=[{k: c[k] for k in ("id", "url", "sha256")} for c in sorted(catalogues, key=lambda c: c["id"])],
                packages={name: packages[name] for name in sorted(included)}, selections=graphs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = collect(args.selection, args.sha256)
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as error:
        print(f"package DAG refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
