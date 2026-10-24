#!/usr/bin/env python3
"""Fail closed until the exact 1.3.1 ISO and MacBook acceptance are current."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "d63d77f4eb3cc29e16510f7bdec73602e27c2844"
PORTS = "7e417dae24ffb95c4625601ae9d654eb2ca68f4d"
DESKTOP = "ec2a00824ec95b342c0c095657ac725c56f0528b"
ISO_PRODUCT = "cdeb3434a2f7e5e205feb756c897b1e4a98d4c28"
CHECKS = (
    "fresh_install", "wifi_only_install", "nvme_io", "graphics", "keyboard",
    "trackpad", "debugger_resume", "signed_boot_chain", "untrusted_boot_rejected",
    "package_upgrade",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON key: " + key)
        value[key] = item
    return value


def document(path):
    require(path.is_file() and not path.is_symlink(), "missing regular file: " + str(path))
    return json.loads(path.read_text(), object_pairs_hook=unique_pairs)


def external_file(variable):
    value = os.environ.get(variable, "")
    require(bool(value), "set " + variable + " to the reviewed evidence file")
    path = Path(value)
    require(path.is_absolute() and not path.is_symlink(),
            variable + " must name a regular absolute path")
    return path.resolve(strict=True)


def run(*argv):
    subprocess.run(argv, cwd=ROOT, check=True)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def public_feed(tag):
    payload = subprocess.check_output(
        ["gh", "api", f"repos/jordanhubbard/daemonarchy/releases/tags/{tag}"],
        text=True,
    )
    feed = json.loads(payload, object_pairs_hook=unique_pairs)
    require(feed.get("tag_name") == tag and feed.get("target_commitish") == ISO_PRODUCT,
            "support feed selects another release: " + tag)
    require(feed.get("draft") is False and feed.get("prerelease") is False,
            "support feed is not published: " + tag)
    require(isinstance(feed.get("assets"), list) and feed["assets"],
            "support feed has no assets: " + tag)


def main():
    record_path = external_file("DAEMONARCHY_RELEASE_RECORD")
    record = document(record_path)
    require(record.get("schema") == "daemonarchy/release-inputs@1"
            and record.get("version") == "1.3.1"
            and record.get("tag") == "daemonarchy-1.3.1", "wrong release record")
    require(record.get("iso_installer_commit") == ISO_PRODUCT
            and record.get("source_commit") == SOURCE
            and record.get("ports_commit") == PORTS
            and record.get("desktop_commit") == DESKTOP, "release input selection changed")
    require(record.get("evidence_status") == "qualified on final MacBook image",
            "final MacBook qualification is not recorded")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(record.get("installer_commit") == head, "release record selects another product commit")
    run("git", "merge-base", "--is-ancestor", ISO_PRODUCT, head)

    run("litai", "verify")

    assets = os.environ.get("DAEMONARCHY_RELEASE_ASSETS", "")
    require(bool(assets), "set DAEMONARCHY_RELEASE_ASSETS to the reviewed local stage")
    stage = Path(assets).resolve(strict=True)
    require(stage.is_dir(), "release asset stage is not a directory")
    run(sys.executable, "scripts/verify-release-assets.py", "--record", str(record_path),
        "--assets", str(stage))
    iso = stage / "daemonarchy-1.3.1-amd64.iso"
    run("sh", "scripts/check-image-size.sh", str(iso))

    hardware = document(external_file("DAEMONARCHY_HARDWARE_RECORD"))
    require(hardware.get("schema") == "daemonarchy/macbook-acceptance@1"
            and hardware.get("model") == "MacBookPro16,1"
            and hardware.get("result") == "passed", "MacBook acceptance has not passed")
    iso_identity = record["assets"][iso.name][1]
    require(hardware.get("iso_sha256") == iso_identity.removeprefix("sha256:")
            and hardware.get("installer_commit") == ISO_PRODUCT,
            "MacBook acceptance selects other ISO bytes or installer source")
    require(hardware.get("t2_boot_policy") in ("Full Security", "Medium Security")
            and hardware.get("firmware_enforced") is True,
            "T2 firmware enforcement is not established")
    checks = hardware.get("checks")
    require(isinstance(checks, dict) and all(checks.get(name) is True for name in CHECKS),
            "MacBook acceptance checks are incomplete")
    evidence_root = os.environ.get("DAEMONARCHY_HARDWARE_EVIDENCE", "")
    require(bool(evidence_root), "set DAEMONARCHY_HARDWARE_EVIDENCE to retained logs")
    evidence_root = Path(evidence_root).resolve(strict=True)
    evidence = hardware.get("evidence")
    require(isinstance(evidence, dict) and evidence,
            "MacBook acceptance has no retained evidence")
    for name, expected in evidence.items():
        require(isinstance(name, str) and name == Path(name).name and name not in (".", ".."),
                "invalid hardware evidence name")
        require(isinstance(expected, str) and len(expected) == 64,
                "invalid hardware evidence digest")
        path = evidence_root / name
        require(path.is_file() and not path.is_symlink() and digest(path) == expected,
                "hardware evidence is missing or differs: " + name)

    public_feed("checkouts-16-amd64-1.3.1")
    public_feed("packages-16-amd64-1.3.1")
    print("1.3.1 release gate passed for the exact native receipt, ISO, feeds and MacBook evidence")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        sys.exit("1.3.1 release gate refused: " + str(error))
