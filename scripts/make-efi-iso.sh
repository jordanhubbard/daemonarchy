#!/bin/sh
# Build a UEFI or amd64 BIOS/UEFI hybrid ISO from a poudriere tar image.
# poudriere's iso/hybridiso types embed x86 BIOS boot code (cdboot, pmbr,
# isoboot), which aarch64 does not have. This follows FreeBSD's
# release/arm64/mkisoimages.sh: an El Torito EFI boot image plus a GPT in the
# ISO system area that points at the same ESP, so the image boots from a
# virtual CD or a USB stick. Append initialized DATRACE storage for writable
# USB use; optical media remain read-only. Run on FreeBSD (makefs, etdump,
# mkimg, Python 3). Matching loaders capture a normal startup checkpoint;
# deeper kernel/installer persistence needs separate qualification.
#
# usage: make-efi-iso.sh world.txz LABEL output.iso new-work-dir [BOOTAA64.EFI|BOOTX64.EFI] [efi|bios]
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
py=$(command -v python3 || command -v python3.12 || command -v python3.11) || {
    echo 'Python 3 is needed to prepare installation trace storage' >&2; exit 1;
}
if [ ! -f "$here/make-install-trace.py" ] || [ ! -f "$here/../tools/boottrace/stick.py" ]; then
    echo 'The co-located installation trace helpers are missing' >&2; exit 1;
fi
usage='usage: make-efi-iso.sh world.txz LABEL output.iso new-work-dir [BOOTAA64.EFI|BOOTX64.EFI] [efi|bios]'
[ $# -ge 4 ] && [ $# -le 6 ] || { echo "$usage" >&2; exit 2; }
archive=$1 label=$2 output=$3 work=$4 boot_file=${5:-BOOTAA64.EFI} boot_mode=${6:-efi}
case "$label" in
    ''|*[!A-Za-z0-9]*) echo 'The ISO label must be alphanumeric' >&2; exit 2 ;;
esac
[ "${#label}" -le 32 ] || { echo 'The ISO label must be at most 32 characters' >&2; exit 2; }
case "$boot_file" in
    BOOTAA64.EFI|BOOTX64.EFI) ;;
    *) echo "Unsupported EFI boot file name: $boot_file" >&2; exit 2 ;;
esac
case "$boot_mode:$boot_file" in
    efi:*) ;;
    bios:BOOTX64.EFI) ;;
    *) echo 'BIOS hybrid mode requires BOOTX64.EFI; mode must be efi or bios' >&2; exit 2 ;;
esac
size_kb=${ESP_SIZE_KB:-2048}
case "$size_kb" in ''|*[!0-9]*) echo 'ESP_SIZE_KB must be a number of KiB' >&2; exit 2 ;; esac
[ -f "$archive" ] || { echo "Image archive not found: $archive" >&2; exit 1; }
[ ! -e "$work" ] && [ ! -e "$output" ] || {
    echo 'The work directory and output must not exist yet' >&2; exit 1;
}
mkdir -m 0700 "$work"
payload=$work/payload.iso
world=$work/world
mkdir "$world" "$work/esp"
archive_hash=$("$py" - "$archive" <<'PY'
import hashlib, sys
with open(sys.argv[1], 'rb') as stream:
    print(hashlib.file_digest(stream, 'sha256').hexdigest())
PY
)
tar -xpf "$archive" -C "$world"
[ -f "$world/boot/kernel/kernel" ] && [ -f "$world/boot/loader.efi" ] || {
    echo 'The image world has no kernel or EFI loader' >&2; exit 1;
}
if [ "$boot_mode" = bios ]; then
    for file in cdboot pmbr isoboot loader; do
        [ -f "$world/boot/$file" ] && [ ! -L "$world/boot/$file" ] || {
            echo "The amd64 image world lacks regular BIOS boot file: $file" >&2; exit 1;
        }
    done
    [ "$(stat -f %z "$world/boot/isoboot")" -le 15360 ] || {
        echo 'BIOS isoboot would overlap the ISO primary volume descriptor' >&2; exit 1;
    }
fi
"$py" - "$world" "$archive_hash" <<'PY'
from pathlib import Path
import sys, uuid
world = Path(sys.argv[1])
identity, config = world / 'boot/trace-id', world / 'boot/loader.conf.local'
loader = (world / 'boot/loader.efi').read_bytes()
if not any(f'Daemonarchy normal boot trace v{version}'.encode() in loader
           for version in (1, 2, 3, 4)):
    raise ValueError('EFI loader lacks normal installation trace capture')
lua = (world / 'boot/lua/boottrace.lua').read_text()
if 'daemonarchy.trace.enable' not in lua or 'boottrace observe' not in lua:
    raise ValueError('loader Lua lacks automatic normal trace startup')
for path in (identity, config):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('trace metadata paths must be regular files')
identity.write_text('Daemonarchy installation trace identity v1\n'
                    f'image_id={uuid.uuid4()}\narchive_sha256={sys.argv[2]}\n'
                    'mode=observe-only\n')
with config.open('a') as stream:
    stream.write('\n# Normal tracing observes boot without consuming experiments.\n'
                 'daemonarchy.trace.enable="YES"\n')
PY

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

set -- makefs -t cd9660 -o rockridge -o label="$upper" -o publisher=Daemonarchy
if [ "$boot_mode" = bios ]; then
    set -- "$@" -o bootimage="i386;$world/boot/cdboot" -o no-emul-boot
fi
"$@" -o bootimage="efi;$work/efiboot.img" -o no-emul-boot -o platformid=efi \
    "$payload" "$world"

# With BIOS first, only the explicit EFI catalogue entry names the ESP.
espparam=''
for entry in $(etdump --format shell "$payload"); do
    et_platform='' et_lba='' et_sectors=''
    eval "$entry"
    case "$et_platform:$boot_mode" in
        efi:*|default:efi)
            espparam="-p efi::$((et_sectors * 512)):$((et_lba * 2048))"
            break
            ;;
    esac
done
[ -n "$espparam" ] || { echo 'The ISO has no EFI boot entry' >&2; exit 1; }
# shellcheck disable=SC2086
set -- mkimg -s gpt --capacity "$(stat -f %z "$payload")"
if [ "$boot_mode" = bios ]; then
    set -- "$@" -b "$world/boot/pmbr" -p "freebsd-boot:=$world/boot/isoboot"
fi
# espparam is one controlled '-p efi::SIZE:OFFSET' pair from etdump.
# shellcheck disable=SC2086
"$@" $espparam -o "$work/gpt.img"
dd if="$work/gpt.img" of="$payload" bs=32k count=1 conv=notrunc 2>/dev/null
"$py" - "$archive" "$archive_hash" <<'PY'
import hashlib, sys
with open(sys.argv[1], 'rb') as stream:
    if hashlib.file_digest(stream, 'sha256').hexdigest() != sys.argv[2]:
        raise ValueError('input archive changed during EFI assembly')
PY
"$py" "$here/make-install-trace.py" "$payload" "$output" "$work/trace" \
    --identity "$world/boot/trace-id"
echo "$boot_mode hybrid ISO: $output ($boot_file)"
