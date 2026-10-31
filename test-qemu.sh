#!/bin/sh

# Install-test a Daemonarchy ISO under QEMU, for hosts without bhyve (Linux,
# macOS, or a non-x86 machine, where the x86 guest is emulated; expect two to
# three hours there). Needs qemu-system-x86_64, x86 OVMF firmware, an
# OpenSSH client (ARCH=aarch64 uses qemu-system-aarch64 and AArch64 edk2
# firmware instead, always UEFI, with the 'virt' machine), and either mkfs.fat/mtools or xorriso for CIDATA; no root.
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
ARCH=${ARCH:-x86_64}
case "$ARCH" in
	x86_64) OVMF=${OVMF:-/usr/share/ovmf/OVMF.fd} ;;
	aarch64)
		# Homebrew (Apple silicon), then Debian/Ubuntu's qemu-efi-aarch64.
		for fw in /opt/homebrew/share/qemu/edk2-aarch64-code.fd /usr/share/qemu-efi-aarch64/QEMU_EFI.fd; do
			[ -r "$fw" ] && break
		done
		OVMF=${OVMF:-$fw} ;;
	*) echo 'ARCH must be x86_64 or aarch64' >&2; exit 1 ;;
esac
UEFI_CODE=${UEFI_CODE:-}
UEFI_VARS_TEMPLATE=${UEFI_VARS_TEMPLATE:-}
UEFI_SECUREBOOT=${UEFI_SECUREBOOT:-false}
VIRGL_RENDER_NODE=${VIRGL_RENDER_NODE:-}
VNC_LISTEN=${VNC_LISTEN:-127.0.0.1:11}
BOOT_MODE=${BOOT_MODE:-uefi}
SSH_PORT=${SSH_PORT:-2222}
# An emulated Intel HDA codec with no host audio backend, so the guest's sound path is exercised
# (snd_hda must attach and /dev/sndstat list a pcm device). aarch64 only by default.
SOUND_TEST=${SOUND_TEST:-$([ "${ARCH:-x86_64}" = aarch64 ] && echo yes || echo no)}
case "$SOUND_TEST" in yes|no) ;; *) echo 'SOUND_TEST must be yes or no' >&2; exit 1 ;; esac
EXPECTED_PACKAGE_REPOSITORY_TAG=${EXPECTED_PACKAGE_REPOSITORY_TAG:-packages-16-amd64}
case "$EXPECTED_PACKAGE_REPOSITORY_TAG" in
    ''|*[!A-Za-z0-9._-]*) echo 'Invalid expected package repository tag' >&2; exit 1 ;;
esac
MEM=${MEM:-4G}
PASSWORD=daemonarchy
VM_TIMEOUT=${VM_TIMEOUT:-7200}
case "$VM_TIMEOUT" in ''|*[!0-9]*) echo 'VM_TIMEOUT must be positive seconds' >&2; exit 1 ;; esac
[ "$VM_TIMEOUT" -gt 0 ] || { echo 'VM_TIMEOUT must be positive seconds' >&2; exit 1; }

case "$BOOT_MODE" in
	uefi)
		if [ -n "$UEFI_CODE$UEFI_VARS_TEMPLATE" ]; then
			[ -r "$UEFI_CODE" ] && [ -r "$UEFI_VARS_TEMPLATE" ] || {
				echo 'UEFI_CODE and UEFI_VARS_TEMPLATE must both name readable pflash inputs' >&2; exit 1;
			}
		else
			[ -r "$OVMF" ] || { echo "UEFI firmware not found: $OVMF" >&2; exit 1; }
		fi ;;
	bios)
		[ "$ARCH" = x86_64 ] || { echo 'BOOT_MODE=bios exists only for x86_64' >&2; exit 1; }
		;; # QEMU's default SeaBIOS firmware.
	*) echo "BOOT_MODE must be uefi or bios" >&2; exit 1 ;;
esac
case "$UEFI_SECUREBOOT" in true|false) ;; *) echo 'UEFI_SECUREBOOT must be true or false' >&2; exit 1 ;; esac
if [ "$UEFI_SECUREBOOT" = true ] && { [ "$BOOT_MODE" != uefi ] || [ -z "$UEFI_CODE" ]; }; then
	echo 'Enforced Secure Boot tests require UEFI pflash code and enrolled variables' >&2; exit 1
fi

# Emulated guests get a CPU model without AVX: QEMU's emulation of AVX2 has
# faulted inside ZFS's SHA-256 routines. With KVM, use the host's CPU.
if [ "$ARCH" = aarch64 ]; then
	machine=virt,gic-version=max
	qemu=qemu-system-aarch64
	if [ "$(uname -m)" = arm64 ] || [ "$(uname -m)" = aarch64 ]; then
		# Apple silicon uses HVF (no /dev/kvm); Linux arm64 uses KVM.
		if [ -w /dev/kvm ]; then accel="-accel kvm -cpu host"; else accel="-accel hvf -cpu host"; fi
	else
		accel="-accel tcg,thread=multi -cpu max"
	fi
else
	machine=q35,smm=on
	qemu=qemu-system-x86_64
	if [ -w /dev/kvm ] && [ "$(uname -m)" = x86_64 ]; then
		accel="-accel kvm -cpu host"
	else
		accel="-accel tcg,thread=multi -cpu Westmere"
	fi
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
if [ -n "$UEFI_CODE" ]; then cp "$UEFI_VARS_TEMPLATE" OVMF_VARS.fd; fi

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
# QA of an unpublished feed: the installer's iterative package cache (an https/http
# URL to a signed versioned feed plus the exact SHA-256 of its three metadata files).
if [ -n "${PACKAGE_CACHE_URL:-}" ]; then
	: "${PACKAGE_CACHE_META_SHA256:?PACKAGE_CACHE_URL needs the three PACKAGE_CACHE_*_SHA256 pins}"
	: "${PACKAGE_CACHE_PACKAGESITE_SHA256:?needs PACKAGE_CACHE_PACKAGESITE_SHA256}"
	: "${PACKAGE_CACHE_DATA_SHA256:?needs PACKAGE_CACHE_DATA_SHA256}"
	cat >>daemonarchy-install.conf <<EOF
package_cache_url=$PACKAGE_CACHE_URL
package_cache_meta_sha256=$PACKAGE_CACHE_META_SHA256
package_cache_packagesite_sha256=$PACKAGE_CACHE_PACKAGESITE_SHA256
package_cache_data_sha256=$PACKAGE_CACHE_DATA_SHA256
EOF
fi
if command -v mformat >/dev/null && command -v mcopy >/dev/null && ! command -v mkfs.fat >/dev/null; then
	# mtools alone (macOS/Homebrew has no mkfs.fat): make the FAT image with mformat.
	cidata_drive=file=cidata.img,if=none,id=ci,format=raw
	cidata_device=ide-hd
	[ "$ARCH" = x86_64 ] || cidata_device=scsi-hd
	mformat -C -v CIDATA -T 65536 -i cidata.img ::
	mcopy -i cidata.img daemonarchy-install.conf ::/
elif command -v mkfs.fat >/dev/null && command -v mcopy >/dev/null; then
	cidata_drive=file=cidata.img,if=none,id=ci,format=raw
	cidata_device=ide-hd
	[ "$ARCH" = x86_64 ] || cidata_device=scsi-hd
	mkfs.fat -C -F 16 -n CIDATA cidata.img 32768 >/dev/null
	mcopy -i cidata.img daemonarchy-install.conf ::/
elif command -v xorriso >/dev/null; then
	cidata_drive=file=cidata.img,if=none,id=ci,format=raw,media=cdrom,readonly=on
	cidata_device=ide-cd
	[ "$ARCH" = x86_64 ] || cidata_device=scsi-cd
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
		if [ -n "$UEFI_CODE" ]; then
			set -- -global driver=cfi.pflash01,property=secure,value=on \
				-drive "if=pflash,format=raw,unit=0,readonly=on,file=$UEFI_CODE" \
				-drive if=pflash,format=raw,unit=1,file=OVMF_VARS.fd "$@"
		else
			set -- -bios "$OVMF" "$@"
		fi
	fi
	if [ -n "$VIRGL_RENDER_NODE" ]; then
		if [ "$ARCH" = aarch64 ]; then gpu=virtio-gpu-gl-pci; else gpu=virtio-vga-gl; fi
		set -- -device "$gpu" -display "egl-headless,rendernode=$VIRGL_RENDER_NODE" \
			-vnc "$VNC_LISTEN" -device qemu-xhci,id=desktop-usb \
			-device usb-tablet,bus=desktop-usb.0 "$@"
	elif [ "$ARCH" = aarch64 ]; then
		# The installer autologs in on ttyv0 only, and 'virt' has no VGA, so
		# without a display device the guest has only the serial console.
		set -- -device virtio-gpu-pci -display none "$@"
	else
		set -- -display none "$@"
	fi
	if [ "$SOUND_TEST" = yes ]; then
		set -- -audiodev none,id=snd0 -device intel-hda -device hda-duplex,audiodev=snd0 "$@"
	fi
	# shellcheck disable=SC2086
	$qemu -machine $machine $accel -smp 4 -m "$MEM" \
		-no-reboot -monitor none -qmp "unix:$log.qmp.sock,server=on,wait=off" \
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
		if [ "$log" = install.log ] && grep -aq 'FAILED\|panic:\|Installation exited with status [1-9]' install.log; then
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
# edk2's AArch64 firmware has no AHCI driver, so the 'virt' machine gets
# virtio-scsi for the ISO and CIDATA instead.
if [ "$ARCH" = x86_64 ]; then
	vm install.log \
		-device ahci,id=ahci0 \
		-drive "file=$ISO,if=none,id=cd,media=cdrom,readonly=on" -device ide-cd,drive=cd,bus=ahci0.0,bootindex=1 \
		-drive "$cidata_drive" -device "$cidata_device,drive=ci,bus=ahci0.1" \
		-netdev user,id=n0 -device virtio-net-pci,netdev=n0
else
	vm install.log \
		-device virtio-scsi-pci,id=scsi0 \
		-drive "file=$ISO,if=none,id=cd,media=cdrom,readonly=on" -device scsi-cd,drive=cd,bus=scsi0.0,bootindex=1 \
		-drive "$cidata_drive" -device "$cidata_device,drive=ci,bus=scsi0.0" \
		-netdev user,id=n0 -device virtio-net-pci,netdev=n0
fi
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
if [ "$ARCH" = x86_64 ]; then
	check "booted using $BOOT_MODE firmware" "sysctl -n machdep.bootmethod | grep -ix $BOOT_MODE"
else
	# arm64 has no machdep.bootmethod; UEFI is the only way it boots.
	check "booted using UEFI firmware" "sysctl -n machdep.efi_map >/dev/null 2>&1 || kenv -q efi-map-header >/dev/null 2>&1 || test -d /boot/efi || test -e /dev/efi"
fi
if [ "$ARCH" = x86_64 ]; then
	check "BIOS boot partition present" "gpart show vtbd0 | grep -q freebsd-boot"
fi
if [ "$UEFI_SECUREBOOT" = true ]; then
	check "firmware Secure Boot enabled" "test \$(as_root efivar -p -N -b -n 8be4df61-93ca-11d2-aa0d-00e098032b8c-SecureBoot | od -An -tu1 | tr -d '[:space:]') = 1"
	check "verified kernel selected" "kenv kernelname | grep -q '/boot/kernel.secure/kernel'"
	check "verified policy loaded, active, enforcing and locked" "sysctl -n security.mac.veriexec.state | grep -q 'loaded active enforce locked'"
else
	check "normal kernel has no module policy" "! sysctl -n security.mac.veriexec.state 2>/dev/null"
fi
if [ "$ENCRYPT_INSTALLATION" = true ]; then
	check "ZFS boots from the GELI provider" "as_root zpool status -P | grep -q '/dev/vtbd0p3.eli'"
fi
for g in wheel operator video audio; do
	check "tester in \$g" "id -Gn | grep -qw \$g"
done
if [ "$SOUND_TEST" = yes ]; then
	check "QEMU HDA sound device attaches" "as_root kldload -n snd_hda && sleep 2 && grep -q '^pcm0:' /dev/sndstat"
fi
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
check "selected signed application feed" "grep -Fqx '  url: \"https://github.com/jordanhubbard/daemonarchy/releases/download/$EXPECTED_PACKAGE_REPOSITORY_TAG\",' /usr/local/etc/pkg/repos/Daemonarchy.conf"
check "Daemonarchy defaults staged" "test -d /usr/local/share/omarchy/skel.d/daemonarchy"
exit \$failures
EOF
guest "sh -s" <"$SCRIPT_DIR/tests/installed-desktop.sh" || status=1
guest "sh -s -- $INSTALL_PORTS $INSTALL_SRC" <"$SCRIPT_DIR/tests/installed-checkouts.sh" || status=1
if [ -n "${POST_INSTALL_CHECK:-}" ]; then
	"$POST_INSTALL_CHECK" "$WORK" "$SSH_PORT" || status=1
fi
guest "echo $PASSWORD | sudo -S -p '' shutdown -p now" >/dev/null 2>&1 || true
wait "$booter" 2>/dev/null || true
if [ "$status" -ne 0 ]; then
	echo "$status check(s) failed" >&2
	exit 1
fi
echo "==> All checks passed"
