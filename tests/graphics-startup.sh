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
      -e "s|log=/var/log/daemonarchy-graphics.log|log=$work/log|")"
kenv() { [[ $1 != -q ]] || shift; [[ $1 != boot_safe || $safe != YES ]] || echo YES; }
checkyesno() { [[ ${!1} == YES ]]; }
service() { [[ $ssh_ready == YES ]]; }
kldstat() { return 1; }
kldload() { echo "$1" >>"$work/loaded"; [[ $fail_module != "$1" ]]; }
reset_case() {
  : >"$work/loaded"
  safe=NO ssh_ready=YES sddm_enable=YES sshd_enable=YES fail_module=''
  daemonarchy_graphics_modules='linux linux64 nvidia-drm'
}
reset_case
daemonarchy_graphics_start
printf 'linux\nlinux64\nnvidia-drm\n' >"$work/expected"
cmp "$work/expected" "$work/loaded"
[[ -f $work/ready ]]
reset_case
daemonarchy_graphics_modules=virtio_gpu_drm
daemonarchy_graphics_start
grep -qx virtio_gpu_drm "$work/loaded"
[[ -f $work/ready ]]
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
echo 'PASS: requested SSH precedes GPU loading, recovery skips graphics, failures stay unready'
