#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""DRAFT generator for the daemonarchy (product) retained-project manifest and profile.

Run with the Literate AI runtime's interpreter (it imports literate_ai) from the
project root, after `closure-inventory.py` and `stage-closure.py` have produced the
untracked ./closure directory:

    litai-venv/bin/python tools/retained-draft/draft-retained-inputs.py \
        --manifest-out /abs/path/outside/tree/manifest.draft.json

It writes the two tracked draft authority files next to itself (profile and test
policy) and the full inventory manifest (NOT tracked) to --manifest-out.  It reads,
hashes and lists; it runs nothing from the tree and asserts no build, test, signing or
acceptance result.  See PROVENANCE.md for every unknown.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

from literate_ai.contracts.execution_dispatch import ExecutionWorker, ExecutionWorkerKind
from literate_ai.contracts.retained_project import (
    RetainedProjectLimits,
    RetainedProjectManifest,
    RetainedProjectMember,
    RetainedProjectTreePolicy,
)
from literate_ai.contracts.retained_project_lifecycle import RetainedProjectProfile
from literate_ai.contracts.retained_project_tests import RetainedProjectTestPolicy
from literate_ai.projects import ProjectConfigurationStore

HERE = "tools/retained-draft"
PROFILE = HERE + "/profile.draft.json"
POLICY = HERE + "/test-policy.draft.json"
REPORT_TOOL = HERE + "/unittest-report.py"
CLOSURE = HERE + "/closure-inventory.json"
RELEASE = "literate.release.json"
TARGET = "freebsd"
TC = "closure/toolchain/bin/"
# _build: litai cache (git-ignored); retained-out: sealed outputs, not inputs.
EXCLUDED_TOP = {".git", ".literate", "literate.project.json", "retained-out", "_build"}
RELEASE_TAG = "packages-16-amd64-1.5.0"

# Python suites that .github/workflows/release-14-controls.yml runs as
# `python3 tests/X.py -v` (plain) or `python3 -I tests/X.py -v` (isolated).
# gui-package-gtk.py is omitted: CI notes it skips without PyGObject and a display,
# and no skip is authorized here.  Shell suites have no per-case report (UNKNOWN).
DOCS = ("docs-lifecycle", "docs-release-sync")
PLAIN = ("build-timing-record", "install-trace", "install-trace-baseline", "gpu-report",
         "login-trace", "package-feed-manifest", "package-feed-stage",
         "package-feed-upload", "package-mirror-plan", "parallel-fetch",
         "release-check-1.4", "release-prepare-fill", "version-sync")
ISOLATED = ("extension-bundles", "gui-package-manager", "gui-package-transaction",
            "gui-package-window", "installer-extensions", "installer-progress-stats",
            "installer-sdk-audit", "plugins-and-games", "sdk-windows", "visual-sdk")
TEST_FILES = tuple("tests/%s.py" % n for n in DOCS + PLAIN + ISOLATED)
BUILD_FILES = ("build-iso.sh", "scripts/master-release.sh", "scripts/image-architecture.sh",
               "origins.sh", "live-post.sh", "scripts/iso-stage.sh",
               "scripts/cache-release-sets.sh", "scripts/check-checkout-feed-abi.sh",
               "scripts/check-gpu-packages.sh", "scripts/check-image-size.sh",
               "scripts/check-closure-feed.sh", "scripts/make-efi-iso.sh",
               HERE + "/run-build-iso.sh", HERE + "/build-iso.env",
               HERE + "/ambient-preflight.py", HERE + "/accept-image.py",
               HERE + "/closure-inventory.json", HERE + "/closure-spec.json")
# Documentation selection (project-authored docs; docs/ is the project's documentation root).
DOC_INCLUDE = ("docs/**/*.md", "*.md", "components/**/*.md", "secureboot/**/*.md",
               "overlay/**/*.md", "skills/**/*.md", "workflows/**/*.md", "sdk/**/*.md",
               "tools/**/*.md")


def role_of(path: str) -> str:
    if path.startswith("closure/toolchain/"):
        return "toolchain"
    if path.startswith("closure/dependency/"):
        return "dependency"
    if path == RELEASE:
        return "release-policy"
    if path == POLICY:
        return "test-policy"
    if path == PROFILE or path in BUILD_FILES:
        return "build-definition"
    if path in TEST_FILES or path == REPORT_TOOL or path.startswith("tests/"):
        return "test-definition"
    if path.startswith("docs/") or path.endswith(".md") and "/" not in path \
            or path == HERE + "/docs-tree-check.py":
        return "docs-definition"
    return "source"


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def inventory(root: Path, roots):
    members, dirs = [], []

    def visit(rel: str):
        full = root / rel
        st = os.lstat(full)
        if stat.S_ISLNK(st.st_mode):
            target = os.readlink(full)
            data = target.encode()
            members.append(RetainedProjectMember(rel, len(data), 0o120000,
                hashlib.sha256(data).hexdigest(), role_of(rel), symlink_target=target))
        elif stat.S_ISDIR(st.st_mode):
            dirs.append(rel)
            for name in os.listdir(full):
                visit(rel + "/" + name)
        elif stat.S_ISREG(st.st_mode):
            mode = 0o755 if st.st_mode & 0o111 else 0o644
            members.append(RetainedProjectMember(rel, st.st_size, mode,
                sha256(full), role_of(rel)))
        else:
            raise SystemExit("special file in retained roots: " + rel)

    for r in roots:
        visit(r)
    members.sort(key=lambda m: m.path)
    return tuple(members), tuple(sorted(dirs))


def cases_for(names):
    cases = []
    for name in names:
        path = "tests/%s.py" % name
        tree = ast.parse(Path(path).read_text())
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test"):
                        cases.append(f"{name}.{node.name}.{item.name}")
    return tuple(sorted(set(cases)))


def doc_files(root: Path):
    spec = importlib.util.spec_from_file_location("docs_tree_check", root / HERE / "docs-tree-check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "_build", "closure", "retained-out"))
        for n in sorted(names):
            rel = os.path.relpath(os.path.join(base, n), root)
            if module.matches(rel, DOC_INCLUDE):
                found.append(rel)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-out", required=True)
    args = ap.parse_args()
    root = Path.cwd().resolve()
    roots = tuple(sorted(n for n in os.listdir(root) if n not in EXCLUDED_TOP))
    definition = ProjectConfigurationStore(root).read().definition
    closure = json.loads((root / CLOSURE).read_text())
    if closure["problems"]:
        raise SystemExit("closure inventory has unresolved problems")

    plain, isolated = cases_for(PLAIN), cases_for(ISOLATED)
    policy = RetainedProjectTestPolicy.from_dict({
        "schema": "literate-ai/retained-project-test-policy@1",
        "project_policy_identity": definition.test_receipt_policy.identity.uri,
        "cases": [{"id": c, "action": "draft-ci-isolated-tests" if c in isolated
                   else "draft-ci-tests", "skip_reason": None}
                  for c in sorted(set(plain) | set(isolated))],
        "reports": [{"action": "draft-ci-isolated-tests",
                     "path": "tests-isolated/ci-report.json"},
                    {"action": "draft-ci-tests", "path": "tests/ci-report.json"}],
    })
    (root / POLICY).write_text(json.dumps(policy.to_dict(), indent=2) + "\n")

    limits = RetainedProjectLimits(100_000, 128 * 1024 * 1024, 2 * 1024**3)
    tree = RetainedProjectTreePolicy(case_sensitive=True)
    profile_stub = root / PROFILE
    profile_stub.write_text("{}\n")
    members, dirs = inventory(root, roots)
    provisional = RetainedProjectManifest(roots, members, limits, dirs, (), tree)
    by_path = {m.path: m for m in members}

    def tool(name):
        m = by_path[TC + name]
        return {"name": name, "path": m.path, "identity": "sha256:" + m.sha256}

    worker = ExecutionWorker("local", ExecutionWorkerKind.LOCAL, target_profile=TARGET)
    py = TC + "python3.12"
    docs_files = doc_files(root)
    libdirs = ["closure/toolchain/lib"]
    ambient_items = ["ambient:" + a["name"] for a in closure["ambient"]]
    profile = {
        "schema": "literate-ai/retained-project-profile@1",
        "authority_mode": "retained-project",
        "target": TARGET,
        "worker_identity": worker.identity.uri,
        "toolchain_identity": provisional.role_identity({"sdk", "toolchain"}).uri,
        "dependency_identity": provisional.role_identity({"dependency"}).uri,
        "test_policy_identity": "sha256:" + by_path[POLICY].sha256,
        "release_policy_identity": "sha256:" + by_path[RELEASE].sha256,
        "tools": [tool(t["name"]) for t in closure["tools"] if t["role"] == "toolchain"],
        "runtime_library_paths": libdirs,
        "actions": [
            # Refuses a run whose ambient host inputs (jail, ports tree, package set,
            # release sets, catalogue, public secure-boot artifacts) differ from the
            # reviewed closure-inventory.json.  Reads and hashes only.
            {"id": "draft-ambient-preflight", "stage": "stage", "tool": "python3.12",
             "argv": [py, HERE + "/ambient-preflight.py", "--inventory", CLOSURE,
                      "--output", "{output_root}/preflight/ambient.json"],
             "requires": [], "inventory": ambient_items, "outputs": ["preflight"],
             "timeout_seconds": 7200},
            # HACKING.md "Build the image" step 5 (`./build-iso.sh`) through the wrapper that
            # maps the reviewed environment (build-iso.env) and OUTDIR onto build-iso.sh.
            # Runs as root (poudriere).  Its ISO, .xz and .sha256 files are the outputs.
            {"id": "draft-build-iso", "stage": "build", "tool": "sh",
             "argv": [TC + "sh", HERE + "/run-build-iso.sh", "{output_root}/images"],
             "requires": ["draft-ambient-preflight"],
             "inventory": ["build-iso.sh", "run-build-iso.sh"], "outputs": ["images"],
             "timeout_seconds": 86400},
            # CI "Documentation graph matches the Literate AI authority gate" and
            # "Documentation and release media agree".
            {"id": "draft-docs-tests", "stage": "docs", "tool": "python3.12",
             "argv": [py, "-B", REPORT_TOOL, "--action", "draft-docs-tests"]
                     + [a for n in DOCS for a in ("--test-file", "tests/%s.py" % n)]
                     + ["--output", "{output_root}/docs/report.json"],
             "requires": ["draft-build-iso"],
             "inventory": ["docs-lifecycle", "docs-release-sync"],
             "outputs": ["docs"], "timeout_seconds": 3600},
            # Whole-tree check of every project-authored Markdown file (links, images,
            # fragments, UTF-8).  Selection: DOC_INCLUDE in the generator.
            {"id": "draft-docs-tree", "stage": "docs", "tool": "python3.12",
             "argv": [py, "-B", HERE + "/docs-tree-check.py", "--root", "."]
                     + [a for p in DOC_INCLUDE for a in ("--include", p)]
                     + ["--output", "{output_root}/docs-tree/report.json"],
             "requires": ["draft-build-iso"],
             "inventory": ["docs-tree:" + f for f in docs_files],
             "outputs": ["docs-tree"], "timeout_seconds": 3600},
            # release-14-controls.yml `python3 tests/X.py -v` steps.
            {"id": "draft-ci-tests", "stage": "test", "tool": "python3.12",
             "argv": [py, "-B", REPORT_TOOL, "--action", "draft-ci-tests"]
                     + [a for n in PLAIN for a in ("--test-file", "tests/%s.py" % n)]
                     + ["--output", "{output_root}/tests/ci-report.json"],
             "requires": ["draft-build-iso"],
             "inventory": list(plain), "outputs": ["tests"], "timeout_seconds": 3600},
            # The CI steps run as `python3 -I tests/X.py -v`.  -B is added: -I ignores
            # PYTHONDONTWRITEBYTECODE and would otherwise write .pyc files into the
            # frozen input snapshot.
            {"id": "draft-ci-isolated-tests", "stage": "test", "tool": "python3.12",
             "argv": [py, "-I", "-B", REPORT_TOOL, "--action", "draft-ci-isolated-tests"]
                     + [a for n in ISOLATED for a in ("--test-file", "tests/%s.py" % n)]
                     + ["--output", "{output_root}/tests-isolated/ci-report.json"],
             "requires": ["draft-build-iso"],
             "inventory": list(isolated), "outputs": ["tests-isolated"], "timeout_seconds": 3600},
            # STATIC image acceptance by a verifier separate from build-iso.sh and
            # master-release.sh verify.  VM/QEMU and physical acceptance are not defined
            # as retained actions (UNKNOWN) and no acceptance policy file exists.
            {"id": "draft-accept-image", "stage": "accept", "tool": "python3.12",
             "argv": [py, "-B", HERE + "/accept-image.py", "--images", "{output_root}/images",
                      "--version-file", "VERSION", "--expect-tag", RELEASE_TAG,
                      "--output", "{output_root}/acceptance/image.json"],
             "requires": ["draft-ambient-preflight", "draft-build-iso", "draft-docs-tests",
                          "draft-docs-tree", "draft-ci-tests", "draft-ci-isolated-tests"],
             "inventory": ["image:" + c for c in
                           ("present", "sidecar-iso", "sidecar-xz", "xz-roundtrip", "budget-raw",
                            "budget-xz", "iso9660", "image-version", "image-abi", "image-tag",
                            "live-sqlite3")],
             "outputs": ["acceptance"], "timeout_seconds": 3600},
        ],
        "package_inventory": ["images"],
    }
    RetainedProjectProfile.from_dict(profile)
    profile_stub.write_text(json.dumps(profile, indent=2) + "\n")

    members, dirs = inventory(root, roots)
    manifest = RetainedProjectManifest(roots, members, limits, dirs, (), tree)
    out = Path(args.manifest_out)
    out.write_text(json.dumps(manifest.to_dict(), separators=(",", ":")) + "\n")
    print(json.dumps({
        "roots": len(roots), "members": len(members), "directories": len(dirs),
        "symlinks": sum(1 for m in members if m.symlink_target is not None),
        "total_bytes": sum(m.size for m in members),
        "tools": len(profile["tools"]), "doc_files": len(docs_files),
        "test_cases_plain": len(plain), "test_cases_isolated": len(isolated),
        "manifest_identity": manifest.identity.uri,
        "profile_identity": RetainedProjectProfile.from_dict(profile).identity.uri,
        "worker_identity": worker.identity.uri,
        "toolchain_identity": profile["toolchain_identity"],
        "dependency_identity": profile["dependency_identity"],
        "test_policy_identity": profile["test_policy_identity"],
        "release_policy_identity": profile["release_policy_identity"],
    }, indent=2))


if __name__ == "__main__":
    sys.exit(main())
