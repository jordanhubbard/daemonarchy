#!/usr/bin/env bash
# Portable policy tests: no module loading, pkg installation, or disk writes.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/gpu-config"
ids=$here/overlay/usr/local/share/daemonarchy-installer/gpu-ids
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
check() { [[ $1 == "$2" ]] || { echo "Expected '$2', got '$1'" >&2; exit 1; }; }
select_gpu() {
  printf '%s\n' "$@" >"$work/pci"
  gpu_select "$work/pci" "$ids"
}
select_gpu 'virtio_pci0@pci0:0:1:0: class=0x030000 vendor=0x1af4 device=0x1050'
check "$kld_list" virtio_gpu_drm
check "$gpu_virtio" true
check "$gpu_vulkan" false
check "${gpu_userspace_packages[*]}" mesa-dri
mkdir -p "$work/virtio/boot" "$work/virtio/etc"
gpu_write_config "$work/virtio"
grep -qx 'daemonarchy_graphics_modules="virtio_gpu_drm"' "$work/virtio/etc/rc.conf"
grep -q '^devmatch_blocklist=".* virtio_gpu_drm"$' "$work/virtio/etc/rc.conf"
select_gpu 'virtio_pci1@pci0:0:2:0: class=0x020000 vendor=0x1af4 device=0x1000'
check "$kld_list" ''
check "$gpu_virtio" false
select_gpu 'vgapci0@pci0:3:0:0: class=0x030000 vendor=0x1002 device=0x7340 subvendor=0x106b subdevice=0x021e'
check "$kld_list" amdgpu
check "$gpu_navi14" true
check "$gpu_vulkan" true
check "${gpu_packages[*]}" gpu-firmware-amd-kmod-navi14
check "${gpu_userspace_packages[*]}" 'vulkan-loader mesa-dri'
select_gpu 'vgapci0@pci0:1:0:0: class=0x030000 vendor=0x1002 device=0x68c1'
check "$kld_list" radeonkms
check "$gpu_vulkan" false
check "${gpu_userspace_packages[*]}" ''
check "$gpu_navi14" false
select_gpu 'vgapci0@pci0:1:0:0: class=0x030000 vendor=0x1002 device=0x71c5'
check "$kld_list" radeonkms
select_gpu 'vgapci0@pci0:1:0:0: class=0x030000 vendor=0x1002 device=0x67ef'
check "$kld_list" amdgpu
for device in 2182 1e04 2204 2684 2b85; do
  select_gpu "vgapci0@pci0:1:0:0: class=0x030000 vendor=0x10de device=0x$device"
  check "$kld_list" 'linux linux64 nvidia-drm'
  check "$gpu_vulkan" true
  check "${gpu_packages[*]}" 'nvidia-driver nvidia-kmod nvidia-drm-612-kmod linux-nvidia-libs'
  check "${gpu_userspace_packages[*]}" 'vulkan-loader mesa-dri'
done
mkdir -p "$work/nvidia/boot" "$work/nvidia/etc"
touch "$work/nvidia/etc/rc.conf"
gpu_write_config "$work/nvidia"
grep -qx 'hw.nvidiadrm.modeset="1"' "$work/nvidia/boot/loader.conf"
grep -qx 'export GBM_BACKEND=nvidia-drm' "$work/nvidia/usr/local/share/uwsm/env.d/90-daemonarchy-nvidia"
grep -qx 'linux_enable="YES"' "$work/nvidia/etc/rc.conf"
select_gpu 'vgapci0@pci0:0:2:0: class=0x030000 vendor=0x8086 device=0x3e9b'
check "$kld_list" i915kms
check "$gpu_vulkan" true
check "${gpu_userspace_packages[*]}" 'vulkan-loader mesa-dri'
for device in 0393 0407 0863 0a29 0fd5 0fe9 13c2 1b80 ffff; do
  select_gpu "vgapci0@pci0:1:0:0: class=0x030000 vendor=0x10de device=0x$device"
  check "$gpu_nvidia" false
done
# HDMI audio must not trigger a driver; duplicate display functions are unique.
select_gpu 'hdac0@pci0:1:0:1: class=0x040300 vendor=0x10de device=0x1e04'
check "$kld_list" ''
select_gpu \
  'vgapci0@pci0:0:2:0: class=0x030000 vendor=0x8086 device=0x3e9b' \
  'vgapci1@pci0:1:0:0: class=0x030200 vendor=0x10de device=0x2684' \
  'vgapci2@pci0:2:0:0: class=0x030000 vendor=0x10de device=0x2684'
check "$kld_list" 'linux linux64 i915kms nvidia-drm'
mkdir -p "$work/mixed/boot"
gpu_write_config "$work/mixed"
[[ ! -e $work/mixed/usr/local/share/uwsm/env.d/90-daemonarchy-nvidia ]]
# A subsystem-only supported product cannot admit a different notebook design.
specific=$(awk '$1 == "10de" && $3 != "*" { print $2; exit }' "$ids")
awk -v d="$specific" '$1 == "10de" && $2 == d && $3 != "*"' "$ids" >"$work/subsystem-ids"
printf 'vgapci0@pci0:1:0:0: class=0x030000 vendor=0x10de device=0x%s subvendor=0xffff subdevice=0xffff\n' "$specific" >"$work/pci"
gpu_select "$work/pci" "$work/subsystem-ids"
check "$gpu_nvidia" false
# Missing/malformed payload fails before installation; no fallback to remote kmods.
select_gpu 'vgapci0@pci0:1:0:0: class=0x030000 vendor=0x10de device=0x2684'
mkdir -p "$work/repo/All"
for name in drm-612-kmod gpu-firmware-kmod nvidia-driver nvidia-kmod nvidia-drm-612-kmod linux-nvidia-libs; do
  printf '%s 1.0\n' "$name" >>"$work/manifest"
  touch "$work/repo/All/$name-1.0.pkg"
done
gpu_resolve_packages "$work/manifest" "$work/repo"
check "${#gpu_exact_packages[@]}" 6
# The same image on AMD selects the shared 6.12 core without NVIDIA packages.
select_gpu 'vgapci0@pci0:1:0:0: class=0x030000 vendor=0x1002 device=0x67ef'
gpu_resolve_packages "$work/manifest" "$work/repo"
check "${gpu_lock_packages[*]}" 'drm-612-kmod gpu-firmware-kmod'
# A stale image manifest must not silently select the conflicting 6.6 core.
sed 's/^drm-612-kmod /drm-66-kmod /' "$work/manifest" >"$work/stale-manifest"
if gpu_resolve_packages "$work/stale-manifest" "$work/repo"; then echo 'Accepted stale DRM family' >&2; exit 1; fi
select_gpu 'vgapci0@pci0:1:0:0: class=0x030000 vendor=0x10de device=0x2684'
rm "$work/repo/All/nvidia-kmod-1.0.pkg"
if gpu_resolve_packages "$work/manifest" "$work/repo"; then echo 'Accepted missing kmod' >&2; exit 1; fi
if gpu_select "$work/pci" "$work/missing-ids"; then echo 'Accepted missing table' >&2; exit 1; fi
(
  gpu_nvidia=true
  kldstat() { return 1; }
  kldload() { echo "$1" >>"$work/live-loaded"; }
  sysctl() { echo 1; }
  gpu_prepare_live_compat
  printf 'linux\nlinux64\n' >"$work/live-expected"
  cmp "$work/live-expected" "$work/live-loaded"
  sysctl() { return 1; }
  if gpu_prepare_live_compat; then echo 'Missing Linux64 support accepted' >&2; exit 1; fi
  kldload() { return 1; }
  if gpu_prepare_live_compat; then echo 'Failed compatibility load accepted' >&2; exit 1; fi
  gpu_nvidia=false
  gpu_prepare_live_compat
)
echo 'PASS: GPU selection, live Linux ABI prerequisites, mixed GPU environment, and payload admission'
