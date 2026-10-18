#!/bin/sh
# Native read-only audit of a built ISO's live tools and dynamic dependencies.
# Uses only an md device it allocates itself; never boots or installs a system.
set -eu
[ "$(uname -s)" = FreeBSD ] || { echo 'Run on FreeBSD' >&2; exit 1; }
[ "$(id -u)" = 0 ] || { echo 'Run as root' >&2; exit 1; }
iso=$(realpath "${1:?usage: live-image-runtime.sh image.iso [public|headless]}")
mode=${2:-public}
case "$mode" in public|headless) ;; *) echo 'Choose public or headless image role' >&2; exit 1 ;; esac
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
chroot "$work/root" /bin/sh -s -- "$mode" <<'AUDIT'
set -eu
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
export PATH
payload=/usr/local/share/daemonarchy-installer/headless
if [ "$1" = public ]; then
  [ ! -e "$payload" ] && [ ! -e /usr/local/etc/rc.d/daemonarchy-headless ] || {
    echo 'Private rescue authorization found in public image' >&2; exit 1;
  }
  echo 'PASS: public image contains no private rescue authorization or startup service'
else
  [ -x /usr/local/etc/rc.d/daemonarchy-headless ]
  for key in authorized_keys host_key; do
    [ "$(stat -f '%u:%Lp' "$payload/$key")" = 0:600 ] || {
      echo 'Invalid private rescue key ownership or permissions' >&2; exit 1;
    }
  done
  grep -q '^devmatch_blocklist=.*apple_bce.*amdgpu' /boot/loader.conf.local
  echo 'PASS: explicit private rescue image has protected authorization and blocked drivers'
fi
for tool in sh bash gum jq pkg pkg-static fetch timeout lockf ssh sshd tar xz zpool zfs gpart \
  geli efibootmgr mount umount pw sysrc ifconfig wpa_supplicant \
  wpa_cli dhclient ntpd date file ldd; do
  command -v "$tool" >/dev/null || { echo "Missing live tool: $tool" >&2; exit 1; }
done
for path in /usr/freebsd-dist/base.txz /usr/freebsd-dist/kernel.txz /usr/freebsd-dist/lib32.txz \
  /boot/kernel/kernel /boot/kernel/zfs.ko /boot/loader.efi \
  /usr/local/libexec/daemonarchy-installer/install-integrity \
  /usr/local/libexec/daemonarchy-installer/debug-observe \
  /usr/local/libexec/daemonarchy-installer/debug-events.py \
  /usr/local/share/daemonarchy-installer/omarchy-wifi-enterprise \
  /usr/local/share/daemonarchy-installer/package-repository-tag \
  /usr/local/share/daemonarchy-installer/checkouts.json; do
  [ -s "$path" ] || { echo "Missing live payload: $path" >&2; exit 1; }
done
. /usr/local/libexec/daemonarchy-installer/package-repository
package_repository_prepare /usr/local/share/daemonarchy-installer
echo "PASS: signed application feed selection: $package_repository_tag"
bash --version
gum --version
jq --version
pkg-static -v
python_command=$(head -n 1 /usr/local/share/daemonarchy-installer/omarchy-wifi-enterprise)
python_command=${python_command#\#!}
case "$python_command" in /usr/local/bin/python3.[0-9]*) ;; *) echo 'Invalid enterprise helper interpreter' >&2; exit 1 ;; esac
"$python_command" -c 'import runpy; runpy.run_path("/usr/local/share/daemonarchy-installer/omarchy-wifi-enterprise", run_name="audit"); print("Enterprise Wi-Fi runtime imports passed")'
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
