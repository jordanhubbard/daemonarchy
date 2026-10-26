#!/bin/sh
# Validate ISO GPU payload against the image ABI; emit name/version manifest.
# Run on FreeBSD: check-gpu-packages.sh repository/All FreeBSD_version [ABI]
# The DRM and NVIDIA kernel module ports are amd64-only; an aarch64 image
# carries only the architecture-neutral firmware and refuses any of them.
set -eu
packages=$1
osversion=$2
abi_expected=${3:-FreeBSD:16:amd64}
case "$abi_expected" in
  FreeBSD:16:amd64) required='drm-612-kmod gpu-firmware-kmod gpu-firmware-amd-kmod-navi14 nvidia-driver nvidia-kmod nvidia-drm-612-kmod linux-nvidia-libs' ;;
  FreeBSD:16:aarch64) required='gpu-firmware-kmod' ;;
  *) echo "Unsupported image ABI: $abi_expected" >&2; exit 1 ;;
esac
manifest=$(mktemp)
trap 'rm -f "$manifest"' EXIT HUP INT TERM
for file in "$packages"/*.pkg; do
  name=$(pkg query -F "$file" '%n')
  case "$name" in
    gpu-firmware-*) ;;
    drm-612-kmod|nvidia-driver|nvidia-kmod|nvidia-drm-612-kmod|linux-nvidia-libs)
      [ "$abi_expected" = FreeBSD:16:amd64 ] || { echo "Unexpected $abi_expected GPU package: $name" >&2; exit 1; } ;;
    drm-*-kmod|nvidia-*) echo "Unexpected GPU package: $name" >&2; exit 1 ;;
    *) continue ;;
  esac
  version=$(pkg query -F "$file" '%v')
  case "$name" in
    drm-612-kmod) case "$version" in 6.12.110.*) ;; *) echo "Refresh the DRM PCI table before changing DRM versions" >&2; exit 1 ;; esac ;;
    linux-nvidia-libs|nvidia-*) case "$version" in 595.104.02|595.104.02.*|595.104.02_*) ;; *) echo "Refresh the NVIDIA PCI table before changing driver versions" >&2; exit 1 ;; esac ;;
  esac
  if [ "$name" = drm-612-kmod ]; then
    pkg query -F "$file" '%Fp' | grep -qx '/boot/modules/virtio_gpu_drm.ko' || {
      echo 'DRM package lacks the VirtIO module required by this installer' >&2
      exit 1
    }
  fi
  abi=$(pkg query -F "$file" '%q')
  case "$name:$abi" in
    gpu-firmware-kmod:FreeBSD:16:\*) ;;
    *:"$abi_expected") ;;
    *) echo "$name: unexpected ABI $abi" >&2; exit 1 ;;
  esac
  case "$name" in
    drm-612-kmod|nvidia-kmod|nvidia-drm-612-kmod|gpu-firmware-*-kmod-*)
      built_for=$(pkg query -F "$file" '%At %Av' | awk '$1 == "FreeBSD_version" { print $2 }')
      [ "$built_for" = "$osversion" ] || { echo "$name: built for $built_for, image is $osversion" >&2; exit 1; }
      ;;
  esac
  printf '%s %s\n' "$name" "$version" >>"$manifest"
done
for name in $required; do
  count=$(awk -v n="$name" '$1 == n { count++ } END { print count+0 }' "$manifest")
  [ "$count" = 1 ] || { echo "Need exactly one $name package, found $count" >&2; exit 1; }
done
sort "$manifest"
