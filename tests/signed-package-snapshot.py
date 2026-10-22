#!/usr/bin/env python3
"""Frozen-origin routing, signed inventory and retained payload refusal checks."""

from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.request


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/signed-package-snapshot.py"
spec = importlib.util.spec_from_file_location("signed_snapshot", SCRIPT)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args):
        return None


class SignedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_publisher_requires_https_without_credentials_or_ambiguity(self):
        self.assertEqual(snapshot.https_url("https://example.invalid/feed/"), "https://example.invalid/feed")
        for url in ("http://example.invalid", "https://user:secret@example.invalid", "https://example.invalid/?x=1",
                    "https://example.invalid/#fragment", "https://example.invalid:bad", "https://bad host.invalid"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                snapshot.https_url(url)

    def test_unsafe_archive_paths_refuse(self):
        self.assertEqual(snapshot.archive_path("All/a-1.pkg"), "All/a-1.pkg")
        for path in ("/absolute.pkg", "../outside.pkg", "All/../outside.pkg", "All//a.pkg", "All/%2e%2e/a.pkg",
                     "All/a.pkg?x", "All/a.pkg#x", "All\\a.pkg", "metadata.txt"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                snapshot.archive_path(path)

    def test_only_public_pem_material_is_retained(self):
        public = b"-----BEGIN PUBLIC KEY-----\nYQ==\n-----END PUBLIC KEY-----\n"
        self.assertEqual(snapshot.public_key_bytes(public), public)
        crlf = public.replace(b"\n", b"\r\n")
        self.assertEqual(snapshot.public_key_bytes(crlf), crlf)
        for key in (b"-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n", b"untyped bytes",
                    public + b"-----BEGIN PRIVATE KEY-----"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "public key"):
                snapshot.public_key_bytes(key)

    def test_only_frozen_metadata_is_served(self):
        with snapshot.FrozenOrigin({"data.pkg": b"frozen signed bytes"}, {"url": "https://example.invalid/feed"}) as origin:
            with urllib.request.urlopen(origin.url + "/data.pkg", timeout=2) as response:
                self.assertEqual(response.read(), b"frozen signed bytes")
            for path in ("/unknown.pkg", "/../outside.pkg", "/%2e%2e/outside.pkg", "/data.pkg?changed=1"):
                with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(origin.url + path, timeout=2)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()

    def test_payload_redirect_is_allowlisted_and_keeps_metadata_url(self):
        opener = urllib.request.build_opener(NoRedirect)
        with snapshot.FrozenOrigin({"meta.conf": b"frozen"}, {"url": "https://example.invalid/feed"}) as origin:
            original = origin.url
            origin.payloads = {"All/a+1.pkg": 4}
            with self.assertRaises(urllib.error.HTTPError) as error:
                opener.open(origin.url + "/All/a+1.pkg", timeout=2)
            self.assertEqual(error.exception.code, 302)
            self.assertEqual(error.exception.headers["Location"], "https://example.invalid/feed/All/a%2B1.pkg")
            self.assertEqual(origin.url, original)
            error.exception.close()

    def test_offline_replay_is_read_only_and_refuses_wrong_size(self):
        (self.root / "a.pkg").write_bytes(b"test")
        with snapshot.FrozenOrigin({}, {"directory": str(self.root)}) as origin:
            origin.payloads = {"a.pkg": 4}
            with urllib.request.urlopen(origin.url + "/a.pkg", timeout=2) as response:
                self.assertEqual(response.read(), b"test")
            self.assertEqual((self.root / "a.pkg").read_bytes(), b"test")
            origin.payloads = {"a.pkg": 5}
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(origin.url + "/a.pkg", timeout=2)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()

    def test_offline_source_final_symlink_refuses(self):
        (self.root / "real.pkg").write_bytes(b"test")
        (self.root / "alias.pkg").symlink_to(self.root / "real.pkg")
        with snapshot.FrozenOrigin({}, {"directory": str(self.root)}) as origin:
            origin.payloads = {"alias.pkg": 4}
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(origin.url + "/alias.pkg", timeout=2)
            error.exception.close()

    def test_seed_reuse_falls_back_only_for_missing_or_wrong_size_files(self):
        (self.root / "seed.pkg").write_bytes(b"test")
        (self.root / "short.pkg").write_bytes(b"x")
        opener = urllib.request.build_opener(NoRedirect)
        source = dict(directory=str(self.root), url="https://example.invalid/feed")
        with snapshot.FrozenOrigin({}, source) as origin:
            origin.payloads = {"seed.pkg": 4, "missing.pkg": 4, "short.pkg": 4}
            with urllib.request.urlopen(origin.url + "/seed.pkg", timeout=2) as response:
                self.assertEqual(response.read(), b"test")
            for name in ["missing.pkg", "short.pkg"]:
                with self.subTest(name=name), self.assertRaises(urllib.error.HTTPError) as error:
                    opener.open(origin.url + "/" + name, timeout=2)
                self.assertEqual(error.exception.code, 302)
                error.exception.close()
            self.assertEqual(origin.offline_requests, 1)
            self.assertEqual(origin.redirect_requests, 2)
        self.assertEqual((self.root / "seed.pkg").read_bytes(), b"test")

    def database(self, rows=None):
        path = self.root / "repo.sqlite"
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("CREATE TABLE packages (name TEXT,version TEXT,origin TEXT,arch TEXT,cksum TEXT,path TEXT,pkgsize INTEGER,flatsize INTEGER)")
            connection.executemany("INSERT INTO packages VALUES (?,?,?,?,?,?,?,?)", rows or [])
        return path

    def row(self):
        return ["a", "1", "misc/a", "FreeBSD:16:amd64", "a" * 64, "All/a.pkg", 4, 100]

    def test_authenticated_inventory_is_complete_and_read_only(self):
        path = self.database([self.row()])
        original = path.read_bytes()
        rows = snapshot.inventory(path)
        self.assertEqual(rows["a"]["archive_checksum"], "a" * 64)
        self.assertEqual(rows["a"]["download_bytes"], 4)
        self.assertEqual(path.read_bytes(), original)

    def test_empty_duplicate_or_unsafe_signed_inventory_refuses(self):
        path = self.database()
        with self.assertRaisesRegex(ValueError, "empty"):
            snapshot.inventory(path)
        for index, value in [(0, "-option"), (4, "bad"), (5, "../escape.pkg"), (6, 0), (6, -1), (7, -1)]:
            row = self.row()
            row[index] = value
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("DELETE FROM packages")
                connection.execute("INSERT INTO packages VALUES (?,?,?,?,?,?,?,?)", row)
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                snapshot.inventory(path)
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("DELETE FROM packages")
            connection.executemany("INSERT INTO packages VALUES (?,?,?,?,?,?,?,?)", [self.row(), self.row()])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            snapshot.inventory(path)

    def test_payload_inventory_has_exact_names_sizes_and_independent_hashes(self):
        directory = self.root / "payloads"
        (directory / "All").mkdir(parents=True)
        (directory / "All/a.pkg").write_bytes(b"test")
        packages = {"a": dict(archive_path="All/a.pkg", download_bytes=4)}
        result = snapshot.verify_payload_files(directory, packages)
        self.assertEqual(result["a"]["sha256"], hashlib.sha256(b"test").hexdigest())
        (directory / "unexpected.pkg").write_bytes(b"test")
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            snapshot.verify_payload_files(directory, packages)
        (directory / "unexpected.pkg").unlink()
        (directory / "All/a.pkg").write_bytes(b"wrong length")
        with self.assertRaisesRegex(ValueError, "size/type"):
            snapshot.verify_payload_files(directory, packages)

    def test_missing_or_linked_fetched_payload_refuses(self):
        packages = {"a": dict(archive_path="a.pkg", download_bytes=4)}
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            snapshot.verify_payload_files(self.root, packages)
        target = self.root.parent / (self.root.name + "-external.pkg")
        target.write_bytes(b"test")
        self.addCleanup(target.unlink)
        (self.root / "a.pkg").symlink_to(target)
        with self.assertRaises(OSError):
            snapshot.verify_payload_files(self.root, packages)

    def test_parallel_policy_is_explicit_and_bounded(self):
        self.assertIsNone(snapshot.fetch_policy({"schema": "daemonarchy/signed-package-snapshot-inputs@1"}))
        self.assertEqual(snapshot.fetch_policy(dict(schema="daemonarchy/signed-package-snapshot-inputs@2", fetch_workers=4)), (4, 32))
        for data in [dict(schema="daemonarchy/signed-package-snapshot-inputs@1", fetch_workers=2),
                     dict(schema="unknown"),
                     *[dict(schema="daemonarchy/signed-package-snapshot-inputs@2", fetch_workers=n)
                       for n in [0, 17, True]],
                     *[dict(schema="daemonarchy/signed-package-snapshot-inputs@2", fetch_workers=2, fetch_batch_packages=n)
                       for n in [0, 129, False]]]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                snapshot.fetch_policy(data)

    def test_balanced_batches_preserve_selection_and_refuse_path_collisions(self):
        packages = {name: dict(archive_path=f"All/{name}.pkg", download_bytes=size)
                    for name, size in zip("abcdef", [30, 20, 15, 10, 5, 1])}
        batches = snapshot.fetch_batches(packages, 2)
        self.assertEqual(sorted(n for batch in batches for n in batch), sorted(packages))
        self.assertTrue(all(len(batch) <= 2 for batch in batches))
        self.assertEqual(batches, snapshot.fetch_batches(dict(reversed(list(packages.items()))), 2))
        packages["b"]["archive_path"] = "All/a.pkg/b.pkg"
        with self.assertRaisesRegex(ValueError, "files and directories"):
            snapshot.fetch_batches(packages, 2)

    def native_fetch_peer(self, action="normal", barrier=1):
        """A command-protocol fixture, never native signature/checksum evidence."""
        case = self.root / "case"
        (case / "db").mkdir(parents=True)
        (case / "cache").mkdir()
        (case / "repos").mkdir()
        repo = case / "db/repo-Test.sqlite"
        repo.write_bytes(b"frozen authenticated database fixture")
        with closing(sqlite3.connect(case / "db/local.sqlite")) as db, db:
            db.execute("CREATE TABLE packages (name TEXT)")
        packages = {name: dict(archive_path=f"All/{name}.pkg", download_bytes=size)
                    for name, size in zip("abc", [4, 8, 12])}
        settings = self.root / "peer-settings.json"
        settings.write_text(json.dumps(dict(action=action, barrier=barrier, packages=packages)))
        executable = self.root / "fetch-peer"
        executable.write_text(f"#!{sys.executable}\n" + '''
import json, pathlib, sqlite3, sys, time
settings=json.loads((pathlib.Path(__file__).parent/'peer-settings.json').read_text())
args=sys.argv[1:]; cfg=json.loads(pathlib.Path(args[args.index('-C')+1]).read_text())
job=pathlib.Path(cfg['PKG_DBDIR']).parent; case=job.parent.parent
out=pathlib.Path(args[args.index('-o')+1]); names=args[args.index('--')+1:]
start=time.monotonic(); ready=case/'peer-ready'; ready.mkdir(exist_ok=True)
(ready/job.name).write_text('ready'); deadline=time.monotonic()+3
while len(list(ready.iterdir()))<settings['barrier']:
 if time.monotonic()>deadline: raise RuntimeError('peer barrier deadline')
 time.sleep(.01)
time.sleep(.06)
for name in names:
 row=settings['packages'][name]; path=out/row['archive_path']; path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(name.encode()*row['download_bytes'])
action=settings['action']
if action=='extra': (out/'extra.pkg').write_bytes(b'wrong')
if action=='catalogue': (pathlib.Path(cfg['PKG_DBDIR'])/'repo-Test.sqlite').write_bytes(b'changed')
if action=='installed':
 db=sqlite3.connect(pathlib.Path(cfg['PKG_DBDIR'])/'local.sqlite'); db.execute("INSERT INTO packages VALUES ('unexpected')"); db.commit(); db.close()
if action=='cache': (pathlib.Path(cfg['PKG_CACHEDIR'])/'unexpected').write_bytes(b'wrong')
if action=='diagnostic': print('native diagnostic',file=sys.stderr)
if action=='mutate-published':
 for path in (case/'payloads').rglob('*.pkg'): path.write_bytes(b'x'*path.stat().st_size)
print(json.dumps({'database':cfg['PKG_DBDIR'],'start':start,'end':time.monotonic()}))
''')
        executable.chmod(0o755)
        return case, repo, packages, executable

    def run_peer(self, fixture, workers=2, batch=1):
        case, repo, packages, executable = fixture
        return snapshot.parallel_fetch(executable, {}, packages, repo,
                                       hashlib.sha256(repo.read_bytes()).hexdigest(),
                                       case, "Test", (workers, batch), 5, "a" * 64)

    def test_parallel_coordinator_keeps_database_state_private_and_progress_measured(self):
        fixture = self.native_fetch_peer(barrier=2)
        case, repo, packages, _executable = fixture
        original = repo.read_bytes()
        result = self.run_peer(fixture)
        self.assertEqual(result['peak_active'], 2)
        self.assertEqual(result['commands'], 3)
        self.assertEqual(repo.read_bytes(), original)
        observations = [json.loads(p.read_text()) for p in (case/'parallel').glob('*/*.stdout')]
        self.assertEqual(len({o['database'] for o in observations}), 3)
        first = sorted(observations, key=lambda o:o['start'])[:2]
        self.assertLess(max(o['start'] for o in first), min(o['end'] for o in first))
        inventory = snapshot.verify_payload_files(case/'payloads', packages)
        self.assertEqual(set(inventory), set(packages))
        events = [json.loads(line) for line in (case/'events.jsonl').read_text().splitlines()]
        self.assertEqual([e['sequence'] for e in events], list(range(1, len(events)+1)))
        self.assertTrue(all(e['input_sha256']=='a'*64 for e in events))
        self.assertEqual(events[-1]['verified_bytes'], sum(p['download_bytes'] for p in packages.values()))
        self.assertEqual(events[-1]['verified_packages'], 3)
        self.assertTrue(all(e['state']!='completed' for e in events))

    def test_failed_batch_checks_never_promote_its_archives(self):
        for action, reason in [('extra','inventory differs'), ('catalogue','clone changed'),
                               ('installed','installed package database'), ('cache','outside'),
                               ('diagnostic','exit 0')]:
            with self.subTest(action=action):
                # Separate cases preserve every failed attempt in this test.
                original = self.root
                self.root = original/action
                self.root.mkdir()
                try:
                    fixture = self.native_fetch_peer(action=action)
                    with self.assertRaisesRegex(ValueError, reason):
                        self.run_peer(fixture, workers=1)
                    case = fixture[0]
                    self.assertEqual(list((case/'payloads').iterdir()), [])
                    events = [json.loads(line) for line in (case/'events.jsonl').read_text().splitlines()]
                    self.assertEqual(events[-1]['state'], 'failed')
                    self.assertFalse(any(e['state']=='verified' for e in events))
                finally:
                    self.root = original

    def test_completed_batch_mutation_refuses_final_inventory(self):
        fixture = self.native_fetch_peer(action='mutate-published')
        with self.assertRaisesRegex(ValueError, 'changed after native batch verification'):
            self.run_peer(fixture, workers=1)
        events = [json.loads(line) for line in (fixture[0]/'events.jsonl').read_text().splitlines()]
        self.assertEqual(events[-1]['state'], 'failed')


if __name__ == "__main__":
    unittest.main()
