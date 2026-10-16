#!/bin/sh

# Install-test a Daemonarchy ISO under QEMU, for hosts without bhyve (Linux,
# macOS, or a non-x86 machine, where the x86 guest is emulated; expect two to
# three hours there). Needs qemu-system-x86_64, x86 OVMF firmware, an
# OpenSSH client, and either mkfs.fat/mtools or xorriso for CIDATA; no root.
#
#   1. boot the ISO with a blank 40 GB disk and a CIDATA drive holding an
#      unattended daemonarchy-install.conf; the installer powers off when done
#   2. boot the installed disk, log in over SSH as the test user, and check
#      what a VM without a GPU cannot show on screen: the account and its
#      groups, SDDM's user, session, and theme, and the network services
#
#   test-qemu.sh daemonarchy.iso
#
# The guest's serial console goes to $WORK/install.log and $WORK/boot.log.

set -eu

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
INSTALL_PORTS=${INSTALL_PORTS:-false}
INSTALL_SRC=${INSTALL_SRC:-false}
ENCRYPT_INSTALLATION=${ENCRYPT_INSTALLATION:-false}
for selected in "$INSTALL_PORTS" "$INSTALL_SRC" "$ENCRYPT_INSTALLATION"; do
	case "$selected" in true|false) ;; *) echo 'Installation selections must be true or false' >&2; exit 1 ;; esac
done
if [ "$ENCRYPT_INSTALLATION" = true ]; then
	command -v python3 >/dev/null || { echo 'Encrypted boot checks need host python3 for QMP input' >&2; exit 1; }
fi
ISO=$(realpath "${1:?usage: test-qemu.sh daemonarchy.iso}")
WORK=${WORK:-$PWD/daemonarchy-qemu}
OVMF=${OVMF:-/usr/share/ovmf/OVMF.fd}
BOOT_MODE=${BOOT_MODE:-uefi}
SSH_PORT=${SSH_PORT:-2222}
PASSWORD=daemonarchy
VM_TIMEOUT=${VM_TIMEOUT:-7200}
case "$VM_TIMEOUT" in ''|*[!0-9]*) echo 'VM_TIMEOUT must be positive seconds' >&2; exit 1 ;; esac
[ "$VM_TIMEOUT" -gt 0 ] || { echo 'VM_TIMEOUT must be positive seconds' >&2; exit 1; }

case "$BOOT_MODE" in
	uefi) [ -r "$OVMF" ] || { echo "UEFI firmware not found: $OVMF" >&2; exit 1; } ;;
	bios) ;; # QEMU's default SeaBIOS firmware.
	*) echo "BOOT_MODE must be uefi or bios" >&2; exit 1 ;;
esac

# Emulated guests get a CPU model without AVX: QEMU's emulation of AVX2 has
# faulted inside ZFS's SHA-256 routines. With KVM, use the host's CPU.
if [ -w /dev/kvm ] && [ "$(uname -m)" = x86_64 ]; then
	accel="-accel kvm -cpu host"
else
	accel="-accel tcg,thread=multi -cpu Westmere"
fi

mkdir -p "$WORK"
cd "$WORK"
WORK=$PWD
[ ! -e disk.img ] && [ ! -e qemu.pid ] || {
	echo "Use a fresh WORK directory; existing test evidence is preserved: $WORK" >&2
	exit 1
}
cleanup() {
	if [ -s qemu.pid ]; then
		read -r cleanup_pid <qemu.pid
		kill "$cleanup_pid" 2>/dev/null || true
	fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
truncate -s 40G disk.img

cat >daemonarchy-install.conf <<EOF
disk=vtbd0
encrypt_installation=$ENCRYPT_INSTALLATION
install_ports=$INSTALL_PORTS
install_src=$INSTALL_SRC
keyboard=us
username=tester
password=$PASSWORD
full_name="Daemonarchy Test"
email_address=test@example.com
hostname=daemonarchy-test
timezone=America/Los_Angeles
ssh_enable=true
EOF
if command -v mkfs.fat >/dev/null && command -v mcopy >/dev/null; then
	cidata_drive=file=cidata.img,if=none,id=ci,format=raw
	cidata_device=ide-hd
	mkfs.fat -C -F 16 -n CIDATA cidata.img 32768 >/dev/null
	mcopy -i cidata.img daemonarchy-install.conf ::/
elif command -v xorriso >/dev/null; then
	cidata_drive=file=cidata.img,if=none,id=ci,format=raw,media=cdrom,readonly=on
	cidata_device=ide-cd
	mkdir cidata
	cp daemonarchy-install.conf cidata/
	xorriso -as mkisofs -quiet -V CIDATA -o cidata.img cidata >cidata.log 2>&1
else
	echo 'Install mkfs.fat/mtools or xorriso to create CIDATA' >&2
	exit 1
fi

vm() {
	log=$1
	shift
	if [ "$BOOT_MODE" = uefi ]; then
		set -- -bios "$OVMF" "$@"
	fi
	# shellcheck disable=SC2086
	qemu-system-x86_64 -machine q35 $accel -smp 4 -m 4G \
		-display none -no-reboot -monitor none -qmp "unix:$log.qmp.sock,server=on,wait=off" \
		-serial "file:$log" \
		-drive file=disk.img,if=virtio,format=raw,cache=unsafe "$@" >"$log.qemu" 2>&1 &
	pid=$!
	printf '%s\n' "$pid" >qemu.pid
	vm_start=$(date +%s)
	while kill -0 "$pid" 2>/dev/null; do
		sleep 5
		if [ "$(( $(date +%s) - vm_start ))" -ge "$VM_TIMEOUT" ]; then
			kill "$pid" 2>/dev/null || true
			wait "$pid" 2>/dev/null || true
			: >qemu.pid
			echo "VM timed out; see $WORK/$log" >&2
			exit 1
		fi
		if [ "$log" = install.log ] && grep -aq 'FAILED\|panic:' install.log; then
			kill "$pid"
			wait "$pid" 2>/dev/null || true
			: >qemu.pid
			echo "the install failed; see $WORK/install.log" >&2
			exit 1
		fi
	done
	vm_status=0
	wait "$pid" || vm_status=$?
	: >qemu.pid
	[ "$vm_status" -eq 0 ] || { echo "QEMU exited with status $vm_status; see $WORK/$log.qemu" >&2; return 1; }
}

echo "==> Installing from $ISO (log: $WORK/install.log)"
start=$(date +%s)
vm install.log \
	-device ahci,id=ahci0 \
	-drive "file=$ISO,if=none,id=cd,media=cdrom,readonly=on" -device ide-cd,drive=cd,bus=ahci0.0,bootindex=1 \
	-drive "$cidata_drive" -device "$cidata_device,drive=ci,bus=ahci0.1" \
	-netdev user,id=n0 -device virtio-net-pci,netdev=n0
grep -aq 'Daemonarchy is installed' install.log || { echo "the install did not finish; see $WORK/install.log" >&2; exit 1; }
echo "    installed in $(( ($(date +%s) - start) / 60 )) minutes"

echo "==> Booting the installed system (log: $WORK/boot.log)"
vm boot.log -netdev "user,id=n0,hostfwd=tcp:127.0.0.1:$SSH_PORT-:22" -device virtio-net-pci,netdev=n0 &
booter=$!

# Log in with the test user's password, without a terminal to type it into.
printf '#!/bin/sh\necho %s\n' "$PASSWORD" >askpass.sh
chmod 700 askpass.sh
guest() {
	SSH_ASKPASS=$WORK/askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY=:0 \
		ssh -p "$SSH_PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
		-o LogLevel=ERROR -o PreferredAuthentications=password,keyboard-interactive \
		-o PubkeyAuthentication=no -o ConnectTimeout=10 tester@127.0.0.1 "$@"
}
tries=0
unlocked=false
until guest true 2>/dev/null; do
	if [ "$ENCRYPT_INSTALLATION" = true ] && [ "$unlocked" = false ]; then
		if printf '%s\n' "$PASSWORD" | python3 "$SCRIPT_DIR/tests/qemu-unlock-geli.py" \
		    "$WORK/boot.log.qmp.sock" "$BOOT_MODE" "$WORK/boot.log"; then
			unlocked=true
			echo '    entered the GELI passphrase at the loader prompt'
		else
			unlock_status=$?
			[ "$unlock_status" -eq 2 ] || exit "$unlock_status"
		fi
	fi
	tries=$((tries + 1))
	[ "$tries" -lt 120 ] || { echo "no SSH login after boot; see $WORK/boot.log" >&2; exit 1; }
	sleep 5
done

echo "==> Checking the installed system"
status=0
guest 'sh -s' <<EOF || status=$?
failures=0
check() {
	if eval "\$2" >/dev/null 2>&1; then echo "    ok    \$1"; else echo "    FAIL  \$1"; failures=\$((failures + 1)); fi
}
as_root() { echo $PASSWORD | sudo -S -p "" "\$@"; }
check "sudo works for tester" "as_root true"
check "booted using $BOOT_MODE firmware" "sysctl -n machdep.bootmethod | grep -ix $BOOT_MODE"
check "BIOS boot partition present" "gpart show vtbd0 | grep -q freebsd-boot"
if [ "$ENCRYPT_INSTALLATION" = true ]; then
	check "ZFS boots from the GELI provider" "as_root zpool status -P | grep -q '/dev/vtbd0p3.eli'"
fi
for g in wheel operator video audio; do
	check "tester in \$g" "id -Gn | grep -qw \$g"
done
check "SDDM signs in as tester" "as_root grep -qx User=tester /var/lib/sddm/state.conf"
check "SDDM opens the Omarchy session" "as_root grep -qx Session=/usr/local/share/wayland-sessions/omarchy.desktop /var/lib/sddm/state.conf"
check "SDDM uses the Daemonarchy theme" "grep -qx Current=daemonarchy /usr/local/etc/sddm.conf.d/20-daemonarchy-theme.conf"
check "sddm running" "service sddm onestatus"
check "sshd enabled, no reverse DNS" "grep -q '^sshd_enable=\"YES\"' /etc/rc.conf && grep -qx 'UseDNS no' /etc/ssh/sshd_config"
check "avahi running" "service avahi-daemon onestatus"
check "mdns lookups" "grep -q '^hosts: files mdns dns' /etc/nsswitch.conf"
check "network by DHCP" "grep -q '^ifconfig_DEFAULT=\"DHCP\"' /etc/rc.conf"
check "daemonarchy installed" "pkg info -e daemonarchy && pkg info -e omarchy"
check "packaged files keep their owners" "test \$(stat -f %Sg /usr/local/libexec/dbus-daemon-launch-helper) = messagebus && test -u /usr/local/libexec/dbus-daemon-launch-helper"
check "GSettings schemas compiled" "test -s /usr/local/share/glib-2.0/schemas/gschemas.compiled && test -s /usr/local/lib/gio/modules/giomodule.cache"
check "/bin/bash runs bash" "/bin/bash -c true && test \$(readlink /bin/bash) = /usr/local/bin/bash"
check "no broken FreeBSD repository entry" "! grep -q '^FreeBSD:' /usr/local/etc/pkg/repos/Daemonarchy.conf"
check "updates from the signed Daemonarchy repository" "test -s /usr/local/etc/pkg/keys/daemonarchy.pub && as_root pkg update -f -r Daemonarchy && pkg rquery -r Daemonarchy %n omarchy | grep -qx omarchy"
check "Daemonarchy defaults staged" "test -d /usr/local/share/omarchy/skel.d/daemonarchy"
exit \$failures
EOF
guest "sh -s" <"$SCRIPT_DIR/tests/installed-desktop.sh" || status=1
guest "sh -s -- $INSTALL_PORTS $INSTALL_SRC" <"$SCRIPT_DIR/tests/installed-checkouts.sh" || status=1
guest "echo $PASSWORD | sudo -S -p '' shutdown -p now" >/dev/null 2>&1 || true
wait "$booter" 2>/dev/null || true
if [ "$status" -ne 0 ]; then
	echo "$status check(s) failed" >&2
	exit 1
fi
echo "==> All checks passed"
