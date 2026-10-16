#!/bin/sh
# Native read-only audit of a built ISO's live tools and dynamic dependencies.
# Uses only an md device it allocates itself; never boots or installs a system.
set -eu
[ "$(uname -s)" = FreeBSD ] || { echo 'Run on FreeBSD' >&2; exit 1; }
[ "$(id -u)" = 0 ] || { echo 'Run as root' >&2; exit 1; }
iso=$(realpath "${1:?usage: live-image-runtime.sh image.iso}")
[ -f "$iso" ] || { echo "Image not found: $iso" >&2; exit 1; }
work=$(mktemp -d /var/tmp/daemonarchy-live-audit.XXXXXX)
device=''
mounted=false
devfs_mounted=false
cleanup() {
  if "$devfs_mounted"; then umount "$work/root/dev"; fi
  if "$mounted"; then umount "$work/root"; fi
  [ -z "$device" ] || mdconfig -d -u "$device"
  rmdir "$work/root" "$work"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
mkdir "$work/root"
device=$(mdconfig -a -t vnode -f "$iso" -o readonly)
mount -t cd9660 -o ro "/dev/$device" "$work/root"
mounted=true
mount -t devfs devfs "$work/root/dev"
devfs_mounted=true
chroot "$work/root" /bin/sh -s <<'AUDIT'
set -eu
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
export PATH
for tool in sh bash gum jq pkg pkg-static fetch ssh sshd tar xz zpool zfs gpart \
  geli efibootmgr mount umount pw sysrc ifconfig wpa_supplicant \
  wpa_cli dhclient ntpd date file ldd; do
  command -v "$tool" >/dev/null || { echo "Missing live tool: $tool" >&2; exit 1; }
done
for path in /usr/freebsd-dist/base.txz /usr/freebsd-dist/kernel.txz \
  /boot/kernel/kernel /boot/kernel/zfs.ko /boot/loader.efi \
  /usr/local/share/daemonarchy-installer/checkouts.json; do
  [ -s "$path" ] || { echo "Missing live payload: $path" >&2; exit 1; }
done
bash --version
gum --version
jq --version
pkg-static -v
# A compiler-only library accidentally removed from a retained executable's
# dependency chain must fail here, even if that command is not on our tool list.
find /bin /sbin /lib /libexec /usr/bin /usr/sbin /usr/lib /usr/libexec \
  /usr/local/bin /usr/local/sbin /usr/local/lib /usr/local/libexec -type f |
while IFS= read -r path; do
  case "$(file -b "$path")" in
    *ELF*dynamically\ linked*)
      if ! result=$(ldd "$path" 2>&1); then
        printf 'Cannot resolve live ELF dependencies: %s\n%s\n' "$path" "$result" >&2
        exit 1
      fi
      case "$result" in *'not found'*) printf '%s\n%s\n' "$path" "$result" >&2; exit 1 ;; esac
      ;;
  esac
done
echo 'PASS: live tools, install payloads and retained ELF dependencies'
AUDIT
