#!/bin/sh
# Build a UEFI-only hybrid ISO (optical and USB) from a poudriere tar image.
# poudriere's iso/hybridiso types embed x86 BIOS boot code (cdboot, pmbr,
# isoboot), which aarch64 does not have. This follows FreeBSD's
# release/arm64/mkisoimages.sh: an El Torito EFI boot image plus a GPT in the
# ISO system area that points at the same ESP, so the image boots from a
# virtual CD or a USB stick. Run on FreeBSD as root (makefs, etdump, mkimg).
#
# usage: make-efi-iso.sh world.txz LABEL output.iso new-work-dir [BOOTAA64.EFI|BOOTX64.EFI]
set -eu
usage='usage: make-efi-iso.sh world.txz LABEL output.iso new-work-dir [BOOTAA64.EFI|BOOTX64.EFI]'
[ $# -ge 4 ] && [ $# -le 5 ] || { echo "$usage" >&2; exit 2; }
archive=$1 label=$2 output=$3 work=$4 boot_file=${5:-BOOTAA64.EFI}
case "$label" in
    ''|*[!A-Za-z0-9]*) echo 'The ISO label must be alphanumeric' >&2; exit 2 ;;
esac
[ "${#label}" -le 32 ] || { echo 'The ISO label must be at most 32 characters' >&2; exit 2; }
case "$boot_file" in
    BOOTAA64.EFI|BOOTX64.EFI) ;;
    *) echo "Unsupported EFI boot file name: $boot_file" >&2; exit 2 ;;
esac
size_kb=${ESP_SIZE_KB:-2048}
case "$size_kb" in ''|*[!0-9]*) echo 'ESP_SIZE_KB must be a number of KiB' >&2; exit 2 ;; esac
[ -f "$archive" ] || { echo "Image archive not found: $archive" >&2; exit 1; }
[ ! -e "$work" ] && [ ! -e "$output" ] || {
    echo 'The work directory and output must not exist yet' >&2; exit 1;
}
mkdir -m 0700 "$work"
world=$work/world
mkdir "$world" "$work/esp"
tar -xpf "$archive" -C "$world"
[ -f "$world/boot/kernel/kernel" ] && [ -f "$world/boot/loader.efi" ] || {
    echo 'The image world has no kernel or EFI loader' >&2; exit 1;
}

upper=$(printf '%s' "$label" | tr '[:lower:]' '[:upper:]')
# The same live-root mounts poudriere's ISO types add.
cat >>"$world/etc/fstab" <<FSTAB
/dev/iso9660/$upper / cd9660 ro 0 0
tmpfs /tmp tmpfs rw,mode=1777 0 0
FSTAB

# FAT size thresholds from FreeBSD tools/boot/install-boot.sh.
if [ "$size_kb" -ge 33292 ]; then fat=32
elif [ "$size_kb" -ge 2100 ]; then fat=16
else fat=12
fi
mkdir -p "$work/esp/EFI/BOOT"
cp "$world/boot/loader.efi" "$work/esp/EFI/BOOT/$boot_file"
makefs -t msdos -o fat_type="$fat" -o sectors_per_cluster=1 -o volume_label=EFISYS \
    -s "${size_kb}k" "$work/efiboot.img" "$work/esp"

makefs -t cd9660 -o rockridge -o label="$upper" -o publisher=Daemonarchy \
    -o bootimage="efi;$work/efiboot.img" -o no-emul-boot -o platformid=efi \
    "$output" "$world"

# Locate the ESP inside the ISO; its only boot entry is the initial/default one.
espparam=''
for entry in $(etdump --format shell "$output"); do
    et_platform='' et_lba='' et_sectors=''
    eval "$entry"
    case "$et_platform" in
        efi|default)
            espparam="-p efi::$((et_sectors * 512)):$((et_lba * 2048))"
            break
            ;;
    esac
done
[ -n "$espparam" ] || { echo 'The ISO has no EFI boot entry' >&2; exit 1; }
# shellcheck disable=SC2086
mkimg -s gpt --capacity "$(stat -f %z "$output")" $espparam -o "$work/gpt.img"
dd if="$work/gpt.img" of="$output" bs=32k count=1 conv=notrunc 2>/dev/null
echo "UEFI-only ISO: $output ($boot_file)"
