#!/usr/bin/env bash
# Exercise the installer's proactive network pipeline (NET-001) against a
# shimmed FreeBSD network: ifconfig, dhclient, route, arp, drill, sntp,
# ntpdate, fwget, pkg, devmatch and sysctl answer from fixture files, and
# nothing touches the host's adapters, resolver or clock.
# Variables below configure the sourced pipeline or are read back from it.
# shellcheck disable=SC2034,SC1090
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lib=$here/overlay/usr/local/libexec/daemonarchy-installer
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

fail() { echo "FAIL: $*" >&2; [[ -f $NB_LOG ]] && tail -n 40 "$NB_LOG" >&2; exit 1; }

export ISO_SHARE=$work/share NB_REPO=$work/share/repo
mkdir -p "$ISO_SHARE/repo/All" "$ISO_SHARE/secureboot"
: >"$ISO_SHARE/secureboot/certificate.pem"   # validity comes from the openssl shim
# shellcheck source=/dev/null
source "$lib/network-bringup"
set +e  # the library runs without errexit, as the installer does
set -u

# ---------------------------------------------------------------- fixtures

world() { # reset the simulated machine
  NB_STATE=$work/state NB_LOG=$work/state/log NB_RESOLV_CONF=$work/resolv.conf
  NB_BOOT_LEASES=$work/boot-leases NB_DHCLIENT_PIDDIR=$work/run NB_DHCP_TIMEOUT=20
  NB_EXTRA_DNS='' net_mode='' net_if='' net_addr='' net_gw='' net_dns=''
  wifi_ssid='' wifi_psk='' wifi_hidden=false wifi_enterprise_profile=''
  rm -rf "$work/state" "$work/w" "$work/resolv.conf" "$work/boot-leases" "$work/target"
  mkdir -p "$work/w" "$work/boot-leases" "$work/run"
  printf 'nameserver 192.0.2.250\n' >"$work/resolv.conf"
  : >"$work/w/ether"; : >"$work/w/radios"; : >"$work/w/pciconf"
  : >"$work/w/dns-ok"; : >"$work/w/calls"; : >"$work/w/unbounded"
  echo "$floor" >"$ISO_SHARE/build-epoch"
  echo $((floor + 86400)) >"$work/w/now"
  echo $((floor + 10 * 365 * 86400)) >"$work/w/cert-until"
  rm -f "$work/w/ntp-ok"
}
floor=1792000000   # 2026-10-14
call() { printf '%s\n' "$*" >>"$work/w/calls"; }
bounded() { [[ -n ${NB_TEST_BOUNDED:-} ]] || printf '%s\n' "$*" >>"$work/w/unbounded"; }
nic() { # name link [address router dns ntp arp]
  echo "$1" >>"$work/w/ether"
  echo "$2" >"$work/w/link.$1"
  if [[ -n ${3:-} ]]; then
    printf '%s|%s|%s|%s\n' "$3" "$4" "${5:-}" "${6:-}" >"$work/w/offer.$1"
    [[ ${7:-yes} == yes ]] && echo "$1" >"$work/w/arp.$4"
  fi
  return 0
}
dns_ok() { printf '%s\n' "$@" >>"$work/w/dns-ok"; }

timeout() { local limit=$1; shift; NB_TEST_BOUNDED=$limit "$@"; }
sleep() { :; }
nb_now() { cat "$work/w/now"; }
ifconfig() {
  case "$*" in
    '-l ether') tr '\n' ' ' <"$work/w/ether"; echo ;;
    -C) echo 'bridge epair gif lo tap tun vlan wlan' ;;
    *' inet') [[ -f $work/w/addr.$1 ]] && printf '\tinet %s netmask 0xffffff00\n' "$(cat "$work/w/addr.$1")"; return 0 ;;
    *' up') [[ $2 == inet ]] && { call "ifconfig $*"; echo "${3%/*}" >"$work/w/addr.$1"; }; return 0 ;;
    'wlan0 destroy') rm -f "$work/w/wlan-parent"; return 0 ;;
    'wlan0 create wlandev '*) call "ifconfig $*"; echo "$4" >"$work/w/wlan-parent" ;;
    *)
      [[ $# == 1 ]] || return 0
      case $(cat "$work/w/link.$1" 2>/dev/null) in
        up) printf '\tstatus: active\n' ;;
        down) printf '\tstatus: no carrier\n' ;;
      esac
      ;;
  esac
}
dhclient() {
  bounded dhclient "$@"
  local ifc=${!#} lease=$4 address router dns ntp
  call "dhclient $ifc"
  command sleep 1   # a real delay: concurrent probes overlap
  [[ -f $work/w/offer.$ifc ]] || return 0
  IFS='|' read -r address router dns ntp <"$work/w/offer.$ifc"
  echo "$address" >"$work/w/addr.$ifc"
  {
    echo 'lease {'
    printf '  interface "%s";\n  fixed-address %s;\n  option routers %s;\n' "$ifc" "$address" "$router"
    [[ -n $dns ]] && printf '  option domain-name-servers %s;\n' "$dns"
    [[ -n $ntp ]] && printf '  option ntp-servers %s;\n' "$ntp"
    printf '  option domain-name "example.test";\n}\n'
  } >"$lease"
}
route() {
  case "$*" in
    '-n get default') [[ -f $work/w/default ]] && echo "  interface: $(cat "$work/w/default")"; return 0 ;;
    '-q delete default') rm -f "$work/w/default" ;;
    '-q add default '*)
      call "route add default $4"
      local ifc
      for ifc in $(cat "$work/w/ether"); do
        [[ -f $work/w/offer.$ifc ]] && [[ $(cut -d'|' -f2 "$work/w/offer.$ifc") == "$4" ]] && echo "$ifc" >"$work/w/default"
      done
      [[ $4 == 192.0.2.1 ]] && echo em0 >"$work/w/default"
      return 0
      ;;
  esac
}
ping() { call "ping ${!#}"; return 1; }   # every host on this network drops ICMP
arp() {
  if [[ -f $work/w/arp.$2 ]]; then echo "? ($2) at 00:11:22:33:44:55 on $(cat "$work/w/arp.$2") expires in 1200 seconds [ethernet]"
  else echo "? ($2) at (incomplete) on em0 expired [ethernet]"; fi
}
drill() {
  bounded drill "$@"
  local server=${1#@}
  call "drill $server $2 $3"
  if grep -qx "$server" "$work/w/dns-ok"; then
    printf ';; ->>HEADER<<- opcode: QUERY, rcode: NOERROR, id: 4711\n;; ANSWER SECTION:\n'
    printf '%s.\t300\tIN\tCNAME\tpkgmir.geo.freebsd.org.\npkgmir.geo.freebsd.org.\t60\tIN\tA\t203.0.113.7\n' "$2"
  elif [[ -f $work/w/servfail.$server ]]; then
    printf ';; ->>HEADER<<- opcode: QUERY, rcode: SERVFAIL, id: 4711\n'
  else
    echo 'Error: error sending query: Could not send or receive, because of network error'; return 1
  fi
}
sntp() {
  bounded sntp "$@"
  call "sntp ${!#}"
  [[ -f $work/w/ntp-ok ]] || return 1
  echo $((floor + 2 * 86400)) >"$work/w/now"
}
ntpdate() { bounded ntpdate "$@"; call "ntpdate ${!#}"; return 1; }
openssl() { (($(nb_now) < $(cat "$work/w/cert-until"))); }
sysctl() {
  case "$*" in
    '-n net.wlan.devices') tr '\n' ' ' <"$work/w/radios" ;;
    '-n net.wlan.0.%parent') cat "$work/w/wlan-parent" 2>/dev/null ;;
    '-n kern.module_path') echo '/boot/kernel;/boot/modules' ;;
    kern.module_path=*) call "sysctl $*" ;;
    -n\ dev.*.%desc) echo "Adapter ${2#dev.}" ;;
    *) return 1 ;;
  esac
}
devinfo() { [[ $2 == ue* ]] && echo "$2 uhub1 usbus0 xhci0 pci0"; return 0; }
pciconf() { cat "$work/w/pciconf"; }
usbconfig() { return 0; }
devmatch() { bounded devmatch "$@"; cat "$work/w/devmatch" 2>/dev/null; }
kldload() {
  call "kldload ${!#}"
  [[ ${!#} == "$(cat "$work/w/radio-driver" 2>/dev/null)" ]] && echo rtw890 >>"$work/w/radios"
  return 0
}
devctl() { call "devctl $*"; }
ps() { echo "dhclient: ${work##*/} (dhclient)"; }
kill() { :; }
fwget() { bounded fwget "$@"; cat "$work/w/fwget" 2>/dev/null; }
pkg() {
  if [[ $1 == info ]]; then grep -qx "$3" "$work/w/installed" 2>/dev/null; return; fi
  bounded pkg "$@"
  local dest name
  call "pkg $*"
  while (($#)); do case $1 in -o) [[ $2 == */* && $2 != *=* ]] && dest=$2; shift 2 ;; fetch|-y) shift ;; *) name=$1; shift ;; esac; done
  mkdir -p "$dest/All"
  : >"$dest/All/$name-20261001.pkg"
}
tar() {
  local file=$2 root=$4 name
  name=${file##*/}; name=${name%-[0-9]*}
  mkdir -p "$root/boot/modules"
  : >"$root/boot/modules/$name.ko"
}
apple_firmware_hardware() { return 1; }
gum() { echo "gum $*" >>"$work/w/prompted"; return 1; }
called() { grep -q -- "$1" "$work/w/calls"; }
steps_in_order() { grep -o '== [a-z-]* begins' "$NB_LOG" | awk '{ print $2 }' | tr '\n' ' '; }

# ---------------------------------------------------------------- 1. discovery

world
nic em0 up; nic igb0 up; nic ue0 up
for pseudo in bridge0 tap0 vlan5 epair0a; do echo "$pseudo" >>"$work/w/ether"; done
echo iwlwifi0 >"$work/w/radios"
cat >"$work/w/pciconf" <<'PCI'
none2@pci0:3:0:0:	class=0x028000 rev=0x01 hdr=0x00 vendor=0x14e4 device=0x4464 subvendor=0x106b subdevice=0x07bf
    vendor     = 'Broadcom Inc. and subsidiaries'
    device     = 'BCM4364 802.11ac Wireless Network Adapter'
    class      = network
em0@pci0:0:31:6:	class=0x020000 rev=0x10 hdr=0x00 vendor=0x8086 device=0x15fa
    vendor     = 'Intel Corporation'
    class      = network
none5@pci0:5:0:0:	class=0x0c0330 rev=0x01 hdr=0x00 vendor=0x1912 device=0x0014
    class      = serial bus
PCI
nb_reset; nb_discover
[[ $(cut -f1 "$NB_STATE/interfaces" | tr '\n' ' ') == 'em0 igb0 ue0 ' ]] || fail 'pseudo interfaces were offered'
[[ $(awk -F '\t' '$1 == "ue0" { print $2 }' "$NB_STATE/interfaces") == usb ]] || fail 'ue0 is not USB tethering'
grep -q 'Found 4 network adapter(s)' "$NB_STATE/report.discover" || fail 'adapter count'
grep -q 'iwlwifi0 (Wi-Fi)' "$NB_STATE/report.discover" || fail 'wireless radio not reported'
grep -q 'ue0 (USB network or tethering' "$NB_STATE/report.discover" || fail 'tethering not described'
grep -q "BCM4364 802.11ac Wireless Network Adapter (pci0:3:0:0) has no driver" "$NB_STATE/report.discover" ||
  fail 'driverless wireless device not reported'
grep -Eq 'bridge0|tap0|vlan5|epair0a|lo0|0c0330' "$NB_STATE/report.discover" "$NB_STATE/unattached" && fail 'pseudo or non-network device shown'
nb_valid_ipv4 192.168.1.1 && ! nb_valid_ipv4 300.1.1.1 && ! nb_valid_ipv4 127.0.0.1 &&
  ! nb_valid_ipv4 1.2.3 && ! nb_valid_ipv4 '1.1.1.1; rm' || fail 'IPv4 validation'

# ---------------------------------------------------------------- 2. several NICs, one DHCP

world
nic em0 down
nic igb0 up 192.168.7.20 192.168.7.1 192.168.7.53 192.168.7.123
nic ix0 up
nic ue0 up 172.20.10.2 172.20.10.1 172.20.10.1
nb_reset; nb_discover
start=$SECONDS
nb_dhcp || fail 'no primary chosen'
((SECONDS - start < 3)) || fail "DHCP probes ran one after another ($((SECONDS - start)) s)"
[[ $(nb_get primary) == igb0 ]] || fail "primary is $(nb_get primary), not the wired lease"
called 'dhclient em0' && fail 'probed a port with no cable'
called 'dhclient ix0' || fail 'did not probe ix0'
[[ $(grep -c '^route add default' "$work/w/calls") == 1 ]] || fail 'default route set more than once'
called 'route add default 192.168.7.1' || fail 'default route not via primary gateway'
grep -q 'em0: no cable connected' "$NB_STATE/report.dhcp" || fail 'no-cable not reported'
grep -q 'ix0: no DHCP answer within 20 seconds' "$NB_STATE/report.dhcp" || fail 'no-lease not reported'
grep -q 'igb0: address 192.168.7.20, gateway 192.168.7.1, DNS 192.168.7.53' "$NB_STATE/report.dhcp" || fail 'lease details'
[[ $(nb_kv igb0 ntp) == 192.168.7.123 && $(nb_kv ue0 gateway_ok) == yes ]] || fail 'lease record'
[[ -s $work/w/unbounded ]] && fail "unbounded command: $(cat "$work/w/unbounded")"
# A user override, and a retry that keeps the lease it already holds.
nb_step primary ue0 && [[ $(nb_get primary) == ue0 ]] || fail 'override'
: >"$work/w/calls"
nb_dhcp
called 'dhclient igb0' && fail 'retry discarded an existing lease'
[[ $(nb_get primary) == igb0 ]] || fail 'retry changed the primary'
# The working gateway wins over a lease whose gateway never answers ARP.
world
nic em0 up 10.1.0.5 10.1.0.1 '' '' no
nic em1 up 10.2.0.5 10.2.0.1
nb_reset; nb_discover; nb_dhcp
[[ $(nb_get primary) == em1 ]] || fail 'chose a lease without a working gateway'
grep -q 'em0: address 10.1.0.5, gateway 10.1.0.1 (gateway did not answer)' "$NB_STATE/report.dhcp" || fail 'dead gateway not reported'

# ---------------------------------------------------------------- 3. DNS

world
nic igb0 up 192.168.7.20 192.168.7.1 192.168.7.53
dns_ok 1.1.1.1 8.8.8.8 9.9.9.9
nb_reset; nb_discover; nb_dhcp; nb_dns || fail 'public DNS not used when DHCP DNS is broken'
called 'drill 192.168.7.53 pkg.FreeBSD.org A' || fail 'DHCP DNS was not tried'
[[ $(nb_get dns) == 1.1.1.1,8.8.8.8,9.9.9.9 && $(nb_get dns_source) == public ]] || fail "dns $(nb_get dns)"
grep -q "network's DNS server 192.168.7.53 did not answer" "$NB_STATE/report.dns" || fail 'broken DHCP DNS not reported'
[[ $(grep -c '^nameserver' "$NB_RESOLV_CONF") == 3 ]] && grep -qx 'nameserver 1.1.1.1' "$NB_RESOLV_CONF" &&
  grep -qx 'search example.test' "$NB_RESOLV_CONF" || fail 'resolv.conf not written'
# ICMP is blocked everywhere; no DNS server was pinged, yet queries succeed.
grep -E '^ping (1\.1\.1\.1|1\.0\.0\.1|8\.8\.8\.8|8\.8\.4\.4|9\.9\.9\.9|192\.168\.7\.53)$' "$work/w/calls" && fail 'pinged a DNS server'
# Working DHCP DNS is preferred and labeled as the network's own.
dns_ok 192.168.7.53
nb_dns && [[ $(nb_get dns) == 192.168.7.53,1.1.1.1,8.8.8.8 && $(nb_get dns_source) == dhcp ]] || fail 'DHCP DNS not first'
# A server that answers SERVFAIL is not a working resolver.
world
nic igb0 up 192.168.7.20 192.168.7.1 192.168.7.53
touch "$work/w/servfail.192.168.7.53"; dns_ok 9.9.9.9
nb_reset; nb_discover; nb_dhcp; nb_dns && [[ $(nb_get dns) == 9.9.9.9 ]] || fail 'SERVFAIL accepted'
# A DHCP renewal that rewrites resolv.conf is undone before downloads.
printf 'nameserver 192.168.7.53\n' >"$NB_RESOLV_CONF"
nb_dns_ensure; grep -qx 'nameserver 9.9.9.9' "$NB_RESOLV_CONF" || fail 'dns-ensure did not restore servers'

# All public DNS blocked: unattended fails clearly; a user server must answer.
world
nic igb0 up 192.168.7.20 192.168.7.1 192.168.7.53
nb_reset; nb_discover; nb_dhcp
nb_dns && fail 'accepted DNS with nothing answering'
grep -q 'None of 6 DNS servers answered' "$NB_STATE/report.dns" || fail 'blocked DNS not explained'
nb_dns_user 300.1.1.1; [[ $? == 2 ]] || fail 'invalid user DNS syntax accepted'
nb_dns_user 10.0.0.99 && fail 'accepted a user DNS server that does not answer'
grep -qx 'nameserver 192.0.2.250' "$NB_RESOLV_CONF" || fail 'resolv.conf changed by a failed server'
dns_ok 10.0.0.53
nb_dns_user 10.0.0.53 && [[ $(nb_get dns) == 10.0.0.53 && $(nb_get dns_source) == user ]] || fail 'answering user DNS refused'
grep -qx 'nameserver 10.0.0.53' "$NB_RESOLV_CONF" || fail 'user DNS not written'

# ---------------------------------------------------------------- 4. clock

world
nic igb0 up 192.168.7.20 192.168.7.1 '' 192.168.7.123
nb_reset; nb_discover; nb_dhcp
[[ $(nb_clock_status) == usable ]] || fail 'correct clock rejected'
echo $((floor - 365 * 86400)) >"$work/w/now"
[[ $(nb_clock_status) == before-build ]] || fail 'clock before the build accepted'
touch "$work/w/ntp-ok"
nb_clock && [[ $(nb_get clock) == synchronized ]] || fail 'bad clock not fixed by network time'
head -n 1 < <(grep '^sntp' "$work/w/calls") | grep -qx 'sntp 192.168.7.123' || fail 'DHCP NTP server not tried first'
grep -q 'before this image was built' "$NB_STATE/report.clock" || fail 'wrong clock not explained'
# Sync failing: the step fails and the front-end's manual hook decides.
rm -f "$work/w/ntp-ok"; : >"$work/w/calls"
echo $((floor - 86400)) >"$work/w/now"
nb_clock; [[ $? == 1 && $(nb_get clock) == wrong ]] || fail 'failed sync reported success'
called 'ntpdate pool.ntp.org' || fail 'ntpdate fallback not tried'
grep -q 'Network time synchronization did not answer' "$NB_STATE/report.clock" || fail 'sync failure not explained'
# A clock past the signing certificate is wrong; if network time agrees, the image expired.
echo $((floor + 86400)) >"$work/w/now"; echo "$floor" >"$work/w/cert-until"
[[ $(nb_clock_status) == certificate-expired ]] || fail 'expired certificate window accepted'
echo $((floor + 3 * 86400)) >"$work/w/cert-until"; echo $((floor + 9 * 86400)) >"$work/w/now"
touch "$work/w/ntp-ok"
nb_clock; [[ $? == 0 ]] || fail 'network time inside certificate validity rejected'

# ---------------------------------------------------------------- 5. firmware

firmware_world() {
  world
  nic igb0 up 192.168.7.20 192.168.7.1
  dns_ok 1.1.1.1
  echo 'Needed packages: wifi-firmware-rtw89-kmod-rtw8852b gpu-firmware-amd-kmod-navy-flounder' >"$work/w/fwget"
  nb_reset; nb_discover; nb_dhcp; nb_dns
}
firmware_world
echo wifi-firmware-rtw89-kmod-rtw8852b >"$work/w/installed"
nb_firmware || fail 'present firmware reported as missing'
called '^pkg ' && fail 'downloaded firmware that is already present'
grep -q 'Every attached device has the firmware it needs' "$NB_STATE/report.firmware" || fail 'present firmware not reported'
grep -q 'Graphics firmware (gpu-firmware-amd-kmod-navy-flounder)' "$NB_STATE/report.firmware" || fail 'GPU firmware not explained'
firmware_world
: >"$ISO_SHARE/repo/All/wifi-firmware-rtw89-kmod-rtw8852b-20260901.pkg"
nb_firmware || fail 'media firmware not used'
called '^pkg ' && fail 'downloaded firmware that is on the media'
called 'kldload .*/wifi-firmware-rtw89-kmod-rtw8852b.ko' || fail 'media firmware not loaded'
grep -q 'Loaded wifi-firmware-rtw89-kmod-rtw8852b from the installer media' "$NB_STATE/report.firmware" || fail 'media load not reported'
rm -f "$ISO_SHARE/repo/All/"*.pkg
firmware_world
nb_firmware || fail 'missing firmware not downloaded'
grep -q '^pkg .*fetch -y -o .* wifi-firmware-rtw89-kmod-rtw8852b$' "$work/w/calls" || fail 'pkg fetch not used'
grep '^pkg ' "$work/w/calls" | grep -q gpu-firmware && fail 'downloaded GPU firmware for the live system'
called 'sysctl kern.module_path=.*firmware/root/boot/modules' || fail 'firmware module path not added'
grep -q 'Downloaded and loaded wifi-firmware-rtw89-kmod-rtw8852b' "$NB_STATE/report.firmware" || fail 'download not reported'
[[ -s $work/w/unbounded ]] && fail "unbounded command: $(cat "$work/w/unbounded")"
# Offline (no DNS yet): nothing is fetched; the step says it will retry.
firmware_world; nb_set dns ''
nb_firmware && fail 'offline firmware step claimed success'
called '^pkg ' && fail 'fetched without a network'
grep -q 'will be downloaded once the network works' "$NB_STATE/report.firmware" || fail 'offline deferral not reported'
# MacBook: offline Apple sources first; download only when they fail and the network works.
firmware_world; : >"$work/w/fwget"
apple_attached=false
apple_firmware_hardware() { return 0; }
apple_firmware_radio_attached() { $apple_attached; }
apple_firmware_preloaded() { return 1; }
apple_firmware_prepare_internal() { call apple-internal; return 1; }
apple_firmware_prepare_media() { call apple-media; return 1; }
apple_firmware_prepare() { call "apple-$1"; apple_attached=true; }
nb_firmware || fail 'Apple download path failed'
[[ $(grep '^apple-' "$work/w/calls" | tr '\n' ' ') == 'apple-internal apple-media apple-download ' ]] ||
  fail "Apple sources out of order: $(grep '^apple-' "$work/w/calls" | tr '\n' ' ')"
apple_firmware_hardware() { return 1; }

# ---------------------------------------------------------------- 6/7. Wi-Fi first

world
nic em0 down
echo if_rtw89 >"$work/w/devmatch"; echo if_rtw89 >"$work/w/radio-driver"
dns_ok 9.9.9.9
wifi_ssid=HomeNet wifi_psk=secret
wifi_connect() {
  [[ $1 == HomeNet && $2 == secret && $(cat "$work/w/wlan-parent") == rtw890 ]] || return 1
  echo 10.9.0.5 >"$work/w/addr.wlan0"
  printf 'lease {\n  fixed-address 10.9.0.5;\n  option routers 10.9.0.1;\n  option domain-name-servers 10.9.0.1;\n}\n' \
    >"$NB_BOOT_LEASES/dhclient.leases.wlan0"
  echo wlan0 >"$work/w/arp.10.9.0.1"
}
echo $((floor - 86400)) >"$work/w/now"; touch "$work/w/ntp-ok"
nb_pipeline || fail "Wi-Fi-first pipeline failed: $(nb_get failure)"
[[ $(steps_in_order) == 'discover dhcp wifi-prepare wifi-join dns clock firmware ' ]] ||
  fail "Wi-Fi-first order: $(steps_in_order)"
called 'kldload if_rtw89' && called 'ifconfig wlan0 create wlandev rtw890' || fail 'driver or wlan0 not prepared'
[[ $(nb_get primary) == wlan0 && $(nb_get dns) == 9.9.9.9 && $(nb_get clock) == synchronized ]] ||
  fail 'checks did not rerun over Wi-Fi'
called 'sntp 10.9.0.1' && fail 'used an NTP server the Wi-Fi lease did not offer'
[[ -e $work/w/prompted ]] && fail 'the unattended pipeline prompted'
# With a wired lease, checks run first and Wi-Fi radios are prepared after firmware.
world
nic igb0 up 192.168.7.20 192.168.7.1
dns_ok 1.1.1.1
echo iwlwifi0 >"$work/w/radios"
nb_pipeline || fail "wired pipeline failed: $(nb_get failure)"
[[ $(steps_in_order) == 'discover dhcp dns clock firmware wifi-prepare ' ]] || fail "wired order: $(steps_in_order)"
grep -q 'Wi-Fi radio ready: iwlwifi0' "$NB_STATE/report.wifi-prepare" || fail 'radio not prepared'

# ---------------------------------------------------------------- unattended

world
nic em0 down
nic igb0 up 192.168.7.20 192.168.7.1 192.168.7.53
nic ix0 up
dns_ok 1.1.1.1 8.8.8.8
conf=$work/install.conf
printf 'username=test\nhostname=box\n' >"$conf"
(nb_auto "$conf") >"$work/out" 2>&1 || fail "unattended run failed: $(cat "$work/out")"
grep -q '  network: Primary connection: igb0.' "$work/out" || fail 'unattended progress not shown'
(source "$conf"; [[ $net_if == igb0 && $net_dns == 1.1.1.1,8.8.8.8 && $net_dns_source == public ]]) ||
  fail "answers not recorded: $(cat "$conf")"
[[ -e $work/w/prompted ]] && fail 'unattended run prompted'
# Configured values are honored: a static address and its own DNS server.
world
echo em0 >"$work/w/ether"; echo up >"$work/w/link.em0"
dns_ok 192.0.2.53 1.1.1.1
printf 'net_mode=static\nnet_if=em0\nnet_addr=192.0.2.10/24\nnet_gw=192.0.2.1\nnet_dns=192.0.2.53\n' >"$conf"
(nb_auto "$conf") >"$work/out" 2>&1 || fail "unattended static failed: $(cat "$work/out")"
called dhclient && fail 'probed DHCP for a static configuration'
called 'route add default 192.0.2.1' || fail 'static gateway not applied'
(source "$conf"; [[ $net_dns == 192.0.2.53,1.1.1.1 && $net_dns_source == static ]]) || fail "static DNS: $(cat "$conf")"
# A static resolver that does not answer is replaced by public DNS, labeled as such.
world
echo em0 >"$work/w/ether"; echo up >"$work/w/link.em0"
dns_ok 1.1.1.1
printf 'net_mode=static\nnet_if=em0\nnet_addr=192.0.2.10/24\nnet_gw=192.0.2.1\nnet_dns=192.0.2.53\n' >"$conf"
(nb_auto "$conf") >"$work/out" 2>&1 || fail "unattended static fallback failed: $(cat "$work/out")"
(source "$conf"; [[ $net_dns == 1.1.1.1 && $net_dns_source == public ]]) || fail "static fallback DNS: $(cat "$conf")"
# A configured interface without a lease, or no DNS at all, fails clearly.
world
nic igb0 up 192.168.7.20 192.168.7.1; nic ix0 up; dns_ok 1.1.1.1
printf 'net_if=ix0\n' >"$conf"
(nb_auto "$conf") >"$work/out" 2>&1 && fail 'accepted a configured interface without a lease'
grep -q 'The requested interface ix0 has no DHCP lease' "$work/out" || fail 'forced interface failure unclear'
world
nic igb0 up 192.168.7.20 192.168.7.1
printf 'username=test\n' >"$conf"
(nb_auto "$conf") >"$work/out" 2>&1 && fail 'unattended run accepted no DNS'
grep -q 'Network setup failed: No DNS server answered. Set net_dns' "$work/out" || fail "DNS failure unclear: $(cat "$work/out")"
grep -q "Diagnostic log: $NB_LOG" "$work/out" || fail 'log location not given'
world
nic igb0 up 192.168.7.20 192.168.7.1; dns_ok 1.1.1.1
echo $((floor - 86400)) >"$work/w/now"
(nb_auto "$conf") >"$work/out" 2>&1 && fail 'unattended run accepted a wrong clock'
grep -q 'The system clock is wrong and network time did not answer' "$work/out" || fail 'clock failure unclear'
world
(nb_auto "$conf") >"$work/out" 2>&1 && fail 'unattended run without adapters succeeded'
grep -q 'no Wi-Fi radio is available' "$work/out" || fail 'no-adapter failure unclear'
[[ -e $work/w/prompted ]] && fail 'unattended failure prompted'
# Interactive front-ends supply the prompts: a user DNS that answers on the second try.
world
nic igb0 up 192.168.7.20 192.168.7.1
dns_ok 10.0.0.53
nb_hook_dns_prompt() { nb_dns_user 10.0.0.99 || nb_dns_user 10.0.0.53; }
nb_pipeline || fail 'prompted DNS was not accepted'
[[ $(nb_get dns_source) == user ]] || fail 'user DNS not recorded'
# Sync failure then a manual clock through the front-end's hook.
world
nic igb0 up 192.168.7.20 192.168.7.1; dns_ok 1.1.1.1
echo $((floor - 86400)) >"$work/w/now"
nb_hook_clock_prompt() { echo $((floor + 86400)) >"$work/w/now"; [[ $(nb_clock_status) == usable ]]; }
nb_pipeline || fail 'manual clock after failed sync not accepted'
called 'sntp pool.ntp.org' || fail 'manual clock offered before network time'

# ---------------------------------------------------------------- installed system

eval "$(sed -n '/^installed_resolver() {$/,/^}$/p' "$lib/install")"
TARGET=$work/target; mkdir -p "$TARGET/etc"
net_dns=1.1.1.1,8.8.8.8 net_dns_source=public
installed_resolver
[[ $(cat "$TARGET/etc/resolv.conf") == $'nameserver 1.1.1.1\nnameserver 8.8.8.8' ]] || fail 'installed resolv.conf'
grep -qx 'supersede domain-name-servers 1.1.1.1,8.8.8.8;' "$TARGET/etc/dhclient.conf" || fail 'installed dhclient.conf'
rm -f "$TARGET/etc/"*
cp() { command cp "$work/resolv.conf" "$2"; }
net_dns=192.168.7.53 net_dns_source=dhcp
installed_resolver
[[ ! -e $TARGET/etc/dhclient.conf ]] || fail 'pinned working DHCP DNS'
unset -f cp

# ---------------------------------------------------------------- configurator front-end

for function in network_step_title network_step_bound nb_hook_run nb_hook_show network_dns_prompt \
    network_bringup_options network_bringup_adopt; do
  eval "$(sed -n "/^$function() {$/,/^}$/p" "$lib/configurator")"
done
NB_EXEC=/nonexistent/network-bringup
say() { printf '%s\n' "$*" >>"$work/w/said"; }
answer() { printf '%s\n' "$@" >"$work/w/answers"; }
gum() {
  case $1 in
    spin) # record the bounded child command, then run that step in-process
      printf '%s\n' "$*" >>"$work/w/spin"
      while [[ $1 != -- ]]; do shift; done
      shift 4
      nb_step "$@"
      ;;
    input) # a file queue: the configurator reads answers in command substitutions
      head -n 1 "$work/w/answers"; sed -i.old 1d "$work/w/answers" ;;
    confirm) return 0 ;;
  esac
}
world
nic igb0 up 192.168.7.20 192.168.7.1; nic ue0 up 172.20.10.2 172.20.10.1
dns_ok 10.0.0.53
nb_reset; nb_discover; nb_dhcp
answer dns.example 10.0.0.99 10.0.0.53
network_dns_prompt || fail 'front-end did not accept an answering DNS server'
grep -q 'dns.example is not an IPv4 address' "$work/w/said" || fail 'front-end accepted a host name'
grep -q 'timeout 20 /nonexistent/network-bringup dns-try 10.0.0.99' "$work/w/spin" || fail 'DNS try not bounded'
grep -q '10.0.0.99 did not answer a lookup' "$work/w/said" || fail 'refused server not reported'
net_mode=dhcp net_dns='' net_dns_source=''
network_bringup_adopt
[[ $net_if == igb0 && $net_dns == 10.0.0.53 && $net_dns_source == user ]] || fail 'front-end did not adopt the result'
[[ $(network_bringup_options) == $'Run network checks again\nUse ue0 as the primary connection\nEnter a DNS server' ]] ||
  fail "primary override not offered: $(network_bringup_options)"
[[ $(network_step_bound dhcp) -gt $NB_DHCP_TIMEOUT ]] || fail 'DHCP step bound shorter than its probes'
answer ''
network_dns_prompt && fail 'empty DNS answer accepted'

# ---------------------------------------------------------------- wiring

grep -q '^source "$(dirname "$0")/network-bringup"$' "$lib/configurator" || fail 'configurator does not share the pipeline'
grep -q 'printf .net_dns_source=%q' "$lib/configurator" || fail 'DNS source not written to install.conf'
main=$(sed -n '/^user_step$/,/^network_step$/p' "$lib/configurator")
[[ $main == $'user_step\nnetwork_bringup_auto\nnetwork_step' ]] || fail 'network check does not run before the network screen'
auto=$(grep -n 'network-bringup" auto' "$lib/launch" | cut -d: -f1)
run=$(grep -n '^  if run_install; then' "$lib/launch" | head -n 1 | cut -d: -f1)
[[ -n $auto && $auto -lt $run ]] || fail 'unattended installs skip the network check'
grep -q 'network-bringup" dns-ensure' "$lib/install" || fail 'installer does not restore checked DNS'
grep -q 'build-epoch' "$here/build-iso.sh" || fail 'image does not record its build time'
bash -n "$lib/network-bringup" "$lib/configurator" "$lib/launch" "$lib/install"
echo 'PASS: discovery, concurrent DHCP and primary choice, direct DNS with user fallback, clock, firmware, Wi-Fi-first, unattended'
