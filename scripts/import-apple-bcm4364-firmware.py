#!/usr/bin/env python3
"""Import verified BCM4364 B3 firmware from an Apple Sonoma recovery image.

This tool obtains firmware for the operator's own Mac. It never packages Apple
firmware into the Daemonarchy source tree or a redistributable image.

Sources, all ending in the same four pinned file hashes and provenance record:
Apple's recovery download, an operator-supplied BaseSystem.dmg, the Mac's own
internal APFS disk (read through 7-Zip without mounting or writing), and
pre-extracted files on separate media.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen


RECOVERY_SERVICE = "http://osrecovery.apple.com"
SONOMA_BOARD_ID = "Mac-827FAC58A8FDFA22"
SONOMA_PRODUCT = "696-08090"
IMAGE_BYTES = 789568598
IMAGE_SHA256 = "591f07a9a4a58d855a2e53b86a5f5da854a250000a66a9382adaf106c20f839b"
FIRMWARE_ROOT = "macOS Base System/usr/share/firmware/wifi/C-4364__s-B3"
FIRMWARE_SUFFIX = "usr/share/firmware/wifi/C-4364__s-B3"
# A recovery BaseSystem.dmg of another macOS build may still carry identical
# board files. Bound how much of the internal disk a candidate may copy.
INTERNAL_IMAGE_LIMIT = 2 * 1024 * 1024 * 1024
LISTING_LINE_LIMIT = 20_000_000
SOURCE_KINDS = ("apple-download", "recovery-image", "internal-apfs", "verified-files")
FILES = {
    "brcmfmac4364b3-pcie.bin": (
        "borneo.trx", 820013,
        "5bea76866f6c08c16e64f5c3d833a776e6f419b7758638d818b64ce64820aa2c",
    ),
    "brcmfmac4364b3-pcie.txt": (
        "P-bali_M-HRPN_V-u__m-7.7.txt", 12905,
        "3379a394ab8e1b883514b677876cd158d654e7377bc35f43ab99f6d2ae37ea25",
    ),
    "brcmfmac4364b3-pcie.clm_blob": (
        "bali.clmb", 31998,
        "61f9ffe33d4137eac1dfd93c4be03e6c721f282cfc85a89d7d345ffd12f9f9ac",
    ),
    "brcmfmac4364b3-pcie.txcap_blob": (
        "bali.txcb", 723,
        "8b794d5ce9311d2794a6eff4f35ffd1d362f341cb648a3b98f7d7420a251866c",
    ),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def snapshot_image(source, target):
    if source.is_symlink() or not source.is_file():
        raise ValueError("recovery image must be a regular file, not a symlink")
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with os.fdopen(descriptor, "rb") as input_file, target.open("xb") as output_file:
            if not stat.S_ISREG(os.fstat(input_file.fileno()).st_mode):
                raise ValueError("recovery image must be a regular file")
            size, hasher = 0, hashlib.sha256()
            while block := input_file.read(1024 * 1024):
                size += len(block)
                if size > IMAGE_BYTES:
                    raise ValueError("recovery image exceeds the pinned size")
                hasher.update(block)
                output_file.write(block)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    if size != IMAGE_BYTES or hasher.hexdigest() != IMAGE_SHA256:
        target.unlink(missing_ok=True)
        raise ValueError("recovery image does not match the pinned Apple image")


def apple_image_request():
    headers = {"User-Agent": "InternetRecovery/1.0", "Connection": "close"}
    with urlopen(Request(RECOVERY_SERVICE + "/", headers=headers), timeout=30) as response:
        cookies = response.headers.get_all("Set-Cookie", [])
    sessions = [part for cookie in cookies for part in cookie.split("; ")
                if part.startswith("session=")]
    if len(sessions) != 1:
        raise ValueError("Apple recovery service did not issue one session")
    fields = {
        "cid": secrets.token_hex(8).upper(),
        "sn": "00000000000000000",
        "bid": SONOMA_BOARD_ID,
        "k": secrets.token_hex(32).upper(),
        "fg": secrets.token_hex(32).upper(),
        "os": "default",
    }
    request_data = "\n".join(key + "=" + value for key, value in fields.items()).encode("ascii")
    headers.update({"Cookie": sessions[0], "Content-Type": "text/plain"})
    request = Request(RECOVERY_SERVICE + "/InstallationPayload/RecoveryImage",
                      data=request_data, headers=headers)
    with urlopen(request, timeout=30) as response:
        lines = response.read(16 * 1024 + 1)
    if len(lines) > 16 * 1024:
        raise ValueError("Apple recovery response exceeds the size budget")
    info = {}
    for line in lines.decode("ascii").splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if key in info:
                raise ValueError("duplicate Apple recovery response field")
            info[key] = value
    url, token = info.get("AU", ""), info.get("AT", "")
    parsed = urlparse(url)
    if (info.get("AP") != SONOMA_PRODUCT or parsed.scheme != "http"
            or parsed.hostname != "oscdn.apple.com"
            or not parsed.path.endswith("/RecoveryImage/BaseSystem.dmg")
            or not token or any(character.isspace() for character in token)):
        raise ValueError("Apple recovery response does not identify the selected image")
    return url, token


def download_image(target):
    url, token = apple_image_request()
    size, hasher = 0, hashlib.sha256()
    next_report = 64 * 1024 * 1024
    request = Request(url, headers={"User-Agent": "InternetRecovery/1.0",
                                    "Cookie": "AssetToken=" + token,
                                    "Connection": "close"})
    with urlopen(request, timeout=30) as response, target.open("xb") as output_file:
        while block := response.read(1024 * 1024):
            size += len(block)
            if size > IMAGE_BYTES:
                raise ValueError("download exceeds the pinned image size")
            hasher.update(block)
            output_file.write(block)
            if size >= next_report:
                print(f"Apple recovery image: {size // (1024 * 1024)} of "
                      f"{(IMAGE_BYTES + 1024 * 1024 - 1) // (1024 * 1024)} MiB downloaded",
                      file=sys.stderr, flush=True)
                next_report += 64 * 1024 * 1024
    if size != IMAGE_BYTES or hasher.hexdigest() != IMAGE_SHA256:
        raise ValueError("Apple download does not match the pinned recovery image")
    return url


def extract(image, root=FIRMWARE_ROOT):
    payloads = {}
    for destination, (source, size, expected) in FILES.items():
        result = subprocess.run(
            ["7z", "x", "-so", str(image), root + "/" + source],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if result.returncode or len(result.stdout) != size or digest(result.stdout) != expected:
            raise ValueError("recovery firmware differs from the selected board: " + destination)
        payloads[destination] = result.stdout
    return payloads


def read_only_device(device):
    """Accept only an existing device node; 7-Zip opens it for reading only."""
    if not device.is_absolute() or Path("/dev") not in device.parents:
        raise ValueError("internal disk must be a device node under /dev")
    if device.is_symlink() or not stat.S_ISCHR(device.stat().st_mode):
        raise ValueError("internal disk must be a character device, not a file or symlink")
    descriptor = os.open(device, os.O_RDONLY)
    os.close(descriptor)


def archive_listing(archive):
    """Yield every path 7-Zip reports, without extracting or writing anything."""
    process = subprocess.Popen(["7z", "l", "-slt", "-ba", str(archive)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True,
                               errors="surrogateescape")
    try:
        for count, line in enumerate(process.stdout, 1):
            if count > LISTING_LINE_LIMIT:
                raise ValueError("internal disk listing exceeds its bound")
            if line.startswith("Path = "):
                yield line[len("Path = "):].rstrip("\n")
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait()


def internal_candidates(device):
    images, roots = [], []
    for path in archive_listing(device):
        if path.endswith("/BaseSystem.dmg") or path == "BaseSystem.dmg":
            images.append(path)
        elif path.endswith(FIRMWARE_SUFFIX + "/" + FILES["brcmfmac4364b3-pcie.bin"][0]):
            roots.append(path.rsplit("/", 1)[0])
    return sorted(set(images)), sorted(set(roots))


def copy_member(archive, member, target, limit):
    with target.open("xb") as output_file:
        process = subprocess.Popen(["7z", "x", "-so", str(archive), member],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        size, hasher = 0, hashlib.sha256()
        try:
            while block := process.stdout.read(1024 * 1024):
                size += len(block)
                if size > limit:
                    raise ValueError("internal recovery image exceeds its size bound")
                hasher.update(block)
                output_file.write(block)
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
            returncode = process.wait()
    if returncode:
        raise ValueError("7-Zip could not read the internal recovery image")
    return size, hasher.hexdigest()


def import_internal(device, temporary):
    """Read the Mac's own APFS disk; return payloads, source text and image hash."""
    read_only_device(device)
    images, roots = internal_candidates(device)
    failures = []
    for member in images:
        image = Path(temporary) / ("internal-" + secrets.token_hex(8) + ".dmg")
        try:
            size, observed = copy_member(device, member, image, INTERNAL_IMAGE_LIMIT)
            payloads = extract(image)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append(member + ": " + str(error))
            continue
        finally:
            image.unlink(missing_ok=True)
        pinned = size == IMAGE_BYTES and observed == IMAGE_SHA256
        return payloads, "internal APFS recovery image " + member, observed, pinned
    for root in roots:
        try:
            return extract(device, root), "internal APFS volume " + root, None, False
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append(root + ": " + str(error))
    if not images and not roots:
        raise ValueError("no macOS recovery image or BCM4364 firmware found on " + str(device))
    raise ValueError("no internal source matched the selected board: " + "; ".join(failures))


def read_verified_files(directory):
    """Pre-extracted files on separate media must match every pinned size and hash."""
    verify_files(directory, "MacBookPro16,1")
    payloads = {}
    for name, (_, size, expected) in FILES.items():
        descriptor = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("invalid firmware file: " + name)
            data = stream.read(size + 1)
        if len(data) != size or digest(data) != expected:
            raise ValueError("firmware hash changed: " + name)
        payloads[name] = data
    return payloads


def verify_files(directory, model):
    if model != "MacBookPro16,1":
        raise ValueError("this firmware profile is only for MacBookPro16,1")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("firmware directory must be a real directory")
    for name, (_, size, expected) in FILES.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            raise ValueError("invalid firmware file: " + name)
        if digest(path.read_bytes()) != expected:
            raise ValueError("firmware hash changed: " + name)
    print("Verified four BCM4364 B3 firmware files in", directory)


def verify_stage(directory, model):
    if (directory.is_symlink() or not directory.is_dir()
            or directory.stat().st_uid != os.geteuid()
            or stat.S_IMODE(directory.stat().st_mode) != 0o700):
        raise ValueError("firmware stage must be an owned private directory")
    verify_files(directory, model)
    expected_names = set(FILES) | {"provenance.json"}
    if {path.name for path in directory.iterdir()} != expected_names:
        raise ValueError("firmware stage has missing or unexpected files")
    manifest = directory / "provenance.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 16384:
        raise ValueError("invalid firmware provenance record")
    record = json.loads(manifest.read_text())
    expected_hashes = {name: expected for name, (_, _, expected) in FILES.items()}
    if (not isinstance(record, dict)
            or record.get("schema") != "daemonarchy/apple-recovery-firmware@1"
            or record.get("model") != model
            or record.get("pci_device") != "14e4:4464"
            or record.get("apple_subsystem") != "106b:07bf"
            or record.get("recovery_image_sha256") != IMAGE_SHA256
            or record.get("files") != expected_hashes
            or not isinstance(record.get("source"), str)
            or not 0 < len(record["source"]) <= 4096
            or record.get("source_kind", "recovery-image") not in SOURCE_KINDS
            or ("source_image_sha256" in record
                and (not isinstance(record["source_image_sha256"], str)
                     or len(record["source_image_sha256"]) != 64
                     or set(record["source_image_sha256"]) - set("0123456789abcdef")))
            or not isinstance(record.get("source_image_pinned", False), bool)):
        raise ValueError("firmware provenance does not match the selected board")

def import_firmware(args):
    if args.model != "MacBookPro16,1":
        raise ValueError("this firmware profile is only for MacBookPro16,1")
    if args.destination.exists() or args.destination.is_symlink():
        raise ValueError("use a fresh destination directory")
    os.umask(0o077)
    extra = {}
    if args.files:
        payloads = read_verified_files(args.files)
        source, kind = "operator-supplied pre-extracted files matching the pinned board hashes", "verified-files"
    else:
        required_space = (INTERNAL_IMAGE_LIMIT if args.internal_disk else IMAGE_BYTES) + 64 * 1024 * 1024
        if shutil.disk_usage(tempfile.gettempdir()).free < required_space:
            required_mib = (required_space + 1024 * 1024 - 1) // (1024 * 1024)
            raise ValueError(f"the live temporary filesystem needs at least {required_mib} MiB free")
        with tempfile.TemporaryDirectory(prefix="daemonarchy-apple-recovery-") as temporary:
            image = Path(temporary) / "BaseSystem.dmg"
            if args.download:
                source, kind = download_image(image), "apple-download"
                payloads = extract(image)
            elif args.internal_disk:
                payloads, source, observed, pinned = import_internal(args.internal_disk, temporary)
                kind = "internal-apfs"
                if observed is not None:
                    extra["source_image_sha256"] = observed
                extra["source_image_pinned"] = pinned
            else:
                snapshot_image(args.image, image)
                source, kind = "operator-supplied verified recovery image", "recovery-image"
                payloads = extract(image)
    args.destination.mkdir(mode=0o700)
    try:
        for name, data in payloads.items():
            path = args.destination / name
            path.write_bytes(data)
            path.chmod(0o444)
        (args.destination / "provenance.json").write_text(json.dumps({
            "schema": "daemonarchy/apple-recovery-firmware@1",
            "model": args.model,
            "pci_device": "14e4:4464",
            "apple_subsystem": "106b:07bf",
            "recovery_image_sha256": IMAGE_SHA256,
            "source": source,
            "source_kind": kind,
            "files": {name: digest(data) for name, data in payloads.items()},
            **extra,
        }, indent=2, sort_keys=True) + "\n")
    except BaseException:
        for path in args.destination.iterdir():
            path.unlink()
        args.destination.rmdir()
        raise
    print("Imported four verified BCM4364 B3 firmware files into", args.destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, help="operator-supplied Apple BaseSystem.dmg")
    source.add_argument("--download", action="store_true", help="fetch the pinned image from Apple")
    source.add_argument("--internal-disk", type=Path,
                        help="read this Mac's APFS partition device (read-only, never mounted)")
    source.add_argument("--files", type=Path, help="directory of pre-extracted board files")
    source.add_argument("--verify-stage", action="store_true", help="recheck an imported directory")
    source.add_argument("--verify-files", action="store_true", help="check preloaded preview files")
    parser.add_argument("--model", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.verify_stage:
            verify_stage(args.destination, args.model)
        elif args.verify_files:
            verify_files(args.destination, args.model)
        else:
            import_firmware(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("Apple firmware import refused:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
