#!/usr/bin/env python3
"""Import verified BCM4364 B3 firmware from an Apple Sonoma recovery image.

This tool obtains firmware for the operator's own Mac. It never packages Apple
firmware into the Daemonarchy source tree or a redistributable image.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
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
    if size != IMAGE_BYTES or hasher.hexdigest() != IMAGE_SHA256:
        raise ValueError("Apple download does not match the pinned recovery image")
    return url


def extract(image):
    payloads = {}
    for destination, (source, size, expected) in FILES.items():
        result = subprocess.run(
            ["7z", "x", "-so", str(image), FIRMWARE_ROOT + "/" + source],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if result.returncode or len(result.stdout) != size or digest(result.stdout) != expected:
            raise ValueError("recovery firmware differs from the selected board: " + destination)
        payloads[destination] = result.stdout
    return payloads


def import_firmware(args):
    if args.model != "MacBookPro16,1":
        raise ValueError("this firmware profile is only for MacBookPro16,1")
    if args.destination.exists() or args.destination.is_symlink():
        raise ValueError("use a fresh destination directory")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="daemonarchy-apple-recovery-") as temporary:
        image = Path(temporary) / "BaseSystem.dmg"
        if args.download:
            source = download_image(image)
        else:
            snapshot_image(args.image, image)
            source = "operator-supplied verified recovery image"
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
            "files": {name: digest(data) for name, data in payloads.items()},
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
    parser.add_argument("--model", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        import_firmware(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("Apple firmware import refused:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
