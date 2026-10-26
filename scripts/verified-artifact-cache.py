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
    if not isinstance(package, dict):
        raise ValueError("invalid package selection mapping")
    fields = ("version", "abi", "archive_checksum", "archive_path", "download_bytes")
    if any(key not in package for key in fields):
        raise ValueError("incomplete package selection")
    if any(not isinstance(package[key], str) or not package[key] for key in fields[:-1]):
        raise ValueError("invalid package identity")
    if type(package["download_bytes"]) is not int or package["download_bytes"] <= 0:
        raise ValueError("invalid package byte count")
    return dict(schema="daemonarchy/verified-cache-selection@1", catalogue=catalogue,
                name=name, **{key: package[key] for key in fields})


class NativeAuthenticatedCatalogue:
    """Trusted producer witness, constructed only after fresh native authentication.

    This class cannot authenticate a signature itself. Its caller owns that trust
    boundary, just as the caller of retain owns native archive verification.
    """
    def __init__(self, catalogue, packages, database_sha256):
        self.database_sha256 = pin(database_sha256)
        self.selections = {name: selection_identity(catalogue, name, row)
                           for name, row in packages.items()}
        # Snapshot the authenticated selection; later caller mutations cannot
        # silently expand what this authentication witness selects.
        self.selections = json.loads(canonical(self.selections))

    def require(self, identity):
        if self.selections.get(identity["name"]) != identity:
            raise ValueError("candidate does not match freshly authenticated selection")


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
        self.candidate_index = None
        self.candidate_offers = {}

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

    def verified_object(self, digest, size):
        stream = self.stream(self.root / "objects" / pin(digest))
        try:
            if os.fstat(stream.fileno()).st_size != size:
                raise ValueError("corrupt cache entry size")
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("corrupt cache entry SHA-256")
            stream.seek(0)
        except BaseException:
            stream.close()
            raise
        return stream

    def refuse_corrupt(self, key, start, error, digest=None):
        # Measure the refusal; never repair, replace, delete or redirect it.
        self.events.append(dict(kind="corrupt_refused", selection=key, sha256=digest,
                                reason=str(error), bytes_saved=0, seconds=time.monotonic()-start))

    @staticmethod
    def candidate_key(identity):
        # A transport candidate may move archive path or catalogue/signing key.
        # It must still pass the current selected native checksum verification.
        fields = ("name", "version", "abi", "archive_checksum", "download_bytes")
        return hashlib.sha256(canonical({key: identity[key] for key in fields})).hexdigest()

    def index_candidates(self):
        index = {}
        with os.scandir(self.root / "selections") as entries:
            for count, entry in enumerate(entries, 1):
                if count > 100000:
                    raise ValueError("retained candidate inventory exceeds bounded scan")
                with self.stream(entry.path) as stream:
                    raw = stream.read(65537)
                if len(raw) > 65536:
                    raise ValueError("oversized retained candidate record")
                record = json.loads(raw)
                if (not isinstance(record, dict)
                        or record.get("schema") != "daemonarchy/verified-cache-entry@1"
                        or entry.name != self.key(record["identity"]) + ".json"):
                    raise ValueError("retained candidate record binding differs")
                pin(record["sha256"])
                index.setdefault(self.candidate_key(record["identity"]), []).append(record)
        self.candidate_index = index

    def candidate(self, identity, authenticated):
        """Offer retained bytes for fresh native verification; never admit a hit."""
        start = time.monotonic()
        key = self.key(identity)
        if not isinstance(authenticated, NativeAuthenticatedCatalogue):
            raise ValueError("candidate reuse requires fresh native catalogue authentication")
        authenticated.require(identity)
        if self.candidate_index is None:
            try:
                self.index_candidates()
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.refuse_corrupt(key, start, error)
                raise
        records = self.candidate_index.get(self.candidate_key(identity), [])
        if not records:
            return None
        digests = {row["sha256"] for row in records}
        if len(digests) != 1:
            raise ValueError("ambiguous retained candidate archive identities")
        digest = next(iter(digests))
        try:
            stream = self.verified_object(digest, identity["download_bytes"])
        except (OSError, ValueError) as error:
            self.refuse_corrupt(key, start, error, digest)
            raise
        offered = dict(selection=key, sha256=digest,
                       source_selections=sorted(self.key(row["identity"]) for row in records),
                       authenticated_database_sha256=authenticated.database_sha256)
        self.candidate_offers[key] = offered
        self.events.append(dict(kind="candidate_offered", **offered,
                                bytes=identity["download_bytes"], seconds=time.monotonic()-start))
        return stream

    def record_candidate_admission(self, key, digest, size):
        offer = self.candidate_offers.pop(key, None)
        if offer is not None:
            if offer["sha256"] != digest:
                raise ValueError("native verified archive differs from retained candidate")
            self.events.append(dict(kind="candidate_admitted", **offer, bytes=size,
                                    native_selected_checksum_reverified=True,
                                    runtime_qualification_copied=False))

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
        except (OSError, ValueError) as error:
            if record_event:
                self.refuse_corrupt(key, start, error)
            raise
        digest = None
        try:
            if (not isinstance(selected, dict) or selected.get("identity") != identity
                    or selected.get("schema") != "daemonarchy/verified-cache-entry@1"):
                raise ValueError("cache entry selection binding differs")
            digest = pin(selected.get("sha256"))
            stream = self.verified_object(digest, identity["download_bytes"])
        except (OSError, ValueError) as error:
            if record_event:
                self.refuse_corrupt(key, start, error, digest)
            raise
        if record_event:
            self.events.append(dict(kind="hit", selection=key, sha256=digest,
                                    bytes_saved=identity["download_bytes"], seconds=time.monotonic()-start))
        return stream

    def retain(self, identity, source, expected_sha256):
        """Call only after native signature and package checksum verification succeeds."""
        key = self.key(identity)
        expected_sha256 = pin(expected_sha256.removeprefix("sha256:"))
        offer = self.candidate_offers.get(key)
        if offer is not None and offer["sha256"] != expected_sha256:
            raise ValueError("native verified archive differs from retained candidate")
        existing = self.lookup(identity, record_event=False)
        if existing is not None:
            with existing:
                if hashlib.file_digest(existing, "sha256").hexdigest() != expected_sha256:
                    raise ValueError("existing selected cache binding differs")
            self.events.append(dict(kind="retained_existing", selection=key, sha256=expected_sha256))
            self.record_candidate_admission(key, expected_sha256, identity["download_bytes"])
            return
        target = self.root / "objects" / expected_sha256
        try:
            existing_blob = self.verified_object(expected_sha256, identity["download_bytes"])
        except FileNotFoundError:
            existing_blob = None
        if existing_blob is not None:
            existing_blob.close()
            # Reverify the freshly native-checked source, then associate the
            # existing object without copying a duplicate archive into pending.
            with self.stream(source) as incoming:
                total = os.fstat(incoming.fileno()).st_size
                if (total != identity["download_bytes"]
                        or hashlib.file_digest(incoming, "sha256").hexdigest() != expected_sha256):
                    raise ValueError("retained archive differs from verified SHA-256/size")
        else:
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
            try:
                os.link(temporary, target)
            except FileExistsError:
                with self.verified_object(expected_sha256, total):
                    pass
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
        self.candidate_index = None
        self.record_candidate_admission(key, expected_sha256, total)

    def summary(self):
        return dict(hits=sum(e["kind"] == "hit" for e in self.events),
                    misses=sum(e["kind"] == "miss" for e in self.events),
                    corrupt_refusals=sum(e["kind"] == "corrupt_refused" for e in self.events),
                    bytes_saved=sum(e.get("bytes_saved", 0) for e in self.events),
                    candidate_requests=sum(e["kind"] == "candidate_offered" for e in self.events),
                    candidate_bytes_offered=sum(e.get("bytes", 0) for e in self.events if e["kind"] == "candidate_offered"),
                    candidate_bytes_admitted=sum(e.get("bytes", 0) for e in self.events if e["kind"] == "candidate_admitted"),
                    verification_seconds=sum(e.get("seconds", 0) for e in self.events), events=list(self.events))
