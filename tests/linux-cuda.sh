#!/usr/bin/env bash
# Policy checks for the Linux CUDA toolkit pinned to the image driver.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck disable=SC1091
source "$here/overlay/usr/local/sbin/daemonarchy-linux-cuda"
check() { [[ $1 == "$2" ]] || { echo "Expected '$2', got '$1'" >&2; exit 1; }; }
check "$(linux_cuda_spec)" '595.104.02 cuda-toolkit-13-2'
studio=$(DISPLAY=:0 XAUTHORITY='' XDG_RUNTIME_DIR='' cudalab_script jkh)
grep -q 'exec ./build/dev/cudalab$' <<<"$studio"
showcase=$(DISPLAY=:0 XAUTHORITY='' XDG_RUNTIME_DIR='' cudalab_script jkh cuda-cosmos)
grep -q 'exec ./build/dev/cudalab --demo cuda-cosmos$' <<<"$showcase"
build=$(cudalab_script jkh '' build)
grep -q 'cmake --build --preset dev' <<<"$build"
grep -q 'Cudalab build complete' <<<"$build"
! grep -q 'exec ./build/dev/cudalab' <<<"$build"
bash -n <<<"$build"
[[ -f $here/overlay/usr/local/share/daemonarchy-installer/uvm_ioctl_override.c ]]
grep -q 'NV_UVM_INITIALIZE' "$here/overlay/usr/local/share/daemonarchy-installer/uvm_ioctl_override.c"
# dnf downloads in parallel (the CUDA phase is network-bound), once, under [main].
dnf_root=$(mktemp -d)
trap 'rm -rf "$dnf_root"' EXIT
mkdir -p "$dnf_root/etc/dnf"
printf '[main]\ngpgcheck=1\n' >"$dnf_root/etc/dnf/dnf.conf"
linux_root=$dnf_root
dnf_no_caps
dnf_parallel
dnf_parallel
check "$(grep -c '^max_parallel_downloads=16$' "$dnf_root/etc/dnf/dnf.conf")" 1
check "$(sed -n 2p "$dnf_root/etc/dnf/dnf.conf")" 'max_parallel_downloads=16'
grep -q '^tsflags=nocaps$' "$dnf_root/etc/dnf/dnf.conf"
echo 'PASS: Linux CUDA toolkit pin and UVM shim'
echo 'PASS: dnf downloads in parallel'

