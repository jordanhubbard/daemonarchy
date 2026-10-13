#!/usr/local/bin/bash
# Native destructive tests restricted to the md device allocated by this file.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
work=$(mktemp -d)
disk='' pool='' geli_device='' mounted=false
cleanup() {
  $mounted && umount "$work/target/boot/efi"
  [[ -z $pool ]] || zpool export "$pool"
  [[ -z $geli_device ]] || geli detach "$geli_device"
  [[ -z $disk ]] || mdconfig -d -u "${disk#md}"
  rm -rf "$work"
}
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
# Firmware is a validation input. The transaction tests can also run on a BIOS
# build worker; this override does not claim that it booted in UEFI mode.
firmware=UEFI
sysctl() {
  if [[ $* == '-n machdep.bootmethod' ]]; then echo "$firmware"; else command sysctl "$@"; fi
}
reject_without_writes() {
  local before after
  before=$(disk_fingerprint "$disk")
  if apply_install_layout; then fail 'unsafe plan was accepted'; fi
  after=$(disk_fingerprint "$disk")
  [[ $before == "$after" ]] || fail 'rejected plan changed the partition table'
}
mkdir -p "$work/target/boot/efi"
printf 'test loader\n' >"$work/target/boot/loader.efi"
for encrypted in false true; do
for sectors in 512 4096; do
  for install_mode in partition free_space; do
    disk=$(mdconfig -a -t swap -s 32g -S "$sectors")
    [[ $disk =~ ^md[0-9]+$ ]] || fail 'unexpected md device'
    gpart create -s gpt "$disk"
    gpart add -i 1 -t efi -a 1m -s 260m -l "dmtest-efi-$$" "$disk"
    gpart add -i 2 -t ms-reserved -a 1m -s 16m "$disk"
    gpart add -i 3 -t ms-basic-data -a 1m -s 64m -l Windows "$disk"
    gpart add -i 4 -t ms-recovery -a 1m -s 32m "$disk"
    [[ $install_mode != partition ]] || gpart add -i 5 -t linux-data -a 1m -s 21g -l ReplaceMe "$disk"
    newfs_msdos -F 32 -c 1 "/dev/${disk}p1" >/dev/null
    mount -t msdosfs "/dev/${disk}p1" "$work/target/boot/efi"
    mounted=true
    mkdir -p "$work/target/boot/efi/EFI/"{Microsoft/Boot,BOOT,FreeBSD}
    for path in Microsoft/Boot/bootmgfw.efi BOOT/BOOTX64.EFI FreeBSD/loader.efi; do
      printf 'Preserve %s exactly\n' "$path" >"$work/target/boot/efi/EFI/$path"
    done
    umount "$work/target/boot/efi"
    mounted=false
    printf 'Windows data must survive\n' | dd bs="$sectors" count=1 conv=sync status=none | dd of="/dev/${disk}p3" bs="$sectors" count=1 conv=notrunc status=none
    windows_before=$(sha256 -q "/dev/${disk}p3")
    recovery_before=$(sha256 -q "/dev/${disk}p4")
    table_before=$(partition_rows "$disk" | awk '$1 <= 4')
    uuid_before=$(partition_uuid "$disk" 1)
    uuids_before=$(for i in 1 2 3 4; do partition_uuid "$disk" "$i"; done)
    target_uuid_before=$(partition_uuid "$disk" 5)
    disk_snapshot=$(disk_fingerprint "$disk")
    efi_index=1 partition_index=5 install_size_mib=21504
    free_start=$(free_rows "$disk" | awk -v s="$sectors" '$2*s >= 22*1024*1024*1024 { print $1; exit }')

    # A BIOS boot, stale selection, active partition, or invalid ESP must fail
    # before gpart modifies the table or creates a new partition.
    firmware=BIOS
    reject_without_writes
    firmware=UEFI
    saved_snapshot=$disk_snapshot
    disk_snapshot=stale
    reject_without_writes
    disk_snapshot=$saved_snapshot
    efi_index=3
    reject_without_writes
    efi_index=1
    mount -t msdosfs "/dev/gpt/dmtest-efi-$$" "$work/target/boot/efi"
    mounted=true
    reject_without_writes
    umount "$work/target/boot/efi"
    mounted=false
    if [[ $install_mode == partition ]]; then
      for partition_index in 1 2 3 4 999; do reject_without_writes; done
      partition_index=5
    else
      saved_start=$free_start
      free_start=2048
      reject_without_writes
      free_start=$saved_start
      install_size_mib=999999
      reject_without_writes
      install_size_mib=1
      reject_without_writes
      install_size_mib=21504
    fi

    apply_install_layout
    [[ $(partition_field "$disk" "$partition_index" 2) == freebsd-zfs ]] || fail 'wrong target type'
    [[ $(partition_rows "$disk" | awk '$1 <= 4') == "$table_before" ]] || fail 'unselected partitions changed'
    [[ $(partition_uuid "$disk" 1) == "$uuid_before" ]] || fail 'EFI UUID changed'
    [[ $(for i in 1 2 3 4; do partition_uuid "$disk" "$i"; done) == "$uuids_before" ]] || fail 'unselected partition UUIDs changed'
    if [[ $install_mode == partition ]]; then
      [[ $(partition_uuid "$disk" 5) == "$target_uuid_before" ]] || fail 'selected partition UUID changed'
    fi
    [[ -z $swap_dev ]] || fail 'borrowed another partition for swap' 
    if $encrypted; then
      (umask 077; printf 'disposable-test-key' >"$work/key")
      geli init -b -g -e AES-XTS -l 256 -s 4096 -J "$work/key" "$zfs_dev"
      geli attach -j "$work/key" "$zfs_dev"
      geli_device="$zfs_dev.eli"
      zfs_dev=$geli_device
    fi
    pool="dmshared$$"
    zpool create -f -o cachefile=none -O mountpoint=none "$pool" "$zfs_dev"
    mount -t msdosfs "$efi_dev" "$work/target/boot/efi"
    mounted=true
    write_efi_loader "$work/target" "$pool" true
    cmp "$work/target/boot/loader.efi" "$efi_loader"
    for path in Microsoft/Boot/bootmgfw.efi BOOT/BOOTX64.EFI FreeBSD/loader.efi; do
      printf 'Preserve %s exactly\n' "$path" | cmp - "$work/target/boot/efi/EFI/$path"
    done
    umount "$work/target/boot/efi"
    mounted=false
    [[ $(sha256 -q "/dev/${disk}p3") == "$windows_before" ]] || fail 'Windows data changed'
    [[ $(sha256 -q "/dev/${disk}p4") == "$recovery_before" ]] || fail 'recovery data changed'
    zpool export "$pool"
    pool=''
    [[ -z $geli_device ]] || geli detach "$geli_device"
    geli_device=''
    mdconfig -d -u "${disk#md}"
    disk=''
    echo "PASS: $install_mode on $sectors-byte sectors, encrypted=$encrypted; Windows/recovery data and EFI loaders preserved"
  done
done
done
