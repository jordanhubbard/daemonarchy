#!/usr/bin/env python3
"""Extension bundles: deterministic compressed packing, a signed index, strict verification, safe extraction,
bounded downloads and the staging tool. Uses throwaway RSA keys; no release key is involved."""

import functools
import http.server
import io
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "overlay/usr/local/lib/daemonarchy-visual"
sys.path.insert(0, str(LIB))

import daemonarchy_visual as sdk  # noqa: E402
from daemonarchy_visual import bundle, plugin  # noqa: E402

GAMES = ROOT / "extensions/games"
SCRIPT = ROOT / "scripts/extension-bundle.py"
FEED = "extensions-16-amd64-1.4.1"


def openssl(*args):
    subprocess.run(["openssl", *args], check=True, capture_output=True)


class Keys:
    def __init__(self, directory, name):
        self.private = str(Path(directory) / f"{name}.key")
        self.public = str(Path(directory) / f"{name}.pub")
        openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", self.private)
        openssl("pkey", "-in", self.private, "-pubout", "-out", self.public)


def make_extension(root, ext_id="demo", version="1.0.0", ext_type="tool", caps=("draw", "input"), body="print('x')\n" * 200):
    directory = Path(root) / ext_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "game.py").write_text(f"def create(api):\n    pass\n# {body}\n")
    manifest = dict(schema=plugin.SCHEMA, id=ext_id, name=ext_id.title(), version=version, type=ext_type, api="1.3",
                    entry="game.py", entry_sha256="0" * 64, capabilities=list(caps), min_size=[40, 12],
                    description=f"The {ext_id} extension.", limits={})
    (directory / "manifest.json").write_text(json.dumps(manifest))
    plugin.seal_manifest(str(directory))
    return directory


class Staged:
    """A signed feed of a few extensions in a temp directory."""

    def __init__(self, root, ids=("alpha", "beta"), types=("game", "tool")):
        self.root = Path(root)
        self.keys = Keys(root, "dev")
        self.sources = [make_extension(self.root / "src", i, ext_type=t) for i, t in zip(ids, types)]
        self.feed = self.root / "feed"
        entries = [bundle.build_bundle(s, self.feed) for s in self.sources]
        (self.feed / bundle.INDEX_NAME).write_bytes(bundle.compress(bundle.build_index(entries, FEED, "amd64", "2026-10-30T00:00:00Z")))
        self.sign(self.keys.private)
        self.entries = entries

    def sign(self, key):
        for name in [bundle.INDEX_NAME] + [e["bundle"]["file"] for e in bundle.parse_index((self.feed / bundle.INDEX_NAME).read_bytes())["extensions"]]:
            bundle.sign_file(str(self.feed / name), key)


class Packing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_packing_is_deterministic_normalised_and_compressed(self):
        d = make_extension(self.tmp.name)
        a, b = bundle.pack(d), bundle.pack(d)
        self.assertEqual(a, b)
        os.utime(d / "game.py", (12345, 12345))
        os.chmod(d / "game.py", 0o600)
        self.assertEqual(bundle.pack(d), a, "mtime and mode do not leak into the bundle")
        with tarfile.open(fileobj=io.BytesIO(a)) as archive:
            members = archive.getmembers()
        self.assertEqual([m.name for m in members], ["demo", "demo/game.py", "demo/manifest.json"])
        self.assertTrue(all(m.mtime == 0 and m.uid == 0 and m.gid == 0 for m in members))
        self.assertEqual([oct(m.mode) for m in members], ["0o755", "0o644", "0o644"])
        entry = bundle.build_bundle(d, Path(self.tmp.name) / "out")
        info = entry["bundle"]
        self.assertLess(info["bytes"], info["raw_bytes"] / 4, "xz compresses it well")
        self.assertEqual(info["file"], "ext-demo-1.0.0.tar.xz")
        data = (Path(self.tmp.name) / "out" / info["file"]).read_bytes()
        self.assertEqual((len(data), bundle.sha256_bytes(data)), (info["bytes"], info["sha256"]))
        self.assertTrue(data.startswith(b"\xfd7zXZ\x00"), "an xz file, not a raw tar")

    def test_python_bytecode_beside_the_source_is_left_out(self):
        d = make_extension(self.tmp.name)
        (d / "__pycache__").mkdir()
        (d / "__pycache__" / "game.cpython-313.pyc").write_bytes(b"junk")
        with tarfile.open(fileobj=io.BytesIO(bundle.pack(d))) as archive:
            self.assertEqual([m.name for m in archive.getmembers()], ["demo", "demo/game.py", "demo/manifest.json"])

    def test_only_plain_visible_files_are_bundled(self):
        d = make_extension(self.tmp.name)
        os.symlink("/etc/passwd", d / "link.py")
        with self.assertRaises(bundle.BundleError):
            bundle.pack(d)
        os.unlink(d / "link.py")
        (d / ".hidden").write_text("x")
        with self.assertRaises(bundle.BundleError):
            bundle.pack(d)

    def test_a_bad_or_unsealed_manifest_is_refused(self):
        d = make_extension(self.tmp.name)
        manifest = json.loads((d / "manifest.json").read_text())
        for change in ({"type": "malware"}, {"capabilities": ["input"]}, {"capabilities": ["draw", "network"]},
                       {"version": "1.0"}, {"id": "Bad Id"}, {"api": "9.0"}, {"entry_sha256": "0"}):
            (d / "manifest.json").write_text(json.dumps(dict(manifest, **change)))
            with self.assertRaises(bundle.BundleError, msg=str(change)):
                bundle.build_bundle(d, Path(self.tmp.name) / "o")
        (d / "manifest.json").write_text(json.dumps(dict(manifest, id="other")))
        with self.assertRaises(bundle.BundleError):
            bundle.build_bundle(d, Path(self.tmp.name) / "o")

    def test_every_extension_type_is_allowed_and_categorised(self):
        for ext_type, category in (("game", "Games"), ("tool", "Tools"), ("animation", "Visuals"), ("visualizer", "Visuals")):
            d = make_extension(self.tmp.name, f"x-{ext_type}", ext_type=ext_type)
            self.assertEqual(bundle.build_bundle(d, Path(self.tmp.name) / "o")["category"], category)

    def test_the_window_capability_is_a_valid_capability(self):
        d = make_extension(self.tmp.name, caps=("draw", "input", "audio", "window"))
        self.assertIn("window", bundle.build_bundle(d, Path(self.tmp.name) / "o")["capabilities"])


class IndexAndSignatures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Staged(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_signed_feed_verifies_end_to_end(self):
        index, rows = bundle.verify_feed(str(self.s.feed), self.s.keys.public, FEED)
        self.assertEqual([e["id"] for e in index["extensions"]], ["alpha", "beta"])
        self.assertEqual(len(rows), 3)

    def test_the_wrong_key_a_missing_signature_and_a_swapped_signature_are_refused(self):
        other = Keys(self.tmp.name, "other")
        with self.assertRaises(bundle.BundleError):
            bundle.verify_feed(str(self.s.feed), other.public)
        index = self.s.feed / bundle.INDEX_NAME
        saved = (index.with_name(index.name + ".sig")).read_bytes()
        os.unlink(str(index) + ".sig")
        with self.assertRaises(bundle.BundleError):
            bundle.verify_feed(str(self.s.feed), self.s.keys.public)
        bundle_sig = self.s.feed / (self.s.entries[0]["bundle"]["file"] + ".sig")
        Path(str(index) + ".sig").write_bytes(bundle_sig.read_bytes())    # another file's valid signature
        with self.assertRaises(bundle.BundleError):
            bundle.verify_feed(str(self.s.feed), self.s.keys.public)
        Path(str(index) + ".sig").write_bytes(saved)
        bundle.verify_feed(str(self.s.feed), self.s.keys.public)

    def test_tampering_with_the_index_a_bundle_or_its_hash_is_caught(self):
        index = self.s.feed / bundle.INDEX_NAME
        original = index.read_bytes()
        index.write_bytes(original[:-5] + b"XXXXX")
        with self.assertRaises(bundle.BundleError):
            bundle.verify_feed(str(self.s.feed), self.s.keys.public)
        index.write_bytes(original)
        path = self.s.feed / self.s.entries[0]["bundle"]["file"]
        good = path.read_bytes()
        path.write_bytes(good[:-1] + bytes([good[-1] ^ 1]))                # same size, one bit flipped
        with self.assertRaisesRegex(bundle.BundleError, "SHA-256"):
            bundle.verify_feed(str(self.s.feed), self.s.keys.public)
        path.write_bytes(good + b"\0")
        with self.assertRaisesRegex(bundle.BundleError, "size"):
            bundle.verify_feed(str(self.s.feed), self.s.keys.public)
        path.write_bytes(good)
        bundle.verify_feed(str(self.s.feed), self.s.keys.public)

    def test_a_correctly_signed_bundle_that_the_index_does_not_list_is_still_refused(self):
        """The index is what is trusted: re-signing a different bundle under the same name changes its hash."""
        name = self.s.entries[0]["bundle"]["file"]
        evil = make_extension(Path(self.tmp.name) / "evil", "alpha", body="evil()\n" * 100)
        entry = bundle.build_bundle(evil, Path(self.tmp.name) / "evilout")
        shutil.copy(Path(self.tmp.name) / "evilout" / name, self.s.feed / name)
        bundle.sign_file(str(self.s.feed / name), self.s.keys.private)    # even a valid signature does not help
        with self.assertRaisesRegex(bundle.BundleError, "SHA-256"):
            bundle.verify_feed(str(self.s.feed), self.s.keys.public)

    def test_feed_name_schema_and_entries_are_validated(self):
        good = bundle.build_index(self.s.entries, FEED, "amd64")
        self.assertEqual(bundle.parse_index(bundle.compress(good), FEED)["feed"], FEED)
        with self.assertRaisesRegex(bundle.BundleError, "not 'extensions-16-amd64-9.9.9'"):
            bundle.parse_index(bundle.compress(good), "extensions-16-amd64-9.9.9")
        for mutate in (lambda i: i.update(schema="x"), lambda i: i.update(feed="packages-16-amd64-1.4.0"),
                       lambda i: i.update(extensions="no"), lambda i: i["extensions"][0].update(type="evil"),
                       lambda i: i["extensions"][0]["bundle"].update(sha256="zz"),
                       lambda i: i["extensions"][0]["bundle"].update(bytes=10 ** 9),
                       lambda i: i["extensions"][0]["bundle"].update(file="../../x.tar.xz"),
                       lambda i: i["extensions"].append(i["extensions"][0])):
            index = json.loads(good)
            mutate(index)
            with self.assertRaises(bundle.BundleError):
                bundle.parse_index(bundle.compress(json.dumps(index).encode()))
        with self.assertRaises(bundle.BundleError):
            bundle.build_index(self.s.entries, "latest", "amd64")
        with self.assertRaises(bundle.BundleError):
            bundle.build_index(self.s.entries + self.s.entries, FEED, "amd64")

    def test_an_index_that_expands_without_limit_is_refused(self):
        bomb = lzma.compress(b" " * (bundle.MAX_INDEX_RAW + 10), format=lzma.FORMAT_XZ)
        self.assertLess(len(bomb), 4096)
        with self.assertRaisesRegex(bundle.BundleError, "expands"):
            bundle.parse_index(bomb)
        with self.assertRaises(bundle.BundleError):
            bundle.parse_index(b"not xz at all")
        with self.assertRaises(bundle.BundleError):
            bundle.parse_index(bytes(bundle.MAX_INDEX_BYTES + 1))

    def test_resigning_with_the_release_key_changes_only_the_signatures(self):
        before = {p.name: p.read_bytes() for p in self.s.feed.iterdir() if not p.name.endswith(".sig")}
        release = Keys(self.tmp.name, "release")
        self.s.sign(release.private)
        after = {p.name: p.read_bytes() for p in self.s.feed.iterdir() if not p.name.endswith(".sig")}
        self.assertEqual(before, after)
        bundle.verify_feed(str(self.s.feed), release.public, FEED)
        with self.assertRaises(bundle.BundleError):
            bundle.verify_feed(str(self.s.feed), self.s.keys.public)

    def test_a_key_that_cannot_verify_is_a_refusal_not_a_crash(self):
        real_public = ROOT / "keys/pkg-repo-1.3.1.pub"
        self.assertFalse(bundle.verify_file(str(self.s.feed / bundle.INDEX_NAME), str(real_public)))
        self.assertFalse(bundle.verify_file(str(self.s.feed / bundle.INDEX_NAME), "/nonexistent.pub"))


def evil_tar(members):
    """A tar with the given (name, kind, data) members, for extraction tests."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for name, kind, data in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            if kind == tarfile.REGTYPE:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            else:
                info.linkname = data.decode() if isinstance(data, bytes) else ""
                archive.addfile(info)
    return buffer.getvalue()


class Extraction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "cache"
        self.good = make_extension(Path(self.tmp.name) / "src", "demo")
        self.entry = bundle.build_bundle(self.good, Path(self.tmp.name) / "out")
        self.raw = bundle.pack(self.good)

    def tearDown(self):
        self.tmp.cleanup()

    def files_outside(self):
        return [p for p in Path(self.tmp.name).rglob("*") if p.is_file() and self.dest not in p.parents
                and "src" not in p.parts and "out" not in p.parts]

    def test_a_good_bundle_extracts_with_normalised_modes_and_replaces_an_older_copy(self):
        target = Path(bundle.extract(self.raw, self.entry, str(self.dest)))
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["game.py", "manifest.json"])
        self.assertTrue(all(oct(p.stat().st_mode & 0o777) == "0o644" for p in target.iterdir()))
        (target / "stale").write_text("old")
        bundle.extract(self.raw, self.entry, str(self.dest))
        self.assertFalse((target / "stale").exists())
        self.assertEqual([p.name for p in self.dest.iterdir()], ["demo"], "no staging directory left behind")

    def test_hostile_archives_are_refused_and_nothing_escapes(self):
        manifest = (self.good / "manifest.json").read_bytes()
        game = (self.good / "game.py").read_bytes()
        reg = tarfile.REGTYPE
        cases = {
            "parent path": [("demo/", tarfile.DIRTYPE, b""), ("demo/../../escaped.py", reg, b"x")],
            "absolute path": [("/tmp/escaped.py", reg, b"x")],
            "wrong top directory": [("other/manifest.json", reg, manifest)],
            "symlink": [("demo/", tarfile.DIRTYPE, b""), ("demo/manifest.json", reg, manifest), ("demo/game.py", tarfile.SYMTYPE, b"/etc/passwd")],
            "hard link": [("demo/", tarfile.DIRTYPE, b""), ("demo/game.py", tarfile.LNKTYPE, b"demo/manifest.json")],
            "device": [("demo/", tarfile.DIRTYPE, b""), ("demo/dev", tarfile.CHRTYPE, b"")],
            "fifo": [("demo/", tarfile.DIRTYPE, b""), ("demo/pipe", tarfile.FIFOTYPE, b"")],
            "nested directory": [("demo/", tarfile.DIRTYPE, b""), ("demo/sub/", tarfile.DIRTYPE, b""), ("demo/sub/x.py", reg, b"x")],
            "backslash": [("demo/", tarfile.DIRTYPE, b""), ("demo\\x.py", reg, b"x")],
            "oversized member": [("demo/", tarfile.DIRTYPE, b""), ("demo/big.bin", reg, b"\0" * (bundle.MAX_FILE_BYTES + 1))],
            "too many files": [("demo/", tarfile.DIRTYPE, b"")] + [(f"demo/f{i}.py", reg, b"x") for i in range(bundle.MAX_FILES + 2)],
            "duplicate member": [("demo/", tarfile.DIRTYPE, b""), ("demo/a.py", reg, b"x"), ("demo/a.py", reg, b"y")],
            "dot-dot only": [("demo/..", reg, b"x")],
        }
        for label, members in cases.items():
            with self.subTest(label):
                with self.assertRaises(bundle.BundleError):
                    bundle.extract(evil_tar(members), self.entry, str(self.dest))
        self.assertEqual(self.files_outside(), [])
        self.assertFalse(Path("/tmp/escaped.py").exists())
        leftovers = [p for p in self.dest.iterdir()] if self.dest.exists() else []
        self.assertEqual(leftovers, [], "failed extractions leave nothing behind")

    def test_the_manifest_must_agree_with_the_signed_index_and_its_entry_hash(self):
        entry = dict(self.entry)
        for key, value in (("capabilities", ["draw"]), ("type", "game"), ("version", "9.9.9"), ("name", "Other"),
                           ("id", "demo2")):
            lie = dict(entry, **{key: value})
            with self.assertRaises(bundle.BundleError, msg=key):
                bundle.extract(self.raw, lie, str(self.dest))
        lie = dict(entry, min_size=[10, 10])
        with self.assertRaises(bundle.BundleError):
            bundle.extract(self.raw, lie, str(self.dest))
        tampered = make_extension(Path(self.tmp.name) / "t", "demo")
        (tampered / "game.py").write_text("evil = 1\n")
        with self.assertRaisesRegex(bundle.BundleError, "entry file"):
            bundle.extract(bundle.pack(tampered), self.entry, str(self.dest))

    def test_an_extracted_tree_loads_through_the_plugin_registry(self):
        bundle.extract(self.raw, self.entry, str(self.dest))
        plugin.write_index(str(self.dest))
        registry = plugin.Registry(str(self.dest))
        self.assertEqual(list(registry.plugins), ["demo"], registry.refused)
        self.assertEqual(registry.plugins["demo"].type, "tool")


class Downloads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Staged(self.tmp.name)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.s.feed))
        handler.log_message = lambda *a, **k: None
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.trace = Path(self.tmp.name) / "trace.jsonl"
        self.trace.write_text(json.dumps({"t_us": 1_000_000, "event": "trace_start"}) + "\n")

    def tearDown(self):
        self.server.shutdown()
        self.tmp.cleanup()

    def rows(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()][1:]

    def test_fetch_downloads_verifies_and_records_bytes_and_time_in_the_trace(self):
        trace = bundle.Trace(str(self.trace))
        entry = self.s.entries[0]
        got_index = bundle.fetch(f"{self.base}/{bundle.INDEX_NAME}", str(Path(self.tmp.name) / "i.xz"), bundle.MAX_INDEX_BYTES, trace)
        path = Path(self.tmp.name) / entry["bundle"]["file"]
        got = bundle.fetch(f"{self.base}/{entry['bundle']['file']}", str(path), entry["bundle"]["bytes"], trace)
        self.assertEqual(got, entry["bundle"]["bytes"])
        self.assertEqual(got_index, (self.s.feed / bundle.INDEX_NAME).stat().st_size)
        rows = self.rows()
        self.assertEqual([r["event"] for r in rows], ["ext_fetch", "ext_fetch"])
        self.assertEqual((rows[1]["name"], rows[1]["bytes"], rows[1]["status"]), (entry["bundle"]["file"], got, "ok"))
        self.assertGreaterEqual(rows[1]["dur_us"], 0)
        self.assertEqual(rows[1]["source"], "extensions")
        self.assertGreater(rows[1]["since_start_us"], 0)

    def test_a_download_larger_than_the_index_says_is_stopped(self):
        entry = self.s.entries[0]
        with self.assertRaisesRegex(bundle.BundleError, "larger"):
            bundle.fetch(f"{self.base}/{entry['bundle']['file']}", str(Path(self.tmp.name) / "x"), entry["bundle"]["bytes"] - 1,
                         bundle.Trace(str(self.trace)))
        self.assertEqual(self.rows()[-1]["status"], "refused")

    def test_offline_is_a_clear_error_not_a_traceback(self):
        self.server.shutdown()
        self.server.server_close()
        with self.assertRaisesRegex(bundle.BundleError, "could not download"):
            bundle.fetch(f"{self.base}/{bundle.INDEX_NAME}", str(Path(self.tmp.name) / "x"), 1000, bundle.Trace(str(self.trace)), timeout=2)
        self.assertNotEqual(self.rows()[-1]["status"], "ok")

    def test_only_https_or_loopback_http_is_allowed(self):
        for url in ("http://example.com/x", "ftp://example.com/x", "file:///etc/passwd", "gopher://x/", "https:///nohost"):
            self.assertFalse(bundle.allowed_url(url), url)
        for url in ("https://github.com/x", "http://127.0.0.1:8000/x", "http://localhost/x"):
            self.assertTrue(bundle.allowed_url(url), url)
        with self.assertRaises(bundle.BundleError):
            bundle.fetch("http://example.com/x", "/tmp/never", 10, bundle.Trace(str(self.trace)))

    def test_without_an_install_trace_fetch_still_works_and_writes_nothing(self):
        os.environ.pop("DAEMONARCHY_TRACE_FILE", None)
        trace = bundle.Trace(None)
        if trace.path:                                    # a real install trace exists on this machine: do not touch it
            trace.path = None
        got = bundle.fetch(f"{self.base}/{bundle.INDEX_NAME}", str(Path(self.tmp.name) / "i.xz"), bundle.MAX_INDEX_BYTES, trace)
        self.assertGreater(got, 0)


class StagingTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True)

    def test_stage_builds_signs_verifies_and_reports_the_four_games(self):
        keys = Keys(self.tmp.name, "dev")
        out = Path(self.tmp.name) / "feed"
        sources = [str(GAMES / g) for g in ("hordeshot", "shatter", "rockdrift", "wyrm")]
        run = self.run_tool("stage", *sources, "--out", str(out), "--feed", FEED, "--arch", "amd64",
                            "--key", keys.private, "--pubkey", keys.public)
        self.assertEqual(run.returncode, 0, run.stderr)
        names = sorted(p.name for p in out.iterdir())
        self.assertEqual(names, sorted([bundle.INDEX_NAME, bundle.INDEX_NAME + ".sig"]
                                       + [f"ext-{g}-1.0.0.tar.xz{s}" for g in ("hordeshot", "shatter", "rockdrift", "wyrm") for s in ("", ".sig")]))
        self.assertTrue(all(n.endswith((".xz", ".sig")) for n in names), "nothing uncompressed is published")
        for line in ("feed extensions-16-amd64-1.4.1", "ext-hordeshot-1.0.0.tar.xz", "bundles:"):
            self.assertIn(line, run.stdout)
        verify = self.run_tool("verify", str(out), "--pubkey", keys.public, "--feed", FEED)
        self.assertEqual((verify.returncode, "verified 4 extensions"), (0, "verified 4 extensions"))
        self.assertIn("verified 4 extensions", verify.stdout)
        bad = self.run_tool("verify", str(out), "--pubkey", str(ROOT / "keys/pkg-repo-1.3.1.pub"))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("signature", bad.stderr)

    def test_resign_then_verify_with_the_release_public_key(self):
        keys, release = Keys(self.tmp.name, "dev"), Keys(self.tmp.name, "release")
        out = Path(self.tmp.name) / "feed"
        self.assertEqual(self.run_tool("stage", str(GAMES / "wyrm"), "--out", str(out), "--feed", FEED, "--arch", "amd64",
                                       "--key", keys.private, "--pubkey", keys.public).returncode, 0)
        before = {p.name: p.read_bytes() for p in out.iterdir() if not p.name.endswith(".sig")}
        self.assertEqual(self.run_tool("sign", str(out), "--key", release.private).returncode, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir() if not p.name.endswith(".sig")})
        self.assertEqual(self.run_tool("verify", str(out), "--pubkey", release.public).returncode, 0)
        self.assertEqual(self.run_tool("verify", str(out), "--pubkey", keys.public).returncode, 1)

    def test_a_bad_feed_name_is_refused_by_the_tool(self):
        keys = Keys(self.tmp.name, "dev")
        run = self.run_tool("stage", str(GAMES / "wyrm"), "--out", str(Path(self.tmp.name) / "f"), "--feed", "latest",
                            "--arch", "amd64", "--key", keys.private, "--pubkey", keys.public)
        self.assertEqual(run.returncode, 1)
        self.assertIn("feed name", run.stderr)

    def test_the_games_sources_are_small_text_that_compresses(self):
        entries = [bundle.build_bundle(GAMES / g, Path(self.tmp.name) / "o") for g in ("hordeshot", "shatter", "rockdrift", "wyrm")]
        packed = sum(e["bundle"]["bytes"] for e in entries)
        raw = sum(e["bundle"]["raw_bytes"] for e in entries)
        self.assertLess(packed, raw * 0.5)


if __name__ == "__main__":
    unittest.main()
