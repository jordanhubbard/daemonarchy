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
ram_device=''
outer_mounted=false
root_mounted=false
devfs_mounted=false
tmp_mounted=false
cleanup() {
  status=$?
  trap - EXIT
  set +e
  failed=0
  if "$tmp_mounted"; then umount "$root/tmp" || failed=1; fi
  if "$devfs_mounted"; then umount "$root/dev" || failed=1; fi
  if "$root_mounted"; then umount "$work/root" || failed=1; fi
  if [ -n "$ram_device" ]; then mdconfig -d -u "$ram_device" || failed=1; fi
  if "$outer_mounted"; then umount "$work/outer" || failed=1; fi
  if [ -n "$device" ]; then mdconfig -d -u "$device" || failed=1; fi
  rmdir "$work/root" "$work/outer" "$work" || failed=1
  if [ "$status" -eq 0 ] && [ "$failed" -ne 0 ]; then status=1; fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
mkdir "$work/root" "$work/outer"
device=$(mdconfig -a -t vnode -f "$iso" -o readonly)
mount -t cd9660 -o ro "/dev/$device" "$work/outer"
outer_mounted=true
root=$work/outer
layout=legacy
if [ -e "$work/outer/boot/mfsroot.uzip" ]; then
  [ -f "$work/outer/boot/mfsroot.uzip" ] && [ ! -L "$work/outer/boot/mfsroot.uzip" ] || {
    echo 'RAM root must be a regular packed filesystem' >&2; exit 1;
  }
  kldload -n geom_uzip
  ram_device=$(mdconfig -a -t vnode -f "$work/outer/boot/mfsroot.uzip" -o readonly)
  mount -t ufs -o ro "/dev/$ram_device.uzip" "$work/root"
  root_mounted=true
  root=$work/root
  layout=ram
fi
abi=$(cat "$root/usr/local/share/daemonarchy-installer/ABI")
case "$abi:$(uname -p)" in
  FreeBSD:16:amd64:amd64|FreeBSD:16:aarch64:aarch64) ;;
  *) echo 'Audit requires a native worker matching the live-root ABI' >&2; exit 1 ;;
esac
mount -t devfs devfs "$root/dev"
devfs_mounted=true
# Both legacy ISO roots and packed UFS roots stay read-only. Only tmux's
# scratch directory and devfs are mounted over them for these runtime checks.
mount -t tmpfs -o size=16m tmpfs "$root/tmp"
tmp_mounted=true
chroot "$root" /bin/sh -s -- "$mode" "$layout" <<'AUDIT'
set -eu
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
export PATH
if [ "$2" = ram ]; then
  for path in /etc/rc.d/daemonarchy_trace \
      /usr/local/libexec/daemonarchy-installer/boot-trace \
      /usr/local/libexec/daemonarchy-boottrace/stick.py \
      /usr/local/libexec/daemonarchy-boottrace/boot-medium.py \
      /usr/local/libexec/daemonarchy-boottrace/fat-volume.py \
      /usr/local/libexec/daemonarchy-boottrace/observe-medium.py \
      /usr/local/libexec/daemonarchy-boottrace/capture-medium.py \
      /usr/local/libexec/daemonarchy-boottrace/session-log.py; do
    [ -f "$path" ] && [ ! -L "$path" ] && [ "$(stat -f '%u:%Lp' "$path")" = 0:555 ] || {
      echo "Missing or unsafe default trace helper: $path" >&2; exit 1;
    }
  done
  for path in /etc/rc.d/daemonarchy_trace /usr/local/libexec/daemonarchy-installer/boot-trace; do
    sh -n "$path"
  done
  /usr/local/bin/python3.12 -c 'import runpy; runpy.run_path("/usr/local/libexec/daemonarchy-boottrace/capture-medium.py", run_name="audit"); print("PASS: default trace helper runtime imports")'
fi
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
for tool in sh bash gum tmux infocmp jq pkg pkg-static fetch timeout lockf fsync ssh sshd tar xz zpool zfs gpart \
  geli efibootmgr mount umount pw sysrc ifconfig wpa_supplicant \
  wpa_cli dhclient ntpd date file ldd; do
  command -v "$tool" >/dev/null || { echo "Missing live tool: $tool" >&2; exit 1; }
done
if [ "$(cat /usr/local/share/daemonarchy-installer/ABI)" = FreeBSD:16:amd64 ]; then
  [ -s /usr/freebsd-dist/lib32.txz ] || { echo 'Missing amd64 lib32 install set' >&2; exit 1; }
fi
for path in /usr/freebsd-dist/base.txz /usr/freebsd-dist/kernel.txz \
  /boot/kernel/kernel /boot/kernel/zfs.ko /boot/loader.efi \
  /usr/local/libexec/daemonarchy-installer/install-integrity \
  /usr/local/libexec/daemonarchy-installer/debug-observe \
  /usr/local/libexec/daemonarchy-installer/debug-events.py \
  /usr/local/libexec/daemonarchy-installer/progress-model.py \
  /usr/local/libexec/daemonarchy-installer/install-screen \
  /usr/local/libexec/daemonarchy-installer/install-failed \
  /usr/local/libexec/daemonarchy-installer/install-views \
  /usr/local/libexec/daemonarchy-installer/sound.py \
  /usr/local/libexec/daemonarchy-installer/sound \
  /usr/local/libexec/daemonarchy-installer/charm.py \
  /usr/local/libexec/daemonarchy-installer/charm \
  /usr/local/libexec/daemonarchy-installer/sound-setup \
  /usr/local/share/daemonarchy-installer/greeting/daemonarchy_greeting \
  /usr/local/share/daemonarchy-installer/clock/daemonarchy_clock \
  /usr/local/share/daemonarchy-installer/netselect/daemonarchy-netselect \
  /usr/local/share/daemonarchy-installer/netselect/dhclient-enter-hooks \
  /usr/local/share/daemonarchy-installer/netselect/dhclient-exit-hooks \
  /usr/local/share/daemonarchy-installer/netselect/daemonarchy-netselect.conf \
  /usr/local/share/daemonarchy-installer/netselect/daemonarchy-t2link \
  /usr/local/share/daemonarchy-installer/netselect/daemonarchy-t2link.conf \
  /usr/local/share/daemonarchy-installer/netselect/daemonarchy-t2link.rc.conf \
  /usr/local/libexec/daemonarchy-installer/pkg-events \
  /usr/local/share/daemonarchy-installer/install-tmux.conf \
  /usr/local/share/daemonarchy-installer/omarchy-wifi-enterprise \
  /usr/local/share/daemonarchy-installer/package-repository-tag \
  /usr/local/share/daemonarchy-installer/checkouts.json; do
  [ -s "$path" ] || { echo "Missing live payload: $path" >&2; exit 1; }
done
# Console messages stay off the installer's tmux screen (issue #244).
if grep -Eq '^[^#].*/dev/console' /etc/syslog.conf; then
  echo 'syslog still writes to /dev/console on the live image' >&2; exit 1
fi
grep -q '^tinker panic 0' /etc/ntp.conf || { echo 'ntpd would exit after a large clock jump' >&2; exit 1; }
. /usr/local/libexec/daemonarchy-installer/package-repository
package_repository_prepare /usr/local/share/daemonarchy-installer
echo "PASS: signed application feed selection: $package_repository_tag"
bash --version
gum --version
tmux -V
infocmp tmux-256color >/dev/null
# The installer's tmux configuration parses and binds the documented keys.
DAEMONARCHY_PYTHON=/usr/local/bin/python3.12 DAEMONARCHY_LIBEXEC=/usr/local/libexec/daemonarchy-installer \
  tmux -L live-image-check -f /usr/local/share/daemonarchy-installer/install-tmux.conf \
  new-session -d true \; list-keys -N -T prefix >/tmp/install-tmux-keys
tmux -L live-image-check kill-server 2>/dev/null || true
grep -q 'Detach is not available' /tmp/install-tmux-keys
/usr/local/bin/python3.12 -c 'import ctypes, ctypes.util; print("ctypes", ctypes.util.find_library("c"))'
jq --version
pkg-static -v
python_command=$(head -n 1 /usr/local/share/daemonarchy-installer/omarchy-wifi-enterprise)
python_command=${python_command#\#!}
case "$python_command" in /usr/local/bin/python3.[0-9]*) ;; *) echo 'Invalid enterprise helper interpreter' >&2; exit 1 ;; esac
"$python_command" -c 'import runpy; runpy.run_path("/usr/local/share/daemonarchy-installer/omarchy-wifi-enterprise", run_name="audit"); print("Enterprise Wi-Fi runtime imports passed")'
# Live desktop (LIVE-001): the minimal desktop set, its startup wiring and the
# graphical installer's runtime. A Wayland session is not needed to import GTK.
for tool in Hyprland foot seatd sudo dbus-run-session kldxref su; do
  command -v "$tool" >/dev/null || { echo "Missing live desktop tool: $tool" >&2; exit 1; }
done
for path in /etc/rc.d/daemonarchy_live /home/live/.config/hypr/hyprland.lua \
  /usr/local/libexec/daemonarchy-installer/live-installer \
  /usr/local/libexec/daemonarchy-installer/live-backend \
  /usr/local/libexec/daemonarchy-installer/live-gpu \
  /usr/local/libexec/daemonarchy-installer/live-session; do
  [ -s "$path" ] || { echo "Missing live desktop payload: $path" >&2; exit 1; }
done
[ -d /live ] && [ -d /home ] || { echo 'Missing live mount points' >&2; exit 1; }
id -Gn live | tr ' ' '\n' | grep -qx video || { echo 'The live account is not in the video group' >&2; exit 1; }
[ "$(stat -f '%u:%Lp' /usr/local/etc/sudoers.d/daemonarchy-live)" = 0:440 ]
grep -qx 'live ALL=(ALL) NOPASSWD: ALL' \
  /usr/local/etc/sudoers.d/daemonarchy-live
grep -qx 'daemonarchy_live_media="YES"' /boot/loader.conf
grep -q 'daemonarchy_live' /boot/lua/brand-daemonarchy.lua
# Comments explain why unionfs is avoided; only commands count.
if grep -n 'mount_unionfs\|-t unionfs\|kldload unionfs' /etc/rc.d/daemonarchy_live \
    /usr/local/libexec/daemonarchy-installer/live-gpu /usr/local/libexec/daemonarchy-installer/live-session |
    grep -v '^[^:]*:[0-9]*:[[:space:]]*#'; then
  echo 'The live desktop must not use unionfs' >&2; exit 1
fi
installer_python=$(head -n 1 /usr/local/libexec/daemonarchy-installer/live-installer)
installer_python=${installer_python#\#!}
"$installer_python" -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk; print("GTK", Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION)'
echo 'PASS: live desktop tools, startup wiring and installer runtime'
# A compiler-only library accidentally removed from a retained executable's
# dependency chain must fail here, even if that command is not on our tool list.
# Batch only file(1) classification. Every regular pathname is still inspected,
# and every dynamic ELF gets its own ldd invocation (including hardlink aliases
# whose dependency resolution may depend on their path). NUL framing preserves
# whitespace/newlines in names and descriptions without a file process per path.
/usr/local/bin/python3.12 - <<'ELF_AUDIT'
import glob
import subprocess
import sys

roots = [b'/bin', b'/sbin', b'/lib', b'/libexec', b'/usr/bin', b'/usr/sbin',
         b'/usr/lib', b'/usr/libexec', b'/usr/local/bin', b'/usr/local/sbin',
         b'/usr/local/lib', b'/usr/local/libexec']
roots += glob.glob(b'/usr/local/llvm[0-9]*') or [b'/usr/local/llvm[0-9]*']
raw = subprocess.run([b'find', *roots, b'-type', b'f', b'-print0'],
                     check=True, stdout=subprocess.PIPE).stdout
if not raw or not raw.endswith(b'\0'):
    raise SystemExit('Missing or malformed retained-file enumeration')
paths = raw[:-1].split(b'\0')
checked = dynamic = 0
print(f'ELF audit: discovered {len(paths)} regular paths', flush=True)
for offset in range(0, len(paths), 128):
    batch = paths[offset:offset + 128]
    result = subprocess.run([b'file', b'-E', b'-r', b'-0', b'-0', b'--', *batch],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fields = result.stdout.split(b'\0')
    if result.returncode or fields[-1] != b'' or len(fields) != 2 * len(batch) + 1:
        sys.stderr.buffer.write(result.stderr)
        raise SystemExit('Cannot classify retained files')
    for index, path in enumerate(batch):
        name, description = fields[2 * index:2 * index + 2]
        if name != path:
            raise SystemExit('Retained-file classification pathname mismatch')
        checked += 1
        if b'ELF' not in description or b'dynamically linked' not in description:
            continue
        result = subprocess.run([b'ldd', path], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        if result.returncode or b'not found' in result.stdout:
            sys.stderr.buffer.write(b'Cannot resolve live ELF dependencies: ' +
                                    path + b'\n' + result.stdout + b'\n')
            raise SystemExit(1)
        dynamic += 1
    if checked % 4096 == 0 or checked == len(paths):
        print(f'ELF audit: classified {checked}/{len(paths)} paths; '
              f'resolved {dynamic} dynamic ELF paths', flush=True)
print(f'PASS: all {checked} retained paths classified; '
      f'all {dynamic} dynamic ELF paths resolved', flush=True)
ELF_AUDIT
echo 'PASS: live tools, install payloads and retained ELF dependencies'
AUDIT
