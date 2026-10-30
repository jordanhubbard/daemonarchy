#!/usr/bin/env python3
"""Read, write and check the one Daemonarchy release version.

  version.py show               print the version (what the installer displays)
  version.py set X.Y.Z          write VERSION and literate.project.json
  version.py check              fail unless every place that records it agrees
  version.py show --json        {"version": "X.Y.Z"}

VERSION at the repository root is the single source. build-iso.sh reads it for
the installer's version line and the default image name; literate.project.json
carries a copy that `set` keeps in step. Which release is published is a
different fact, kept in release/current.json by release-current.py.
"""

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "VERSION"
PROJECT = ROOT / "literate.project.json"
SEMVER = re.compile(r"\d+\.\d+\.\d+\Z")


def read():
    text = VERSION.read_text().strip()
    if not SEMVER.match(text):
        sys.exit(f"{VERSION}: {text!r} is not X.Y.Z")
    return text


def project_version():
    return json.loads(PROJECT.read_text())["version"]


def write_project(version):
    # Edit in place so the file's layout and key order stay as they are.
    text = PROJECT.read_text()
    new, count = re.subn(r'("version"\s*:\s*")[^"]*(")', rf"\g<1>{version}\g<2>", text, count=1)
    if count != 1:
        sys.exit(f"{PROJECT}: no version field")
    PROJECT.write_text(new)


def check():
    version = read()
    problems = []
    if project_version() != version:
        problems.append(f"literate.project.json says {project_version()}, VERSION says {version}")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show")
    show.add_argument("--json", action="store_true")
    setter = sub.add_parser("set")
    setter.add_argument("version")
    sub.add_parser("check")
    args = parser.parse_args(argv)

    if args.command == "show":
        print(json.dumps({"version": read()}) if args.json else read())
    elif args.command == "set":
        if not SEMVER.match(args.version):
            sys.exit(f"{args.version!r} is not X.Y.Z")
        VERSION.write_text(args.version + "\n")
        write_project(args.version)
        print(args.version)
    else:
        problems = check()
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1
        print(f"version {read()}: consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
