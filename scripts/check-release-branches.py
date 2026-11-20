#!/usr/bin/env python3
"""Audit owned main versus release tips; optional refresh never changes worktrees."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def git(repo, *args, input=None):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], input=input, text=True).strip()


def exception(repo, commit, branch):
    message = git(repo, "show", "-s", "--format=%B", commit)
    trailers = git(repo, "interpret-trailers", "--parse", input=message)
    versions = re.findall(r"^Daemonarchy-Release-Only: (.+)$", trailers, re.M)
    reasons = re.findall(r"^Daemonarchy-No-Forward-Port: (.+)$", trailers, re.M)
    version = branch.removeprefix("release/").removeprefix("daemonarchy-")
    if not versions and not reasons:
        return None
    if (versions != [version] or len(reasons) != 1 or
            len(reasons[0].strip()) < 20 or
            not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.(?:[0-9]+|x))?", version)):
        raise ValueError(f"invalid release-only trailers: {branch} {commit}")
    return reasons[0]


def inspect(repo, prefix, required, legacy=()):
    refs = dict(line.split(" ", 1) for line in git(
        repo, "for-each-ref", "--format=%(refname) %(objectname)", prefix).splitlines())
    main = refs.get(prefix + "main")
    if not main or prefix + required not in refs:
        raise ValueError("main and " + required + " must both exist")
    branches = sorted(ref.removeprefix(prefix) for ref in refs
                      if ref.startswith(prefix + "release/") or
                      ref.removeprefix(prefix) in legacy)
    result = {"main": main, "branches": [], "ok": True}
    for branch in branches:
        tip = refs[prefix + branch]
        missing = git(repo, "rev-list", tip, "--not", main).splitlines()
        row = {"branch": branch, "tip": tip, "missing": [], "exceptions": [],
               "patch_equivalent": [], "unresolved_merge_commits": []}
        if missing:
            # Proved containment needs no older history. Divergent shallow refs
            # cannot establish patch equivalence or complete exception coverage.
            if git(repo, "rev-parse", "--is-shallow-repository") == "true":
                raise ValueError("complete divergent histories required; shallow repository refused")
            # git cherry compares actual patches, including cherry-picked backports.
            for line in git(repo, "cherry", main, tip).splitlines():
                sign, commit = line.split()
                if sign == "-":
                    row["patch_equivalent"].append(commit)
                else:
                    reason = exception(repo, commit, branch)
                    if reason:
                        row["exceptions"].append({"commit": commit, "reason": reason})
                    else:
                        row["missing"].append(commit)
            # Cherry ignores merges. A merge with its own conflict resolution needs
            # review even when its parents' patches were forwarded separately.
            for commit in git(repo, "rev-list", "--merges", tip, "--not", main).splitlines():
                if git(repo, "show", "--format=", "--cc", commit):
                    reason = exception(repo, commit, branch)
                    if reason:
                        row["exceptions"].append({"commit": commit, "reason": reason})
                    else:
                        row["unresolved_merge_commits"].append(commit)
            if row["missing"] or row["unresolved_merge_commits"]:
                result["ok"] = False
        result["branches"].append(row)
    return result


def github_contained(name, required, legacy=()):
    """Cheap ancestry fast path; divergence falls back to the local patch audit."""
    def api(path, *args):
        return json.loads(subprocess.check_output(["gh", "api", *args,
                          "repos/jordanhubbard/" + name + "/" + path], text=True))
    pages = api("branches?per_page=100", "--paginate", "--slurp")
    refs = {row["name"]: row["commit"]["sha"] for page in pages for row in page}
    if "main" not in refs or required not in refs:
        raise ValueError("main and " + required + " must both exist")
    rows = []
    for branch, tip in sorted(refs.items()):
        if not (branch.startswith("release/") or branch in legacy):
            continue
        contained = tip == refs["main"]
        if not contained:
            compare = api("compare/" + refs["main"] + "..." + tip + "?per_page=1")
            contained = compare["status"] in ("identical", "behind")
        rows.append({"branch": branch, "tip": tip, "contained": contained})
    return {"main": refs["main"], "branches": rows,
            "ok": all(row["contained"] for row in rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "release/branches.json")
    parser.add_argument("--repo", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--prefix", default="refs/remotes/origin/")
    parser.add_argument("--only", help="Audit one configured repository")
    parser.add_argument("--refresh", action="store_true",
                        help="Fetch owned main/release refs into a dedicated audit namespace")
    parser.add_argument("--github-contained", action="store_true",
                        help="Ancestry fast path via public GitHub API; divergence needs local audit")
    args = parser.parse_args()
    try:
        if args.refresh and not args.prefix.startswith("refs/daemonarchy-release-audit/"):
            raise ValueError("--refresh requires --prefix refs/daemonarchy-release-audit/")
        config = json.loads(args.config.read_text())
        if config["schema"] != "daemonarchy/release-branches@1":
            raise ValueError("unsupported branch policy")
        bindings = dict(item.split("=", 1) for item in args.repo)
        names = [args.only] if args.only else list(config["repositories"])
        if args.only and args.only not in config["repositories"]:
            raise ValueError("unknown repository")
        results = {}
        for name in names:
            legacy = config["repositories"][name].get("legacy_release_branches", [])
            if args.github_contained:
                results[name] = github_contained(name, config["release_branch"], legacy)
            else:
                if args.refresh:
                    refspecs = ["+refs/heads/main:" + args.prefix + "main",
                                "+refs/heads/release/*:" + args.prefix + "release/*"]
                    refspecs.extend("+refs/heads/" + ref + ":" + args.prefix + ref for ref in legacy)
                    subprocess.run(["git", "-C", bindings[name], "fetch", "--no-tags",
                                    "https://github.com/jordanhubbard/" + name + ".git",
                                    *refspecs], check=True)
                results[name] = inspect(bindings[name], args.prefix, config["release_branch"], legacy)
        print(json.dumps({"schema": "daemonarchy/release-branch-audit@1",
                          "repositories": results, "ok": all(r["ok"] for r in results.values())}, indent=2))
        return 0 if all(r["ok"] for r in results.values()) else 1
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"release branch audit refused: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
