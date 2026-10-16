#!/usr/bin/env python3
"""Check virt-fw-vars JSON evidence for the isolated append-to-db test."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


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
    if {k: v for k, v in old.items() if k != "data"} != {
            k: v for k, v in new.items() if k != "data"}:
        raise ValueError("db attributes or identity changed")
    old_bytes, new_bytes = bytes.fromhex(old["data"]), bytes.fromhex(new["data"])
    certificate = subprocess.check_output([
        "openssl", "x509", "-in", str(args.certificate), "-outform", "DER"])
    if (not new_bytes.startswith(old_bytes) or len(new_bytes) <= len(old_bytes) or
            certificate in old_bytes or certificate not in new_bytes[len(old_bytes):]):
        raise ValueError("db did not preserve its prior bytes and append the expected certificate")
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
