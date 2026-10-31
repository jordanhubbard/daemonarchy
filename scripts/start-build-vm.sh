#!/bin/sh
# Boot the amd64 build VM (mudflap) from its installed disk, as boot-worker.py did.
set -eu
B=/home/jkh/daemonarchy-builder-vm
if pgrep -f 'qemu-system-x86_64.*recovery-virtio-20261031T004143Z/disk.img' >/dev/null; then
  echo 'the build VM is already running' >&2
  exit 0
fi
case_dir=$B/boot-$(date -u +%Y%m%dT%H%M%SZ)
mkdir "$case_dir"
cp "$(cat $B/active-boot)/OVMF_VARS.fd" "$case_dir/OVMF_VARS.fd"
printf '%s\n' "$case_dir" > $B/active-boot
cd "$case_dir"
nohup qemu-system-x86_64 -machine q35,smm=on -accel kvm -cpu host -smp 16 -m 48G \
  -global driver=cfi.pflash01,property=secure,value=on \
  -drive if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd \
  -drive if=pflash,format=raw,unit=1,file=OVMF_VARS.fd \
  -display none -monitor none -qmp unix:qmp.sock,server=on,wait=off -serial file:boot.log \
  -drive file=$B/recovery-virtio-20261031T004143Z/disk.img,if=virtio,format=raw \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:22461-:22 -device virtio-net-pci,netdev=n0 \
  > qemu.log 2>&1 < /dev/null &
echo $! > qemu.pid
echo "started $case_dir"
