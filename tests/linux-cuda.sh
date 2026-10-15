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
[[ -f $here/overlay/usr/local/share/daemonarchy-installer/uvm_ioctl_override.c ]]
grep -q 'NV_UVM_INITIALIZE' "$here/overlay/usr/local/share/daemonarchy-installer/uvm_ioctl_override.c"
echo 'PASS: Linux CUDA toolkit pin and UVM shim'
