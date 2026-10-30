#!/usr/bin/env python3
"""Upload and verify a staged closure feed (PKG-002). The operator runs this.

  package-feed-upload.py upload --out DIR [--repo OWNER/NAME] [--workers 4] [--retries 5]
                                [--notes-file FILE]
  package-feed-upload.py verify --out DIR [--repo OWNER/NAME] [--workers 8]

DIR is what `package-feed-stage.py stage` wrote: one directory per shard tag and
its TAG.manifest.json. `upload` creates each release (non-latest, never replaced)
and uploads the packages, then the catalogue files, so a client never sees a
catalogue whose packages are missing. It can be run again to resume: an asset that
is already complete is left alone and a complete asset is never replaced, even if
it differs (that is an error). A failed upload is retried for that asset only,
with backoff; if it left a partial asset behind, only that partial asset is
deleted first.

`verify` checks that each release is published, not a draft and not the latest,
lists exactly the manifest's assets with their sizes and digests (paging through
GitHub's asset list), and then downloads every asset and compares its SHA-256 with
the manifest: an independent check of what GitHub serves.

Needs an authenticated `gh` (GH overrides the command) and curl for downloads.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

CATALOGUE_ORDER = ("meta", "meta.conf", "meta.pkg", "packagesite.pkg", "data.pkg")
LATEST_NOTE = "--latest=false"


def gh(*args, check=True):
    return subprocess.run([os.environ.get("GH", "gh"), *args], capture_output=True, text=True, check=check)


def api(path):
    return json.loads(gh("api", path).stdout)


def release_exists(repo, tag):
    return gh("release", "view", tag, "-R", repo, check=False).returncode == 0


def list_assets(repo, tag):
    """Every asset of the release, paging past GitHub's 100-per-page limit."""
    release = api(f"repos/{repo}/releases/tags/{tag}")
    assets, page = [], 1
    while True:
        chunk = api(f"repos/{repo}/releases/{release['id']}/assets?per_page=100&page={page}")
        assets += chunk
        if len(chunk) < 100:
            return release, {a["name"]: a for a in assets}
        page += 1


def manifests(out):
    return sorted(Path(out).glob("*.manifest.json"))


def upload_order(manifest):
    names = [a["name"] for a in manifest["assets"]]
    packages = sorted(n for n in names if n not in CATALOGUE_ORDER)
    return packages, [n for n in CATALOGUE_ORDER if n in names]


def upload_asset(repo, tag, directory, entry, retries, sleep=time.sleep):
    """Upload one asset, never clobbering; on failure retry just this asset."""
    name = entry["name"]
    for attempt in range(retries):
        result = gh("release", "upload", tag, str(Path(directory) / name), "-R", repo, check=False)
        if result.returncode == 0:
            return True        # `verify` re-checks every asset afterwards; no listing per upload
        _release, assets = list_assets(repo, tag)
        found = assets.get(name)
        if found and found.get("state") == "uploaded":
            if found.get("size") == entry["bytes"]:
                return True    # the upload landed although gh reported an error
            raise RuntimeError(f"{name}: a complete asset of a different size already exists; refusing to replace it")
        if found:               # a partial asset from this failed attempt: remove only it
            gh("release", "delete-asset", tag, name, "-R", repo, "-y", check=False)
        sleep(min(30, 2 ** attempt))
    return False


def upload(out, repo, workers=4, retries=5, notes_file=None, sleep=time.sleep):
    failures = []
    for path in manifests(out):
        manifest = json.loads(path.read_text())
        tag, directory = manifest["tag"], Path(out) / manifest["tag"]
        if not release_exists(repo, tag):
            args = ["release", "create", tag, "-R", repo, LATEST_NOTE,
                    "--title", f"Daemonarchy upstream package mirror ({tag})"]
            args += ["--notes-file", str(notes_file)] if notes_file else ["--notes", "Signed upstream package snapshot for the Daemonarchy installer."]
            gh(*args)
        _release, present = list_assets(repo, tag)
        by_name = {a["name"]: a for a in manifest["assets"]}
        packages, catalogue = upload_order(manifest)

        def pending(names):
            return [by_name[n] for n in names
                    if not (n in present and present[n].get("state") == "uploaded" and present[n].get("size") == by_name[n]["bytes"])]

        for batch, parallel in ((pending(packages), workers), (pending(catalogue), 1)):
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                results = list(pool.map(lambda e: (e["name"], upload_asset(repo, tag, directory, e, retries, sleep)), batch))
            failures += [f"{tag}/{name}" for name, ok in results if not ok]
            if failures:
                break    # never publish a catalogue ahead of missing packages
    return failures


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def curl_fetch(url, destination):
    return subprocess.run(["curl", "-sSfL", "--retry", "3", "-o", str(destination), url]).returncode == 0


def verify(out, repo, workers=8, fetch=curl_fetch):
    problems, checked, total = [], 0, 0
    latest = api(f"repos/{repo}/releases/latest")
    for path in manifests(out):
        manifest = json.loads(path.read_text())
        tag = manifest["tag"]
        release, assets = list_assets(repo, tag)
        if release.get("draft") is not False or release.get("id") == latest.get("id") or latest.get("tag_name") == tag:
            problems.append(f"{tag}: not a published, non-latest release")
        wanted = {a["name"]: a for a in manifest["assets"]}
        if set(assets) != set(wanted):
            problems.append(f"{tag}: asset names differ ({len(assets)} published, {len(wanted)} expected)")
        for name, entry in wanted.items():
            seen = assets.get(name)
            if seen and (seen.get("state") != "uploaded" or seen.get("size") != entry["bytes"]
                         or seen.get("digest") not in (None, "sha256:" + entry["sha256"])):
                problems.append(f"{tag}/{name}: size, state or digest differs from the manifest")
        with tempfile.TemporaryDirectory(prefix="closure-verify-") as tmp:
            def check(entry):
                target = Path(tmp) / entry["name"]
                url = f"https://github.com/{repo}/releases/download/{tag}/{entry['name']}"
                if not fetch(url, target):
                    return f"{tag}/{entry['name']}: download failed"
                actual = sha256_file(target)
                target.unlink()
                return None if actual == entry["sha256"] else f"{tag}/{entry['name']}: downloaded SHA-256 differs from the manifest"
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for result in pool.map(check, [wanted[n] for n in sorted(set(assets) & set(wanted))]):
                    checked += 1
                    if result:
                        problems.append(result)
        total += sum(a["bytes"] for a in manifest["assets"])
    return problems, checked, total, latest.get("tag_name")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("upload", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--out", required=True)
        s.add_argument("--repo", default="jordanhubbard/daemonarchy")
        s.add_argument("--workers", type=int, default=4 if name == "upload" else 8)
        if name == "upload":
            s.add_argument("--retries", type=int, default=5)
            s.add_argument("--notes-file")
    args = parser.parse_args(argv)
    if not manifests(args.out):
        print("package-feed-upload: no manifests in --out", file=sys.stderr)
        return 2
    if args.command == "upload":
        failures = upload(args.out, args.repo, args.workers, args.retries, args.notes_file)
        for failure in failures:
            print(f"failed: {failure}", file=sys.stderr)
        print("upload complete" if not failures else f"{len(failures)} asset(s) failed; run again to resume")
        return 1 if failures else 0
    problems, checked, total, latest = verify(args.out, args.repo, args.workers)
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"{checked} assets re-downloaded and hashed; {total} bytes expected; latest release is {latest}; "
          + ("verified" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
