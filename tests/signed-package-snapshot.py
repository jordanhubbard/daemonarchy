#!/usr/bin/env python3
"""Frozen-origin routing, signed inventory and retained payload refusal checks."""

from contextlib import closing
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
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


if __name__ == "__main__":
    unittest.main()
