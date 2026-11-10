#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Preserve a complete live-root archive in a compressed UFS2 RAM filesystem.
# Native FreeBSD filesystem authoring only; no target executable is run here.
set -eu
usage='usage: make-ram-iso.sh world.txz LABEL output.iso new-work-dir [BOOTAA64.EFI|BOOTX64.EFI] [efi|bios]'
[ "$#" -ge 4 ] && [ "$#" -le 6 ] || { echo "$usage" >&2; exit 2; }
archive=$1 label=$2 output=$3 work=$4 boot_file=${5:-BOOTAA64.EFI} boot_mode=${6:-efi}
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
case "$boot_mode:$boot_file" in
    efi:BOOTAA64.EFI|efi:BOOTX64.EFI|bios:BOOTX64.EFI) ;;
    *) echo 'Select a supported EFI file and boot mode' >&2; exit 2 ;;
esac
case "$label" in ''|*[!A-Za-z0-9]*) echo 'The ISO label must be alphanumeric' >&2; exit 2 ;; esac
[ "${#label}" -le 32 ] || { echo 'The ISO label is too long' >&2; exit 2; }
. "$here/iso-stage.sh"
iso_stage_require_fresh_outputs "$work" "$output" "$output.ram.json"
[ -f "$archive" ] && [ ! -L "$archive" ] || {
    echo 'A regular nonsymlink live-root archive is required' >&2; exit 1;
}
[ "$(uname -s)" = FreeBSD ] && [ "$(id -u)" -eq 0 ] || {
    echo 'Native FreeBSD root is required to retain live-root ownership and permissions' >&2; exit 1;
}
py=$(command -v python3.12 || command -v python3) || exit 1
archive_hash=$(sha256 -q "$archive")
mkdir -m 0700 "$work"
world=$work/world
mkdir "$world"
tar -xpf "$archive" -C "$world"
"$py" "$here/live-root-metadata.py" "$archive" "$world" > "$work/root-directory.json"
# Validate the selected ABI, actual kernel/shell ELF machines and complete
# installer payload before modifying the private extracted copy.
"$py" - "$world" "$boot_file" "$archive" <<'CHECK'
from pathlib import Path
import struct, sys
root = Path(sys.argv[1])
abi, machine = {'BOOTAA64.EFI': ('FreeBSD:16:aarch64', 183),
                'BOOTX64.EFI': ('FreeBSD:16:amd64', 62)}[sys.argv[2]]
for name in ('etc', 'var', 'boot', 'usr', 'usr/local', 'usr/local/share',
             'usr/local/share/daemonarchy-installer'):
    p = root / name
    if not p.is_dir() or p.is_symlink():
        raise ValueError('Regular live-root directory required: ' + name)
for name in ('etc/fstab', 'etc/rc.conf', 'boot/loader.efi', 'boot/kernel/kernel',
             'boot/kernel/geom_uzip.ko', 'boot/lua/local.lua',
             'boot/lua/brand-daemonarchy.lua', 'bin/sh', 'usr/freebsd-dist/base.txz',
             'usr/freebsd-dist/kernel.txz', 'usr/freebsd-dist/MANIFEST',
             'usr/local/libexec/daemonarchy-installer/install', 'var/db/pkg/local.sqlite',
             'usr/local/share/daemonarchy-installer/ABI'):
    p = root / name
    if not p.is_file() or p.is_symlink():
        raise ValueError('Regular installer payload required: ' + name)
if (root / 'usr/local/share/daemonarchy-installer/ABI').read_text().strip() != abi:
    raise ValueError('Live-root ABI does not match selected EFI architecture')
if not (root / 'usr/local/share/daemonarchy-installer/repo/All').is_dir():
    raise ValueError('Missing complete offline installer repository')
for name in ('boot/kernel/kernel', 'bin/sh', 'boot/kernel/geom_uzip.ko'):
    with (root / name).open('rb') as stream:
        header = stream.read(20)
    if (len(header) != 20 or header[:7] != b'\x7fELF\x02\x01\x01'
            or struct.unpack_from('<H', header, 18)[0] != machine):
        raise ValueError('Wrong native ELF architecture: ' + name)
CHECK
# Keep the existing database, caches and service state when rc.d/var mounts
# writable memory over /var. Use an input-bound fresh seed, never erase one.
seed=/usr/local/share/daemonarchy-installer/ram-var-$(printf '%s' "$archive_hash" | cut -c1-16)
mkdir "$world$seed"
tar -cf "$work/var.tar" -C "$world/var" .
tar -xpf "$work/var.tar" -C "$world$seed"
printf '\n# Preserve packaged /var in the live RAM root.\nvarmfs_flags="-k %s"\n' "$seed" >> "$world/etc/rc.conf"
printf '/dev/md0.uzip / ufs ro 0 0\ntmpfs /tmp tmpfs rw,mode=1777 0 0\n' > "$world/etc/fstab"
makefs -t ffs -B little -o version=2 -f 10% -b 5% "$work/mfsroot" "$world" > "$work/makefs.log" 2>&1
fsck_ffs -n "$work/mfsroot" > "$work/fsck.log" 2>&1 || { cat "$work/fsck.log" >&2; exit 1; }
if grep -Eiq 'INTEGRITY CHECK FAILED|CORRUPT|UNEXPECTED INCONSISTENCY|BAD |UNREF |SKIPPED' "$work/fsck.log" ||
    ! grep -Fq '** Phase 5 - Check Cyl groups' "$work/fsck.log"; then
    cat "$work/fsck.log" >&2; exit 1;
fi
mkdir -p "$work/outer/boot" "$work/outer/etc"
cp -Rp "$world/boot/." "$work/outer/boot/"
mkuzip -L -s 262144 -j 2 -o "$work/outer/boot/mfsroot.uzip" "$work/mfsroot"
[ "$(stat -f %z "$work/outer/boot/mfsroot.uzip")" -lt 4294967296 ] || {
    echo 'Packed RAM root exceeds the 4 GiB bootstrap input profile' >&2; exit 1;
}
cat >> "$work/outer/boot/loader.conf.local" <<'CONF'

# Complete live root is loaded before kernel device takeover.
mfsroot_load="YES"
mfsroot_type="md_image"
mfsroot_name="/boot/mfsroot.uzip"
geom_uzip_load="YES"
vfs.root.mountfrom="ufs:/dev/md0.uzip"
CONF
tar -cf "$work/outer.tar" -C "$work/outer" .
sh "$here/make-efi-iso.sh" "$work/outer.tar" "$label" "$output" "$work/iso" "$boot_file" "$boot_mode"
[ "$(sha256 -q "$archive")" = "$archive_hash" ] || { echo 'Live-root input changed during authoring' >&2; exit 1; }
"$py" - "$archive" "$archive_hash" "$world" "$work" "$output" "$seed" "$boot_file" "$boot_mode" <<'RECORD'
from pathlib import Path
import hashlib, json, stat, struct, sys
archive, expected, root, work, image, seed, boot, mode = sys.argv[1:]
root, work, image = map(Path, (root, work, image))
def artifact(p):
    with p.open('rb') as stream:
        h = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(bytes=p.stat().st_size, sha256=h)
packed = work / 'outer/boot/mfsroot.uzip'
with packed.open('rb') as stream:
    header = stream.read(136)
if len(header) != 136 or header[:11] != b'#!/bin/sh\n#' or chr(header[11]).upper() != 'L':
    raise ValueError('Expected native LZMA UZIP')
cluster, blocks = struct.unpack_from('>II', header, 128)
expanded = artifact(work / 'mfsroot')
if cluster != 262144 or not expanded['bytes'] <= cluster * blocks < expanded['bytes'] + cluster:
    raise ValueError('Unexpected packed-root geometry')
record = dict(schema='daemonarchy/ram-live-image@1',
    abi=(root / 'usr/local/share/daemonarchy-installer/ABI').read_text().strip(),
    input_archive_sha256=expected, outer_archive=artifact(work / 'outer.tar'),
    kernel=artifact(root / 'boot/kernel/kernel'),
    package_database=artifact(root / 'var/db/pkg/local.sqlite'),
    root_directory=dict(mode=format(stat.S_IMODE(root.stat().st_mode), '04o'),
                        uid=root.stat().st_uid, gid=root.stat().st_gid),
    var_seed=seed, ram_root=expanded, packed_root=artifact(packed),
    codec='lzma', cluster_bytes=cluster, expanded_media_bytes=cluster * blocks,
    boot_file=boot, boot_mode=mode, image=artifact(image),
    qualification=dict(assembly=True, native_root_fsck=True, vm_boot=False,
                       installation=False, desktop=False, recovery=False, physical=False, signing=False))
with Path(str(image) + '.ram.json').open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps(record, indent=2))
RECORD
