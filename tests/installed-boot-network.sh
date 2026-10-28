#!/usr/bin/env bash
# Installed-system boot networking (NET-002): daemonarchy-netselect, the
# dhclient hooks and the installer's rc.conf, against a shimmed FreeBSD
# network. ifconfig, route, arp, ping, drill, sysctl and lockf answer from
# fixture files; nothing touches the host's adapters, routes or resolver.
# timeout(1) is real, so the per-candidate budget is measured, not assumed.
#
# Set DHCLIENT_SCRIPT to FreeBSD's sbin/dhclient/dhclient-script to also run
# the hooks inside the real script (it is not part of this repository).
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
src=$here/overlay/usr/local/share/daemonarchy-installer/netselect
install=$here/overlay/usr/local/libexec/daemonarchy-installer/install
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
W=$work/w
export W

fail() { echo "FAIL: $*" >&2; [[ -f $work/net.log ]] && tail -n 30 "$work/net.log" >&2; exit 1; }

sh -n "$src/daemonarchy-netselect" "$src/dhclient-enter-hooks" "$src/dhclient-exit-hooks" \
  "$src/daemonarchy-t2link" "$src/daemonarchy-t2link.rc.conf"
command -v flock >/dev/null || fail 'flock(1) is needed for the lockf shim'

# ---------------------------------------------------------------- shims

mkdir -p "$work/bin"
shim() { cat >"$work/bin/$1"; chmod +x "$work/bin/$1"; }
shim ifconfig <<'EOF'
#!/bin/sh
ifc=$1
[ "$ifc" = -l ] && { ls "$W" | sed -n 's/^link\.//p' | tr '\n' ' '; echo; exit 0; }
[ -f "$W/link.$ifc" ] || { echo "ifconfig: interface $ifc does not exist" >&2; exit 1; }
if [ "$2" = inet ] && [ $# -gt 2 ]; then
	echo "ifconfig $*" >>"$W/calls"
	[ "$4" = -alias ] && rm -f "$W/addr.$ifc"
	exit 0
fi
if [ "$2" = inet ]; then
	[ -f "$W/addr.$ifc" ] && printf '\tinet %s netmask 0xffffff00 broadcast 192.0.2.255\n' "$(cat "$W/addr.$ifc")"
	exit 0
fi
if [ "$2" = inet6 ] && [ $# -gt 2 ]; then
	echo "ifconfig $*" >>"$W/calls"
	echo "fe80::aede:48ff:fe00:1122%$ifc" >"$W/ll.$ifc"
	exit 0
fi
if [ "$2" = inet6 ]; then
	[ -f "$W/ll.$ifc" ] && printf '\tinet6 %s prefixlen 64 scopeid 0x5\n' "$(cat "$W/ll.$ifc")"
	exit 0
fi
if [ "$2" = ether ]; then
	[ -f "$W/mac.$ifc" ] && printf '\tether %s\n' "$(cat "$W/mac.$ifc")"
	exit 0
fi
if [ "$2" = up ]; then
	echo "ifconfig $*" >>"$W/calls"
	exit 0
fi
case $(cat "$W/link.$ifc") in
up) case $ifc in wlan*) echo '	status: associated' ;; *) echo '	status: active' ;; esac ;;
no-carrier) echo '	status: no carrier' ;;
esac
EOF
shim route <<'EOF'
#!/bin/sh
# One default route, as in the kernel: add fails when one exists.
echo "route $*" >>"$W/calls"
case "$*" in
'-n get -inet default')
	[ -f "$W/default" ] || { echo 'route: route has not been found' >&2; exit 1; }
	read -r gw ifc <"$W/default"
	printf '   route to: default\n    gateway: %s\n  interface: %s\n' "$gw" "$ifc"
	;;
'-q add default '*)
	[ -f "$W/default" ] && exit 1
	sleep 0.05   # widen any window a racing publisher could use
	echo "$4 $(cat "$W/gwif.$4" 2>/dev/null)" >"$W/default"
	echo "$4" >>"$W/route-writes"
	;;
'-q change default '*)
	[ -f "$W/default" ] || exit 1
	sleep 0.05
	echo "$4 $(cat "$W/gwif.$4" 2>/dev/null)" >"$W/default"
	echo "$4" >>"$W/route-writes"
	;;
'-q delete default') rm -f "$W/default" ;;
esac
exit 0
EOF
shim arp <<'EOF'
#!/bin/sh
if [ -f "$W/arp.$2" ]; then
	echo "? ($2) at 00:11:22:33:44:55 on $(cat "$W/arp.$2") expires in 1200 seconds [ethernet]"
else
	echo "? ($2) at (incomplete) on em0 expired [ethernet]"
fi
EOF
shim ping <<'EOF'
#!/bin/sh
echo "ping $*" >>"$W/calls"
exit 1   # every host here drops ICMP
EOF
shim drill <<'EOF'
#!/bin/sh
# drill -I source @server name A
server=${3#@}
echo "drill $*" >>"$W/calls"
if grep -qx "$server" "$W/dns-ok" 2>/dev/null; then
	echo ';; ->>HEADER<<- opcode: QUERY, rcode: NOERROR, id: 4711'
elif grep -qx "$server" "$W/dns-servfail" 2>/dev/null; then
	echo ';; ->>HEADER<<- opcode: QUERY, rcode: SERVFAIL, id: 4711'
else
	exec sleep 30   # a dead server: only timeout(1) ends this
fi
EOF
shim sysctl <<'EOF'
#!/bin/sh
case "$*" in
'-n kern.boottime') echo "{ sec = $(cat "$W/boot"), usec = 0 } Tue Oct 27 09:00:00 2026" ;;
'-n net.ue.'*'.%parent') x=${2#net.ue.}; cat "$W/ue-parent.${x%%.*}" 2>/dev/null ;;
'-n dev.cdce.'*'.%pnpinfo') x=${2#dev.cdce.}; cat "$W/pnp.${x%%.*}" 2>/dev/null ;;
*) exit 1 ;;
esac
EOF
shim ps <<'EOF'
#!/bin/sh
# ps -p PID -o command=
cat "$W/ps.$2" 2>/dev/null
EOF
shim kill <<'EOF'
#!/bin/sh
echo "kill $*" >>"$W/calls"
EOF
shim pgrep <<'EOF'
#!/bin/sh
exit 1
EOF
shim lockf <<'EOF'
#!/bin/sh
# lockf -k -t SECONDS FILE COMMAND...
[ "$1" = -k ] && shift
[ "$1" = -t ] && { t=$2; shift 2; }
f=$1; shift
exec flock -w "${t:-0}" "$f" "$@"
EOF

netselect=$work/daemonarchy-netselect
cp "$src/daemonarchy-netselect" "$netselect"
t2link=$work/daemonarchy-t2link
cp "$src/daemonarchy-t2link" "$t2link"
chmod +x "$netselect" "$t2link"
export NETSELECT_T2LINK=$t2link T2LINK_DHCLIENT_PIDDIR=$work/run T2LINK_ATTACH_WAIT=2 T2LINK_KILL=$work/bin/kill
export PATH=$work/bin:$PATH
export NETSELECT_STATE=$work/state NETSELECT_LOG=$work/net.log NETSELECT_RESOLV=$work/resolv.conf
export NETSELECT_GATEWAY_TIMEOUT=1 NETSELECT_DNS_TIMEOUT=1

# ---------------------------------------------------------------- fixtures

world() {
  rm -rf "$W" "$work/state" "$work/net.log" "$work/resolv.conf"
  mkdir -p "$W"
  : >"$W/calls"; : >"$W/route-writes"; : >"$W/dns-ok"; : >"$W/dns-servfail"
  echo $(($(date +%s) - 7)) >"$W/boot"
  printf 'nameserver 192.0.2.250\n' >"$work/resolv.conf"
}
nic() { echo "$2" >"$W/link.$1"; }                     # name up|no-carrier
gateway() { echo "$2" >"$W/gwif.$1"; [[ ${3:-arp} == arp ]] && echo "$2" >"$W/arp.$1"; return 0; }
dns_ok() { printf '%s\n' "$@" >>"$W/dns-ok"; }
# What dhclient-exit-hooks passes for one dhclient-script run.
lease() { # ifc address gateway "dns..." [reason]
  echo "$2" >"$W/addr.$1"
  "$netselect" lease "$1" "${5:-BOUND}" 0 "$2" "$3" "$4" example.test
}
ended() { rm -f "$W/addr.$1"; "$netselect" lease "$1" "$2" 1 '' '' '' ''; }
owner() { cat "$work/state/owner" 2>/dev/null || echo none; }
route_if() { [[ -f $W/default ]] && cut -d' ' -f2 "$W/default" || echo none; }
route_gw() { [[ -f $W/default ]] && cut -d' ' -f1 "$W/default" || echo none; }
nameservers() { awk '/^nameserver/ { printf "%s%s", sep, $2; sep = " " }' "$work/resolv.conf"; }
cand() { sed -n "s/^$2=//p" "$work/state/cand.$1"; }
writes() { wc -l <"$W/route-writes" | tr -d ' '; }

# ---------------------------------------------------------------- installer

# The installer adds the bounded-boot settings and the owner to DHCP and
# Wi-Fi installs, and leaves a static address alone.
awk '/^installed_boot_dhcp\(\) \{/,/^\}/' "$install" >"$work/installed_boot_dhcp"
grep -q 'background_dhclient="YES"' "$work/installed_boot_dhcp" || fail 'dhclient is not backgrounded at boot'
grep -q 'defaultroute_delay="10"' "$work/installed_boot_dhcp" || fail 'total boot budget is not declared'
grep -q 'defaultroute_carrier_delay="5"' "$work/installed_boot_dhcp" || fail 'no-carrier budget is not declared'
for f in daemonarchy-netselect dhclient-enter-hooks dhclient-exit-hooks daemonarchy-netselect.conf; do
  grep -q "\$src/$f" "$work/installed_boot_dhcp" || fail "installer does not install $f"
done
# The T2 link handling goes on every install, whatever the network mode.
[[ $(grep -c '^installed_t2_link$' "$install") == 1 ]] || fail 'installer does not set up the T2 link at top level'
awk '/^installed_t2_link\(\) \{/,/^\}/' "$install" >"$work/installed_t2_link"
for f in daemonarchy-t2link daemonarchy-t2link.conf daemonarchy-t2link.rc.conf; do
  grep -q "\$src/$f\"" "$work/installed_t2_link" || fail "installer does not install $f"
done
[[ $(awk '/^  wifi\)/,/;;/' "$install" | grep -c installed_boot_dhcp) == 1 ]] || fail 'Wi-Fi install lacks the boot settings'
[[ $(awk '/^  \*\)/,/;;/' "$install" | grep -c installed_boot_dhcp) == 1 ]] || fail 'DHCP install lacks the boot settings'
[[ $(awk '/^  static\)/,/;;/' "$install" | grep -c installed_boot_dhcp) == 0 ]] || fail 'static install got DHCP settings'
grep -q 'LINK_DOWN' "$src/daemonarchy-netselect.conf" || fail 'no devd link-down rule'

# The installer function itself, run against a scratch target.
TARGET=$work/target ISO_SHARE=$here/overlay/usr/local/share/daemonarchy-installer
mkdir -p "$TARGET/etc"; : >"$TARGET/etc/rc.conf"
# shellcheck source=/dev/null
source "$work/installed_boot_dhcp"
# shellcheck source=/dev/null
source "$work/installed_t2_link"
installed_boot_dhcp
installed_t2_link
for f in usr/local/libexec/daemonarchy-netselect etc/dhclient-enter-hooks etc/dhclient-exit-hooks \
  usr/local/etc/devd/daemonarchy-netselect.conf usr/local/etc/newsyslog.conf.d/daemonarchy-net.conf \
  usr/local/libexec/daemonarchy-t2link usr/local/etc/devd/daemonarchy-t2link.conf \
  usr/local/etc/rc.conf.d/network/daemonarchy-t2link; do
  [[ -s $TARGET/$f ]] || fail "installer did not write $f"
done
grep -qx 'defaultroute_delay="10"' "$TARGET/etc/rc.conf" || fail 'rc.conf lacks the total budget'

# ---------------------------------------------------------------- 1. absent Ethernet, Wi-Fi only

world
nic wlan0 up; gateway 192.168.1.1 wlan0; dns_ok 192.168.1.1
lease wlan0 192.168.1.20 192.168.1.1 192.168.1.1
[[ $(owner) == wlan0 && $(route_if) == wlan0 ]] || fail 'Wi-Fi alone did not get the route'
[[ $(nameservers) == 192.168.1.1 ]] || fail 'Wi-Fi DNS not published'
grep -q '^search example.test$' "$work/resolv.conf" || fail 'search domain lost'
grep -q 'first usable interface wlan0 [0-9]*s after boot' "$work/net.log" || fail 'boot-to-usable time not recorded'
grep -q 'class=3' "$work/net.log" || fail 'Wi-Fi lease not fully proven'
! grep -q 'em0' "$W/calls" || fail 'an absent interface was probed'

# ---------------------------------------------------------------- 2. disconnected Ethernet plus Wi-Fi

world
nic em0 no-carrier; nic wlan0 up; gateway 192.168.1.1 wlan0; dns_ok 192.168.1.1
"$netselect" link-down em0          # devd reports the unplugged port
[[ ! -e $work/state/cand.em0 ]] || fail 'an unplugged port became a candidate'
lease wlan0 192.168.1.20 192.168.1.1 192.168.1.1
[[ $(owner) == wlan0 ]] || fail 'Wi-Fi did not win over unplugged Ethernet'
# A lease remembered for a port whose cable is now out cannot win.
echo 10.0.0.5 >"$W/addr.em0"; gateway 10.0.0.1 em0; dns_ok 10.0.0.1
"$netselect" lease em0 REBOOT 0 10.0.0.5 10.0.0.1 10.0.0.1 ''
[[ $(owner) == wlan0 && $(route_if) == wlan0 ]] || fail 'a no-carrier port took the route'

# ---------------------------------------------------------------- 3. several NICs, one DHCP server

# A port with a link but no DHCP server; wlan0 works. (This was the
# MacBookPro16,1 ue0 case before the T2 link was recognized: see section 8.)
world
nic ue0 up; nic em0 up; nic wlan0 up; gateway 192.168.1.1 wlan0; dns_ok 192.168.1.1
ended ue0 FAIL                      # dhclient gives up on ue0 (in the background)
ended em0 FAIL
lease wlan0 192.168.1.20 192.168.1.1 192.168.1.1
[[ $(owner) == wlan0 && $(route_if) == wlan0 && $(writes) == 1 ]] || fail 'the one working interface did not own the route'
[[ $(cand ue0 status) == gone && $(cand ue0 reason) == FAIL ]] || fail 'failed candidate diagnostics not kept'
grep -q 'ue0 FAIL: lease ended' "$work/net.log" || fail 'failed candidate not logged'

# ---------------------------------------------------------------- 4. competing valid leases

for round in 1 2 3 4 5; do
  world
  nic em0 up; nic igb0 up
  gateway 10.0.0.1 em0; gateway 10.1.0.1 igb0; dns_ok 10.0.0.53 10.1.0.53
  lease em0 10.0.0.5 10.0.0.1 10.0.0.53 & lease igb0 10.1.0.5 10.1.0.1 10.1.0.53 &
  wait
  o=$(owner)
  [[ $o == em0 || $o == igb0 ]] || fail "round $round: no single owner"
  [[ $(route_if) == "$o" && $(writes) == 1 ]] || fail "round $round: route written $(writes) times or not via $o"
  [[ $(nameservers) == "$(cand "$o" dns_ok)" ]] || fail "round $round: resolv.conf is not the owner's"
  # The loser renews: no change of owner, route or DNS.
  loser=em0; [[ $o == em0 ]] && loser=igb0
  if [[ $loser == em0 ]]; then lease em0 10.0.0.5 10.0.0.1 10.0.0.53 RENEW; else lease igb0 10.1.0.5 10.1.0.1 10.1.0.53 RENEW; fi
  [[ $(owner) == "$o" && $(writes) == 1 ]] || fail "round $round: a renewing loser took over"
done
[[ $(grep -c 'replaces none' "$work/net.log") == 1 ]] || fail 'more than one first owner'

# ---------------------------------------------------------------- 5. late link and failover

world
nic em0 no-carrier; nic wlan0 no-carrier
"$netselect" elect
[[ $(owner) == none && $(route_if) == none ]] || fail 'an offline boot published a route'
# The cable goes in after login: dhclient (already in the background) binds.
nic em0 up; gateway 10.0.0.1 em0; dns_ok 10.0.0.53
lease em0 10.0.0.5 10.0.0.1 10.0.0.53
[[ $(owner) == em0 && $(route_gw) == 10.0.0.1 ]] || fail 'late link did not become usable'
# Wi-Fi associates later still: an equal class does not take over.
nic wlan0 up; gateway 192.168.1.1 wlan0; dns_ok 192.168.1.1
lease wlan0 192.168.1.20 192.168.1.1 192.168.1.1
[[ $(owner) == em0 ]] || fail 'a later equal lease took over'
# The cable is pulled: devd's LINK_DOWN moves the route and DNS at once.
nic em0 no-carrier
"$netselect" link-down em0
[[ $(owner) == wlan0 && $(route_if) == wlan0 && $(nameservers) == 192.168.1.1 ]] || fail 'no failover on link down'
# The cable returns: em0 rebinds and waits its turn; wlan0 keeps the route.
nic em0 up
lease em0 10.0.0.5 10.0.0.1 10.0.0.53 REBOOT
[[ $(owner) == wlan0 ]] || fail 'returning link flapped the route'

# ---------------------------------------------------------------- 6. failed DHCP and DNS

world
nic em0 up; nic igb0 up; nic ue0 up
gateway 10.0.0.1 em0 noarp                 # a lease whose gateway never answers
gateway 10.1.0.1 igb0; gateway 10.2.0.1 ue0; dns_ok 10.2.0.53
start=$(date +%s)
lease em0 10.0.0.5 10.0.0.1 10.0.0.53      # dead DNS too
elapsed=$(($(date +%s) - start))
((elapsed <= NETSELECT_GATEWAY_TIMEOUT + NETSELECT_DNS_TIMEOUT + 2)) ||
  fail "a dead candidate took ${elapsed}s, over its budget"
[[ $(cand em0 class) == 1 && $(cand em0 gateway_ok) == no ]] || fail 'unproven gateway not classed 1'
[[ $(owner) == em0 ]] || fail 'the only lease was not used provisionally'
[[ $(nameservers) == 10.0.0.53 ]] || fail 'unproven DNS servers were not kept as the only choice'
lease igb0 10.1.0.5 10.1.0.1 '10.1.0.53 10.1.0.54'   # gateway answers, DNS dead
[[ $(owner) == igb0 && $(cand igb0 class) == 2 ]] || fail 'a proven gateway did not replace an unproven one'
lease ue0 10.2.0.5 10.2.0.1 '10.2.0.99 10.2.0.53'    # one of two DNS servers answers
[[ $(owner) == ue0 && $(cand ue0 class) == 3 ]] || fail 'working DNS did not win'
[[ $(nameservers) == 10.2.0.53 ]] || fail 'a dead DNS server was published beside a working one'
# igb0's DNS recovers at renewal. It was usable first, but ue0 already owns
# the route at the same class: no flap back.
dns_ok 10.1.0.53
lease igb0 10.1.0.5 10.1.0.1 '10.1.0.53 10.1.0.54' RENEW
[[ $(cand igb0 class) == 3 && $(owner) == ue0 && $(route_if) == ue0 ]] || fail 'an equal class took the route back'
grep -q 'drill -I 10.2.0.5 @10.2.0.53' "$W/calls" || fail 'DNS was not checked from the candidate address'
! grep -q 'ping .* 10.2.0.53' "$W/calls" || fail 'DNS was checked with ICMP'
# A SERVFAIL still proves the server is reachable (no public endpoint needed).
world
nic em0 up; gateway 10.0.0.1 em0; echo 10.0.0.53 >"$W/dns-servfail"
lease em0 10.0.0.5 10.0.0.1 10.0.0.53
[[ $(cand em0 class) == 3 && $(cand em0 dns_rcodes) == 10.0.0.53:SERVFAIL ]] || fail 'a reachable resolver was not recognized offline'
# The lease expires: the route goes, the record stays for diagnosis.
ended em0 EXPIRE
[[ $(owner) == none && $(route_if) == none && $(cand em0 status) == gone ]] || fail 'expired lease kept the route'

# ---------------------------------------------------------------- 7. fully offline boot

world
nic em0 no-carrier; nic wlan0 no-carrier
start=$(date +%s)
"$netselect" link-down em0; "$netselect" link-down wlan0; "$netselect" elect
(($(date +%s) - start <= 2)) || fail 'offline elect was not immediate'
[[ $(owner) == none && $(route_if) == none && $(writes) == 0 ]] || fail 'offline boot changed routes'
[[ $(nameservers) == 192.0.2.250 ]] || fail 'offline boot rewrote resolv.conf'
"$netselect" status >"$work/status"   # whole output: grep -q under pipefail could SIGPIPE it
grep -q '^owner: none' "$work/status" || fail 'status does not report offline'

# A default route that DHCP does not manage (defaultrouter=) is left alone.
world
nic em0 up; gateway 10.0.0.1 em0; dns_ok 10.0.0.53
echo '192.0.2.1 re0' >"$W/default"
lease em0 10.0.0.5 10.0.0.1 10.0.0.53
[[ $(route_if) == re0 && $(writes) == 0 ]] || fail 'a static default route was replaced'

# ---------------------------------------------------------------- 8. Apple T2 internal link

# MacBookPro16,1: the T2 controller is cdce(4) on USB 05ac:8233 (MAC
# ac:de:48:00:11:22), with a link and never a DHCP server. Here it attached
# after the USB Ethernet adapter, so it is ue1: the USB ids decide.
usb_nic() { # ueN parent [vendor product]
  echo "$2" >"$W/ue-parent.${1#ue}"
  [[ -n ${3:-} ]] && echo "vendor=$3 product=$4 devclass=0x00 devsubclass=0x00 sernum=\"0\" release=0x0201 mode=host intclass=0x02 intsubclass=0x0d intprotocol=0x00" \
    >"$W/pnp.${2#cdce}"
  return 0
}
t2_world() {
  world
  mkdir -p "$work/run"; rm -f "$work/run"/*
  nic ue0 up; nic ue1 up; nic ue2 up; nic wlan0 up
  usb_nic ue0 axe0
  usb_nic ue1 cdce0 0x05ac 0x8233; echo ac:de:48:00:11:22 >"$W/mac.ue1"
  usb_nic ue2 cdce1 0x05ac 0x12a8   # iPhone tethering: Apple and cdce, but not the T2
}
t2_world
"$t2link" is ue1 || fail 'T2 link not recognized'
for i in ue0 ue2 wlan0 em0 'ue1;x'; do "$t2link" is "$i" && fail "$i taken for the T2 link"; done
[[ $("$t2link" list) == ue1 ]] || fail "T2 list: $("$t2link" list)"
[[ $("$t2link" rc-vars) == $'ifconfig_ue1="up"\nifconfig_ue1_ipv6="inet6 -ifdisabled auto_linklocal"' ]] ||
  fail "rc-vars: $("$t2link" rc-vars)"
# rc.conf.d/network/daemonarchy-t2link, as load_rc_config sources it, against
# network.subr's ifconfig_IF lookup (get_if_var falls back to ifconfig_DEFAULT).
(
  set +u
  # shellcheck disable=SC2034 # read by the eval below, as network.subr does
  ifconfig_DEFAULT=DHCP
  # shellcheck source=/dev/null
  . <(sed "s|/usr/local/libexec/daemonarchy-t2link|$t2link|g" "$src/daemonarchy-t2link.rc.conf")
  for i in ue0 ue1 ue2; do eval "echo $i \${ifconfig_$i:-\$ifconfig_DEFAULT} \${ifconfig_${i}_ipv6:-}"; done
) >"$work/rcvars"
[[ $(cat "$work/rcvars") == $'ue0 DHCP\nue1 up inet6 -ifdisabled auto_linklocal\nue2 DHCP' ]] ||
  fail "rc.conf.d fragment gave: $(cat "$work/rcvars")"
# devd: keyed on the USB attach, never on an interface name.
# shellcheck disable=SC2016 # $device-name is devd's variable, matched literally
grep -q 'device-name[[:space:]]*"cdce\[0-9\]+"' "$src/daemonarchy-t2link.conf" &&
  grep -q 'match "vendor"[[:space:]]*"0x05ac"' "$src/daemonarchy-t2link.conf" &&
  grep -q 'match "product"[[:space:]]*"0x8233"' "$src/daemonarchy-t2link.conf" &&
  grep -qF 't2link attach $device-name' "$src/daemonarchy-t2link.conf" || fail 'devd rule is not keyed on USB 05ac:8233'
! grep -Eq '\bue[0-9]' "$src/daemonarchy-t2link.conf" "$src/daemonarchy-t2link.rc.conf" || fail 'an interface number is hard-coded'

# devd attach: the boot-time dhclient goes, IPv4 goes, IPv6 link-local comes.
printf 4242 >"$work/run/dhclient.ue1.pid"   # as dhclient writes it: no newline
echo 'dhclient: ue1 (dhclient)' >"$W/ps.4242"
echo 4343 >"$work/run/dhclient.ue0.pid"; echo 'dhclient: ue0 (dhclient)' >"$W/ps.4343"
echo 169.254.7.7 >"$W/addr.ue1"
"$t2link" attach cdce0 || fail 'attach failed'
grep -qx 'kill 4242' "$W/calls" || fail 'dhclient on the T2 link was not stopped'
! grep -q 'kill 4343' "$W/calls" || fail 'dhclient on another interface was stopped'
grep -qx 'ifconfig ue1 inet 169.254.7.7 -alias' "$W/calls" || fail 'IPv4 left on the T2 link'
grep -qx 'ifconfig ue1 inet6 -ifdisabled auto_linklocal' "$W/calls" || fail 'T2 link not IPv6 link-local'
! grep -Eq 'ifconfig ue[02] ' "$W/calls" || fail 'another interface was reconfigured'
grep -q 'ue1: Apple T2 internal link (cdce0, USB 05ac:8233), IPv6 link-local only, no DHCP' "$work/net.log" || fail 'T2 link not logged'
! grep -q 'differs from the usual' "$work/net.log" || fail 'expected MAC flagged'
# Other devices, and a T2 whose interface never appears, change nothing.
: >"$W/calls"
"$t2link" attach cdce1; "$t2link" attach axe0
[[ ! -s $W/calls ]] || fail 'attach of another USB device reconfigured something'
rm -f "$W/ue-parent.1"
! "$t2link" attach cdce0 || fail 'attach without an interface reported success'
grep -q 'cdce0: Apple T2 internal link attached, but no ue interface appeared' "$work/net.log" || fail 'missing interface not logged'
! "$t2link" configure ue0 || fail 'configure accepted a non-T2 interface'
[[ ! -s $W/calls ]] || fail 'a non-T2 interface was reconfigured'
echo cdce0 >"$W/ue-parent.1"
# An unexpected MAC is logged, not acted on.
echo 02:00:00:00:00:01 >"$W/mac.ue1"
"$t2link" configure ue1 && grep -q 'ue1: MAC 02:00:00:00:00:01 differs' "$work/net.log" || fail 'MAC cross-check'

# netselect: a lease reported for the T2 link is never a candidate, and an
# older candidate record for it is dropped and the route moves on.
t2_world
gateway 192.168.1.1 wlan0; dns_ok 192.168.1.1
gateway 169.254.1.1 ue1; dns_ok 169.254.1.53
lease ue1 169.254.1.5 169.254.1.1 169.254.1.53
[[ $(owner) == none && $(route_if) == none && ! -e $work/state/cand.ue1 ]] || fail 'the T2 link became a candidate'
grep -q 'ue1 BOUND ignored: Apple T2 internal link' "$work/net.log" || fail 'ignored T2 lease not logged'
[[ $(nameservers) == 192.0.2.250 ]] || fail 'the T2 link touched resolv.conf'
lease wlan0 192.168.1.20 192.168.1.1 192.168.1.1
[[ $(owner) == wlan0 && $(route_if) == wlan0 ]] || fail 'Wi-Fi beside the T2 link did not get the route'
printf 'status=lease\naddress=169.254.1.5\ngateway=169.254.1.1\nclass=3\nseq=0\n' >"$work/state/cand.ue1"
"$netselect" elect
[[ $(owner) == wlan0 ]] || fail 'a stale T2 candidate was elected'
lease ue1 169.254.1.5 169.254.1.1 169.254.1.53 RENEW
[[ ! -e $work/state/cand.ue1 && $(owner) == wlan0 ]] || fail 'stale T2 candidate kept'
"$t2link" configure ue1
"$netselect" status >"$work/status"
grep -qx 'ue1: Apple T2 internal link (cdce0, USB 05ac:8233, MAC ac:de:48:00:11:22): IPv6 link-local fe80::aede:48ff:fe00:1122%ue1, IPv4 none, dhclient none; never a route or DNS candidate' "$work/status" ||
  fail "status: $(cat "$work/status")"

# ---------------------------------------------------------------- dhclient hooks

# The hooks replace dhclient-script's default-route and resolv.conf steps and
# pass every result on. The surrounding functions mirror dhclient-script's.
world
hooks=$work/hooks; mkdir -p "$hooks"
for h in enter exit; do
  sed "s|/usr/local/libexec/daemonarchy-netselect|$work/bin/netselect-record|g" "$src/dhclient-$h-hooks" >"$hooks/$h"
done
shim netselect-record <<'EOF'
#!/bin/sh
printf '%s|' "$@" >>"$W/netselect-args"; echo >>"$W/netselect-args"
EOF
(
  set +u
  route() { echo "route $*" >>"$W/calls"; }
  arp_flush() { :; }
  is_default_interface() { return 0; }
  add_new_resolv_conf() { echo UNSAFE-resolv >>"$W/calls"; }
  fill_classless_routes() { # as dhclient-script: "24 10 9 8 10 0 0 1" -> pairs
    set -- $1
    while [ $# -ge 5 ]; do
      if [ "$1" -eq 0 ]; then route=default; shift; else route="$2.$3.$4.0/$1"; shift 4; fi
      router="$1.$2.$3.$4"; shift 4
      classless_routes="$classless_routes $route $router"
    done
  }
  # shellcheck source=/dev/null
  . "$hooks/enter"
  interface=em0 new_classless_routes='24 10 9 8 10 0 0 1 0 10 0 0 254' new_static_routes='' new_routers=10.0.0.1
  add_new_routes
  is_default_interface && echo UNSAFE-default >>"$W/calls"
  add_new_resolv_conf
  old_classless_routes=$new_classless_routes
  delete_old_routes
  reason=BOUND exit_status=0 new_ip_address=10.0.0.5 new_domain_name_servers='10.0.0.53 10.0.0.54' new_domain_name=example.test
  # shellcheck source=/dev/null
  . "$hooks/exit"
)
grep -q 'route add 10.9.8.0/24 10.0.0.1' "$W/calls" || fail 'hooks dropped a classless route'
grep -q 'route delete 10.9.8.0/24 10.0.0.1' "$W/calls" || fail 'hooks did not remove an old classless route'
! grep -q 'route .*default' "$W/calls" || fail 'dhclient-script still touches the default route'
! grep -q UNSAFE "$W/calls" || fail 'dhclient-script still owns the default route or resolv.conf'
[[ $(cat "$W/netselect-args") == 'lease|em0|BOUND|0|10.0.0.5|10.0.0.254|10.0.0.53 10.0.0.54|example.test|' ]] ||
  fail "exit hook passed $(cat "$W/netselect-args")"

# Optionally, inside FreeBSD's own dhclient-script.
if [[ -n ${DHCLIENT_SCRIPT:-} ]]; then
  world
  nic em0 up
  real=$work/dhclient-script
  sed -e "s|/etc/dhclient-enter-hooks|$hooks/enter|g" -e "s|/etc/dhclient-exit-hooks|$hooks/exit|g" \
    -e "s|^IFCONFIG=.*|IFCONFIG='ifconfig'|" -e "s|^ARP=.*|ARP=arp|" -e "s|^HOSTNAME=.*|HOSTNAME=true|" \
    -e "s|/sbin/resolvconf|echo UNSAFE-resolvconf >>$W/calls; true|g" -e "s|/var/run/|$work/run-|g" \
    "$DHCLIENT_SCRIPT" >"$real"
  shim logger <<'EOF'
#!/bin/sh
exit 0
EOF
  : >"$W/netselect-args"
  for reason in BOUND RENEW EXPIRE; do
    env -i PATH="$PATH" W="$W" reason=$reason interface=em0 new_ip_address=10.0.0.5 new_subnet_mask=255.255.255.0 \
      new_broadcast_address=10.0.0.255 new_routers=10.0.0.1 new_domain_name_servers=10.0.0.53 \
      new_domain_name=example.test old_ip_address=10.0.0.5 sh "$real" || fail "dhclient-script $reason failed"
  done
  ! grep -q 'route .*default\|UNSAFE' "$W/calls" || fail 'the real dhclient-script still publishes route or DNS'
  [[ $(grep -c '^lease|em0|' "$W/netselect-args") == 3 ]] || fail 'real dhclient-script did not hand over every result'
  echo 'PASS: hooks inside FreeBSD dhclient-script'
fi

echo 'PASS: installed boot selects the first usable interface with one route/DNS owner, bounded checks and late-link recovery'
