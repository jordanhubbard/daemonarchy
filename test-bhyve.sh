#!/bin/sh

# Boot-test a Daemonarchy installer ISO under bhyve (run as root on a FreeBSD
# host with VT-x/AMD-V and the edk2-bhyve firmware package):
#
#   1. boot the ISO with a blank 40 GB disk and a CIDATA drive holding an
#      daemonarchy-install.conf, so the installer runs unattended and powers off
#   2. boot the installed disk on its own
#
# Both runs expose the guest framebuffer over VNC on 127.0.0.1:$VNC_PORT.
#
# NET=nat (default) puts the guest on a private network behind pf NAT, with
# dnsmasq handing out addresses on the tap only; NET=bridge bridges the tap
# onto the host's network instead. "test-bhyve.sh --cleanup" undoes either.

set -eu

WORK=${WORK:-/var/tmp/daemonarchy-bhyve}
VM=${VM:-daemonarchy-test}
NET=${NET:-nat}
TAP=${TAP:-tapdm0}  # bhyve picks its backend from the "tap" prefix
BRIDGE=${BRIDGE:-dmbr0}
SUBNET=10.77.0
NIC=${NIC:-$(route -n get default | awk '/interface:/ { print $2 }')}
VNC_PORT=${VNC_PORT:-5900}
FIRMWARE=/usr/local/share/uefi-firmware/BHYVE_UEFI.fd
INSTALL_TIMEOUT=${INSTALL_TIMEOUT:-7200}

if [ "${1:-}" = --cleanup ]; then
	bhyvectl --destroy --vm="$VM" >/dev/null 2>&1 || true
	if [ -f "$WORK/dnsmasq.pid" ]; then
		kill "$(cat "$WORK/dnsmasq.pid")" 2>/dev/null || true
		rm -f "$WORK/dnsmasq.pid"
	fi
	if [ -f "$WORK/pf-enabled-by-test" ]; then
		pfctl -q -d 2>/dev/null || true
		rm -f "$WORK/pf-enabled-by-test"
	fi
	ifconfig "$TAP" destroy 2>/dev/null || true
	ifconfig "$BRIDGE" destroy 2>/dev/null || true
	exit 0
fi

ISO=${1:?usage: test-bhyve.sh daemonarchy.iso | --cleanup}

kldload -n vmm if_bridge if_tap nmdm
mkdir -p "$WORK"
sysctl -q net.link.tap.up_on_open=1 >/dev/null

if ! ifconfig "$TAP" >/dev/null 2>&1; then
	tap=$(ifconfig tap create)
	ifconfig "$tap" name "$TAP" >/dev/null
fi

if [ "$NET" = bridge ]; then
	# Bridge onto the host's network so the guest can reach pkg.FreeBSD.org.
	if ! ifconfig "$BRIDGE" >/dev/null 2>&1; then
		bridge=$(ifconfig bridge create)
		ifconfig "$bridge" name "$BRIDGE" >/dev/null
		ifconfig "$BRIDGE" addm "$NIC" up
	fi
	ifconfig "$BRIDGE" addm "$TAP" 2>/dev/null || true
else
	# A private network behind NAT, leaving the host's own interface alone.
	ifconfig "$TAP" inet "$SUBNET.1/24" up
	sysctl -q net.inet.ip.forwarding=1 >/dev/null
	kldload -n pf
	if ! pfctl -s info 2>/dev/null | grep -q "Status: Enabled"; then
		printf 'nat on %s inet from %s.0/24 to any -> (%s)\npass all\n' "$NIC" "$SUBNET" "$NIC" | pfctl -q -f -
		pfctl -q -e
		touch "$WORK/pf-enabled-by-test"
	else
		echo "pf is already enabled; add: nat on $NIC inet from $SUBNET.0/24 to any -> ($NIC)" >&2
	fi
	if [ ! -f "$WORK/dnsmasq.pid" ] || ! kill -0 "$(cat "$WORK/dnsmasq.pid")" 2>/dev/null; then
		dnsmasq --interface="$TAP" --bind-interfaces --port=0 \
			--dhcp-range="$SUBNET.10,$SUBNET.50,1h" \
			--dhcp-option=option:dns-server,1.1.1.1 \
			--pid-file="$WORK/dnsmasq.pid"
	fi
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
username=tester
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
	# Closing the tap drops its address; give it back before every run.
	[ "$NET" = bridge ] || ifconfig "$TAP" inet "$SUBNET.1/24" up
	bhyve -c 4 -m 4G -H -A -P \
		-s 0,hostbridge \
		-s 2,virtio-blk,"$disk" \
		-s 4,virtio-net,"$TAP" \
		"$@" \
		-s 29,fbuf,tcp=127.0.0.1:"$VNC_PORT",w=1280,h=800 \
		-s 30,xhci,tablet \
		-s 31,lpc \
		-l com1,/dev/nmdm-dm-A \
		-l bootrom,"$FIRMWARE" \
		"$VM"
}

# The guest's first serial port, where an unattended install copies its log.
cat /dev/nmdm-dm-B >"$WORK/serial.log" 2>/dev/null &
serial_reader=$!
trap 'kill "$serial_reader" 2>/dev/null || true' EXIT

echo "==> Installing from $ISO (VNC on 127.0.0.1:$VNC_PORT; log in $WORK/serial.log)"
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
