#!/usr/bin/env python3
"""Pinned Git/canonical retained-contract regressions; no native execution claims."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from literate_ai.contracts.identity import ComponentCoordinate, ContentIdentity
from literate_ai.contracts.retained_component_ownership import RetainedComponentOwner
from literate_ai.contracts.retained_project import (RetainedProjectLimits, RetainedProjectManifest,
                                                  RetainedProjectMember)
from literate_ai.contracts.retained_project_lifecycle import RetainedProjectAction, RetainedProjectProfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release-input-graph.py"
spec = importlib.util.spec_from_file_location("release_graph", SCRIPT)
graph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph)
ID = ContentIdentity.parse_uri("sha256:" + "1" * 64)
OTHER = "sha256:" + "2" * 64


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Graph fixture")
        actions = tuple(RetainedProjectAction(name, name, "cc", (), requires,
                                              (name,), ("out/" + name,), 30)
                        for name, requires in (("build", ()), ("test", ("build",)),
                                               ("docs", ("build",)), ("accept", ("build", "test", "docs"))))
        self.profile = RetainedProjectProfile("FreeBSD-amd64", ID, ID, ID, ID, ID,
                                              (("cc", "unit/cc", ID),), actions, ("out/build",)).to_dict()
        self.write("unit/cc", b"fixture compiler bytes")
        self.write("unit/source.c", b"int main(void) { return 0; }\n")
        self.upstream = self.commit()
        self.selection = {"schema": graph.SCHEMA, "repositories": [], "units": []}
        self.unit = {"id": "source:tool", "repository": "source", "options": {"WITH_TESTS": True},
                     "flavor": None, "compiler": ID.uri, "sysroot": ID.uri,
                     "execution_identity": ID.uri, "generated_inputs": [], "dependencies": [],
                     "unresolved_inputs": [], "base_abi": {"osversion": 1600029,
                                                          "contract": ID.uri, "kernel_bound": False}}
        self.update_selection()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()

    def write(self, path, data):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"path": path, "sha256": graph.digest(data)}

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def update_selection(self, *, ownership=True):
        # Canonical role identities ignore unrelated profile policy bytes.
        tool = RetainedProjectMember("unit/cc", len((self.repo/"unit/cc").read_bytes()), 0o644,
                                     graph.digest((self.repo/"unit/cc").read_bytes()), "toolchain")
        auxiliary = []
        for path, role in (("unit/dep.lib", "dependency"), ("unit/sysroot.h", "sdk"),
                           ("unit/generated.h", "source"), ("unit/pkg-plist", "build-definition")):
            if (self.repo/path).exists():
                data = (self.repo/path).read_bytes()
                auxiliary.append(RetainedProjectMember(path, len(data), 0o644, graph.digest(data), role))
        skeleton = RetainedProjectManifest(("unit",), tuple(sorted([tool]+auxiliary, key=lambda m:m.path)),
                                          RetainedProjectLimits(100, 100000, 1000000), ("unit",))
        self.profile["toolchain_identity"] = skeleton.role_identity({"sdk", "toolchain"}).uri
        self.profile["dependency_identity"] = skeleton.role_identity({"dependency"}).uri
        self.profile["tools"][0]["identity"] = "sha256:" + tool.sha256
        self.unit["compiler"] = "sha256:" + tool.sha256
        self.unit["sysroot"] = skeleton.role_identity({"sdk"}).uri
        self.unit["profile"] = self.write("unit/profile.json", json.dumps(self.profile).encode())
        members = tuple(RetainedProjectMember(path, len((self.repo/path).read_bytes()), 0o644,
                                              graph.digest((self.repo/path).read_bytes()), role)
                        for path, role in (("unit/cc", "toolchain"), ("unit/profile.json", "build-definition"),
                                           ("unit/source.c", "source")))
        members = tuple(sorted(list(members) + auxiliary, key=lambda m:m.path))
        owners = (RetainedComponentOwner("unit", ComponentCoordinate("fixture", "tool"), ID),) if ownership else ()
        manifest = RetainedProjectManifest(("unit",), members,
                                          RetainedProjectLimits(100, 100000, 1000000),
                                          ("unit",), owners)
        self.unit["manifest"] = self.write("manifest.json", json.dumps(manifest.to_dict()).encode())
        revision = self.commit()
        self.selection["repositories"] = [{"id": "source", "repository": "https://example.invalid/source.git",
                                            "revision": revision,
                                            "upstream": {"repository": "https://example.invalid/upstream.git",
                                                         "revision": self.upstream}}]
        self.selection["units"] = [copy.deepcopy(self.unit)]

    def collect(self):
        return graph.collect(self.selection, {"source": self.repo})

    def decision(self, old, current=None):
        return graph.compare(old, self.collect() if current is None else current)["decisions"][0]["reason"]

    def test_exact_git_ancestry_and_canonical_profiles_are_locked_without_admission(self):
        report = self.collect()
        self.assertFalse(report["admitted"])
        self.assertEqual(report["repositories"][0]["upstream"]["merge_base"], self.upstream)
        self.assertEqual(report["repositories"][0]["git_tree"], self.git("rev-parse", "HEAD^{tree}"))
        self.assertEqual(report["build_dependency_order"], ["source:tool"])
        self.assertFalse(report["units"][0]["admitted"])
        self.assertIsNone(report["units"][0]["native_receipt"])

    def test_unrelated_commit_and_dirty_worktree_do_not_invalidate_compilation(self):
        old = self.collect()
        self.write("unrelated.txt", b"not a unit input")
        revision = self.commit()
        self.selection["repositories"][0]["revision"] = revision
        self.write("unit/source.c", b"uncommitted source is not the locked input")
        self.assertEqual(self.decision(old), "unchanged-inputs-verify-retained-products")

    def test_runtime_version_and_userland_osversion_require_requalification(self):
        old = self.collect()
        self.selection["units"][0]["base_abi"]["osversion"] += 1
        self.assertEqual(self.decision(old), "native-ABI-requalification-required")
        self.assertEqual(old["units"][0]["build_inputs_identity"],
                         self.collect()["units"][0]["build_inputs_identity"])

    def test_source_options_flavor_compiler_and_executor_changes_rebuild(self):
        for key, value in (("options", {"WITH_TESTS": False}), ("flavor", "native-port-flavor"),
                           ("execution_identity", OTHER)):
            with self.subTest(key=key):
                selection = copy.deepcopy(self.selection)
                old = self.collect()
                self.selection["units"][0][key] = value
                self.assertEqual(self.decision(old), "build-inputs-changed")
                self.selection = selection
        old = self.collect()
        self.write("unit/cc", b"changed compiler bytes")
        self.update_selection()
        self.assertEqual(self.decision(old), "build-inputs-changed")
        old = self.collect()
        self.write("unit/source.c", b"changed source or tracked generated input\n")
        self.update_selection()
        self.assertEqual(self.decision(old), "build-inputs-changed")

    def test_worker_and_release_policy_envelope_does_not_force_recompile(self):
        old = self.collect()
        self.profile["worker_identity"] = OTHER
        self.profile["release_policy_identity"] = OTHER
        self.update_selection()
        self.assertNotEqual(old["units"][0]["profile_identity"], self.collect()["units"][0]["profile_identity"])
        self.assertEqual(self.decision(old), "unchanged-inputs-verify-retained-products")

    def test_kernel_bound_osversion_change_rebuilds(self):
        self.selection["units"][0]["base_abi"]["kernel_bound"] = True
        old = self.collect()
        self.selection["units"][0]["base_abi"]["osversion"] += 1
        self.assertEqual(self.decision(old), "build-inputs-changed")

    def typed_dependency_fixture(self, kind):
        self.write("unit/dep.lib", b"selected dependency bytes")
        self.unit["dependencies"] = [{"unit": "source:provider", "kind": kind, "identity": ID.uri,
                                     "artifact_identity": ID.uri, "members": ["unit/dep.lib"],
                                     "selected_version": "1.0", "version_constraint": ">=1"}]
        self.update_selection()
        provider = copy.deepcopy(self.selection["units"][0])
        provider["id"] = "source:provider"
        provider["dependencies"][0]["unit"] = "source:provider"
        provider["dependencies"][0]["kind"] = "runtime"
        self.selection["units"].append(provider)

    def test_runtime_only_member_bytes_never_enter_compilation_projection(self):
        self.typed_dependency_fixture("runtime")
        old = self.collect()
        self.selection["units"][0]["dependencies"][0]["selected_version"] = "1.1"
        current = self.collect()
        before = {u["id"]:u for u in old["units"]}["source:tool"]
        after = {u["id"]:u for u in current["units"]}["source:tool"]
        self.assertEqual(before["build_inputs_identity"], after["build_inputs_identity"])
        self.assertNotEqual(before["qualification_inputs_identity"], after["qualification_inputs_identity"])
        self.assertFalse(any(m["role"] == "dependency" for m in after["build_inputs"]["members"]))
        self.write("unit/dep.lib", b"new compatible runtime implementation")
        self.update_selection()
        provider = copy.deepcopy(self.selection["units"][0])
        provider["id"] = "source:provider"
        provider["dependencies"][0]["unit"] = "source:provider"
        self.selection["units"].append(provider)
        changed = {u["id"]:u for u in self.collect()["units"]}["source:tool"]
        self.assertEqual(before["build_inputs_identity"], changed["build_inputs_identity"])
        self.assertNotEqual(before["qualification_inputs_identity"], changed["qualification_inputs_identity"])

    def test_untyped_canonical_dependency_members_refuse(self):
        self.typed_dependency_fixture("runtime")
        self.selection["units"][0]["dependencies"] = []
        with self.assertRaisesRegex(ValueError, "complete typed"):
            self.collect()

    def test_static_build_identity_change_invalidates_only_consumer(self):
        self.typed_dependency_fixture("build")
        old = self.collect()
        self.selection["units"][0]["dependencies"][0]["identity"] = OTHER
        current = self.collect()
        reasons = {d["unit"]:d["reason"] for d in graph.compare(old, current)["decisions"]}
        self.assertEqual(reasons["source:tool"], "build-inputs-changed")
        self.assertEqual(reasons["source:provider"], "unchanged-inputs-verify-retained-products")

    def test_changed_build_producer_blocks_consumer_until_output_is_proved(self):
        self.typed_dependency_fixture("build")
        old = self.collect()
        self.selection["units"][1]["options"] = {"WITH_TESTS": False}
        reasons = {d["unit"]:d["reason"] for d in graph.compare(old, self.collect())["decisions"]}
        self.assertEqual(reasons["source:provider"], "build-inputs-changed")
        self.assertEqual(reasons["source:tool"], "build-dependency-output-unproven")

    def test_sdk_header_and_generated_input_changes_rebuild(self):
        old = self.collect()
        self.write("unit/sysroot.h", b"typedef int selected_header;\n")
        self.update_selection()
        self.assertEqual(self.decision(old), "build-inputs-changed")
        old = self.collect()
        generated = self.write("unit/generated.h", b"#define GENERATED 1\n")
        self.unit["generated_inputs"] = [{**generated, "producer": "source:tool#generate", "output": "unit/generated.h"}]
        self.profile["actions"].insert(0, {"id":"generate", "stage":"generate", "tool":"cc", "argv":[],
                                         "requires":[], "inventory":["generated-header"],
                                         "outputs":["unit/generated.h"], "timeout_seconds":30})
        self.profile["actions"][1]["requires"] = ["generate"]
        self.update_selection()
        self.assertEqual(self.decision(old), "build-inputs-changed")
        self.selection["units"][0]["generated_inputs"][0]["producer"] = "missing#generate"
        with self.assertRaisesRegex(ValueError, "missing producer"):
            self.collect()
        self.selection["units"][0]["generated_inputs"][0]["producer"] = "source:tool#generate"
        self.selection["units"][0]["generated_inputs"][0]["sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "generated input"):
            self.collect()

    def test_missing_and_changed_retained_bytes_and_ownership_refuse(self):
        self.selection["units"][0]["profile"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest changed"):
            self.collect()
        self.update_selection(ownership=False)
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.collect()

    def test_missing_dependency_and_cycles_refuse(self):
        dep = {"unit": "missing", "kind": "build", "identity": ID.uri, "artifact_identity": ID.uri, "members": [],
               "selected_version": "1", "version_constraint": ">=1"}
        self.selection["units"][0]["dependencies"] = [dep]
        with self.assertRaisesRegex(ValueError, "closure"):
            self.collect()
        dep["unit"] = "source:tool"
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.collect()

    def test_unresolved_inputs_never_recommend_an_unchanged_hit(self):
        old = self.collect()
        self.selection["units"][0]["unresolved_inputs"] = ["native conditional header closure"]
        self.assertEqual(self.decision(old), "unresolved-inputs-repair-before-reuse")

    def test_nonexact_commits_and_unrelated_ancestry_refuse(self):
        self.selection["repositories"][0]["revision"] = "HEAD"
        with self.assertRaisesRegex(ValueError, "exact"):
            self.collect()

    def test_unrelated_upstream_commit_cannot_claim_ancestry(self):
        unrelated = self.git("commit-tree", self.git("rev-parse", "HEAD^{tree}"), "-m", "unrelated root")
        self.selection["repositories"][0]["upstream"]["revision"] = unrelated
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            self.collect()

    def test_json_duplicate_keys_and_unknown_fields_refuse(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            graph.document(b'{"schema":1,"schema":2}')
        self.selection["unexpected"] = 1
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.collect()


    def scoped_trace(self, phase="compile", paths=None):
        if paths is None:
            paths=["unit/cc","unit/source.c"]
        return {"schema":"daemonarchy/source-action-trace-observation@1","scope":phase,
                "commands":["cc -c /sealed/unit/source.c -o /obj/source.o" if phase=="compile" else "pkg create -m /sealed/unit/pkg-plist"],
                "cwd":"/obj","target":"source.o" if phase=="compile" else "fixture.pkg",
                "meta_sha256":"3"*64,"environment_identity":"4"*64,
                "input_accesses":[{"operation":"R","pid":1,"cwd":"/obj","path":"/sealed/"+p} for p in paths],
                "unresolved_inputs":[]}

    def projection(self, trace):
        manifest=RetainedProjectManifest.from_dict(json.loads((self.repo/self.unit["manifest"]["path"]).read_bytes()))
        profile=RetainedProjectProfile.from_dict(json.loads((self.repo/self.unit["profile"]["path"]).read_bytes()))
        return graph.project_action_trace(manifest,profile,"build",trace,{"/sealed":""})

    def test_packaging_only_bytes_change_package_projection_without_forcing_compile_key(self):
        self.write("unit/pkg-plist",b"old package envelope")
        self.update_selection()
        before=self.projection(self.scoped_trace())
        package_before=self.projection(self.scoped_trace("package",["unit/pkg-plist"]))
        self.write("unit/pkg-plist",b"changed packaging plist/install envelope")
        self.update_selection()
        after=self.projection(self.scoped_trace())
        package_after=self.projection(self.scoped_trace("package",["unit/pkg-plist"]))
        self.assertNotEqual(before["source_manifest_identity"],after["source_manifest_identity"])
        self.assertEqual(before["projected_inputs_identity"],after["projected_inputs_identity"])
        self.assertNotEqual(package_before["projected_inputs_identity"],package_after["projected_inputs_identity"])
        self.assertFalse(after["cache_admission"])
        self.assertIsNone(after["native_receipt"])
        self.assertEqual(graph.compare_action_projections(before,after)["reason"],"verify-prior-payload-under-current-native-policy")
        self.assertEqual(graph.compare_action_projections(package_before,package_after)["reason"],
                         "package-inputs-changed-repackage-and-requalify")

    def test_scoped_header_or_actual_command_change_invalidates_its_projection(self):
        self.write("unit/sysroot.h",b"selected header")
        self.update_selection()
        trace=self.scoped_trace(paths=["unit/cc","unit/source.c","unit/sysroot.h"])
        before=self.projection(trace)
        self.write("unit/sysroot.h",b"changed header")
        self.update_selection()
        after=self.projection(trace)
        self.assertNotEqual(before["projected_inputs_identity"],after["projected_inputs_identity"])
        trace["commands"]=["cc -O3 -c /sealed/unit/source.c -o /obj/source.o"]
        self.assertNotEqual(after["projected_inputs_identity"],self.projection(trace)["projected_inputs_identity"])

    def test_unknown_access_and_missing_environment_remain_explicit_native_gaps(self):
        trace=self.scoped_trace()
        trace["input_accesses"].append({"path":"/outside/unknown.so"})
        trace["environment_identity"]=None
        report=self.projection(trace)
        self.assertEqual(len(report["unresolved_inputs"]),2)
        self.assertFalse(report["cache_admission"])

    def test_trace_projection_cli_uses_actual_canonical_snapshot_bytes(self):
        trace=self.root/"trace.json"
        trace.write_text(json.dumps(self.scoped_trace()))
        output=self.root/"projection.json"
        args=[sys.executable,str(SCRIPT),"trace","--manifest",str(self.repo/self.unit["manifest"]["path"]),
              "--manifest-sha256",self.unit["manifest"]["sha256"],"--profile",str(self.repo/self.unit["profile"]["path"]),
              "--profile-sha256",self.unit["profile"]["sha256"],"--trace",str(trace),"--trace-sha256",graph.digest(trace.read_bytes()),
              "--snapshot",str(self.repo),"--action","build","--bind","/sealed=","--output",str(output)]
        result=subprocess.run(args,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(json.loads(output.read_bytes())["cache_admission"])
        self.assertEqual(output.stat().st_mode & 0o777,0o600)
        original=output.read_bytes()
        self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
        self.assertEqual(output.read_bytes(),original)

    def test_canonical_snapshot_byte_verification_refuses_changed_native_tool(self):
        first = graph.collect(self.selection, {"source": self.repo}, {"source:tool": self.repo})
        self.assertFalse(first["admitted"])
        self.write("unit/cc", b"different installed compiler")
        with self.assertRaises(ValueError):
            graph.collect(self.selection, {"source": self.repo}, {"source:tool": self.repo})

    def test_compiler_and_sysroot_must_match_canonical_role_closure(self):
        for key in ("compiler", "sysroot"):
            selection = copy.deepcopy(self.selection)
            self.selection["units"][0][key] = OTHER
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.collect()
            self.selection = selection

    def test_cli_preserves_existing_output_and_selected_repos(self):
        config = self.root/"selection.json"
        config.write_text(json.dumps(self.selection))
        output = self.root/"graph.json"
        args = [sys.executable, str(SCRIPT), str(config), "--repo", "source="+str(self.repo), "--output", str(output)]
        result = subprocess.run(args, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        original = output.read_bytes()
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(self.git("status", "--porcelain"), "")
        compared = self.root/"compared.json"
        compare_args = args[:-1] + [str(compared), "--previous", str(output)]
        self.assertEqual(subprocess.run(compare_args, capture_output=True).returncode, 0)
        self.assertEqual(json.loads(compared.read_bytes())["comparison"]["decisions"][0]["reason"],
                         "unchanged-inputs-verify-retained-products")


if __name__ == "__main__":
    unittest.main()
