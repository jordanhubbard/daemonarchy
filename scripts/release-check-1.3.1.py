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
REUSE_EVIDENCE = (NATIVE_EVIDENCE - {"bulk.log", "bulk.exit"}) | frozenset((
    "image-install.log", "image-install.exit", "pkg-check-deps.log",
    "pkg-check-files.log", "runtime-smoke.log", "reuse-provenance.json",
    "native-signed-feed-check.log", "native-signed-feed-check.exit",
))
REUSED_ARCHIVES = {
    "cef-152.0.6.pkg": "31dcd655bab385a5a134f54d4c28414a1f71bd0bb798151035879be8897a72b3",
    "chromium-154.0.8037.57_2.pkg": "e81a45507040c957303138f6c837a01873157827f8f3e3b578c6833a52a72177",
    "hyprland-preview-share-picker-0.2.1.pkg": "ff77d04adff7200c8a218fe3cd3779e05989d33663e4c29ee5bcab62f2bf7c74",
    "obs-studio-32.2.2_1.pkg": "a3444865cf47768cdd86b7a0107f5087242864c0f942231d2c4c3532ddd56b30",
    "tensaku-0.29.0.pkg": "2017171beeabe043f27fd24d47c1862360af76543c746a774412ebbf966570ad",
}
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
    schema = native.get("schema")
    require(schema in ("daemonarchy/native-release-evidence@1",
                       "daemonarchy/native-release-evidence@2")
            and native.get("source_commit") == SOURCE
            and native.get("ports_commit") == PORTS
            and native.get("desktop_commit") == DESKTOP
            and native.get("iso_installer_commit") == ISO_PRODUCT
            and native.get("osversion") == 1600029
            and native.get("iso_sha256") == iso_sha256,
            "native evidence selects other release inputs")
    entries = native.get("evidence")
    expected_files = (NATIVE_EVIDENCE if schema.endswith("@1") else REUSE_EVIDENCE)
    require(isinstance(entries, dict) and set(entries) == expected_files,
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
    for name in (name for name in expected_files if name.endswith(".exit")):
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
    if schema.endswith("@2"):
        require(manifest.get("schema") == "daemonarchy/madmax-package-import@2"
                and manifest.get("assembly_kind") == "selected-base-installed-reuse"
                and manifest.get("image_install_log_sha256") == digest(paths["image-install.log"])
                and manifest.get("reuse_provenance_sha256") == digest(paths["reuse-provenance.json"]),
                "qualified reuse installation is not bound to package manifest")
        provenance = document(paths["reuse-provenance.json"])
        retained = provenance.get("retained_archives")
        require(provenance.get("schema") == "daemonarchy/package-reuse-candidate@1"
                and provenance.get("status") == "admitted_for_release"
                and provenance.get("source_revision") == SOURCE
                and provenance.get("ports_revision") == PORTS
                and provenance.get("selected_base_osversion") == 1600029
                and isinstance(retained, list) and len(retained) == len(REUSED_ARCHIVES),
                "reuse provenance does not select qualified inputs")
        archives = {item.get("archive"): item for item in retained}
        require(set(archives) == set(REUSED_ARCHIVES),
                "retained archive inventory differs")
        for name, sha256 in REUSED_ARCHIVES.items():
            item = archives[name]
            package_name = item.get("name")
            require(item.get("sha256") == "sha256:" + sha256
                    and item.get("source_tree_equal") is True
                    and item.get("public_release") == "packages-16-amd64-1.1.1"
                    and item.get("qualification") == "admitted_for_release"
                    and isinstance(package_name, str)
                    and name.startswith(package_name + "-")
                    and packages.get(name, [None, None])[1] == sha256
                    and ("Installing " + name.removesuffix(".pkg") + "...").encode()
                        in paths["image-install.log"].read_bytes()
                    and ("Checking " + package_name + ": . done").encode()
                        in paths["pkg-check-deps.log"].read_bytes()
                    and ("Checking " + package_name + ": . done").encode()
                        in paths["pkg-check-files.log"].read_bytes(),
                    "retained archive lacks exact public or native install evidence: " + name)
        require(b"Installing daemonarchy-1.3.1,1..." in paths["image-install.log"].read_bytes()
                and b"Checking daemonarchy: . done" in paths["pkg-check-deps.log"].read_bytes()
                and b"Checking daemonarchy: . done" in paths["pkg-check-files.log"].read_bytes()
                and b"Chromium 154.0.8037.57" in paths["runtime-smoke.log"].read_bytes()
                and b"OBS Studio - 32.2.2" in paths["runtime-smoke.log"].read_bytes()
                and b"CEF RTLD_NOW load passed" in paths["runtime-smoke.log"].read_bytes(),
                "installed desktop or reused executable checks are missing")
        require(b"Selected root OSVERSION: 1600029; IGNORE_OSVERSION unset" in
                paths["native-signed-feed-check.log"].read_bytes()
                and b"Daemonarchy-Test repository update completed. 203 packages processed." in
                paths["native-signed-feed-check.log"].read_bytes(),
                "native selected-base signed feed verification is missing")


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
