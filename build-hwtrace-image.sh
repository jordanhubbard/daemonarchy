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
#                When the stick carries KEYS/authorized_keys the rescue root
#                also brings up a wired network (bounded DHCP) and sshd on
#                port 2222 for that key, records the address on DATRACE and
#                holds the boot for a bounded time (tools/hwtrace/net.sh).
#   3  DATRACE   FAT32: DATRACE.TAG, STATE.TXT, QUEUE/, TRACES/, DUMPS/,
#                KEYS/ (authorized_keys, and the host key if made here),
#                SLOTS.MAP (where STATE.TXT and each TRACES/ slot live, so
#                the loader rewrites their sectors through EFI_BLOCK_IO
#                instead of the firmware FAT driver)
#
# Runs on the FreeBSD builder (makefs, mkimg, bsdtar, Python 3 for the
# block map).  The world pieces
# (rescue, a few diagnostic tools and libraries, modules) come from the
# release ISO the kernel matches.  Queue experiments afterwards with
# tools/boottrace/stick.py queue IMAGE EXPERIMENTS (any host with mtools).
#
# usage: build-hwtrace-image.sh -I RELEASE.iso -k KERNEL -l LOADER.efi
#            -L LUADIR -V VERSION [-o OUTDIR] [-m "MODULE ..."] [-s DATA-MIB]
#            [-S] [-Z] [-x EXTRA.conf] [-K AUTHORIZED_KEYS] [-H]
#   -S  also use a serial console (VM testing)
#   -Z  also write the published form, .img.xz with its .sha256
#   -K  put these public keys on the stick as KEYS/authorized_keys: the
#       network debugger starts only for them.  Without -K the image never
#       starts a network service (the published form carries no keys; add
#       yours with tools/boottrace/stick.py keys).
#   -H  also generate the stick's ssh host key here, so its fingerprint is
#       known before the first boot (written to OUT.img.hostkey as the
#       fingerprint only).  Without -H the first boot generates and keeps
#       one on the stick.  For a private image only.
#   -x  append EXTRA.conf to loader.conf (test knobs such as
#       boottrace_test_drop; never for a published image)
#
# Output: OUTDIR/daemonarchy-hwtrace-VERSION-amd64.img and its .sha256.
set -eu

usage() { sed -n '/^# usage:/,/^set -eu/p' "$0" | sed '$d'; exit 64; }
here=$(cd "$(dirname "$0")" && pwd)
iso= kernel= loader= luadir= version= outdir=. datamib=256 serial= compress=
extra= keys= hostkey=
# msdosfs for DATRACE; the NIC drivers GENERIC lacks (Realtek rge/re, Intel
# igc, USB Ethernet) and the helpers they depend on.  Missing ones are
# skipped with a note.
modules="msdosfs miibus uether if_rge if_re if_igc if_em if_igb if_ix if_bge if_msk if_ure if_axge if_axe if_cdce if_mos if_smsc if_muge if_urndis if_ipheth if_aue"
while getopts I:k:l:L:V:o:m:s:SZx:K:H opt; do
	case $opt in
	I) iso=$OPTARG ;; k) kernel=$OPTARG ;; l) loader=$OPTARG ;;
	L) luadir=$OPTARG ;; V) version=$OPTARG ;; o) outdir=$OPTARG ;;
	m) modules=$OPTARG ;; s) datamib=$OPTARG ;; S) serial=1 ;; Z) compress=1 ;;
	x) extra=$OPTARG ;; K) keys=$OPTARG ;; H) hostkey=1 ;; *) usage ;;
	esac
done
[ -n "$iso" ] && [ -n "$kernel" ] && [ -n "$loader" ] && [ -n "$luadir" ] &&
    [ -n "$version" ] || usage
case $version in
*[!A-Za-z0-9.+-]*|'') echo "invalid version: $version" >&2; exit 64 ;;
esac
[ "$(uname -s)" = FreeBSD ] || { echo "run on the FreeBSD builder" >&2; exit 1; }
py=$(command -v python3 || command -v python3.12 || command -v python3.11) ||
    { echo "Python 3 is needed for the block map" >&2; exit 1; }
name=daemonarchy-hwtrace-$version-amd64.img
out=$outdir/$name
[ -e "$out" ] && { echo "refusing to overwrite $out" >&2; exit 1; }
if [ -n "$keys" ]; then
	[ -s "$keys" ] && grep -q -E '^(ssh-|ecdsa-|sk-)' "$keys" ||
	    { echo "-K $keys has no public keys" >&2; exit 1; }
	if grep -q 'PRIVATE KEY' "$keys"; then
		echo "-K must name public keys only" >&2; exit 1
	fi
fi

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
tar -tf "$iso" >"$work/iso.list"
for m in $modules; do
	if grep -qx "boot/kernel/$m.ko" "$work/iso.list"; then
		set -- "$@" "boot/kernel/$m.ko"
	else
		echo "note: module $m is not in the ISO; skipped" >&2
	fi
done
# Network debugger payload: sshd, ssh-keygen, sftp-server, scp, usbconfig and
# netstat, the login classes sshd looks up, the ISO's module hints, and every
# shared library they need (closure computed with readelf).
netbins="usr/sbin/sshd usr/bin/ssh-keygen usr/bin/scp usr/libexec/sftp-server usr/sbin/usbconfig usr/bin/netstat"
set -- "$@" $netbins etc/login.conf etc/login.conf.db boot/kernel/linker.hints
tar -xf "$iso" -C "$root" "$@"
for f in usr/sbin/pciconf usr/sbin/devinfo usr/sbin/acpidump $netbins; do
	echo "$f"
done >"$work/dynbins"
: >"$work/libs"
while :; do
	: >"$work/want"
	while read -r f; do
		readelf -d "$root/$f" 2>/dev/null |
		    sed -n 's/.*NEEDED.*\[\(.*\)\].*/\1/p'
	done <"$work/dynbins" | sort -u |
	    while read -r lib; do
		grep -m1 -E "^(lib|usr/lib)/$lib\$" "$work/iso.list" || echo "note: no $lib in the ISO" >&2
	done | sort -u >"$work/want"
	comm -13 "$work/libs" "$work/want" >"$work/new"
	[ -s "$work/new" ] || break
	tar -xf "$iso" -C "$root" -T "$work/new"
	cat "$work/new" "$work/libs" | sort -u >"$work/libs.next"
	mv "$work/libs.next" "$work/libs"
	cat "$work/libs" >>"$work/dynbins"
	sort -u "$work/dynbins" -o "$work/dynbins"
done
for p in sh init mount mount_msdosfs umount mkdir sed kenv kldload \
    kldstat sysctl dmesg date sync sleep reboot ls cat; do
	ln -s rescue "$root/rescue/$p"
done
# The network tools and the rest of /rescue, reachable from sshd's default
# PATH (/usr/bin:/bin:/usr/sbin:/sbin) as well as the rc script's.
for p in dhclient dhclient-script ifconfig route mdmfs mdconfig newfs ping \
    ps kill pgrep pkill hostname id ln cp mv rm rmdir chmod tail head tee \
    test expr echo more less stty df mount_msdosfs fsck_msdosfs gpart geom \
    camcontrol nc tar xz sed; do
	[ -e "$root/rescue/$p" ] || ln -s rescue "$root/rescue/$p"
done
for p in "$root"/rescue/*; do
	p=${p##*/}
	[ "$p" = rescue ] && continue
	[ -e "$root/bin/$p" ] || ln -s ../rescue/rescue "$root/bin/$p"
done
ln -sf ../rescue/rescue "$root/bin/sh"
ln -s ../rescue/rescue "$root/sbin/init"
rm -f "$root/sbin/dhclient-script"
ln -s ../rescue/dhclient-script "$root/sbin/dhclient-script"
mkdir -p "$root/var" "$root/root"
install -m 0555 "$here/tools/hwtrace/rc" "$root/etc/rc"
install -m 0444 "$here/tools/hwtrace/net.sh" "$root/etc/hwtrace-net.sh"
install -m 0555 "$here/tools/hwtrace/hwtrace-continue" "$here/tools/hwtrace/hwtrace-hold" "$root/sbin/"
# Minimal accounts for sshd (privilege separation) and a root whose shell
# exists here; the databases are made by pwd_mkdb.
cat >"$work/master.passwd" <<EOP
root:*:0:0::0:0:Hardware trace root:/:/bin/sh
sshd:*:22:22::0:0:Secure Shell Daemon:/var/empty:/usr/sbin/nologin
nobody:*:65534:65534::0:0:Unprivileged user:/nonexistent:/usr/sbin/nologin
EOP
printf 'wheel:*:0:root\nsshd:*:22:\nnobody:*:65534:\n' >"$root/etc/group"
pwd_mkdb -d "$root/etc" -p "$work/master.passwd"
printf 'PATH=/rescue:/usr/sbin:/usr/bin:/sbin:/bin; export PATH\n' >"$root/.profile"
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
[ -n "$extra" ] && cat "$extra" >>"$root/boot/loader.conf"
printf 'daemonarchy-hwtrace %s\n' "$version" >"$root/boot/version"

makefs -t ffs -B little -o version=2,minfree=0,label=HWTROOT \
    -s "$(( $(du -Ask "$root" | cut -f1) * 13 / 10 / 1024 + 8 ))m" \
    "$work/root.ufs" "$root"

mkdir -p "$work/esp/EFI/BOOT"
cp "$loader" "$work/esp/EFI/BOOT/BOOTX64.EFI"
makefs -t msdos -s 40m -o fat_type=16,volume_label=EFISYS \
    "$work/esp.img" "$work/esp"

# Preallocated files, rewritten in place by the loader (see stick.py):
# 200 trace slots of 16 KiB and a 512-byte STATE.TXT, newline padded, and
# a 16 KiB SLOTS.MAP filled in after the image is assembled.  A fresh
# makefs allocates each file contiguously; write-map checks that.
mkdir -p "$work/data/QUEUE" "$work/data/TRACES" "$work/data/DUMPS" "$work/data/KEYS"
printf 'authorized_keys: public keys the network debugger accepts (tools/boottrace/stick.py keys)\n' >"$work/data/KEYS/README.TXT"
[ -n "$keys" ] && cp "$keys" "$work/data/KEYS/authorized_keys"
if [ -n "$hostkey" ]; then
	ssh-keygen -q -t ed25519 -N '' -C hwtrace-host -f "$work/data/KEYS/ssh_host_ed25519_key"
	fingerprint=$(ssh-keygen -l -f "$work/data/KEYS/ssh_host_ed25519_key" | awk '{ print $2 }')
fi
printf 'Daemonarchy boottrace stick v1\n' >"$work/data/DATRACE.TAG"
pad() { # pad FILE SIZE
	dd if=/dev/zero bs="$(( $2 - $(stat -f %z "$1") ))" count=1 2>/dev/null |
	    tr '\0' '\n' >>"$1"
}
# epoch: the queue generation the loader's NVRAM self-report belongs to.
printf 'next=1\ntraces=0\npending=\nepoch=%u\n' \
    "$(( $(od -An -N4 -tu4 /dev/urandom) % 2147483647 + 1 ))" \
    >"$work/data/STATE.TXT"
pad "$work/data/STATE.TXT" 512
printf '(block map not written yet)\n' >"$work/data/SLOTS.MAP"
pad "$work/data/SLOTS.MAP" 16384
printf '(empty trace slot)\n' >"$work/slot"
pad "$work/slot" 16384
i=1
while [ $i -le 200 ]; do
	cp "$work/slot" "$work/data/TRACES/$(printf %04d $i).TXT"
	i=$((i + 1))
done
makefs -t msdos -s "${datamib}m" -o fat_type=32,sectors_per_cluster=4,volume_label=DATRACE \
    "$work/data.img" "$work/data"
# makefs reports "too few clusters for FAT32" yet exits 0 (seen with -s 64).
[ -s "$work/data.img" ] || { echo "makefs did not create DATRACE; use -s 256 or more" >&2; exit 1; }

mkdir -p "$outdir"
mkimg -s gpt -f raw -p efi/EFISYS:="$work/esp.img" \
    -p freebsd-ufs/HWTROOT:="$work/root.ufs" \
    -p ms-basic-data/DATRACE:="$work/data.img" -o "$out"
# Record where STATE.TXT and the trace slots are; fails unless contiguous.
"$py" "$here/tools/boottrace/stick.py" write-map "$out"
[ -n "$hostkey" ] && { printf '%s\n' "$fingerprint" >"$out.hostkey"; echo "host key $fingerprint"; }
(cd "$outdir" && sha256 -r "$name" | awk '{ print $1 "  " $2 }' >"$name.sha256")
cat "$out.sha256"
if [ -n "$compress" ]; then
	xz -T0 -k -9 "$out"
	(cd "$outdir" && sha256 -r "$name.xz" |
	    awk '{ print $1 "  " $2 }' >"$name.xz.sha256")
	cat "$out.xz.sha256"
fi
echo "Queue experiments: tools/boottrace/stick.py queue $out EXPERIMENTS"
