#!/usr/bin/env python3
"""Lock owned Git inputs and project canonical retained profiles into a review graph.

Read-only adapter: it neither schedules actions nor authorizes cache reuse. Native
producer observations, registered ownership and lifecycle admission remain required.
Run with the project's matching installed Literate AI interpreter.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from literate_ai.adapters.retained_project_inputs import verify_retained_project_inputs
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.retained_component_ownership import retained_owner
from literate_ai.contracts.retained_project import RetainedProjectManifest
from literate_ai.contracts.retained_project_lifecycle import RetainedProjectProfile

SCHEMA = "daemonarchy/release-input-selection@1"
GRAPH_SCHEMA = "daemonarchy/release-input-graph@1"
CHANGED = {"new-unit", "build-inputs-changed", "build-dependency-output-unproven",
           "unresolved-inputs-repair-before-reuse"}
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


def write_report(path, report):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(descriptor,"w") as stream:
        json.dump(report,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write("\n")


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
        git(repo, "merge-base", "--is-ancestor", upstream, revision)
        base = upstream
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
    owners = {o.prefix: o for o in manifest.component_ownership}
    member_owners = {}
    for member in manifest.members:
        owner = retained_owner(member.path, owners)
        require(owner is not None, "retained member has no canonical Component owner: " + member.path)
        member_owners[member.path] = (owner.component.uri, owner.authoring_identity.uri, member.sha256)
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
        fields(entry, "path sha256 producer output")
        member = known.get(relative(entry["path"]))
        require(member is not None and member.sha256 == entry["sha256"],
                "generated input must be in retained byte closure")
        generated.append({**entry, "producer": text(entry["producer"]), "output": relative(entry["output"])})
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
    providers = {}
    for dep in dependencies:
        for path in dep["members"]:
            require(providers.setdefault(path, dep["unit"]) == dep["unit"],
                    "ambiguous dependency edge: member has several producer units: " + path)
    mapped = set(providers)
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
                                "retained-native-admission", "verified-output-and-ABI-qualification"]}, member_owners


def collect(selection, paths, retained_roots=None):
    retained_roots = retained_roots or {}
    # The report must be an immutable snapshot, never aliasing caller selection values.
    selection = copy.deepcopy(selection)
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
    units, claimed = {}, {}
    for spec in selection["units"]:
        unit, member_owners = unit_record(spec, repos, paths, retained_roots.get(spec.get("id")))
        require(unit["id"] not in units, "duplicate unit")
        units[unit["id"]] = unit
        # One selected repository path has one canonical owner and one locked byte
        # identity across every unit; two retained closures cannot disagree.
        for path, owner in member_owners.items():
            previous = claimed.setdefault((unit["repository"], path), owner)
            require(previous == owner, "ambiguous cross-unit owner or bytes for input: " + path)
    require(set(retained_roots) <= set(units), "unselected retained root")
    pending, order = set(units), []
    for unit in units.values():
        require(all(d["unit"] in units for d in unit["dependencies"]), "incomplete cross-repository dependency closure")
        for generated in unit["build_inputs"]["generated_inputs"]:
            provider, separator, action_id = generated["producer"].partition("#")
            require(separator and provider in units, "generated input names a missing producer unit")
            actions = {a["id"]: a for a in units[provider]["build_inputs"]["actions"]}
            require(action_id in actions and any(generated["output"] == output or
                    generated["output"].startswith(output + "/") for output in actions[action_id]["outputs"]),
                    "generated input names an undeclared producer output")
            require(provider == unit["id"] or any(d["unit"] == provider and d["kind"] == "build"
                    for d in unit["dependencies"]), "generated cross-unit input requires a build edge")
    while pending:
        ready = sorted(n for n in pending if all(d["unit"] not in pending for d in units[n]["dependencies"]
                                                if d["kind"] == "build"))
        require(ready, "build dependency cycle")
        order.extend(ready)
        pending.difference_update(ready)
    return {"schema": GRAPH_SCHEMA, "repositories": [repos[n] for n in sorted(repos)],
            "units": [units[n] for n in sorted(units)], "build_dependency_order": order,
            "admitted": False, "acceptance": "not-qualified", "selection_identity": canonical_identity(selection).uri,
            "gaps": ([] if units else ["no retained per-unit producer profiles selected"])}


def project_action_trace(manifest, profile, action_id, trace, bindings):
    """Project actual scoped accesses; missing trace/byte authority never admits reuse.

    Bindings map native absolute roots to canonical retained path prefixes. They
    resolve ownership only: command/cwd paths are preserved verbatim in the key.
    This makes packaging-only read changes separable without inferring usage from
    plist/install-script names or from whole port-tree equality.
    """
    require(isinstance(manifest, RetainedProjectManifest) and isinstance(profile, RetainedProjectProfile),
            "canonical retained manifest/profile required")
    require(trace.get("schema") == "daemonarchy/source-action-trace-observation@1" and
            trace.get("scope") in {"compile", "link", "generate", "package"}, "scoped filemon facts required")
    require(isinstance(trace.get("commands"),list) and trace["commands"] and
            all(isinstance(c,str) and c for c in trace["commands"]), "actual command records required")
    identity("sha256:"+trace["meta_sha256"])
    require(Path(trace["cwd"]).is_absolute(), "actual command cwd required")
    actions = {a.action_id:a for a in profile.actions}
    require(action_id in actions, "trace action is absent from current canonical profile")
    by_path = {m.path:m for m in manifest.members}
    owners = {o.prefix:o for o in manifest.component_ownership}
    require(owners, "canonical retained input ownership required")
    roots=[]
    for native, prefix in bindings.items():
        require(isinstance(native,str) and Path(native).is_absolute(), "native ownership root must be absolute")
        require(prefix == "" or relative(prefix), "canonical ownership prefix required")
        roots.append((Path(native),prefix))
    roots.sort(key=lambda pair:len(pair[0].parts),reverse=True)
    selected=set()
    unresolved=list(trace.get("unresolved_inputs",[]))
    for access in trace.get("input_accesses",[]):
        path=Path(access["path"])
        if not path.is_absolute():
            unresolved.append({"input":str(path),"reason":"relative/dirfd access ownership not proved"})
            continue
        match=next(((native,prefix) for native,prefix in roots if path.is_relative_to(native)),None)
        if match is None:
            unresolved.append({"input":str(path),"reason":"native access has no retained ownership binding"})
            continue
        native,prefix=match
        name=(PurePosixPath(prefix)/path.relative_to(native).as_posix()).as_posix()
        if name not in by_path:
            unresolved.append({"input":name,"reason":"accessed file/directory is outside sealed member inventory"})
            continue
        selected.add(name)
    require(selected, "trace has no byte-owned canonical input members")
    pending=list(selected)
    while pending:
        member=by_path[pending.pop()]
        target=member.symlink_destination
        if target is not None:
            require(target in by_path,"trace symlink target is outside retained closure")
            if target not in selected:
                selected.add(target)
                pending.append(target)
    selected_roots=tuple(root for root in manifest.roots if any(n==root or n.startswith(root+"/") for n in selected))
    directories=tuple(d for d in manifest.directories if any(n.startswith(d+"/") for n in selected))
    nodes=selected|set(directories)
    selected_owners={retained_owner(n,owners).prefix for n in nodes if retained_owner(n,owners) is not None}
    sliced=RetainedProjectManifest(selected_roots,tuple(by_path[n] for n in sorted(selected)),manifest.limits,
                                  directories,tuple(owners[n] for n in sorted(selected_owners)),manifest.tree_policy)
    if trace.get("environment_identity") is None:
        unresolved.append({"reason":"actual command environment was not captured/admitted"})
    facts={"schema":"daemonarchy/traced-action-inputs@1","phase":trace["scope"],"target":profile.target,
           "commands":trace["commands"],"cwd":trace["cwd"],"target_output":trace["target"],
           "environment_identity":trace.get("environment_identity"),"members":[m.to_dict() for m in sliced.members],
           "member_owners":[o.to_dict() for o in sliced.component_ownership],
           "tools":[{"name":n,"path":p,"identity":i.uri} for n,p,i in profile.tools if p in selected]}
    return {"schema":"daemonarchy/traced-action-input-projection@1","action_id":action_id,
            "source_manifest_identity":manifest.identity.uri,"profile_identity":profile.identity.uri,
            "trace_identity":"sha256:"+trace["meta_sha256"],"action_manifest":sliced.to_dict(),
            "projected_inputs":facts,"projected_inputs_identity":canonical_identity(facts).uri,
            "unresolved_inputs":unresolved,"cache_admission":False,"native_receipt":None,
            "remaining_gates":["trusted complete native action trace coverage", "current sealed input/owner admission",
                               "trace environment/ignore/path policy", "generated/output producer and native qualification receipts"]}


def graph_units(report):
    """Re-derive each unit's typed identities; a recorded identity alone is not evidence."""
    require(isinstance(report, dict) and report.get("schema") == GRAPH_SCHEMA and
            isinstance(report.get("units"), list), "typed release input graph required")
    units = {}
    for unit in report["units"]:
        require(isinstance(unit, dict) and isinstance(unit.get("id"), str) and unit["id"] not in units,
                "graph units must have unique ids")
        require(unit["build_inputs_identity"] == canonical_identity(unit["build_inputs"]).uri and
                unit["qualification_inputs_identity"] == canonical_identity(unit["qualification_inputs"]).uri and
                unit["dependencies"] == unit["qualification_inputs"]["dependencies"],
                "graph unit identity differs from its typed inputs: " + unit["id"])
        units[unit["id"]] = unit
    for unit in units.values():
        require(all(d["unit"] in units for d in unit["dependencies"]),
                "graph has an unknown dependency edge: " + unit["id"])
    return units


def compare(previous, current):
    """Conservative pre-scheduling recommendations; never cache-hit authorization."""
    old = graph_units(previous)
    new = graph_units(current)
    require(current.get("build_dependency_order") is not None and
            set(current["build_dependency_order"]) == set(new), "current build order must cover its units")
    decisions = {}
    for name in sorted(old.keys() | new.keys()):
        if name not in new:
            reason = "removed"
        elif name not in old:
            reason = "new-unit"
        elif new[name]["unresolved_inputs"] or old[name]["unresolved_inputs"]:
            # A previous output built with an open closure was never proved reusable.
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
        if any(decisions[d["unit"]] in CHANGED
               for d in new[name]["dependencies"] if d["kind"] == "build"):
            decisions[name] = "build-dependency-output-unproven"
    # Runtime edges may be cyclic. A changed or requalifying producer leaves its
    # runtime consumers' installed behavior unproven, so they cannot keep an
    # unchanged recommendation even when their own declared inputs are equal.
    changed = True
    while changed:
        changed = False
        for name in sorted(new):
            if decisions[name] == "unchanged-inputs-verify-retained-products" and any(
                    decisions[d["unit"]] in CHANGED | {"native-ABI-requalification-required"}
                    for d in new[name]["dependencies"] if d["kind"] == "runtime"):
                decisions[name] = "native-ABI-requalification-required"
                changed = True
    return {"schema": "daemonarchy/release-input-comparison@1", "cache_admission": False,
            "decisions": [{"unit": n, "reason": decisions[n]} for n in sorted(decisions)]}


def compare_action_projections(previous, current):
    require(previous.get("schema")==current.get("schema")=="daemonarchy/traced-action-input-projection@1",
            "typed action projections required")
    require(previous["action_id"]==current["action_id"] and
            previous["projected_inputs"]["phase"]==current["projected_inputs"]["phase"],
            "compare the same canonical action and observed phase")
    for record in (previous,current):
        require(record["projected_inputs_identity"]==canonical_identity(record["projected_inputs"]).uri,
                "action projection content identity changed")
    phase=current["projected_inputs"]["phase"]
    if current["unresolved_inputs"]:
        reason="repair-incomplete-native-inputs-before-equivalence"
    elif previous["projected_inputs_identity"]==current["projected_inputs_identity"]:
        reason="verify-prior-payload-under-current-native-policy"
    elif phase=="package":
        reason="package-inputs-changed-repackage-and-requalify"
    else:
        reason=phase+"-inputs-changed"
    return {"schema":"daemonarchy/traced-action-comparison@1","phase":phase,"reason":reason,
            "cache_admission":False,"native_action_admission":False,
            "binary_input_adoption":"separate-policy-and-native-qualification-required"}


def trace_projection_main(argv):
    parser=argparse.ArgumentParser(description="Project scoped filemon accesses into canonical retained byte ownership")
    for name in ("manifest","profile","trace"):
        parser.add_argument("--"+name,type=Path,required=True)
        parser.add_argument("--"+name+"-sha256",required=True)
    parser.add_argument("--snapshot",type=Path,required=True)
    parser.add_argument("--previous",type=Path)
    parser.add_argument("--previous-sha256")
    parser.add_argument("--action",required=True)
    parser.add_argument("--bind",action="append",default=[],metavar="NATIVE_ROOT=RETAINED_PREFIX")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        records={}
        for name in ("manifest","profile","trace"):
            path=getattr(args,name)
            require(not path.is_symlink(),"record must be a regular direct file")
            with path.open("rb") as stream:
                data=stream.read(MAX_JSON+1)
            require(digest(data)==getattr(args,name+"_sha256"),"projection record digest changed")
            records[name]=document(data)
        manifest=RetainedProjectManifest.from_dict(records["manifest"])
        profile=RetainedProjectProfile.from_dict(records["profile"])
        snapshot=args.snapshot.resolve(strict=True)
        verify_retained_project_inputs(snapshot,manifest)
        profile_path=args.profile.resolve(strict=True).relative_to(snapshot).as_posix()
        require(any(m.path==profile_path and m.role=="build-definition" and m.sha256==args.profile_sha256
                    for m in manifest.members),"profile is outside the captured build-definition closure")
        require(profile.toolchain_identity==manifest.role_identity({"sdk","toolchain"}) and
                profile.dependency_identity==manifest.role_identity({"dependency"}),"profile role closure differs")
        bindings={}
        for binding in args.bind:
            native,prefix=binding.split("=",1)
            require(native not in bindings,"duplicate native root binding")
            bindings[native]=prefix
        report=project_action_trace(manifest,profile,args.action,records["trace"],bindings)
        if args.previous is not None:
            with args.previous.open("rb") as stream:
                previous=stream.read(MAX_JSON+1)
            require(args.previous_sha256 is not None and digest(previous)==args.previous_sha256,
                    "pin the previous action projection bytes")
            report["comparison"]=compare_action_projections(document(previous),report)
        output=args.output.absolute()
        require(output.parent.resolve(strict=True)==output.parent and not output.is_relative_to(snapshot),
                "projection evidence must be outside its sealed snapshot")
        write_report(output,report)
        print(json.dumps({"projected_inputs_identity":report["projected_inputs_identity"],"cache_admission":False}))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print("trace input projection refused: "+str(error),file=sys.stderr)
        return 1


def main():
    if sys.argv[1:2] == ["trace"]:
        return trace_projection_main(sys.argv[2:])
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
        write_report(args.output,report)
        print(json.dumps({"output_sha256": digest(args.output.read_bytes()), "admitted": False}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print("release input graph refused: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
