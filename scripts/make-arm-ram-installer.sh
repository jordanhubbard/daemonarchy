#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Full installer RAM root for native ARM kernel bring-up. FreeBSD worker only.
# This creates regular files; it never selects or writes a physical device.
set -eu
usage='usage: make-arm-ram-installer.sh world.txz world-sha256 kernel kernel-sha256 omarchy.pkg package-sha256 output.iso new-work-dir'
[ "$#" -eq 8 ] || { echo "$usage" >&2; exit 2; }
[ "$(uname -s)" = FreeBSD ] && [ "$(id -u)" -eq 0 ] || {
    echo 'Run on the allocated native FreeBSD worker as root' >&2; exit 1;
}
archive=$1 archive_hash=$2 kernel=$3 kernel_hash=$4
package=$5 package_hash=$6 output=$7 work=$8
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
for pin in "$archive_hash" "$kernel_hash" "$package_hash"; do
    [ "${#pin}" = 64 ] || { echo 'Input hashes must be SHA-256' >&2; exit 2; }
    case "$pin" in *[!0-9a-f]*) echo 'Malformed SHA-256' >&2; exit 2 ;; esac
done
for input in "$archive" "$kernel" "$package"; do
    [ -f "$input" ] && [ ! -L "$input" ] || { echo 'Regular nonsymlink inputs required' >&2; exit 1; }
done
archive=$(realpath "$archive")
kernel=$(realpath "$kernel")
package=$(realpath "$package")
[ "$(sha256 -q "$archive")" = "$archive_hash" ] &&
    [ "$(sha256 -q "$kernel")" = "$kernel_hash" ] &&
    [ "$(sha256 -q "$package")" = "$package_hash" ] || {
    echo 'Input checksum mismatch' >&2; exit 1;
}
[ "$(od -An -tx1 -N6 "$kernel" | tr -d ' \n')" = 7f454c460201 ] &&
    [ "$(od -An -tu2 -j18 -N2 "$kernel" | tr -d ' \n')" = 183 ] || {
    echo 'An AArch64 ELF64 kernel is required' >&2; exit 1;
}
[ "$(pkg query -F "$package" '%n %q')" = 'omarchy FreeBSD:16:aarch64' ] || {
    echo 'Expected an Omarchy package for FreeBSD:16:aarch64' >&2; exit 1;
}
for destination in "$work" "$output" "$output.manifest.json"; do
    [ ! -e "$destination" ] && [ ! -L "$destination" ] || {
        echo 'Outputs and work directory must not exist' >&2; exit 1;
    }
    case "$destination" in /*) ;; *) echo 'Absolute output paths required' >&2; exit 2 ;; esac
done
mkdir -m 0700 "$work"
mkdir "$work/no-repos"
world=$work/world
mkdir "$world"
tar -xpf "$archive" -C "$world"
share=$world/usr/local/share/daemonarchy-installer
for required in boot/loader.efi usr/freebsd-dist/base.txz usr/freebsd-dist/kernel.txz \
    usr/freebsd-dist/MANIFEST usr/local/libexec/daemonarchy-installer/install \
    var/db/pkg/local.sqlite; do
    [ -f "$world/$required" ] || { echo "Missing full installer payload: $required" >&2; exit 1; }
done
[ "$(cat "$share/ABI")" = FreeBSD:16:aarch64 ] || { echo 'Installer ABI mismatch' >&2; exit 1; }
[ -d "$share/repo/All" ] || { echo 'Missing installer package repository' >&2; exit 1; }

# Keep the live kernel and the kernel installed by this medium together.
cp -p "$kernel" "$world/boot/kernel/kernel"
mkdir "$work/kernel-set"
tar -xpf "$world/usr/freebsd-dist/kernel.txz" -C "$work/kernel-set"
[ -f "$work/kernel-set/boot/kernel/kernel" ] || { echo 'Invalid kernel set' >&2; exit 1; }
cp -p "$kernel" "$work/kernel-set/boot/kernel/kernel"
tar -cJf "$work/kernel.txz" -C "$work/kernel-set" .
mv "$work/kernel.txz" "$world/usr/freebsd-dist/kernel.txz"
set_hash=$(sha256 -q "$world/usr/freebsd-dist/kernel.txz")
awk -v digest="$set_hash" 'BEGIN { FS=OFS="\t" } $1=="kernel.txz" {$2=digest; found=1} {print} END {if (!found) exit 1}' \
    "$world/usr/freebsd-dist/MANIFEST" > "$work/MANIFEST"
mv "$work/MANIFEST" "$world/usr/freebsd-dist/MANIFEST"

# Install only into the disposable root, then refresh its unsigned local ISO
# repository. Public dependency signatures and configured feeds are untouched.
mounted=no
cleanup() { [ "$mounted" = no ] || umount "$world/dev"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
mount -t devfs -o ruleset=4 devfs "$world/dev"
mounted=yes
env ASSUME_ALWAYS_YES=yes pkg -r "$world" -o REPOS_DIR="$work/no-repos" add -f "$package"
package_version=$(pkg query -F "$package" '%v')
[ "$(pkg -r "$world" query '%v' omarchy)" = "$package_version" ]
pkg -r "$world" query '%n %v %q' | LC_ALL=C sort > "$work/installed-packages.txt"
umount "$world/dev"
mounted=no
cp -p "$package" "$share/repo/All/omarchy-$package_version.pkg"
pkg repo "$share/repo"

# A compressed read-only root retains the live image's existing in-memory
# /var and /tmp handling. UZIP avoids gzip's 32-bit uncompressed-size field
# and does not require reserving the entire expanded filesystem in RAM.
[ -f "$world/boot/kernel/geom_uzip.ko" ] || { echo 'Missing GEOM UZIP module' >&2; exit 1; }
printf '/dev/md0.uzip / ufs ro 0 0\ntmpfs /tmp tmpfs rw,mode=1777 0 0\n' > "$world/etc/fstab"
cat >> "$world/boot/loader.conf.local" <<'EOF'

# Entire installer root is loaded through EFI before kernel device takeover.
mfsroot_load="YES"
mfsroot_type="md_image"
mfsroot_name="/boot/mfsroot.uzip"
geom_uzip_load="YES"
vfs.root.mountfrom="ufs:/dev/md0.uzip"
EOF
makefs -t ffs -B little -o version=2 -f 10% -b 5% "$work/mfsroot" "$world"
# UFS1's legacy inode-count field can overflow for a complete desktop root.
# fsck_ffs -n may return zero even after reporting bad cylinder groups, so
# retain and inspect its diagnostics as well as its exit status.
fsck_ffs -n "$work/mfsroot" > "$work/fsck.log" 2>&1 || {
    cat "$work/fsck.log" >&2; exit 1;
}
if grep -Eiq 'INTEGRITY CHECK FAILED|CORRUPT|UNEXPECTED INCONSISTENCY|BAD |UNREF |SKIPPED' "$work/fsck.log"; then
    cat "$work/fsck.log" >&2
    echo 'RAM-root filesystem failed independent integrity checks' >&2; exit 1;
fi
grep -Fq '** Phase 5 - Check Cyl groups' "$work/fsck.log" || {
    cat "$work/fsck.log" >&2; echo 'Incomplete RAM-root integrity check' >&2; exit 1;
}
root_size=$(stat -f %z "$work/mfsroot")
root_hash=$(sha256 -q "$work/mfsroot")
mkuzip -j 2 -o "$work/mfsroot.uzip" "$work/mfsroot"
[ "$(stat -f %z "$work/mfsroot.uzip")" -lt 4294967296 ] || {
    echo 'Compressed RAM payload exceeds the 4 GiB bootstrap input profile' >&2; exit 1;
}
mkdir -p "$work/outer/boot" "$work/outer/etc"
cp -Rp "$world/boot/." "$work/outer/boot/"
cp "$work/mfsroot.uzip" "$work/outer/boot/mfsroot.uzip"
cp "$work/installed-packages.txt" "$work/outer/installed-packages.txt"
tar -cf "$work/outer.tar" -C "$work/outer" .
sh "$here/make-efi-iso.sh" "$work/outer.tar" DAEMARMROOT "$output" "$work/iso" BOOTAA64.EFI

# Record actual bytes, not native hardware or installation qualification.
export RAM_ARCHIVE_HASH=$archive_hash RAM_KERNEL_HASH=$kernel_hash RAM_PACKAGE_HASH=$package_hash
export RAM_ROOT_HASH=$root_hash RAM_ROOT_SIZE=$root_size RAM_PACKAGE_VERSION=$package_version
[ "$(sha256 -q "$archive")" = "$archive_hash" ] &&
    [ "$(sha256 -q "$kernel")" = "$kernel_hash" ] &&
    [ "$(sha256 -q "$package")" = "$package_hash" ] || { echo 'Inputs changed during assembly' >&2; exit 1; }
python3.12 - "$output" "$work/mfsroot.uzip" "$set_hash" "$work/installed-packages.txt" <<'PY'
import hashlib, json, os, sys
from pathlib import Path
image, compressed = map(Path, sys.argv[1:3])
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
record = dict(schema='daemonarchy/arm-ram-installer@1', abi='FreeBSD:16:aarch64',
    world_archive_sha256=os.environ['RAM_ARCHIVE_HASH'], kernel_sha256=os.environ['RAM_KERNEL_HASH'],
    kernel_set_sha256=sys.argv[3], omarchy_package_sha256=os.environ['RAM_PACKAGE_HASH'],
    omarchy_version=os.environ['RAM_PACKAGE_VERSION'],
    ram_root=dict(bytes=int(os.environ['RAM_ROOT_SIZE']), sha256=os.environ['RAM_ROOT_HASH'],
                  format='ufs-geom-uzip', compressed_bytes=compressed.stat().st_size,
                  compressed_sha256=digest(compressed)),
    installed_packages_sha256=digest(Path(sys.argv[4])),
    image=dict(bytes=image.stat().st_size, sha256=digest(image)),
    qualification=dict(assembly=True, vm_boot=False, physical_boot=False, installation=False,
                       desktop=False, recovery=False))
with Path(str(image)+'.manifest.json').open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps(record, indent=2))
PY
