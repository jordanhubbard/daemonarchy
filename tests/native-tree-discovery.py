#!/usr/bin/env python3
"""Pinned-tree discovery checks, not native dependency or package acceptance."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/inspect-freebsd-graph.py"
spec = importlib.util.spec_from_file_location("native_discovery", SCRIPT)
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()

    def add(self, name, content="input\n"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def source_fixture(self):
        self.add("Makefile")
        self.add("lib/foo/Makefile")
        self.add("usr.bin/tool/Makefile", f"BROKEN != touch {self.root / 'should-not-execute'}\n")
        self.add("usr.bin/tool/Makefile.depend", '''DIRDEPS = \\
 lib/foo \\
 lib/foo.host \\
 lib/${CSU_DIR}
.include <dirdeps.mk>
.if ${OPTION} == "yes"
DIRDEPS += missing/unit
.else
DIRDEPS += lib/foo
.endif\t# native comment
''')
        self.add("contrib/vendor/source.c")
        self.add("sys/dev/widget/device.c")
        self.add("share/data/binary.bin", "payload")
        os.symlink("../../contrib/vendor/source.c", self.repo / "lib/foo/linked.c")
        return self.commit()

    def test_complete_candidate_assignment_and_declared_variant_context(self):
        revision = self.source_fixture()
        report = discovery.discover("source", self.repo, revision)
        self.assertEqual(report["counts"]["tracked_inputs"], len(self.git("ls-files").splitlines()))
        self.assertEqual(sum(n["input_count"] for n in report["candidate_units"]), report["counts"]["tracked_inputs"])
        self.assertTrue(all(e["candidate_owner"] for e in report["inputs"]))
        edges = report["declared_references"]
        self.assertEqual(len(edges), 5)
        self.assertEqual(next(e for e in edges if e["token"] == "lib/foo.host")["provider_variant"], "host")
        self.assertEqual(report["counts"]["unresolved_reference_tokens"], 2)
        self.assertTrue(next(e for e in edges if e["token"] == "missing/unit")["conditions"])
        self.assertFalse((self.root / "should-not-execute").exists())
        self.assertEqual(report["counts"]["canonical_components"], 0)
        self.assertFalse(any(n["native_dependencies_complete"] for n in report["candidate_units"]))

    def test_pinned_objects_ignore_dirty_worktree_and_untracked_inputs(self):
        revision = self.source_fixture()
        first = discovery.discover("source", self.repo, revision)
        self.add("usr.bin/tool/Makefile.depend", "DIRDEPS = invented\n")
        self.add("extra/untracked.c")
        second = discovery.discover("source", self.repo, revision)
        self.assertEqual(first, second)

    def test_ports_origins_include_unselected_and_shared_support_inputs(self):
        for path in ("Makefile", "category/Makefile", "category/one/Makefile", "category/one/distinfo",
                     "category/two/Makefile", "category/two/pkg-descr", "Mk/bsd.port.mk", "Mk/helper/Makefile"):
            self.add(path)
        report = discovery.discover("ports", self.repo, self.commit())
        self.assertEqual(report["counts"]["port_origins"], 2)
        self.assertEqual(report["counts"]["tracked_inputs"], 8)
        self.assertEqual(report["counts"]["qualified_packages"], 0)
        self.assertEqual(report["counts"]["reviewed_input_owners"], 0)
        self.assertEqual(report["declared_references"], [])
        self.assertTrue(all(n["pkg_required"] for n in report["candidate_units"]))

    def test_symlink_is_an_input_and_never_followed(self):
        revision = self.source_fixture()
        report = discovery.discover("source", self.repo, revision)
        link = next(e for e in report["inputs"] if e["path"].endswith("linked.c"))
        self.assertEqual(link["mode"], "120000")
        self.assertEqual(link["candidate_owner"], "source:lib/foo")

    def test_missing_or_nonexact_revision_refused(self):
        revision = self.source_fixture()
        for value in ("HEAD", revision[:12], "0" * 40):
            with self.subTest(value=value), self.assertRaises((ValueError, subprocess.CalledProcessError)):
                discovery.discover("source", self.repo, value)

    def test_gitlink_requires_separate_admission(self):
        revision = self.source_fixture()
        self.git("update-index", "--add", "--cacheinfo", "160000," + revision + ",external")
        self.git("commit", "-qm", "gitlink")
        with self.assertRaisesRegex(ValueError, "separately admit"):
            discovery.discover("source", self.repo, self.git("rev-parse", "HEAD"))

    def test_truncated_or_unbalanced_inputs_fail_closed(self):
        revision = self.source_fixture()
        with patch.object(discovery, "MAX_ENTRIES", 1), self.assertRaisesRegex(ValueError, "bounded"):
            discovery.discover("source", self.repo, revision)
        with self.assertRaisesRegex(ValueError, "unbalanced"):
            discovery.literal_references(".if X\nDIRDEPS = lib/foo\n")

    def test_option_controls_are_not_dependency_edges(self):
        rows = discovery.literal_references("DIRDEPS_OPTIONS= CASPER\nDIRDEPS.CASPER.yes+= lib/foo\n")
        self.assertEqual(rows[0]["declaration_type"], "native-control-statement")
        self.assertEqual(rows[1]["token"], "lib/foo")
        self.assertEqual(rows[1]["variable"], "DIRDEPS.CASPER.yes")
        self.assertEqual(rows[1]["assignment"], "+=")

    def test_cli_exclusive_output_and_no_output_in_input_repo(self):
        revision = self.source_fixture()
        output = self.root / "report.json"
        args = [sys.executable, str(SCRIPT), "--kind", "source", "--repo", str(self.repo),
                "--revision", revision, "--output", str(output)]
        first = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(output.read_text())["state"], "discovery-only")
        before = output.read_bytes()
        second = subprocess.run(args, capture_output=True, text=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(output.read_bytes(), before)
        args[-1] = str(self.repo / "unsafe.json")
        third = subprocess.run(args, capture_output=True, text=True)
        self.assertNotEqual(third.returncode, 0)
        self.assertFalse((self.repo / "unsafe.json").exists())


if __name__ == "__main__":
    unittest.main()
