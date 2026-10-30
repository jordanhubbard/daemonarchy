#!/usr/bin/env python3
"""Build, sign, verify and stage installer extension feeds.

  extension-bundle.py build  SRC... --out DIR --feed TAG --arch ARCH
      One compressed bundle per extension directory SRC (each with a sealed manifest.json) and an
      unsigned compressed index, in DIR.
  extension-bundle.py sign   DIR --key PRIVATE_KEY
      A detached signature over the index and over every bundle (the key whose public half the image
      pins: its package repository key). Run again with the release key to re-sign a staged feed; the
      content and hashes do not change, only the .sig files.
  extension-bundle.py verify DIR --pubkey PUBLIC_KEY [--feed TAG]
      Everything the installer checks: index signature, schema and feed name, each bundle's size, hash
      and signature, bounded decompression, safe extraction and manifest/entry agreement.
  extension-bundle.py stage  SRC... --out DIR --feed TAG --arch ARCH --key KEY --pubkey PUB
      build + sign + verify, then print the assets with compressed and uncompressed sizes and SHA-256.
  extension-bundle.py table  DIR
      Print that table for an existing feed directory.

Every file in a feed is compressed (xz) or a signature; nothing is published uncompressed. The feed tag
is extensions-<os>-<arch>-X.Y.Z, for example extensions-16-amd64-1.4.1: a versioned release, never the
latest release and never an existing release's tag. This script never uploads anything.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "overlay/usr/local/lib/daemonarchy-visual"))
from daemonarchy_visual import bundle  # noqa: E402


def build(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    entries = [bundle.build_bundle(src, out) for src in args.src]
    (out / bundle.INDEX_NAME).write_bytes(bundle.compress(bundle.build_index(entries, args.feed, args.arch, args.generated)))
    return 0


def sign(args):
    directory = Path(args.dir)
    index = bundle.parse_index((directory / bundle.INDEX_NAME).read_bytes())
    for name in [bundle.INDEX_NAME] + [e["bundle"]["file"] for e in index["extensions"]]:
        bundle.sign_file(str(directory / name), args.key)
    return 0


def verify(args):
    index, rows = bundle.verify_feed(args.dir, args.pubkey, args.feed)
    print(f"verified {len(index['extensions'])} extensions in feed {index['feed']}")
    return 0


def table(directory):
    directory = Path(directory)
    index = bundle.parse_index((directory / bundle.INDEX_NAME).read_bytes())
    rows = [(bundle.INDEX_NAME, (directory / bundle.INDEX_NAME).stat().st_size, None, bundle.sha256_file(directory / bundle.INDEX_NAME))]
    for entry in index["extensions"]:
        info = entry["bundle"]
        rows.append((info["file"], info["bytes"], info["raw_bytes"], info["sha256"]))
    for name, size, raw, digest in list(rows):
        sig = directory / (name + ".sig")
        if sig.exists():
            rows.append((name + ".sig", sig.stat().st_size, None, bundle.sha256_file(sig)))
    print(f"feed {index['feed']}  arch {index['arch']}  generated {index['generated']}")
    print(f"{'asset':44} {'bytes':>9} {'uncompressed':>13}  sha256")
    for name, size, raw, digest in rows:
        print(f"{name:44} {size:>9} {raw if raw else '-':>13}  {digest}")
    packed = sum(r[1] for r in rows if r[0].endswith(".tar.xz"))
    raws = sum(r[2] for r in rows if r[2])
    print(f"bundles: {packed} bytes compressed, {raws} bytes uncompressed ({packed / raws:.0%} of the raw size)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "stage"):
        p = sub.add_parser(name)
        p.add_argument("src", nargs="+")
        p.add_argument("--out", required=True)
        p.add_argument("--feed", required=True)
        p.add_argument("--arch", required=True)
        p.add_argument("--generated")
        if name == "stage":
            p.add_argument("--key", required=True)
            p.add_argument("--pubkey", required=True)
    p = sub.add_parser("sign")
    p.add_argument("dir")
    p.add_argument("--key", required=True)
    p = sub.add_parser("verify")
    p.add_argument("dir")
    p.add_argument("--pubkey", required=True)
    p.add_argument("--feed")
    p = sub.add_parser("table")
    p.add_argument("dir")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            return build(args)
        if args.command == "sign":
            return sign(args)
        if args.command == "verify":
            return verify(args)
        if args.command == "table":
            return table(args.dir)
        build(args)
        args.dir = args.out
        sign(args)
        args.feed = args.feed
        verify(args)
        return table(args.out)
    except bundle.BundleError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
