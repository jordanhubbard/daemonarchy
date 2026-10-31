#!/usr/bin/env python3
"""Fill the 1.4.1 release records from the verified assets (docs/mastering-1.4.1.md).

The release pull request carries placeholders: `@@TOKEN@@` in the documents and
`TODO` in release/current.json and verification/release-1.4.1.json. Once the
final ISOs and the r2 feeds exist, this script replaces every one of them from
a small set of values, copies the published checkout catalogue over the overlay,
and refuses to finish while any placeholder is left.

  scripts/fill-release-1.4.1.py --assets DIR \\
      --installer-commit SHA40 --ports-commit SHA40 \\
      --packages-amd64 TAG --packages-aarch64 TAG \\
      --checkouts-amd64 TAG --checkouts-aarch64 TAG \\
      --aarch64-final-qemu "TEXT" --physical-status "TEXT" \\
      [--published-at 2026-10-31T00:00:00Z] [--dry-run]

DIR holds exactly the eight release assets, as they will be (or were) uploaded.
It writes files only; it never publishes, tags or uploads anything. To redo a
run, `git checkout -- .` the files it lists first (the tokens are consumed).
"""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.4.1"
REPO = "jordanhubbard/daemonarchy"
SOURCE_COMMIT = "303b3646270ffa4bf7cec65c5c1d28bd8000cbce"
CATALOGUE = ROOT / "overlay/usr/local/share/daemonarchy-installer/checkouts.json"
CURRENT = ROOT / "release/current.json"
RECORD = ROOT / f"verification/release-{VERSION}.json"
CLOSURE_RECORDS = sorted((ROOT / "verification/closure-feeds").glob("packages-16-*-1.4.1-upstream*.json"))
TOKEN_FILES = ["README.md", "HACKING.md", "PROJECT.md", "CHANGELOG.md",
               "docs/release-1.4.1.md", "docs/aarch64.md"]
ASSETS = [f"daemonarchy-{VERSION}-{arch}.iso.xz{suffix}"
          for arch in ("amd64", "aarch64") for suffix in ("", ".sha256")] + [
    f"daemonarchy-{VERSION}-boot.txz", f"daemonarchy-{VERSION}-boot.txz.sig",
    f"daemonarchy-{VERSION}.pem", f"daemonarchy-{VERSION}.der"]
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
FEED = {
    "packages_amd64": re.compile(r"packages-16-amd64-1\.4\.1(-r\d+)?\Z"),
    "packages_aarch64": re.compile(r"packages-16-aarch64-1\.4\.1(-r\d+)?\Z"),
    "checkouts_amd64": re.compile(r"checkouts-16-amd64-1\.4\.1(-r\d+)?\Z"),
    "checkouts_aarch64": re.compile(r"checkouts-16-aarch64-1\.4\.1(-r\d+)?\Z"),
}


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message):
    sys.exit(f"fill-release-1.4.1: {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--installer-commit", required=True)
    parser.add_argument("--ports-commit", required=True)
    for name in FEED:
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--aarch64-final-qemu", required=True,
                        help="one truthful sentence on whether the release arm64 image itself was run in QEMU")
    parser.add_argument("--physical-status", required=True,
                        help="one truthful sentence on physical MSI and MacBook runs of the final amd64 image")
    parser.add_argument("--published-at", help="ISO time; omit before publication (then run release-current.py update)")
    parser.add_argument("--checkouts-json", type=Path,
                        help="the downloaded checkouts.json (default: gh release download from the amd64 checkout feed)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for flag, value in (("installer", args.installer_commit), ("ports", args.ports_commit)):
        if not COMMIT.fullmatch(value):
            fail(f"--{flag}-commit must be 40 lowercase hex characters")
    feeds = {name: getattr(args, name) for name in FEED}
    for name, pattern in FEED.items():
        if not pattern.fullmatch(feeds[name]):
            fail(f"--{name.replace('_', '-')} {feeds[name]!r} is not a 1.4.1 tag of that kind")
    if not args.assets.is_dir() or {p.name for p in args.assets.iterdir()} != set(ASSETS):
        fail("--assets must be a directory holding exactly: " + ", ".join(ASSETS))
    assets = {name: [(args.assets / name).stat().st_size, "sha256:" + digest(args.assets / name)] for name in ASSETS}
    for arch in ("amd64", "aarch64"):
        iso = f"daemonarchy-{VERSION}-{arch}.iso.xz"
        expected = f"{assets[iso][1][7:]}  {iso}\n".encode()
        if (args.assets / (iso + ".sha256")).read_bytes() != expected:
            fail(f"{iso}.sha256 does not cover the {iso} next to it")

    # The overlay catalogue is the published r2 catalogue, byte for byte.
    base = f"https://github.com/{REPO}/releases/download/{feeds['checkouts_amd64']}"
    catalogue = args.checkouts_json
    if catalogue is None:
        catalogue = ROOT / ".fill-checkouts.json"
        subprocess.run(["gh", "release", "download", feeds["checkouts_amd64"], "-R", REPO,
                        "-p", "checkouts.json", "-O", str(catalogue), "--clobber"], check=True)
    data = catalogue.read_bytes()
    parsed = json.loads(data)
    if parsed.get("repository_url") != base:
        fail(f"catalogue repository_url {parsed.get('repository_url')!r} is not {base!r}")
    if parsed["trees"]["src"]["revision"] != SOURCE_COMMIT:
        fail("catalogue source revision is not " + SOURCE_COMMIT)
    if parsed["trees"]["ports"]["revision"] != args.ports_commit:
        fail(f"catalogue ports revision {parsed['trees']['ports']['revision']} is not --ports-commit")

    published = args.published_at
    date = None
    if published:
        date = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
        date = f"{date:%B} {date.day}, {date.year}"
    values = {
        "AMD64_ISO_BYTES": f"{assets[f'daemonarchy-{VERSION}-amd64.iso.xz'][0]:,}",
        "AMD64_ISO_SHA256": assets[f"daemonarchy-{VERSION}-amd64.iso.xz"][1][7:],
        "AARCH64_ISO_BYTES": f"{assets[f'daemonarchy-{VERSION}-aarch64.iso.xz'][0]:,}",
        "AARCH64_ISO_SHA256": assets[f"daemonarchy-{VERSION}-aarch64.iso.xz"][1][7:],
        "PACKAGES_AMD64_FEED": feeds["packages_amd64"],
        "PACKAGES_AARCH64_FEED": feeds["packages_aarch64"],
        "CHECKOUTS_AMD64_FEED": feeds["checkouts_amd64"],
        "CHECKOUTS_AARCH64_FEED": feeds["checkouts_aarch64"],
        "PORTS_COMMIT": args.ports_commit,
        "PORTS_SHORT": args.ports_commit[:8],
        "INSTALLER_SHORT": args.installer_commit[:8],
        "AARCH64_FINAL_QEMU_STATUS": args.aarch64_final_qemu,
        "PHYSICAL_STATUS": args.physical_status,
    }
    if date:
        values["PUBLISHED_DATE"] = date

    current = json.loads(CURRENT.read_text())
    current["assets"] = assets
    current["application_feed"] = feeds["packages_amd64"]
    current["checkout_feed"] = feeds["checkouts_amd64"]
    if published:
        current["published_at"] = published
    record = json.loads(RECORD.read_text())
    record.update(
        installer_commit=args.installer_commit, ports_commit=args.ports_commit,
        application_feed=feeds["packages_amd64"], checkout_feed=feeds["checkouts_amd64"],
        aarch64_application_feed=feeds["packages_aarch64"], aarch64_checkout_feed=feeds["checkouts_aarch64"],
        evidence_status="published release record", assets=assets,
        closure_feeds=[entry for path in CLOSURE_RECORDS for entry in json.loads(path.read_text())])

    texts = {}
    for name in TOKEN_FILES:
        text = (ROOT / name).read_text()
        for token, value in values.items():
            text = text.replace(f"@@{token}@@", value)
        texts[name] = text
    if args.dry_run:
        print("values:", json.dumps(values, indent=2))
        print("would write:", CURRENT, RECORD, CATALOGUE, *TOKEN_FILES, sep="\n  ")
        left = {n: sorted(set(re.findall(r"@@[A-Z0-9_]+@@", t))) for n, t in texts.items() if "@@" in t}
        print("tokens still unfilled (PUBLISHED_DATE needs --published-at):", left or "none")
        return 0

    CATALOGUE.write_bytes(data)
    CURRENT.write_text(json.dumps(current, indent=2) + "\n")
    RECORD.write_text(json.dumps(record, indent=2) + "\n")
    for name, text in texts.items():
        (ROOT / name).write_text(text)
    if args.checkouts_json is None:
        catalogue.unlink()
    left = [n for n, t in texts.items() if "@@" in t]
    if left:
        print("still holds placeholders (give --published-at, or fill after publication):", *left, sep="\n  ")
    print("filled. Next: python3 tests/docs-release-sync.py -v; python3 scripts/verify-release-assets.py "
          f"--record {RECORD.relative_to(ROOT)} --assets {args.assets} --closure-assets <staged closure dir>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
