#!/usr/local/bin/bash
# Disposable native boot-chain fixture; run the resulting image under UEFI QEMU.
# Usage: sudo bash tests/efi-boot-image.sh /new/output /snapshot/root [broken]
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
output=${1:?Specify a new output directory}
snapshot=${2:?Specify the snapshot root}
mode=${3:-fixed}
[[ $mode == fixed || $mode == broken ]] || exit 1
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
mkdir -m 700 "$output"
output=$(realpath "$output")
md='' pool="daemonarchy-efi-$$" created=false mounted=false
cleanup() {
  if $mounted; then umount "$output/root/boot/efi"; fi
  if $created; then zpool export "$pool"; fi
  [[ -z $md ]] || mdconfig -d -u "${md#md}"
}
trap cleanup EXIT
truncate -s 2g "$output/disk.img"
md=$(mdconfig -a -t vnode -f "$output/disk.img")
[[ $md =~ ^md[0-9]+$ ]] || exit 1
gpart create -s gpt "$md"
gpart add -t efi -a 1m -s 64m "$md"
gpart add -t freebsd-zfs -a 1m "$md"
mkdir "$output/root"
zpool create -o cachefile=none -o altroot="$output/root" -m none "$pool" "/dev/${md}p2"
created=true
zfs create -o mountpoint=none "$pool/ROOT"
zfs create -o mountpoint=/ "$pool/ROOT/default"
zpool set bootfs="$pool/ROOT/default" "$pool"
cp -R "$snapshot/boot" "$output/root/"
mkdir -p "$output/root/boot/efi"
newfs_msdos -F 32 -c 1 "/dev/${md}p1" >/dev/null
mount -t msdosfs "/dev/${md}p1" "$output/root/boot/efi"
mounted=true
write_efi_loader "$output/root" "$pool" false
{
  echo 'console=comconsole'
  if [[ $mode == broken ]]; then
    printf 'rootdev=zfs:%s:\n' "$pool"
  else
    efi_root_environment "$pool"
  fi
} >"$output/root/boot/efi/EFI/FreeBSD/loader.env"
cat >"$output/root/boot/loader.conf" <<'EOF'
console="comconsole"
autoboot_delay="NO"
beastie_disable="YES"
EOF
umount "$output/root/boot/efi"
mounted=false
zpool export "$pool"
created=false
mdconfig -d -u "${md#md}"
md=''
gzip -c "$output/disk.img" >"$output/disk.img.gz"
echo "Boot $output/disk.img under UEFI QEMU with a serial console."
echo 'Fixed: Lua initializes and loads the kernel. Broken: loader.lua ENOENT.'
