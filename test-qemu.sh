#!/bin/sh

# Install-test a Daemonarchy ISO under QEMU, for hosts without bhyve (Linux,
# macOS, or a non-x86 machine, where the x86 guest is emulated; expect two to
# three hours there). Needs qemu-system-x86_64, x86 OVMF firmware, mkfs.fat
# and mtools, and an OpenSSH client; no root.
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

ISO=$(realpath "${1:?usage: test-qemu.sh daemonarchy.iso}")
WORK=${WORK:-$PWD/daemonarchy-qemu}
OVMF=${OVMF:-/usr/share/ovmf/OVMF.fd}
SSH_PORT=${SSH_PORT:-2222}
PASSWORD=daemonarchy

# Emulated guests get a CPU model without AVX: QEMU's emulation of AVX2 has
# faulted inside ZFS's SHA-256 routines. With KVM, use the host's CPU.
if [ -w /dev/kvm ] && [ "$(uname -m)" = x86_64 ]; then
	accel="-accel kvm -cpu host"
else
	accel="-accel tcg,thread=multi -cpu Westmere"
fi

mkdir -p "$WORK"
cd "$WORK"
rm -f disk.img cidata.img install.log boot.log qemu.pid
truncate -s 40G disk.img

cat >daemonarchy-install.conf <<EOF
disk=vtbd0
encrypt_installation=false
keyboard=us
username=tester
password=$PASSWORD
full_name="Daemonarchy Test"
email_address=test@example.com
hostname=daemonarchy-test
timezone=America/Los_Angeles
ssh_enable=true
EOF
mkfs.fat -C -F 16 -n CIDATA cidata.img 32768 >/dev/null
mcopy -i cidata.img daemonarchy-install.conf ::/

vm() {
	log=$1
	shift
	# shellcheck disable=SC2086
	qemu-system-x86_64 -machine q35 $accel -smp 4 -m 4G \
		-bios "$OVMF" -display none -no-reboot -monitor none \
		-serial "file:$log" -daemonize -pidfile qemu.pid \
		-drive file=disk.img,if=virtio,format=raw,cache=unsafe "$@"
	pid=$(cat qemu.pid)
	while kill -0 "$pid" 2>/dev/null; do
		sleep 5
		if [ "$log" = install.log ] && grep -aq 'FAILED\|panic:' install.log; then
			kill "$pid"
			echo "the install failed; see $WORK/install.log" >&2
			exit 1
		fi
	done
}

echo "==> Installing from $ISO (log: $WORK/install.log)"
start=$(date +%s)
vm install.log \
	-device ahci,id=ahci0 \
	-drive "file=$ISO,if=none,id=cd,media=cdrom,readonly=on" -device ide-cd,drive=cd,bus=ahci0.0,bootindex=1 \
	-drive file=cidata.img,if=none,id=ci,format=raw -device ide-hd,drive=ci,bus=ahci0.1 \
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
until guest true 2>/dev/null; do
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
check "/bin/bash runs bash" "/bin/bash -c true && test \$(readlink /bin/bash) = /usr/local/bin/bash"
check "no broken FreeBSD repository entry" "! grep -q '^FreeBSD:' /usr/local/etc/pkg/repos/Daemonarchy.conf"
check "updates from the signed Daemonarchy repository" "test -s /usr/local/etc/pkg/keys/daemonarchy.pub && as_root pkg update -f -r Daemonarchy && pkg rquery -r Daemonarchy %n omarchy | grep -qx omarchy"
check "Daemonarchy defaults staged" "test -d /usr/local/share/omarchy/skel.d/daemonarchy"
exit \$failures
EOF
guest "echo $PASSWORD | sudo -S -p '' shutdown -p now" >/dev/null 2>&1 || true
wait "$booter" 2>/dev/null || true
if [ "$status" -ne 0 ]; then
	echo "$status check(s) failed" >&2
	exit 1
fi
echo "==> All checks passed"
