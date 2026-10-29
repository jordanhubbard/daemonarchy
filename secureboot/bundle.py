#!/usr/bin/env python3
"""Create a signed maintenance bundle from an already signed staging boot tree.

Run only on the protected signing host. No private material enters the archive.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

MANAGED = (
    "boot/kernel.secure/kernel", "boot/loader.efi", "boot/loader_normal.efi",
    "boot/manifest", "boot/manifest.sig", "boot/manifest.certs",
    "boot/runtime.manifest", "boot/runtime.manifest.sig", "boot/runtime.manifest.certs",
    "boot/lua/local.lua", "boot/lua/brand-daemonarchy.lua", "boot/daemonarchy-secureboot.conf",
    "usr/local/sbin/daemonarchy-secureboot",
)
SOURCE_OSVERSIONS = {
    "bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf": 1600028,
    "02984cfbe95c063f130ae20d7ea6ed520df88a8f": 1600029,
    "faac40107e936c2e133bd938ca56097d3cfed1c4": 1600029,
    "d63d77f4eb3cc29e16510f7bdec73602e27c2844": 1600029,
    "68512eda0d047bba542749b26e5ce1926a5c2ef1": 1600029,
    "f6f30e8e17139e03f1262cc48a5f8acb829bb467": 1600029,
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(args):
    root = args.root.resolve(strict=True)
    key = args.key.resolve(strict=True)
    if root == Path("/") or key.is_relative_to(root) or key.stat().st_mode & 0o077:
        raise ValueError("Use a staging tree and an external owner-only signing key")
    if args.out.exists() or Path(str(args.out) + ".sig").exists():
        raise ValueError("Output exists; preserve existing signed artifacts")
    public = subprocess.check_output([
        "openssl", "x509", "-in", str(args.certificate), "-noout", "-pubkey"])
    if public != subprocess.check_output(["openssl", "pkey", "-in", str(key), "-pubout"]):
        raise ValueError("Certificate/key mismatch")
    receipt = json.loads(args.build_receipt.read_text())
    osversion = SOURCE_OSVERSIONS.get(receipt.get("base_source"))
    if (receipt.get("boot_pool_selector") != 1 or
            osversion is None or
            receipt.get("trust_anchor_sha256") != digest(args.certificate) or
            receipt.get("kernel_sha256") != digest(root / MANAGED[0]) or
            receipt.get("normal_loader_sha256") != digest(root / MANAGED[2])):
        raise ValueError("Bundle files do not match the build receipt")
    files = {}
    for name in MANAGED:
        path = root / name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("Bundle files must be regular files inside the staging root")
        files[name] = digest(path)
    metadata = dict(schema=1, loader_protocol=1, release=args.release,
                    base_source=receipt["base_source"], osversion=osversion,
                    build=receipt,
                    stock_kernel_sha256=digest(root / "boot/kernel/kernel"),
                    files=files)
    with tarfile.open(args.out, "w:xz") as archive:
        data = (json.dumps(metadata, indent=2) + "\n").encode()
        info = tarfile.TarInfo("bundle.json")
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))

        def normalize(member):
            member.uid, member.gid = 0, 0
            member.uname, member.gname = "root", "wheel"
            member.mode = 0o755 if member.name == "usr/local/sbin/daemonarchy-secureboot" else 0o644
            member.mtime = receipt["build_epoch"]
            return member

        for name in MANAGED:
            archive.add(root / name, arcname=name, recursive=False, filter=normalize)
    signature = Path(str(args.out) + ".sig")
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(key),
                    "-out", str(signature), str(args.out)], check=True)
    print(f"Created {args.out.name} and detached signature; no private key copied")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--release", required=True)
    parser.add_argument("--build-receipt", required=True, type=Path)
    parser.add_argument("--certificate", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    args = parser.parse_args()
    try:
        main(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Bundle creation failed: {error}\n")
