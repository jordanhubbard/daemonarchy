#!/usr/bin/env python3
"""Check virt-fw-vars JSON evidence for the isolated append-to-db test."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import uuid


def variables(path):
    data = json.loads(path.read_text())
    if data.get("version") != 2:
        raise ValueError("Expected virt-fw-vars JSON version 2")
    result = {(entry["name"], entry["guid"]): entry for entry in data["variables"]}
    if len(result) != len(data["variables"]):
        raise ValueError("Duplicate firmware variables")
    return result


def check(args):
    before, after = variables(args.before), variables(args.after)
    if set(before) != set(after):
        raise ValueError("Firmware variable set changed")
    db_key = ("db", "d719b2cb-3d3a-4596-a3bc-dad00e67656f")
    for name in ("PK", "KEK", "db", "dbx"):
        if not any(key[0] == name for key in before):
            raise ValueError(f"Missing prior trust database: {name}")
    for key in before:
        if key != db_key and before[key] != after[key]:
            raise ValueError(f"Non-db firmware variable changed: {key[0]}")
    old, new = before[db_key], after[db_key]
    if {k: v for k, v in old.items() if k not in ("data", "time")} != {
            k: v for k, v in new.items() if k not in ("data", "time")}:
        raise ValueError("db attributes or identity changed")
    # Authenticated variable updates can advance EFI_TIME. The db update
    # timestamp is metadata, not a pre-existing trust entry to preserve.
    if old.get("time") != new.get("time"):
        def timestamp(value):
            raw = bytes.fromhex(value)
            if len(raw) != 16:
                raise ValueError("Invalid authenticated-variable timestamp")
            return (datetime(int.from_bytes(raw[:2], "little"), *raw[2:7]),
                    int.from_bytes(raw[8:12], "little"))
        if timestamp(new.get("time", "")) < timestamp(old.get("time", "")):
            raise ValueError("db authenticated-update timestamp moved backwards")
    old_bytes, new_bytes = bytes.fromhex(old["data"]), bytes.fromhex(new["data"])
    certificate = subprocess.check_output([
        "openssl", "x509", "-in", str(args.certificate), "-outform", "DER"])
    if (not new_bytes.startswith(old_bytes) or len(new_bytes) <= len(old_bytes) or
            certificate in old_bytes or certificate not in new_bytes[len(old_bytes):]):
        raise ValueError("db did not preserve its prior bytes and append the expected certificate")
    appended = new_bytes[len(old_bytes):]
    expected_size = 28 + 16 + len(certificate)
    x509_type = uuid.UUID("a5c059a1-94e4-4aa7-87b5-ab155c2bf072").bytes_le
    if (len(appended) != expected_size or appended[:16] != x509_type or
            struct.unpack_from("<III", appended, 16) != (
                expected_size, 0, 16 + len(certificate)) or
            appended[44:] != certificate):
        raise ValueError("db must append exactly one X.509 signature entry for the expected certificate")
    print("PASS: prior db entries and all other firmware variables preserved")
    print("Appended certificate DER SHA256=" + hashlib.sha256(certificate).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--certificate", type=Path, required=True)
    args = parser.parse_args()
    try:
        check(args)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Enrollment evidence failed: {error}\n")
