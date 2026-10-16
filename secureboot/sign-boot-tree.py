#!/usr/bin/env python3
"""Sign a disposable FreeBSD boot tree; private keys stay on the signing host.

This authoring utility is not installed in the ISO. It must never target the
running system. Install/update callers must prepare a separate tree first.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def replace(path, contents):
    # Only public material is written into the boot tree.
    fd, name = tempfile.mkstemp(prefix=".sign-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def inventory(root):
    boot = root.resolve(strict=True) / "boot"
    for directory, dirs, files in os.walk(boot, followlinks=False):
        # The ESP is independently authenticated by firmware and may contain
        # another OS. It must never become part of our boot-tree inventory.
        if Path(directory) == boot:
            dirs[:] = [name for name in dirs if name != "efi"]
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError("Symlinked boot directories are not supported")
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(boot).as_posix()
            if any(c in relative for c in "\n\r\0"):
                raise ValueError("Boot path cannot be represented in a manifest")
            if not path.resolve().is_relative_to(boot) or not path.is_file():
                raise ValueError("Boot files must resolve to regular files inside /boot")
            yield relative, path


def sign(args):
    if args.root.is_symlink():
        raise ValueError("Staging root must not be a symlink")
    root = args.root.resolve(strict=True)
    if root == Path("/"):
        raise ValueError("Use a disposable staging tree, never the running root")
    boot = root / "boot"
    kernel_path = args.kernel_path
    if kernel_path not in ("kernel/kernel", "kernel.secure/kernel"):
        raise ValueError("Unsupported policy kernel path")
    if boot.is_symlink() or not (boot / kernel_path).is_file():
        raise ValueError("Expected a real /boot directory with a staged kernel")
    key = args.key.resolve(strict=True)
    certificate = args.certificate.resolve(strict=True)
    if key.is_relative_to(root):
        raise ValueError("Signing key must be outside the image tree")
    if key.stat().st_mode & 0o077:
        raise ValueError("Signing key must not be readable by group or other users")
    cert_bytes = certificate.read_bytes()
    if b"PRIVATE KEY" in cert_bytes:
        raise ValueError("Certificate input must contain public material only")
    # Check before changing the staging tree, using only exported public keys.
    cert_public = subprocess.check_output(
        ["openssl", "x509", "-in", str(certificate), "-noout", "-pubkey"])
    key_public = subprocess.check_output(
        ["openssl", "pkey", "-in", str(key), "-pubout"])
    if cert_public != key_public:
        raise ValueError("Certificate does not match the signing key")
    run("openssl", "x509", "-in", str(certificate), "-checkend", "0", "-noout")
    entries = sorted(inventory(root))
    for name, _ in entries:
        if Path(name).name.startswith("loader.ve."):
            raise ValueError("Verification-control files must not enter a release tree")
    modules = {name: digest(path) for name, path in entries
               if not path.is_symlink() and (name == kernel_path or
               (name.startswith(("kernel/", "kernel.secure/", "modules/"))
                and name.endswith(".ko")))}
    additional = {}
    if args.module_inventory is not None:
        receipt = json.loads(args.module_inventory.read_text())
        if (not isinstance(receipt, dict) or receipt.get("schema") != 1 or
                receipt.get("osversion") != 1600027 or
                not isinstance(receipt.get("modules"), dict)):
            raise ValueError("Unsupported release module inventory")
        for name, fingerprint in receipt["modules"].items():
            if not isinstance(name, str) or not isinstance(fingerprint, str):
                raise ValueError("Invalid signed module inventory entry")
            path = PurePosixPath(name)
            if (not name.startswith("/boot/modules/") or not name.endswith(".ko") or
                    ".." in path.parts or any(c in name for c in "\r\n\0") or
                    not re.fullmatch("[0-9a-f]{64}", fingerprint)):
                raise ValueError("Invalid signed module inventory entry")
            relative = name.removeprefix("/boot/")
            if relative in modules and modules[relative] != fingerprint:
                raise ValueError("Local and packaged module fingerprints conflict")
            additional[relative] = fingerprint
        modules.update(additional)
    if args.build_receipt is None:
        raise ValueError("A matching kernel/loader build receipt is required")
    build = json.loads(args.build_receipt.read_text())
    required_options = {"WITH_LOADER_VERIEXEC=yes", "WITH_LOADER_EFI_SECUREBOOT=yes",
                        "WITH_LOADER_VERIEXEC_PASS_MANIFEST=yes", "VE_SELF_TESTS=yes",
                        "WITHOUT_LOADER_VERIEXEC_TESTING=yes",
                        "WITHOUT_LOADER_VERIEXEC_VECTX=yes"}
    if (not isinstance(build, dict) or build.get("schema") != 1 or
            not required_options.issubset(build.get("loader_options", [])) or
            build.get("kernel_sha256") != digest(boot / kernel_path) or
            build.get("unsigned_loader_sha256") != digest(args.loader.resolve(strict=True)) or
            build.get("trust_anchor_sha256") != digest(certificate) or
            build.get("source_patch_sha256") != digest(
                Path(__file__).resolve().parent / "patches/module-policy.patch") or
            build.get("loader_patch_sha256") != digest(
                Path(__file__).resolve().parent / "patches/loader-rootpool.patch") or
            build.get("optional_verification_patch_sha256") != digest(
                Path(__file__).resolve().parent / "patches/efi-optional-verification.patch")):
        raise ValueError("Boot inputs do not match the required verified build receipt")
    if args.module_inventory is not None and receipt.get("source_revision") != build.get("base_source"):
        raise ValueError("Module inventory and kernel source revisions differ")
    with tempfile.TemporaryDirectory(prefix="daemonarchy-sign-") as temp:
        temp = Path(temp)
        public = temp / "public.pem"
        public.write_bytes(cert_public)

        def manifest(name, data):
            source = temp / name
            signature = temp / (name + ".signature")
            source.write_bytes(data)
            run("openssl", "dgst", "-sha256", "-sign", str(key),
                "-out", str(signature), str(source))
            run("openssl", "dgst", "-sha256", "-verify", str(public),
                "-signature", str(signature), str(source), stdout=subprocess.DEVNULL)
            armored = (b"-----BEGIN SIGNATURE-----\n" +
                       base64.encodebytes(signature.read_bytes()) +
                       b"-----END SIGNATURE-----\n")
            replace(boot / name, data)
            replace(boot / (name + ".sig"), armored)
            replace(boot / (name + ".certs"), cert_bytes)

        signed_loader = temp / "loader.efi"
        run("uefisign", "-k", str(key), "-c", str(certificate),
            "-o", str(signed_loader), str(args.loader.resolve(strict=True)))
        replace(boot / "loader.efi", signed_loader.read_bytes())
        manifest("runtime.manifest", "".join(
            f"/boot/{name} sha256={fingerprint}\n"
            for name, fingerprint in sorted(modules.items())).encode())

        def mutable(name):
            # Configuration can select only code whose fingerprint the loader
            # trusts. Kernel policy still requires the verified handoff.
            return (name in ("loader.conf", "loader.conf.local", "device.hints") or
                    (name.startswith("loader.conf.d/") and name.endswith(".conf")) or
                    name.endswith((".hints", ".symbols")))

        entries = {name: digest(path) for name, path in inventory(root)}
        entries.update(additional)
        manifest("manifest", "".join(
            f"{name} sha256={fingerprint}\n" for name, fingerprint in sorted(entries.items())
            if name not in ("manifest", "manifest.sig", "manifest.certs")
            and (not name.endswith("/kernel") or name == kernel_path)
            and not mutable(name)).encode())
    print("Signed loader, boot manifest and kernel-module manifest; no private key copied.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--loader", type=Path, required=True,
                        help="verified-loader build, before PE signing")
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--kernel-path", default="kernel/kernel",
                        choices=("kernel/kernel", "kernel.secure/kernel"))
    parser.add_argument("--module-inventory", type=Path,
                        help="native release module-inventory.py receipt")
    parser.add_argument("--build-receipt", type=Path, required=True,
                        help="build.py receipt matching kernel, loader and trust anchor")
    args = parser.parse_args()
    try:
        sign(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Signing failed: {error}\n")
