#!/usr/bin/env python3
"""Prepare exact artifact QA obligations through existing LitAI release APIs.

This read-only planner neither signs nor publishes and never creates acceptance
receipts. Native/VM workers must execute its obligations on the selected bytes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote


def prepare(root, plan, files, required_roles, *, receipt_root=None):
    from literate_ai.contracts.identity import canonical_identity
    from literate_ai.project_releases import RELEASE_PLAN_SCHEMA, load_release_policy
    from literate_ai.release_files import validate_release_files

    if plan.get("schema") != RELEASE_PLAN_SCHEMA:
        raise ValueError("expected existing LitAI release plan")
    if (
        plan.get("identity")
        != canonical_identity(
            {key: value for key, value in plan.items() if key != "identity"}
        ).uri
    ):
        raise ValueError("release plan identity differs")
    actual_root, policy = load_release_policy(root)
    if actual_root != root.resolve() or policy.identity != plan.get("policy_identity"):
        raise ValueError("release plan selects another current policy")
    if plan.get("source_clean") is not True:
        raise ValueError("release plan requires a clean selected source revision")
    manifest = validate_release_files(
        root,
        files,
        revision=plan["source_revision"],
        version=plan["next_version"],
        required_roles=tuple(required_roles),
    )
    provider = plan.get("provider")
    if (
        not isinstance(provider, dict)
        or provider.get("kind") != "github"
        or provider.get("repository") != policy.provider_repository
    ):
        raise ValueError("public QA requires the selected GitHub release provider")
    prefix = f"https://github.com/{provider['repository']}/releases/download/{quote(plan['tag'], safe='')}/"
    artifacts = [
        {
            "role": item["role"],
            "identity": item["identity"],
            "size": item["size"],
            "public_url": prefix + quote(Path(item["path"]).name, safe=""),
        }
        for item in manifest["files"]
    ]
    harness_environment = {"PACKAGE_QA_MODE": "final-rc"}
    if receipt_root is not None:
        receipt_root = Path(receipt_root)
        if (
            not receipt_root.is_absolute()
            or receipt_root.is_symlink()
            or not receipt_root.is_dir()
        ):
            raise ValueError(
                "receipt root must be an existing owned absolute directory"
            )
        work = receipt_root / "bhyve-work"
        if work.exists() or work.is_symlink():
            raise ValueError(
                "bhyve WORK must be a new child separate from retained receipts"
            )
        harness_environment["WORK"] = str(work)
    blockers = []
    if policy.authenticated_receipt is None:
        blockers.append(
            "current release policy does not configure authenticated receipts"
        )
    obligations = [
        {
            "operation": operation,
            "environment": environment,
            "artifact_manifest_identity": manifest["identity"],
            "cache_override": None,
            "harness_environment": harness_environment,
            "workspace_policy": "new bhyve-work child under existing owned receipt root",
            "forbidden_environment": [
                "PACKAGE_CACHE_URL",
                "PACKAGE_CACHE_META_SHA256",
                "PACKAGE_CACHE_PACKAGESITE_SHA256",
                "PACKAGE_CACHE_DATA_SHA256",
            ],
            "distribution": "public-urls",
            "status": "pending",
        }
        for operation, environment in (
            ("native-signature-and-package-check", "FreeBSD-native"),
            ("fresh-install-and-installed-boot", "fresh-FreeBSD-VM"),
            ("upgrade", "FreeBSD-VM"),
            ("rollback", "FreeBSD-VM"),
            ("physical-hardware-matrix", "FreeBSD-physical"),
        )
    ]
    result = {
        "schema": "daemonarchy/release-qa-plan@1",
        "release_plan_identity": plan["identity"],
        "qualified_files_identity": manifest["identity"],
        "source_revision": plan["source_revision"],
        "version": plan["next_version"],
        "artifacts": artifacts,
        "obligations": obligations,
        "blockers": blockers,
        "ready": not blockers,
        "acceptance_complete": False,
        "publication_owner": "litai release publish",
        "independent_publication_check": "litai release verify-published",
    }
    result["identity"] = canonical_identity(result).uri
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--release-plan", type=Path, required=True)
    parser.add_argument("--qualified-files", type=Path, required=True)
    parser.add_argument("--required-role", action="append", required=True)
    parser.add_argument(
        "--receipt-root",
        type=Path,
        help="existing native supervisor receipt root; bhyve-work child must not exist",
    )
    args = parser.parse_args()
    try:
        result = prepare(
            args.project,
            json.loads(args.release_plan.read_text()),
            json.loads(args.qualified_files.read_text()),
            args.required_role,
            receipt_root=args.receipt_root,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ready"] else 1
    except (ValueError, KeyError, TypeError, OSError, ImportError) as exc:
        parser.exit(2, f"QA plan refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
