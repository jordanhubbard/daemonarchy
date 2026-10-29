#!/usr/bin/env python3
"""Derive an exact installer measurement context from retained native pkg state.

This controller reads an installed-package manifest and the repository databases
retained from that same target.  It does not authenticate a catalogue, install a
package, or turn a historical observation into release acceptance.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import tarfile
import tempfile


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "installer_measurements", HERE / "installer-measurements.py"
)
measurements = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurements)

TARGET_SCHEMA = "daemonarchy/installer-baseline-target@1"
INVENTORY_SCHEMA = "daemonarchy/installer-package-selection@1"
REPOSITORY_DB = re.compile(r"var/db/pkg/repos/([A-Za-z0-9][A-Za-z0-9_.-]{0,63})/db\Z")
MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024 * 1024
REQUIRED_COLUMNS = {
    "name", "version", "arch", "origin", "pkgsize", "flatsize", "cksum", "path"
}


def regular(path: Path, maximum: int) -> int:
    measurements.require(path.is_file() and not path.is_symlink(),
                         f"missing regular input: {path.name}")
    size = path.stat().st_size
    measurements.require(0 < size <= maximum, f"input byte size outside bound: {path.name}")
    return size


def file_identity(path: Path, maximum: int) -> tuple[str, int]:
    size = regular(path, maximum)
    import hashlib
    observed = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            observed.update(chunk)
    measurements.require(path.stat().st_size == size, f"input size changed: {path.name}")
    return "sha256:" + observed.hexdigest(), size


def load_target(path: Path) -> dict:
    raw = measurements.read_small(path)
    try:
        value = json.loads(raw, object_pairs_hook=measurements.unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid baseline target") from error
    measurements.require(isinstance(value, dict) and set(value) == {
        "schema", "release", "target"
    } and value["schema"] == TARGET_SCHEMA, "invalid baseline target schema")
    measurements.require(isinstance(value["release"], str)
                         and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value["release"]),
                         "semantic release required")
    # The measurement context validator remains the single target-field authority.
    synthetic = {
        "schema": measurements.CONTEXT_SCHEMA,
        "image": {"identity": "sha256:" + "0" * 64,
                  "release": value["release"], "size_bytes": 1},
        "selection": {"identity": "sha256:" + "0" * 64,
                      "catalogue_identity": "sha256:" + "0" * 64,
                      "package_count": 0, "download_bytes": 0},
        "target": value["target"],
    }
    with tempfile.TemporaryDirectory() as temporary:
        candidate = Path(temporary) / "context.json"
        candidate.write_text(json.dumps(synthetic))
        measurements.load_context(candidate)
    return value


def manifest(path: Path) -> list[dict]:
    raw = measurements.read_small(path, 16 * 1024 * 1024)
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("installed package manifest is not UTF-8") from error
    measurements.require(lines.count("-- packages --") == 1,
                         "installed package manifest marker differs")
    rows = lines[lines.index("-- packages --") + 1:]
    measurements.require(rows, "installed package manifest is empty")
    packages, names = [], set()
    for line in rows:
        parts = line.split()
        measurements.require(len(parts) == 6, "installed package row fields differ")
        name, version, arch, origin, repository, installed = parts
        measurements.require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]{0,127}", name)
                             and name not in names, "invalid or duplicate installed package")
        measurements.require(all(value and len(value) <= 255
                                 for value in (version, arch, origin, repository)),
                             "invalid installed package field")
        packages.append({
            "name": name, "version": version, "arch": arch, "origin": origin,
            "installed_repository": repository,
            "installed_bytes": measurements.nonnegative(int(installed), "installed bytes"),
        })
        names.add(name)
    return packages


def repository_databases(archive: Path, temporary: Path) -> tuple[list[dict], dict]:
    regular(archive, MAX_ARCHIVE_BYTES)
    catalogues, records, seen = [], {}, set()
    with tarfile.open(archive, "r:*") as retained:
        member_count = 0
        for member in retained:
            member_count += 1
            measurements.require(member_count <= 100_000,
                                 "retained archive member count outside bound")
            match = REPOSITORY_DB.fullmatch(member.name)
            if not match:
                continue
            repository = match.group(1)
            measurements.require(repository not in seen and member.isfile()
                                 and not member.issym() and not member.islnk(),
                                 "duplicate or redirected repository database")
            measurements.require(0 < member.size <= MAX_DATABASE_BYTES,
                                 "repository database byte size outside bound")
            source = retained.extractfile(member)
            measurements.require(source is not None, "repository database unavailable")
            data = source.read(MAX_DATABASE_BYTES + 1)
            measurements.require(len(data) == member.size, "repository database size differs")
            target = temporary / f"{len(catalogues):03d}.sqlite"
            target.write_bytes(data)
            identity = measurements.digest(data)
            with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as database:
                measurements.require(database.execute("pragma quick_check").fetchone() == ("ok",),
                                     "repository database integrity check failed")
                columns = {row[1] for row in database.execute("pragma table_info(packages)")}
                measurements.require(REQUIRED_COLUMNS <= columns,
                                     "repository package schema differs")
                query = ("select name,version,arch,origin,pkgsize,flatsize,cksum,path "
                         "from packages order by name,version")
                for row in database.execute(query):
                    name, version, arch, origin, pkgsize, flatsize, checksum, package_path = row
                    measurements.require(type(pkgsize) is int and pkgsize >= 0
                                         and type(flatsize) is int and flatsize >= 0,
                                         "repository package size differs")
                    value = {
                        "name": name, "version": version, "arch": arch, "origin": origin,
                        "download_bytes": pkgsize, "installed_bytes_catalogue": flatsize,
                        "archive_checksum": checksum, "archive_path": package_path,
                        "repository": repository,
                    }
                    records.setdefault((name, version), []).append(value)
            catalogues.append({"repository": repository, "format": "native-sqlite",
                               "identity": identity,
                               "size_bytes": len(data)})
            seen.add(repository)
    measurements.require(catalogues, "no native repository databases retained")
    return sorted(catalogues, key=lambda row: row["repository"]), records


def package_catalogue(specification: str) -> tuple[dict, list[dict]]:
    measurements.require("=" in specification, "package catalogue must be ID=PATH")
    repository, filename = specification.split("=", 1)
    measurements.require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", repository),
                         "invalid package catalogue ID")
    path = Path(filename)
    identity, size = file_identity(path, 64 * 1024 * 1024)
    with tarfile.open(path, "r:*") as retained:
        members = retained.getmembers()
        measurements.require(len(members) == 1 and members[0].name == "packagesite.yaml"
                             and members[0].isfile() and not members[0].issym()
                             and not members[0].islnk(), "packagesite archive members differ")
        measurements.require(0 < members[0].size <= 64 * 1024 * 1024,
                             "packagesite payload byte size outside bound")
        stream = retained.extractfile(members[0])
        measurements.require(stream is not None, "packagesite payload unavailable")
        raw = stream.read(64 * 1024 * 1024 + 1)
    measurements.require(len(raw) == members[0].size,
                         "packagesite payload byte size differs")
    rows = []
    for line in raw.splitlines():
        try:
            value = json.loads(line, object_pairs_hook=measurements.unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid packagesite JSON line") from error
        measurements.require(isinstance(value, dict) and {
            "name", "version", "abi", "origin", "pkgsize", "flatsize", "sum", "repopath"
        } <= set(value), "packagesite package fields differ")
        for field in ("name", "version", "abi", "origin", "sum", "repopath"):
            measurements.require(isinstance(value[field], str) and value[field]
                                 and len(value[field]) <= 1024,
                                 f"invalid packagesite {field}")
        parts = Path(value["repopath"]).parts
        measurements.require(not Path(value["repopath"]).is_absolute()
                             and parts[:1] == ("All",)
                             and all(part not in ("", ".", "..") for part in parts)
                             and "\\" not in value["repopath"],
                             "unsafe packagesite archive path")
        rows.append({
            "name": value["name"], "version": value["version"],
            "arch": value["abi"], "origin": value["origin"],
            "download_bytes": measurements.nonnegative(value["pkgsize"], "package bytes"),
            "installed_bytes_catalogue": measurements.nonnegative(
                value["flatsize"], "package installed bytes"
            ),
            "archive_checksum": value["sum"], "archive_path": value["repopath"],
            "repository": repository,
        })
    measurements.require(rows, "packagesite catalogue is empty")
    return ({"repository": repository, "format": "packagesite.pkg",
             "identity": identity, "size_bytes": size}, rows)


def repository_aliases(specifications: list[str] | None) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for specification in specifications or []:
        measurements.require("=" in specification, "repository alias must be INSTALLED=SOURCE")
        installed, source = specification.split("=", 1)
        for value in (installed, source):
            measurements.require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value),
                                 "invalid repository alias")
        measurements.require(source not in aliases.setdefault(installed, []),
                             "duplicate repository alias")
        aliases[installed].append(source)
    return aliases


def select(installed: list[dict], records: dict,
           aliases: dict[str, list[str]]) -> list[dict]:
    selected = []
    for package in installed:
        candidates = [row for row in records.get((package["name"], package["version"]), [])
                      if row["arch"] == package["arch"] and row["origin"] == package["origin"]]
        measurements.require(candidates, f"installed package absent from retained catalogues: {package['name']}")
        exact = [row for row in candidates
                 if row["repository"] == package["installed_repository"]]
        if exact:
            candidates = exact
        else:
            for source in aliases.get(package["installed_repository"], []):
                associated = [row for row in candidates if row["repository"] == source]
                if associated:
                    candidates = associated
                    break
        comparable = {(row["download_bytes"], row["installed_bytes_catalogue"],
                       row["archive_checksum"], row["archive_path"]) for row in candidates}
        measurements.require(len(comparable) == 1,
                             f"ambiguous retained package identity: {package['name']}")
        row = candidates[0]
        selected.append({**package,
                         "download_bytes": row["download_bytes"],
                         "installed_bytes_catalogue": row["installed_bytes_catalogue"],
                         "archive_checksum": row["archive_checksum"],
                         "archive_path": row["archive_path"],
                         "source_catalogues": sorted({item["repository"] for item in candidates})})
    return sorted(selected, key=lambda row: row["name"])


def build(image: Path, archive: Path, installed_path: Path, target_path: Path,
          additional_catalogues: list[str] | None = None,
          replacement_catalogues: list[str] | None = None,
          alias_specifications: list[str] | None = None) -> tuple[dict, dict]:
    target = load_target(target_path)
    image_identity, image_size = file_identity(image, MAX_IMAGE_BYTES)
    installed = manifest(installed_path)
    with tempfile.TemporaryDirectory() as temporary:
        catalogues, records = repository_databases(archive, Path(temporary))
        for specification in replacement_catalogues or []:
            catalogue, rows = package_catalogue(specification)
            repository = catalogue["repository"]
            measurements.require(repository in {item["repository"] for item in catalogues},
                                 "replacement package catalogue ID is not retained")
            catalogues = [item for item in catalogues if item["repository"] != repository]
            for key in list(records):
                records[key] = [row for row in records[key]
                                if row["repository"] != repository]
                if not records[key]:
                    del records[key]
            catalogues.append(catalogue)
            for row in rows:
                records.setdefault((row["name"], row["version"]), []).append(row)
        for specification in additional_catalogues or []:
            catalogue, rows = package_catalogue(specification)
            measurements.require(catalogue["repository"] not in {
                item["repository"] for item in catalogues
            }, "duplicate package catalogue ID")
            catalogues.append(catalogue)
            for row in rows:
                records.setdefault((row["name"], row["version"]), []).append(row)
        catalogues.sort(key=lambda row: row["repository"])
        aliases = repository_aliases(alias_specifications)
        packages = select(installed, records, aliases)
    catalogue_identity = measurements.content_identity(catalogues)
    inventory = {
        "schema": INVENTORY_SCHEMA,
        "catalogue_identity": catalogue_identity,
        "catalogue_databases": catalogues,
        "repository_aliases": aliases,
        "package_count": len(packages),
        "download_bytes": sum(row["download_bytes"] for row in packages),
        "installed_bytes": sum(row["installed_bytes"] for row in packages),
        "packages": packages,
        "limitations": (
            "Retained native catalogue and installed-state identity only; this record "
            "does not authenticate the catalogue or grant install or release acceptance."
        ),
    }
    inventory["identity"] = measurements.content_identity(inventory)
    context = {
        "schema": measurements.CONTEXT_SCHEMA,
        "image": {"identity": image_identity, "release": target["release"],
                  "size_bytes": image_size},
        "selection": {"identity": inventory["identity"],
                      "catalogue_identity": catalogue_identity,
                      "package_count": inventory["package_count"],
                      "download_bytes": inventory["download_bytes"]},
        "target": target["target"],
    }
    return inventory, context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--package-evidence", type=Path, required=True)
    parser.add_argument("--installed-manifest", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--catalogue", action="append", default=[], metavar="ID=PATH",
                        help="additional retained packagesite.pkg catalogue")
    parser.add_argument("--replace-catalogue", action="append", default=[],
                        metavar="ID=PATH",
                        help="replace a refreshed native DB with its immutable install-time catalogue")
    parser.add_argument("--repository-alias", action="append", default=[],
                        metavar="INSTALLED=SOURCE",
                        help="reviewed source repository name rewritten in installed records")
    parser.add_argument("--inventory-output", type=Path, required=True)
    parser.add_argument("--context-output", type=Path, required=True)
    args = parser.parse_args(argv)
    measurements.require(args.inventory_output != args.context_output,
                         "inventory and context outputs must differ")
    measurements.require(not args.inventory_output.exists() and not args.context_output.exists(),
                         "output already exists")
    inventory, context = build(args.image, args.package_evidence,
                               args.installed_manifest, args.target, args.catalogue,
                               args.replace_catalogue, args.repository_alias)
    measurements.write_new(args.inventory_output, inventory)
    measurements.write_new(args.context_output, context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
