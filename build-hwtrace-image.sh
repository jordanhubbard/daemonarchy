#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
#
# Build the Daemonarchy hardware bring-up / trace image, a separate image
# type from the install/live ISO, for developers and agentic researchers
# bringing up machines that fail during kernel startup.  See HACKING.md
# ("Hardware bring-up trace image") and docs/boottrace.md.
#
# Layout (GPT, written to a USB stick):
#   1  efi       ESP: the boottrace loader as \EFI\BOOT\BOOTX64.EFI
#   2  HWTROOT   UFS, mounted read-only: /boot (boottrace kernel, selected
#                modules, Lua, presets in /boot/d, loader.conf with the
#                unattended cycle as the only behaviour) and a rescue root
#                whose /etc/rc saves dmesg, sysctl, kenv, kldstat, pciconf,
#                devinfo and acpidump output to DATRACE when a boot
#                reaches init
#   3  DATRACE   FAT32: DATRACE.TAG, STATE.TXT, QUEUE/, TRACES/, DUMPS/
#
# Runs on the FreeBSD builder (makefs, mkimg, bsdtar).  The world pieces
# (rescue, a few diagnostic tools and libraries, modules) come from the
# release ISO the kernel matches.  Queue experiments afterwards with
# tools/boottrace/stick.py queue IMAGE EXPERIMENTS (any host with mtools).
#
# usage: build-hwtrace-image.sh -I RELEASE.iso -k KERNEL -l LOADER.efi
#            -L LUADIR -V VERSION [-o OUTDIR] [-m "MODULE ..."] [-s DATA-MIB]
#            [-S] [-Z]
#   -S  also use a serial console (VM testing)
#   -Z  also write the published form, .img.xz with its .sha256
#
# Output: OUTDIR/daemonarchy-hwtrace-VERSION-amd64.img and its .sha256.
set -eu

usage() { sed -n '/^# usage:/,/^set -eu/p' "$0" | sed '$d'; exit 64; }
here=$(cd "$(dirname "$0")" && pwd)
iso= kernel= loader= luadir= version= outdir=. datamib=256 serial= compress=
modules="msdosfs"
while getopts I:k:l:L:V:o:m:s:SZ opt; do
	case $opt in
	I) iso=$OPTARG ;; k) kernel=$OPTARG ;; l) loader=$OPTARG ;;
	L) luadir=$OPTARG ;; V) version=$OPTARG ;; o) outdir=$OPTARG ;;
	m) modules=$OPTARG ;; s) datamib=$OPTARG ;; S) serial=1 ;; Z) compress=1 ;; *) usage ;;
	esac
done
[ -n "$iso" ] && [ -n "$kernel" ] && [ -n "$loader" ] && [ -n "$luadir" ] &&
    [ -n "$version" ] || usage
case $version in
*[!A-Za-z0-9.+-]*|'') echo "invalid version: $version" >&2; exit 64 ;;
esac
[ "$(uname -s)" = FreeBSD ] || { echo "run on the FreeBSD builder" >&2; exit 1; }
name=daemonarchy-hwtrace-$version-amd64.img
out=$outdir/$name
[ -e "$out" ] && { echo "refusing to overwrite $out" >&2; exit 1; }

work=$(mktemp -d "${TMPDIR:-/tmp}/hwtrace.XXXXXX")
trap 'chmod -R u+w "$work" 2>/dev/null; rm -rf "$work"' EXIT
root=$work/root
mkdir -p "$root/boot/kernel" "$root/boot/lua" "$root/boot/d" \
    "$root/rescue" "$root/bin" "$root/sbin" "$root/etc" "$root/dev" \
    "$root/mnt" "$root/tmp" "$root/lib" "$root/libexec" "$root/usr/lib" \
    "$root/usr/sbin"

# World pieces from the release ISO the kernel was built for.
# rescue/* are hard links in the ISO; bsdtar resolves them only through
# the first name, so extract that one and rename it.
first=$(tar -tf "$iso" | grep -m1 '^rescue/.')
tar -xf "$iso" -C "$root" "$first"
[ "$first" = rescue/rescue ] || mv "$root/$first" "$root/rescue/rescue"
set -- libexec/ld-elf.so.1 lib/libc.so.7 lib/libsys.so.7 \
    usr/lib/libdevinfo.so.7 \
    usr/sbin/pciconf usr/sbin/devinfo usr/sbin/acpidump \
    boot/defaults/loader.conf boot/device.hints
for m in $modules; do
	set -- "$@" "boot/kernel/$m.ko"
done
tar -xf "$iso" -C "$root" "$@"
for p in sh init mount mount_msdosfs umount mkdir sed kenv kldload \
    kldstat sysctl dmesg date sync sleep reboot ls cat; do
	ln -s rescue "$root/rescue/$p"
done
ln -s ../rescue/rescue "$root/bin/sh"
ln -s ../rescue/rescue "$root/sbin/init"
install -m 0555 "$here/tools/hwtrace/rc" "$root/etc/rc"
printf 'Daemonarchy hardware trace image %s\n' "$version" >"$root/etc/motd"

install -m 0555 "$kernel" "$root/boot/kernel/kernel"
install -m 0444 "$loader" "$root/boot/loader.efi"
install -m 0444 "$luadir"/*.lua "$root/boot/lua/"
install -m 0444 "$here/tools/boottrace/presets/"* "$root/boot/d/"
cat >"$root/boot/loader.conf" <<EOF
# Daemonarchy hardware trace image $version: every boot files the previous
# NVRAM trace on DATRACE and boots the next queued experiment.
loader_brand="daemonarchy"
loader_logo="none"
autoboot_delay="5"
kernel="kernel"
vfs.root.mountfrom="ufs:/dev/gpt/HWTROOT"
vfs.root.mountfrom.options="ro"
init_path="/sbin/init:/rescue/init"
debug.boottrace="1"
boot_verbose="YES"
kern.panic_reboot_wait_time="15"
debug.trace_on_panic="1"
debug.debugger_on_panic="0"
boottrace_stick="YES"
boottrace_autocycle="YES"
boottrace_autocycle_delay="5"
boottrace_conf="/boot/d/1"
boottrace_label="/boot/d/1 preset"
EOF
[ -n "$serial" ] && printf '%s\n' 'boot_multicons="YES"' \
    'boot_serial="YES"' >>"$root/boot/loader.conf"
printf 'daemonarchy-hwtrace %s\n' "$version" >"$root/boot/version"

makefs -t ffs -B little -o version=2,minfree=0,label=HWTROOT \
    -s "$(( $(du -Ask "$root" | cut -f1) * 13 / 10 / 1024 + 8 ))m" \
    "$work/root.ufs" "$root"

mkdir -p "$work/esp/EFI/BOOT"
cp "$loader" "$work/esp/EFI/BOOT/BOOTX64.EFI"
makefs -t msdos -s 40m -o fat_type=16,volume_label=EFISYS \
    "$work/esp.img" "$work/esp"

# Preallocated files, rewritten in place by the loader (see stick.py):
# 200 trace slots of 16 KiB and a 512-byte STATE.TXT, newline padded.
mkdir -p "$work/data/QUEUE" "$work/data/TRACES" "$work/data/DUMPS"
printf 'Daemonarchy boottrace stick v1\n' >"$work/data/DATRACE.TAG"
pad() { # pad FILE SIZE
	dd if=/dev/zero bs="$(( $2 - $(stat -f %z "$1") ))" count=1 2>/dev/null |
	    tr '\0' '\n' >>"$1"
}
printf 'next=1\ntraces=0\npending=\n' >"$work/data/STATE.TXT"
pad "$work/data/STATE.TXT" 512
printf '(empty trace slot)\n' >"$work/slot"
pad "$work/slot" 16384
i=1
while [ $i -le 200 ]; do
	cp "$work/slot" "$work/data/TRACES/$(printf %04d $i).TXT"
	i=$((i + 1))
done
makefs -t msdos -s "${datamib}m" -o fat_type=32,sectors_per_cluster=4,volume_label=DATRACE \
    "$work/data.img" "$work/data"

mkdir -p "$outdir"
mkimg -s gpt -f raw -p efi/EFISYS:="$work/esp.img" \
    -p freebsd-ufs/HWTROOT:="$work/root.ufs" \
    -p ms-basic-data/DATRACE:="$work/data.img" -o "$out"
(cd "$outdir" && sha256 -r "$name" | awk '{ print $1 "  " $2 }' >"$name.sha256")
cat "$out.sha256"
if [ -n "$compress" ]; then
	xz -T0 -k -9 "$out"
	(cd "$outdir" && sha256 -r "$name.xz" |
	    awk '{ print $1 "  " $2 }' >"$name.xz.sha256")
	cat "$out.xz.sha256"
fi
echo "Queue experiments: tools/boottrace/stick.py queue $out EXPERIMENTS"
