#!/usr/local/bin/python3.12
"""Validate and stage Daemonarchy's signed, same-snapshot boot maintenance bundles.

Development tool: installer integration and native transaction qualification
are required before this can be exposed as a supported update command.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

BASE = "bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf"
MANAGED = {
    "boot/kernel.secure/kernel", "boot/loader.efi", "boot/loader_normal.efi",
    "boot/manifest", "boot/manifest.sig", "boot/manifest.certs",
    "boot/runtime.manifest", "boot/runtime.manifest.sig", "boot/runtime.manifest.certs",
    "boot/lua/local.lua", "boot/lua/brand-daemonarchy.lua", "boot/daemonarchy-secureboot.conf",
    "usr/local/sbin/daemonarchy-secureboot",
}
APPLE_BCM4364 = {
    "boot/firmware/brcmfmac4364b3-pcie.bin",
    "boot/firmware/brcmfmac4364b3-pcie.txt",
    "boot/firmware/brcmfmac4364b3-pcie.clm_blob",
    "boot/firmware/brcmfmac4364b3-pcie.txcap_blob",
}


def verify_firmware_stage(staged, directory):
    """Check private Apple bytes against the authenticated boot inventory."""
    if directory is None or directory.is_symlink():
        raise ValueError("A private, non-symlinked firmware stage is required")
    directory = directory.resolve(strict=True)
    importer = Path(__file__).resolve().parents[1] / "import-apple-bcm4364-firmware.py"
    if not importer.is_file():
        importer = Path(__file__).resolve().parents[1] / "scripts/import-apple-bcm4364-firmware.py"
    spec = importlib.util.spec_from_file_location("apple_bcm4364_import", importer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify_stage(directory, "MacBookPro16,1")
    signed = {}
    for line in (staged / "boot/manifest").read_text().splitlines():
        match = re.fullmatch(r"(\S+) sha256=([0-9a-f]{64})", line)
        if not match:
            raise ValueError("Malformed signed boot manifest")
        name, expected = match.groups()
        if name in signed:
            raise ValueError("Duplicate signed boot manifest entry")
        signed[name] = expected
    for relative in APPLE_BCM4364:
        name = relative.removeprefix("boot/firmware/")
        if signed.get("firmware/" + name) != digest(directory / name):
            raise ValueError("Private MacBook firmware differs from the signed release: " + name)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def public_key(certificate):
    return subprocess.check_output([
        "openssl", "x509", "-in", str(certificate), "-noout", "-pubkey"])


def verify_signature(source, signature, certificate):
    with tempfile.TemporaryDirectory(prefix="daemonarchy-verify-") as name:
        key = Path(name) / "public.pem"
        key.write_bytes(public_key(certificate))
        subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(key),
                        "-signature", str(signature), str(source)],
                       check=True, stdout=subprocess.DEVNULL)


def unpack(bundle, signature, certificate, destination):
    # Snapshot inputs into a private directory: a mutable download path must not
    # change between signature verification and archive parsing.
    with tempfile.TemporaryDirectory(prefix="daemonarchy-input-") as name:
        private = Path(name)
        frozen = private / "bundle.txz"
        frozen_signature = private / "bundle.sig"
        frozen_certificate = private / "certificate.pem"
        for source, target in ((bundle, frozen), (signature, frozen_signature),
                               (certificate, frozen_certificate)):
            shutil.copyfile(source, target)
        return unpack_snapshot(frozen, frozen_signature, frozen_certificate, destination)


def unpack_snapshot(bundle, signature, certificate, destination):
    # Verify the complete archive before parsing even its metadata or paths.
    verify_signature(bundle, signature, certificate)
    with tarfile.open(bundle, "r:xz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if set(names) != MANAGED | {"bundle.json"} or len(set(names)) != len(names):
            raise ValueError("Bundle contains missing, duplicate or unexpected paths")
        for member in members:
            if not member.isfile() or member.size > 256 * 1024 * 1024:
                raise ValueError("Bundle entries must be bounded regular files")
        metadata = json.load(archive.extractfile("bundle.json"))
        if (not isinstance(metadata, dict) or
                not isinstance(metadata.get("files"), dict) or
                metadata.get("schema") != 1 or metadata.get("loader_protocol") != 1 or
                metadata.get("base_source") != BASE or metadata.get("osversion") != 1600028 or
                set(metadata.get("files", {})) != MANAGED or
                not isinstance(metadata.get("stock_kernel_sha256"), str) or
                not re.fullmatch("[0-9a-f]{64}", metadata["stock_kernel_sha256"]) or
                any(not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value)
                    for value in metadata["files"].values())):
            raise ValueError("Unsupported boot bundle or snapshot")
        for member in members:
            path = destination / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, path.open("wb") as target:
                shutil.copyfileobj(source, target)
            path.chmod(0o644)
            if member.name != "bundle.json" and digest(path) != metadata["files"][member.name]:
                raise ValueError(f"Bundle digest mismatch: {member.name}")
    return metadata


def inside(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Path escapes installation: {relative}")
    return path


def verify_tree(root, metadata, *, require_apple_bcm4364=False):
    root = root.resolve(strict=True)
    if digest(inside(root, "boot/kernel/kernel")) != metadata["stock_kernel_sha256"]:
        raise ValueError("Stock kernel differs from the bundle's qualified snapshot")
    for name, expected in metadata["files"].items():
        if digest(inside(root, name)) != expected:
            raise ValueError(f"Managed boot file mismatch: {name}")
    boot_fingerprints = {}
    for manifest, prefix in (("boot/manifest", "boot/"), ("boot/runtime.manifest", "")):
        for line in inside(root, manifest).read_text().splitlines():
            match = re.fullmatch(r"(\S+) sha256=([0-9a-f]{64})", line)
            if not match:
                raise ValueError(f"Malformed manifest entry in {manifest}")
            name, expected = match.groups()
            relative = prefix + name.lstrip("/")
            if ".." in PurePosixPath(relative).parts or not relative.startswith("boot/"):
                raise ValueError("Manifest path escapes /boot")
            path = inside(root, relative)
            if require_apple_bcm4364 and relative in APPLE_BCM4364 and not path.exists():
                raise ValueError(f"Required MacBook firmware is missing: {relative}")
            # Shared media can omit signed files for other hardware. A MacBook
            # target explicitly requires its four signed board files below.
            if (not path.exists() and
                    ((relative.startswith("boot/modules/") and relative.endswith(".ko"))
                     or (relative in APPLE_BCM4364 and not require_apple_bcm4364))):
                continue
            if digest(path) != expected:
                raise ValueError(f"Signed fingerprint mismatch: {relative}")
            if manifest == "boot/manifest":
                boot_fingerprints[relative] = expected
    if require_apple_bcm4364 and not APPLE_BCM4364.issubset(boot_fingerprints):
        raise ValueError("MacBook firmware is absent from the signed boot inventory")
    for path in (root / "boot/firmware").glob("brcmfmac4364b3-pcie.*"):
        relative = path.relative_to(root).as_posix()
        if relative not in boot_fingerprints:
            raise ValueError(f"Installed firmware is absent from the signed inventory: {relative}")
    for path in (root / "boot/modules").glob("*.ko"):
        relative = path.relative_to(root).as_posix()
        if relative not in boot_fingerprints:
            raise ValueError(f"Installed module is absent from the signed inventory: {relative}")
    for path in (root / "boot").rglob("loader.ve.*"):
        if "efi" not in path.relative_to(root / "boot").parts:
            raise ValueError("Verification-control files are forbidden")


def install(root, staged, metadata, *, require_apple_bcm4364=False):
    root = root.resolve(strict=True)
    if root == Path("/") or staged.resolve().is_relative_to(root):
        raise ValueError("Install only into an offline target or mounted boot environment")
    if digest(inside(root, "boot/kernel/kernel")) != metadata["stock_kernel_sha256"]:
        raise ValueError("Target stock kernel does not match the qualified snapshot")
    for name in sorted(MANAGED):
        target = inside(root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Replace rather than following an existing file symlink.
        temporary = target.with_name(target.name + ".daemonarchy-new")
        if temporary.exists() or temporary.is_symlink():
            raise ValueError(f"Pending temporary file already exists: {temporary}")
        shutil.copyfile(staged / name, temporary)
        temporary.chmod(0o755 if name == "usr/local/sbin/daemonarchy-secureboot" else 0o644)
        os.replace(temporary, target)
    verify_tree(root, metadata, require_apple_bcm4364=require_apple_bcm4364)


def output(*command):
    return subprocess.check_output(command, text=True).strip()


def native_root():
    if os.uname().sysname != "FreeBSD" or os.geteuid() != 0:
        raise ValueError("This command requires root on native FreeBSD")


def status():
    native_root()
    method = output("sysctl", "-n", "machdep.bootmethod")
    kernel = output("kenv", "kernelname")
    try:
        policy = subprocess.check_output(
            ["sysctl", "-n", "security.mac.veriexec.state"], text=True,
            stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        policy = "absent"
    firmware = "unavailable (BIOS)"
    if method == "UEFI":
        probe = subprocess.run([
            "efivar", "-p", "-N", "-b", "-n",
            "8be4df61-93ca-11d2-aa0d-00e098032b8c-SecureBoot"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=dict(os.environ, LC_ALL="C"))
        if probe.returncode != 0:
            if b"No such file or directory" not in probe.stderr:
                raise ValueError("Cannot read firmware Secure Boot state")
            firmware = "unavailable (no SecureBoot variable)"
        else:
            if probe.stdout not in (b"\x00", b"\x01"):
                raise ValueError("Firmware returned an unknown Secure Boot state")
            firmware = "enforced" if probe.stdout == b"\x01" else "disabled"
    print(f"Firmware Secure Boot: {firmware}\nKernel: {kernel}\nModule policy: {policy}")
    if firmware == "enforced" and (
            not {"loaded", "active", "enforce", "locked"}.issubset(policy.split()) or
            not kernel.endswith("/boot/kernel.secure/kernel")):
        raise ValueError("Enforced firmware did not boot the complete verified profile")


def main(args):
    if args.command == "status":
        status()
        return
    with tempfile.TemporaryDirectory(prefix="daemonarchy-bundle-") as name:
        staged = Path(name)
        metadata = unpack(args.bundle.resolve(strict=True), args.signature.resolve(strict=True),
                          args.certificate.resolve(strict=True), staged)
        if args.command == "firmware-stage":
            verify_firmware_stage(staged, args.firmware_stage)
            print("PASS: private MacBook firmware matches the signed boot inventory")
        elif args.command == "verify":
            verify_tree(args.root, metadata,
                        require_apple_bcm4364=args.require_apple_bcm4364)
            print("PASS: signed bundle and installed boot files match")
        elif args.command == "install":
            install(args.root, staged, metadata,
                    require_apple_bcm4364=args.require_apple_bcm4364)
            print("PASS: offline boot profile installed and validated; EFI setup remains required")
        else:
            native_root()
            be = args.environment
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}", be):
                raise ValueError("Use a simple boot environment name")
            if args.command == "stage":
                # No running /boot writes and no activation during staging.
                subprocess.run(["bectl", "create", "-r", be], check=True)
            mountpoint = staged / "mounted-be"
            mountpoint.mkdir()
            subprocess.run(["bectl", "mount", be, str(mountpoint)], check=True)
            try:
                if args.command == "stage":
                    install(mountpoint, staged, metadata,
                            require_apple_bcm4364=args.require_apple_bcm4364)
                else:
                    verify_tree(mountpoint, metadata,
                                require_apple_bcm4364=args.require_apple_bcm4364)
            finally:
                subprocess.run(["bectl", "unmount", be], check=True)
            if args.command == "activate":
                # The installed EFI entry must use the qualified pool selector.
                if not output("kenv", "daemonarchy_rootpool").isdecimal():
                    raise ValueError("EFI active-boot-environment selection has not been configured")
                subprocess.run(["bectl", "activate", be], check=True)
                print(f"Validated and activated {be}; previous environment retained; reboot manually")
            else:
                print(f"Validated {be}; current boot selection unchanged. Activate separately after review")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "verify", "install", "stage", "activate", "firmware-stage"))
    parser.add_argument("bundle", type=Path, nargs="?")
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--certificate", type=Path,
                        help="trusted public certificate obtained independently of the bundle")
    parser.add_argument("--root", type=Path, default=Path("/"))
    parser.add_argument("--environment")
    parser.add_argument("--firmware-stage", type=Path,
                        help="private operator-acquired MacBookPro16,1 firmware directory")
    parser.add_argument("--require-apple-bcm4364", action="store_true",
                        help="require all four signed BCM4364 B3 files on this target")
    args = parser.parse_args()
    if args.command != "status" and not all((args.bundle, args.signature, args.certificate)):
        parser.error("A bundle, --signature and --certificate are required")
    if args.command in ("stage", "activate") and not args.environment:
        parser.error("--environment is required")
    if args.command == "firmware-stage" and not args.firmware_stage:
        parser.error("--firmware-stage is required")
    try:
        main(args)
    except (ValueError, OSError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Maintenance failed; boot selection was not changed: {error}\n")
