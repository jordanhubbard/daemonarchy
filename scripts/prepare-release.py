#!/usr/bin/env python3
"""Write the placeholder records of a release's draft pull request (docs/mastering-1.4.2.md).

  scripts/prepare-release.py --version 1.4.2 --source-commit SHA40 [--osversion 1600029] [--dry-run]

It writes, from release/templates/ and the current record:

  docs/release-VERSION.md            a copy of release/templates/release-VERSION.md (tokens left in)
  verification/release-VERSION.json  the release-inputs skeleton: `TODO` digests, the source
                                     commit and OSVERSION, and `closure_feed_records`, the closure
                                     shards the image will carry (every record in
                                     verification/closure-feeds/; remove or add tags for the release)
  release/current.json               the new release as current, with `TODO` digests, the old
                                     current release moved into previous_releases

Until scripts/fill-release.py fills them, tests/docs-release-sync.py is expected to fail: that
is why the pull request stays a draft. The script then prints the prose files that still need
their `@@TOKEN@@` sentences written by hand. It writes files only and refuses to overwrite a
release that already has notes or a record.

DAEMONARCHY_RELEASE_ROOT points the script at another tree (the test uses it).
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(os.environ.get("DAEMONARCHY_RELEASE_ROOT") or Path(__file__).resolve().parents[1])
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
REPO = "jordanhubbard/daemonarchy"
PROSE = {
    "README.md": "the Download section and the release section: version, date, @@AMD64_ISO_BYTES@@, @@AMD64_ISO_SHA256@@, "
                 "@@AARCH64_ISO_BYTES@@, @@AARCH64_ISO_SHA256@@, @@PUBLISHED_DATE@@",
    "HACKING.md": "the latest-release paragraph (@@PORTS_COMMIT@@) and the `gh release create` example",
    "PROJECT.md": "the current-release paragraph (@@PUBLISHED_DATE@@) and the next-release sentence",
    "CHANGELOG.md": "a new section for the release",
    "docs/aarch64.md": "the status of the release image (@@AARCH64_FINAL_QEMU_STATUS@@ where it applies)",
    "docs/roadmap/release-VERSION.md": "the plan: mark what shipped and what moved on",
}


def version_tuple(text):
    return tuple(map(int, VERSION.fullmatch(text).groups()))


def asset_names(version):
    return [f"daemonarchy-{version}-{arch}.iso.xz{suffix}"
            for arch in ("amd64", "aarch64") for suffix in ("", ".sha256")] + [
        f"daemonarchy-{version}-boot.txz", f"daemonarchy-{version}-boot.txz.sig",
        f"daemonarchy-{version}.pem", f"daemonarchy-{version}.der"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True, help="the daemonarchy-src commit of the base (40 hex)")
    parser.add_argument("--osversion", type=int, help="default: the current release's OSVERSION")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    version = args.version
    if not VERSION.fullmatch(version):
        sys.exit("prepare-release: --version must be X.Y.Z")
    if not COMMIT.fullmatch(args.source_commit):
        sys.exit("prepare-release: --source-commit must be 40 lowercase hex characters")
    current_path = ROOT / "release/current.json"
    current = json.loads(current_path.read_text())
    if version_tuple(version) <= version_tuple(current["version"]):
        sys.exit(f"prepare-release: {version} is not newer than the current release {current['version']}")
    template = ROOT / f"release/templates/release-{version}.md"
    notes = ROOT / f"docs/release-{version}.md"
    record = ROOT / f"verification/release-{version}.json"
    if not template.is_file():
        sys.exit(f"prepare-release: write {template.relative_to(ROOT)} first (the honest notes template)")
    for path in (notes, record):
        if path.exists():
            sys.exit(f"prepare-release: {path.relative_to(ROOT)} already exists")

    osversion = args.osversion or current["osversion"]
    shards = sorted(path.stem for path in (ROOT / "verification/closure-feeds").glob("packages-16-*.json"))
    skeleton = {
        "schema": "daemonarchy/release-inputs@1",
        "version": version,
        "tag": f"daemonarchy-{version}",
        "installer_commit": "TODO",
        "source_commit": args.source_commit,
        "osversion": osversion,
        "ports_commit": "TODO",
        "application_feed": "TODO",
        "checkout_feed": "TODO",
        "aarch64_application_feed": "TODO",
        "aarch64_checkout_feed": "TODO",
        "architectures": ["amd64", "aarch64"],
        "qualification": f"docs/release-{version}.md",
        "evidence_status": "draft: placeholders, not a release record",
        "assets": {name: [0, "sha256:TODO"] for name in sorted(asset_names(version))},
        "closure_feed_records": shards,
    }
    installer = next(image for image in current["images"] if image["type"] == "installer")
    size, digest = current["assets"][installer["asset"]]
    previous = [{
        "version": current["version"], "tag": current["tag"], "published_at": current["published_at"],
        "image": [installer["asset"], size, digest],
    }] + list(current.get("previous_releases", []))
    new_current = {
        "schema": current["schema"],
        "version": version,
        "tag": f"daemonarchy-{version}",
        "name": f"Daemonarchy {version}",
        "published_at": "TODO",
        "url": f"https://github.com/{REPO}/releases/tag/daemonarchy-{version}",
        "notes": f"docs/release-{version}.md",
        "osversion": osversion,
        "application_feed": "TODO",
        "checkout_feed": "TODO",
        "images": [{"type": "installer", "arch": arch, "asset": f"daemonarchy-{version}-{arch}.iso.xz",
                    "checksum_asset": f"daemonarchy-{version}-{arch}.iso.xz.sha256"} for arch in ("amd64", "aarch64")],
        "assets": {name: [0, "sha256:TODO"] for name in sorted(asset_names(version))},
        "previous_releases": previous,
    }

    print(f"{'would write' if args.dry_run else 'writing'}: {notes.relative_to(ROOT)}, "
          f"{record.relative_to(ROOT)}, release/current.json ({len(shards)} closure shard records listed)")
    if not args.dry_run:
        notes.write_text(template.read_text())
        record.write_text(json.dumps(skeleton, indent=2) + "\n")
        current_path.write_text(json.dumps(new_current, indent=2) + "\n")
    print("\nStill by hand (the tokens fill-release.py replaces):")
    for name, what in PROSE.items():
        print(f"  {name.replace('VERSION', version)}: {what}")
    print("\nThe pull request stays a draft until scripts/fill-release.py has run and "
          "tests/docs-release-sync.py passes (docs/mastering-1.4.2.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
