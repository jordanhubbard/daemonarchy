#!/usr/bin/env python3
"""Maintain release/current.json, the record of the latest published release.

  release-current.py show
  release-current.py check-published
  release-current.py update daemonarchy-<version> --osversion N \
      --application-feed TAG --checkout-feed TAG

`update` reads the published GitHub release with `gh`, never local build
outputs. It refuses drafts, prereleases and a release that GitHub does not mark
latest, and moves the previous current release into `previous_releases`.
`check-published` compares the file with GitHub's latest release. Documents are
then checked against the file by tests/docs-release-sync.py.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "release/current.json"
REPOSITORY = "jordanhubbard/daemonarchy"
SCHEMA = "daemonarchy/current-release@1"
# Every published image product: daemonarchy[-<product>]-<version>-<arch>.iso[.xz]
# or .img[.xz]. The installer has no product word; other products, such as the
# hardware-trace bring-up image, name themselves.
IMAGE = re.compile(
    r"daemonarchy-(?:(?P<product>[a-z][a-z0-9-]*?)-)?(?P<version>\d+\.\d+\.\d+)-"
    r"(?P<arch>amd64|aarch64)\.(?:iso|img)(?:\.parts\.json\.xz|\.xz)?\Z"
)


def gh_json(*args):
    output = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(output)


def published(tag=None):
    fields = "tagName,name,isDraft,isPrerelease,publishedAt,url,assets"
    release = gh_json("release", "view", *([tag] if tag else []), "-R", REPOSITORY, "--json", fields)
    latest = gh_json("api", f"repos/{REPOSITORY}/releases/latest")["tag_name"]
    if release["isDraft"] or release["isPrerelease"]:
        raise SystemExit(f"{release['tagName']} is a draft or prerelease")
    if release["tagName"] != latest:
        raise SystemExit(f"{release['tagName']} is not GitHub's latest release ({latest})")
    return release


def media_helpers():
    spec = importlib.util.spec_from_file_location("daemonarchy_current_media", Path(__file__).resolve().parent / "verify-release-assets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def approved_record(version, assets):
    if not any(name.endswith(".parts.json.xz") for name in assets):
        return None
    path = ROOT / f"verification/release-{version}.json"
    if not path.is_file():
        raise SystemExit("published split images require their approved release input record")
    record, _ = media_helpers().read_record(path)
    if record["version"] != version or record["assets"] != assets:
        raise SystemExit("published split assets differ from the approved release input record")
    return record


def images(version, assets, record=None):
    result, claimed_parts = [], set()
    helper = media_helpers() if record is not None else None
    transports = helper.image_transports(record) if helper else {}
    if record is not None and record["assets"] != assets:
        raise SystemExit("published assets differ from the approved release input record")
    for name in sorted(assets):
        match = IMAGE.match(name)
        if not match or match["version"] != version:
            continue
        checksum = name + ".sha256"
        if checksum not in assets:
            raise SystemExit(f"{name} has no published {checksum}")
        if name.endswith(".parts.json.xz"):
            logical = name.removesuffix(".parts.json.xz") + ".xz"
            if logical not in transports or transports[logical]["manifest"] != name:
                raise SystemExit("published split image has no approved logical-image selection")
            claimed_parts.update(transports[logical]["parts"])
            result.append(helper.current_image(logical, transports[logical], match["product"] or "installer", match["arch"]))
        else:
            result.append({"type": match["product"] or "installer", "arch": match["arch"],
                           "asset": name, "checksum_asset": checksum})
    unclaimed = {name for name in assets if re.search(r"\.(?:iso|img)\.part[0-9]{4}\.xz$", name)} - claimed_parts
    if unclaimed:
        raise SystemExit("published image parts have no approved manifest")
    if not result:
        raise SystemExit(f"no published image for {version}")
    pairs = [(entry["type"], entry["arch"]) for entry in result]
    if len(set(pairs)) != len(pairs):
        raise SystemExit("published image has multiple competing transports")
    return result


def asset_map(release):
    assets = {}
    for asset in release["assets"]:
        digest = asset.get("digest") or ""
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise SystemExit(f"{asset['name']} has no published SHA-256 digest")
        assets[asset["name"]] = [asset["size"], digest]
    return dict(sorted(assets.items()))


def check_published(current):
    release = published()
    problems = []
    if release["tagName"] != current["tag"]:
        problems.append(f"GitHub's latest release is {release['tagName']}, the record says {current['tag']}")
    elif asset_map(release) != current["assets"]:
        problems.append("published asset names, sizes or digests differ from the record")
    if not problems:
        expected = images(current["version"], current["assets"], approved_record(current["version"], current["assets"]))
        ordered = lambda entries: sorted(entries, key=lambda entry: (entry["type"], entry["arch"]))
        if ordered(current["images"]) != ordered(expected):
            problems.append("published image transports differ from the approved record")
    if not problems and release["publishedAt"] != current["published_at"]:
        problems.append("publication time differs from the record")
    return problems


def update(current, tag, args):
    release = published(tag)
    version = tag.removeprefix("daemonarchy-")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"{tag} is not a daemonarchy-<version> release")
    assets = asset_map(release)
    notes = f"docs/release-{version}.md"
    if not (ROOT / notes).is_file():
        raise SystemExit(f"write {notes} before recording the release")
    selected_images = images(version, assets, approved_record(version, assets))
    previous = list(current.get("previous_releases", []))
    if current["version"] != version:
        installer = next(image for image in current["images"] if image["type"] == "installer")
        size, digest = current["assets"][installer["asset"]]
        entry = {
            "version": current["version"],
            "tag": current["tag"],
            "published_at": current["published_at"],
            "image": [installer["asset"], size, digest],
        }
        if "transport" in installer:
            entry["image_transport"] = installer["transport"]
        record = f"verification/release-{current['version']}.json"
        if (ROOT / record).is_file():
            entry["record"] = record
        previous.insert(0, entry)
    return {
        "schema": SCHEMA,
        "version": version,
        "tag": tag,
        "name": release["name"],
        "published_at": release["publishedAt"],
        "url": release["url"],
        "notes": notes,
        "osversion": args.osversion,
        "application_feed": args.application_feed,
        "checkout_feed": args.checkout_feed,
        "images": selected_images,
        "assets": assets,
        "previous_releases": previous,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show")
    commands.add_parser("check-published")
    change = commands.add_parser("update")
    change.add_argument("tag")
    change.add_argument("--osversion", type=int, required=True)
    change.add_argument("--application-feed", required=True)
    change.add_argument("--checkout-feed", required=True)
    args = parser.parse_args()
    current = json.loads(CURRENT.read_text())
    if args.command == "show":
        print(f"{current['name']} ({current['tag']}), published {current['published_at']}")
        for image in current["images"]:
            size, digest = current["assets"][image["asset"]]
            print(f"  {image['type']}/{image['arch']}: {image['asset']} {size:,} bytes {digest}")
            if "transport" in image:
                transport = image["transport"]
                print(f"    raw image: {transport['raw_image'][0]:,} bytes {transport['raw_image'][1]}")
                for part in transport["parts"]:
                    print(f"    part: {part} {current['assets'][part][0]:,} bytes {current['assets'][part][1]}")
        return 0
    if args.command == "check-published":
        problems = check_published(current)
        for problem in problems:
            print(problem, file=sys.stderr)
        if not problems:
            print(f"release/current.json matches the published {current['tag']}")
        return 1 if problems else 0
    CURRENT.write_text(json.dumps(update(current, args.tag, args), indent=2) + "\n")
    print(f"recorded {args.tag}; now run python3 tests/docs-release-sync.py -v")
    return 0


if __name__ == "__main__":
    sys.exit(main())
