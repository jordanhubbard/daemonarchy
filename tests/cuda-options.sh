#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lib=$here/overlay/usr/local/libexec/daemonarchy-installer
source "$lib/gpu-config"
source "$lib/cuda-options"
source "$lib/checkout-options"
eval "$(sed -n '/^cuda_step() {$/,/^}$/p' "$lib/configurator")"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
ISO_SHARE=$here/overlay/usr/local/share/daemonarchy-installer
pciconf() { cat "$work/pci"; }
step() { printf '%s\n' "$*"; }
say() { printf '%s\n' "$*"; }
abort() { echo "$*" >&2; exit 1; }
gum() { printf '%s\n' "$*" >>"$work/prompts"; return "$answer"; }

for hardware in intel amd nvidia mixed legacy audio unknown; do
  case $hardware in
    intel) vendor=8086 device=3e9b ;;
    amd) vendor=1002 device=7340 ;;
    nvidia|mixed) vendor=10de device=2684 ;;
    legacy) vendor=10de device=0393 ;;
    audio) vendor=10de device=2684 ;;
    unknown) vendor=1234 device=ffff ;;
  esac
  class=030000
  [[ $hardware != audio ]] || class=040300
  printf 'vgapci0: class=0x%s vendor=0x%s device=0x%s\n' "$class" "$vendor" "$device" >"$work/pci"
  [[ $hardware != mixed ]] || echo 'vgapci1: class=0x030000 vendor=0x8086 device=0x3e9b' >>"$work/pci"
  for answer in 0 1; do
    : >"$work/prompts"
    cuda_step >"$work/messages" 2>&1
    expected=false
    [[ ! -s $work/prompts ]]
    [[ $install_cuda == "$expected" ]]
    checkout_options_prepare "$work/absent"
    bytes=21474836480
    [[ $expected != true ]] || bytes=$((bytes + 16 * 1024 * 1024 * 1024))
    [[ $MIN_INSTALL_BYTES == "$bytes" ]]
    target=$work/$hardware-$answer
    mkdir -p "$target/usr/local/"{bin,sbin,share/applications,share/daemonarchy-installer}
    cuda_install_support "$target" "$ISO_SHARE" "$here/overlay"
    if [[ $expected == true ]]; then
      [[ -x $target/usr/local/bin/daemonarchy-cudalab ]]
      [[ -f $target/usr/local/share/applications/cudalab.desktop ]]
      grep -q 'system.freebsd.cudalab' "$target/usr/local/share/omarchy/vendor/omarchy-menu.jsonc"
    else
      [[ ! -e $target/usr/local/bin/daemonarchy-cudalab ]]
      [[ ! -e $target/usr/local/share/applications/cudalab.desktop ]]
      ! grep -Ei 'nvidia|cuda' "$target/usr/local/share/omarchy/vendor/omarchy-menu.jsonc"
    fi
  done
done
unset install_cuda
cuda_options_prepare
[[ $install_cuda == false ]]
install_cuda=true gpu_nvidia=false
! cuda_options_prepare
install_cuda=invalid
! cuda_options_prepare

# Preserve the opt-in in the answers passed to the installer.
eval "$(sed -n '/^write_install_conf() {$/,/^}$/p' "$lib/configurator")"
DAEMONARCHY_INSTALL_CONF=$work/answers
for selected in true false; do
  (set +u; install_cuda=$selected; write_install_conf)
  (source "$work/answers"; [[ $install_cuda == "$selected" ]])
done

# Cleanup must never touch the host or sibling targets, and children precede parents.
mount() {
  printf '%s\n' 'devfs /dev devfs rw 0 0' 'devfs /mnt/compat/linux/dev devfs rw 0 0' \
    'tmpfs /mnt/compat/linux/dev/shm tmpfs rw 0 0' '/home /mnt/compat/linux/home nullfs rw 0 0' \
    'devfs /other/compat/linux/dev devfs rw 0 0'
}
umount() { echo "$1" >>"$work/unmounted"; }
cuda_unmount_target /mnt
printf '%s\n' /mnt/compat/linux/home /mnt/compat/linux/dev/shm /mnt/compat/linux/dev >"$work/expected"
cmp "$work/expected" "$work/unmounted"
echo 'PASS: unqualified compute selection withheld, default menu, space and mount cleanup'
