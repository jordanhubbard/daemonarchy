#!/usr/bin/env python3
"""Immutable verified archive retention. Trust admission belongs to the native producer."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

HEX = re.compile(r"[0-9a-f]{64}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def pin(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("expected SHA-256 hex identity")
    return value


def selection_identity(catalogue, name, package):
    """Construct a transport identity, not a compilation or ABI compatibility key."""
    if (not isinstance(catalogue, dict)
            or set(catalogue) != {"meta.conf", "packagesite.pkg", "data.pkg", "public_key"}):
        raise ValueError("missing selected signed catalogue identity")
    for value in catalogue.values():
        if not isinstance(value, str):
            raise ValueError("invalid signed catalogue identity")
        pin(value.removeprefix("sha256:"))
    if not isinstance(name, str) or not name:
        raise ValueError("missing package name")
    fields = ("version", "abi", "archive_checksum", "archive_path", "download_bytes")
    if any(key not in package for key in fields):
        raise ValueError("incomplete package selection")
    if any(not isinstance(package[key], str) or not package[key] for key in fields[:-1]):
        raise ValueError("invalid package identity")
    if type(package["download_bytes"]) is not int or package["download_bytes"] <= 0:
        raise ValueError("invalid package byte count")
    return dict(schema="daemonarchy/verified-cache-selection@1", catalogue=catalogue,
                name=name, **{key: package[key] for key in fields})


class VerifiedCache:
    """Append-only namespace: corrupt entries fail closed and are never replaced."""
    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ValueError("cache root must be absolute")
        for path in (self.root, *self.root.parents):
            if path.is_symlink():
                raise ValueError("cache paths must not contain symlinks")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name in ("objects", "selections", "pending"):
            path = self.root / name
            path.mkdir(mode=0o700, exist_ok=True)
            if path.is_symlink() or not path.is_dir():
                raise ValueError("cache namespace is not a directory")
        self.events = []

    def key(self, identity):
        # Revalidate all bindings rather than accepting opaque arbitrary keys.
        checked = selection_identity(identity["catalogue"], identity["name"], identity)
        if checked != identity:
            raise ValueError("cache selection schema or fields differ")
        return hashlib.sha256(canonical(identity)).hexdigest()

    @staticmethod
    def stream(path):
        stream = os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb")
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            stream.close()
            raise ValueError("cache entry is not a regular file")
        return stream

    def lookup(self, identity, record_event=True):
        start = time.monotonic()
        key = self.key(identity)
        record = self.root / "selections" / (key + ".json")
        try:
            with self.stream(record) as stream:
                raw = stream.read(65537)
                if len(raw) > 65536:
                    raise ValueError("oversized cache selection record")
                selected = json.loads(raw)
        except FileNotFoundError:
            if record_event:
                self.events.append(dict(kind="miss", selection=key, bytes_saved=0, seconds=time.monotonic()-start))
            return None
        if selected.get("identity") != identity or selected.get("schema") != "daemonarchy/verified-cache-entry@1":
            raise ValueError("cache entry selection binding differs")
        digest = pin(selected["sha256"])
        stream = self.stream(self.root / "objects" / digest)
        try:
            if os.fstat(stream.fileno()).st_size != identity["download_bytes"]:
                raise ValueError("corrupt cache entry size")
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("corrupt cache entry SHA-256")
            stream.seek(0)
        except BaseException:
            stream.close()
            raise
        if record_event:
            self.events.append(dict(kind="hit", selection=key, sha256=digest,
                                    bytes_saved=identity["download_bytes"], seconds=time.monotonic()-start))
        return stream

    def retain(self, identity, source, expected_sha256):
        """Call only after native signature and package checksum verification succeeds."""
        key = self.key(identity)
        expected_sha256 = pin(expected_sha256.removeprefix("sha256:"))
        existing = self.lookup(identity, record_event=False)
        if existing is not None:
            with existing:
                if hashlib.file_digest(existing, "sha256").hexdigest() != expected_sha256:
                    raise ValueError("existing selected cache binding differs")
            self.events.append(dict(kind="retained_existing", selection=key, sha256=expected_sha256))
            return
        temporary = self.root / "pending" / uuid.uuid4().hex
        # Failed pending products are deliberately retained for diagnosis.
        with self.stream(source) as incoming, temporary.open("xb") as outgoing:
            digest = hashlib.sha256()
            total = 0
            while chunk := incoming.read(1024 * 1024):
                total += len(chunk)
                if total > identity["download_bytes"]:
                    raise ValueError("retained archive exceeds selected size")
                digest.update(chunk)
                outgoing.write(chunk)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if total != identity["download_bytes"] or digest.hexdigest() != expected_sha256:
            raise ValueError("retained archive differs from verified SHA-256/size")
        os.chmod(temporary, 0o444)
        target = self.root / "objects" / expected_sha256
        try:
            os.link(temporary, target)
        except FileExistsError:
            with self.stream(target) as stream:
                if (os.fstat(stream.fileno()).st_size != total
                        or hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256):
                    raise ValueError("existing content-addressed object is corrupt")
        entry = dict(schema="daemonarchy/verified-cache-entry@1", identity=identity, sha256=expected_sha256)
        record = self.root / "pending" / (uuid.uuid4().hex + ".json")
        with record.open("xb") as stream:
            stream.write(canonical(entry))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(record, 0o444)
        try:
            os.link(record, self.root / "selections" / (key + ".json"))
        except FileExistsError:
            with self.stream(self.root / "selections" / (key + ".json")) as stream:
                if stream.read(65537) != canonical(entry):
                    raise ValueError("existing selected cache binding differs")
        self.events.append(dict(kind="retained", selection=key, sha256=expected_sha256, bytes=total))

    def summary(self):
        return dict(hits=sum(e["kind"] == "hit" for e in self.events),
                    misses=sum(e["kind"] == "miss" for e in self.events),
                    bytes_saved=sum(e.get("bytes_saved", 0) for e in self.events),
                    verification_seconds=sum(e.get("seconds", 0) for e in self.events), events=list(self.events))
