#!/usr/bin/env python3
"""Check exact 1.3.1 artifacts and the recorded MacBook release decision."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "d63d77f4eb3cc29e16510f7bdec73602e27c2844"
PORTS = "b785784219af455a9ce4fd70c59bc96ba77f469f"
DESKTOP = "ec2a00824ec95b342c0c095657ac725c56f0528b"
ISO_PRODUCT = "cdeb3434a2f7e5e205feb756c897b1e4a98d4c28"
CHECKS = (
    "fresh_install", "wifi_only_install", "nvme_io", "graphics", "keyboard",
    "trackpad", "debugger_resume", "signed_boot_chain", "untrusted_boot_rejected",
    "package_upgrade", "s3_resume", "t2_boot_policy",
)
DECISION = ROOT / "verification/macbook-release-decision-1.3.1.json"
EVIDENCE_STATUS = "MacBook pre-production checks operator-confirmed passed; final ISO rerun waived"
NATIVE_EVIDENCE = frozenset((
    "source-world.log", "source-kernel.log", "source-release-sets.log",
    "source-build.exit", "secureboot-build.exit", "bulk.log", "bulk.exit",
    "package-manifest.json", "ports.built", "app-feed.log", "app-feed.exit",
    "boot-bundle.log", "boot-bundle.exit", "iso-build.log", "iso.exit",
))
NATIVE_RESULTS = frozenset(name for name in NATIVE_EVIDENCE if name.endswith(".exit"))
HEX = re.compile(r"[0-9a-f]{64}\Z")


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


def tail_contains(path, marker):
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - 65536))
        return marker in stream.read()


def native_evidence(record, iso_sha256):
    """Bind the existing native build path to retained, exact release evidence.

    Literate AI's full project receipt remains an open 1.4 adoption task. This
    1.3.1 gate checks its current authority and locks separately, then requires
    the native build, signed feed, signed boot and ISO outputs used for release.
    """
    path = external_file("DAEMONARCHY_NATIVE_RECORD")
    require(record.get("native_evidence_sha256") == digest(path),
            "native evidence record differs from release selection")
    native = document(path)
    require(native.get("schema") == "daemonarchy/native-release-evidence@1"
            and native.get("source_commit") == SOURCE
            and native.get("ports_commit") == PORTS
            and native.get("desktop_commit") == DESKTOP
            and native.get("iso_installer_commit") == ISO_PRODUCT
            and native.get("osversion") == 1600029
            and native.get("iso_sha256") == iso_sha256,
            "native evidence selects other release inputs")
    entries = native.get("evidence")
    require(isinstance(entries, dict) and set(entries) == NATIVE_EVIDENCE,
            "native evidence inventory is incomplete")
    root = Path(os.environ.get("DAEMONARCHY_NATIVE_EVIDENCE_ROOT", ""))
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),
            "set DAEMONARCHY_NATIVE_EVIDENCE_ROOT to the retained native logs")
    paths = {}
    for name, expected in entries.items():
        require(isinstance(expected, str) and HEX.fullmatch(expected),
                "invalid native evidence digest: " + name)
        evidence = root / name
        require(evidence.is_file() and not evidence.is_symlink()
                and digest(evidence) == expected,
                "native evidence is missing or differs: " + name)
        paths[name] = evidence
    for name in NATIVE_RESULTS:
        require(paths[name].read_bytes() == b"0\n", "native result failed: " + name)
    require(tail_contains(paths["source-world.log"], b">>> World build completed")
            and tail_contains(paths["source-kernel.log"],
                              b">>> Kernel build for GENERIC completed"),
            "native source build completion is absent")
    manifest = document(paths["package-manifest.json"])
    require(manifest.get("source_revision") == SOURCE
            and manifest.get("ports_revision") == PORTS
            and manifest.get("jail_osversion") == 1600029,
            "native package manifest selects other source or ports")
    packages = manifest.get("packages")
    require(isinstance(packages, dict)
            and {"daemonarchy-1.3.1,1.pkg", "dotnet-9.0.14.pkg"} <= set(packages),
            "native desktop or required dotnet package is absent")
    require(manifest.get("built_sha256") == digest(paths["ports.built"]),
            "native successful-build list differs from package manifest")
    require(any(line.split()[:2] == ["lang/dotnet", "dotnet-9.0.14"]
                for line in paths["ports.built"].read_text().splitlines()),
            "native dotnet build result is absent")


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


def macbook_release_decision(record):
    """Bind the operator's scoped decision without inventing final-ISO results."""
    require(record.get("evidence_status") == EVIDENCE_STATUS,
            "MacBook release decision differs")
    require(record.get("macbook_release_decision_sha256") == digest(DECISION),
            "MacBook release decision digest differs")
    decision = document(DECISION)
    require(decision.get("schema") == "daemonarchy/macbook-release-decision@1"
            and decision.get("version") == "1.3.1"
            and decision.get("model") == "MacBookPro16,1"
            and decision.get("iso_installer_commit") == ISO_PRODUCT
            and decision.get("operator_confirmation_date") == "2026-10-24"
            and decision.get("operator_confirmation") ==
                "All pre-production checks have passed on the Intel 16-inch MacBook Pro."
            and decision.get("preproduction_result") == "passed (operator-confirmed)"
            and decision.get("preproduction_artifact_scope") ==
                "pre-production MacBook configurations; exact artifact hashes were not supplied with the operator confirmation"
            and decision.get("final_public_iso_rerun") == "waived by operator; not run"
            and decision.get("final_public_iso_sha256") is None
            and decision.get("final_public_iso_physical_result") == "not claimed"
            and decision.get("hardware_rooted_attestation") == "not claimed",
            "MacBook decision claims an unsupported physical result")
    checks = decision.get("final_public_iso_checks")
    require(isinstance(checks, dict) and set(checks) == set(CHECKS)
            and all(value == "not rerun" for value in checks.values()),
            "final public ISO hardware checks must remain not rerun")


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
    macbook_release_decision(record)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    require(record.get("installer_commit") == head, "release record selects another product commit")
    run("git", "merge-base", "--is-ancestor", ISO_PRODUCT, head)

    run("litai", "verify", "--gate", "authority", "--gate", "locks")

    assets = os.environ.get("DAEMONARCHY_RELEASE_ASSETS", "")
    require(bool(assets), "set DAEMONARCHY_RELEASE_ASSETS to the reviewed local stage")
    stage = Path(assets).resolve(strict=True)
    require(stage.is_dir(), "release asset stage is not a directory")
    run(sys.executable, "scripts/verify-release-assets.py", "--record", str(record_path),
        "--assets", str(stage))
    iso = stage / "daemonarchy-1.3.1-amd64.iso"
    run("sh", "scripts/check-image-size.sh", str(iso))
    native_evidence(record, record["assets"][iso.name][1].removeprefix("sha256:"))

    public_feed("checkouts-16-amd64-1.3.1-r2")
    public_feed("packages-16-amd64-1.3.1")
    print("1.3.1 release gate passed for exact native evidence, ISO, feeds and scoped MacBook decision")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        sys.exit("1.3.1 release gate refused: " + str(error))
