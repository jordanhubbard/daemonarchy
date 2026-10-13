#!/usr/local/bin/bash
# Run on FreeBSD as root. Only the memory disk allocated here is modified.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || {
  echo 'Run this test on FreeBSD as root.' >&2
  exit 1
}
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
md=''
cleanup() {
  [[ -z $md ]] || mdconfig -d -u "${md#md}"
}
trap cleanup EXIT
for sector_size in 512 4096; do
  md=$(mdconfig -a -t swap -s 6g -S "$sector_size")
  [[ $md =~ ^md[0-9]+$ ]] || exit 1
  create_whole_disk_layout "$md"
  layout=$(gpart show "$md")
  for pair in '1 efi' '2 freebsd-swap' '3 freebsd-zfs' '4 freebsd-boot'; do
    read -r index type <<<"$pair"
    awk -v i="$index" -v t="$type" '$3 == i && $4 == t { found=1 } END { exit !found }' <<<"$layout"
  done
  # Install actual native bootcode and verify that the payload reached p4.
  install_bios_bootcode "$md" ""
  bytes=$(stat -f %z /boot/gptzfsboot)
  cmp -n "$bytes" /boot/gptzfsboot "/dev/${md}p4"
  echo "PASS: ${sector_size}-byte sectors, stable partition indices, BIOS bootcode"
  mdconfig -d -u "${md#md}"
  md=''
done
