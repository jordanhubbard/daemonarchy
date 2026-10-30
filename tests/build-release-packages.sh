#!/usr/bin/env bash
# The release package build rebuilds what is kernel-bound or changed, and nothing else.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
script=$here/scripts/build-release-packages.sh
bash -n "$script"
# shellcheck disable=SC1090
source "$script"

# Kernel-bound and release-changed origins are rebuilt ...
for origin in graphics/drm-612-kmod graphics/gpu-firmware-amd-kmod net/wifi-firmware-iwlwifi-kmod \
              net/if_brcmfmac-kmod x11/nvidia-driver x11/nvidia-kmod graphics/nvidia-drm-612-kmod \
              x11/linux-nvidia-libs x11-wm/omarchy x11-wm/daemonarchy; do
  must_rebuild_origin "$origin" || { echo "$origin must be rebuilt" >&2; exit 1; }
done
# ... and the retained userland is not (chromium would take many hours).
for origin in www/chromium multimedia/obs-studio net/tigervnc-viewer x11-toolkits/fltk x11/quickshell \
              x11-toolkits/aquamarine devel/usage archivers/7-zip security/sudo; do
  ! must_rebuild_origin "$origin" || { echo "$origin must be retained" >&2; exit 1; }
done

# The bulk list is the ISO's origins plus the live root's, once each.
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
ORIGINS_FILE=$work/origins bash "$script" origins >/dev/null
[[ $(sort "$work/origins" | uniq -d | wc -l) == 0 ]]
for origin in net/tigervnc-viewer x11-toolkits/fltk x11-wm/daemonarchy x11-wm/omarchy net/if_brcmfmac-kmod \
              x11/nvidia-kmod graphics/drm-612-kmod security/sudo archivers/7-zip x11/quickshell \
              databases/py-sqlite3@py312; do
  grep -qx "$origin" "$work/origins" || { echo "$origin missing from the bulk list" >&2; exit 1; }
done
[[ $(wc -l <"$work/origins") -ge 30 ]]

# Unknown commands print usage and fail.
! bash "$script" nonsense >/dev/null 2>&1
echo 'build-release-packages checks passed'
