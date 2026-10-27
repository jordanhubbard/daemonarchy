#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
#
# Remaster a Daemonarchy live ISO into a boottrace diagnostic USB image:
#   - /boot/kernel.bt/kernel: the boottrace kernel (default kernel)
#   - the boottrace loader on the EFI system partition and as /boot/loader.efi
#   - the matching Lua scripts (boottrace.lua, loader.lua, menu.lua)
#   - /boot/d/1 legacy-ISA-off preset (if absent) and loader.conf settings for
#     the unattended loop (boottrace_loop) with plain wired netdebug
#   - DAEMDBG/PROBE.TAG on the ESP so the loader may save trace files there
#   - a GPT FAT32 partition DATRACE (stick.py) holding QUEUE/, TRACES/ and
#     STATE.TXT, and boottrace_autocycle="YES" so every boot files the last
#     trace and runs the next queued experiment (-M disables autocycle)
#
# Needs xorriso, mtools (mcopy/mmd) and python3.  El Torito is not kept: the
# result is meant to be written to a USB stick and booted by UEFI.
#
# usage: make-stick.sh -i BASE.iso -o OUT.img -k KERNEL -l LOADER.efi \
#            -L LUADIR [-a LOADER-IP -p CONTROLLER-IP] [-n UNIT] [-w SECONDS]
#            [-c PRESET] [-x EXTRA-LOADER-CONF] [-s DATA-MIB] [-q EXPERIMENTS] [-M]
set -eu

usage() { sed -n '/^# usage:/,/^set -eu/p' "$0" | sed '$d'; exit 64; }
here=$(cd "$(dirname "$0")" && pwd)
base= out= kernel= loader= luadir= ip= peer= unit=0 wait=25 preset=/boot/d/1 extra=
datamib=256 queue= autocycle=YES
while getopts i:o:k:l:L:a:p:n:w:c:x:s:q:M opt; do
	case $opt in
	i) base=$OPTARG ;; o) out=$OPTARG ;; k) kernel=$OPTARG ;;
	l) loader=$OPTARG ;; L) luadir=$OPTARG ;; a) ip=$OPTARG ;;
	p) peer=$OPTARG ;; n) unit=$OPTARG ;; w) wait=$OPTARG ;;
	c) preset=$OPTARG ;; x) extra=$OPTARG ;; s) datamib=$OPTARG ;;
	q) queue=$OPTARG ;; M) autocycle=NO ;; *) usage ;;
	esac
done
[ -n "$base" ] && [ -n "$out" ] && [ -n "$kernel" ] && [ -n "$loader" ] &&
    [ -n "$luadir" ] || usage
[ -e "$out" ] && { echo "refusing to overwrite $out" >&2; exit 1; }
if { [ -n "$ip" ] && [ -z "$peer" ]; } || { [ -z "$ip" ] && [ -n "$peer" ]; }; then
	echo "-a and -p go together" >&2; exit 64
fi

work=$(mktemp -d "${TMPDIR:-/tmp}/bt-stick.XXXXXX")
trap 'rm -rf "$work"' EXIT

xorriso -osirrox on -indev "$base" -extract /boot/loader.conf "$work/loader.conf" \
    >/dev/null 2>&1
has_preset=$(xorriso -indev "$base" -ls "$preset" 2>/dev/null | grep -c . || true)
chmod u+w "$work/loader.conf"
cat >>"$work/loader.conf" <<EOF

# --- Daemonarchy boottrace diagnostic stick ---
kernel="kernel.bt"
module_path="/boot/kernel.bt;/boot/kernel;/boot/modules;/boot/dtb;/boot/dtb/overlays"
debug.boottrace="1"
boot_verbose="YES"
boottrace_conf="$preset"
boottrace_label="$preset preset"
boottrace_stick="YES"
# Hardware trace stick workflow: file the last trace, run the next experiment.
boottrace_autocycle="$autocycle"
boottrace_autocycle_delay="5"
EOF
if [ -n "$ip" ]; then
	cat >>"$work/loader.conf" <<EOF
# Unattended loop: plain wired console, then the controller or the preset.
boottrace_loop="YES"
boottrace_controller_wait="$wait"
netdebug.plain="1"
netdebug.interface="$unit"
netdebug.ip="$ip"
netdebug.peer="$peer"
EOF
fi
[ -n "$extra" ] && cat "$extra" >>"$work/loader.conf"

set --
if [ "$has_preset" = 0 ] && [ "$preset" = /boot/d/1 ]; then
	set -- -map "$here/presets/1" /boot/d/1
fi
for f in boottrace.lua loader.lua menu.lua; do
	set -- "$@" -map "$luadir/$f" "/boot/lua/$f"
done
xorriso -indev "$base" -outdev "$out" -boot_image any replay \
    -map "$kernel" /boot/kernel.bt/kernel \
    -map "$loader" /boot/loader.efi \
    -map "$work/loader.conf" /boot/loader.conf \
    "$@" -commit >/dev/null 2>"$work/xorriso.log" ||
    { cat "$work/xorriso.log" >&2; exit 1; }

# Locate the EFI system partition in the GPT and update it in place.
esp=$(python3 -I - "$out" <<'EOF'
import struct, sys, uuid
ESP = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b").bytes_le
with open(sys.argv[1], "rb") as f:
    f.seek(512)
    hdr = f.read(92)
    assert hdr[:8] == b"EFI PART", "no GPT"
    lba, count, size = struct.unpack_from("<QII", hdr, 72)
    f.seek(lba * 512)
    table = f.read(count * size)
for i in range(count):
    e = table[i * size:(i + 1) * size]
    if e[:16] == ESP:
        first, last = struct.unpack_from("<QQ", e, 32)
        print(first, last - first + 1)
        break
else:
    sys.exit("no EFI system partition")
EOF
)
set -- $esp
dd if="$out" of="$work/esp.img" bs=512 skip="$1" count="$2" status=none
mcopy -o -i "$work/esp.img" "$loader" ::/EFI/BOOT/BOOTX64.EFI
mmd -i "$work/esp.img" ::/DAEMDBG 2>/dev/null || true
printf 'Daemonarchy firmware inventory USB v1\n' >"$work/PROBE.TAG"
mcopy -o -i "$work/esp.img" "$work/PROBE.TAG" ::/DAEMDBG/PROBE.TAG
dd if="$work/esp.img" of="$out" bs=512 seek="$1" conv=notrunc status=none
python3 -I "$here/stick.py" add-partition "$out" --size-mib "$datamib"
python3 -I "$here/stick.py" init "$out"
[ -n "$queue" ] && python3 -I "$here/stick.py" queue "$out" "$queue"
echo "wrote $out"
