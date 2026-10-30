#!/usr/bin/env python3
"""package-feed-stage: archive checks, GitHub-safe names, manifests, verification and the publish plan."""

import hashlib
import importlib.machinery
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("stage", str(ROOT / "scripts/package-feed-stage.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
tool = importlib.util.module_from_spec(spec)
loader.exec_module(tool)

PACKAGES = {"bash": ("5.3.9", b"bash-archive"), "ffmpeg": ("9.0.2_3,1", b"ffmpeg-archive-bytes"), "zstd": ("1.5.7_2", b"z")}


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cache, self.out = self.root / "cache", self.root / "out"
        self.cache.mkdir()
        hosted = []
        for name, (version, data) in PACKAGES.items():
            real = self.cache / f"{name}-{version}~2$hash.pkg"
            real.write_bytes(data)
            (self.cache / f"{name}-{version}.pkg").symlink_to(real.name)
            # pkg's checksum is "2$<base32 blake2>", not a SHA-256; the tool treats it as opaque.
            hosted.append({"name": name, "version": version, "sum": f"2${name}opaque",
                           "pkgsize": len(data), "path": f"All/Hashed/{name}.pkg"})
        self.plan = {"hosted": hosted, "shards": [{"assets": 3, "bytes": 0, "packages": sorted(PACKAGES)}]}
        self.prefix = "packages-16-amd64-9.9.9-upstream"

    def stage(self, **kw):
        return tool.stage(self.plan, self.cache, self.out, self.prefix, **kw)

    def close(self):
        self.tmp.cleanup()


def with_fixture(test):
    def wrapper(self):
        f = Fixture()
        self.addCleanup(f.close)
        test(self, f)
    return wrapper


class StageTests(unittest.TestCase):
    @with_fixture
    def test_stage_copies_verified_archives_under_github_safe_names(self, f):
        manifests = f.stage()
        self.assertEqual([m.name for m in manifests], [f"{f.prefix}.manifest.json"])
        names = sorted(p.name for p in (f.out / f.prefix).iterdir())
        self.assertEqual(names, ["bash-5.3.9.pkg", "ffmpeg-9.0.2_3.1.pkg", "zstd-1.5.7_2.pkg"])
        self.assertEqual(tool.verify(f.out / f.prefix), [])

    @with_fixture
    def test_a_corrupt_or_missing_archive_stops_staging(self, f):
        (f.cache / "bash-5.3.9~2$hash.pkg").write_bytes(b"tampered-archive")
        with self.assertRaisesRegex(ValueError, "bash-5.3.9"):
            f.stage()
        f2 = Fixture()
        self.addCleanup(f2.close)
        (f2.cache / "zstd-1.5.7_2.pkg").unlink()
        with self.assertRaisesRegex(ValueError, "not in the cache"):
            f2.stage()

    @with_fixture
    def test_verify_catches_tampering_extras_and_missing_assets(self, f):
        f.stage()
        shard = f.out / f.prefix
        (shard / "bash-5.3.9.pkg").write_bytes(b"x")
        (shard / "extra.pkg").write_bytes(b"x")
        (shard / "zstd-1.5.7_2.pkg").unlink()
        problems = "\n".join(tool.verify(shard))
        self.assertIn("bash-5.3.9.pkg: size differs", problems)
        self.assertIn("unlisted asset extra.pkg", problems)
        self.assertIn("missing asset zstd-1.5.7_2.pkg", problems)

    @with_fixture
    def test_catalogue_must_name_exactly_the_staged_packages(self, f):
        f.stage()
        shard = f.out / f.prefix
        rows = [{"name": n, "version": v, "sum": f"2${n}opaque"} for n, (v, d) in PACKAGES.items()]

        def catalogue(entries):
            (shard / "packagesite.yaml").write_text("".join(json.dumps(r) + "\n" for r in entries))
            subprocess.run(["tar", "-cf", str(shard / "packagesite.pkg"), "-C", str(shard), "packagesite.yaml"], check=True)
            (shard / "packagesite.yaml").unlink()
            tool.write_manifest(f.out, f.prefix, shard, sorted(PACKAGES))   # keeps the upstream sums
            return "\n".join(tool.verify(shard))

        self.assertEqual(catalogue(rows), "")
        self.assertIn("does not name exactly", catalogue(rows[:2]))
        altered = [dict(rows[0], sum="2$different")] + rows[1:]
        self.assertIn("differs from the upstream catalogue", catalogue(altered))

    @with_fixture
    def test_publish_plan_is_text_only_with_packages_before_catalogue(self, f):
        f.stage()
        shard = f.out / f.prefix
        (shard / "packagesite.pkg").write_bytes(b"catalogue")
        tool.write_manifest(f.out, f.prefix, shard, sorted(PACKAGES))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            plan = tool.publish_plan(f.out, "owner/repo")
        commands = plan["commands"]
        self.assertTrue(commands[0].startswith(f"gh release create {f.prefix} -R owner/repo --latest=false"))
        self.assertLess(max(i for i, c in enumerate(commands) if "zstd-1.5.7_2.pkg" in c),
                        min(i for i, c in enumerate(commands) if c.endswith("packagesite.pkg")))
        self.assertIn("this plan was not executed", plan["notes"])
        self.assertTrue((f.out / "publish-plan.json").exists())

    @with_fixture
    def test_record_entries_are_what_the_release_verifier_accepts(self, f):
        f.stage()
        shard = f.out / f.prefix
        (shard / "data.pkg").write_bytes(b"d")
        (shard / "meta.conf").write_bytes(b"c")
        tool.write_manifest(f.out, f.prefix, shard, sorted(PACKAGES))
        entries = tool.closure_record(f.out)
        self.assertEqual(entries[0]["tag"], f.prefix)
        self.assertEqual(entries[0]["assets"]["bash-5.3.9.pkg"][0], len(PACKAGES["bash"][1]))
        self.assertTrue(entries[0]["assets"]["bash-5.3.9.pkg"][1].startswith("sha256:"))
        verifier_loader = importlib.machinery.SourceFileLoader("v", str(ROOT / "scripts/verify-release-assets.py"))
        verifier_spec = importlib.util.spec_from_loader(verifier_loader.name, verifier_loader)
        verifier = importlib.util.module_from_spec(verifier_spec)
        verifier_loader.exec_module(verifier)
        record = {"version": "1.4.1", "closure_feeds": entries}
        self.assertEqual(list(verifier.closure_feeds(record)), [f.prefix])

    def test_tag_prefix_and_existing_output_are_validated(self):
        with self.assertRaises(ValueError):
            tool.shard_tags("latest", 1)
        self.assertEqual(tool.shard_tags("packages-16-amd64-1.4.1-x", 2), ["packages-16-amd64-1.4.1-x-1", "packages-16-amd64-1.4.1-x-2"])
        f = Fixture()
        self.addCleanup(f.close)
        f.stage()
        with self.assertRaisesRegex(ValueError, "already exists"):
            f.stage()


class RecordedFeeds(unittest.TestCase):
    def test_every_recorded_feed_is_valid_and_matches_its_file_name(self):
        verifier_loader = importlib.machinery.SourceFileLoader("v2", str(ROOT / "scripts/verify-release-assets.py"))
        verifier_spec = importlib.util.spec_from_loader(verifier_loader.name, verifier_loader)
        verifier = importlib.util.module_from_spec(verifier_spec)
        verifier_loader.exec_module(verifier)
        records = sorted((ROOT / "verification/closure-feeds").glob("*.json"))
        self.assertTrue(records)
        for path in records:
            entries = json.loads(path.read_text())
            arch = path.stem.split("-")[2]          # packages-16-<arch>-<version>-upstream
            feeds = verifier.closure_feeds({"version": "1.4.1", "architectures": [arch], "closure_feeds": entries})
            self.assertEqual(list(feeds), [path.stem], path.name)
            assets = feeds[path.stem]
            self.assertLessEqual(len(assets), 1000)
            self.assertTrue(all(name.endswith(".pkg") or name in ("meta", "meta.conf") for name in assets))
            self.assertTrue(all(entry[0] < 2 * 2**30 for entry in assets.values()), "an asset exceeds GitHub's 2 GiB limit")


if __name__ == "__main__":
    unittest.main()
