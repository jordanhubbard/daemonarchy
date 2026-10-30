#!/usr/bin/env python3
"""Stage a built application feed for the safe uploader (package-feed-upload.py).

  package-feed-manifest.py --feed DIR --tag TAG --out OUT [--title TEXT]

DIR is what `pkg-repo.sh build` wrote: the packages plus meta, meta.conf, packagesite.pkg
and data.pkg. This hard-links them (or copies across filesystems) into OUT/TAG/ and writes
OUT/TAG.manifest.json (name, size and SHA-256 of every asset). package-feed-upload.py then
creates the release (never the latest), uploads packages before the catalogue files, never
replaces an existing asset, and its `verify` re-downloads everything against the manifest.
Publishes nothing and never touches a signing key.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

CATALOGUE = ("meta", "meta.conf", "packagesite.pkg", "data.pkg")
SCHEMA = "daemonarchy/package-feed-shard@1"
ZSTD = b"\x28\xb5\x2f\xfd"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage(feed, tag, out, title=None):
    if not re.fullmatch(r"packages-16-(amd64|aarch64)-[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9._-]*", tag):
        sys.exit(f"{tag!r} is not a versioned package feed tag (packages-16-ARCH-X.Y.Z...)")
    feed, out = Path(feed), Path(out)
    names = sorted(p.name for p in feed.iterdir() if p.is_file())
    missing = [n for n in CATALOGUE if n not in names]
    if missing:
        sys.exit(f"{feed} lacks {', '.join(missing)}: run pkg-repo.sh build first")
    packages = [n for n in names if n.endswith(".pkg") and n not in CATALOGUE]
    if not packages:
        sys.exit(f"{feed} holds no packages")
    for name in packages + ["packagesite.pkg", "data.pkg"]:
        with open(feed / name, "rb") as stream:
            if stream.read(4) != ZSTD:
                sys.exit(f"{name} is not zstd-compressed: every published asset must be compressed")
    for name in names:
        if (feed / name).stat().st_size >= 2 << 30:
            sys.exit(f"{name} is at or over GitHub's 2 GiB asset limit")
    if len(names) > 1000:
        sys.exit("more than 1000 assets: split the feed across releases")
    target = out / tag
    if target.exists() or (out / (tag + ".manifest.json")).exists():
        sys.exit(f"{target} already staged; remove it deliberately to restage")
    target.mkdir(parents=True)
    assets = []
    for name in names:
        try:
            os.link(feed / name, target / name)
        except OSError:
            shutil.copy2(feed / name, target / name)
        assets.append({"name": name, "bytes": (feed / name).stat().st_size, "sha256": sha256(feed / name)})
    manifest = {"schema": SCHEMA, "tag": tag, "packages": [n[:-4] for n in packages], "catalogue": True,
                "upstream_sums": {}, "assets": assets}
    if title:
        manifest["title"] = title
    (out / (tag + ".manifest.json")).write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{target}: {len(assets)} assets, {sum(a['bytes'] for a in assets)} bytes")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feed", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--title")
    args = parser.parse_args(argv)
    stage(args.feed, args.tag, args.out, args.title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
