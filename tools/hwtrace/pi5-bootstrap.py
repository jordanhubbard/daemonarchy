#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Stage a pinned Pi 5/Pi 500 SD/FDT bootstrap bundle, never a physical device.

This creates inputs for a NEW diagnostic image, not an installable distribution.
Matching FreeBSD Lua/rootfs support must come from the selected hwtrace image.
The BCM2711 raspi4b emulator cannot validate this BCM2712 profile.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import struct
import subprocess
import sys

UBOOT_COMMIT = "5508406582f6f7120dce0c4b3059819a41788db2"
BOOTCOMMAND = 'if mmc dev 0; then if fatload mmc 0:1 ${scriptaddr} boot.scr; then source ${scriptaddr}; fi; fi'
BOARDS = {"pi5b": "raspberrypi,5-model-b", "pi500": "raspberrypi,500"}
REQUIRED_CONFIG = ("CONFIG_TARGET_RPI_ARM64=y", "CONFIG_OF_BOARD=y",
                   "CONFIG_EFI_LOADER=y", "CONFIG_CMD_FAT=y", "CONFIG_CMD_MMC=y",
                   "CONFIG_EFI_PARTITION=y", "CONFIG_ENV_IS_NOWHERE=y",
                   "CONFIG_USE_BOOTCOMMAND=y", 'CONFIG_BOOTCOMMAND="' + BOOTCOMMAND + '"')
FORBIDDEN_CONFIG = ("CONFIG_ENV_IS_IN_FAT=y", "CONFIG_USE_PREBOOT=y",
                    "CONFIG_EFI_RUNTIME_UPDATE_CAPSULE=y")


def regular(path, limit):
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > limit:
        raise ValueError(f"not a bounded regular input: {path.name}")
    return path.read_bytes()


def checked(path, expected, limit):
    data = regular(path, limit)
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"checksum mismatch: {path.name}")
    return data


def elf_aarch64(data):
    return (len(data) >= 64 and data[:6] == b"\x7fELF\x02\x01" and
            struct.unpack_from("<H", data, 18)[0] == 183)


def pe_aarch64(data):
    if len(data) < 64 or data[:2] != b"MZ":
        return False
    offset = struct.unpack_from("<I", data, 60)[0]
    return (offset + 26 <= len(data) and data[offset:offset+4] == b"PE\0\0" and
            struct.unpack_from("<H", data, offset+4)[0] == 0xaa64 and
            struct.unpack_from("<H", data, offset+24)[0] == 0x20b)


def validate_dtb(path, board):
    data = regular(path, 16 * 1024 * 1024)
    if len(data) < 40 or struct.unpack_from(">I", data)[0] != 0xd00dfeed:
        raise ValueError("invalid FDT header")
    size = struct.unpack_from(">I", data, 4)[0]
    if not 40 <= size <= len(data):
        raise ValueError("invalid FDT size")
    compatible = subprocess.check_output(
        ["fdtget", "-t", "s", str(path), "/", "compatible"], text=True).split()
    if BOARDS[board] not in compatible or "brcm,bcm2712" not in compatible:
        raise ValueError("DTB does not match selected BCM2712 board")
    return compatible


MEMORY_CAPS = ("3G", "none")
LOADER_PREFIX = ('# FDT control: this boot path does not supply ACPI tables.\n'
                 'boottrace_capture_acpi="NO"\nhw.ncpu="4"\n')


def memory_inputs(cap, board):
    if cap not in MEMORY_CAPS or board not in BOARDS:
        raise ValueError("unsupported bootstrap memory profile or board")
    setting = 'hw.physmem="3G"\n' if cap == "3G" else ""
    loader = (LOADER_PREFIX + setting + 'boot_verbose="YES"\n').encode()
    command = "hw.physmem=3G" if cap == "3G" else "unset hw.physmem"
    queue = f"[{board}-sd-fdt-mmc0-{cap.lower()}]\nhw.ncpu=4\n{command}\n".encode()
    return loader, queue


def verify_bundle(directory, expected_cap=None, queue_file=None):
    """Validate retained bytes/profile; never infer the base UFS configuration."""
    if (directory / "manifest.json").is_symlink():
        raise ValueError("symlink bundle manifest")
    manifest = json.loads(regular(directory / "manifest.json", 1024 * 1024))
    if not isinstance(manifest, dict):
        raise ValueError("invalid bundle manifest")
    if manifest.get("schema") != "daemonarchy/pi5-bootstrap-bundle@1":
        raise ValueError("unsupported bootstrap bundle schema")
    profile = manifest.get("memory_profile")
    if profile is not None and not isinstance(profile, dict):
        raise ValueError("invalid bundle memory profile")
    # Historical v1 bundles have no profile or queue and were always capped3G.
    cap = "3G" if profile is None else profile.get("memory_cap")
    if cap not in MEMORY_CAPS or (expected_cap is not None and cap != expected_cap):
        raise ValueError("bundle memory profile differs from requested cap")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("missing bundle file identities")
    for name, identity in files.items():
        if (not isinstance(identity, dict) or type(identity.get("bytes")) is not int or
                identity["bytes"] < 0 or not isinstance(identity.get("sha256"), str) or
                re.fullmatch("[0-9a-f]{64}", identity["sha256"]) is None):
            raise ValueError("invalid bundle file identity")
        path = Path(name)
        if (not name or path.as_posix() != name or name == "manifest.json" or
                path.is_absolute() or ".." in path.parts or "\\" in name):
            raise ValueError("invalid bundle member path")
        if any(parent.is_symlink() for parent in (directory / path, *(directory / path).parents)):
            raise ValueError("symlink in bundle member path")
        data = checked(directory / path, identity["sha256"], 256 * 1024 * 1024)
        if len(data) != identity["bytes"]:
            raise ValueError("bundle member size mismatch")
    actual_files = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() or p.is_symlink()}
    if actual_files != set(files) | {"manifest.json"}:
        raise ValueError("bundle file inventory differs from manifest")
    loader, queue = memory_inputs(cap, manifest.get("board"))
    if "boot/loader.conf.local" not in files or regular(directory / "boot/loader.conf.local", 65536) != loader:
        raise ValueError("bundle loader configuration conflicts with memory profile")
    if profile is not None:
        if profile != memory_profile(cap):
            raise ValueError("inconsistent bundle memory profile metadata")
        if "queue.txt" not in files or regular(directory / "queue.txt", 65536) != queue:
            raise ValueError("bundle queue conflicts with memory profile")
    elif "queue.txt" in files:
        raise ValueError("queue requires explicit memory profile metadata")
    if queue_file is not None:
        if profile is None or regular(queue_file, 65536) != queue:
            raise ValueError("selected queue file differs from profile-bound bundle queue")
    audit = manifest.get("base_profile_audit")
    if audit is not None:
        if "base-profile-audit.json" not in files or "boot/kernel/kernel" not in files:
            raise ValueError("base profile audit lacks retained input identities")
        data = regular(directory / "base-profile-audit.json", 1024 * 1024)
        if audit != base_audit_record(data, cap, files["boot/kernel/kernel"]["sha256"]):
            raise ValueError("inconsistent base profile audit metadata")
    elif "base-profile-audit.json" in files:
        raise ValueError("base profile audit requires explicit metadata")
    return manifest


def memory_profile(cap):
    if cap not in MEMORY_CAPS:
        raise ValueError("unsupported bootstrap memory profile")
    return {"memory_cap": cap, "kernel_cap_bytes": 3 << 30 if cap == "3G" else None,
            "queue_hw_physmem": "3G" if cap == "3G" else "unset",
            "base_ufs_profile": "independent-readback-required",
            "runtime_memory_verified": False}


def base_audit_record(data, cap, kernel_sha256):
    """Bind externally obtained native readback assertions, not UFS inspection."""
    receipt = json.loads(data)
    if (not isinstance(receipt, dict) or
            receipt.get("schema") != "daemonarchy/pi5-base-profile-audit@1" or
            receipt.get("memory_cap") != cap or receipt.get("kernel_sha256") != kernel_sha256):
        raise ValueError("base profile audit disagrees with bundle memory cap or kernel")
    for field in ("image_sha256", "kernel_sha256", "loader_conf_sha256"):
        if not isinstance(receipt.get(field), str) or not re.fullmatch("[0-9a-f]{64}", receipt[field]):
            raise ValueError("base profile audit lacks exact readback identities")
    local_hash = receipt.get("loader_conf_local_sha256")
    if receipt.get("loader_conf_local_exists") is False:
        if "loader_conf_local_sha256" not in receipt or local_hash is not None:
            raise ValueError("absent loader.conf.local must have an explicit null hash")
    elif (receipt.get("loader_conf_local_exists", True) is not True or
          not isinstance(local_hash, str) or not re.fullmatch("[0-9a-f]{64}", local_hash)):
        raise ValueError("base profile audit lacks loader.conf.local readback identity")
    return {"path": "base-profile-audit.json", "sha256": hashlib.sha256(data).hexdigest(),
            "image_sha256": receipt["image_sha256"], "memory_cap": cap,
            "status": "external-readback-recorded", "ufs_verified_by_this_tool": False}


def stage(args):
    if not re.fullmatch(r"[0-9a-f]{40}", args.kernel_source_commit):
        raise ValueError("kernel source must have an exact Git commit identity")
    if args.board == "pi500" and args.stepping != "D0":
        raise ValueError("Pi 500 profile requires the separately enrolled D0 target")
    source = args.uboot_source.resolve()
    commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if commit != UBOOT_COMMIT or subprocess.check_output(
            ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"]):
        raise ValueError("U-Boot must be clean at the pinned v2026.10 commit")
    config = regular(args.uboot_build / ".config", 1024 * 1024)
    lines = config.decode().splitlines()
    if any(item not in lines for item in REQUIRED_CONFIG):
        raise ValueError("U-Boot lacks required SD/FDT/EFI/nonpersistent environment configuration")
    if any(item in lines for item in FORBIDDEN_CONFIG):
        raise ValueError("capsule updates, persistent FAT environment and automatic preboot are outside this control")
    if not elf_aarch64(regular(args.uboot_build / "u-boot", 128 * 1024 * 1024)):
        raise ValueError("U-Boot ELF is not little-endian AArch64")
    inputs = {
        "u-boot.bin": checked(args.uboot_build / "u-boot.bin", args.uboot_sha256, 16 * 1024 * 1024),
        "EFI/BOOT/BOOTAA64.EFI": checked(args.loader, args.loader_sha256, 32 * 1024 * 1024),
        "boot/kernel/kernel": checked(args.kernel, args.kernel_sha256, 256 * 1024 * 1024),
    }
    if not pe_aarch64(inputs["EFI/BOOT/BOOTAA64.EFI"]):
        raise ValueError("FreeBSD loader is not AArch64 PE32+ EFI")
    if not elf_aarch64(inputs["boot/kernel/kernel"]):
        raise ValueError("FreeBSD kernel is not little-endian AArch64 ELF")
    compatible = validate_dtb(args.dtb, args.board)
    dtb_name = "bcm2712-rpi-500.dtb" if args.board == "pi500" else (
        "bcm2712-d-rpi-5-b.dtb" if args.stepping == "D0" else "bcm2712-rpi-5-b.dtb")
    inputs[dtb_name] = checked(args.dtb, args.dtb_sha256, 16 * 1024 * 1024)
    inputs["u-boot.config"] = config
    inputs["config.txt"] = (
        "# Separate BCM2712 SD diagnostic media only.\n[all]\narm_64bit=1\n"
        f"kernel=u-boot.bin\ndevice_tree={dtb_name}\n"
        "enable_uart=1\nauto_initramfs=0\n").encode()
    inputs["boot.cmd"] = b'''# SD-only control; preserve the firmware-supplied, fixed-up FDT.
if test -z "${fdt_addr}"; then
    echo "Missing firmware FDT; refusing EFI handoff"
    exit
fi
if fatload mmc 0:1 ${kernel_addr_r} EFI/BOOT/BOOTAA64.EFI; then
    bootefi ${kernel_addr_r} ${fdt_addr}
else
    echo "SD EFI loader could not be read"
fi
'''
    cap = getattr(args, "memory_cap", "3G")
    inputs["boot/loader.conf.local"], inputs["queue.txt"] = memory_inputs(cap, args.board)
    audit_record = None
    if getattr(args, "base_profile_audit", None) is not None:
        data = regular(args.base_profile_audit, 1024 * 1024)
        audit_record = base_audit_record(data, cap, args.kernel_sha256)
        inputs["base-profile-audit.json"] = data
    for name in ("Licenses/README", "Licenses/gpl-2.0.txt"):
        inputs["licenses/u-boot/" + Path(name).name] = regular(source / name, 1024 * 1024)
    # Exclusive directory creation refuses an existing output, symlink or device.
    args.output.mkdir(mode=0o700)
    for name, data in inputs.items():
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    epoch = subprocess.check_output(
        ["git", "-C", str(source), "show", "-s", "--format=%ct", "HEAD"], text=True).strip()
    environment = dict(os.environ, SOURCE_DATE_EPOCH=epoch)
    subprocess.run([str(args.uboot_build / "tools/mkimage"), "-A", "arm64", "-O", "linux",
                    "-T", "script", "-C", "none", "-n", "Daemonarchy BCM2712 SD FDT control",
                    "-d", str(args.output / "boot.cmd"), str(args.output / "boot.scr")],
                   check=True, env=environment)
    files = {}
    for path in sorted(args.output.rglob("*")):
        if path.is_file():
            name = path.relative_to(args.output).as_posix()
            data = path.read_bytes()
            if name in inputs and data != inputs[name]:
                raise ValueError(f"staged input readback differs: {name}")
            files[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    manifest = dict(schema="daemonarchy/pi5-bootstrap-bundle@1", board=args.board,
                    stepping=args.stepping, compatible=compatible,
                    boot_path="EEPROM -> U-Boot v2026.10 -> EFI loader with firmware FDT",
                    uboot_commit=commit, source_date_epoch=int(epoch), firmware_identity=args.firmware_identity,
                    uboot_source_url="https://github.com/u-boot/u-boot/tree/" + commit,
                    kernel_source_commit=args.kernel_source_commit,
                    files=files, memory_profile=memory_profile(cap), boot_tested=False, limitations=[
                        "Staging bundle only; matching hwtrace Lua, rootfs and trace map required",
                        "SD-only control; USB/NVMe boot not qualified",
                        ("Initial 3 GiB kernel memory cap" if cap == "3G" else
                         "Uncapped experimental kernel memory profile; actual usable RAM unverified"),
                        "Bundle does not inspect the base UFS loader configuration",
                        "BCM2712/RP1 is not emulated by raspi4b",
                        "Native cold/warm boot and reset-surviving trace acceptance pending",
                        "FreeBSD RP1 nexus, interrupts, clocks, DMA and Cadence GEM remain unqualified",
                    ])
    if audit_record is not None:
        manifest["base_profile_audit"] = audit_record
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify_bundle(args.output, cap)
    return manifest


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--verify-bundle":
        parser = argparse.ArgumentParser(description="Check bundle bytes, memory profile and queue; no UFS or runtime qualification")
        parser.add_argument("--verify-bundle", type=Path, required=True)
        parser.add_argument("--memory-cap", choices=MEMORY_CAPS)
        parser.add_argument("--queue-file", type=Path,
                            help="experiment source file to compare byte-for-byte with bundle queue.txt")
        args = parser.parse_args()
        try:
            manifest = verify_bundle(args.verify_bundle, args.memory_cap, args.queue_file)
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.exit(1, f"Bootstrap validation refused: {error}\n")
        print(json.dumps({"memory_profile": manifest.get("memory_profile", memory_profile("3G")),
                          "bundle_files_verified": True, "base_ufs_verified": False}, indent=2))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--board", choices=BOARDS, required=True)
    parser.add_argument("--stepping", choices=("C1", "D0"), required=True)
    for option in ("uboot-source", "uboot-build", "dtb", "loader", "kernel"):
        parser.add_argument("--" + option, type=Path, required=True)
    for option in ("uboot", "dtb", "loader", "kernel"):
        parser.add_argument("--" + option + "-sha256", required=True)
    parser.add_argument("--firmware-identity", required=True,
                        help="retained source/package identity of the board DTB and current EEPROM")
    parser.add_argument("--base-profile-audit", type=Path,
                        help="optional external native UFS profile audit JSON; recorded, not independently verified")
    parser.add_argument("--kernel-source-commit", required=True)
    parser.add_argument("--memory-cap", choices=MEMORY_CAPS, default="3G",
                        help="kernel memory cap; none is experimental and requires separate base-UFS readback")
    args = parser.parse_args()
    try:
        stage(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Bootstrap staging refused: {error}\n")
    print(f"Staged {args.output}; physical boot and image assembly remain pending")


if __name__ == "__main__":
    main()
