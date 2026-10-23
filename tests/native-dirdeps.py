#!/usr/bin/env python3
"""Portable refusal/observation tests; not native FreeBSD qualification."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/resolve-freebsd-dirdeps.py"
spec = importlib.util.spec_from_file_location("dirdeps", SCRIPT)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "source"
        self.repo.mkdir()
        for name in ("bin/ls/Makefile.depend", "lib/libc/Makefile.depend",
                     "lib/libc/Makefile.depend.host", "share/mk/dirdeps.mk", "tools/daemonarchy/src.conf"):
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# native fixture\n")
        self.names = frozenset(p.relative_to(self.repo).as_posix()
                               for p in self.repo.rglob("*") if p.is_file())

    def observation(self, targets=None, includes=None, extra=None):
        targets = targets or [str(self.repo / "bin/ls.amd64"), str(self.repo / "lib/libc.host")]
        includes = includes or ["Makefile.depend", str(self.repo / "share/mk/dirdeps.mk"), "/dev/null"]
        return ("lib/libc\n" + " ".join(targets) + "\n" + " ".join(extra or targets)
                + "\n" + " ".join(includes) + "\namd64\n").encode()

    def test_real_qualified_contexts_and_shared_make_inputs(self):
        result = native.parse_observation(self.observation(), self.repo, "bin/ls", self.names)
        self.assertEqual(result["qualified_targets"][1]["context"], "host")
        self.assertEqual(result["qualified_targets"][1]["declaration"], "lib/libc/Makefile.depend.host")
        self.assertTrue(result["qualified_targets"][0]["self"])
        self.assertEqual(result["consulted_makefiles"], ["bin/ls/Makefile.depend", "share/mk/dirdeps.mk"])

    def test_extra_directory_inputs_are_preserved_and_missing_stays_unresolved(self):
        result = native.parse_observation(self.observation(extra=[str(self.repo / "missing.common")]),
                                          self.repo, "bin/ls", self.names)
        missing = result["qualified_targets"][-1]
        self.assertEqual(missing["kind"], "extra-directory-target")
        self.assertIsNone(missing["declaration"])
        self.assertIsNone(native.declaration(self.names, "lib/libc", "unsupported"))

    def test_dots_in_unqualified_extra_directories_are_not_machine_contexts(self):
        target = str(self.repo / "gnu/usr.bin/cc/cc")
        result = native.parse_observation(self.observation(extra=[target]), self.repo, "bin/ls", self.names)
        self.assertEqual(result["unqualified_targets"], [{
            "target": "gnu/usr.bin/cc/cc", "reason": "no-established-target-context"}])
        self.assertFalse(any(t["context"] == "bin/cc/cc" for t in result["qualified_targets"]))
        # A valid qualified reference in the same query must survive.
        self.assertTrue(any(t["unit"] == "lib/libc" for t in result["qualified_targets"]))
        record = {"unit": "bin/ls", "context": "amd64", "status": "observed",
                  "qualified_targets": [], "unqualified_targets": result["unqualified_targets"]}
        self.assertFalse(native.directory_graph({("bin/ls", "amd64"): record})[
            "observed_directory_closure_resolved"])

    def test_external_and_untracked_make_inputs_refuse(self):
        for includes in (["/etc/make.conf"], ["unknown.mk"]):
            with self.assertRaises(ValueError):
                native.parse_observation(self.observation(includes=includes), self.repo, "bin/ls", self.names)

    def test_redirected_make_input_refuses(self):
        p = self.repo / "share/mk/dirdeps.mk"
        p.unlink()
        external = self.root / "external.mk"
        external.write_text("# redirected\n")
        p.symlink_to(external)
        with self.assertRaises(ValueError):
            native.parse_observation(self.observation(), self.repo, "bin/ls", self.names)

    def test_escaping_targets_unsupported_paths_and_ambiguous_output_refuse(self):
        for value in (self.observation(targets=["/elsewhere/libc.amd64"]),
                      self.observation(targets=[str(self.repo / "../libc.amd64")]),
                      b"noise\n" + self.observation(), b"\n" * 5,
                      self.observation().replace(b"\namd64\n", b"\narm64\n")):
            with self.assertRaises(ValueError):
                native.parse_observation(value, self.repo, "bin/ls", self.names)
        for unit in (".", "../escape", "/absolute", "unit;touch", "unit/./path"):
            with self.assertRaises(ValueError):
                native.relative(unit)

    def test_acknowledgement_and_native_identity_before_any_query(self):
        with patch.object(native, "bounded_query") as query:
            with self.assertRaisesRegex(ValueError, "acknowledge"):
                native.collect(self.repo, "a" * 40, [], self.root / "out", acknowledged=False)
            with patch.object(native.platform, "system", return_value="Linux"):
                with self.assertRaisesRegex(ValueError, "native amd64 FreeBSD"):
                    native.collect(self.repo, "a" * 40, [], self.root / "out", acknowledged=True)
            query.assert_not_called()
        self.assertFalse((self.root / "out").exists())

    def test_actual_bounded_process_exit_deadline_and_output_limit(self):
        env = {"PATH": os.defpath}
        code, stdout, stderr = native.bounded_query([sys.executable, "-c", "print('observed')"], env, 2)
        self.assertEqual((code, stdout, stderr), (0, b"observed\n", b""))
        with self.assertRaisesRegex(ValueError, "deadline"):
            native.bounded_query([sys.executable, "-c", "import time; time.sleep(10)"], env, 0.05)
        with patch.object(native, "MAX_QUERY_BYTES", 1024):
            code, stdout, stderr = native.bounded_query(
                [sys.executable, "-c", "import os; os.write(1,b'x'*100000)"], env, 2)
        self.assertLessEqual(len(stdout) + len(stderr), 1024)

    def test_clean_pin_and_ignored_inputs(self):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL).decode().strip()
        git("init")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "user.name", "Fixture")
        (self.repo / ".gitignore").write_text("ignored.mk\n")
        git("add", ".")
        git("commit", "-m", "fixture")
        revision = git("rev-parse", "HEAD")
        self.assertIn("bin/ls/Makefile.depend", native.clean_source(self.repo, revision))
        (self.repo / "ignored.mk").write_text("DIRDEPS=unreviewed\n")
        with self.assertRaisesRegex(ValueError, "ignored"):
            native.clean_source(self.repo, revision)
        (self.repo / "ignored.mk").unlink()
        git("update-index", "--assume-unchanged", "bin/ls/Makefile.depend")
        (self.repo / "bin/ls/Makefile.depend").write_text("# hidden mutation\n")
        self.assertFalse(git("status", "--porcelain"))
        with self.assertRaisesRegex(ValueError, "hidden index flags"):
            native.clean_source(self.repo, revision)
        with self.assertRaises(ValueError):
            native.clean_source(self.repo, "HEAD")

    def test_collection_retains_failure_and_refuses_overwrite(self):
        output = self.root / "observation"
        value = self.observation(targets=[str(self.repo / "bin/ls.amd64"), str(self.repo / "lib/libc.amd64")])
        def query(argv, env, timeout):
            self.assertNotIn("MAKEFLAGS", env)
            self.assertIn("__MAKE_CONF=/dev/null", argv)
            if argv[argv.index("-C") + 1].endswith("bin/ls"):
                return 0, value, b""
            return 2, b"", b"fixture metadata rejected\n"
        with patch.object(native.platform, "system", return_value="FreeBSD"), \
                patch.object(native.platform, "machine", return_value="amd64"), \
                patch.object(native.os, "geteuid", return_value=1001), \
                patch.object(native, "clean_source", return_value=self.names), \
                patch.object(native, "bounded_query", side_effect=query), \
                patch.object(native, "digest", return_value="a" * 64):
            report = native.collect(self.repo, "a" * 40, ["bin/ls"], output, acknowledged=True)
            self.assertFalse(report["directory_graph"]["observed_directory_closure_resolved"])
            self.assertEqual(report["canonical_components_registered"], 0)
            self.assertEqual(report["records"][1]["status"], "query-failed")
            for record in report["records"]:
                for name in ("stdout", "stderr"):
                    self.assertTrue((output / record["query_output"][name]).is_file())
            retained = (output / "observation.json").read_bytes()
            self.assertEqual(json.loads(retained)["state"], "observation-only")
            with self.assertRaises(FileExistsError):
                native.collect(self.repo, "a" * 40, ["bin/ls"], output, acknowledged=True)
            self.assertEqual((output / "observation.json").read_bytes(), retained)

    def test_cycles_and_missing_nodes_cannot_claim_a_resolved_directory_closure(self):
        def record(unit, dependency):
            return {"unit": unit, "context": "amd64", "status": "observed",
                    "qualified_targets": [{"unit": dependency, "context": "amd64", "self": False}]}
        records = {("a", "amd64"): record("a", "b"), ("b", "amd64"): record("b", "a")}
        graph = native.directory_graph(records)
        self.assertFalse(graph["acyclic"])
        self.assertFalse(graph["observed_directory_closure_resolved"])
        self.assertEqual(len(graph["cyclic_or_cycle_dependent_nodes"]), 2)
        records.pop(("b", "amd64"))
        with self.assertRaises(ValueError):
            native.directory_graph(records)


if __name__ == "__main__":
    unittest.main()
