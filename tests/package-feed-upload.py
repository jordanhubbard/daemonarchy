#!/usr/bin/env python3
"""package-feed-upload: ordered, resumable, never-clobbering upload and an independent hash check (fake gh)."""

import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("upload", str(ROOT / "scripts/package-feed-upload.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
tool = importlib.util.module_from_spec(spec)
loader.exec_module(tool)

FAKE_GH = r'''#!/usr/bin/env python3
import hashlib, json, os, shutil, sys
store = os.environ["FAKE_STORE"]
a = sys.argv[1:]
def assets_dir(): os.makedirs(store + "/assets", exist_ok=True); return store + "/assets"
def log(line): open(store + "/log", "a").write(line + "\n")
if a[:2] == ["release", "view"]:
    sys.exit(0 if os.path.exists(store + "/release.json") else 1)
if a[:2] == ["release", "create"]:
    assert "--latest=false" in a, a
    json.dump({"id": 7, "tag_name": a[2], "draft": False}, open(store + "/release.json", "w"))
    log("create " + " ".join(a))
elif a[:2] == ["release", "upload"]:
    assert "--clobber" not in a, "must never clobber"
    name = os.path.basename(a[3]); log("upload " + name)
    fail = os.environ.get("FAKE_FAIL_ONCE", "").split()
    marker = store + "/failed-" + name
    if name in fail and not os.path.exists(marker):
        open(marker, "w").close()
        open(assets_dir() + "/" + name, "wb").write(open(a[3], "rb").read()[:3])
        open(assets_dir() + "/" + name + ".state", "w").write("starter")
        sys.exit(1)
    if os.path.exists(assets_dir() + "/" + name):      # gh without --clobber refuses an existing asset
        sys.exit(1)
    shutil.copyfile(a[3], assets_dir() + "/" + name)
    open(assets_dir() + "/" + name + ".state", "w").write("uploaded")
elif a[:2] == ["release", "delete-asset"]:
    log("delete " + a[3])
    for suffix in ("", ".state"):
        p = assets_dir() + "/" + a[3] + suffix
        if os.path.exists(p): os.remove(p)
elif a[0] == "api":
    path = a[1]
    if path.endswith("releases/latest"):
        print(json.dumps({"tag_name": os.environ.get("FAKE_LATEST", "daemonarchy-1.4.0"), "id": 99}))
    elif "/releases/tags/" in path:
        print(open(store + "/release.json").read())
    elif "/assets?" in path:
        page = int(path.rsplit("page=", 1)[1]); rows = []
        for n in sorted(x for x in os.listdir(assets_dir()) if not x.endswith(".state")):
            p = assets_dir() + "/" + n
            rows.append({"name": n, "size": os.path.getsize(p), "state": open(p + ".state").read(),
                         "digest": "sha256:" + hashlib.sha256(open(p, "rb").read()).hexdigest()})
        print(json.dumps(rows[(page - 1) * 100: page * 100]))
'''


class Fixture:
    def __init__(self, count=5, **env):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out, self.store = self.root / "out", self.root / "store"
        self.store.mkdir()
        self.tag = "packages-16-amd64-9.9.9-upstream"
        shard = self.out / self.tag
        shard.mkdir(parents=True)
        files = {f"p{n}-1.pkg": f"package {n}".encode() * 10 for n in range(count)}
        files.update({"data.pkg": b"catalogue data", "packagesite.pkg": b"catalogue site", "meta": b"m", "meta.conf": b"m"})
        assets = []
        for name, data in files.items():
            (shard / name).write_bytes(data)
            assets.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        (self.out / f"{self.tag}.manifest.json").write_text(json.dumps({"schema": "x", "tag": self.tag, "assets": assets}))
        gh = self.root / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        os.environ.update(GH=str(gh), FAKE_STORE=str(self.store), **env)

    def log(self):
        path = self.store / "log"
        return path.read_text().splitlines() if path.exists() else []

    def uploads(self):
        return [line.split()[1] for line in self.log() if line.startswith("upload")]

    def fetch(self, tamper=None):
        def fetch(url, destination):
            name = url.rsplit("/", 1)[1]
            source = self.store / "assets" / name
            if not source.exists():
                return False
            data = source.read_bytes()
            Path(destination).write_bytes(b"X" * len(data) if name == tamper else data)
            return True
        return fetch

    def close(self):
        for key in ("FAKE_FAIL_ONCE", "FAKE_LATEST"):
            os.environ.pop(key, None)
        self.tmp.cleanup()


def fixture(test):
    def wrapper(self):
        f = Fixture()
        self.addCleanup(f.close)
        test(self, f)
    return wrapper


class UploadTests(unittest.TestCase):
    @fixture
    def test_creates_a_non_latest_release_and_uploads_packages_before_the_catalogue(self, f):
        self.assertEqual(tool.upload(f.out, "o/r", workers=3, retries=3, sleep=lambda _: None), [])
        order = f.uploads()
        self.assertEqual(len(order), 9)
        self.assertTrue(set(order[:5]) == {f"p{n}-1.pkg" for n in range(5)})
        self.assertEqual(order[-1], "data.pkg")
        self.assertEqual(sum(line.startswith("create") for line in f.log()), 1)
        self.assertEqual(tool.verify(f.out, "o/r", fetch=f.fetch())[0], [])

    def test_a_failed_asset_is_retried_alone_and_its_partial_removed(self):
        f = Fixture(FAKE_FAIL_ONCE="p2-1.pkg")
        self.addCleanup(f.close)
        self.assertEqual(tool.upload(f.out, "o/r", workers=2, retries=3, sleep=lambda _: None), [])
        uploads = f.uploads()
        self.assertEqual(uploads.count("p2-1.pkg"), 2)
        self.assertTrue(all(uploads.count(n) == 1 for n in uploads if n != "p2-1.pkg"))
        self.assertEqual([line for line in f.log() if line.startswith("delete")], ["delete p2-1.pkg"])
        self.assertEqual(tool.verify(f.out, "o/r", fetch=f.fetch())[0], [])

    @fixture
    def test_running_again_resumes_without_uploading_anything(self, f):
        tool.upload(f.out, "o/r", sleep=lambda _: None)
        before = len(f.uploads())
        self.assertEqual(tool.upload(f.out, "o/r", sleep=lambda _: None), [])
        self.assertEqual(len(f.uploads()), before)

    @fixture
    def test_a_complete_asset_of_another_size_is_never_replaced(self, f):
        tool.upload(f.out, "o/r", sleep=lambda _: None)
        (f.out / f.tag / "p1-1.pkg").write_bytes(b"different length content here")
        manifest = json.loads((f.out / f"{f.tag}.manifest.json").read_text())
        for entry in manifest["assets"]:
            if entry["name"] == "p1-1.pkg":
                entry["bytes"] = 29
        (f.out / f"{f.tag}.manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError, "refusing to replace"):
            tool.upload(f.out, "o/r", sleep=lambda _: None)
        self.assertEqual(f.uploads().count("p1-1.pkg"), 2)   # one try, refused: no delete
        self.assertFalse(any(line == "delete p1-1.pkg" for line in f.log()))


class VerifyTests(unittest.TestCase):
    @fixture
    def test_independent_download_catches_a_changed_asset_and_a_latest_feed(self, f):
        tool.upload(f.out, "o/r", sleep=lambda _: None)
        problems, checked, total, latest = tool.verify(f.out, "o/r", fetch=f.fetch(tamper="p3-1.pkg"))
        self.assertEqual(checked, 9)
        self.assertTrue(any("p3-1.pkg" in p and "SHA-256 differs" in p for p in problems))
        self.assertEqual(latest, "daemonarchy-1.4.0")
        os.environ["FAKE_LATEST"] = f.tag
        self.assertTrue(any("non-latest" in p for p in tool.verify(f.out, "o/r", fetch=f.fetch())[0]))

    @fixture
    def test_missing_asset_and_failed_download_are_reported(self, f):
        tool.upload(f.out, "o/r", sleep=lambda _: None)
        (f.store / "assets" / "p0-1.pkg").unlink()
        (f.store / "assets" / "p0-1.pkg.state").unlink()
        problems = tool.verify(f.out, "o/r", fetch=f.fetch())[0]
        self.assertTrue(any("asset names differ" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
