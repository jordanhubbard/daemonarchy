#!/usr/bin/env python3
"""Prepare-only contracts; these fixtures are never native QA receipts."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from literate_ai.contracts.identity import canonical_identity
from literate_ai.project_releases import RELEASE_PLAN_SCHEMA
from literate_ai.release_files import SCHEMA

spec = importlib.util.spec_from_file_location(
    "qa", Path(__file__).resolve().parents[1] / "scripts/release-qa-plan.py"
)
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
IDENTITY = "sha256:" + "a" * 64


def identified(value):
    value["identity"] = canonical_identity(value).uri
    return value


class QAPlan(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "image.iso").write_bytes(b"fixture bytes")
        self.policy = SimpleNamespace(
            identity=IDENTITY,
            provider_repository="fixture/product",
            authenticated_receipt=None,
        )
        self.plan = identified(
            {
                "schema": RELEASE_PLAN_SCHEMA,
                "policy_identity": IDENTITY,
                "source_revision": "b" * 40,
                "next_version": "1.4.0",
                "tag": "product-1.4.0",
                "source_clean": True,
                "provider": {"kind": "github", "repository": "fixture/product"},
            }
        )
        self.files = identified(
            {
                "schema": SCHEMA,
                "revision": "b" * 40,
                "version": "1.4.0",
                "files": [
                    {
                        "role": "installer-iso",
                        "path": "image.iso",
                        "size": 13,
                        "identity": "sha256:"
                        + hashlib.sha256(b"fixture bytes").hexdigest(),
                    }
                ],
            }
        )

    def prepare(self):
        with patch(
            "literate_ai.project_releases.load_release_policy",
            return_value=(self.root, self.policy),
        ):
            return qa.prepare(self.root, self.plan, self.files, ("installer-iso",))

    def test_missing_authenticated_policy_is_explicit_blocker(self):
        result = self.prepare()
        self.assertFalse(result["ready"])
        self.assertFalse(result["acceptance_complete"])
        self.assertEqual(
            result["artifacts"][0]["public_url"],
            "https://github.com/fixture/product/releases/download/product-1.4.0/image.iso",
        )
        self.assertEqual(len(result["obligations"]), 5)
        for obligation in result["obligations"]:
            self.assertEqual(obligation["status"], "pending")
            self.assertEqual(
                obligation["harness_environment"], {"PACKAGE_QA_MODE": "final-rc"}
            )
            self.assertIsNone(obligation["cache_override"])

    def test_changed_artifact_is_refused_before_qa(self):
        (self.root / "image.iso").write_bytes(b"changed bytes")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.prepare()

    def test_changed_plan_or_policy_is_refused(self):
        self.plan["tag"] = "other"
        with self.assertRaisesRegex(ValueError, "identity"):
            self.prepare()
        self.plan.pop("identity")
        identified(self.plan)
        self.policy.identity = "sha256:" + "c" * 64
        with self.assertRaisesRegex(ValueError, "policy"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
