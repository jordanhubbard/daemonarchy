# shellcheck shell=sh disable=SC2034
# Sourced by build-iso.sh and tests: the per-architecture image defaults.
# amd64 keeps its historical values. aarch64 is UEFI-only: no BIOS hybrid boot
# code, no NVIDIA/CUDA, no DRM kernel modules (amd64-only ports) and no Apple
# T2 BCM4364 driver. Each architecture has its own jail, sets, feeds and image.
image_architecture_select() { # ARCH
    case "$1" in
        amd64)
            image_abi=FreeBSD:16:amd64
            image_jail=16amd64
            image_snapshot_url=https://download.freebsd.org/snapshots/amd64/16.0-CURRENT
            image_set_cache_dir=/var/cache/daemonarchy-iso
            image_efi_boot_file=BOOTX64.EFI
            image_type=hybridiso
            image_kernel_packages=if_brcmfmac-kmod
            ;;
        aarch64)
            image_abi=FreeBSD:16:aarch64
            image_jail=16aarch64
            image_snapshot_url=https://download.freebsd.org/snapshots/arm64/aarch64/16.0-CURRENT
            # A separate set cache: verified sets never cross architectures.
            image_set_cache_dir=/var/cache/daemonarchy-iso-aarch64
            image_efi_boot_file=BOOTAA64.EFI
            image_type=efi-iso
            image_kernel_packages=
            ;;
        *)
            echo "Unsupported image architecture: $1 (expected amd64 or aarch64)" >&2
            return 1
            ;;
    esac
    image_package_repository_tag=packages-16-$1
}
