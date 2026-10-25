#!/usr/bin/env python3
"""Lock owned Git inputs and project canonical retained profiles into a review graph.

Read-only adapter: it neither schedules actions nor authorizes cache reuse. Native
producer observations, registered ownership and lifecycle admission remain required.
Run with the project's matching installed Literate AI interpreter.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from literate_ai.adapters.retained_project_inputs import verify_retained_project_inputs
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.retained_project import RetainedProjectManifest
from literate_ai.contracts.retained_project_lifecycle import RetainedProjectProfile

SCHEMA = "daemonarchy/release-input-selection@1"
MAX_JSON = 32 * 1024 * 1024


def require(test, message):
    if not test:
        raise ValueError(message)


def fields(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected.split()),
            "missing or unknown graph fields")


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def document(data):
    require(len(data) <= MAX_JSON, "JSON exceeds input bound")
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda value: require(False, "invalid JSON constant"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text(value):
    require(isinstance(value, str) and value and len(value) <= 4096 and
            not any(ord(c) < 32 for c in value), "invalid bounded text")
    return value


def relative(value):
    text(value)
    path = PurePosixPath(value)
    require(not path.is_absolute() and value == path.as_posix() and
            not any(p in (".", "..") for p in path.parts) and "\\" not in value,
            "input must be a canonical repository-relative path")
    return value


def identity(value):
    return ContentIdentity.parse_uri(value).uri


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
                          env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}).stdout


def commit(repo, revision):
    require(isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{40}", revision),
            "select an exact 40-digit Git commit")
    require(git(repo, "rev-parse", "--verify", revision + "^{commit}").decode().strip() == revision,
            "selected commit does not exist")
    return revision


def lock_repository(spec, repo):
    fields(spec, "id repository revision upstream")
    name, url = text(spec["id"]), text(spec["repository"])
    require(url.startswith("https://") and "@" not in url, "public repository URL required")
    revision = commit(repo, spec["revision"])
    tree = git(repo, "rev-parse", revision + "^{tree}").decode().strip()
    ancestry = None
    if spec["upstream"] is not None:
        fields(spec["upstream"], "repository revision")
        upstream_url = text(spec["upstream"]["repository"])
        require(upstream_url.startswith("https://") and "@" not in upstream_url,
                "public upstream URL required")
        upstream = commit(repo, spec["upstream"]["revision"])
        base = git(repo, "merge-base", revision, upstream).decode().strip()
        require(base == upstream, "selected upstream commit is not an ancestor; ancestry is not admitted")
        ancestry = {"repository": upstream_url, "revision": upstream,
                    "git_tree": git(repo, "rev-parse", upstream + "^{tree}").decode().strip(),
                    "merge_base": base}
    return {"id": name, "repository": url, "revision": revision, "git_tree": tree,
            "upstream": ancestry}


def blob(repo, revision, path, expected=None):
    relative(path)
    # ls-tree checks the entry type so a symlink's text cannot masquerade as JSON.
    entries = git(repo, "ls-tree", "-z", revision, "--", path).split(b"\0")
    require(len(entries) == 2 and entries[0], "selected input is not one Git file: " + path)
    metadata, actual = entries[0].split(b"\t", 1)
    mode, kind, oid = metadata.decode().split()
    require(actual.decode() == path and kind == "blob" and mode in ("100644", "100755", "120000"),
            "unsupported Git input: " + path)
    data = git(repo, "cat-file", "blob", oid)
    if expected is not None:
        require(digest(data) == expected, "selected input digest changed: " + path)
    return mode, data


def read_record(repo, revision, reference, retained_root=None):
    fields(reference, "path sha256")
    if retained_root is not None:
        path = retained_root / relative(reference["path"])
        require(not path.is_symlink() and path.resolve().is_relative_to(retained_root.resolve()),
                "retained metadata must stay within its explicit root")
        with path.open("rb") as stream:
            data = stream.read(MAX_JSON + 1)
        require(digest(data) == reference["sha256"], "retained record digest changed")
        return document(data)
    mode, data = blob(repo, revision, reference["path"], reference["sha256"])
    require(mode != "120000", "record must be a regular Git file")
    return document(data)


def unit_record(spec, repos, paths, retained_root=None):
    fields(spec, "id repository manifest profile options flavor compiler sysroot generated_inputs dependencies unresolved_inputs base_abi execution_identity")
    name, repository = text(spec["id"]), text(spec["repository"])
    require(repository in repos, "unit names an unselected repository")
    revision, repo = repos[repository]["revision"], paths[repository]
    manifest = RetainedProjectManifest.from_dict(read_record(repo, revision, spec["manifest"], retained_root))
    profile = RetainedProjectProfile.from_dict(read_record(repo, revision, spec["profile"], retained_root))
    require(bool(getattr(manifest, "component_ownership", ())),
            "canonical retained Component ownership is required; discovery is insufficient")
    profile_members = [m for m in manifest.members if m.path == spec["profile"]["path"]]
    require(len(profile_members) == 1 and profile_members[0].role == "build-definition",
            "profile must belong to the retained build-definition closure")
    known = {m.path: m for m in manifest.members}
    if retained_root is not None:
        # Use the framework's own byte/mode/link verifier for captured native tools
        # and generated inputs, which must never be committed as repository blobs.
        verify_retained_project_inputs(retained_root, manifest)
    generated_paths = {e["path"] for e in spec["generated_inputs"]}
    for member in manifest.members:
        if retained_root is not None:
            entry = git(repo, "ls-tree", "-z", revision, "--", member.path)
            if not entry:
                require(member.role in {"sdk", "toolchain", "dependency", "test-policy", "release-policy",
                                        "acceptance-policy", "sdk-policy"} or
                        member.path == spec["profile"]["path"] or member.path in generated_paths,
                        "untracked source/build input needs an explicit generated producer: " + member.path)
                continue
        mode, data = blob(repo, revision, member.path, member.sha256)
        require(len(data) == member.size and
                (0o120000 if mode == "120000" else 0o755 if mode == "100755" else 0o644) == member.mode,
                "retained member mode/size differs from selected Git object")
        require((mode == "120000") == (member.symlink_target is not None), "retained link kind differs")
        if mode == "120000":
            require(data.decode() == member.symlink_target, "retained symlink target differs")
    require(profile.toolchain_identity == manifest.role_identity({"sdk", "toolchain"}),
            "canonical SDK/toolchain role closure differs from profile")
    require(profile.dependency_identity == manifest.role_identity({"dependency"}),
            "canonical dependency role closure differs from profile")
    for tool_name, tool_path, tool_identity in profile.tools:
        tool = known.get(tool_path)
        require(tool is not None and tool.role in {"toolchain", "sdk"} and
                tool.sha256 == tool_identity.digest, "tool bytes absent from canonical SDK/toolchain closure")
    require(spec["compiler"] in {i.uri for _, _, i in profile.tools},
            "compiler must name an exact tool in the canonical profile")
    require(spec["sysroot"] == manifest.role_identity({"sdk"}).uri,
            "sysroot must bind the exact selected canonical SDK closure")
    require(isinstance(spec["options"], dict) and
            all(isinstance(k, str) and isinstance(v, (str, bool, int)) for k, v in spec["options"].items()),
            "options must name exact native selections")
    require(spec["flavor"] is None or isinstance(spec["flavor"], str), "invalid native port flavor")
    fields(spec["base_abi"], "osversion contract kernel_bound")
    base = spec["base_abi"]
    require(type(base["osversion"]) is int and base["osversion"] > 0 and
            type(base["kernel_bound"]) is bool, "invalid FreeBSD ABI provenance")
    identity(base["contract"])
    for key in ("compiler", "sysroot", "execution_identity"):
        identity(spec[key])
    require(isinstance(spec["generated_inputs"], list), "generated input inventory required")
    generated = []
    for entry in spec["generated_inputs"]:
        fields(entry, "path sha256 producer")
        member = known.get(relative(entry["path"]))
        require(member is not None and member.sha256 == entry["sha256"],
                "generated input must be in retained byte closure")
        generated.append({**entry, "producer": text(entry["producer"])})
    require(len({e["path"] for e in generated}) == len(generated), "duplicate generated input")
    dependencies, seen = [], set()
    require(isinstance(spec["dependencies"], list), "typed dependency inventory required")
    for dep in spec["dependencies"]:
        fields(dep, "unit kind identity artifact_identity members selected_version version_constraint")
        require(dep["kind"] in ("build", "runtime"), "dependency kind must be build or runtime")
        key = (text(dep["unit"]), dep["kind"])
        require(key not in seen, "duplicate typed dependency edge")
        seen.add(key)
        identity(dep["identity"])
        identity(dep["artifact_identity"])
        require(isinstance(dep["members"], list) and len(set(dep["members"])) == len(dep["members"]),
                "dependency member inventory must be unique")
        for path in dep["members"]:
            require(relative(path) in known and known[path].role == "dependency",
                    "typed dependency member is outside canonical dependency closure")
        text(dep["selected_version"])
        text(dep["version_constraint"])
        dependencies.append(dep)
    require(isinstance(spec["unresolved_inputs"], list) and
            all(isinstance(item, str) and item for item in spec["unresolved_inputs"]),
            "explicit unresolved input inventory required")
    mapped = {p for d in dependencies for p in d["members"]}
    require(mapped == {m.path for m in manifest.members if m.role == "dependency"},
            "canonical dependency members require complete typed build/runtime edges")
    build_dependencies = {p for d in dependencies if d["kind"] == "build" for p in d["members"]}
    # The profile file itself contains worker/test/release policy provenance.
    # Project its build semantics separately; do not key compilation on those policies.
    sources = [m.to_dict() for m in manifest.members if m.path != spec["profile"]["path"]
               and (m.role != "dependency" or m.path in build_dependencies)]
    tools = [{"name": n, "path": p, "identity": i.uri} for n, p, i in profile.tools]
    build = {"schema": "daemonarchy/retained-build-inputs@1", "target": profile.target,
             "members": sources, "actions": [a.to_dict() for a in profile.actions
                                                if a.stage in {"acquire", "stage", "generate", "build"}],
             "tools": tools, "toolchain": profile.toolchain_identity.uri,
             "compiler": spec["compiler"], "sysroot": spec["sysroot"],
             "execution_identity": spec["execution_identity"], "options": spec["options"],
             "flavor": spec["flavor"], "generated_inputs": sorted(generated, key=lambda e: e["path"]),
             "build_dependencies": sorted([{"unit": d["unit"], "identity": d["identity"]}
                                            for d in dependencies if d["kind"] == "build"], key=lambda e: e["unit"])}
    if base["kernel_bound"]:
        build["base_abi"] = base
    runtime = {"base_abi": base, "dependencies": sorted(dependencies, key=lambda d: (d["unit"], d["kind"])),
               "dependency_members": [m.to_dict() for m in manifest.members if m.role == "dependency"]}
    return {"id": name, "repository": repository, "manifest_identity": manifest.identity.uri,
            "profile_identity": profile.identity.uri, "build_inputs": build,
            "build_inputs_identity": canonical_identity(build).uri,
            "qualification_inputs": runtime, "qualification_inputs_identity": canonical_identity(runtime).uri,
            "dependencies": runtime["dependencies"], "unresolved_inputs": spec["unresolved_inputs"],
            "admitted": False, "native_receipt": None,
            "remaining_gates": ["registered-component-ownership", "producer-closure-observation",
                                "retained-native-admission", "verified-output-and-ABI-qualification"]}


def collect(selection, paths, retained_roots=None):
    retained_roots = retained_roots or {}
    fields(selection, "schema repositories units")
    require(selection["schema"] == SCHEMA, "unknown release input selection schema")
    require(isinstance(selection["repositories"], list) and selection["repositories"], "select repositories")
    repos = {}
    for spec in selection["repositories"]:
        name = spec.get("id")
        require(name not in repos and name in paths, "duplicate repository or missing local object store")
        repos[name] = lock_repository(spec, paths[name])
    require(set(paths) == set(repos), "unselected repository object store")
    require(isinstance(selection["units"], list), "unit inventory required")
    units = {}
    for spec in selection["units"]:
        unit = unit_record(spec, repos, paths, retained_roots.get(spec.get("id")))
        require(unit["id"] not in units, "duplicate unit")
        units[unit["id"]] = unit
    require(set(retained_roots) <= set(units), "unselected retained root")
    pending, order = set(units), []
    for unit in units.values():
        require(all(d["unit"] in units for d in unit["dependencies"]), "incomplete cross-repository dependency closure")
    while pending:
        ready = sorted(n for n in pending if all(d["unit"] not in pending for d in units[n]["dependencies"]
                                                if d["kind"] == "build"))
        require(ready, "build dependency cycle")
        order.extend(ready)
        pending.difference_update(ready)
    return {"schema": "daemonarchy/release-input-graph@1", "repositories": [repos[n] for n in sorted(repos)],
            "units": [units[n] for n in sorted(units)], "build_dependency_order": order,
            "admitted": False, "acceptance": "not-qualified", "selection_identity": canonical_identity(selection).uri,
            "gaps": ([] if units else ["no retained per-unit producer profiles selected"])}


def compare(previous, current):
    """Conservative pre-scheduling recommendations; never cache-hit authorization."""
    old = {u["id"]: u for u in previous["units"]}
    new = {u["id"]: u for u in current["units"]}
    decisions = {}
    for name in sorted(old.keys() | new.keys()):
        if name not in new:
            reason = "removed"
        elif name not in old:
            reason = "new-unit"
        elif new[name]["unresolved_inputs"]:
            reason = "unresolved-inputs-repair-before-reuse"
        elif old[name]["build_inputs_identity"] != new[name]["build_inputs_identity"]:
            reason = "build-inputs-changed"
        elif old[name]["qualification_inputs_identity"] != new[name]["qualification_inputs_identity"]:
            reason = "native-ABI-requalification-required"
        else:
            reason = "unchanged-inputs-verify-retained-products"
        decisions[name] = reason
    # A changed producer's unknown output cannot be silently reused by consumers.
    for name in current["build_dependency_order"]:
        if any(decisions[d["unit"]] in {"new-unit", "build-inputs-changed", "build-dependency-output-unproven",
                                          "unresolved-inputs-repair-before-reuse"}
               for d in new[name]["dependencies"] if d["kind"] == "build"):
            decisions[name] = "build-dependency-output-unproven"
    return {"schema": "daemonarchy/release-input-comparison@1", "cache_admission": False,
            "decisions": [{"unit": n, "reason": decisions[n]} for n in sorted(decisions)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("selection", type=Path)
    parser.add_argument("--repo", action="append", default=[], metavar="ID=OBJECT_STORE")
    parser.add_argument("--retained-root", action="append", default=[], metavar="UNIT=SNAPSHOT")
    parser.add_argument("--previous", type=Path, help="previous exact graph for conservative comparison")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        paths = {}
        for binding in args.repo:
            name, path = binding.split("=", 1)
            require(name not in paths, "duplicate repository binding")
            paths[name] = Path(path).resolve(strict=True)
        roots = {}
        for binding in args.retained_root:
            name, path = binding.split("=", 1)
            require(name not in roots, "duplicate retained snapshot binding")
            roots[name] = Path(path).resolve(strict=True)
        report = collect(document(args.selection.read_bytes()), paths, roots)
        output = args.output.resolve()
        require(all(not output.is_relative_to(root) for root in (*paths.values(), *roots.values())),
                "write graph evidence outside inspected input repositories and snapshots")
        if args.previous is not None:
            report["comparison"] = compare(document(args.previous.read_bytes()), report)
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(json.dumps({"output_sha256": digest(args.output.read_bytes()), "admitted": False}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("release input graph refused: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
