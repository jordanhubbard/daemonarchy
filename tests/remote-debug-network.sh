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

# Wi-Fi is optional. A missing adapter must not fail the probe, and an
# Ethernet machine must not be told that the absence is a problem.
eval "$(sed -n '/^wifi_adapters() {$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/configurator")"
eval "$(sed -n '/^network_summary() {$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/configurator")"
PADDING_LEFT_SPACES=
port_address() { echo 10.1.1.9; }
port_state() { echo connected; }
adapter_description() { echo USB Ethernet; }
say() { printf '%s\n' "$*" >>"$work/messages"; }
for wifi_probe in missing empty listed; do
  case $wifi_probe in
    missing) sysctl() { return 1; } ;;
    empty) sysctl() { printf '\n'; } ;;
    listed) sysctl() { printf 'iwm0 iwlwifi0\n'; } ;;
  esac
  if [[ $wifi_probe == listed ]]; then
    [[ $(wifi_adapters) == $'iwm0\niwlwifi0' ]]
  else
    [[ -z $(wifi_adapters) ]]
    : >"$work/messages"
    network_summary >/dev/null
    grep -i 'wi-fi' "$work/messages" && exit 1
  fi
done
ether_ports() { :; }
sysctl() { return 1; }
: >"$work/messages"
network_summary >/dev/null
grep -F 'A USB Ethernet adapter is enough to install.' "$work/messages" >/dev/null
grep -i 'wi-fi' "$work/messages" && exit 1
ether_ports() { echo em0; }
sysctl() { printf 'iwm0\n'; }
online() { return 0; }
default_port() { echo em0; }
touch "$work/ready"
network_step >/dev/null
dhcp_line=$(grep -n 'Use DHCP on em0' "$work/options" | cut -d: -f1)
wifi_line=$(grep -n 'Join Wi-Fi with iwm0' "$work/options" | cut -d: -f1)
[[ -n $dhcp_line && -n $wifi_line && $dhcp_line -lt $wifi_line ]]
sysctl() { return 1; }
touch "$work/ready"
network_step >/dev/null
grep -qx 'Use DHCP on em0' "$work/options"
grep -qx 'Set up em0 by hand' "$work/options"
grep -q 'Join Wi-Fi' "$work/options" && exit 1
echo 'PASS: inactive addresses rejected; LAN-only DHCP/Wi-Fi, cancellation and interface labels'
echo 'PASS: missing Wi-Fi is not fatal for Ethernet'
