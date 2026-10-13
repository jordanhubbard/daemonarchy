#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/network-addresses"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
ifconfig() { cat "$work/interfaces"; }
cat >"$work/interfaces" <<'NET'
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST>
    inet 127.0.0.1 netmask 0xff000000
em0: flags=8802<BROADCAST,SIMPLEX,MULTICAST>
    inet 192.168.1.9 netmask 0xffffff00
em1: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST>
    inet 192.168.2.9 netmask 0xffffff00
    status: no carrier
NET
! network_has_address
cat >>"$work/interfaces" <<'NET'
wlan0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST>
    inet 10.20.30.40 netmask 0xffffff00
    status: associated
NET
[[ $(network_addresses) == 10.20.30.40 ]]
# Exercise the real network form with deterministic console and network responses.
eval "$(sed -n '/^network_step() {$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/configurator")"
step() { :; }
say() { :; }
network_summary() { :; }
online() { echo 'Unexpected internet probe' >&2; exit 99; }
default_port() { return 0; }
ether_ports() { echo em0; }
wifi_adapters() { echo iwm0; }
network_has_address() { [[ -f $work/ready ]]; }
use_dhcp() { touch "$work/ready"; }
use_wifi() { touch "$work/ready"; }
gum() {
  printf '%s\n' "$@" >"$work/options"
  if [[ -f $work/ready ]]; then
    grep -qx Continue "$work/options"
    echo Continue
  else
    ! grep -qx Continue "$work/options"
    cat "$work/choice"
  fi
}
net_mode=dhcp OMARCHY_FORM_BACK=2
for choice in 'Use DHCP on em0' 'Join Wi-Fi with iwm0'; do
  rm -f "$work/ready"
  echo "$choice" >"$work/choice"
  network_step remote-debug
  [[ -f $work/ready ]]
done
rm -f "$work/ready"
echo 'Back to installer menu' >"$work/choice"
! network_step remote-debug
eval "$(sed -n '/^adapter_kind() {$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/configurator")"
[[ $(adapter_kind ue0) == 'USB network' ]]
[[ $(adapter_kind vtnet0) == Virtual ]]
[[ $(adapter_kind wlan0) == Wi-Fi ]]
[[ $(adapter_kind em0) == Network ]]
echo 'PASS: inactive addresses rejected; LAN-only DHCP/Wi-Fi, cancellation and interface labels'
