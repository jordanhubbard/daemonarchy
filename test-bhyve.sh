#!/bin/sh

# Boot-test a Daemonarchy installer ISO under bhyve (run as root on a FreeBSD
# host with VT-x/AMD-V and the edk2-bhyve firmware package):
#
#   1. boot the ISO with a blank 40 GB disk and a CIDATA drive holding an
#      daemonarchy-install.conf, so the installer runs unattended and powers off
#   2. boot the installed disk on its own
#
# Both runs expose the guest framebuffer over VNC on 127.0.0.1:$VNC_PORT.

set -eu

ISO=${1:?usage: test-bhyve.sh daemonarchy.iso}
WORK=${WORK:-/var/tmp/daemonarchy-bhyve}
VM=${VM:-daemonarchy-test}
NIC=${NIC:-$(route -n get default | awk '/interface:/ { print $2 }')}
VNC_PORT=${VNC_PORT:-5900}
FIRMWARE=/usr/local/share/uefi-firmware/BHYVE_UEFI.fd
INSTALL_TIMEOUT=${INSTALL_TIMEOUT:-7200}

kldload -n vmm if_bridge if_tap
mkdir -p "$WORK"

# A bridge onto the host's network so the guest can reach pkg.FreeBSD.org.
if ! ifconfig "$VM-br" >/dev/null 2>&1; then
	bridge=$(ifconfig bridge create)
	ifconfig "$bridge" name "$VM-br" >/dev/null
	ifconfig "$VM-br" addm "$NIC" up
fi
if ! ifconfig "$VM-tap" >/dev/null 2>&1; then
	tap=$(ifconfig tap create)
	ifconfig "$tap" name "$VM-tap" >/dev/null
	ifconfig "$VM-br" addm "$VM-tap"
	sysctl -q net.link.tap.up_on_open=1 >/dev/null
fi

disk=$WORK/disk.img
rm -f "$disk"
truncate -s 40G "$disk"

# The guest sees the scratch disk as vtbd0 and the CIDATA drive as ada0.
mkdir -p "$WORK/cidata"
cat >"$WORK/cidata/daemonarchy-install.conf" <<'EOF'
disk=vtbd0
encrypt_installation=false
keyboard=us
username=daemon
password=daemonarchy
full_name="Daemonarchy Test"
email_address=test@example.com
hostname=daemonarchy-test
timezone=America/Los_Angeles
EOF
rm -f "$WORK/cidata.img"
makefs -t msdos -o volume_label=CIDATA -o fat_type=16 -s 32m "$WORK/cidata.img" "$WORK/cidata"

run_vm() {
	bhyvectl --destroy --vm="$VM" >/dev/null 2>&1 || true
	bhyve -c 4 -m 4G -H -A -P \
		-s 0,hostbridge \
		-s 2,virtio-blk,"$disk" \
		-s 4,virtio-net,"$VM-tap" \
		"$@" \
		-s 29,fbuf,tcp=127.0.0.1:"$VNC_PORT",w=1280,h=800 \
		-s 30,xhci,tablet \
		-s 31,lpc \
		-l bootrom,"$FIRMWARE" \
		"$VM"
}

echo "==> Installing from $ISO (VNC on 127.0.0.1:$VNC_PORT)"
start=$(date +%s)
status=0
run_vm -s 3,ahci-cd,"$ISO" -s 5,ahci-hd,"$WORK/cidata.img" &
vm_pid=$!
# Destroy the guest if the install has not finished in time.
( sleep "$INSTALL_TIMEOUT"; bhyvectl --destroy --vm="$VM" >/dev/null 2>&1 ) &
watchdog=$!
wait "$vm_pid" || status=$?
kill "$watchdog" 2>/dev/null || true
echo "    bhyve exited with $status after $(( $(date +%s) - start ))s (1 = powered off)"
[ "$status" -eq 1 ] || { echo "install did not power off cleanly" >&2; exit 1; }

echo "==> Booting the installed system (VNC on 127.0.0.1:$VNC_PORT)"
run_vm &
echo "    guest running as pid $!; stop it with: bhyvectl --destroy --vm=$VM"
