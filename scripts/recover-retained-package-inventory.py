#!/usr/bin/env python3
"""Recover pinned historical archive identities without new cache or release admission."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

SHA = re.compile(r"[0-9a-f]{64}\Z")
UNKNOWN = ("current_selection", "source_inputs", "port_inputs", "options", "flavor",
           "generated_inputs", "toolchain", "sysroot", "build_dependencies", "abi",
           "native_archive_checksum", "runtime_abi_contracts", "native_requalification")


def digest(value):
    if not isinstance(value, str) or not SHA.fullmatch(value.removeprefix("sha256:")):
        raise ValueError("invalid SHA-256 identity")
    return value.removeprefix("sha256:")


def read_pinned(path, expected):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("historical manifest must be a bounded regular file")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest(expected):
        raise ValueError("historical metadata differs from selected SHA-256")
    return json.loads(data)


def archive_name(name):
    if (not isinstance(name, str) or name.startswith("/") or "\\" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
            or not name.endswith(".pkg") or any(ord(c) < 32 for c in name)):
        raise ValueError("unsafe historical archive name")
    return name


def recover(manifest, manifest_sha, provenance, provenance_sha):
    manifest_sha, provenance_sha = digest(manifest_sha), digest(provenance_sha)
    if not isinstance(manifest, dict) or not isinstance(provenance, dict):
        raise ValueError("historical metadata must be objects")
    if (manifest.get("schema") != "daemonarchy/madmax-package-import@2"
            or manifest.get("assembly_kind") != "selected-base-installed-reuse"
            or provenance.get("schema") != "daemonarchy/package-reuse-candidate@1"
            or provenance.get("status") != "admitted_for_release"):
        raise ValueError("unsupported historical manifest or qualification scope")
    if digest(manifest["reuse_provenance_sha256"]) != provenance_sha:
        raise ValueError("historical manifest does not bind selected provenance")
    for key in ("source_revision", "ports_revision"):
        if manifest.get(key) != provenance.get(key):
            raise ValueError("historical assembly/provenance revisions differ")
    if manifest.get("jail_osversion") != provenance.get("selected_base_osversion"):
        raise ValueError("historical selected base differs")
    packages = manifest["packages"]
    if not isinstance(packages, dict) or not 1 <= len(packages) <= 100000:
        raise ValueError("empty or oversized historical inventory")
    for name, identity in packages.items():
        archive_name(name)
        if not isinstance(identity, list) or len(identity) != 2 or type(identity[0]) is not int or identity[0] <= 0:
            raise ValueError("invalid historical archive size/identity")
        digest(identity[1])
    admitted = {}
    if not isinstance(provenance.get("retained_archives"), list):
        raise ValueError("historical admissions must be a list")
    for item in provenance["retained_archives"]:
        if not isinstance(item, dict):
            raise ValueError("historical admission must be an object")
        name = archive_name(item["archive"])
        if name in admitted or item.get("qualification") != "admitted_for_release":
            raise ValueError("duplicate or unqualified historical admission")
        if name not in packages or digest(item["sha256"]) != digest(packages[name][1]):
            raise ValueError("historical admitted archive differs from manifest")
        admitted[name] = item
    rows = []
    for name, identity in sorted(packages.items()):
        item = admitted.get(name)
        rows.append(dict(archive=name, bytes=identity[0], sha256=digest(identity[1]),
                         package_name=item.get("name") if item else None,
                         package_version=item.get("version") if item else None,
                         historical_state="admitted_for_recorded_1.3.1_scope" if item else "retained_archive_identity_only",
                         historical_provenance_sha256=provenance_sha if item else None,
                         current_release="1.4", admitted_for_current_release=False,
                         current_compilation_decision="not_determined_by_historical_inventory",
                         unknown_current_identities=list(UNKNOWN), bytes_verified_in_this_run=False))
    return dict(schema="daemonarchy/historical-retained-package-inventory@1", packages=rows,
                input_sha256=dict(manifest=manifest_sha, provenance=provenance_sha),
                counts=dict(sorted(Counter(row["historical_state"] for row in rows).items())),
                archive_count=len(rows), archive_bytes=sum(row["bytes"] for row in rows),
                historical_scope=provenance.get("qualification_scope"),
                historical_evidence=provenance.get("qualification_evidence", {}),
                historical_assembly=dict(source_revision=manifest["source_revision"], ports_revision=manifest["ports_revision"],
                                         selected_base_osversion=manifest["jail_osversion"]),
                new_native_qualification=False, cache_admission_authorized=False,
                retention_policy="read only; preserve all original archives, metadata and receipts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--provenance-sha256", required=True)
    args = parser.parse_args()
    result = recover(read_pinned(args.manifest, args.manifest_sha256), args.manifest_sha256,
                     read_pinned(args.provenance, args.provenance_sha256), args.provenance_sha256)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("historical inventory refused: " + str(error), file=sys.stderr)
        sys.exit(1)
