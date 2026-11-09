#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Full installer RAM root for native ARM kernel bring-up. FreeBSD worker only.
# This creates regular files; it never selects or writes a physical device.
set -eu
usage='usage: make-arm-ram-installer.sh world.txz world-sha256 kernel.txz kernel-set-sha256 omarchy.pkg package-sha256 output.iso new-work-dir closure.json closure-sha256'
[ "$#" -eq 10 ] || { echo "$usage" >&2; exit 2; }
if [ "$(uname -s)" != FreeBSD ] || [ "$(id -u)" -ne 0 ]; then
    echo 'Run on the allocated native FreeBSD worker as root' >&2; exit 1;
fi
archive=$1 archive_hash=$2 kernel_set=$3 kernel_set_hash=$4
package=$5 package_hash=$6 output=$7 work=$8
closure=$9 closure_hash=${10}
pkg_cmd=/usr/local/sbin/pkg
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
[ -f "$here/make-efi-iso.sh" ] || {
    echo 'The co-located EFI ISO builder is missing' >&2; exit 1;
}
[ -f "$here/check-arm-kernel-set.py" ] || {
    echo 'The co-located ARM kernel-set checker is missing' >&2; exit 1;
}
for pin in "$archive_hash" "$kernel_set_hash" "$package_hash" "$closure_hash"; do
    [ "${#pin}" = 64 ] || { echo 'Input hashes must be SHA-256' >&2; exit 2; }
    case "$pin" in *[!0-9a-f]*) echo 'Malformed SHA-256' >&2; exit 2 ;; esac
done
for input in "$archive" "$kernel_set" "$package" "$closure"; do
    if [ ! -f "$input" ] || [ -L "$input" ]; then
        echo 'Regular nonsymlink inputs required' >&2; exit 1;
    fi
done
archive=$(realpath "$archive")
kernel_set=$(realpath "$kernel_set")
package=$(realpath "$package")
closure=$(realpath "$closure")
if [ "$(sha256 -q "$archive")" != "$archive_hash" ] ||
    [ "$(sha256 -q "$kernel_set")" != "$kernel_set_hash" ] ||
    [ "$(sha256 -q "$package")" != "$package_hash" ]; then
    echo 'Input checksum mismatch' >&2; exit 1;
fi
kernel_hash=$(python3.12 "$here/check-arm-kernel-set.py" "$kernel_set")
[ "$("$pkg_cmd" query -F "$package" '%n %q')" = 'omarchy FreeBSD:16:aarch64' ] || {
    echo 'Expected an Omarchy package for FreeBSD:16:aarch64' >&2; exit 1;
}
for destination in "$work" "$output" "$output.manifest.json"; do
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        echo 'Outputs and work directory must not exist' >&2; exit 1;
    fi
    case "$destination" in /*) ;; *) echo 'Absolute output paths required' >&2; exit 2 ;; esac
done
[ -f "$here/arm-package-closure.py" ] || {
    echo 'The co-located ARM package-closure checker is missing' >&2; exit 1;
}
python3.12 "$here/arm-package-closure.py" verify "$closure" "$closure_hash" "$package_hash"
mkdir -m 0700 "$work"
python3.12 "$here/arm-package-closure.py" stage "$closure" "$closure_hash" "$package_hash" \
    --destination "$work/packages" > "$work/package-closure.json"
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

# Replace the entire live kernel/module closure; do not retain modules from
# the original installer alongside a kernel from another native build.
rm -rf "$world/boot/kernel" "$world/boot/dtb" \
    "$world/usr/lib/debug/boot/kernel" "$world/usr/lib/debug/boot/dtb"
tar -xpf "$kernel_set" -C "$world"
cp -p "$kernel_set" "$world/usr/freebsd-dist/kernel.txz"
set_hash=$(sha256 -q "$world/usr/freebsd-dist/kernel.txz")
if [ "$set_hash" != "$kernel_set_hash" ] ||
    [ "$(sha256 -q "$world/boot/kernel/kernel")" != "$kernel_hash" ]; then
    echo 'Kernel set changed during assembly' >&2; exit 1;
fi
awk -v digest="$set_hash" 'BEGIN { FS=OFS="\t" } $1=="kernel.txz" {$2=digest; found=1} {print} END {if (!found) exit 1}' \
    "$world/usr/freebsd-dist/MANIFEST" > "$work/MANIFEST"
mv "$work/MANIFEST" "$world/usr/freebsd-dist/MANIFEST"

# Install only into the disposable root, then refresh its unsigned local ISO
# repository. Public dependency signatures and configured feeds are untouched.
mounted=no
packages_mounted=no
cleanup() {
    cleanup_status=0
    if [ "$packages_mounted" = yes ]; then umount "$world/ram-packages" || cleanup_status=1; fi
    if [ "$mounted" = yes ]; then umount "$world/dev" || cleanup_status=1; fi
    return "$cleanup_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
mount -t devfs -o ruleset=4 devfs "$world/dev"
mounted=yes
# A private directory contains only the verified closure. Install every selected
# archive, so an old dependency already in the live root cannot survive by name.
# The trimmed live skeleton omits this directory, but ConsoleKit's native
# post-install script expects it before touching its history file.
install -d -m 0755 "$world/var/log/ConsoleKit"
mkdir "$world/ram-packages" "$world/ram-no-repos"
mount -t nullfs -o ro "$work/packages" "$world/ram-packages"
packages_mounted=yes
python3.12 "$here/arm-package-closure.py" install "$closure" "$closure_hash" "$package_hash" \
    --destination "$work/packages" --root "$world" --repository "$world/ram-no-repos"
python3.12 "$here/arm-package-closure.py" installed "$closure" "$closure_hash" "$package_hash" --root "$world"
package_version=$("$pkg_cmd" query -F "$package" '%v')
"$pkg_cmd" -r "$world" query '%n %v %q' | LC_ALL=C sort > "$work/installed-packages.txt"
umount "$world/ram-packages"
packages_mounted=no
rmdir "$world/ram-packages" "$world/ram-no-repos"
umount "$world/dev"
mounted=no
python3.12 "$here/arm-package-closure.py" repo "$closure" "$closure_hash" "$package_hash" \
    --destination "$work/packages" --repository "$share/repo/All"
cp "$work/package-closure.json" "$share/ram-package-closure.json"
"$pkg_cmd" repo "$share/repo"

# rc.d/var mounts a fresh writable /var over the read-only root. Seed it
# through mdmfs's supported skeleton option so pkg retains the built inventory.
mkdir "$share/ram-var"
tar -cf - -C "$world/var" . | tar -xpf - -C "$share/ram-var"
cat >> "$world/etc/rc.conf" <<'EOF'

# Preserve the packaged state when rc.d/var creates its writable RAM filesystem.
varmfs_flags="-k /usr/local/share/daemonarchy-installer/ram-var"
EOF

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
# Preserve the complete filesystem while avoiding the size of 16 KiB zlib
# clusters. The selected GENERIC set must still pass exact-image VM/board QA.
mkuzip -L -s 262144 -j 2 -o "$work/mfsroot.uzip" "$work/mfsroot"
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
export RAM_ARCHIVE_HASH="$archive_hash" RAM_KERNEL_HASH="$kernel_hash" RAM_PACKAGE_HASH="$package_hash"
export RAM_ROOT_HASH="$root_hash" RAM_ROOT_SIZE="$root_size" RAM_PACKAGE_VERSION="$package_version"
export RAM_CLOSURE_HASH="$closure_hash"
if [ "$(sha256 -q "$archive")" != "$archive_hash" ] ||
    [ "$(sha256 -q "$kernel_set")" != "$kernel_set_hash" ] ||
    [ "$(sha256 -q "$package")" != "$package_hash" ]; then
    echo 'Inputs changed during assembly' >&2; exit 1;
fi
python3.12 "$here/arm-package-closure.py" verify "$closure" "$closure_hash" "$package_hash"
python3.12 - "$output" "$work/mfsroot.uzip" "$set_hash" "$work/installed-packages.txt" "$work/package-closure.json" <<'PY'
import hashlib, json, os, struct, sys
from pathlib import Path
image, compressed = map(Path, sys.argv[1:3])
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
with compressed.open('rb') as stream:
    header = stream.read(136)
if len(header) != 136 or header[:11] != b'#!/bin/sh\n#' or chr(header[11]).upper() != 'L':
    raise ValueError('Expected a native LZMA UZIP payload')
cluster, blocks = struct.unpack_from('>II', header, 128)
root_size = int(os.environ['RAM_ROOT_SIZE'])
if cluster != 262144 or not root_size <= cluster * blocks < root_size + cluster:
    raise ValueError('Unexpected UZIP cluster geometry')
record = dict(schema='daemonarchy/arm-ram-installer@1', abi='FreeBSD:16:aarch64',
    world_archive_sha256=os.environ['RAM_ARCHIVE_HASH'], kernel_sha256=os.environ['RAM_KERNEL_HASH'],
    kernel_set_sha256=sys.argv[3], omarchy_package_sha256=os.environ['RAM_PACKAGE_HASH'],
    omarchy_version=os.environ['RAM_PACKAGE_VERSION'],
    package_closure_manifest_sha256=os.environ['RAM_CLOSURE_HASH'],
    package_closure_inventory_sha256=digest(Path(sys.argv[5])),
    package_closure_count=len(json.loads(Path(sys.argv[5]).read_text())['packages']),
    ram_root=dict(bytes=root_size, sha256=os.environ['RAM_ROOT_HASH'],
                  format='ufs-geom-uzip', codec='lzma', cluster_bytes=cluster,
                  expanded_media_bytes=cluster * blocks, zero_padding_bytes=cluster * blocks - root_size,
                  compressed_bytes=compressed.stat().st_size,
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
