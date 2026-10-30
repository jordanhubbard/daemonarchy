#!/usr/bin/env python3
"""Resolve an Omarchy release's package lists to a full dependency closure.

  omarchy-package-closure.py --dbs DIR --checkout OMARCHY_GIT --ref v4.0.6 \
      [--manifest fresh-install.json]

DIR holds the pacman sync databases core.db, extra.db and omarchy.db (from
Omarchy's stable mirrors). The roots are install/omarchy-base.packages at REF
plus the system packages the ISO installs outside it. With --manifest, the
explicit packages of a measured fresh install are resolved the same way, as a
calibration against what was really installed. Reads only; prints package
counts and archive and installed sizes. Used for docs/install-weight-vs-omarchy.md.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tarfile

SYSTEM_ROOTS = ["base", "linux-firmware", "linux-omarchy", "limine", "limine-snapper-sync",
                "limine-mkinitcpio-hook", "btrfs-progs"]


def load(db):
    packages = {}
    with tarfile.open(db) as archive:
        for member in archive.getmembers():
            if not member.name.endswith("/desc"):
                continue
            section, desc = None, {}
            for line in archive.extractfile(member).read().decode().splitlines():
                if line.startswith("%") and line.endswith("%"):
                    section = line.strip("%")
                    desc[section] = []
                elif line and section:
                    desc[section].append(line)
            packages[desc["NAME"][0]] = dict(
                deps=desc.get("DEPENDS", []), provides=desc.get("PROVIDES", []),
                csize=int(desc.get("CSIZE", ["0"])[0]), isize=int(desc.get("ISIZE", ["0"])[0]))
    return packages


def repositories(directory):
    repos = {}
    for name in ("core.db", "extra.db", "omarchy.db"):
        for package, row in load(Path(directory) / name).items():
            if package not in repos or name == "omarchy.db":
                repos[package] = row
    providers = {}
    for package, row in repos.items():
        providers.setdefault(package, []).insert(0, package)
        for item in row["provides"]:
            providers.setdefault(item, []).append(package)
            providers.setdefault(re.split(r"[<>=]", item)[0], []).append(package)
    return repos, providers


def closure(roots, repos, providers):
    seen, missing, queue = set(), set(), list(roots)
    while queue:
        name = queue.pop()
        if name in seen or name in missing:
            continue
        if name not in repos:
            missing.add(name)
            continue
        seen.add(name)
        for dep in repos[name]["deps"]:
            for key in (dep, re.split(r"[<>=]", dep)[0]):
                if key in repos:
                    queue.append(key)
                    break
                if key in providers:
                    queue.append(providers[key][0])
                    break
    return seen, sorted(missing)


def package_list(checkout, ref):
    text = subprocess.run(["git", "-C", checkout, "show", f"{ref}:install/omarchy-base.packages"],
                          check=True, capture_output=True, text=True).stdout
    return [line.split("#")[0].strip() for line in text.splitlines() if line.split("#")[0].strip()]


def report(label, roots, repos, providers):
    packages, missing = closure(roots, repos, providers)
    gib = 2**30
    print(f"{label}: {len(set(roots))} roots -> {len(packages)} packages, "
          f"{sum(repos[p]['csize'] for p in packages) / gib:.2f} GiB archives, "
          f"{sum(repos[p]['isize'] for p in packages) / gib:.2f} GiB installed; "
          f"not in the databases: {missing or 'none'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dbs", required=True)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()
    repos, providers = repositories(args.dbs)
    if args.manifest:
        explicit = json.loads(Path(args.manifest).read_text())["packages"]["explicit"]
        report("measured install's explicit packages", explicit, repos, providers)
    base = package_list(args.checkout, args.ref)
    report(f"{args.ref} base list", base, repos, providers)
    report(f"{args.ref} base list + system packages", base + SYSTEM_ROOTS, repos, providers)


if __name__ == "__main__":
    main()
