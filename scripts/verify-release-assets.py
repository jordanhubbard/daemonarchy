#!/usr/bin/env python3
"""Verify staged public release assets against an exact release input record.

This checks artifact integrity and the signed boot bundle. Native ISO runtime,
physical hardware, repository publication and the current test receipt have
separate acceptance gates.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
HEX = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
CERTIFICATE = re.compile(r"daemonarchy-[0-9]+(?:\.[0-9]+){1,2}\.pem\Z")
XZ_MAGIC = b"\xfd7zXZ\x00"
# Each architecture publishes its own image; aarch64 begins with 1.4.0.
ARCHITECTURES = {"amd64": (0, 0, 0), "aarch64": (1, 4, 0)}


def release_tuple(version):
    return tuple(map(int, version.split(".")))


def iso_asset(version, arch="amd64"):
    """Name the public image: xz-compressed from 1.4.0, the raw ISO before."""
    if arch not in ARCHITECTURES:
        raise ValueError(f"Unsupported image architecture: {arch}")
    raw = f"daemonarchy-{version}-{arch}.iso"
    return raw + ".xz" if release_tuple(version) >= (1, 4, 0) else raw


def record_architectures(record):
    """The record's image architectures; a record without the field is amd64 only."""
    if "architectures" not in record:
        return ["amd64"]
    architectures = record["architectures"]
    if (not isinstance(architectures, list) or not architectures
            or len(set(architectures)) != len(architectures)
            or any(not isinstance(arch, str) or arch not in ARCHITECTURES for arch in architectures)):
        raise ValueError("Release architectures must be a unique list of supported architectures")
    if architectures != sorted(architectures, key=list(ARCHITECTURES).index):
        raise ValueError("Release architectures must be listed in canonical order")
    for arch in architectures:
        if release_tuple(record["version"]) < ARCHITECTURES[arch]:
            raise ValueError(f"Release {record['version']} predates {arch} images")
    return architectures


def iso_assets(record):
    return [iso_asset(record["version"], arch) for arch in record_architectures(record)]


# The hardware bring-up trace image (DEBUG-004) is a separate image type,
# published xz-compressed from 1.4.0 when the record lists its architectures.
HWTRACE_FIRST = (1, 4, 0)


def hwtrace_asset(version, arch="amd64"):
    if arch != "amd64":
        raise ValueError(f"Unsupported hardware trace architecture: {arch}")
    return f"daemonarchy-hwtrace-{version}-{arch}.img.xz"


def hwtrace_assets(record):
    if "hwtrace" not in record:
        return []
    architectures = record["hwtrace"]
    if (not isinstance(architectures, list) or architectures != ["amd64"]):
        raise ValueError("Hardware trace images must be listed as [\"amd64\"]")
    if release_tuple(record["version"]) < HWTRACE_FIRST:
        raise ValueError(f"Release {record['version']} predates hardware trace images")
    return [hwtrace_asset(record["version"], arch) for arch in architectures]


def checked_images(record):
    return iso_assets(record) + hwtrace_assets(record)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate record key: {key}")
        result[key] = value
    return result


# The closure feeds: the signed upstream snapshot the installer prefers (PKG-002),
# one or more sharded, versioned, non-latest releases per architecture. Every
# asset is a compressed package or a pkg catalogue file; no raw payload.
CLOSURE_TAG = re.compile(r"packages-16-(amd64|aarch64)-[A-Za-z0-9._-]+\Z")
CLOSURE_PAYLOAD = re.compile(r"[A-Za-z0-9._-]+\.pkg\Z")
CLOSURE_CATALOGUE = ("meta", "meta.conf", "meta.pkg", "packagesite.pkg", "data.pkg")
CLOSURE_REQUIRED = ("meta.conf", "data.pkg")
CLOSURE_MAX_ASSETS = 1000
CLOSURE_FIRST_VERSION = (1, 4, 1)


def closure_feeds(record):
    """Validate and return the record's closure feeds: {tag: {asset: [size, "sha256:..."]}}."""
    feeds = record.get("closure_feeds")
    if feeds is None:
        if release_tuple(record["version"]) >= CLOSURE_FIRST_VERSION:
            raise ValueError("Releases from 1.4.1 must record the closure feeds the installer prefers")
        return {}
    if not isinstance(feeds, list) or not feeds:
        raise ValueError("Closure feeds must be a non-empty list")
    result, architectures = {}, set()
    for feed in feeds:
        if not isinstance(feed, dict) or set(feed) != {"tag", "assets"}:
            raise ValueError("A closure feed records exactly its tag and assets")
        tag, assets = feed["tag"], feed["assets"]
        match = CLOSURE_TAG.fullmatch(tag) if isinstance(tag, str) else None
        if not match or tag in result:
            raise ValueError(f"Invalid or duplicate closure feed tag: {tag!r}")
        if not isinstance(assets, dict) or not assets or len(assets) > CLOSURE_MAX_ASSETS:
            raise ValueError(f"Closure feed {tag} has no assets or too many")
        payloads = 0
        for name, entry in assets.items():
            if not (CLOSURE_PAYLOAD.fullmatch(name) or name in CLOSURE_CATALOGUE):
                raise ValueError(f"Closure feed {tag} has an unexpected or uncompressed asset: {name}")
            if (not isinstance(entry, list) or len(entry) != 2 or type(entry[0]) is not int or entry[0] <= 0
                    or not isinstance(entry[1], str) or not entry[1].startswith("sha256:") or not HEX.fullmatch(entry[1][7:])):
                raise ValueError(f"Invalid closure asset size or digest: {tag}/{name}")
            payloads += name not in CLOSURE_CATALOGUE
        if payloads == 0 or any(name not in assets for name in CLOSURE_REQUIRED):
            raise ValueError(f"Closure feed {tag} needs packages and a signed catalogue ({', '.join(CLOSURE_REQUIRED)})")
        result[tag] = assets
        architectures.add(match.group(1))
    if architectures != set(record_architectures(record)):
        raise ValueError("Closure feeds must cover exactly the release's image architectures")
    return result


def verify_closure_directory(feeds, directory):
    if directory is None:
        raise ValueError("The record lists closure feeds: pass --closure-assets with their staged directories")
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Closure asset directory must be a real directory")
    for tag, assets in feeds.items():
        shard = directory / tag
        if shard.is_symlink() or not shard.is_dir():
            raise ValueError(f"Missing staged closure feed directory: {tag}")
        present = {p.name for p in shard.iterdir()}
        if present != set(assets):
            raise ValueError(f"Closure feed {tag} assets differ from the record")
        for name, entry in assets.items():
            path = verified_asset(shard, name, entry)
            if name in ("meta", "meta.conf") and b"PRIVATE KEY" in path.read_bytes():
                raise ValueError(f"Closure feed {tag} contains private key material in {name}")
            if name in ("data.pkg", "packagesite.pkg"):
                member = subprocess.run(["tar", "-xOf", str(path)], capture_output=True)
                if member.returncode or b"PRIVATE KEY" in member.stdout:
                    raise ValueError(f"Closure feed catalogue {tag}/{name} is unreadable or holds private key material")


def read_record(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Release record must be a regular file")
    record = json.loads(path.read_text(), object_pairs_hook=unique_pairs)
    if not isinstance(record, dict) or record.get("schema") != "daemonarchy/release-inputs@1":
        raise ValueError("Unsupported release record")
    version = record.get("version")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("Expected a canonical release version")
    if record.get("tag") != f"daemonarchy-{version}":
        raise ValueError("Release tag and version differ")
    for field in ("installer_commit", "source_commit"):
        if not isinstance(record.get(field), str) or not COMMIT.fullmatch(record[field]):
            raise ValueError(f"Release {field} is invalid")
    if not isinstance(record.get("osversion"), int) or isinstance(record["osversion"], bool):
        raise ValueError("Release OSVERSION is invalid")
    assets = record.get("assets")
    if not isinstance(assets, dict):
        raise ValueError("Release asset map is missing")
    prefix = f"daemonarchy-{version}"
    expected = {name for image in checked_images(record) for name in (image, image + ".sha256")}
    expected |= {
        f"{prefix}-boot.txz",
        f"{prefix}-boot.txz.sig",
    }
    certificates = [name for name in assets if CERTIFICATE.fullmatch(name)]
    if len(certificates) != 1:
        raise ValueError("Expected one versioned public certificate")
    certificate = certificates[0]
    expected.update((certificate, certificate.removesuffix(".pem") + ".der"))
    if set(assets) != expected:
        raise ValueError("Release asset names are incomplete or unexpected")
    for name, entry in assets.items():
        if Path(name).name != name or not isinstance(entry, list) or len(entry) != 2:
            raise ValueError(f"Invalid asset record: {name}")
        size, identity = entry
        if type(size) is not int or size <= 0 or not isinstance(identity, str) or not identity.startswith("sha256:") or not HEX.fullmatch(identity[7:]):
            raise ValueError(f"Invalid asset size or digest: {name}")
    closure_feeds(record)
    return record, certificate


def verified_asset(directory, name, entry):
    path = directory / name
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != entry[0]:
            raise ValueError(f"Release asset size or type differs: {name}")
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != entry[1][7:]:
        raise ValueError(f"Release asset digest differs: {name}")
    return path


def verify(record_path, directory, closure_directory=None):
    record, certificate = read_record(record_path)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Asset directory must be a real directory")
    feeds = closure_feeds(record)
    if feeds:
        verify_closure_directory(feeds, closure_directory)
    paths = {
        name: verified_asset(directory, name, entry)
        for name, entry in record["assets"].items()
    }
    prefix = f"daemonarchy-{record['version']}"
    for iso in checked_images(record):
        checksum = paths[iso + ".sha256"].read_bytes()
        if checksum != f"{record['assets'][iso][1][7:]}  {iso}\n".encode():
            raise ValueError(f"ISO checksum file differs from the verified image: {iso}")
        if iso.endswith(".xz"):
            with paths[iso].open("rb") as stream:
                if stream.read(len(XZ_MAGIC)) != XZ_MAGIC:
                    raise ValueError(f"Compressed ISO asset is not an xz stream: {iso}")

    pem, der = paths[certificate], paths[certificate.removesuffix(".pem") + ".der"]
    if b"PRIVATE KEY" in pem.read_bytes():
        raise ValueError("Public certificate asset contains private material")
    if subprocess.check_output(["openssl", "x509", "-in", str(pem), "-outform", "DER"]) != der.read_bytes():
        raise ValueError("Public certificate PEM and DER differ")
    subprocess.run(["openssl", "x509", "-in", str(pem), "-checkend", "0", "-noout"],
                   check=True, stdout=subprocess.DEVNULL)

    spec = importlib.util.spec_from_file_location("daemonarchy_maintenance", ROOT / "secureboot" / "maintenance.py")
    if spec is None or spec.loader is None:
        raise ValueError("Secure Boot bundle verifier is unavailable")
    maintenance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maintenance)
    with tempfile.TemporaryDirectory(prefix="daemonarchy-release-assets-") as temporary:
        metadata = maintenance.unpack_snapshot(
            paths[f"{prefix}-boot.txz"], paths[f"{prefix}-boot.txz.sig"], pem, Path(temporary)
        )
    if (metadata.get("release") != record["version"]
            or metadata.get("base_source") != record["source_commit"]
            or metadata.get("osversion") != record["osversion"]
            or metadata.get("build", {}).get("base_source") != record["source_commit"]):
        raise ValueError("Signed boot bundle differs from the release selection")
    if metadata["build"].get("trust_anchor_sha256") != record["assets"][certificate][1][7:]:
        raise ValueError("Boot build receipt selects a different certificate")
    return record


def github(path):
    output = subprocess.check_output(
        ["gh", "api", f"repos/jordanhubbard/daemonarchy/{path}"], text=True
    )
    return json.loads(output, object_pairs_hook=unique_pairs)


def verify_published(record):
    tag = record["tag"]
    release = github(f"releases/tags/{tag}")
    latest = github("releases/latest")
    if (release.get("tag_name") != tag or release.get("draft") is not False
            or release.get("prerelease") is not False
            or release.get("target_commitish") != record["installer_commit"]
            or release.get("id") != latest.get("id")):
        raise ValueError("Published release is not the exact stable latest selection")
    observed = release.get("assets")
    if not isinstance(observed, list) or len(observed) != len(record["assets"]):
        raise ValueError("Published asset count differs")
    assets = {entry.get("name"): entry for entry in observed if isinstance(entry, dict)}
    if set(assets) != set(record["assets"]) or len(assets) != len(observed):
        raise ValueError("Published asset names differ")
    for name, (size, identity) in record["assets"].items():
        if assets[name].get("size") != size or assets[name].get("digest") != identity:
            raise ValueError(f"Published asset differs: {name}")
    reference = github(f"git/ref/tags/{tag}")
    target = reference.get("object")
    if not isinstance(target, dict):
        raise ValueError("Published tag has no Git object")
    if target.get("type") == "tag":
        annotated = github(f"git/tags/{target.get('sha')}")
        if annotated.get("tag") != tag:
            raise ValueError("Annotated tag name differs")
        target = annotated.get("object")
    if not isinstance(target, dict) or target.get("type") != "commit" or target.get("sha") != record["installer_commit"]:
        raise ValueError("Published tag does not select the reviewed product commit")
    verify_published_closure(record, latest)


def verify_published_closure(record, latest):
    """Each closure feed is its own versioned release, never the latest, with exactly the recorded assets."""
    for tag, assets in closure_feeds(record).items():
        release = github(f"releases/tags/{tag}")
        if release.get("tag_name") != tag or release.get("draft") is not False or release.get("id") == latest.get("id"):
            raise ValueError(f"Closure feed {tag} is not a published, non-latest release")
        observed = release.get("assets")
        if not isinstance(observed, list) or len(observed) != len(assets):
            raise ValueError(f"Published closure feed {tag} asset count differs")
        found = {entry.get("name"): entry for entry in observed if isinstance(entry, dict)}
        if set(found) != set(assets) or len(found) != len(observed):
            raise ValueError(f"Published closure feed {tag} asset names differ")
        for name, (size, identity) in assets.items():
            if found[name].get("size") != size or found[name].get("digest") != identity:
                raise ValueError(f"Published closure asset differs: {tag}/{name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--published", action="store_true",
                        help="also compare GitHub's stable latest release, tag and asset digests")
    parser.add_argument("--closure-assets", type=Path,
                        help="directory holding one staged subdirectory per closure feed tag (required from 1.4.1)")
    args = parser.parse_args()
    try:
        selection = verify(args.record, args.assets, args.closure_assets)
        if args.published:
            verify_published(selection)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        parser.exit(1, f"Release asset verification failed: {error}\n")
    suffix = " and published stable release" if args.published else ""
    print(f"Verified {len(selection['assets'])} staged assets and signed boot bundle{suffix} for {selection['tag']}")
