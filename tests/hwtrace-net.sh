#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Host test of tools/hwtrace/net.sh (the hardware trace image's network
# hand-over) and of the rc script's wiring, against shimmed commands:
#   sh tests/hwtrace-net.sh
# The shims stand in for kenv, ifconfig, dhclient, ssh-keygen, sshd, sleep.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
shims=$tmp/shims
mkdir -p "$shims" "$tmp/data/KEYS" "$tmp/data/DUMPS" "$tmp/var"
fail() { echo "FAIL: $*" >&2; exit 1; }

sh -n "$here/tools/hwtrace/rc" "$here/tools/hwtrace/net.sh" \
    "$here/tools/hwtrace/hwtrace-continue" "$here/tools/hwtrace/hwtrace-hold" \
    "$here/build-hwtrace-image.sh"

cat >"$shims/kenv" <<'SH'
#!/bin/sh
[ "$1" = -q ] && shift
name=$(echo "$1" | tr '.' '_')
eval "v=\${KENV_$name:-}"
[ -n "$v" ] && echo "$v"
exit 0
SH
cat >"$shims/kldload" <<'SH'
#!/bin/sh
echo "$*" >>"$SHIM_LOG/kldload"
SH
cat >"$shims/ifconfig" <<'SH'
#!/bin/sh
case $* in
"-l") echo "lo0 em0 ue0 wlan0" ;;
"-a") echo "lo0: flags=8049" ;;
"ue0") echo "	ether ac:de:48:00:11:22" ;;
"em0") echo "	ether 52:54:00:12:34:56" ;;
"em0 up"|"ue0 up") echo "$*" >>"$SHIM_LOG/up" ;;
"em0 inet")
	[ -e "$SHIM_LOG/lease" ] && echo "	inet 10.0.2.15 netmask 0xffffff00 broadcast 10.0.2.255"
	echo "	inet 169.254.1.1 netmask 0xffff0000" ;;
*) ;;
esac
exit 0
SH
cat >"$shims/dhclient" <<'SH'
#!/bin/sh
echo "$*" >>"$SHIM_LOG/dhclient"
[ -z "${SHIM_NO_LEASE:-}" ] && [ "$2" = em0 ] && : >"$SHIM_LOG/lease"
exit 0
SH
cat >"$shims/ssh-keygen" <<'SH'
#!/bin/sh
case $1 in
-l) echo "256 SHA256:abcdefTESTFINGERPRINT hwtrace-host (ED25519)" ;;
-q) for last; do :; done
    echo "generated" >>"$SHIM_LOG/keygen"
    echo "PRIVATE-KEY-TEXT" >"$last"; echo "ssh-ed25519 AAAAHOST hwtrace-host" >"$last.pub" ;;
esac
exit 0
SH
cat >"$shims/mysshd" <<'SH'
#!/bin/sh
echo "$*" >>"$SHIM_LOG/sshd"
SH
cat >"$shims/sleep" <<'SH'
#!/bin/sh
n=$(cat "$SHIM_LOG/sleeps" 2>/dev/null || echo 0)
n=$((n + 1)); echo "$n" >"$SHIM_LOG/sleeps"
[ -n "${SHIM_CONTINUE_AT:-}" ] && [ "$n" -ge "$SHIM_CONTINUE_AT" ] && : >"$HW_VAR/continue"
[ -n "${SHIM_HOLD_AT:-}" ] && [ "$n" -ge "$SHIM_HOLD_AT" ] && echo 10 >"$HW_VAR/hold"
exit 0
SH
cat >"$shims/sysctl" <<'SH'
#!/bin/sh
echo "FreeBSD test kernel"
SH
cat >"$shims/netstat" <<'SH'
#!/bin/sh
echo "default 10.0.2.2"
SH
chmod +x "$shims"/*

export HW_CON=/nonexistent SHIM_LOG=$tmp/log HW_DATA=$tmp/data HW_VAR=$tmp/var/hwtrace HW_SSHD=$shims/mysshd HW_STEP=5
PATH=$shims:$PATH
reset() { rm -rf "$SHIM_LOG" "$HW_VAR"; mkdir -p "$SHIM_LOG"; unset KENV_hwtrace_net KENV_hwtrace_hold KENV_hwtrace_dhcp SHIM_NO_LEASE SHIM_CONTINUE_AT SHIM_HOLD_AT || true; }
reset
. "$here/tools/hwtrace/net.sh"

# 1. No keys (or none that look like keys): no hand-over.
hwtrace_wanted && fail "wanted without keys"
echo "not a key" >"$HW_DATA/KEYS/authorized_keys"
hwtrace_wanted && fail "wanted with a junk key file"
echo "ssh-ed25519 AAAAOPERATOR jkh@sparky" >"$HW_DATA/KEYS/authorized_keys"
hwtrace_wanted || fail "not wanted with a key"
KENV_hwtrace_net=NO; export KENV_hwtrace_net
hwtrace_wanted && fail "wanted although hwtrace.net=NO"
unset KENV_hwtrace_net

# 2. Hand-over: only the real wired NIC gets DHCP, sshd is configured for the
# key alone, the address is recorded, the host key is made once and kept.
reset
hwtrace_handover 0001 || fail "hand-over failed"
[ "$HW_IFACE" = em0 ] && [ "$HW_ADDR" = 10.0.2.15 ] || fail "iface/addr $HW_IFACE $HW_ADDR"
grep -qx 'dhclient -b em0' "$SHIM_LOG/dhclient" 2>/dev/null || grep -q -- '-b em0' "$SHIM_LOG/dhclient" || fail "no dhclient on em0"
! grep -q 'ue0\|wlan0\|lo0' "$SHIM_LOG/dhclient" || fail "DHCP asked on T2 link, wlan or lo"
grep -q '^Port 2222$' "$HW_VAR/sshd_config" || fail "port"
grep -q '^PasswordAuthentication no$' "$HW_VAR/sshd_config" || fail "password auth"
grep -q '^PermitRootLogin prohibit-password$' "$HW_VAR/sshd_config" || fail "root login"
grep -q "^AuthorizedKeysFile $HW_VAR/authorized_keys$" "$HW_VAR/sshd_config" || fail "keys file"
grep -q AAAAOPERATOR "$HW_VAR/authorized_keys" || fail "key not copied"
grep -q '^state=listening$' "$HW_DATA/DUMPS/0001/network.txt" || fail "network.txt"
grep -q '^address=10.0.2.15$' "$HW_DATA/ADDRESS.TXT" || fail "ADDRESS.TXT"
grep -q 'ssh -p 2222 root@10.0.2.15' "$HW_DATA/ADDRESS.TXT" || fail "ADDRESS.TXT command"
grep -q 'SHA256:abcdefTESTFINGERPRINT' "$HW_DATA/ADDRESS.TXT" || fail "fingerprint"
[ -s "$HW_DATA/KEYS/ssh_host_ed25519_key" ] || fail "host key not kept on the stick"
[ "$(wc -l <"$SHIM_LOG/keygen")" -eq 1 ] || fail "host key generated more than once"
[ -s "$SHIM_LOG/sshd" ] || fail "sshd not started"
# A second boot reuses the stick's host key.
reset
hwtrace_handover 0002 || fail "second hand-over failed"
[ ! -e "$SHIM_LOG/keygen" ] || fail "host key regenerated on the second boot"
[ "$HW_HOSTKEY_SOURCE" = stick ] || fail "host key source $HW_HOSTKEY_SOURCE"

# 3. No address within the wait: recorded, no sshd, the loop continues.
reset
SHIM_NO_LEASE=1; export SHIM_NO_LEASE
KENV_hwtrace_dhcp=3; export KENV_hwtrace_dhcp
if hwtrace_handover 0003; then fail "hand-over without an address"; fi
grep -q '^state=no-address$' "$HW_DATA/DUMPS/0003/network.txt" || fail "no-address record"
[ ! -e "$SHIM_LOG/sshd" ] || fail "sshd started without an address"
unset SHIM_NO_LEASE KENV_hwtrace_dhcp

# 4. The hold: bounded, ends early on the marker, length changeable.
reset; mkdir -p "$HW_VAR"; HW_HOLD=30
hwtrace_hold >"$tmp/hold.out"
[ "$(cat "$SHIM_LOG/sleeps")" -eq 6 ] || fail "30 s hold took $(cat "$SHIM_LOG/sleeps") polls"
reset; mkdir -p "$HW_VAR"; HW_HOLD=3000; SHIM_CONTINUE_AT=3; export SHIM_CONTINUE_AT
hwtrace_hold >"$tmp/hold.out"
[ "$(cat "$SHIM_LOG/sleeps")" -eq 3 ] || fail "continue marker ignored"
grep -q 'continue requested' "$tmp/hold.out" || fail "continue not reported"
reset; mkdir -p "$HW_VAR"; HW_HOLD=3000; SHIM_HOLD_AT=2; export SHIM_HOLD_AT
hwtrace_hold >"$tmp/hold.out"
[ "$(cat "$SHIM_LOG/sleeps")" -eq 3 ] || fail "hold override ignored ($(cat "$SHIM_LOG/sleeps"))"

# 5. The operator commands write the markers the hold looks for.
reset
mkdir -p "$tmp/fakevar"
sed "s,/var/hwtrace,$tmp/fakevar,g" "$here/tools/hwtrace/hwtrace-continue" >"$tmp/c.sh"
sed "s,/var/hwtrace,$tmp/fakevar,g" "$here/tools/hwtrace/hwtrace-hold" >"$tmp/h.sh"
sh "$tmp/c.sh" >/dev/null; [ -e "$tmp/fakevar/continue" ] || fail "hwtrace-continue"
sh "$tmp/h.sh" 120 >/dev/null; [ "$(cat "$tmp/fakevar/hold")" = 120 ] || fail "hwtrace-hold"
sh "$tmp/h.sh" abc >/dev/null 2>&1 && fail "hwtrace-hold accepted junk"

# 6. The rc only hands over for a stick with keys and never blocks the loop:
# the hand-over is after the diagnostics save, before the reboot.
awk '/hwtrace_wanted/ { w = NR } /dmesg -a/ { d = NR } /^reboot$/ { r = NR } END { exit !(d < w && w < r) }' \
    "$here/tools/hwtrace/rc" || fail "rc ordering"
grep -q 'hwtrace_hold' "$here/tools/hwtrace/rc" || fail "rc does not hold"

echo "PASS: hwtrace network hand-over: keys required, T2 link skipped, sshd for the key only, address recorded, bounded hold"
