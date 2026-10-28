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

sh -n "$src/daemonarchy-netselect" "$src/dhclient-enter-hooks" "$src/dhclient-exit-hooks"
command -v flock >/dev/null || fail 'flock(1) is needed for the lockf shim'

# ---------------------------------------------------------------- shims

mkdir -p "$work/bin"
shim() { cat >"$work/bin/$1"; chmod +x "$work/bin/$1"; }
shim ifconfig <<'EOF'
#!/bin/sh
ifc=$1
[ -f "$W/link.$ifc" ] || { echo "ifconfig: interface $ifc does not exist" >&2; exit 1; }
if [ "$2" = inet ]; then
	[ -f "$W/addr.$ifc" ] && printf '\tinet %s netmask 0xffffff00 broadcast 192.0.2.255\n' "$(cat "$W/addr.$ifc")"
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
[ "$*" = '-n kern.boottime' ] && echo "{ sec = $(cat "$W/boot"), usec = 0 } Tue Oct 27 09:00:00 2026"
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
chmod +x "$netselect"
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
[[ $(awk '/^  wifi\)/,/;;/' "$install" | grep -c installed_boot_dhcp) == 1 ]] || fail 'Wi-Fi install lacks the boot settings'
[[ $(awk '/^  \*\)/,/;;/' "$install" | grep -c installed_boot_dhcp) == 1 ]] || fail 'DHCP install lacks the boot settings'
[[ $(awk '/^  static\)/,/;;/' "$install" | grep -c installed_boot_dhcp) == 0 ]] || fail 'static install got DHCP settings'
grep -q 'LINK_DOWN' "$src/daemonarchy-netselect.conf" || fail 'no devd link-down rule'

# The installer function itself, run against a scratch target.
TARGET=$work/target ISO_SHARE=$here/overlay/usr/local/share/daemonarchy-installer
mkdir -p "$TARGET/etc"; : >"$TARGET/etc/rc.conf"
# shellcheck source=/dev/null
source "$work/installed_boot_dhcp"
installed_boot_dhcp
for f in usr/local/libexec/daemonarchy-netselect etc/dhclient-enter-hooks etc/dhclient-exit-hooks \
  usr/local/etc/devd/daemonarchy-netselect.conf usr/local/etc/newsyslog.conf.d/daemonarchy-net.conf; do
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

# The MacBookPro16,1 case: ue0 has a link but no DHCP server; wlan0 works.
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
"$netselect" status | grep -q '^owner: none' || fail 'status does not report offline'

# A default route that DHCP does not manage (defaultrouter=) is left alone.
world
nic em0 up; gateway 10.0.0.1 em0; dns_ok 10.0.0.53
echo '192.0.2.1 re0' >"$W/default"
lease em0 10.0.0.5 10.0.0.1 10.0.0.53
[[ $(route_if) == re0 && $(writes) == 0 ]] || fail 'a static default route was replaced'

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
