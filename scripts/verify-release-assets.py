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
CERTIFICATE = re.compile(r"daemonarchy-[0-9]+\.[0-9]+\.pem\Z")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate record key: {key}")
        result[key] = value
    return result


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
    if not isinstance(record.get("source_commit"), str) or not COMMIT.fullmatch(record["source_commit"]):
        raise ValueError("Release source commit is invalid")
    if not isinstance(record.get("osversion"), int) or isinstance(record["osversion"], bool):
        raise ValueError("Release OSVERSION is invalid")
    assets = record.get("assets")
    if not isinstance(assets, dict):
        raise ValueError("Release asset map is missing")
    prefix = f"daemonarchy-{version}"
    expected = {
        f"{prefix}-amd64.iso",
        f"{prefix}-amd64.iso.sha256",
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


def verify(record_path, directory):
    record, certificate = read_record(record_path)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Asset directory must be a real directory")
    paths = {
        name: verified_asset(directory, name, entry)
        for name, entry in record["assets"].items()
    }
    prefix = f"daemonarchy-{record['version']}"
    iso = f"{prefix}-amd64.iso"
    checksum = paths[iso + ".sha256"].read_bytes()
    if checksum != f"{record['assets'][iso][1][7:]}  {iso}\n".encode():
        raise ValueError("ISO checksum file differs from the verified image")

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    try:
        selection = verify(args.record, args.assets)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError,
            subprocess.CalledProcessError) as error:
        parser.exit(1, f"Release asset verification failed: {error}\n")
    print(f"Verified {len(selection['assets'])} staged assets and signed boot bundle for {selection['tag']}")
