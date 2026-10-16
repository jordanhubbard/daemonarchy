#!/usr/bin/env bash
# Exercise the actual network form without touching an adapter or credentials.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export ISO_SHARE=$work
export TEST_ENTERPRISE_ARGS=$work/arguments TEST_ENTERPRISE_STATUS=0
cat >"$work/omarchy-wifi-enterprise" <<'HELPER'
#!/bin/sh
printf '%s\n' "$@" >"$TEST_ENTERPRISE_ARGS"
exit "$TEST_ENTERPRISE_STATUS"
HELPER
chmod 755 "$work/omarchy-wifi-enterprise"
eval "$(sed -n '/^use_wifi() {$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/configurator")"
sysctl() { echo iwlwifi0; }
step() { :; }
wifi_scan() { :; }
notice() { printf '%s\n' "$*"; }
gum() {
  case $1 in
    spin) echo 'Corporate Wi-Fi' ;;
    choose)
      if [[ $* == *'Wi-Fi authentication'* ]]; then echo 'Enterprise (802.1X)'
      else
        cat >/dev/null
        if [[ $test_hidden == true ]]; then echo 'Other network...'; else echo 'Corporate Wi-Fi'; fi
      fi
      ;;
    input) echo 'Corporate Wi-Fi' ;;
    *) return 99 ;;
  esac
}
for test_hidden in false true; do
  net_mode=dhcp net_if='' wifi_psk=old wifi_enterprise_profile='' wifi_hidden=unset
  use_wifi iwlwifi0
  [[ $net_mode == wifi && $net_if == iwlwifi0 && -z $wifi_psk ]]
  [[ $wifi_enterprise_profile == /tmp/daemonarchy-enterprise-profile.json ]]
  [[ $wifi_hidden == "$test_hidden" ]]
  grep -qx -- --live "$TEST_ENTERPRISE_ARGS"
  grep -qx wlan0 "$TEST_ENTERPRISE_ARGS"
  grep -qx 'Corporate Wi-Fi' "$TEST_ENTERPRISE_ARGS"
  if [[ $test_hidden == true ]]; then grep -qx -- --hidden "$TEST_ENTERPRISE_ARGS"; fi
done
TEST_ENTERPRISE_STATUS=1
net_mode=dhcp net_if=ue0 wifi_enterprise_profile=''
if use_wifi iwlwifi0 >"$work/failure"; then echo 'Accepted failed enterprise setup' >&2; exit 1; fi
[[ $net_mode == dhcp && $net_if == ue0 && -z $wifi_enterprise_profile ]]
grep -q 'did not connect' "$work/failure"
echo 'PASS: enterprise/hidden selection, protected profile handoff and failed-join state'
