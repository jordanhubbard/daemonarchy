#!/usr/bin/env python3
"""Release gate for the 1.4.x line, run by `litai release check` (literate.release.json).

It replaces release-check-1.3.1.py, which pins one release's source commits and evidence.
This gate pins nothing: the release record names the inputs, and the gate refuses anything
the record does not prove. It fails closed. It checks, in order:

  1. DAEMONARCHY_RELEASE_RECORD (absolute path) is a release-inputs@1 record for exactly
     VERSION, tagged daemonarchy-VERSION, selects this checkout's HEAD as installer_commit,
     and carries no `TODO` placeholder digest (scripts/prepare-release.py writes those).
  2. release/current.json names the same version, with no `TODO` placeholder.
  3. `litai verify` authority and locks pass.
  4. The stdlib documentation, version and lifecycle suites pass.
  5. scripts/verify-release-assets.py verifies the staged assets in DAEMONARCHY_RELEASE_ASSETS
     against the record (and DAEMONARCHY_CLOSURE_ASSETS when the record carries closure feeds).

Native ISO runtime, physical hardware, publication and the LitAI test receipt are separate
acceptance gates; passing this gate does not claim them.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(os.environ.get("DAEMONARCHY_RELEASE_ROOT") or Path(__file__).resolve().parents[1])
VERSION_RE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
SUITES = ("tests/docs-release-sync.py", "tests/version-sync.py", "tests/docs-lifecycle.py")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON key: " + key)
        value[key] = item
    return value


def document(path):
    require(path.is_file() and not path.is_symlink(), "missing regular file: " + str(path))
    return json.loads(path.read_text(), object_pairs_hook=unique_pairs)


def external_path(variable, directory=False):
    value = os.environ.get(variable, "")
    require(bool(value), "set " + variable + " to the reviewed " + ("stage" if directory else "record"))
    path = Path(value)
    require(path.is_absolute() and not path.is_symlink(), variable + " must be an absolute, non-symlink path")
    path = path.resolve(strict=True)
    require(path.is_dir() if directory else path.is_file(), variable + " has the wrong kind of path")
    return path


def has_placeholder(value):
    if isinstance(value, str):
        return "TODO" in value
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    return False


def run(*argv):
    subprocess.run(argv, cwd=ROOT, check=True)


def check_record(record, version, head):
    require(record.get("schema") == "daemonarchy/release-inputs@1", "not a release-inputs record")
    require(record.get("version") == version and record.get("tag") == "daemonarchy-" + version,
            "record is not for release " + version)
    require(record.get("installer_commit") == head, "record selects another product commit")
    require(not has_placeholder(record), "record still has TODO placeholders")
    current = document(ROOT / "release/current.json")
    require(current.get("version") == version, "release/current.json is not at " + version)
    require(not has_placeholder(current), "release/current.json still has TODO placeholders")


def main():
    version = (ROOT / "VERSION").read_text().strip()
    require(VERSION_RE.fullmatch(version) is not None, "VERSION is not major.minor.patch")
    record_path = external_path("DAEMONARCHY_RELEASE_RECORD")
    record = document(record_path)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    check_record(record, version, head)
    run("litai", "verify", "--gate", "authority", "--gate", "locks")
    for suite in SUITES:
        run(sys.executable, "-I", suite)
    command = [sys.executable, "scripts/verify-release-assets.py", "--record", str(record_path),
               "--assets", str(external_path("DAEMONARCHY_RELEASE_ASSETS", True))]
    if record.get("closure_feeds"):
        command += ["--closure-assets", str(external_path("DAEMONARCHY_CLOSURE_ASSETS", True))]
    run(*command)
    print(version + " release gate passed: record, authority, locks, documentation and staged assets")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        sys.exit("release gate refused: " + str(error))
