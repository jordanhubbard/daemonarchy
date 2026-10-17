#!/usr/bin/env python3
"""Hash native amd64 modules from the already validated release package cache."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile


def output(*command):
    return subprocess.check_output(command, text=True).strip()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(args):
    modules, packages = {}, []
    for package in sorted(args.repo.resolve(strict=True).glob("*kmod*.pkg")):
        paths = [name for name in output("pkg", "query", "-F", str(package), "%Fp").splitlines()
                 if name.startswith("/boot/modules/") and name.endswith(".ko")]
        if not paths:
            continue
        abi = output("pkg", "query", "-F", str(package), "%q")
        annotations = output("pkg", "query", "-F", str(package), "%At %Av").splitlines()
        if abi != "FreeBSD:16:amd64" or f"FreeBSD_version {args.osversion}" not in annotations:
            raise ValueError(f"{package.name}: module ABI/snapshot annotation mismatch")
        for name in paths:
            path = PurePosixPath(name)
            if ".." in path.parts or any(c in name for c in "\r\n\0*?[]"):
                raise ValueError("Invalid module archive path")
            h = hashlib.sha256()
            with tempfile.TemporaryFile() as errors:
                process = subprocess.Popen(["tar", "-xOf", str(package), "--", name],
                                           stdout=subprocess.PIPE, stderr=errors)
                header = process.stdout.read(64)
                # Modules must be relocatable native objects, never an alternate
                # executable kernel hidden under a .ko name.
                if (header[:6] != b"\x7fELF\x02\x01" or
                        header[16:20] != b"\x01\x00\x3e\x00"):
                    process.stdout.close()
                    process.wait()
                    raise ValueError(f"{package.name}: {name} is not an amd64 relocatable module")
                h.update(header)
                for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
                    h.update(block)
                process.stdout.close()
                if process.wait() != 0:
                    raise ValueError(f"Cannot read {name} from {package.name}")
            fingerprint = h.hexdigest()
            if name in modules and modules[name] != fingerprint:
                raise ValueError(f"Conflicting release modules at {name}")
            modules[name] = fingerprint
        packages.append(dict(file=package.name, sha256=digest(package),
                             origin=output("pkg", "query", "-F", str(package), "%o")))
    if not modules:
        raise ValueError("Release repository contains no admissible native modules")
    return dict(schema=1, source_revision=args.source_revision, osversion=args.osversion,
                packages=packages, modules=dict(sorted(modules.items())))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path, help="release repository's All directory")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--osversion", type=int, required=True)
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.source_revision) or args.osversion != 1600028:
        parser.error("Use the selected full source revision and qualified osversion 1600028")
    try:
        print(json.dumps(inventory(args), indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Inventory failed: {error}\n")
