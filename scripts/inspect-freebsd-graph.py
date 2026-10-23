#!/usr/bin/env python3
"""Inspect pinned Git trees for native Component discovery; never qualify them.

This reads Git objects, not working files, and never evaluates a Makefile. Output
is discovery evidence for subsequent canonical LitAI admission, not a substitute
Component catalog, dependency lock, pkg manifest, SBOM or execution receipt.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


MAX_ENTRIES = 1_000_000
MAX_DECLARATION_BYTES = 32 * 1024 * 1024
VARIANTS = ("host", "common", "amd64", "i386", "arm64", "aarch64", "riscv", "powerpc")


def git(repo, *args, input=None):
    return subprocess.run(["git", "-C", str(repo), *args], input=input,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True, timeout=180).stdout


def tree(repo, revision):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("select a full source commit, not a branch or abbreviation")
    if git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip() != revision:
        raise ValueError("source selection is not an exact commit")
    result = []
    for raw in git(repo, "ls-tree", "-r", "-z", revision).split(b"\0"):
        if not raw:
            continue
        metadata, name = raw.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        name = name.decode("utf-8", errors="strict")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or any(ord(c) < 32 for c in name):
            raise ValueError("unsupported source path")
        if kind != "blob" or mode not in ("100644", "100755", "120000"):
            raise ValueError(f"separately admit unsupported Git entry: {name} ({kind}/{mode})")
        result.append({"path": name, "mode": mode, "git_blob": oid})
        if len(result) > MAX_ENTRIES:
            raise ValueError("tree exceeds bounded discovery inventory")
    if not result:
        raise ValueError("empty source tree")
    return sorted(result, key=lambda item: item["path"])


def declarations(repo, entries):
    selected = [e for e in entries if e["mode"] != "120000"
                and PurePosixPath(e["path"]).name.startswith("Makefile.depend")]
    if not selected:
        return {}
    if len(selected) > 20_000:
        raise ValueError("too many native dependency declaration files")
    request = "".join(e["git_blob"] + "\n" for e in selected).encode()
    checks = git(repo, "cat-file", "--batch-check", input=request).decode().splitlines()
    if len(checks) != len(selected):
        raise ValueError("incomplete declaration object inventory")
    total = 0
    for entry, line in zip(selected, checks):
        oid, kind, size = line.split()
        if oid != entry["git_blob"] or kind != "blob":
            raise ValueError("dependency declaration object mismatch")
        size = int(size)
        if size > 1024 * 1024:
            raise ValueError("dependency declaration exceeds one MiB")
        total += size
    if total > MAX_DECLARATION_BYTES:
        raise ValueError("native declarations exceed bounded discovery budget")
    raw = git(repo, "cat-file", "--batch", input=request)
    offset = 0
    output = {}
    for entry in selected:
        end = raw.index(b"\n", offset)
        oid, kind, size = raw[offset:end].decode().split()
        if oid != entry["git_blob"] or kind != "blob":
            raise ValueError("dependency declaration content mismatch")
        start = end + 1
        offset = start + int(size)
        if raw[offset:offset + 1] != b"\n":
            raise ValueError("invalid declaration object framing")
        output[entry["path"]] = raw[start:offset].decode("utf-8", errors="strict")
        offset += 1
    if offset != len(raw):
        raise ValueError("unexpected dependency declaration content")
    return output


def literal_references(text):
    """Retain lexical declarations and condition context without evaluating make."""
    conditions = []
    statements = []
    for line in re.sub(r"\\\n", " ", text).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"\.if(?:n?def|n?make)?\b", line):
            conditions.append(line)
        elif re.match(r"\.(elif|else)\b", line):
            if not conditions:
                raise ValueError("unbalanced native dependency condition")
            conditions[-1] += " ; " + line
        elif re.match(r"\.endif\b", line):
            if not conditions:
                raise ValueError("unbalanced native dependency condition")
            conditions.pop()
        elif line.startswith("DIRDEPS"):
            match = re.match(r"(DIRDEPS(?:\.[^\s=]+?)?)\s*(\+=|:=|\?=|=)\s*(.*)", line)
            if match:
                tokens = match[3].split("#", 1)[0].split()
                statements.extend({"token": token, "variable": match[1], "assignment": match[2],
                                   "declaration_type": "directory-reference",
                                   "conditions": list(conditions)} for token in tokens)
            else:
                statements.append({"token": line, "assignment": "unparsed",
                                   "declaration_type": "native-control-statement",
                                   "conditions": list(conditions)})
    if conditions:
        raise ValueError("unbalanced native dependency condition")
    return statements


def discover(kind, repo, revision):
    entries = tree(repo, revision)
    roots = {}
    if kind == "source":
        for entry in entries:
            path = PurePosixPath(entry["path"])
            if path.name == "Makefile" or path.name.startswith("Makefile.depend"):
                roots[path.parent.as_posix()] = "native-build-directory"
        # Support and vendored sources remain explicit candidates, not hidden
        # under the world aggregate. Native consumers are not guessed here.
        for entry in entries:
            parts = PurePosixPath(entry["path"]).parts
            if len(parts) >= 3 and parts[0] in ("contrib", "crypto"):
                roots.setdefault("/".join(parts[:2]), "retained-vendor-inputs")
            elif len(parts) >= 4 and parts[:2] == ("sys", "dev"):
                roots.setdefault("/".join(parts[:3]), "driver-source-inputs")
    elif kind == "ports":
        reserved = {"Mk", "Tools", "Templates", "Keywords", ".github"}
        for entry in entries:
            parts = PurePosixPath(entry["path"]).parts
            if len(parts) == 3 and parts[2] == "Makefile" and parts[0] not in reserved:
                roots["/".join(parts[:2])] = "port-origin"
    else:
        raise ValueError("unknown source tree kind")
    roots.setdefault(".", "shared-repository-inputs")
    # Shared top-level/category inputs receive an explicit support owner.
    for entry in entries:
        parts = PurePosixPath(entry["path"]).parts
        if len(parts) > 1:
            roots.setdefault(parts[0], "shared-tree-inputs")
    nodes = {root: {"id": f"{kind}:{root}", "root": root, "kind": unit_kind,
                    "input_count": 0, "input_identity": "", "ownership_reviewed": False,
                    "canonical_component_registered": False, "pkg_required": True,
                    "pkg_status": "not-produced", "native_dependencies_complete": False}
             for root, unit_kind in sorted(roots.items())}
    memberships = {root: hashlib.sha256() for root in nodes}
    for entry in entries:
        parent = PurePosixPath(entry["path"]).parent
        while parent.as_posix() not in nodes:
            parent = parent.parent
        owner = parent.as_posix()
        entry["candidate_owner"] = nodes[owner]["id"]
        nodes[owner]["input_count"] += 1
        memberships[owner].update(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    for root, hasher in memberships.items():
        nodes[root]["input_identity"] = "sha256:" + hasher.hexdigest()
    edges = []
    controls = []
    if kind == "source":
        for path, text in sorted(declarations(repo, entries).items()):
            consumer = PurePosixPath(path).parent.as_posix()
            variant = PurePosixPath(path).name.removeprefix("Makefile.depend").removeprefix(".") or None
            for declaration in literal_references(text):
                if declaration["declaration_type"] != "directory-reference":
                    controls.append({"declaration_file": path, **declaration})
                    continue
                token = declaration["token"]
                provider = token if token in nodes else None
                provider_variant = None
                if provider is None:
                    for suffix in VARIANTS:
                        if token.endswith("." + suffix) and token[:-(len(suffix) + 1)] in nodes:
                            provider = token[:-(len(suffix) + 1)]
                            provider_variant = suffix
                            break
                edges.append({"consumer": nodes[consumer]["id"],
                              "provider": nodes[provider]["id"] if provider else None,
                              "consumer_variant": variant, "provider_variant": provider_variant,
                              "declaration_file": path, **declaration,
                              "kind": "declared-directory-reference", "native_context_evaluated": False})
    return {
        "schema": "daemonarchy/native-tree-discovery@1", "kind": kind,
        "revision": revision, "git_tree": git(repo, "rev-parse", f"{revision}^{{tree}}").decode().strip(),
        "state": "discovery-only", "canonical_catalog": False, "acceptance": "not-qualified",
        "identity_semantics": "SHA256 inventory binds paths, Git blob IDs and candidate owners; not content SHA256 admission",
        "counts": {"tracked_inputs": len(entries), "candidate_units": len(nodes),
                   "port_origins": sum(n["kind"] == "port-origin" for n in nodes.values()),
                   "declared_directory_references": len(edges),
                   "unresolved_reference_tokens": sum(e["provider"] is None for e in edges),
                   "native_control_statements": len(controls), "native_evaluated_contexts": 0,
                   "origins_needing_native_dependency_resolution": sum(n["kind"] == "port-origin" for n in nodes.values()),
                   "reviewed_input_owners": 0, "canonical_components": 0, "qualified_packages": 0},
        "limitations": ["No Makefile evaluation or target/options resolution",
                        "Directory candidates do not prove logical build-unit completeness",
                        "Candidate ownership needs review and shared-consumer input relationships",
                        "Native dependency conditions, includes and bootstrap cycles remain unresolved",
                        "Ports dependencies require native selected-variant metadata",
                        "No canonical Components, locks, packages, SBOMs or receipts are fabricated"],
        "candidate_units": list(nodes.values()), "inputs": entries, "declared_references": edges,
        "native_control_statements": controls,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("source", "ports"), required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        repository = args.repo.resolve()
        output = args.output.resolve()
        if repository == output or repository in output.parents:
            raise ValueError("write discovery evidence outside the inspected repository")
        value = discover(args.kind, repository, args.revision)
        encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with output.open("xb") as stream:
            stream.write(encoded)
        print(json.dumps({"path": str(output), "sha256": hashlib.sha256(encoded).hexdigest(),
                          "counts": value["counts"], "state": value["state"]}, sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"native-tree-discovery: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
