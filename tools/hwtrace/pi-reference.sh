#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Read-only Linux baseline; do not change EEPROM, boot files or installed OS.
# Raw results are private: device-tree/boot arguments can identify the machine.
set -eu
# Use the installed OS tools rather than shell aliases or user PATH shims.
PATH=/usr/sbin:/usr/bin:/sbin:/bin:/opt/vc/bin
export PATH
umask 077
out=${1:?usage: pi-reference.sh NEW-OUTPUT-DIRECTORY}
[ ! -e "$out" ] || { echo 'output already exists' >&2; exit 1; }
[ "$(uname -s)" = Linux ] || { echo 'run on the Pi Linux reference' >&2; exit 1; }
mkdir -p "$out"
probe() {
    name=$1; shift
    printf 'start %s\n' "$name" >>"$out/capture.log"
    if timeout -k 2 20 "$@" >"$out/$name.txt" 2>&1; then result=0; else result=$?; fi
    printf 'finish %s status=%s\n' "$name" "$result" >>"$out/capture.log"
}
probe system uname -a
probe os cat /etc/os-release
probe userspace-bits getconf LONG_BIT
probe userspace-architecture dpkg --print-architecture
probe libc getconf GNU_LIBC_VERSION
probe page-size getconf PAGESIZE
probe model cat /sys/firmware/devicetree/base/model
probe compatible cat /sys/firmware/devicetree/base/compatible
probe board-revision awk '/^Revision[[:space:]]*:/ { print }' /proc/cpuinfo
probe cpu lscpu
probe memory cat /proc/meminfo
probe command-line cat /proc/cmdline
probe block lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS,MODEL,TRAN
probe pci lspci -nnk
probe usb lsusb -t
probe drivers lsmod
probe kernel dmesg
probe graphics sh -c 'for p in /sys/class/drm/card*-*/status; do [ ! -f "$p" ] || { echo "$p"; cat "$p"; }; done'
probe firmware vcgencmd version
probe throttled vcgencmd get_throttled
probe eeprom rpi-eeprom-update
probe boot-config sh -c 'for p in /boot/firmware/config.txt /boot/firmware/cmdline.txt /boot/config.txt /boot/cmdline.txt; do [ ! -f "$p" ] || { echo "$p"; cat "$p"; }; done'
probe package-versions dpkg-query -W -f '${binary:Package}\t${db:Status-Abbrev}\t${Version}\t${Architecture}\n' 'linux-image*' 'raspberrypi*' 'raspi*' 'firmware*'
probe active-kernel-package dpkg-query -W -f '${binary:Package}\t${db:Status-Abbrev}\t${Version}\t${Architecture}\n' "linux-image-$(uname -r)"
probe kernel-source dpkg-query -W -f '${binary:Package}\t${db:Status-Abbrev}\t${source:Package}\t${source:Version}\n' 'linux-image*'
probe kernel-config sh -c 'if [ -r /proc/config.gz ]; then zcat /proc/config.gz; elif [ -r "/boot/config-$(uname -r)" ]; then cat "/boot/config-$(uname -r)"; else exit 69; fi'
if [ -r /sys/firmware/fdt ]; then
    cp /sys/firmware/fdt "$out/firmware.dtb"
fi
probe boot-hashes sh -c 'for p in /boot/firmware/*.dtb /boot/firmware/kernel*.img /boot/*.dtb /boot/vmlinuz-*; do [ ! -f "$p" ] || sha256sum "$p"; done'
date -u >"$out/completed.txt"
echo "Reference captured in $out; functional network/display/DMA tests remain separate."
