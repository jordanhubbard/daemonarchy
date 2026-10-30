"""Extension bundles: compressed, content-identified, signed, and verified before anything runs.

A bundle is one extension as a deterministic tar (sorted, mtime 0, owner 0, normalised modes) compressed
with xz. A feed is a set of bundles plus a compressed index that lists them:

  ext-<id>-<version>.tar.xz        the bundle            (+ .sig, a detached signature)
  extensions-index.json.xz         the signed index      (+ .sig)

Everything published is compressed; there are no raw payloads. The index (schema
daemonarchy/extension-index@1) names each bundle's size and SHA-256, its uncompressed size and SHA-256,
and the facts the installer shows the user (name, description, type, capabilities, minimum terminal size).
Signatures are RSA/EC signatures over the compressed file's bytes, made and checked with `openssl dgst
-sha256` against the public key the image already pins for its package repository, so the image needs no
new trust anchor and no tool beyond the base system's openssl.

Verification order, all before anything runs: index signature; index schema and feed name; for each
bundle chosen, its size against the index (before and while reading), its SHA-256 and signature,
decompression bounded by the declared uncompressed size (so a small file cannot expand without limit), safe
extraction (regular files only, no links, no absolute or parent paths, bounded counts and sizes), and finally
that the extracted manifest agrees with the index entry and that the entry file's hash matches the manifest.
"""

import hashlib
import io
import json
import lzma
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

from . import compatible

INDEX_SCHEMA = "daemonarchy/extension-index@1"
INDEX_NAME = "extensions-index.json.xz"
TYPES = ("game", "tool", "animation", "visualizer")
CATEGORIES = dict(game="Games", tool="Tools", animation="Visuals", visualizer="Visuals")
ID = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
VERSION = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,4}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
FEED = re.compile(r"^extensions-[a-z0-9]+-[a-z0-9]+-\d{1,4}\.\d{1,4}\.\d{1,4}$")
MAX_INDEX_BYTES = 1 << 20
MAX_INDEX_RAW = 4 << 20
MAX_BUNDLE_BYTES = 8 << 20
MAX_RAW_BYTES = 16 << 20
MAX_FILES, MAX_FILE_BYTES = 64, 4 << 20
CAPABILITIES = ("draw", "input", "audio", "window")


class BundleError(Exception):
    """Something about a feed, index or bundle is not acceptable; the message says what."""


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def bundle_name(ext_id, version):
    return f"ext-{ext_id}-{version}.tar.xz"


# ---------------------------------------------------------------- making a bundle


def _normal(info, executable=False):
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    info.mode = 0o755 if (info.isdir() or executable) else 0o644
    return info


def pack(ext_dir):
    """Deterministic tar (bytes) of one extension directory, and its entries' names."""
    ext_dir = os.path.realpath(ext_dir)
    ext_id = os.path.basename(ext_dir)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        archive.addfile(_dir_info(ext_id))
        for name in sorted(os.listdir(ext_dir)):
            if name == "__pycache__":
                continue    # bytecode Python leaves beside the source is never part of an extension
            path = os.path.join(ext_dir, name)
            if os.path.islink(path) or not os.path.isfile(path) or name.startswith("."):
                raise BundleError(f"{ext_id}/{name}: only plain visible files can be bundled")
            with open(path, "rb") as stream:
                data = stream.read()
            info = _normal(tarfile.TarInfo(f"{ext_id}/{name}"))
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _dir_info(ext_id):
    info = tarfile.TarInfo(ext_id + "/")
    info.type = tarfile.DIRTYPE
    return _normal(info)


def compress(data):
    return lzma.compress(data, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=9 | lzma.PRESET_EXTREME)


def build_bundle(ext_dir, out_dir):
    """Write ext-<id>-<version>.tar.xz and return its index entry."""
    with open(os.path.join(ext_dir, "manifest.json"), encoding="utf-8") as stream:
        manifest = json.load(stream)
    problems = check_manifest_fields(manifest)
    if problems:
        raise BundleError(f"{os.path.basename(ext_dir)}: " + "; ".join(problems))
    if manifest["id"] != os.path.basename(os.path.realpath(ext_dir)):
        raise BundleError("the manifest id must match its directory name")
    raw = pack(ext_dir)
    packed = compress(raw)
    name = bundle_name(manifest["id"], manifest["version"])
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, name), "wb") as stream:
        stream.write(packed)
    return dict(
        id=manifest["id"], name=manifest["name"], version=manifest["version"], type=manifest["type"],
        category=CATEGORIES[manifest["type"]], description=manifest.get("description", ""),
        capabilities=list(manifest["capabilities"]), min_size=list(manifest.get("min_size", [0, 0])),
        api=manifest["api"],
        bundle=dict(file=name, bytes=len(packed), sha256=sha256_bytes(packed), raw_bytes=len(raw),
                    raw_sha256=sha256_bytes(raw)))


def check_manifest_fields(manifest):
    problems = []
    if not isinstance(manifest, dict):
        return ["manifest is not an object"]
    if not isinstance(manifest.get("id"), str) or not ID.match(manifest["id"]):
        problems.append("bad id")
    if not isinstance(manifest.get("version"), str) or not VERSION.match(manifest["version"]):
        problems.append("version must be X.Y.Z")
    if not isinstance(manifest.get("name"), str) or not 0 < len(manifest["name"]) <= 64:
        problems.append("bad name")
    if manifest.get("type") not in TYPES:
        problems.append("type must be one of " + ", ".join(TYPES))
    caps = manifest.get("capabilities")
    if not isinstance(caps, list) or not caps or any(c not in CAPABILITIES for c in caps) or "draw" not in caps:
        problems.append("capabilities must be a non-empty subset of " + ", ".join(CAPABILITIES) + " including draw")
    if not isinstance(manifest.get("api"), str) or not compatible(manifest["api"]):
        problems.append("unsupported SDK api")
    if not isinstance(manifest.get("entry_sha256"), str) or not HEX.match(manifest["entry_sha256"]):
        problems.append("entry_sha256 is not sealed")
    return problems


def build_index(entries, feed, arch, generated=None):
    if not FEED.match(feed):
        raise BundleError(f"feed name {feed!r} is not extensions-<os>-<arch>-X.Y.Z")
    ids = [e["id"] for e in entries]
    if len(set(ids)) != len(ids):
        raise BundleError("duplicate extension ids")
    index = dict(schema=INDEX_SCHEMA, feed=feed, arch=arch,
                 generated=generated or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 extensions=sorted(entries, key=lambda e: e["id"]))
    return (json.dumps(index, indent=2, sort_keys=True) + "\n").encode("utf-8")


# ---------------------------------------------------------------- signatures (openssl)


def _openssl(*args):
    try:
        done = subprocess.run(["openssl", *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise BundleError(f"openssl is not usable: {error}") from error
    return done.returncode, (done.stdout + done.stderr).strip()


def sign_file(path, key):
    """Write `path`.sig: an RSA/EC signature over the file's bytes."""
    code, out = _openssl("dgst", "-sha256", "-sign", key, "-out", path + ".sig", path)
    if code != 0:
        raise BundleError(f"signing {os.path.basename(path)} failed: {out[:200]}")


def verify_file(path, pubkey):
    """True only if `path`.sig is a valid signature over the file's bytes by `pubkey`."""
    if not os.path.isfile(path + ".sig"):
        return False
    code, out = _openssl("dgst", "-sha256", "-verify", pubkey, "-signature", path + ".sig", path)
    return code == 0 and "Verified OK" in out


# ---------------------------------------------------------------- reading and checking


def decompress_bounded(data, limit):
    """Decompress xz `data`, refusing to produce more than `limit` bytes."""
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    try:
        out = decoder.decompress(data, max_length=limit + 1)
    except lzma.LZMAError as error:
        raise BundleError(f"not a valid xz stream: {error}") from error
    if len(out) > limit:
        raise BundleError("expands beyond its declared size")
    if not decoder.eof:
        raise BundleError("truncated or oversized xz stream")
    return out


def parse_index(compressed, expected_feed=None):
    if len(compressed) > MAX_INDEX_BYTES:
        raise BundleError("index is too large")
    try:
        index = json.loads(decompress_bounded(compressed, MAX_INDEX_RAW))
    except ValueError as error:
        raise BundleError(f"index is not JSON: {error}") from error
    if not isinstance(index, dict) or index.get("schema") != INDEX_SCHEMA:
        raise BundleError("index has the wrong schema")
    if not isinstance(index.get("feed"), str) or not FEED.match(index["feed"]):
        raise BundleError("index names no valid feed")
    if expected_feed and index["feed"] != expected_feed:
        raise BundleError(f"index is for feed {index['feed']!r}, not {expected_feed!r}")
    extensions = index.get("extensions")
    if not isinstance(extensions, list):
        raise BundleError("index lists no extensions")
    seen = set()
    for entry in extensions:
        check_entry(entry)
        if entry["id"] in seen:
            raise BundleError("duplicate extension id in the index")
        seen.add(entry["id"])
    return index


def check_entry(entry):
    if not isinstance(entry, dict):
        raise BundleError("index entry is not an object")
    problems = check_manifest_fields(dict(entry, entry_sha256="0" * 64))
    bundle = entry.get("bundle")
    if not isinstance(bundle, dict):
        problems.append("no bundle")
    else:
        if bundle.get("file") != bundle_name(entry.get("id"), entry.get("version")):
            problems.append("bundle file name does not match id and version")
        for key in ("sha256", "raw_sha256"):
            if not isinstance(bundle.get(key), str) or not HEX.match(bundle[key]):
                problems.append(f"bad {key}")
        for key, cap in (("bytes", MAX_BUNDLE_BYTES), ("raw_bytes", MAX_RAW_BYTES)):
            if not isinstance(bundle.get(key), int) or isinstance(bundle.get(key), bool) or not 0 < bundle[key] <= cap:
                problems.append(f"bad {key}")
    size = entry.get("min_size", [0, 0])
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and 0 <= v <= 400 for v in size)):
        problems.append("bad min_size")
    if problems:
        raise BundleError(f"index entry {entry.get('id')!r}: " + "; ".join(problems))


def verified_index(index_path, pubkey, expected_feed=None):
    """The parsed index, after its signature and structure check out."""
    if not verify_file(index_path, pubkey):
        raise BundleError("the extension index signature is not valid for the pinned key")
    with open(index_path, "rb") as stream:
        return parse_index(stream.read(MAX_INDEX_BYTES + 1), expected_feed)


def verify_bundle(path, entry, pubkey):
    """Check a bundle file against its index entry and signature. Returns the uncompressed tar bytes."""
    info = entry["bundle"]
    size = os.path.getsize(path)
    if size != info["bytes"]:
        raise BundleError(f"{entry['id']}: size {size} is not the {info['bytes']} the index lists")
    if sha256_file(path) != info["sha256"]:
        raise BundleError(f"{entry['id']}: SHA-256 does not match the index")
    if not verify_file(path, pubkey):
        raise BundleError(f"{entry['id']}: signature is not valid for the pinned key")
    with open(path, "rb") as stream:
        raw = decompress_bounded(stream.read(), info["raw_bytes"])
    if len(raw) != info["raw_bytes"] or sha256_bytes(raw) != info["raw_sha256"]:
        raise BundleError(f"{entry['id']}: uncompressed content does not match the index")
    return raw


def extract(raw, entry, dest_root):
    """Safely unpack a verified tar into dest_root/<id>; returns that directory.

    Only regular files and the one directory are accepted; no links, devices, absolute or parent paths;
    at most MAX_FILES files of at most MAX_FILE_BYTES each. Modes are reset to 0644, 0755 for the directory.
    """
    ext_id = entry["id"]
    os.makedirs(dest_root, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".extract-", dir=dest_root)
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            members = archive.getmembers()
            if len(members) > MAX_FILES + 1:
                raise BundleError("too many files")
            names = set()
            for member in members:
                name = member.name.rstrip("/")
                parts = name.split("/")
                if (member.name.startswith("/") or "\\" in member.name or ".." in parts or parts[0] != ext_id
                        or len(parts) > 2 or not all(parts)):
                    raise BundleError(f"unsafe path in bundle: {member.name!r}")
                if member.isdir():
                    if len(parts) != 1:
                        raise BundleError("nested directories are not allowed")
                    continue
                if not member.isreg() or member.size > MAX_FILE_BYTES or name in names:
                    raise BundleError(f"unacceptable member: {member.name!r}")
                names.add(name)
            target = os.path.join(stage, ext_id)
            os.mkdir(target, 0o755)
            for member in members:
                if member.isreg():
                    data = archive.extractfile(member).read()
                    path = os.path.join(stage, member.name)
                    with open(path, "wb") as out:
                        out.write(data)
                    os.chmod(path, 0o644)
        check_extracted(target, entry)
        final = os.path.join(dest_root, ext_id)
        if os.path.isdir(final):
            shutil.rmtree(final)
        os.rename(target, final)
        return final
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def check_extracted(directory, entry):
    """The extracted manifest must say what the index said, and its entry file must match its hash."""
    try:
        with open(os.path.join(directory, "manifest.json"), encoding="utf-8") as stream:
            manifest = json.load(stream)
    except (OSError, ValueError) as error:
        raise BundleError(f"{entry['id']}: unreadable manifest: {error}") from error
    for key in ("id", "name", "version", "type", "capabilities", "api"):
        if manifest.get(key) != entry.get(key):
            raise BundleError(f"{entry['id']}: manifest {key} differs from the signed index")
    if list(manifest.get("min_size", [0, 0])) != list(entry.get("min_size", [0, 0])):
        raise BundleError(f"{entry['id']}: manifest min_size differs from the signed index")
    entry_file = os.path.join(directory, str(manifest.get("entry", "")))
    if not os.path.isfile(entry_file) or sha256_file(entry_file) != manifest.get("entry_sha256"):
        raise BundleError(f"{entry['id']}: entry file does not match its manifest")


def verify_feed(directory, pubkey, expected_feed=None):
    """Verify a whole staged or downloaded feed directory; returns a list of report rows."""
    index = verified_index(os.path.join(directory, INDEX_NAME), pubkey, expected_feed)
    rows = [dict(file=INDEX_NAME, bytes=os.path.getsize(os.path.join(directory, INDEX_NAME)),
                 sha256=sha256_file(os.path.join(directory, INDEX_NAME)))]
    for entry in index["extensions"]:
        path = os.path.join(directory, entry["bundle"]["file"])
        raw = verify_bundle(path, entry, pubkey)
        with tempfile.TemporaryDirectory() as scratch:
            extract(raw, entry, scratch)
        rows.append(dict(file=entry["bundle"]["file"], bytes=entry["bundle"]["bytes"], sha256=entry["bundle"]["sha256"],
                         raw_bytes=entry["bundle"]["raw_bytes"]))
    return index, rows


# ---------------------------------------------------------------- fetching


class Trace:
    """Appends to the installer's trace (docs/install-trace.md) when one is running; otherwise does nothing."""

    DEFAULT = "/tmp/daemonarchy-install-trace.jsonl"

    def __init__(self, path=None, now_us=lambda: time.time_ns() // 1000):
        self.path = path or os.environ.get("DAEMONARCHY_TRACE_FILE") or (self.DEFAULT if os.path.exists(self.DEFAULT) else None)
        self.now_us = now_us
        self.start = 0
        start = os.environ.get("DAEMONARCHY_TRACE_START_US", "")
        if start.isdigit():
            self.start = int(start)
        elif self.path:
            try:
                with open(self.path, encoding="utf-8") as stream:
                    self.start = int(json.loads(stream.readline()).get("t_us", 0))
            except (OSError, ValueError, TypeError):
                self.start = 0

    def event(self, event_name, /, **fields):
        if not self.path:
            return
        now = self.now_us()
        row = dict(t_us=now, since_start_us=max(0, now - self.start), event=event_name, source="extensions")
        row.update(fields)
        try:
            with open(self.path, "a", encoding="utf-8") as out:
                out.write(json.dumps(row, separators=(",", ":")) + "\n")
        except OSError:
            pass


def allowed_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return True
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")


def fetch(url, dest, max_bytes, trace=None, name=None, timeout=30, opener=urllib.request.urlopen):
    """Download `url` to `dest`, refusing more than `max_bytes`. Records name, bytes and time in the trace."""
    trace = trace or Trace()
    if not allowed_url(url):
        raise BundleError("extension downloads need https")
    started = time.monotonic()
    got, status = 0, "ok"
    try:
        with opener(urllib.request.Request(url, headers={"User-Agent": "daemonarchy-extensions"}), timeout=timeout) as reply, \
                open(dest, "wb") as out:
            length = reply.headers.get("Content-Length") if hasattr(reply, "headers") else None
            if length and length.isdigit() and int(length) > max_bytes:
                raise BundleError("download is larger than the index allows")
            while True:
                block = reply.read(65536)
                if not block:
                    break
                got += len(block)
                if got > max_bytes:
                    raise BundleError("download is larger than the index allows")
                out.write(block)
    except BundleError:
        status = "refused"
        raise
    except (OSError, ValueError) as error:
        status = type(error).__name__
        raise BundleError(f"could not download {name or url}: {type(error).__name__}") from error
    finally:
        trace.event("ext_fetch", name=name or os.path.basename(url), bytes=got,
                    dur_us=int((time.monotonic() - started) * 1e6), status=status)
    return got
