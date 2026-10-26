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
CATALOG = {a.coordinate.uri: a for a in graph.component_catalog()}


def registered(name):
    """An exact authored Component from the product's real catalog."""
    authoring = CATALOG["component://daemonarchy/" + name]
    return authoring.coordinate, authoring.identity
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
        self.unit = {"id": "source:tool", "repository": "source", "architecture": "amd64",
                     "options": {"WITH_TESTS": True},
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
        self.git("commit", "-q", "--allow-empty", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def update_selection(self, *, ownership=True, owner=None, profile_path="unit/profile.json",
                         manifest_path="manifest.json"):
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
        self.unit["profile"] = self.write(profile_path, json.dumps(self.profile).encode())
        members = tuple(RetainedProjectMember(path, len((self.repo/path).read_bytes()), 0o644,
                                              graph.digest((self.repo/path).read_bytes()), role)
                        for path, role in (("unit/cc", "toolchain"), (profile_path, "build-definition"),
                                           ("unit/source.c", "source")))
        members = tuple(sorted(list(members) + auxiliary, key=lambda m:m.path))
        owners = (RetainedComponentOwner("unit", *(owner or registered("package-engine"))),) if ownership else ()
        manifest = RetainedProjectManifest(("unit",), members,
                                          RetainedProjectLimits(100, 100000, 1000000),
                                          ("unit",), owners)
        self.unit["manifest"] = self.write(manifest_path, json.dumps(manifest.to_dict()).encode())
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

    def neutral_profile(self):
        # Isolate the architecture variant: everything else in the unit is equal.
        self.profile["target"] = "FreeBSD"
        self.update_selection()

    def test_amd64_product_can_never_satisfy_an_aarch64_unit(self):
        self.neutral_profile()
        amd64 = self.collect()
        self.selection["units"][0]["architecture"] = "aarch64"
        aarch64 = self.collect()
        before, after = amd64["units"][0], aarch64["units"][0]
        self.assertEqual((before["architecture"], after["architecture"]), ("amd64", "aarch64"))
        self.assertEqual(after["build_inputs"]["abi_architecture"], "FreeBSD:16:aarch64")
        self.assertNotEqual(before["build_inputs_identity"], after["build_inputs_identity"])
        self.assertNotEqual(before["qualification_inputs_identity"], after["qualification_inputs_identity"])
        for old, new in ((amd64, aarch64), (aarch64, amd64)):
            decision = graph.compare(old, new)["decisions"][0]["reason"]
            self.assertEqual(decision, "architecture-differs-no-reuse")
            self.assertIn(decision, graph.CHANGED)
        self.assertEqual(self.decision(aarch64), "unchanged-inputs-verify-retained-products")

    def test_architecture_change_blocks_consumers_of_the_rebuilt_producer(self):
        self.neutral_profile()
        self.typed_dependency_fixture("build")
        old = self.collect()
        for unit in self.selection["units"]:
            unit["architecture"] = "aarch64"
        decisions = {d["unit"]: d["reason"] for d in graph.compare(old, self.collect())["decisions"]}
        self.assertEqual(decisions["source:provider"], "architecture-differs-no-reuse")
        self.assertIn(decisions["source:tool"], graph.CHANGED)

    def test_unknown_or_missing_architecture_refuses(self):
        for value in ("arm64", "x86_64", "", None):
            with self.subTest(value=value):
                self.selection["units"][0]["architecture"] = value
                with self.assertRaisesRegex(ValueError, "typed variant"):
                    self.collect()
        del self.selection["units"][0]["architecture"]
        with self.assertRaisesRegex(ValueError, "unknown graph fields"):
            self.collect()

    def test_profile_target_for_another_architecture_refuses(self):
        self.selection["units"][0]["architecture"] = "aarch64"
        with self.assertRaisesRegex(ValueError, "different architecture"):
            self.collect()
        for target in ("FreeBSD-aarch64", "FreeBSD:16:aarch64", "freebsd-arm64"):
            with self.subTest(target=target):
                self.profile["target"] = target
                self.update_selection()
                self.selection["units"][0]["architecture"] = "aarch64"
                self.assertEqual(self.collect()["units"][0]["architecture"], "aarch64")

    def test_dependency_edges_never_cross_architectures(self):
        self.neutral_profile()
        self.typed_dependency_fixture("runtime")
        self.selection["units"][1]["architecture"] = "aarch64"
        with self.assertRaisesRegex(ValueError, "crosses architectures"):
            self.collect()
        self.selection["units"][1]["architecture"] = "amd64"
        report = self.collect()
        forged = copy.deepcopy(report)
        provider = next(u for u in forged["units"] if u["id"] == "source:provider")
        provider["architecture"] = "aarch64"
        with self.assertRaisesRegex(ValueError, "architecture differs"):
            graph.compare(report, forged)

    def test_recorded_architecture_must_match_its_typed_identity(self):
        self.neutral_profile()
        old = self.collect()
        forged = copy.deepcopy(old)
        forged["units"][0]["architecture"] = "aarch64"
        with self.assertRaisesRegex(ValueError, "architecture differs"):
            graph.compare(forged, old)

    def test_architecture_record_matches_graph_variants(self):
        record = json.loads((SCRIPT.parents[1] / "native/release-graph/architectures.json").read_text())
        self.assertEqual(record["schema"], "daemonarchy/release-architectures@1")
        variants = {v["id"]: v for v in record["variants"]}
        self.assertEqual(set(variants), set(graph.ARCHITECTURES))
        for name, variant in graph.ARCHITECTURES.items():
            self.assertEqual({k: variants[name][k] for k in ("abi", "target", "target_arch")},
                             {k: variant[k] for k in ("abi", "target", "target_arch")})
            self.assertFalse(variants[name]["qualifies_other_architectures"])

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

    def test_runtime_consumer_of_changed_producer_requires_requalification(self):
        self.typed_dependency_fixture("runtime")
        old = self.collect()
        self.selection["units"][1]["options"] = {"WITH_TESTS": False}
        reasons = {d["unit"]:d["reason"] for d in graph.compare(old, self.collect())["decisions"]}
        self.assertEqual(reasons["source:provider"], "build-inputs-changed")
        self.assertEqual(reasons["source:tool"], "native-ABI-requalification-required")
        # Requalification itself also propagates over (possibly cyclic) runtime edges.
        self.selection["units"][1]["options"] = {"WITH_TESTS": True}
        self.selection["units"][1]["base_abi"]["osversion"] += 1
        reasons = {d["unit"]:d["reason"] for d in graph.compare(old, self.collect())["decisions"]}
        self.assertEqual(reasons, {"source:provider": "native-ABI-requalification-required",
                                   "source:tool": "native-ABI-requalification-required"})

    def test_ambiguous_dependency_member_producer_refuses(self):
        self.typed_dependency_fixture("build")
        other = copy.deepcopy(self.selection["units"][0]["dependencies"][0])
        other.update(unit="source:other", kind="runtime")
        self.selection["units"][0]["dependencies"].append(other)
        with self.assertRaisesRegex(ValueError, "ambiguous dependency edge"):
            self.collect()

    def test_cross_unit_conflicting_owner_refuses(self):
        manifest = RetainedProjectManifest.from_dict(json.loads((self.repo/"manifest.json").read_bytes()))
        owners = (RetainedComponentOwner("unit", *registered("release")),)
        conflicting = RetainedProjectManifest(manifest.roots, manifest.members, manifest.limits,
                                              manifest.directories, owners)
        second = copy.deepcopy(self.unit)
        second["id"] = "source:other"
        second["manifest"] = self.write("other-manifest.json", json.dumps(conflicting.to_dict()).encode())
        self.selection["repositories"][0]["revision"] = self.commit()
        self.selection["units"].append(second)
        with self.assertRaisesRegex(ValueError, "ambiguous cross-unit owner"):
            self.collect()
        # The same canonical owner and bytes across units remain admissible inputs.
        second["manifest"] = self.unit["manifest"]
        self.assertEqual(len(self.collect()["units"]), 2)

    def test_tampered_previous_graph_or_unknown_edge_refuses_comparison(self):
        old = self.collect()
        self.assertFalse(old["units"][0] is self.selection["units"][0])
        self.selection["units"][0]["options"]["WITH_TESTS"] = False
        graph.compare(old, old)  # caller mutation does not alias the locked report
        forged = copy.deepcopy(old)
        forged["units"][0]["build_inputs"]["options"] = {"WITH_TESTS": False}
        with self.assertRaisesRegex(ValueError, "identity differs"):
            graph.compare(forged, self.collect())
        unknown = copy.deepcopy(old)
        edge = {"unit": "source:absent", "kind": "runtime", "identity": ID.uri, "artifact_identity": ID.uri,
                "members": [], "selected_version": "1", "version_constraint": ">=1"}
        unknown["units"][0]["qualification_inputs"]["dependencies"].append(edge)
        unknown["units"][0]["dependencies"] = unknown["units"][0]["qualification_inputs"]["dependencies"]
        unknown["units"][0]["qualification_inputs_identity"] = graph.canonical_identity(
            unknown["units"][0]["qualification_inputs"]).uri
        with self.assertRaisesRegex(ValueError, "unknown dependency edge"):
            graph.compare(unknown, old)
        with self.assertRaisesRegex(ValueError, "typed release input graph"):
            graph.compare({**old, "schema": "other"}, old)

    def test_previous_unresolved_closure_is_never_reused(self):
        self.selection["units"][0]["unresolved_inputs"] = ["native conditional header closure"]
        old = self.collect()
        self.selection["units"][0]["unresolved_inputs"] = []
        self.assertEqual(self.decision(old), "unresolved-inputs-repair-before-reuse")

    # --- registered Component owners -------------------------------------------------

    def test_owners_must_be_registered_project_components(self):
        report = self.collect()
        self.assertEqual(report["units"][0]["registered_owners"][0]["component"],
                         registered("package-engine")[0].to_dict())
        self.assertNotIn("registered-component-ownership", report["units"][0]["remaining_gates"])
        self.assertEqual({c["component"] for c in report["component_catalog"]}, set(CATALOG))
        for owner, message in (((ComponentCoordinate("fixture", "tool"), ID), "not a registered"),
                               ((registered("release")[0], ID), "not a registered")):
            with self.subTest(owner=owner[0].uri):
                self.update_selection(owner=owner)
                with self.assertRaisesRegex(ValueError, message):
                    self.collect()

    # --- producer observation translation ---------------------------------------------

    def edge(self, kind, declaration, requirement, origin, target=None):
        return {"kind": kind, "declaration": declaration, "requirement": requirement,
                "origin": origin, "target": target}

    def ports_observation(self, origin, edges, *, arch="amd64", revision=None):
        revision = revision or self.selection["repositories"][0]["revision"]
        return {"schema": "daemonarchy/ports-unit-input-observation@1", "revision": revision,
                "git_tree": self.git("rev-parse", revision + "^{tree}"), "origin": origin,
                "context": {"architecture": arch, "osversion": 1600029, "flavor": None,
                            "options": {"TEST": True}, "make_variables": {},
                            "package_database": {"mode": "empty-diagnostic", "identity": None}},
                "dependencies": edges, "inputs": [],
                "unresolved_inputs": [{"variable": "PKGMESSAGE", "path": "/private/worker/pkg-message",
                                       "reason": "generated or absent input requires producer"}],
                "recursive_closure_complete": False, "canonical_ownership_registered": False,
                "native_profile_admitted": False, "cache_admission": False}

    def translation(self, observations, *, policy="qualification", retained=None, bindings=None,
                    component="component://daemonarchy/package-engine", hosted=None):
        base = self.root / "translation"
        base.mkdir(exist_ok=True)
        units = []
        for index, observation in enumerate(observations):
            data = json.dumps(observation).encode()
            (base / ("observation-%d.json" % index)).write_bytes(data)
            units.append({"observation": {"path": "observation-%d.json" % index, "sha256": graph.digest(data)},
                          "hosted_summary": (hosted or {}).get(index), "repository": "source",
                          "component": component, "retained": (retained or {}).get(index),
                          "dependency_bindings": (bindings or {}).get(index, [])})
        request = {"schema": graph.TRANSLATION_SCHEMA, "repositories": self.selection["repositories"],
                   "test_edges": policy, "units": units}
        return graph.translate(request, base), request

    def binding(self, origin, kind, members=(), identity=ID.uri):
        return {"origin": origin, "kind": kind, "identity": identity, "artifact_identity": ID.uri,
                "members": list(members), "selected_version": "1.10.0", "version_constraint": ">=1.9"}

    def lz4_edges(self):
        return [self.edge("build", "BUILD_DEPENDS", "lz4", "archivers/liblz4"),
                self.edge("build", "LIB_DEPENDS", "liblz4.so", "archivers/liblz4"),
                self.edge("runtime", "LIB_DEPENDS", "liblz4.so", "archivers/liblz4"),
                self.edge("build", "BUILD_DEPENDS", "gmake", "devel/gmake"),
                self.edge("test", "TEST_DEPENDS", "python3.13", "lang/python313")]

    def test_translator_merges_origins_types_test_edges_and_carries_architecture(self):
        for arch in ("amd64", "aarch64"):
            result, _ = self.translation([self.ports_observation("archivers/tool", self.lz4_edges(), arch=arch)])
            self.assertIsNone(result["selection"])
            unit = result["draft_units"][0]
            self.assertEqual((unit["id"], unit["architecture"]), ("source:archivers/tool:" + arch, arch))
            merged = {(e["origin"], e["kind"]): e["declarations"] for e in result["provenance"][0]["merged_edges"]}
            self.assertEqual(merged, {("archivers/liblz4", "build"): 2, ("archivers/liblz4", "runtime"): 1,
                                      ("devel/gmake", "build"): 1, ("lang/python313", "test"): 1})
            self.assertIn("unbound test dependency lang/python313", unit["unresolved_inputs"])
            self.assertFalse(any("/private/" in item for item in unit["unresolved_inputs"]))
            self.assertFalse(result["admitted"])
        excluded, _ = self.translation([self.ports_observation("archivers/tool", self.lz4_edges())], policy="exclude")
        self.assertEqual([e["origin"] for e in excluded["provenance"][0]["excluded_test_edges"]], ["lang/python313"])
        self.assertFalse(any("python313" in item for item in excluded["draft_units"][0]["unresolved_inputs"]))
        with self.assertRaisesRegex(ValueError, "unobserved or excluded"):
            self.translation([self.ports_observation("archivers/tool", self.lz4_edges())], policy="exclude",
                             bindings={0: [self.binding("lang/python313", "test")]})

    def test_translator_refuses_unregistered_owner_untyped_arch_and_admission_claims(self):
        observation = self.ports_observation("archivers/tool", self.lz4_edges())
        with self.assertRaisesRegex(ValueError, "not a registered"):
            self.translation([observation], component="component://fixture/tool")
        for mutate, message in ((lambda o: o["context"].update(architecture="i386"), "typed variant"),
                                (lambda o: o.update(cache_admission=True), "admission"),
                                (lambda o: o.update(revision="0" * 40), "revision differs"),
                                (lambda o: o["dependencies"].append(self.edge("fetch", "X", "y", "a/b")), "untyped")):
            changed = copy.deepcopy(observation)
            mutate(changed)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.translation([changed])
        with self.assertRaisesRegex(ValueError, "test edge decision"):
            self.translation([observation], policy="refuse")
        with self.assertRaisesRegex(ValueError, "unobserved"):
            self.translation([observation], bindings={0: [self.binding("devel/cmake", "build")]})

    def test_translator_hosted_summary_must_corroborate_the_observation(self):
        source_record = json.loads((SCRIPT.parents[1] / "native/release-graph/hosted-source-40249878784.json").read_bytes())
        facts = source_record["facts"]
        observation = {"schema": "daemonarchy/source-unit-input-observation@1", "revision": facts["source_commit"],
                       "git_tree": facts["source_tree"], "unit": facts["unit"],
                       "context": {"target": "amd64", "target_arch": "amd64", "options": {"WITHOUT_TESTS": "yes"},
                                   "flags": {}, "src_conf_sha256": "5" * 64, "make_conf_sha256": "6" * 64,
                                   "payload_scope": "compile"},
                       "unresolved_inputs": [{"declaration": "LIBADD", "input": "util",
                                              "reason": "native-link-resolution-required-not-runtime-only"}],
                       "recursive_closure_complete": False, "compiler_header_trace_complete": False,
                       "canonical_ownership_registered": False, "native_profile_admitted": False,
                       "cache_admission": False}
        base = self.root / "translation"
        base.mkdir()
        data = json.dumps(source_record).encode()
        (base / "hosted.json").write_bytes(data)
        hosted = {0: {"path": "hosted.json", "sha256": graph.digest(data)}}
        self.selection["repositories"][0]["revision"] = facts["source_commit"]
        result, _ = self.translation([observation], hosted=hosted, component="component://daemonarchy/release")
        self.assertEqual(result["provenance"][0]["hosted_corroboration"]["scope"], "native-metadata-only")
        self.assertEqual(result["draft_units"][0]["id"], "source:usr.bin/truncate:amd64")
        self.assertIn("LIBADD util: native-link-resolution-required-not-runtime-only",
                      result["draft_units"][0]["unresolved_inputs"])
        observation["context"].update(target="arm64", target_arch="aarch64")
        with self.assertRaisesRegex(ValueError, "corroborate"):
            self.translation([observation], hosted=hosted, component="component://daemonarchy/release")

    def test_recorded_translation_example_is_reproducible(self):
        base = SCRIPT.parents[1] / "native/release-graph"
        request = json.loads((base / "translation-example-request.json").read_bytes())
        recorded = json.loads((base / "translation-example-result.json").read_bytes())
        def stable(result):
            # Component authoring identities move with component.md edits; registration is
            # rechecked against the live catalog, so compare everything else byte-for-byte.
            result = copy.deepcopy(result)
            result.pop("component_catalog")
            for item in result["provenance"]:
                item.pop("authoring_identity")
            return result
        self.assertEqual(stable(graph.translate(request, base)), stable(recorded))
        self.assertIsNone(recorded["selection"])
        self.assertFalse(recorded["admitted"])
        self.assertEqual({p["hosted_corroboration"]["scope"] for p in recorded["provenance"]}, {"native-metadata-only"})

    def translated_pair(self, test_identity=ID.uri):
        # Provider retained records without dependency members; consumer with dep.lib.
        if not hasattr(self, "retained_pair"):
            self.update_selection(profile_path="unit/provider-profile.json", manifest_path="provider-manifest.json")
            provider = {k: copy.deepcopy(self.unit[k]) for k in ("manifest", "profile", "compiler", "sysroot")}
            self.write("unit/dep.lib", b"selected dependency bytes")
            self.update_selection()
            consumer = {k: copy.deepcopy(self.unit[k]) for k in ("manifest", "profile", "compiler", "sysroot")}
            self.retained_pair = provider, consumer
        provider, consumer = self.retained_pair
        common = {"execution_identity": ID.uri, "base_abi": {"contract": ID.uri, "kernel_bound": False},
                  "generated_inputs": []}
        edges = self.lz4_edges()[:3] + [self.edge("test", "TEST_DEPENDS", "lz4", "archivers/liblz4")]
        result, _ = self.translation(
            [self.ports_observation("archivers/liblz4", []), self.ports_observation("archivers/tool", edges)],
            retained={0: {**provider, **common}, 1: {**consumer, **common}},
            bindings={1: [self.binding("archivers/liblz4", "build", ["unit/dep.lib"]),
                          self.binding("archivers/liblz4", "runtime", ["unit/dep.lib"]),
                          self.binding("archivers/liblz4", "test", [], test_identity)]})
        return result

    def test_translated_selection_builds_a_registered_typed_graph(self):
        result = self.translated_pair()
        report = self.collect_translated(result)
        units = {u["id"]: u for u in report["units"]}
        tool = units["source:archivers/tool:amd64"]
        build_edge = next(d for d in tool["dependencies"] if d["kind"] == "build")
        self.assertEqual([d["declaration"] for d in build_edge["declarations"]], ["BUILD_DEPENDS", "LIB_DEPENDS"])
        self.assertEqual([e["unit"] for e in tool["build_inputs"]["build_dependencies"]],
                         ["source:archivers/liblz4:amd64"])
        self.assertEqual(report["build_dependency_order"],
                         ["source:archivers/liblz4:amd64", "source:archivers/tool:amd64"])
        self.assertTrue(tool["unresolved_inputs"])
        # A changed test-only producer identity requalifies; it never rebuilds.
        changed = self.collect_translated(self.translated_pair(OTHER))
        after = {u["id"]: u for u in changed["units"]}["source:archivers/tool:amd64"]
        self.assertEqual(tool["build_inputs_identity"], after["build_inputs_identity"])
        self.assertNotEqual(tool["qualification_inputs_identity"], after["qualification_inputs_identity"])

    def collect_translated(self, result):
        self.assertIsNotNone(result["selection"])
        return graph.collect(result["selection"], {"source": self.repo})

    def test_test_edges_are_qualification_only_and_propagate_requalification(self):
        self.typed_dependency_fixture("test")
        old = self.collect()
        tool = {u["id"]: u for u in old["units"]}["source:tool"]
        self.assertEqual(tool["build_inputs"]["build_dependencies"], [])
        self.assertEqual(tool["dependencies"][0]["kind"], "test")
        self.selection["units"][1]["options"] = {"WITH_TESTS": False}
        reasons = {d["unit"]: d["reason"] for d in graph.compare(old, self.collect())["decisions"]}
        self.assertEqual(reasons, {"source:provider": "build-inputs-changed",
                                   "source:tool": "native-ABI-requalification-required"})

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
