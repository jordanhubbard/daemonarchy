#!/usr/bin/env python3
"""Fill a release's records from the verified assets (docs/mastering-1.5.0.md).

The draft release pull request, made by scripts/prepare-release.py, carries
placeholders: `@@TOKEN@@` in the documents and `TODO` in release/current.json and
verification/release-VERSION.json. Once the final ISOs and the feeds exist, this
script replaces every one of them from a small set of values, copies the published
checkout catalogue over the overlay, and refuses to finish while a placeholder is
left that the values should have filled.

  scripts/fill-release.py --version 1.5.0 --assets DIR \\
      --installer-commit SHA40 --ports-commit SHA40 \\
      --packages-amd64 TAG --packages-aarch64 TAG \\
      --checkouts-amd64 TAG --checkouts-aarch64 TAG \\
      --aarch64-final-qemu "TEXT" --physical-status "TEXT" \\
      [--published-at 2026-11-07T00:00:00Z] [--checkouts-json FILE] [--dry-run]

DIR holds exactly the eight release assets, as they will be (or were) uploaded. The
release record's `closure_feed_records` field lists the closure shards the image
carries; each is a file in verification/closure-feeds/ (written by
scripts/package-feed-stage.py). It writes files only; it never publishes, tags or
uploads anything. To redo a run, `git checkout -- .` the files it lists first (the
tokens are consumed).

DAEMONARCHY_RELEASE_ROOT points the script at another tree (the test uses it).
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(os.environ.get("DAEMONARCHY_RELEASE_ROOT") or Path(__file__).resolve().parents[1])
REPO = "jordanhubbard/daemonarchy"
VERSION_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
CATALOGUE = ROOT / "overlay/usr/local/share/daemonarchy-installer/checkouts.json"
CURRENT = ROOT / "release/current.json"
TOKEN_FILES = ["README.md", "HACKING.md", "PROJECT.md", "CHANGELOG.md", "docs/aarch64.md"]


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message):
    sys.exit(f"fill-release: {message}")


def asset_names(version):
    return [f"daemonarchy-{version}-{arch}.iso.xz{suffix}"
            for arch in ("amd64", "aarch64") for suffix in ("", ".sha256")] + [
        f"daemonarchy-hwtrace-{version}-amd64.img.xz{suffix}" for suffix in ("", ".sha256")] + [
        f"daemonarchy-{version}-boot.txz", f"daemonarchy-{version}-boot.txz.sig",
        f"daemonarchy-{version}.pem", f"daemonarchy-{version}.der"]


def feed_patterns(version):
    escaped = re.escape(version)
    return {
        "packages_amd64": re.compile(rf"packages-16-amd64-{escaped}(-r\d+)?\Z"),
        "packages_aarch64": re.compile(rf"packages-16-aarch64-{escaped}(-r\d+)?\Z"),
        "checkouts_amd64": re.compile(rf"checkouts-16-amd64-{escaped}(-r\d+)?\Z"),
        "checkouts_aarch64": re.compile(rf"checkouts-16-aarch64-{escaped}(-r\d+)?\Z"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True, help="the release version, X.Y.Z")
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--installer-commit", required=True)
    parser.add_argument("--ports-commit", required=True)
    for name in feed_patterns("0.0.0"):
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--aarch64-final-qemu", required=True,
                        help="one truthful sentence on whether the release arm64 image itself was run in QEMU")
    parser.add_argument("--physical-status", required=True,
                        help="one truthful sentence on physical MSI and MacBook runs of the final amd64 image")
    parser.add_argument("--set", action="append", default=[], metavar="TOKEN=TEXT",
                        help="a release-specific token of the notes, for example GUI001_EVIDENCE=... (repeatable)")
    parser.add_argument("--published-at", help="ISO time; omit before publication (then run release-current.py update)")
    parser.add_argument("--checkouts-json", type=Path,
                        help="the downloaded checkouts.json (default: gh release download from the amd64 checkout feed)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    version = args.version
    if not VERSION_PATTERN.fullmatch(version):
        fail("--version must be X.Y.Z")
    record_path = ROOT / f"verification/release-{version}.json"
    notes_path = f"docs/release-{version}.md"
    for flag, value in (("installer", args.installer_commit), ("ports", args.ports_commit)):
        if not COMMIT.fullmatch(value):
            fail(f"--{flag}-commit must be 40 lowercase hex characters")
    patterns = feed_patterns(version)
    feeds = {name: getattr(args, name) for name in patterns}
    for name, pattern in patterns.items():
        if not pattern.fullmatch(feeds[name]):
            fail(f"--{name.replace('_', '-')} {feeds[name]!r} is not a {version} tag of that kind")
    names = asset_names(version)
    if not args.assets.is_dir() or {p.name for p in args.assets.iterdir()} != set(names):
        fail("--assets must be a directory holding exactly: " + ", ".join(names))
    assets = {name: [(args.assets / name).stat().st_size, "sha256:" + digest(args.assets / name)] for name in names}
    for iso in [f"daemonarchy-{version}-{arch}.iso.xz" for arch in ("amd64", "aarch64")] + [
            f"daemonarchy-hwtrace-{version}-amd64.img.xz"]:
        expected = f"{assets[iso][1][7:]}  {iso}\n".encode()
        if (args.assets / (iso + ".sha256")).read_bytes() != expected:
            fail(f"{iso}.sha256 does not cover the {iso} next to it")

    record = json.loads(record_path.read_text())
    if record.get("version") != version or record.get("tag") != f"daemonarchy-{version}":
        fail(f"{record_path.relative_to(ROOT)} is not the {version} record")
    source_commit = record.get("source_commit")
    if not isinstance(source_commit, str) or not COMMIT.fullmatch(source_commit):
        fail(f"{record_path.relative_to(ROOT)} has no valid source_commit: set it when preparing the release")
    shards = record.pop("closure_feed_records", None)
    if not isinstance(shards, list) or not shards or not all(isinstance(tag, str) for tag in shards):
        fail("the record's closure_feed_records must list the closure shard tags the image carries")
    closure = []
    for tag in shards:
        path = ROOT / "verification/closure-feeds" / f"{tag}.json"
        if not path.is_file():
            fail(f"no closure feed record for {tag}: stage it with scripts/package-feed-stage.py first")
        closure.extend(json.loads(path.read_text()))

    # The overlay catalogue is the published catalogue, byte for byte.
    base = f"https://github.com/{REPO}/releases/download/{feeds['checkouts_amd64']}"
    catalogue = args.checkouts_json
    downloaded = False
    if catalogue is None:
        catalogue = ROOT / ".fill-checkouts.json"
        downloaded = True
        subprocess.run(["gh", "release", "download", feeds["checkouts_amd64"], "-R", REPO,
                        "-p", "checkouts.json", "-O", str(catalogue), "--clobber"], check=True)
    data = catalogue.read_bytes()
    parsed = json.loads(data)
    if parsed.get("repository_url") != base:
        fail(f"catalogue repository_url {parsed.get('repository_url')!r} is not {base!r}")
    if parsed["trees"]["src"]["revision"] != source_commit:
        fail("catalogue source revision is not " + source_commit)
    if parsed["trees"]["ports"]["revision"] != args.ports_commit:
        fail(f"catalogue ports revision {parsed['trees']['ports']['revision']} is not --ports-commit")

    published = args.published_at
    date = None
    if published:
        date = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
        date = f"{date:%B} {date.day}, {date.year}"
    values = {
        "AMD64_ISO_BYTES": f"{assets[f'daemonarchy-{version}-amd64.iso.xz'][0]:,}",
        "AMD64_ISO_SHA256": assets[f"daemonarchy-{version}-amd64.iso.xz"][1][7:],
        "AARCH64_ISO_BYTES": f"{assets[f'daemonarchy-{version}-aarch64.iso.xz'][0]:,}",
        "AARCH64_ISO_SHA256": assets[f"daemonarchy-{version}-aarch64.iso.xz"][1][7:],
        "HWTRACE_BYTES": f"{assets[f'daemonarchy-hwtrace-{version}-amd64.img.xz'][0]:,}",
        "HWTRACE_SHA256": assets[f"daemonarchy-hwtrace-{version}-amd64.img.xz"][1][7:],
        "PACKAGES_AMD64_FEED": feeds["packages_amd64"],
        "PACKAGES_AARCH64_FEED": feeds["packages_aarch64"],
        "CHECKOUTS_AMD64_FEED": feeds["checkouts_amd64"],
        "CHECKOUTS_AARCH64_FEED": feeds["checkouts_aarch64"],
        "PORTS_COMMIT": args.ports_commit,
        "PORTS_SHORT": args.ports_commit[:8],
        "INSTALLER_COMMIT": args.installer_commit,
        "INSTALLER_SHORT": args.installer_commit[:8],
        "AARCH64_FINAL_QEMU_STATUS": args.aarch64_final_qemu,
        "PHYSICAL_STATUS": args.physical_status,
    }
    if date:
        values["PUBLISHED_DATE"] = date
    for item in args.set:
        token, separator, text = item.partition("=")
        if not separator or not re.fullmatch(r"[A-Z0-9_]+", token) or token in values:
            fail(f"--set expects a new TOKEN=TEXT with an upper-case token, got {item!r}")
        values[token] = text

    current = json.loads(CURRENT.read_text())
    if current.get("version") != version:
        fail(f"release/current.json names {current.get('version')}, not {version}: run scripts/prepare-release.py first")
    current["assets"] = assets
    current["application_feed"] = feeds["packages_amd64"]
    current["checkout_feed"] = feeds["checkouts_amd64"]
    if published:
        current["published_at"] = published
    record.update(
        installer_commit=args.installer_commit, ports_commit=args.ports_commit,
        application_feed=feeds["packages_amd64"], checkout_feed=feeds["checkouts_amd64"],
        aarch64_application_feed=feeds["packages_aarch64"], aarch64_checkout_feed=feeds["checkouts_aarch64"],
        evidence_status="published release record", assets=assets, closure_feeds=closure)

    texts = {}
    for name in [notes_path] + TOKEN_FILES:
        text = (ROOT / name).read_text()
        for token, value in values.items():
            text = text.replace(f"@@{token}@@", value)
        texts[name] = text
    if args.dry_run:
        print("values:", json.dumps(values, indent=2))
        print("would write:", CURRENT, record_path, CATALOGUE, *texts, sep="\n  ")
        left = {n: sorted(set(re.findall(r"@@[A-Z0-9_]+@@", t))) for n, t in texts.items() if "@@" in t}
        print("tokens still unfilled (PUBLISHED_DATE needs --published-at):", left or "none")
        if downloaded:
            catalogue.unlink()
        return 0

    CATALOGUE.write_bytes(data)
    CURRENT.write_text(json.dumps(current, indent=2) + "\n")
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    for name, text in texts.items():
        (ROOT / name).write_text(text)
    if downloaded:
        catalogue.unlink()
    left = [n for n, t in texts.items() if "@@" in t]
    if left:
        print("still holds placeholders (give --published-at, or fill after publication):", *left, sep="\n  ")
    print("filled. Next: python3 tests/docs-release-sync.py -v; python3 scripts/verify-release-assets.py "
          f"--record {record_path.relative_to(ROOT)} --assets {args.assets} --closure-assets <staged closure dir>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
