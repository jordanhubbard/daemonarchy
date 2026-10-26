#!/usr/bin/env bash
# Portable per-architecture image and installer policy checks. No image is
# built, no module is loaded and no disk is written; native ISO, boot and
# install results for each architecture come only from their own workers.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
check() { [[ $1 == "$2" ]] || { echo "Expected '$2', got '$1'" >&2; exit 1; }; }
refuses() { if "$@" >/dev/null 2>&1; then echo "Accepted: $*" >&2; exit 1; fi; }

# Build defaults: amd64 keeps its historical values exactly.
source "$here/scripts/image-architecture.sh"
image_architecture_select amd64
check "$image_abi $image_jail $image_type $image_efi_boot_file" 'FreeBSD:16:amd64 16amd64 hybridiso BOOTX64.EFI'
check "$image_snapshot_url" https://download.freebsd.org/snapshots/amd64/16.0-CURRENT
check "$image_set_cache_dir $image_package_repository_tag" '/var/cache/daemonarchy-iso packages-16-amd64'
check "$image_kernel_packages" if_brcmfmac-kmod
image_architecture_select aarch64
check "$image_abi $image_jail $image_type $image_efi_boot_file" 'FreeBSD:16:aarch64 16aarch64 efi-iso BOOTAA64.EFI'
check "$image_snapshot_url" https://download.freebsd.org/snapshots/arm64/aarch64/16.0-CURRENT
check "$image_set_cache_dir $image_package_repository_tag" '/var/cache/daemonarchy-iso-aarch64 packages-16-aarch64'
check "$image_kernel_packages" ''
for arch in arm64 x86_64 i386 ''; do refuses image_architecture_select "$arch"; done

# The amd64 live package list is byte-identical to the list before ARCH support.
image_architecture_select amd64
# shellcheck disable=SC2086
printf '%s\n' bash gum jq ttfx tzupdate pkg wifi-firmware-kmod $image_kernel_packages 7-zip >"$work/amd64"
printf '%s\n' bash gum jq ttfx tzupdate pkg wifi-firmware-kmod if_brcmfmac-kmod 7-zip >"$work/historical"
cmp "$work/amd64" "$work/historical"
image_architecture_select aarch64
# shellcheck disable=SC2086
printf '%s\n' bash gum jq ttfx tzupdate pkg wifi-firmware-kmod $image_kernel_packages 7-zip >"$work/aarch64"
! grep -q brcmfmac "$work/aarch64"

# build-iso.sh refuses a mismatched ABI and an unknown architecture before any
# FreeBSD tool or input is used.
refuses env ARCH=aarch64 ABI=FreeBSD:16:amd64 sh "$here/build-iso.sh"
refuses env ARCH=arm64 sh "$here/build-iso.sh"
{ env ARCH=aarch64 ABI=FreeBSD:16:amd64 sh "$here/build-iso.sh" 2>&1 || true; } | grep -q 'does not match ARCH'
refuses env ARCH=riscv64 sh "$here/pkg-repo.sh" collect

# Every amd64-only ISO origin is an ISO origin; the remainder suits aarch64.
source "$here/origins.sh"
for origin in $ISO_ORIGINS_AMD64_ONLY; do
  [[ " $(echo $ISO_ORIGINS) " == *" $origin "* ]] || { echo "Not an ISO origin: $origin" >&2; exit 1; }
done
check "$(echo $ISO_ORIGINS_AMD64_ONLY | wc -w | tr -d ' ')" 6

# The UEFI ISO builder validates its request before touching any input.
iso=$here/scripts/make-efi-iso.sh
refuses sh "$iso"
refuses sh "$iso" "$work/none.txz" 'bad-label' "$work/out.iso" "$work/w"
refuses sh "$iso" "$work/none.txz" LABEL "$work/out.iso" "$work/w" BOOTIA32.EFI
refuses env ESP_SIZE_KB=2m sh "$iso" "$work/none.txz" LABEL "$work/out.iso" "$work/w"
refuses sh "$iso" "$work/none.txz" LABEL "$work/out.iso" "$work/w"
[[ ! -e $work/w && ! -e $work/out.iso ]]

# Installed EFI fallback loader name per architecture.
source "$here/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
for pair in 'amd64 BOOTX64.EFI' 'aarch64 BOOTAA64.EFI'; do
  read -r arch boot_file <<<"$pair"
  target=$work/target-$arch
  mkdir -p "$target/boot/efi"
  printf 'loader-%s' "$arch" >"$target/boot/loader.efi"
  write_efi_loader "$target" zroot false "$boot_file"
  cmp "$target/boot/loader.efi" "$target/boot/efi/EFI/BOOT/$boot_file"
  cmp "$target/boot/loader.efi" "$target/boot/efi/EFI/FreeBSD/loader.efi"
  check "$(ls "$target/boot/efi/EFI/BOOT")" "$boot_file"
done
target=$work/target-default
mkdir -p "$target/boot/efi"
echo loader >"$target/boot/loader.efi"
write_efi_loader "$target" zroot false
[[ -f $target/boot/efi/EFI/BOOT/BOOTX64.EFI ]]
target=$work/target-bad
mkdir -p "$target/boot/efi"
echo loader >"$target/boot/loader.efi"
refuses write_efi_loader "$target" zroot false BOOTIA32.EFI

# GPU selection: aarch64 packages no KMS driver and selects none.
ids=$here/overlay/usr/local/share/daemonarchy-installer/gpu-ids
source "$here/overlay/usr/local/libexec/daemonarchy-installer/gpu-config"
printf '%s\n' 'vgapci0@pci0:3:0:0: class=0x030000 vendor=0x10de device=0x2684' \
  'virtio_pci0@pci0:0:1:0: class=0x030000 vendor=0x1af4 device=0x1050' >"$work/pci"
gpu_arch=aarch64
gpu_select "$work/pci" "$ids" 2>"$work/gpu.log"
check "$kld_list" ''
check "$gpu_nvidia $gpu_virtio" 'false false'
check "${gpu_packages[*]}${gpu_userspace_packages[*]}" ''
grep -q 'no aarch64 KMS driver' "$work/gpu.log"
mkdir -p "$work/repo/All"
printf 'gpu-firmware-kmod 20260519\n' >"$work/gpu-packages"
touch "$work/repo/All/gpu-firmware-kmod-20260519.pkg"
gpu_resolve_packages "$work/gpu-packages" "$work/repo"
check "${gpu_exact_packages[*]}" gpu-firmware-kmod-20260519
printf 'drm-612-kmod 6.12.110.1600027\ngpu-firmware-kmod 20260519\n' >"$work/gpu-packages"
touch "$work/repo/All/drm-612-kmod-6.12.110.1600027.pkg"
refuses gpu_resolve_packages "$work/gpu-packages" "$work/repo"
gpu_arch=amd64
refuses gpu_resolve_packages "$work/gpu-packages.missing" "$work/repo"
printf 'gpu-firmware-kmod 20260519\n' >"$work/gpu-packages"
refuses gpu_resolve_packages "$work/gpu-packages" "$work/repo"
gpu_select "$work/pci" "$ids" 2>/dev/null
[[ $gpu_nvidia == true ]]
gpu_arch=riscv64
refuses gpu_select "$work/pci" "$ids"

echo 'PASS: per-architecture image defaults, EFI fallback names, GPU selection and request validation'
