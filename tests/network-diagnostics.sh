#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
configurator=$here/overlay/usr/local/libexec/daemonarchy-installer/configurator
for function in online network_failure network_step; do
  eval "$(sed -n "/^$function() {$/,/^}$/p" "$configurator")"
done
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Exercise the actual probe and form without changing the host's clock/network.
fetch() {
  [[ $* == '-q -T 5 -o /dev/null https://pkg.FreeBSD.org/' ]]
  printf '%s\n' "$fetch_error" >&2
  return "$fetch_status"
}
date() {
  if [[ $* == '-u +%Y' ]]; then echo "$mock_year"; else echo "$mock_year-01-04 14:07:53 UTC"; fi
}
say() { printf '%s\n' "$*"; }
step() { :; }
network_summary() { :; }
ether_ports() { echo ue0; }
wifi_adapters() { :; }
default_port() { echo ue0; }
gum() {
  printf '%s\n' "$@" >"$work/options"
  # Exit after drawing the failed probe, using allow-offline's explicit escape.
  echo Continue
}
net_mode=dhcp
fetch_status=1
while IFS='|' read -r mock_year fetch_error expected; do
  network_step allow-offline >"$work/messages"
  grep -Fq "$expected" "$work/messages"
  grep -Fq "$fetch_error" "$work/messages"
  grep -Fq "System time: $mock_year-" "$work/messages"
  ! grep -Fq 'Not connected to the internet' "$work/messages"
done <<'CASES'
1970|certificate verify failed|The system clock is incorrect
2026|Certificate verification failed for /CN=ISRG Root X2|TLS certificate verification failed
2026|fetch: pkg.FreeBSD.org: No address record|DNS could not resolve
2026|fetch: Network is unreachable|Check the interface and default gateway
2026|fetch: Operation timed out|The package request timed out
2026|fetch: https://pkg.FreeBSD.org/: Service Unavailable|does not necessarily mean the network is disconnected
2026|fetch: Authentication error|does not necessarily mean the network is disconnected
CASES

# Failed normal installs must not offer Continue. Stop the form after inspecting
# its choices; remote-debug already has separate LAN-only coverage.
gum() {
  printf '%s\n' "$@" >"$work/options"
  return 1
}
OMARCHY_FORM_BACK=2
abort() { exit 73; }
status=0
(network_step >"$work/messages") || status=$?
[[ $status == 73 ]]
! grep -qx Continue "$work/options"
grep -qx 'Set date and time' "$work/options"
grep -qx 'Synchronize time over network' "$work/options"

# Recovery clears the previous error and offers Continue on a successful probe.
gum() { printf '%s\n' "$@" >"$work/options"; echo Continue; }
fetch_status=0 fetch_error=
network_step >"$work/messages"
[[ -z $network_probe_error ]]
grep -qx Continue "$work/options"
grep -Fq 'Package repository reachable securely through ue0.' "$work/messages"
! grep -Fq 'request failed' "$work/messages"
echo 'PASS: clock, TLS, DNS, route, timeout and unknown errors; install gate and recovery'
