#!/usr/bin/env python3
"""Stage the self-hosted package feed locally (PKG-002). Publishes nothing.

  package-feed-stage.py stage --plan PLAN.json --cache DIR --out DIR --tag-prefix TAG
                              [--signing-key KEY] [--pkg pkg]
  package-feed-stage.py verify --shard DIR [--manifest FILE]
  package-feed-stage.py publish-plan --out DIR [--repo OWNER/NAME]

PLAN.json is `package-mirror-plan.py --json`: its `hosted` rows name the upstream
packages the installer needs (name, version, SHA-256, archive size) and its
`shards` split them under GitHub's per-release limits. CACHE is a pkg cache
(`parallel-fetch` fills one) holding `name-version.pkg` for each of them.

`stage` checks every archive's size against the catalogue before copying it into
out/TAG/ under a name GitHub keeps (the comma of an epoch becomes a dot, as
pkg-repo.sh does), and, with --signing-key, builds the signed repository
catalogue with `pkg repo` so the shard is ready to upload. The catalogue's
`sum` is pkg's own checksum, not a SHA-256, so identity is proved a different
way: the checksums `pkg repo` computes from the staged archives must equal the
upstream catalogue's, which the manifest records. It writes out/TAG.manifest.json
(every asset's name, size and SHA-256, plus those upstream checksums; never part
of the upload) for each shard. The signing key is only ever passed to `pkg repo`.

`verify` re-checks a staged shard against its manifest and, when a catalogue is
present, that the catalogue names exactly the staged packages with the upstream
checksums, and that the asset count is within the release limit.

`publish-plan` writes out/publish-plan.json and prints the `gh` commands a
publish would run, packages before the catalogue that names them. It never runs
them: every tag is new (published tags are immutable) and nothing existing is
modified. The operator publishes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

SCHEMA = "daemonarchy/package-feed-shard@1"
MAX_ASSETS = 900          # GitHub allows 1000 per release; keep headroom for the catalogue files
CATALOGUE_FILES = ("meta", "meta.conf", "meta.pkg", "packagesite.pkg", "data.pkg")
TAG = re.compile(r"^packages-16-(amd64|aarch64)-[A-Za-z0-9._-]+$")


def asset_name(name, version):
    """GitHub renames assets with characters outside [A-Za-z0-9._-]; pkg finds a package by the catalogue path."""
    return re.sub(r"[^A-Za-z0-9._-]", ".", f"{name}-{version}.pkg")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def shard_tags(prefix, count):
    if not TAG.match(prefix):
        raise ValueError("tag prefix must look like packages-16-amd64-<version>[-label]")
    return [prefix] if count == 1 else [f"{prefix}-{n + 1}" for n in range(count)]


def stage(plan, cache, out, prefix, signing_key=None, pkg="pkg"):
    hosted = {row["name"]: row for row in plan["hosted"]}
    tags = shard_tags(prefix, len(plan["shards"]))
    out = Path(out)
    problems, manifests = [], []
    for tag, shard in zip(tags, plan["shards"]):
        directory = out / tag
        if directory.exists():
            raise ValueError(f"{directory} already exists; stage into a new directory")
        directory.mkdir(parents=True)
        seen = {}
        for name in shard["packages"]:
            row = hosted[name]
            source = (Path(cache) / f"{name}-{row['version']}.pkg").resolve()
            if not source.is_file():
                problems.append(f"{name}-{row['version']}: not in the cache")
                continue
            if row.get("pkgsize") and source.stat().st_size != row["pkgsize"]:
                problems.append(f"{name}-{row['version']}: size {source.stat().st_size} != catalogue {row['pkgsize']}")
                continue
            target = asset_name(name, row["version"])
            if target in seen:
                problems.append(f"{name}: asset name {target} collides with {seen[target]}")
                continue
            seen[target] = name
            shutil.copyfile(source, directory / target)
        if problems:
            continue
        if signing_key:
            result = subprocess.run([pkg, "repo", "-q", str(directory), str(signing_key)],
                                    capture_output=True, text=True)
            if result.returncode:
                problems.append(f"pkg repo failed for {tag}: {result.stderr.strip()[:300]}")
                continue
        sums = {name: hosted[name].get("sum", "") for name in shard["packages"]}
        path = write_manifest(out, tag, directory, sorted(shard["packages"]), sums)
        manifests.append(path)
        if signing_key:
            problems += [f"{tag}: {p}" for p in verify(directory, path)]
    if problems:
        raise ValueError("; ".join(problems))
    return manifests


def write_manifest(out, tag, directory, packages, upstream_sums=None):
    assets = [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha256_file(p)}
              for p in sorted(directory.iterdir()) if p.is_file()]
    previous = Path(out) / f"{tag}.manifest.json"
    if upstream_sums is None and previous.is_file():
        upstream_sums = json.loads(previous.read_text()).get("upstream_sums", {})
    manifest = {"schema": SCHEMA, "tag": tag, "packages": packages, "assets": assets,
                "catalogue": any(a["name"] == "packagesite.pkg" for a in assets),
                # pkg's own checksum of each archive in the upstream catalogue (not a SHA-256).
                "upstream_sums": upstream_sums or {}}
    path = Path(out) / f"{tag}.manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def catalogue_entries(path):
    text = subprocess.run(["tar", "-xOf", str(path), "packagesite.yaml"], check=True, capture_output=True, text=True).stdout
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def verify(directory, manifest_path=None):
    directory = Path(directory)
    manifest_path = Path(manifest_path) if manifest_path else directory.parent / f"{directory.name}.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    problems = []
    if manifest.get("schema") != SCHEMA:
        problems.append("unsupported manifest schema")
    listed = {a["name"]: a for a in manifest["assets"]}
    present = {p.name for p in directory.iterdir() if p.is_file()}
    problems += [f"missing asset {n}" for n in sorted(set(listed) - present)]
    problems += [f"unlisted asset {n}" for n in sorted(present - set(listed))]
    for name in sorted(set(listed) & present):
        path = directory / name
        if path.stat().st_size != listed[name]["bytes"]:
            problems.append(f"{name}: size differs from the manifest")
        elif sha256_file(path) != listed[name]["sha256"]:
            problems.append(f"{name}: SHA-256 differs from the manifest")
    if len(present) > MAX_ASSETS + len(CATALOGUE_FILES):
        problems.append(f"{len(present)} assets exceed the release limit")
    if (directory / "packagesite.pkg").is_file():
        entries = {e["name"]: e for e in catalogue_entries(directory / "packagesite.pkg")}
        if set(entries) != set(manifest["packages"]):
            problems.append("the catalogue does not name exactly the staged packages")
        # pkg computed these checksums from the staged archives; they must equal the
        # upstream catalogue's, which proves each archive is the byte-identical upstream one.
        upstream = manifest.get("upstream_sums", {})
        for name, entry in entries.items():
            if upstream.get(name) and entry.get("sum") != upstream[name]:
                problems.append(f"{name}: the staged archive's checksum differs from the upstream catalogue")
    return problems


def closure_record(out):
    """The release-inputs record's `closure_feeds` entries (scripts/verify-release-assets.py) for every staged shard."""
    entries = []
    for path in sorted(Path(out).glob("*.manifest.json")):
        manifest = json.loads(path.read_text())
        entries.append({"tag": manifest["tag"],
                        "assets": {a["name"]: [a["bytes"], "sha256:" + a["sha256"]] for a in manifest["assets"]}})
    return entries


def publish_plan(out, repo):
    out = Path(out)
    shards, commands = [], []
    for path in sorted(out.glob("*.manifest.json")):
        manifest = json.loads(path.read_text())
        tag, assets = manifest["tag"], manifest["assets"]
        packages = [a["name"] for a in assets if a["name"] not in CATALOGUE_FILES]
        catalogue = [a["name"] for a in assets if a["name"] in CATALOGUE_FILES]
        commands.append(f"gh release create {tag} -R {repo} --latest=false --title 'Daemonarchy upstream package mirror ({tag})' "
                        f"--notes 'Signed snapshot of the FreeBSD packages the installer needs. pkg uses it; nothing to download by hand.'")
        commands += [f"gh release upload {tag} -R {repo} {out / tag / name}" for name in packages]
        commands += [f"gh release upload {tag} -R {repo} {out / tag / name}" for name in catalogue]
        shards.append({"tag": tag, "packages": len(manifest["packages"]), "assets": len(assets),
                       "bytes": sum(a["bytes"] for a in assets), "signed_catalogue": manifest["catalogue"]})
    plan = {"repo": repo, "shards": shards,
            "notes": ["every tag is new; published tags are immutable and nothing existing is modified",
                      "packages upload before the catalogue that names them",
                      "this plan was not executed"],
            "commands": commands}
    (out / "publish-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--plan", required=True)
    s.add_argument("--cache", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--tag-prefix", required=True)
    s.add_argument("--signing-key")
    s.add_argument("--pkg", default="pkg")
    v = sub.add_parser("verify")
    v.add_argument("--shard", required=True)
    v.add_argument("--manifest")
    p = sub.add_parser("publish-plan")
    p.add_argument("--out", required=True)
    p.add_argument("--repo", default="jordanhubbard/daemonarchy")
    r = sub.add_parser("record", help="print the closure_feeds entries for the release-inputs record")
    r.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            plan = json.loads(Path(args.plan).read_text())
            manifests = stage(plan, args.cache, args.out, args.tag_prefix, args.signing_key, args.pkg)
            for manifest in manifests:
                print(f"staged {manifest}")
            return 0
        if args.command == "verify":
            problems = verify(args.shard, args.manifest)
            for problem in problems:
                print(problem, file=sys.stderr)
            print("shard verified" if not problems else f"{len(problems)} problem(s)")
            return 1 if problems else 0
        if args.command == "record":
            print(json.dumps(closure_record(args.out), indent=2))
            return 0
        plan = publish_plan(args.out, args.repo)
        print("\n".join(plan["commands"]))
        print(f"\n{len(plan['shards'])} shard(s); nothing was run. See {Path(args.out) / 'publish-plan.json'}.")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as error:
        print(f"package-feed-stage: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
