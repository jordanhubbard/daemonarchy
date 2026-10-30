#!/usr/local/bin/bash
# Prove the installer's package selections resolve from the repositories an image ships
# with, and from nothing else: the ISO's own repository, the application feed and the
# closure feed (pkg.FreeBSD.org is deliberately NOT configured). Dry run only:
# `pkg install -n` into a scratch root; nothing is installed.
#
#   check-install-resolution.sh ISO_PACKAGES_DIR APP_FEED_DIR CLOSURE_DIR [msi|macbook|all]
#
#   ISO_PACKAGES_DIR  the poudriere package directory the ISO is built from (All/*.pkg)
#   APP_FEED_DIR      the staged application feed (packages + packagesite.pkg)
#   CLOSURE_DIR       the staged closure shard (packages + packagesite.pkg)
#
# Run as root on a FreeBSD host with pkg and the target ABI. The selections mirror what
# gpu-config chooses: the MSI (Intel Arrow Lake iGPU + NVIDIA, CUDA, Wi-Fi) and the
# MacBookPro16,1 (T2, Radeon Pro, BCM4364 brcmfmac).
set -euo pipefail

iso=${1:?ISO_PACKAGES_DIR}
app=${2:?APP_FEED_DIR}
closure=${3:?CLOSURE_DIR}
which=${4:-all}
here=$(cd "$(dirname "$0")/.." && pwd)
ABI=${ABI:-FreeBSD:16:amd64}
# shellcheck disable=SC1091
. "$here/origins.sh"

base_roots='pkg bash sudo daemonarchy chromium octopkg wifi-firmware-kmod'
msi_roots="$base_roots xwayland drm-612-kmod gpu-firmware-intel-kmod nvidia-driver nvidia-kmod nvidia-drm-612-kmod linux-nvidia-libs"
macbook_roots="$base_roots drm-612-kmod gpu-firmware-amd-kmod-navi14 if_brcmfmac-kmod"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/repos" "$work/iso/All"

# The ISO's own repository: what build-iso.sh copies from the package directory.
for f in "$iso"/All/*.pkg; do
  origin=$(pkg query -F "$f" '%o')
  case " $(echo $ISO_ORIGINS) " in
    *" $origin "*) cp "$f" "$work/iso/All/" ;;
    *) case $origin in
         graphics/gpu-firmware-*-kmod | net/wifi-firmware-*-kmod | net/wifi-firmware-kmod) cp "$f" "$work/iso/All/" ;;
       esac ;;
  esac
done
pkg repo -q "$work/iso" >/dev/null
echo "ISO repository: $(ls "$work/iso/All" | wc -l | tr -d ' ') packages"

cat >"$work/repos/repos.conf" <<EOF
Daemonarchy: { url: "file://$work/iso", signature_type: "none", priority: 10, enabled: yes }
Daemonarchy-Dependencies: { url: "file://$app", signature_type: "none", priority: 9, enabled: yes }
Daemonarchy-Closure: { url: "file://$closure", signature_type: "none", priority: 5, enabled: yes }
EOF

resolve() {
  local label=$1 roots=$2 root=$work/root-$1 out=$work/$1.out status=0
  mkdir -p "$root"
  ASSUME_ALWAYS_YES=yes IGNORE_OSVERSION=yes pkg -r "$root" -o REPOS_DIR="$work/repos" -o ABI="$ABI" \
      -o PKG_DBDIR="$root/db" -o PKG_CACHEDIR="$work/cache" update -f >"$out" 2>&1 || true
  ASSUME_ALWAYS_YES=yes IGNORE_OSVERSION=yes pkg -r "$root" -o REPOS_DIR="$work/repos" -o ABI="$ABI" \
      -o PKG_DBDIR="$root/db" -o PKG_CACHEDIR="$work/cache" install -n -y $roots >>"$out" 2>&1 || status=$?
  if [ "$status" -ne 0 ]; then
    echo "$label: NOT RESOLVED"
    grep -E 'missing|No packages|conflict|cannot' "$out" | head -8
    return 1
  fi
  echo "$label: resolved: $(grep -E 'Number of packages to be installed' "$out" | head -1)"
  # Everything must come from the three repositories; a package from nowhere would have failed above.
  grep -E '\[(Daemonarchy|Daemonarchy-Dependencies|Daemonarchy-Closure)\]' "$out" | sed 's/.*\[\(.*\)\]/\1/' | sort | uniq -c | sed 's/^/    from /'
}

status=0
case $which in
  msi | all) resolve msi "$msi_roots" || status=1 ;;
esac
case $which in
  macbook | all) resolve macbook "$macbook_roots" || status=1 ;;
esac
exit "$status"
