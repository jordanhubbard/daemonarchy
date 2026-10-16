#!/bin/sh
# Prepare public boot inputs only. Signing happens separately on its protected host.
set -eu
if [ "$(uname -s)" != FreeBSD ] || [ "$#" -ne 3 ]; then
    echo "Usage (native FreeBSD): $0 SET_CACHE BUILD_DIRECTORY FRESH_STAGING_ROOT" >&2
    exit 1
fi
cache=$(realpath "$1")
build=$(realpath "$2")
root=$3
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
[ ! -e "$root" ] || { echo 'Use a fresh staging root' >&2; exit 1; }
for name in base kernel; do
    expected=$(awk -v name="$name.txz" '$1 == name { print $2 }' "$cache/MANIFEST")
    actual=$(sha256 -q "$cache/$name.txz")
    [ -n "$expected" ] && [ "$actual" = "$expected" ] || {
        echo "Cached $name set does not match MANIFEST" >&2; exit 1;
    }
done
mkdir -p "$root"
tar --no-same-owner -xpf "$cache/base.txz" -C "$root" ./boot
tar --no-same-owner -xpf "$cache/kernel.txz" -C "$root" ./boot
if ! strings "$root/boot/kernel/kernel" | grep -q '3ceb5f150'; then
    echo 'Stock kernel does not match the qualified source snapshot' >&2
    exit 1
fi
mkdir -p "$root/boot/kernel.secure"
cp "$build/kernel" "$root/boot/kernel.secure/kernel"
cp "$build/loader_normal.efi" "$root/boot/loader_normal.efi"
cp "$here/boot/local.lua" "$root/boot/lua/local.lua"
cp "$here/boot/daemonarchy-secureboot.conf" "$root/boot/"
cp "$here/../overlay/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua" "$root/boot/lua/"
echo 'Prepared clean boot tree; no QA probes, userland or signing key included'
