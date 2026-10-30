#!/usr/bin/env python3
"""Measure the installer's package closure and plan a self-hosted feed (PKG-002).

  package-mirror-plan.py --root daemonarchy --root chromium \
      --catalogue Daemonarchy=feed/packagesite.pkg \
      --catalogue FreeBSD=https://pkg.freebsd.org/FreeBSD:16:amd64/latest/packagesite.pkg

Catalogues are listed in priority order; a package is taken from the first one
that carries it, which is how pkg resolves them with the installer's repository
priorities. The plan reports the dependency closure of the roots, how much of
it each source supplies, roots the catalogues cannot satisfy (the aarch64 gap),
the licences involved, and a first-fit split of the packages the self-hosted
feed would need to carry into GitHub release shards. It reads catalogues only;
nothing is downloaded beyond them and nothing is published.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

# GitHub allows 1000 assets and 2 GiB per asset on a release; leave headroom
# for the repository metadata files that travel with each shard.
MAX_ASSETS = 900
MAX_SHARD_BYTES = 40 * 2**30


def load_catalogue(location, cache):
    path = Path(location)
    if location.startswith(("http://", "https://")):
        path = cache / (str(abs(hash(location))) + ".pkg")
        with urllib.request.urlopen(location, timeout=120) as reply:
            path.write_bytes(reply.read())
    text = subprocess.run(["tar", "-xOf", str(path), "packagesite.yaml"],
                          check=True, capture_output=True, text=True).stdout
    return {entry["name"]: entry for entry in map(json.loads, filter(None, text.splitlines()))}


def closure(roots, sources):
    """Return ({name: (source, entry)}, [roots and dependencies nobody supplies])."""
    chosen, missing, queue = {}, [], list(roots)
    while queue:
        name = queue.pop()
        if name in chosen or name in missing:
            continue
        for source, catalogue in sources:
            if name in catalogue:
                chosen[name] = (source, catalogue[name])
                queue.extend(catalogue[name].get("deps", {}))
                break
        else:
            missing.append(name)
    return chosen, sorted(missing)


def shards(entries):
    """First-fit-decreasing split under the asset-count and byte limits."""
    bins = []
    for entry in sorted(entries, key=lambda e: -e["pkgsize"]):
        for shard in bins:
            if shard["assets"] < MAX_ASSETS and shard["bytes"] + entry["pkgsize"] <= MAX_SHARD_BYTES:
                break
        else:
            shard = {"assets": 0, "bytes": 0, "packages": []}
            bins.append(shard)
        shard["assets"] += 1
        shard["bytes"] += entry["pkgsize"]
        shard["packages"].append(entry["name"])
    return bins


def plan(roots, catalogues):
    sources = list(catalogues.items())
    chosen, missing = closure(roots, sources)
    by_source = {}
    for source, entry in chosen.values():
        row = by_source.setdefault(source, {"packages": 0, "archive_bytes": 0, "installed_bytes": 0})
        row["packages"] += 1
        row["archive_bytes"] += entry["pkgsize"]
        row["installed_bytes"] += entry.get("flatsize", 0)
    licences = Counter(lic for _, entry in chosen.values() for lic in entry.get("licenses", ["unknown"]))
    # A shard set is only needed for what the self-hosted feed would newly carry.
    hosted = [entry for source, entry in chosen.values() if source != next(iter(catalogues), None)]
    return {
        "roots": sorted(roots),
        "closure_packages": len(chosen),
        "closure_archive_bytes": sum(row["archive_bytes"] for row in by_source.values()),
        "closure_installed_bytes": sum(row["installed_bytes"] for row in by_source.values()),
        "by_source": by_source,
        "unsatisfied": missing,
        "licences": dict(sorted(licences.items(), key=lambda kv: -kv[1])),
        "shards": [{"assets": s["assets"], "bytes": s["bytes"]} for s in shards(hosted)],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", action="append", required=True)
    parser.add_argument("--catalogue", action="append", required=True, metavar="NAME=PATH_OR_URL")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-unsatisfied", action="store_true",
                        help="exit 1 if any root or dependency has no catalogue (upstream drift)")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        catalogues = {}
        for item in args.catalogue:
            name, _, location = item.partition("=")
            catalogues[name] = load_catalogue(location, Path(tmp))
    result = plan(args.root, catalogues)
    status = 1 if args.fail_on_unsatisfied and result["unsatisfied"] else 0
    if args.json:
        print(json.dumps(result, indent=2))
        return status
    gib = 2**30
    print(f"closure: {result['closure_packages']} packages, "
          f"{result['closure_archive_bytes'] / gib:.2f} GiB archives, "
          f"{result['closure_installed_bytes'] / gib:.2f} GiB installed")
    for name, row in result["by_source"].items():
        print(f"  {name}: {row['packages']} packages, {row['archive_bytes'] / gib:.2f} GiB")
    print(f"unsatisfied: {', '.join(result['unsatisfied']) or 'none'}")
    print(f"shards for the self-hosted feed: {len(result['shards'])} "
          f"({', '.join(str(s['assets']) for s in result['shards'])} assets)")
    return status


if __name__ == "__main__":
    sys.exit(main())
