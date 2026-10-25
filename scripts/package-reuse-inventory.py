#!/usr/bin/env python3
"""Read-only package provenance inventory; never installs, compiles or admits bytes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "daemonarchy/package-reuse-inventory@1"
# Empty mappings/lists are explicit known-empty inputs; absent/null means unknown.
BUILD = ("source_inputs", "port_inputs", "options", "flavor", "generated_inputs",
         "toolchain", "sysroot", "build_dependencies", "command", "environment", "output_format")
RUNTIME = ("abi", "osversion", "runtime_dependencies", "runtime_abi_contracts")
IDENTITIES = BUILD + RUNTIME
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def load(path):
    return json.loads(Path(path).read_text())


def packages(snapshot):
    if snapshot.get("schema") != SCHEMA or not isinstance(snapshot.get("packages"), list):
        raise ValueError("expected package reuse inventory schema")
    result = {}
    for row in snapshot["packages"]:
        name = row.get("name")
        if not isinstance(name, str) or not name or name in result:
            raise ValueError("missing or duplicate package name (split selected variants into distinct names)")
        if not isinstance(row.get("origin"), str) or not row["origin"]:
            raise ValueError("missing package origin")
        if not isinstance(row.get("version"), str) or not row["version"]:
            raise ValueError("missing package version")
        if not isinstance(row.get("identities"), dict):
            raise ValueError("missing identities mapping")
        artifact = row.get("artifact")
        if artifact is not None:
            if (not isinstance(artifact, dict) or not SHA256.fullmatch(str(artifact.get("sha256")))
                    or type(artifact.get("bytes")) is not int or artifact["bytes"] < 0):
                raise ValueError("invalid artifact SHA-256 or size")
        result[name] = row
    return result


def catalogue(rows, assets):
    """Join public metadata by exact archive path/size without claiming authentication."""
    by_path = {}
    for asset in assets["assets"]:
        name = asset["name"]
        if name in by_path:
            raise ValueError("duplicate public asset")
        by_path[name] = asset
    output = []
    used = set()
    for row in rows:
        path = row["path"]
        asset = by_path.get(path)
        if asset is None or asset["size"] != row["pkgsize"] or path in used:
            raise ValueError("catalogue archive missing, duplicated or size differs")
        used.add(path)
        annotations = row.get("annotations", {})
        identities = dict.fromkeys(IDENTITIES)
        identities.update(options=row.get("options"), abi=row.get("abi"),
                          osversion=annotations.get("FreeBSD_version"),
                          runtime_dependencies=row.get("deps"))
        output.append(dict(name=row["name"], origin=row["origin"], version=row["version"],
                           artifact=dict(path=path, sha256=asset.get("digest"), bytes=asset["size"]),
                           identities=identities,
                           unknown_identities=[key for key in IDENTITIES if identities[key] is None]))
    extras = set(by_path) - used - {"meta", "meta.conf", "packagesite.pkg", "data.pkg"}
    if extras:
        raise ValueError("public payloads absent from catalogue: " + ", ".join(sorted(extras)))
    snapshot = dict(schema=SCHEMA, packages=sorted(output, key=lambda r: r["name"]),
                    evidence_scope="public metadata only; payload bytes and signatures not verified",
                    public_url=assets.get("url"))
    packages(snapshot)
    return snapshot


def compare(old, selected):
    before, after = packages(old), packages(selected)
    ledger = []
    for name in sorted(before.keys() | after.keys()):
        a, b = before.get(name), after.get(name)
        row = dict(name=name, old=a, selected=b)
        if a is None:
            decision, reasons = "new_package", ["absent_from_previous_selection"]
        elif b is None:
            decision, reasons = "removed_package", ["absent_from_selected_closure"]
        else:
            ai, bi = a["identities"], b["identities"]
            unknown = [key for key in IDENTITIES if ai.get(key) is None or bi.get(key) is None]
            changed_build = [key for key in BUILD if ai.get(key) is not None and bi.get(key) is not None and ai[key] != bi[key]]
            changed_runtime = [key for key in RUNTIME if ai.get(key) is not None and bi.get(key) is not None and ai[key] != bi[key]]
            changed_package = [key for key in ("origin", "version") if a[key] != b[key]]
            row.update(unknown_identities=unknown, changed_build_inputs=changed_build,
                       changed_runtime_inputs=changed_runtime)
            if changed_build:
                decision, reasons = "rebuild_required", changed_package + changed_build
            elif changed_package:
                decision, reasons = "needs_package_review", changed_package
            elif (a.get("artifact") is not None and b.get("artifact") is not None
                  and any(a["artifact"][key] != b["artifact"][key] for key in ("sha256", "bytes"))):
                decision, reasons = "needs_package_review", ["archive_identity_changed_payload_or_envelope_unknown"]
            elif changed_runtime:
                decision, reasons = "needs_requalification", changed_runtime
            elif unknown:
                decision, reasons = "blocked_missing_provenance", unknown
            else:
                decision, reasons = "needs_retained_byte_verification", ["complete_identity_unchanged"]
            if a.get("artifact") is None:
                decision, reasons = "blocked_missing_artifact", ["no_retained_archive_identity"]
        row.update(decision=decision, reasons=reasons, admitted_cache_hit=False)
        ledger.append(row)
    return dict(schema="daemonarchy/package-reuse-ledger@1", packages=ledger,
                counts=dict(sorted(Counter(r["decision"] for r in ledger).items())),
                previous_inventory_sha256="sha256:" + hashlib.sha256(encoded(old)).hexdigest(),
                selected_inventory_sha256="sha256:" + hashlib.sha256(encoded(selected)).hexdigest(),
                admitted_cache_hits=0, measured_bytes_saved=None, measured_seconds_saved=None,
                retention_policy="preserve every existing archive, installed package and cache; isolate new products")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    imported = commands.add_parser("catalogue", help="inventory JSON-lines packagesite and gh release assets JSON")
    imported.add_argument("--catalogue", type=Path, required=True)
    imported.add_argument("--assets", type=Path, required=True)
    comparison = commands.add_parser("compare", help="compare exhaustive old/selected inventories; no cache admission")
    comparison.add_argument("--previous", type=Path, required=True)
    comparison.add_argument("--selected", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "catalogue":
        result = catalogue([json.loads(line) for line in args.catalogue.read_text().splitlines() if line.strip()], load(args.assets))
        result["input_sha256"] = {
            "catalogue_json_lines": "sha256:" + hashlib.sha256(args.catalogue.read_bytes()).hexdigest(),
            "release_assets_json": "sha256:" + hashlib.sha256(args.assets.read_bytes()).hexdigest(),
        }
    else:
        result = compare(load(args.previous), load(args.selected))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
