#!/usr/bin/env python3
"""Verified transport-cache checks; no native compilation/qualification claims."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import os
import shlex
import unittest

spec = importlib.util.spec_from_file_location("verified_cache", Path(__file__).resolve().parents[1] / "scripts/verified-artifact-cache.py")
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.payload = b"retained package bytes"
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.source = self.root / "source.pkg"
        self.source.write_bytes(self.payload)
        self.package = dict(version="1", abi="FreeBSD:16:amd64", archive_checksum="native-checksum",
                            archive_path="All/a-1.pkg", download_bytes=len(self.payload))
        self.identity = cache.selection_identity({"meta.conf": "d" * 64, "data.pkg": "e" * 64, "packagesite.pkg": "a" * 64, "public_key": "b" * 64}, "a", self.package)
        self.cache = cache.VerifiedCache(self.root / "cache")

    def test_miss_verified_retention_and_byte_checked_hit(self):
        self.assertIsNone(self.cache.lookup(self.identity))
        self.cache.retain(self.identity, self.source, self.sha)
        with self.cache.lookup(self.identity) as stream:
            self.assertEqual(stream.read(), self.payload)
        self.assertEqual(self.source.read_bytes(), self.payload)
        result = self.cache.summary()
        self.assertEqual((result["misses"], result["hits"], result["bytes_saved"]), (1, 1, len(self.payload)))

    def test_catalogue_name_version_abi_and_native_checksum_never_alias(self):
        self.cache.retain(self.identity, self.source, self.sha)
        for key in ("name", "version", "abi", "archive_checksum", "archive_path"):
            changed = copy.deepcopy(self.identity)
            changed[key] = "changed"
            self.assertIsNone(self.cache.lookup(changed))
        changed = copy.deepcopy(self.identity)
        changed["catalogue"]["packagesite.pkg"] = "c" * 64
        self.assertIsNone(self.cache.lookup(changed))

    def test_corrupt_object_fails_closed_without_repair_or_fallback(self):
        self.cache.retain(self.identity, self.source, self.sha)
        target = self.root / "cache/objects" / self.sha
        target.chmod(0o600)
        corrupt = b"x" * len(self.payload)
        target.write_bytes(corrupt)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.cache.lookup(self.identity)
        with self.assertRaisesRegex(ValueError, "corrupt"):
            self.cache.retain(self.identity, self.source, self.sha)
        self.assertEqual(target.read_bytes(), corrupt)
        self.assertEqual(self.source.read_bytes(), self.payload)

    def test_bad_source_never_publishes_selection_and_is_retained(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            self.cache.retain(self.identity, self.source, "c" * 64)
        self.assertIsNone(self.cache.lookup(self.identity))
        self.assertTrue(list((self.root / "cache/pending").iterdir()))

    def test_repeated_retention_is_immutable_and_safe(self):
        self.cache.retain(self.identity, self.source, self.sha)
        record = self.root / "cache/selections" / (self.cache.key(self.identity) + ".json")
        old = record.read_bytes()
        self.cache.retain(self.identity, self.source, self.sha)
        self.assertEqual(record.read_bytes(), old)

    def test_symlink_and_binding_corruption_refuse(self):
        self.cache.retain(self.identity, self.source, self.sha)
        record = self.root / "cache/selections" / (self.cache.key(self.identity) + ".json")
        record.chmod(0o600)
        record.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, "binding"):
            self.cache.lookup(self.identity)
        linked = self.root / "linked"
        linked.symlink_to(self.root / "cache")
        with self.assertRaisesRegex(ValueError, "symlink"):
            cache.VerifiedCache(linked)

    def new_selection(self):
        selected = copy.deepcopy(self.identity)
        selected["catalogue"]["packagesite.pkg"] = "c" * 64
        selected["catalogue"]["public_key"] = "f" * 64
        return selected

    def authentication(self, selected):
        # Controller protocol witness only; no native signature evidence claimed.
        return cache.NativeAuthenticatedCatalogue(selected["catalogue"], {selected["name"]: selected}, "d" * 64)

    def test_new_authenticated_catalogue_candidate_requires_fresh_verification_before_binding(self):
        self.cache.retain(self.identity, self.source, self.sha)
        record = self.root / "cache/selections" / (self.cache.key(self.identity) + ".json")
        previous = record.read_bytes()
        blob = self.root / "cache/objects" / self.sha
        inode = blob.stat().st_ino
        pending_archives = [p for p in (self.root / "cache/pending").iterdir() if p.suffix != ".json"]
        selected = self.new_selection()
        self.assertIsNone(self.cache.lookup(selected))
        fresh = self.root / "fresh-native-fetch.pkg"
        with self.cache.candidate(selected, self.authentication(selected)) as stream:
            fresh.write_bytes(stream.read())
        current_record = self.root / "cache/selections" / (self.cache.key(selected) + ".json")
        self.assertFalse(current_record.exists())
        self.assertEqual(self.cache.summary()["candidate_bytes_admitted"], 0)
        # A current native consumer must reverify its selected checksum; this
        # fixture uses a known SHA-256, not an invented interpretation of pkg's typed digest.
        self.assertEqual(hashlib.sha256(fresh.read_bytes()).hexdigest(), self.sha)
        self.cache.retain(selected, fresh, self.sha)
        self.assertTrue(current_record.exists())
        self.assertEqual(record.read_bytes(), previous)
        self.assertEqual(blob.stat().st_ino, inode)
        self.assertEqual(len(list((self.root / "cache/objects").iterdir())), 1)
        self.assertEqual([p for p in (self.root / "cache/pending").iterdir() if p.suffix != ".json"], pending_archives)
        self.assertEqual(self.cache.summary()["candidate_bytes_admitted"], len(self.payload))
        admitted = next(e for e in self.cache.summary()["events"] if e["kind"] == "candidate_admitted")
        self.assertTrue(admitted["native_selected_checksum_reverified"])
        self.assertFalse(admitted["runtime_qualification_copied"])

    def test_candidate_refuses_missing_or_stale_current_authentication(self):
        self.cache.retain(self.identity, self.source, self.sha)
        for key in ("abi", "archive_checksum", "public_key"):
            selected = copy.deepcopy(self.identity)
            if key == "public_key":
                selected["catalogue"][key] = "f" * 64
            else:
                selected[key] = "changed"
            with self.assertRaisesRegex(ValueError, "fresh native"):
                self.cache.candidate(selected, None)
            with self.assertRaisesRegex(ValueError, "freshly authenticated"):
                self.cache.candidate(selected, self.authentication(self.identity))
        self.assertEqual(self.cache.summary()["candidate_requests"], 0)

    def test_fresh_authentication_does_not_alias_changed_checksum_or_abi(self):
        self.cache.retain(self.identity, self.source, self.sha)
        for key in ("abi", "archive_checksum", "version"):
            selected = self.new_selection()
            selected[key] = "changed"
            self.assertIsNone(self.cache.candidate(selected, self.authentication(selected)))
        self.assertEqual(self.cache.summary()["candidate_requests"], 0)

    def test_corrupt_candidate_preserves_old_record_and_refuses_new_binding(self):
        self.cache.retain(self.identity, self.source, self.sha)
        old = self.root / "cache/selections" / (self.cache.key(self.identity) + ".json")
        previous = old.read_bytes()
        blob = self.root / "cache/objects" / self.sha
        blob.chmod(0o600)
        corrupt = b"x" * len(self.payload)
        blob.write_bytes(corrupt)
        selected = self.new_selection()
        with self.assertRaisesRegex(ValueError, "corrupt cache entry SHA-256"):
            self.cache.candidate(selected, self.authentication(selected))
        self.assertEqual(old.read_bytes(), previous)
        self.assertEqual(blob.read_bytes(), corrupt)
        self.assertEqual(self.source.read_bytes(), self.payload)
        self.assertFalse((self.root / "cache/selections" / (self.cache.key(selected) + ".json")).exists())

    def test_malformed_candidate_record_refuses_without_repair(self):
        self.cache.retain(self.identity, self.source, self.sha)
        record = self.root / "cache/selections" / (self.cache.key(self.identity) + ".json")
        record.chmod(0o600)
        record.write_bytes(b"[]")
        selected = self.new_selection()
        with self.assertRaisesRegex(ValueError, "record binding differs"):
            self.cache.candidate(selected, self.authentication(selected))
        self.assertEqual(record.read_bytes(), b"[]")
        self.assertEqual(self.source.read_bytes(), self.payload)

    def test_failed_candidate_reverification_cannot_publish_current_record(self):
        self.cache.retain(self.identity, self.source, self.sha)
        selected = self.new_selection()
        with self.cache.candidate(selected, self.authentication(selected)):
            pass
        with self.assertRaisesRegex(ValueError, "differs from retained candidate"):
            self.cache.retain(selected, self.source, "b" * 64)
        self.assertFalse((self.root / "cache/selections" / (self.cache.key(selected) + ".json")).exists())
        self.assertEqual(self.cache.summary()["candidate_bytes_admitted"], 0)



class InstallerCacheTests(unittest.TestCase):
    def shell(self, body, extra=None):
        root = Path(__file__).resolve().parents[1]
        helper = root / "overlay/usr/local/libexec/daemonarchy-installer/package-repository"
        return subprocess.run(["sh", "-c", ". " + shlex.quote(str(helper)) + "\n" + body],
                              env=dict(os.environ, **(extra or {})), text=True, capture_output=True)

    def environment(self):
        return dict(package_qa_mode="iterative", package_cache_url="http://127.0.0.1:9999/feed",
                    package_cache_meta_sha256="a" * 64, package_cache_packagesite_sha256="b" * 64,
                    package_cache_data_sha256="c" * 64)

    def test_explicit_iterative_transport_keeps_pubkey_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "repository.conf"
            result = self.shell('package_repository_tag=packages-16-amd64-1.3.1; package_repository_write_dependencies "$TARGET" /selected/public-key',
                                dict(self.environment(), TARGET=str(target)))
            self.assertEqual(result.returncode, 0, result.stderr)
            value = target.read_text()
            self.assertIn('url: "http://127.0.0.1:9999/feed"', value)
            self.assertIn('signature_type: "pubkey"', value)
            self.assertIn('pubkey: "/selected/public-key"', value)

    def test_final_rc_and_malformed_overrides_refuse_before_vm_launch(self):
        env = self.environment()
        env["package_qa_mode"] = "final-rc"
        result = self.shell("package_cache_validate", env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Final RC", result.stderr)
        for url in ('http://host/a/../b', 'http://host/quote"', 'http://user@host/feed', 'file:///tmp/feed'):
            self.assertNotEqual(self.shell("package_cache_validate", dict(self.environment(), package_cache_url=url)).returncode, 0)
        self.assertNotEqual(self.shell("package_cache_validate", dict(self.environment(), package_cache_data_sha256="")).returncode, 0)
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(["sh", str(root / "test-bhyve.sh"), "/does/not/exist.iso"],
                                env=dict(os.environ, PACKAGE_QA_MODE="final-rc", PACKAGE_CACHE_URL="http://127.0.0.1/feed"),
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Final RC", result.stderr)
        self.assertNotIn("kldload", result.stderr)

    def test_harness_refuses_existing_work_before_mutating_host(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            prior = Path(directory) / "disk.img"
            prior.write_bytes(b"retained previous qualification")
            result = subprocess.run(["sh", str(root / "test-bhyve.sh"), "/does/not/exist.iso"],
                                    env=dict(os.environ, WORK=directory, NIC="fixture0"), text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fresh WORK", result.stderr)
            self.assertNotIn("kldload", result.stderr)
            self.assertEqual(prior.read_bytes(), b"retained previous qualification")

    def test_harness_allows_preallocated_empty_work_directory(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            work = path / "allocated-empty"
            work.mkdir()
            shim = path / "bin"
            shim.mkdir()
            command = shim / "kldload"
            command.write_text("#!/bin/sh\nexit 42\n")
            command.chmod(0o755)
            result = subprocess.run(["sh", str(root / "test-bhyve.sh"), "/does/not/exist.iso"],
                                    env=dict(os.environ, WORK=str(work), NIC="fixture0", PATH=str(shim) + os.pathsep + os.environ["PATH"]),
                                    text=True, capture_output=True)
            # Reached the harmless host-operation fixture, then stopped before any mutation.
            self.assertEqual(result.returncode, 42, result.stderr)
            self.assertEqual(list(work.iterdir()), [])

    def test_selected_metadata_pins_reject_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            env = self.environment()
            for filename, variable in (("meta.conf", "package_cache_meta_sha256"), ("packagesite.pkg", "package_cache_packagesite_sha256"), ("data.pkg", "package_cache_data_sha256")):
                payload = filename.encode()
                (path / filename).write_bytes(payload)
                env[variable] = hashlib.sha256(payload).hexdigest()
            env["TEST_METADATA"] = str(path)
            # Transport fixtures only; native pkg remains responsible for authentication.
            body = 'fetch() { cp "$TEST_METADATA/${6##*/}" "$5"; }; sha256() { shasum -a 256 "$2" | cut -d " " -f 1; }; package_cache_check_metadata'
            result = self.shell(body, env)
            self.assertEqual(result.returncode, 0, result.stderr)
            (path / "data.pkg").write_bytes(b"corrupt")
            result = self.shell(body, env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("metadata mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
