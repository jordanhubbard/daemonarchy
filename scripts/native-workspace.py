#!/usr/bin/env python3
"""Deploy independent pinned native checkouts; do not build or award acceptance."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse


SCHEMA = "daemonarchy/native-workspace-selection@1"
RECORD_SCHEMA = "daemonarchy/native-workspace@1"
OUTPUTS = ("obj", "stage", "packages", "cache", "evidence")
REPOSITORY = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def identity(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def document(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result

    with Path(path).open("rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError("workspace selection exceeds metadata limit")
    return json.loads(data, object_pairs_hook=unique)


def repository_url(value):
    if not isinstance(value, str):
        raise ValueError("repository must be an explicit URL")
    parsed = urlparse(value)
    if (parsed.scheme not in {"https", "file"} or not parsed.path
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or any(ord(c) < 32 for c in value)):
        raise ValueError("repository URL must be HTTPS or local file, without credentials")
    if parsed.scheme == "https" and not parsed.hostname:
        raise ValueError("HTTPS repository needs a host")
    if parsed.scheme == "file" and (parsed.netloc or not Path(parsed.path).is_absolute()):
        raise ValueError("local repository needs an absolute file URL")
    return value


def revision(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("each checkout needs an exact 40-character commit")
    return value


def selection(path, control_revision):
    data = document(path)
    if (not isinstance(data, dict)
            or set(data) != {"schema", "control_repository", "trees"}
            or data["schema"] != SCHEMA or not isinstance(data["trees"], dict)
            or set(data["trees"]) != {"src", "ports"}):
        raise ValueError("invalid source/ports workspace selection")
    repos = {"control": {"repository": repository_url(data["control_repository"]),
                         "revision": revision(control_revision), "upstream": None}}
    for name in ("src", "ports"):
        tree = data["trees"][name]
        if not isinstance(tree, dict) or set(tree) != {"repository", "revision", "upstream"}:
            raise ValueError("invalid selected tree")
        repos[name] = {"repository": repository_url(tree["repository"]),
                       "revision": revision(tree["revision"]),
                       "upstream": repository_url(tree["upstream"])}
    return {"schema": RECORD_SCHEMA, "repositories": repos, "outputs": list(OUTPUTS),
            "execution_qualified": False, "lifecycle_receipt": False}


def root_path(value):
    root = Path(value)
    if not root.is_absolute() or root != root.resolve():
        raise ValueError("workspace root must be absolute and have no redirected ancestors")
    for protected in (Path("/usr/src"), Path("/usr/ports")):
        if root == protected or root in protected.parents or protected in root.parents:
            raise ValueError("workspace must be separate from legacy source/ports roots")
    return root


def git(path, *argv):
    environment = dict({key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
                       GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
    command = ["git", "-C", str(path), *argv]
    completed = subprocess.run(command, env=environment, capture_output=True,
                               text=True, timeout=600)
    if completed.returncode:
        raise ValueError(f"git {argv[0]} failed: {completed.stderr.strip()[-2000:]}")
    return completed.stdout.strip()


def inspect(root):
    root = root_path(root)
    if (root / ".incomplete").exists():
        raise ValueError("incomplete deployment retained; inspect evidence before choosing a fresh root")
    record_path = root / "workspace.json"
    if record_path.is_symlink():
        raise ValueError("workspace record is redirected")
    record = document(record_path)
    if (not isinstance(record, dict) or set(record) != {"selection", "identity"}
            or record["identity"] != identity(record["selection"])):
        raise ValueError("workspace selection identity mismatch")
    selected = record["selection"]
    if (not isinstance(selected, dict)
            or set(selected) != {"schema", "repositories", "outputs", "execution_qualified", "lifecycle_receipt"}
            or selected.get("schema") != RECORD_SCHEMA
            or not isinstance(selected.get("repositories"), dict)
            or set(selected.get("repositories", {})) != {"control", "src", "ports"}
            or selected.get("outputs") != list(OUTPUTS)
            or selected.get("execution_qualified") is not False
            or selected.get("lifecycle_receipt") is not False):
        raise ValueError("invalid deployed workspace")
    for name in ("control", "src", "ports"):
        path = root / name
        entry = selected["repositories"][name]
        if not isinstance(entry, dict) or set(entry) != {"repository", "revision", "upstream"}:
            raise ValueError("invalid deployed repository selection")
        metadata = path / ".git"
        if (path.is_symlink() or path.resolve() != path or metadata.is_symlink()
                or not metadata.is_dir()):
            raise ValueError(f"{name} must be an independent checkout")
        if git(path, "rev-parse", "HEAD") != revision(entry["revision"]):
            raise ValueError(f"{name} revision drift")
        if git(path, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError(f"{name} checkout has local changes")
        if git(path, "remote", "get-url", "origin") != repository_url(entry["repository"]):
            raise ValueError(f"{name} origin drift")
        if entry["upstream"] and git(path, "remote", "get-url", "upstream") != repository_url(entry["upstream"]):
            raise ValueError(f"{name} upstream drift")
        common = Path(git(path, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = path / common
        alternates = metadata / "objects/info/alternates"
        if common.resolve() != metadata.resolve() or alternates.exists() or alternates.is_symlink():
            raise ValueError(f"{name} depends on an external Git object store")
    for name in OUTPUTS:
        path = root / name
        if path.is_symlink() or path.resolve() != path or not path.is_dir():
            raise ValueError(f"{name} output root is missing or redirected")
    return {"schema": "daemonarchy/native-workspace-inspection@1", "ok": True,
            "selection_identity": record["identity"], "selection": selected}


def deploy(root, selected):
    root = root_path(root)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("deployment requires a new or empty workspace root; existing state is preserved")
    root.mkdir(exist_ok=True)
    (root / ".incomplete").write_bytes(canonical(selected) + b"\n")
    for name in OUTPUTS:
        (root / name).mkdir()
    template = root / "evidence/empty-git-template"
    template.mkdir()
    for name, entry in selected["repositories"].items():
        path = root / name
        path.mkdir()
        git(path, "init", "--quiet", "--template=" + str(template))
        git(path, "remote", "add", "origin", entry["repository"])
        if entry["upstream"]:
            git(path, "remote", "add", "upstream", entry["upstream"])
        git(path, "fetch", "--depth=1", "--no-tags", "origin", entry["revision"])
        git(path, "checkout", "--quiet", "--detach", entry["revision"])
        with (root / "evidence/deployment.jsonl").open("ab") as stream:
            stream.write(canonical({"checkout": name, "revision": git(path, "rev-parse", "HEAD")}) + b"\n")
    record = {"selection": selected, "identity": identity(selected)}
    with (root / "workspace.json").open("xb") as stream:
        stream.write(canonical(record) + b"\n")
    (root / ".incomplete").unlink()
    return inspect(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "deploy", "inspect"), nargs="?", default="plan")
    parser.add_argument("--root", default="/usr/daemonarchy")
    parser.add_argument("--selection", type=Path, default=REPOSITORY / "native/workspace.json")
    parser.add_argument("--control-revision")
    args = parser.parse_args()
    try:
        root = root_path(args.root)
        if args.operation == "inspect":
            result = inspect(root)
        else:
            pin = args.control_revision or git(REPOSITORY, "rev-parse", "HEAD")
            selected = selection(args.selection, pin)
            result = deploy(root, selected) if args.operation == "deploy" else {
                "schema": "daemonarchy/native-workspace-plan@1", "selection": selected,
                "selection_identity": identity(selected), "root": str(root), "writes": False}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
