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
  usr/lib32/libc++.so.1 libexec/ld-elf32.so.1 usr/bin/ldd32 \
  boot/kernel/kernel boot/kernel/zfs.ko boot/loader.efi lib/libc.so.7 \
  usr/lib/libssl.so.35 usr/bin/fetch usr/bin/ssh usr/bin/tar usr/sbin/gpart \
  usr/local/bin/bash usr/local/bin/gum usr/local/sbin/pkg-static \
  usr/local/share/daemonarchy-installer/checkouts.json \
  usr/local/share/daemonarchy-installer/repo/All/nvidia-kmod.pkg \
  usr/freebsd-dist/base.txz usr/freebsd-dist/kernel.txz usr/freebsd-dist/lib32.txz; do
  mkdir -p "$work/root/$(dirname "$path")"
  printf 'fixture\n' >"$work/root/$path"
done
tar -C "$work/root" -X "$here/scripts/live-image-excludes" -cf "$work/live.tar" .
tar -tf "$work/live.tar" >"$work/contents"
for path in usr/include/sys/param.h usr/lib/libc.a usr/lib/clang/21/include/stddef.h \
  usr/lib/libprivateclang.so.21 usr/lib/libprivatellvm.so.21 usr/lib/libprivatelldb.so.21 \
  usr/bin/cc usr/bin/clang usr/bin/lldb usr/bin/llvm-objcopy usr/bin/strip \
  usr/lib32/libc++.so.1 libexec/ld-elf32.so.1 usr/bin/ldd32; do
  if grep -qxF "./$path" "$work/contents"; then echo "Retained development file: $path" >&2; exit 1; fi
done
for path in boot/kernel/kernel boot/kernel/zfs.ko boot/loader.efi lib/libc.so.7 \
  usr/lib/libssl.so.35 usr/bin/fetch usr/bin/ssh usr/bin/tar usr/sbin/gpart \
  usr/local/bin/bash usr/local/bin/gum usr/local/sbin/pkg-static \
  usr/local/share/daemonarchy-installer/checkouts.json \
  usr/local/share/daemonarchy-installer/repo/All/nvidia-kmod.pkg \
  usr/freebsd-dist/base.txz usr/freebsd-dist/kernel.txz usr/freebsd-dist/lib32.txz; do
  grep -qxF "./$path" "$work/contents"
done
# Apply the real post-install Python pruning block to a disposable live root.
world=$work/python-live
python_lib=$world/usr/local/lib/python3.12
mkdir -p "$python_lib/test/support" "$python_lib/config-3.12" "$python_lib/lib-dynload" "$python_lib/json/__pycache__"
for path in test/support/data config-3.12/libpython3.12.a lib-dynload/_ssl.so json/__init__.py \
  json/__pycache__/__init__.pyc json/__pycache__/__init__.opt-1.pyc json/__pycache__/__init__.opt-2.pyc; do
  printf 'fixture\n' >"$python_lib/$path"
done
eval "$(sed -n '/^for python_lib in /,/^done$/p' "$here/live-post.sh")"
[[ ! -e $python_lib/test && ! -e $python_lib/config-3.12/libpython3.12.a ]]
[[ ! -e $python_lib/json/__pycache__/__init__.opt-1.pyc && ! -e $python_lib/json/__pycache__/__init__.opt-2.pyc ]]
[[ -f $python_lib/lib-dynload/_ssl.so && -f $python_lib/json/__init__.py && -f $python_lib/json/__pycache__/__init__.pyc ]]
# Apply the real live desktop trim to a disposable root: toolchains, headers,
# static archives and documentation go; shared runtime libraries stay.
world=$work/desktop-live
for path in usr/local/llvm19/bin/clang usr/local/llvm19/include/llvm/IR.h usr/local/llvm19/lib/libLLVMCore.a \
  usr/local/llvm19/lib/clang/19/include/stddef.h usr/local/llvm19/lib/libLLVM.so.19.1 \
  usr/local/libexec/gcc14/cc1 usr/local/lib/gcc14/gcc/x86_64-portbld-freebsd16.0/14.2.0/crtbegin.o \
  usr/local/lib/gcc14/libgfortran.so.5 usr/local/lib/gcc14/libgfortran.a usr/local/include/gtk-3.0/gtk.h \
  usr/local/lib/libgtk-3.so.0 usr/local/lib/libfoo.a usr/local/share/doc/mesa/README \
  usr/local/bin/Hyprland usr/local/share/hypr/wall0.png; do
  mkdir -p "$world/$(dirname "$path")"
  printf 'fixture\n' >"$world/$path"
done
eval "$(sed -n '/^\techo "Live \/usr\/local before desktop trim/,/^\techo "Live \/usr\/local after desktop trim/p' "$here/live-post.sh")" >/dev/null
for path in usr/local/llvm19/bin usr/local/llvm19/include usr/local/llvm19/lib/libLLVMCore.a usr/local/llvm19/lib/clang \
  usr/local/libexec/gcc14 usr/local/lib/gcc14/gcc usr/local/lib/gcc14/libgfortran.a usr/local/include \
  usr/local/lib/libfoo.a usr/local/share/doc; do
  if [[ -e $world/$path ]]; then echo "Retained live desktop development file: $path" >&2; exit 1; fi
done
for path in usr/local/llvm19/lib/libLLVM.so.19.1 usr/local/lib/gcc14/libgfortran.so.5 usr/local/lib/libgtk-3.so.0 \
  usr/local/bin/Hyprland usr/local/share/hypr/wall0.png; do
  [[ -f $world/$path ]] || { echo "Removed live desktop runtime file: $path" >&2; exit 1; }
done
# Sparse files exercise the real raw and published boundaries without
# allocating that space. The 2 GiB asset limit applies to the published .xz;
# the raw image keeps a 3.5 GiB budget for 4 GB USB media.
truncate -s 3758096383 "$work/budget.iso"
sh "$here/scripts/check-image-size.sh" "$work/budget.iso"
truncate -s 2371284992 "$work/budget.iso"
truncate -s 2147483647 "$work/budget.iso.xz"
sh "$here/scripts/check-image-size.sh" "$work/budget.iso" "$work/budget.iso.xz"
for bytes in 3758096384 4000000000; do
  truncate -s "$bytes" "$work/budget.iso"
  if sh "$here/scripts/check-image-size.sh" "$work/budget.iso"; then
    echo "Accepted oversized raw image: $bytes" >&2; exit 1
  fi
done
truncate -s 2371284992 "$work/budget.iso"
for bytes in 2147483648 2371284992; do
  truncate -s "$bytes" "$work/budget.iso.xz"
  if sh "$here/scripts/check-image-size.sh" "$work/budget.iso" "$work/budget.iso.xz"; then
    echo "Accepted oversized published image: $bytes" >&2; exit 1
  fi
done
truncate -s 1 "$work/budget.iso.gz"
if sh "$here/scripts/check-image-size.sh" "$work/budget.iso" "$work/budget.iso.gz"; then
  echo 'Accepted a non-xz published image' >&2; exit 1
fi
echo 'PASS: live development files excluded, install payload retained, raw and published image budgets enforced'
