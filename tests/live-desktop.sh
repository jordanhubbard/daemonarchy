#!/usr/bin/env bash
# Live desktop controls (LIVE-001) without booting, mounting or loading
# anything: the rc service, GPU selection, session fallback and image wiring
# run against recorded command stubs. Native mount and boot behavior is
# qualified separately on FreeBSD (see HACKING.md).
# shellcheck disable=SC2034
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lib=$here/overlay/usr/local/libexec/daemonarchy-installer
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# ---------------------------------------------------------------- no unionfs
# A unionfs probe over the ISO's /etc stopped a FreeBSD 16-CURRENT host during
# pw's password database rename. No live-path file may use unionfs.
if grep -n 'mount_unionfs\|-t unionfs\|unionfs\.ko\|kldload unionfs\|mount -o union\b' \
    "$lib"/live-* "$lib/launch" "$here/live-post.sh" "$here/build-iso.sh" | grep -v '^[^:]*:[0-9]*:[[:space:]]*#'; then
  echo 'The live desktop must not use unionfs' >&2; exit 1
fi

# ---------------------------------------------------------------- rc service
eval "$(sed -n '/^daemonarchy_live_unmount()$/,/^}$/p; /^daemonarchy_live_record()$/,/^}$/p;
  /^daemonarchy_live_mount()$/,/^}$/p; /^daemonarchy_live_start()$/,/^}$/p' "$lib/live-service")"
live_flag=YES fail_mount='' fail_copy=''
kenv() { [[ $1 != -q ]] || shift; [[ $1 != daemonarchy_live ]] || echo "$live_flag"; }
mount() {
  printf 'mount %s\n' "$*" >>"$work/calls"
  [[ " $* " != *unionfs* && " $* " != *' union'* && " $* " != *'union,'* ]] || { echo 'unionfs used' >&2; exit 1; }
  [[ -z $fail_mount || ${*: -1} != "$fail_mount" ]]
}
umount() { printf 'umount %s\n' "$*" >>"$work/calls"; }
mount_unionfs() { echo 'mount_unionfs called' >&2; exit 1; }
kldload() { [[ $1 != unionfs ]] || { echo 'unionfs loaded' >&2; exit 1; }; }
tar() {
  printf 'tar %s\n' "$*" >>"$work/calls"
  [[ -z $fail_copy || " $* " != *" $fail_copy "* ]]
}
stat() { case $2 in %Lp) echo 755 ;; %u|%g) echo 0 ;; esac; }
id() { [[ $1 == -u && $2 == live ]] && echo 1000; }
chown() { :; }
reset_service() {
  rm -rf "$work/live" "$work/state" "$work/calls"
  mkdir "$work/live"
  : >"$work/calls"
  daemonarchy_live_root=$work/live daemonarchy_live_state=$work/state daemonarchy_live_user=live
  daemonarchy_live_copies='/etc /usr/local/etc /root /home'
  live_flag=YES fail_mount='' fail_copy=''
}
# Default boot: nothing happens.
reset_service
live_flag=''
daemonarchy_live_start
[[ ! -s $work/calls && ! -e $work/state ]]
# Live boot: one tmpfs for the seeds, then a populated tmpfs per tree.
reset_service
for tree in /etc /usr/local/etc /root /home; do [[ -d $tree ]] || daemonarchy_live_copies=${daemonarchy_live_copies/$tree/}; done
mkdir() { command mkdir "$@" 2>/dev/null || [[ $* == *'/var/run/user/'* ]]; }
chmod() { [[ $* == *'/var/run/user/'* ]] || command chmod "$@"; }
daemonarchy_live_start >/dev/null
[[ -f $work/state/ready && ! -e $work/state/failed ]]
grep -qx "mount -t tmpfs -o mode=0755 tmpfs $work/live" "$work/calls"
for tree in $daemonarchy_live_copies; do
  grep -qx "mount -t tmpfs -o mode=755,uid=0,gid=0 tmpfs $tree" "$work/calls"
  # Copied out before the tmpfs hides the ISO tree, copied back after.
  copy_out=$(grep -n "^tar -cf - -C $tree \.\$" "$work/calls" | cut -d: -f1)
  mounted=$(grep -n "^mount -t tmpfs .* $tree\$" "$work/calls" | cut -d: -f1)
  copy_in=$(grep -n "^tar -xpf - -C $tree\$" "$work/calls" | cut -d: -f1)
  ((copy_out < mounted && mounted < copy_in))
done
grep -q '^tar ' "$work/calls"
! grep -q '^umount' "$work/calls"
# A failed copy unwinds every mount it made, newest first, and records why.
reset_service
fail_copy=/root
[[ -d /root ]] || fail_copy=/etc
daemonarchy_live_start >/dev/null
[[ ! -e $work/state/ready && -s $work/state/failed ]]
grep '^umount' "$work/calls" | head -n 1 | grep -q -v "$work/live\$"
grep '^umount' "$work/calls" | tail -n 1 | grep -qx "umount $work/live"
# Only the four configuration and home trees may be replaced.
reset_service
daemonarchy_live_copies='/usr/local'
daemonarchy_live_start >/dev/null
grep -q 'unexpected live copy' "$work/state/failed"
unset -f mkdir chmod

# ---------------------------------------------------------------- GPU payload
make_pkg() {
  local name=$1; shift
  command mkdir -p "$work/pkgsrc/$name/boot/modules"
  for module in "$@"; do printf 'ko\n' >"$work/pkgsrc/$name/boot/modules/$module.ko"; done
  command tar -cf "$work/repo/All/$name.pkg" -C "$work/pkgsrc/$name" boot
}
command mkdir -p "$work/repo/All" "$work/share" "$work/modules" "$work/gstate" "$work/dri"
make_pkg drm-612-kmod-6.12.110.1600029_7 amdgpu i915kms radeonkms virtio_gpu_drm drmn ttm
make_pkg gpu-firmware-kmod-20260519,1
make_pkg gpu-firmware-amd-kmod-navi14-20260519.1600029 amdgpu_navi14_gpu_info_bin
make_pkg gpu-firmware-intel-kmod-skylake-20260519.1600029 i915_skl_dmc_ver1_27_bin
make_pkg nvidia-kmod-595.104.02.1600029 nvidia nvidia-modeset
make_pkg nvidia-drm-612-kmod-595.104.02.1600029 nvidia-drm
make_pkg nvidia-driver-595.104.02
make_pkg linux-nvidia-libs-595.104.02
cat >"$work/share/gpu-packages" <<'EOF'
drm-612-kmod 6.12.110.1600029_7
gpu-firmware-amd-kmod-navi14 20260519.1600029
gpu-firmware-intel-kmod-skylake 20260519.1600029
gpu-firmware-kmod 20260519,1
linux-nvidia-libs 595.104.02
nvidia-driver 595.104.02
nvidia-drm-612-kmod 595.104.02.1600029
nvidia-kmod 595.104.02.1600029
EOF
cp "$here/overlay/usr/local/share/daemonarchy-installer/gpu-ids" "$work/share/gpu-ids"
nvidia_device=$(awk '$1 == "10de" && $5 == "nvidia-drm" { print $2; exit }' "$work/share/gpu-ids")
ln -s /dev/null "$work/dri/card0"
ln -s /dev/null "$work/dri/renderD128"

run_gpu() (
  ISO_SHARE=$work/share REPO=$work/repo LIVE_STATE=$work/gstate LIVE_MODULES=$work/modules DRI_DIR=$work/dri
  LIVE_GPU_ROOT=$work/root
  # shellcheck source=/dev/null
  source "$lib/live-gpu"
  pciconf() { printf '%s\n' "$pci"; }
  tar() { command tar -xf "$2" -C "$4" --wildcards 'boot/modules/*'; }
  kldxref() { echo "kldxref $*" >>"$work/gcalls"; }
  sysctl() {
    case $* in
      '-n kern.module_path') echo '/boot/kernel;/boot/modules' ;;
      kern.module_path=*) echo "sysctl $*" >>"$work/gcalls" ;;
      '-n kern.features.linux64') echo 1 ;;
    esac
  }
  kldstat() { return 1; }
  kldload() { echo "kldload $1" >>"$work/gcalls"; }
  kenv() { echo "kenv $*" >>"$work/gcalls"; }
  devinfo() { printf '%s\n' "$attached"; }
  mount() { echo "mount $*" >>"$work/gcalls"; [[ $* != *unionfs* ]]; }
  stat() { case $2 in %Lp) echo 755 ;; *) echo 0 ;; esac; }
  pkg() {
    case $1 in
      query) printf '%s\n' "${nvidia_files[@]}" ;;
      add) echo "pkg $*" >>"$work/gcalls" ;;
    esac
  }
  main
)
reset_gpu() { rm -rf "$work/modules"/* "$work/gstate"/* "$work/gcalls" "$work/root"; command mkdir -p "$work/root/usr/local/lib" "$work/root/usr/local/share"; : >"$work/gcalls"; }

# AMD Navi 14: DRM and AMD firmware only, an additive module path, no mounts.
reset_gpu
pci='vgapci0@pci0:3:0:0: class=0x030000 rev=0xc5 hdr=0x00 vendor=0x1002 device=0x7340 subvendor=0x1002 subdevice=0x0b0c'
attached='    drmn0'
run_gpu 2>"$work/err" || { cat "$work/err" >&2; exit 1; }
[[ -f $work/modules/boot/modules/amdgpu.ko && -f $work/modules/boot/modules/amdgpu_navi14_gpu_info_bin.ko ]]
[[ ! -e $work/modules/boot/modules/i915_skl_dmc_ver1_27_bin.ko && ! -e $work/modules/boot/modules/nvidia.ko ]]
grep -qx "sysctl kern.module_path=/boot/kernel;/boot/modules;$work/modules/boot/modules" "$work/gcalls"
grep -qx "kldxref $work/modules/boot/modules" "$work/gcalls"
grep -qx 'kldload amdgpu' "$work/gcalls"
! grep -q '^mount\|^pkg' "$work/gcalls"
[[ ! -s $work/gstate/desktop.env ]]
grep -qx amdgpu "$work/gstate/gpu-modules"

# A loaded driver without an attached device is not ready.
reset_gpu
attached=''
if run_gpu 2>/dev/null; then echo 'Unattached GPU accepted' >&2; exit 1; fi

# No supported display device: the session falls back.
reset_gpu
pci='vgapci0@pci0:0:2:0: class=0x030000 vendor=0x1234 device=0x1111 subvendor=0x1af4 subdevice=0x1100'
if run_gpu 2>"$work/err"; then echo 'Unsupported GPU accepted' >&2; exit 1; fi
grep -q 'no supported desktop GPU' "$work/err"

# NVIDIA: kernel payload in RAM; userspace only adds files, on -o union tmpfs.
reset_gpu
pci="vgapci0@pci0:1:0:0: class=0x030000 vendor=0x10de device=0x$nvidia_device subvendor=0x10de subdevice=0x0000"
attached='    nvidia0'
nvidia_files=(/usr/local/lib/libnvidia-test.so.1 /usr/local/share/glvnd/egl_vendor.d/10_nvidia.json)
run_gpu 2>"$work/err" || { cat "$work/err" >&2; exit 1; }
[[ -f $work/modules/boot/modules/nvidia-drm.ko && ! -e $work/modules/boot/modules/amdgpu_navi14_gpu_info_bin.ko ]]
grep -qx 'kldload linux' "$work/gcalls"
grep -qx 'kldload nvidia-drm' "$work/gcalls"
grep -qx 'kenv hw.nvidiadrm.modeset=1' "$work/gcalls"
grep -qx "mount -t tmpfs -o union,mode=755,uid=0,gid=0 tmpfs $work/root/usr/local/lib" "$work/gcalls"
grep -qx "mount -t tmpfs -o union,mode=755,uid=0,gid=0 tmpfs $work/root/usr/local/share" "$work/gcalls"
grep -q "^pkg add -q -I -M $work/repo/All/nvidia-driver-595.104.02.pkg\$" "$work/gcalls"
! grep -q 'linux-nvidia-libs' "$work/gcalls"
grep -qx 'GBM_BACKEND=nvidia-drm' "$work/gstate/desktop.env"
# A package that would replace an ISO file is refused before any mount.
reset_gpu
printf 'iso\n' >"$work/root/usr/local/lib/libnvidia-test.so.1"
if run_gpu 2>"$work/err"; then echo 'Replacing an ISO file was accepted' >&2; exit 1; fi
grep -q 'would replace ISO files: /usr/local/lib/libnvidia-test.so.1' "$work/err"
! grep -q '^mount\|^pkg add' "$work/gcalls"

# ---------------------------------------------------------------- session
command mkdir -p "$work/session/libexec" "$work/session/state"
cat >"$work/session/libexec/live-gpu" <<'EOF'
#!/bin/sh
[ "${GPU_RESULT:-ok}" = ok ] || { echo 'live-gpu: no supported desktop GPU was detected' >&2; exit 1; }
EOF
printf '#!/bin/sh\nexit 0\n' >"$work/session/seatd"
command chmod +x "$work/session/libexec/live-gpu" "$work/session/seatd"
run_session() (
  LIVE_STATE=$work/session/state ISO_LIBEXEC=$work/session/libexec SEATD_SERVICE=$work/session/seatd
  LIVE_LOG=$work/session/log LIVE_FALLBACK_PAUSE=0
  source "$lib/live-session"
  su() { echo "su $*" >>"$work/session/su"; return "${SU_RESULT:-0}"; }
  kenv() { [[ ${2:-} != daemonarchy_live_test ]] || echo "${LIVE_TEST:-}"; }
  live_session
)
reset_session() { rm -f "$work/session/state"/* "$work/session/su" "$work/session/log"; touch "$work/session/state/ready"; }
reset_session
run_session >"$work/out"
grep -qx "su -l live -c exec $work/session/libexec/live-desktop" "$work/session/su"
grep -qx Hyprland "$work/session/state/compositor"
reset_session
if SU_RESULT=1 run_session >"$work/out"; then echo 'Compositor failure not reported' >&2; exit 1; fi
grep -q 'compositor exited with status 1' "$work/out"
grep -q 'Starting the text installer instead. No disk has been changed.' "$work/out"
reset_session
if GPU_RESULT=fail run_session >"$work/out"; then echo 'GPU failure not reported' >&2; exit 1; fi
grep -q 'could not start: no supported desktop GPU' "$work/out"
[[ ! -e $work/session/su ]]
reset_session
LIVE_TEST=compositor-failure run_session >/dev/null
grep -qx false "$work/session/state/compositor"
reset_session
echo 'Cannot mount a tmpfs on /etc.' >"$work/session/state/failed"
if run_session >"$work/out"; then echo 'Preparation failure not reported' >&2; exit 1; fi
grep -q 'could not start: Cannot mount a tmpfs on /etc.' "$work/out"
rm -f "$work/session/state/ready" "$work/session/state/failed"
if run_session >"$work/out"; then echo 'Missing preparation accepted' >&2; exit 1; fi

# The compositor selection the session writes is the only one the user side runs.
command mkdir -p "$work/desktop/run"
printf 'false\n' >"$work/desktop/compositor"
printf 'GBM_BACKEND=nvidia-drm\nLD_PRELOAD=/tmp/evil.so\n' >"$work/desktop/desktop.env"
if LIVE_STATE=$work/desktop sh -c "
  id() { echo 1000; }
  sed 's|/var/run/user/|$work/desktop/run/|' '$lib/live-desktop' >'$work/desktop/script'
  command mkdir -p '$work/desktop/run/1000'
  . '$work/desktop/script'"; then
  echo 'Forced compositor failure exited 0' >&2; exit 1
fi
printf 'nonsense\n' >"$work/desktop/compositor"
if LIVE_STATE=$work/desktop sh "$work/desktop/script" 2>/dev/null; then echo 'Unknown compositor ran' >&2; exit 1; fi
grep -q 'GBM_BACKEND|__GLX_VENDOR_LIBRARY_NAME) export' "$lib/live-desktop"

# ---------------------------------------------------------------- image wiring
post=$here/live-post.sh
grep -qx 'daemonarchy_live_media="YES"' "$post"
grep -qx 'daemonarchy_live_enable="YES"' "$post"
grep -qx 'dumpdev="NO"' "$post"
grep -qx 'zfs_enable="NO"' "$post"
! grep -q 'swapon\|_swap=\|zpool import' "$post" "$lib"/live-*
grep -q 'install -m 0555 "$world/usr/local/libexec/daemonarchy-installer/live-service" "$world/etc/rc.d/daemonarchy_live"' "$post"
grep -q "live ALL=(root) NOPASSWD: /usr/local/libexec/daemonarchy-installer/live-backend" "$post"
# The live session runs before, and always falls through to, the text installer.
profile=$(sed -n '/^# Start the Daemonarchy installer once/,/^EOF$/p' "$post")
[[ $(grep -n 'live-session' <<<"$profile" | cut -d: -f1) -lt $(grep -n 'exec /usr/local/libexec/daemonarchy-installer/launch' <<<"$profile" | cut -d: -f1) ]]
! grep -q 'exec /usr/local/libexec/daemonarchy-installer/live-session' <<<"$profile"
# The text installer default is unchanged, and the live fallback never starts
# an unattended CIDATA installation.
grep -q '^if \[\[ ${DAEMONARCHY_LIVE:-} != 1 \]\] && find_cidata; then' "$lib/launch"
grep -q 'hyprland seatd dbus sudo mesa-dri foot dejavu gtk3' "$here/build-iso.sh"
grep -q 'sh "$here/scripts/check-image-size.sh" "$iso" "$iso.xz"' "$here/build-iso.sh"
# The configurator still runs its screens when executed, and only defines them when sourced.
grep -q '^  configurator_main$' "$lib/configurator"
echo 'PASS: live service, GPU payload, session fallback, no unionfs and image wiring'
