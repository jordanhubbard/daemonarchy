#!/usr/bin/env python3
"""scripts/prepare-release.py and scripts/fill-release.py, end to end on a scratch tree.

The scratch tree is the repository's real release/current.json, closure feed records and the
1.4.2 notes template, plus stub prose files holding the tokens, so the whole draft-then-fill
flow of docs/mastering-1.4.2.md runs without GitHub, a build or a key.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/release-prepare/current-1.4.1.json"
SOURCE = "303b3646270ffa4bf7cec65c5c1d28bd8000cbce"
PORTS = "a" * 40
INSTALLER = "b" * 40
VERSION = "1.4.2"
FEEDS = {
    "--packages-amd64": "packages-16-amd64-1.4.2-r1", "--packages-aarch64": "packages-16-aarch64-1.4.2-r1",
    "--checkouts-amd64": "checkouts-16-amd64-1.4.2-r1", "--checkouts-aarch64": "checkouts-16-aarch64-1.4.2-r1",
}
PROSE = {
    "README.md": "Release @@PUBLISHED_DATE@@ x86 @@AMD64_ISO_BYTES@@ @@AMD64_ISO_SHA256@@ arm @@AARCH64_ISO_BYTES@@ @@AARCH64_ISO_SHA256@@\n",
    "HACKING.md": "ports @@PORTS_COMMIT@@\n",
    "PROJECT.md": "published @@PUBLISHED_DATE@@\n",
    "CHANGELOG.md": "## 1.4.2 (@@PUBLISHED_DATE@@)\n",
    "docs/aarch64.md": "@@AARCH64_FINAL_QEMU_STATUS@@\n",
}


def run(script, *args, root, check=True):
    env = dict(os.environ, DAEMONARCHY_RELEASE_ROOT=str(root))
    result = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / script), *args],
                            env=env, capture_output=True, text=True)
    if check and result.returncode:
        raise AssertionError(f"{script} failed: {result.stdout}{result.stderr}")
    return result


class PrepareAndFill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "tree"
        # The current record is a fixture (the 1.4.1 one), so the test keeps its meaning after 1.4.2 is published.
        (self.root / "release/templates").mkdir(parents=True)
        shutil.copy(FIXTURE, self.root / "release/current.json")
        shutil.copy(ROOT / "release/templates/release-1.4.2.md", self.root / "release/templates/release-1.4.2.md")
        shutil.copytree(ROOT / "verification/closure-feeds", self.root / "verification/closure-feeds")
        for relative, text in PROSE.items():
            (self.root / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.root / relative).write_text(text)
        (self.root / "overlay/usr/local/share/daemonarchy-installer").mkdir(parents=True)
        self.assets = Path(self.tmp.name) / "assets"
        self.assets.mkdir()
        for arch in ("amd64", "aarch64"):
            name = f"daemonarchy-{VERSION}-{arch}.iso.xz"
            (self.assets / name).write_bytes(arch.encode() * 1000)
            digest = hashlib.sha256((self.assets / name).read_bytes()).hexdigest()
            (self.assets / (name + ".sha256")).write_text(f"{digest}  {name}\n")
        for name in (f"daemonarchy-{VERSION}-boot.txz", f"daemonarchy-{VERSION}-boot.txz.sig",
                     f"daemonarchy-{VERSION}.pem", f"daemonarchy-{VERSION}.der"):
            (self.assets / name).write_bytes(name.encode())
        self.catalogue = Path(self.tmp.name) / "checkouts.json"
        self.catalogue.write_text(json.dumps({
            "repository_url": f"https://github.com/jordanhubbard/daemonarchy/releases/download/{FEEDS['--checkouts-amd64']}",
            "trees": {"src": {"revision": SOURCE}, "ports": {"revision": PORTS}}}))

    def prepare(self, *extra):
        return run("prepare-release.py", "--version", VERSION, "--source-commit", SOURCE, *extra, root=self.root)

    def fill(self, *extra, check=True, **override):
        feeds = dict(FEEDS, **override)
        args = ["--version", VERSION, "--assets", str(self.assets), "--installer-commit", INSTALLER,
                "--ports-commit", PORTS, "--aarch64-final-qemu", "The arm64 release image ran in QEMU.",
                "--physical-status", "No physical run was done.", "--checkouts-json", str(self.catalogue)]
        for flag, value in feeds.items():
            args += [flag, value]
        return run("fill-release.py", *args, *extra, root=self.root, check=check)

    def test_prepare_writes_placeholders_and_moves_the_current_release(self):
        before = json.loads((self.root / "release/current.json").read_text())
        output = self.prepare().stdout
        notes = (self.root / f"docs/release-{VERSION}.md").read_text()
        self.assertEqual(notes, (ROOT / f"release/templates/release-{VERSION}.md").read_text())
        record = json.loads((self.root / f"verification/release-{VERSION}.json").read_text())
        self.assertEqual((record["version"], record["source_commit"]), (VERSION, SOURCE))
        self.assertEqual(record["installer_commit"], "TODO")
        self.assertEqual(len(record["assets"]), 8)
        self.assertTrue(all(value == [0, "sha256:TODO"] for value in record["assets"].values()))
        self.assertEqual(record["closure_feed_records"],
                         sorted(p.stem for p in (ROOT / "verification/closure-feeds").glob("packages-16-*.json")))
        current = json.loads((self.root / "release/current.json").read_text())
        self.assertEqual((current["version"], current["published_at"]), (VERSION, "TODO"))
        self.assertEqual(current["previous_releases"][0]["version"], before["version"])
        self.assertEqual(current["previous_releases"][0]["image"][0], f"daemonarchy-{before['version']}-amd64.iso.xz")
        self.assertEqual(len(current["previous_releases"]), len(before["previous_releases"]) + 1)
        self.assertIn("README.md", output)
        self.assertIn("CHANGELOG.md", output)

    def test_prepare_refuses_overwrites_older_versions_and_bad_input(self):
        self.prepare()
        self.assertNotEqual(self.prepare_result().returncode, 0)             # already prepared
        older = run("prepare-release.py", "--version", "1.4.1", "--source-commit", SOURCE, root=self.root, check=False)
        self.assertNotEqual(older.returncode, 0)
        bad = run("prepare-release.py", "--version", "1.4.3", "--source-commit", "xyz", root=self.root, check=False)
        self.assertNotEqual(bad.returncode, 0)
        missing = run("prepare-release.py", "--version", "1.4.3", "--source-commit", SOURCE, root=self.root, check=False)
        self.assertIn("release-1.4.3.md first", missing.stderr)

    def prepare_result(self):
        return run("prepare-release.py", "--version", VERSION, "--source-commit", SOURCE, root=self.root, check=False)

    def test_dry_run_writes_nothing(self):
        self.prepare("--dry-run")
        self.assertFalse((self.root / f"docs/release-{VERSION}.md").exists())
        self.assertEqual(json.loads((self.root / "release/current.json").read_text())["version"], "1.4.1")

    def test_fill_consumes_every_token_and_records_the_assets(self):
        self.prepare()
        self.fill("--published-at", "2026-11-07T12:00:00Z", "--set", "GUI001_EVIDENCE=Evidence text.")
        current = json.loads((self.root / "release/current.json").read_text())
        record = json.loads((self.root / f"verification/release-{VERSION}.json").read_text())
        iso = f"daemonarchy-{VERSION}-amd64.iso.xz"
        digest = hashlib.sha256((self.assets / iso).read_bytes()).hexdigest()
        for document in (current, record):
            self.assertEqual(document["assets"][iso], [(self.assets / iso).stat().st_size, "sha256:" + digest])
            self.assertEqual(document["application_feed"], FEEDS["--packages-amd64"])
            self.assertEqual(document["checkout_feed"], FEEDS["--checkouts-amd64"])
        self.assertEqual(current["published_at"], "2026-11-07T12:00:00Z")
        self.assertEqual((record["installer_commit"], record["ports_commit"]), (INSTALLER, PORTS))
        self.assertEqual(record["aarch64_application_feed"], FEEDS["--packages-aarch64"])
        self.assertEqual(record["evidence_status"], "published release record")
        self.assertNotIn("closure_feed_records", record)
        self.assertEqual([feed["tag"] for feed in record["closure_feeds"]],
                         sorted(p.stem for p in (ROOT / "verification/closure-feeds").glob("packages-16-*.json")))
        for relative in list(PROSE) + [f"docs/release-{VERSION}.md"]:
            text = (self.root / relative).read_text()
            self.assertNotIn("@@", text, relative)
        self.assertIn("November 7, 2026", (self.root / "PROJECT.md").read_text())
        self.assertIn("Evidence text.", (self.root / f"docs/release-{VERSION}.md").read_text())
        self.assertEqual((self.root / "overlay/usr/local/share/daemonarchy-installer/checkouts.json").read_bytes(),
                         self.catalogue.read_bytes())

    def test_fill_before_publication_leaves_only_the_date_token(self):
        self.prepare()
        output = self.fill("--set", "GUI001_EVIDENCE=Evidence text.").stdout
        self.assertIn("still holds placeholders", output)
        self.assertIn("@@PUBLISHED_DATE@@", (self.root / "PROJECT.md").read_text())
        self.assertNotIn("@@AMD64_ISO_SHA256@@", (self.root / "README.md").read_text())

    def test_fill_refuses_what_does_not_match(self):
        self.prepare()
        self.assertNotEqual(self.fill(check=False, **{"--packages-amd64": "packages-16-amd64-1.4.1-r2"}).returncode, 0)
        self.assertNotEqual(self.fill("--set", "lower=x", check=False).returncode, 0)
        self.assertNotEqual(self.fill("--set", "VERSION_TOKEN", check=False).returncode, 0)
        iso = self.assets / f"daemonarchy-{VERSION}-amd64.iso.xz"
        iso.write_bytes(b"changed")                                            # its .sha256 no longer covers it
        result = self.fill(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not cover", result.stderr)

    def test_fill_checks_the_catalogue_and_the_closure_records(self):
        self.prepare()
        wrong = json.loads(self.catalogue.read_text())
        wrong["trees"]["ports"]["revision"] = "c" * 40
        self.catalogue.write_text(json.dumps(wrong))
        self.assertIn("ports revision", self.fill(check=False).stderr)
        wrong["trees"]["ports"]["revision"] = PORTS
        wrong["repository_url"] = "https://example.invalid/checkouts"
        self.catalogue.write_text(json.dumps(wrong))
        self.assertIn("repository_url", self.fill(check=False).stderr)
        wrong["repository_url"] = f"https://github.com/jordanhubbard/daemonarchy/releases/download/{FEEDS['--checkouts-amd64']}"
        self.catalogue.write_text(json.dumps(wrong))
        record_path = self.root / f"verification/release-{VERSION}.json"
        record = json.loads(record_path.read_text())
        record["closure_feed_records"].append("packages-16-amd64-1.4.2-upstream")
        record_path.write_text(json.dumps(record))
        self.assertIn("no closure feed record for packages-16-amd64-1.4.2-upstream", self.fill(check=False).stderr)


if __name__ == "__main__":
    unittest.main()
