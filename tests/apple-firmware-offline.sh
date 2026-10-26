#!/usr/bin/env bash
# Offline MacBook firmware source selection with shimmed devices and mounts.
# Checks that the internal disk is never mounted, other media are mounted
# read-only and unmounted again, and every source goes through the importer.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
log=$work/log
: >"$log"
ISO_SHARE=$work/share
APFS_FIXTURE=$work/media
mkdir -p "$ISO_SHARE" "$APFS_FIXTURE/da1s1/sub" "$APFS_FIXTURE/da2p1/Recovery/42"
APPLE_FIRMWARE_STAGE=$work/stage
APPLE_FIRMWARE_IMPORTER=$work/importer
cat >"$APPLE_FIRMWARE_IMPORTER" <<EOF
#!/bin/sh
echo "importer \$*" >>"$log"
case "\$*" in *"\${ACCEPT:-none}"*) exit 0 ;; esac
exit 1
EOF
chmod 0755 "$APPLE_FIRMWARE_IMPORTER"
# shellcheck source=/dev/null
source "$here/overlay/usr/local/libexec/daemonarchy-installer/apple-firmware"

: >"$APFS_FIXTURE/da1s1/sub/brcmfmac4364b3-pcie.bin"
: >"$APFS_FIXTURE/da2p1/Recovery/42/BaseSystem.dmg"
apple_firmware_devices() { printf '%s\n' /dev/da0 /dev/nda0p1 /dev/nda0p2 /dev/da1s1 /dev/da2p1 /dev/da3p1; }
fstyp() {
  case $1 in
    /dev/da0) echo cd9660 ;;
    /dev/nda0p1) echo msdosfs ;;
    /dev/nda0p2) echo apfs ;;
    /dev/da1s1) echo msdosfs ;;
    /dev/da2p1) echo ufs ;;
    /dev/da3p1) echo exfat ;;
    *) return 1 ;;
  esac
}
mount() {
  if [[ $1 == -p ]]; then
    printf '/dev/da0\t/\tcd9660\tro\t0 0\n'
    return
  fi
  echo "attempt $*" >>"$log"
  local source=$APFS_FIXTURE/${4#/dev/}
  [[ -d $source ]] || return 1
  echo "mount $*" >>"$log"
  cp -R "$source/." "$5/"
}
umount() { echo "umount ${1#"$work"}" >>"$log"; rm -rf "${1:?}"/*; }

fail() { echo "FAIL: $*" >&2; cat "$log" >&2; exit 1; }

# Internal source: only the APFS partition, through the importer, never mounted.
if apple_firmware_prepare_internal 2>/dev/null; then fail 'accepted an unverified internal disk'; fi
[[ $(cat "$log") == "importer --internal-disk /dev/nda0p2 --model MacBookPro16,1 --destination $APPLE_FIRMWARE_STAGE" ]] ||
  fail 'internal source did not read only the APFS device'

# Second media: every unmounted FAT/UFS volume is mounted read-only, searched
# through the importer and unmounted; the live ISO, APFS and exFAT are skipped.
: >"$log"
if apple_firmware_prepare_media 2>/dev/null; then fail 'accepted unverified media'; fi
grep -q 'attempt .*/dev/da0 ' "$log" && fail 'mounted the live boot media'
grep -q 'attempt .*nda0p' "$log" && fail 'mounted a partition of the internal APFS disk'
grep -q 'attempt .*da3p1' "$log" && fail 'mounted an unsupported filesystem'
grep -q '^mount ' "$log" || fail 'no media was mounted'
if grep '^attempt ' "$log" | grep -qv '^attempt -r '; then fail 'mounted media writable'; fi
[[ $(grep -c '^mount ' "$log") == $(grep -c '^umount ' "$log") ]] || fail 'left media mounted'
grep -q -- '--files /tmp/daemonarchy-firmware-media\.[^ ]*/sub ' "$log" || fail 'skipped verified files'
grep -q -- '--image /tmp/daemonarchy-firmware-media\.[^ ]*/Recovery/42/BaseSystem.dmg ' "$log" ||
  fail 'skipped a recovery image'
if compgen -G '/tmp/daemonarchy-firmware-media.*' >/dev/null; then
  for leftover in /tmp/daemonarchy-firmware-media.*; do
    grep -q "$leftover" "$log" && fail "left mount point $leftover"
  done
fi

# Success stops the search and still unmounts the stick.
apple_firmware_prepare() { echo "prepare $1 ${2#/tmp/daemonarchy-firmware-media.*/}" >>"$log"; [[ $1 == files ]]; }
: >"$log"
apple_firmware_prepare_media >/dev/null || fail 'did not accept verified files'
grep -q '^prepare files sub$' "$log" || fail 'verified files were not prepared'
grep -q 'prepare image' "$log" && fail 'kept searching after success'
[[ $(grep -c '^mount ' "$log") == $(grep -c '^umount ' "$log") ]] || fail 'left media mounted after success'

# The configurator offers both offline paths ahead of the Ethernet download,
# and the unattended installer tries them before downloading.
configurator=$here/overlay/usr/local/libexec/daemonarchy-installer/configurator
internal=$(grep -n "Read from this Mac's internal macOS Recovery" "$configurator" | head -1 | cut -d: -f1)
usb=$(grep -n 'Read from a second USB stick' "$configurator" | head -1 | cut -d: -f1)
download=$(grep -n "Download Apple's recovery image using Ethernet" "$configurator" | head -1 | cut -d: -f1)
((internal < download && usb < download)) || fail 'offline sources are not offered first'
grep -q 'apple_firmware_prepare_internal || apple_firmware_prepare_media ||' \
  "$here/overlay/usr/local/libexec/daemonarchy-installer/install" || fail 'installer downloads before offline sources'
# Generic FreeBSD Wi-Fi firmware stays on the media; Apple board files never do.
grep -q 'net/wifi-firmware-\*-kmod | net/wifi-firmware-kmod)' "$here/build-iso.sh" || fail 'ISO repo drops wifi-firmware-kmod'
grep -q '^printf .* wifi-firmware-kmod .*live-packages' "$here/build-iso.sh" || fail 'live image drops wifi-firmware-kmod'
grep -q 'brcmfmac4364' "$here/build-iso.sh" "$here/scripts/live-image-excludes" && fail 'build stages Apple board files'
echo 'PASS: offline MacBook firmware sources read-only, verified and offered before download'
