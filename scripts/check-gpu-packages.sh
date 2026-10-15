#!/bin/sh
# Validate ISO GPU payload against the image ABI; emit name/version manifest.
# Run on FreeBSD: check-gpu-packages.sh repository/All FreeBSD_version
set -eu
packages=$1
osversion=$2
manifest=$(mktemp)
trap 'rm -f "$manifest"' EXIT HUP INT TERM
for file in "$packages"/*.pkg; do
  name=$(pkg query -F "$file" '%n')
  case "$name" in
    drm-612-kmod|gpu-firmware-*|nvidia-driver|nvidia-kmod|nvidia-drm-612-kmod|linux-nvidia-libs) ;;
    drm-*-kmod|nvidia-*) echo "Unexpected GPU package: $name" >&2; exit 1 ;;
    *) continue ;;
  esac
  version=$(pkg query -F "$file" '%v')
  case "$name" in
    drm-612-kmod) case "$version" in 6.12.85.*) ;; *) echo "Refresh the DRM PCI table before changing DRM versions" >&2; exit 1 ;; esac ;;
    linux-nvidia-libs|nvidia-*) case "$version" in 595.104.02|595.104.02.*|595.104.02_*) ;; *) echo "Refresh the NVIDIA PCI table before changing driver versions" >&2; exit 1 ;; esac ;;
  esac
  abi=$(pkg query -F "$file" '%q')
  case "$name:$abi" in
    gpu-firmware-kmod:FreeBSD:16:\*) ;;
    *:FreeBSD:16:amd64) ;;
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
for name in drm-612-kmod gpu-firmware-kmod gpu-firmware-amd-kmod-navi14 nvidia-driver nvidia-kmod nvidia-drm-612-kmod linux-nvidia-libs; do
  count=$(awk -v n="$name" '$1 == n { count++ } END { print count+0 }' "$manifest")
  [ "$count" = 1 ] || { echo "Need exactly one $name package, found $count" >&2; exit 1; }
done
sort "$manifest"
