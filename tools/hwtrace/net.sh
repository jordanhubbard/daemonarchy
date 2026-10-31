#!/rescue/sh
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daemonarchy contributors.
#
# Network hand-over for the Daemonarchy hardware trace image (sourced by rc).
# When a boot reaches init and the stick carries KEYS/authorized_keys, bring
# up a wired network (bounded DHCP), start sshd on port 2222 for that key
# only, record the address on the DATRACE volume and hold the boot for a
# bounded time so the operator can probe the machine before the loop goes on.
#
# Every path and command can be overridden (HW_*), which is how
# tests/hwtrace-net.sh runs these functions against shims.
#
# Tunables (kenv, from a queue line such as "hwtrace.hold=3600"):
#   hwtrace.net=NO        skip the hand-over (the loop behaves as before)
#   hwtrace.hold=SECONDS  how long to stay up for the operator (default 1800)
#   hwtrace.dhcp=SECONDS  how long to wait for an address (default 40)

: "${HW_DATA:=/mnt}"            # the mounted DATRACE volume
: "${HW_VAR:=/var/hwtrace}"     # volatile state (keys, sshd, markers)
: "${HW_PORT:=2222}"
: "${HW_STEP:=5}"               # hold poll interval, seconds
# The kernel (GENERIC) already has em, igb, igc, ix, re and rge built in (the
# QEMU run printed "already loaded from kernel" for each); these are the
# drivers it lacks: USB Ethernet and a few PCI ones.
: "${HW_NICMODS:=if_ure if_axge if_axe if_cdce if_cdceem if_mos if_smsc if_muge if_urndis if_ipheth if_aue if_bge if_msk}"
# The T2's internal USB link is not a network (docs/roadmap NET-001).
: "${HW_T2_MAC:=ac:de:48:00:11:22}"

hw_kenv() { kenv -q "$1" 2>/dev/null || true; }
# init's stdout does not always reach the console; also write to /dev/console.
: "${HW_CON:=/dev/console}"
hw_out() { echo "$*"; [ -c "$HW_CON" ] && echo "$*" >"$HW_CON" 2>/dev/null; return 0; }
hw_say() { hw_out "hwtrace net: $*"; }

# 0 when a hand-over is wanted: not disabled and the stick carries a key.
hwtrace_wanted() {
	[ "$(hw_kenv hwtrace.net)" = NO ] && return 1
	[ -s "$HW_DATA/KEYS/authorized_keys" ] || return 1
	# (no sed alternation: the rescue sed is BSD basic-regex only)
	while read -r line; do
		case $line in ssh-*|ecdsa-*|sk-*) return 0 ;; esac
	done <"$HW_DATA/KEYS/authorized_keys"
	return 1
}

# The volatile /var (the root is read-only), then keys and host key.
hwtrace_prepare() {
	mkdir -p "$HW_VAR" || return 1
	chmod 700 "$HW_VAR"
	cat "$HW_DATA/KEYS/authorized_keys" >"$HW_VAR/authorized_keys"
	chmod 600 "$HW_VAR/authorized_keys"
	if [ -s "$HW_DATA/KEYS/ssh_host_ed25519_key" ]; then
		cat "$HW_DATA/KEYS/ssh_host_ed25519_key" >"$HW_VAR/ssh_host_ed25519_key"
		chmod 600 "$HW_VAR/ssh_host_ed25519_key"
		HW_HOSTKEY_SOURCE=stick
	else
		# First boot of this stick: make a host key and keep it on the
		# stick, so the fingerprint is the same on every later boot.
		rm -f "$HW_VAR/ssh_host_ed25519_key" "$HW_VAR/ssh_host_ed25519_key.pub"
		ssh-keygen -q -t ed25519 -N '' -C hwtrace-host \
		    -f "$HW_VAR/ssh_host_ed25519_key" || return 1
		mkdir -p "$HW_DATA/KEYS"
		cat "$HW_VAR/ssh_host_ed25519_key" >"$HW_DATA/KEYS/ssh_host_ed25519_key"
		cat "$HW_VAR/ssh_host_ed25519_key.pub" >"$HW_DATA/KEYS/ssh_host_ed25519_key.pub"
		HW_HOSTKEY_SOURCE=generated
	fi
	HW_FINGERPRINT=$(ssh-keygen -l -f "$HW_VAR/ssh_host_ed25519_key" 2>/dev/null |
	    sed -n 's/^[0-9]* \(SHA256:[^ ]*\) .*/\1/p')
}

hwtrace_loadnics() {
	local m
	for m in $HW_NICMODS; do
		kldload -n "$m" >/dev/null 2>&1 || true
	done
}

# Wired interfaces worth asking for an address.
hwtrace_candidates() {
	local i mac
	for i in $(ifconfig -l); do
		case $i in
		lo*|pflog*|pfsync*|enc*|wlan*|bridge*|epair*|tap*|tun*|gif*|stf*|vlan*|lagg*|ipfw*|disc*|edsc*) continue ;;
		esac
		mac=$(ifconfig "$i" | sed -n 's/^[[:space:]]*ether \([0-9a-f:]*\).*/\1/p')
		[ "$mac" = "$HW_T2_MAC" ] && continue
		echo "$i"
	done
}

hwtrace_addr() {	# hwtrace_addr IFACE: first usable IPv4 address
	ifconfig "$1" inet 2>/dev/null |
	    sed -n 's/^[[:space:]]*inet \([0-9.]*\) .*/\1/p' |
	    while read -r a; do
		case $a in 0.0.0.0|169.254.*|'') ;; *) echo "$a"; break ;; esac
	done
}

# Bounded DHCP on every candidate at once; sets HW_IFACE and HW_ADDR.
hwtrace_dhcp() {
	local wait i a n=0
	wait=$(hw_kenv hwtrace.dhcp); : "${wait:=40}"
	hwtrace_loadnics
	# DHCP servers list clients by name: make the machine easy to find.
	hostname "${HW_HOSTNAME:-daemonarchy-hwtrace}" 2>/dev/null || true
	HW_IFACE= HW_ADDR=
	sleep 2
	for i in $(hwtrace_candidates); do
		ifconfig "$i" up >/dev/null 2>&1 || continue
		dhclient -b "$i" >>"$HW_VAR/dhclient.log" 2>&1 &
	done
	while [ "$n" -lt "$wait" ]; do
		for i in $(hwtrace_candidates); do
			a=$(hwtrace_addr "$i")
			if [ -n "$a" ]; then HW_IFACE=$i HW_ADDR=$a; return 0; fi
		done
		sleep 1
		n=$((n + 1))
	done
	return 1
}

hwtrace_sshd() {
	cat >"$HW_VAR/sshd_config" <<EOC
Port $HW_PORT
HostKey $HW_VAR/ssh_host_ed25519_key
PidFile $HW_VAR/sshd.pid
AuthorizedKeysFile $HW_VAR/authorized_keys
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
StrictModes no
UseDNS no
AllowTcpForwarding no
X11Forwarding no
Subsystem sftp /usr/libexec/sftp-server
EOC
	${HW_SSHD:-/usr/sbin/sshd} -f "$HW_VAR/sshd_config" -E "$HW_VAR/sshd.log"
}

# hwtrace_record ID: what the operator needs to connect, on the stick.
hwtrace_record() {
	local id=$1 d=$HW_DATA/DUMPS/$1
	mkdir -p "$d"
	{
		echo "state=$2"
		echo "interface=$HW_IFACE"
		echo "address=$HW_ADDR"
		echo "port=$HW_PORT"
		echo "host_key=$HW_FINGERPRINT ($HW_HOSTKEY_SOURCE)"
		echo "hold_seconds=$HW_HOLD"
		echo "kernel=$(sysctl -n kern.version 2>/dev/null | sed 1q)"
		ifconfig -a
		netstat -rn 2>/dev/null
		echo "--- dhclient"; cat "$HW_VAR/dhclient.log" 2>/dev/null
		echo "--- sshd"; cat "$HW_VAR/sshd.log" 2>/dev/null
	} >"$d/network.txt" 2>&1
	{
		echo "experiment=$id"
		echo "address=$HW_ADDR"
		echo "port=$HW_PORT"
		echo "ssh -p $HW_PORT root@$HW_ADDR"
		echo "host_key=$HW_FINGERPRINT"
	} >"$HW_DATA/ADDRESS.TXT"
}

# Hand over. Returns after the hold; the caller then reboots (loop continues).
hwtrace_handover() {	# hwtrace_handover ID
	local id=$1
	HW_HOLD=$(hw_kenv hwtrace.hold); : "${HW_HOLD:=1800}"
	hwtrace_prepare || { hw_say "could not prepare keys; no hand-over"; return 1; }
	if ! hwtrace_dhcp; then
		hw_say "no address within the wait; continuing the loop"
		hwtrace_record "$id" no-address
		return 1
	fi
	if ! hwtrace_sshd; then
		hw_say "sshd did not start; continuing the loop"
		hwtrace_record "$id" sshd-failed
		return 1
	fi
	hwtrace_record "$id" listening
	HW_READY=1
	return 0
}

hwtrace_banner() {
	hw_out ""
	hw_out "=== Daemonarchy hardware trace: debugger ready ==="
	hw_out "ssh -p $HW_PORT root@$HW_ADDR   ($HW_IFACE)"
	hw_out "host key $HW_FINGERPRINT"
	hw_out "The boot is held for $HW_HOLD s. Over ssh: hwtrace-hold SECONDS changes"
	hw_out "that, hwtrace-continue goes on now. Then the loop continues."
}

# Stay up until the hold runs out or the operator says go on.
hwtrace_hold() {
	local elapsed=0 hold=$HW_HOLD o
	rm -f "$HW_VAR/continue" "$HW_VAR/hold"
	while [ "$elapsed" -lt "$hold" ]; do
		[ -e "$HW_VAR/continue" ] && { hw_say "continue requested"; return 0; }
		if [ -s "$HW_VAR/hold" ]; then
			o=$(cat "$HW_VAR/hold")
			case $o in ''|*[!0-9]*) ;; *) hold=$o ;; esac
		fi
		sleep "$HW_STEP"
		elapsed=$((elapsed + HW_STEP))
		[ $((elapsed % 60)) -eq 0 ] &&
		    hw_say "held $elapsed of $hold s (ssh -p $HW_PORT root@$HW_ADDR)"
	done
	hw_say "hold of $hold s ended"
	return 0
}
