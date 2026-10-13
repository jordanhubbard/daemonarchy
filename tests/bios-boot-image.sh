#!/usr/local/bin/bash
# Create a disposable BIOS boot-chain test image, without installing packages.
# Usage: sudo bash tests/bios-boot-image.sh /new/output/directory /snapshot/root
# The second argument must contain the target snapshot's /boot directory.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || {
  echo 'Run this test on FreeBSD as root.' >&2
  exit 1
}
output=${1:?Specify a new output directory}
snapshot=${2:?Specify the snapshot root}
[[ -f $snapshot/boot/gptzfsboot && -f $snapshot/boot/kernel/kernel ]] || exit 1
mkdir -m 700 "$output" # Refuse to reuse or overwrite an existing test.
output=$(realpath "$output")
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
md='' pool="dmboot$$" pool_created=false
cleanup() {
  if $pool_created; then
    zpool export "$pool" || return
  fi
  [[ -z $md ]] || mdconfig -d -u "${md#md}"
}
trap cleanup EXIT
truncate -s 6g "$output/disk.img"
md=$(mdconfig -a -t vnode -f "$output/disk.img")
[[ $md =~ ^md[0-9]+$ ]] || exit 1
create_whole_disk_layout "$md"
mkdir "$output/root"
zpool create -o altroot="$output/root" -O compress=lz4 -O atime=off -m none "$pool" "/dev/${md}p3"
pool_created=true
zfs create -o mountpoint=none "$pool/ROOT"
zfs create -o mountpoint=/ "$pool/ROOT/default"
zpool set bootfs="$pool/ROOT/default" "$pool"
cp -R "$snapshot/boot" "$output/root/"
printf '%s\n' '-h' >"$output/root/boot.config"
cat >"$output/root/boot/loader.conf" <<'EOF'
console="comconsole"
autoboot_delay="NO"
beastie_disable="YES"
EOF
install_bios_bootcode "$md" "$output/root"
zpool export "$pool"
pool_created=false
mdconfig -d -u "${md#md}"
md=''
gzip -c "$output/disk.img" >"$output/disk.img.gz"
echo "Boot $output/disk.img in QEMU with SeaBIOS and capture its serial console."
echo 'A FreeBSD loader prompt proves the BIOS-to-ZFS-loader chain, not a full installation.'
