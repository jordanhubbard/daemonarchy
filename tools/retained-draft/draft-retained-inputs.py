#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""DRAFT generator for the daemonarchy (product) retained-project manifest and profile.

Run with the Literate AI runtime's interpreter (it imports literate_ai) from the
project root, after staging the draft tools under ./sdk/bin (untracked):

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
RELEASE = "literate.release.json"
TARGET = "freebsd"
# _build: litai cache (git-ignored); retained-out: sealed outputs, not inputs.
EXCLUDED_TOP = {".git", ".literate", "literate.project.json", "retained-out", "_build"}

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
BUILD_FILES = ("build-iso.sh", "scripts/master-release.sh", "scripts/image-architecture.sh")


def role_of(path: str) -> str:
    if path == "sdk" or path.startswith("sdk/"):
        return "toolchain"
    if path == RELEASE:
        return "release-policy"
    if path == POLICY:
        return "test-policy"
    if path == PROFILE or path in BUILD_FILES:
        return "build-definition"
    if path in TEST_FILES or path == REPORT_TOOL or path.startswith("tests/"):
        return "test-definition"
    if path.startswith("docs/") or path.endswith(".md") and "/" not in path:
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-out", required=True)
    args = ap.parse_args()
    root = Path.cwd().resolve()
    roots = tuple(sorted(n for n in os.listdir(root) if n not in EXCLUDED_TOP))
    definition = ProjectConfigurationStore(root).read().definition

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

    def tool(name, rel):
        m = by_path["sdk/bin/" + rel]
        return {"name": name, "path": m.path, "identity": "sha256:" + m.sha256}

    worker = ExecutionWorker("local", ExecutionWorkerKind.LOCAL, target_profile=TARGET)
    py = "sdk/bin/python3.12"
    unknown = "UNKNOWN-placeholder-not-a-result"
    profile = {
        "schema": "literate-ai/retained-project-profile@1",
        "authority_mode": "retained-project",
        "target": TARGET,
        "worker_identity": worker.identity.uri,
        "toolchain_identity": provisional.role_identity({"sdk", "toolchain"}).uri,
        "dependency_identity": provisional.role_identity({"dependency"}).uri,
        "test_policy_identity": "sha256:" + by_path[POLICY].sha256,
        "release_policy_identity": "sha256:" + by_path[RELEASE].sha256,
        "tools": [tool("bash", "bash"), tool("echo", "echo"),
                  tool("python", "python3.12"), tool("sh", "sh")],
        "actions": [
            # Grounded: HACKING.md "Build the image" step 5 (`./build-iso.sh`).  JAIL,
            # PTREE, ARCH and the poudriere data directory are UNKNOWN on the worker.
            {"id": "draft-build-iso", "stage": "build", "tool": "sh",
             "argv": ["sdk/bin/sh", "build-iso.sh"], "requires": [],
             "inventory": ["build-iso.sh"], "outputs": ["images"],
             "timeout_seconds": 86400},
            # Grounded: scripts/master-release.sh documents a `verify` step (xz test,
            # hashes, size budget, version string, ISO contents) that needs no key.
            # The signing `feed`, `qa`, `sticks` and `all` steps are NOT included.
            {"id": "draft-master-release-verify", "stage": "build", "tool": "bash",
             "argv": ["sdk/bin/bash", "scripts/master-release.sh", "verify"],
             "requires": ["draft-build-iso"],
             "inventory": ["master-release.sh verify"], "outputs": ["verify"],
             "timeout_seconds": 3600},
            # Grounded: CI "Documentation graph matches the Literate AI authority gate"
            # and "Documentation and release media agree".
            {"id": "draft-docs-tests", "stage": "docs", "tool": "python",
             "argv": [py, REPORT_TOOL, "--action", "draft-docs-tests"]
                     + [a for n in DOCS for a in ("--test-file", "tests/%s.py" % n)]
                     + ["--output", "{output_root}/docs/report.json"],
             "requires": ["draft-build-iso", "draft-master-release-verify"],
             "inventory": ["docs-lifecycle", "docs-release-sync"],
             "outputs": ["docs"], "timeout_seconds": 3600},
            # Grounded: release-14-controls.yml `python3 tests/X.py -v` steps.
            {"id": "draft-ci-tests", "stage": "test", "tool": "python",
             "argv": [py, REPORT_TOOL, "--action", "draft-ci-tests"]
                     + [a for n in PLAIN for a in ("--test-file", "tests/%s.py" % n)]
                     + ["--output", "{output_root}/tests/ci-report.json"],
             "requires": ["draft-build-iso", "draft-master-release-verify"],
             "inventory": list(plain), "outputs": ["tests"], "timeout_seconds": 3600},
            # Grounded: the CI steps run as `python3 -I tests/X.py -v`.
            {"id": "draft-ci-isolated-tests", "stage": "test", "tool": "python",
             "argv": [py, "-I", REPORT_TOOL, "--action", "draft-ci-isolated-tests"]
                     + [a for n in ISOLATED for a in ("--test-file", "tests/%s.py" % n)]
                     + ["--output", "{output_root}/tests-isolated/ci-report.json"],
             "requires": ["draft-build-iso", "draft-master-release-verify"],
             "inventory": list(isolated), "outputs": ["tests-isolated"], "timeout_seconds": 3600},
            # UNKNOWN: independent acceptance (VM/QEMU QA via test-qemu.sh on a QA host,
            # physical hardware) is not a retained-plan action defined anywhere.
            {"id": "draft-unknown-accept", "stage": "accept", "tool": "echo",
             "argv": ["sdk/bin/echo", unknown],
             "requires": ["draft-build-iso", "draft-master-release-verify",
                          "draft-docs-tests", "draft-ci-tests",
                          "draft-ci-isolated-tests"],
             "inventory": ["UNKNOWN-independent-acceptance"],
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
