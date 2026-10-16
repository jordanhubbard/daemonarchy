#!/usr/bin/env bash
# Exercise real tar exclusions and the actual image-size gate, without a build.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/root"
for path in usr/include/sys/param.h usr/lib/libc.a usr/lib/clang/21/include/stddef.h \
  usr/lib/libprivateclang.so.21 usr/lib/libprivatellvm.so.21 usr/lib/libprivatelldb.so.21 \
  usr/bin/cc usr/bin/clang usr/bin/lldb usr/bin/llvm-objcopy usr/bin/strip \
  boot/kernel/kernel boot/kernel/zfs.ko boot/loader.efi lib/libc.so.7 \
  usr/lib/libssl.so.35 usr/bin/fetch usr/bin/ssh usr/bin/tar usr/sbin/gpart \
  usr/local/bin/bash usr/local/bin/gum usr/local/sbin/pkg-static \
  usr/local/share/daemonarchy-installer/checkouts.json \
  usr/local/share/daemonarchy-installer/repo/All/nvidia-kmod.pkg \
  usr/freebsd-dist/base.txz usr/freebsd-dist/kernel.txz; do
  mkdir -p "$work/root/$(dirname "$path")"
  printf 'fixture\n' >"$work/root/$path"
done
tar -C "$work/root" -X "$here/scripts/live-image-excludes" -cf "$work/live.tar" .
tar -tf "$work/live.tar" >"$work/contents"
for path in usr/include/sys/param.h usr/lib/libc.a usr/lib/clang/21/include/stddef.h \
  usr/lib/libprivateclang.so.21 usr/lib/libprivatellvm.so.21 usr/lib/libprivatelldb.so.21 \
  usr/bin/cc usr/bin/clang usr/bin/lldb usr/bin/llvm-objcopy usr/bin/strip; do
  if grep -qxF "./$path" "$work/contents"; then echo "Retained development file: $path" >&2; exit 1; fi
done
for path in boot/kernel/kernel boot/kernel/zfs.ko boot/loader.efi lib/libc.so.7 \
  usr/lib/libssl.so.35 usr/bin/fetch usr/bin/ssh usr/bin/tar usr/sbin/gpart \
  usr/local/bin/bash usr/local/bin/gum usr/local/sbin/pkg-static \
  usr/local/share/daemonarchy-installer/checkouts.json \
  usr/local/share/daemonarchy-installer/repo/All/nvidia-kmod.pkg \
  usr/freebsd-dist/base.txz usr/freebsd-dist/kernel.txz; do
  grep -qxF "./$path" "$work/contents"
done
# Sparse files exercise the real 2 GiB boundary without allocating that space.
truncate -s 2147483647 "$work/budget.iso"
sh "$here/scripts/check-image-size.sh" "$work/budget.iso"
for bytes in 2147483648 2371284992; do
  truncate -s "$bytes" "$work/budget.iso"
  if sh "$here/scripts/check-image-size.sh" "$work/budget.iso"; then
    echo "Accepted oversized image: $bytes" >&2; exit 1
  fi
done
echo 'PASS: live development files excluded, install payload retained, image budget enforced'
