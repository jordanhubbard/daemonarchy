#!/usr/bin/env bash
# Variables below are read by the service function loaded dynamically.
# shellcheck disable=SC2034
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Exercise the service function without loading a real kernel module. Redirect
# only its state/log paths; native rc ordering is checked separately.
eval "$(sed -n '/^daemonarchy_graphics_start()$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/graphics-service" |
  sed -e "s|ready=/var/run/daemonarchy-graphics.ready|ready=$work/ready|" \
      -e "s|log=/var/log/daemonarchy-graphics.log|log=$work/log|" \
      -e "s|/dev/dri/|$work/dri/|g" \
      -e 's|/usr/sbin/devinfo|devinfo|g')"
kenv() { [[ $1 != -q ]] || shift; [[ $1 != boot_safe || $safe != YES ]] || echo YES; }
checkyesno() { [[ ${!1} == YES ]]; }
service() { [[ $ssh_ready == YES ]]; }
kldstat() { [[ $already_loaded == YES ]]; }
kldload() { echo "$1" >>"$work/loaded"; [[ $fail_module != "$1" ]]; }
devinfo() { printf '%s\n' "$attached_devices"; [[ $devinfo_ok == YES ]]; }
reset_case() {
  : >"$work/loaded"
  rm -rf "$work/dri"
  mkdir "$work/dri"
  # Symlinks to an actual character device exercise test -c portably, without
  # privileged mknod or a GPU. Regular files must never satisfy the guard.
  ln -s /dev/null "$work/dri/card0"
  ln -s /dev/null "$work/dri/renderD128"
  safe=NO ssh_ready=YES sddm_enable=YES sshd_enable=YES fail_module=''
  already_loaded=NO devinfo_ok=YES attached_devices='    nvidia0'
  daemonarchy_graphics_modules='linux linux64 nvidia-drm'
}
reset_case
daemonarchy_graphics_start
printf 'linux\nlinux64\nnvidia-drm\n' >"$work/expected"
cmp "$work/expected" "$work/loaded"
[[ -f $work/ready ]]
reset_case
daemonarchy_graphics_modules=virtio_gpu_drm
attached_devices='    virtio_gpu_drm0'
daemonarchy_graphics_start
grep -qx virtio_gpu_drm "$work/loaded"
[[ -f $work/ready ]]
for module in amdgpu radeonkms i915kms; do
  reset_case
  daemonarchy_graphics_modules=$module
  attached_devices='    drmn0'
  daemonarchy_graphics_start
  [[ -f $work/ready ]]
done
# Hybrid machines require both driver families to have attached devices.
reset_case
daemonarchy_graphics_modules='linux linux64 i915kms nvidia-drm'
attached_devices=$'    drmn0\n    nvidia0'
daemonarchy_graphics_start
[[ -f $work/ready ]]
# BIOS/no-driver and Linux ABI-only paths need no DRM device inventory.
for modules in '' 'linux linux64'; do
  reset_case
  daemonarchy_graphics_modules=$modules
  devinfo_ok=NO attached_devices=''
  rm -rf "$work/dri"
  daemonarchy_graphics_start
  [[ -f $work/ready ]]
done
for disabled in safe sddm ssh; do
  reset_case
  case $disabled in safe) safe=YES ;; sddm) sddm_enable=NO ;; ssh) ssh_ready=NO ;; esac
  if [[ $disabled == ssh ]]; then
    if daemonarchy_graphics_start; then echo 'Graphics started without requested SSH' >&2; exit 1; fi
  else
    daemonarchy_graphics_start
  fi
  [[ ! -s $work/loaded && ! -e $work/ready ]]
done
reset_case
fail_module=nvidia-drm
if daemonarchy_graphics_start; then echo 'Failed driver marked ready' >&2; exit 1; fi
[[ ! -e $work/ready ]]
reset_case
daemonarchy_graphics_modules=unreviewed
if daemonarchy_graphics_start; then echo 'Unknown module accepted' >&2; exit 1; fi
[[ ! -s $work/loaded && ! -e $work/ready ]]
for failure in absent disabled suspended wrong-family devinfo card render regular; do
  reset_case
  daemonarchy_graphics_modules=amdgpu
  attached_devices='    drmn0'
  # Reproduce the Mac failure: kldstat succeeds, kldload is never retried,
  # card/render nodes exist, but the failed drmn attach is absent in devinfo.
  already_loaded=YES
  touch "$work/ready"
  case $failure in
    absent) attached_devices='    vgapci0' ;;
    disabled) attached_devices='    drmn0 (disabled)' ;;
    suspended) attached_devices='    drmn0 (suspended)' ;;
    wrong-family) attached_devices='    nvidia0' ;;
    devinfo) devinfo_ok=NO ;;
    card) rm "$work/dri/card0" ;;
    render) rm "$work/dri/renderD128" ;;
    regular) rm "$work/dri/card0"; touch "$work/dri/card0" ;;
  esac
  if daemonarchy_graphics_start; then echo "Unready graphics accepted: $failure" >&2; exit 1; fi
  [[ ! -s $work/loaded && ! -e $work/ready ]]
done
grep -q 'Missing DRM card/render character devices' "$work/log"
grep -q 'No attached active drmn device' "$work/log"
echo 'PASS: SSH/recovery ordering and DRM attachment/device prerequisites, including failed attach with surviving nodes'
