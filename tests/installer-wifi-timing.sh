#!/usr/bin/env bash
# Exercise the installer's real scan/join functions with delayed radio replies.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export WIFI_CONF=$work/wpa.conf WIFI_ERROR_FILE=$work/error
export WIFI_DHCLIENT_PIDFILE=$work/dhclient.pid
eval "$(sed -n '/^wifi_scan() {$/,/^}$/p; /^wifi_connect() {$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/configurator")"

sleep() { :; }
pkill() { :; }
kill() { printf '%s\n' "$1" >"$work/killed-pid"; }
ps() { printf '%s\n' 'dhclient: wlan0 (dhclient)'; }
wpa_passphrase() { printf 'network={\n ssid="%s"\n psk=example\n}\n' "$1"; }
wpa_supplicant() { :; }
dhclient() { printf '%s\n' called >"$work/dhcp"; }
timeout() { shift; "$@"; }
port_address() { printf '%s\n' 192.0.2.5; }
route() { printf '%s\n' 'interface: wlan0'; }
ifconfig() {
  if [[ $* == 'wlan0 up scan' ]]; then
    echo x >>"$work/scans"
    return
  fi
  [[ $* == '-v wlan0 list scan' ]] || return 1
  printf 'SSID            BSSID              CHAN RATE S:N    INT CAPS\n'
  printf 'First           00:11:22:33:44:55 1    54M  30:0   100 EPS\n'
  if [[ $(<"$work/scans") == $'x\nx\n'* || $(<"$work/scans") == $'x\nx' ]]; then
    for n in 2 3 4 5 6 7 8; do
      printf 'Network%s        00:11:22:33:44:%02d 36   54M  40:0   100 EPS\n' "$n" "$n"
    done
  fi
}

scan=$(wifi_scan)
(( $(wc -l <<<"$scan") == 8 ))
(( $(wc -l <"$work/scans") == 4 ))
for n in 2 3 4 5 6 7 8; do grep -qx "Network$n" <<<"$scan"; done

wpa_cli() {
  echo x >>"$work/status-checks"
  if (( $(wc -l <"$work/status-checks") > 65 )); then
    printf '%s\n' 'wpa_state=COMPLETED'
  else
    printf '%s\n' 'wpa_state=SCANNING'
  fi
}
printf '%s\n' 4321 >"$WIFI_DHCLIENT_PIDFILE"
wifi_connect First example false
[[ $(<"$work/killed-pid") == 4321 ]]
(( $(wc -l <"$work/status-checks") == 66 ))
[[ -f $work/dhcp && ! -e $work/error ]]

rm "$work/killed-pid"
ps() { printf '%s\n' 'unrelated process'; }
wifi_connect First example false
[[ ! -e $work/killed-pid ]]
ps() { printf '%s\n' 'dhclient: wlan0 (dhclient)'; }

route() { printf '%s\n' 'interface: em0'; }
if wifi_connect First example false; then
  echo 'Accepted a Wi-Fi join with the default route on another interface' >&2
  exit 1
fi
grep -q 'em0 owns the default route' "$work/error"
route() { printf '%s\n' 'interface: wlan0'; }

# Keep live Ethernet and its DHCP client for debugging, but send install
# downloads over the newly authenticated Wi-Fi default route.
export WIFI_DHCLIENT_LEASEFILE=$work/wlan0.lease
export WIFI_WIRED_DHCLIENT_PIDFILE=$work/em0.pid
printf 'lease {\n  option routers 192.0.2.1;\n}\n' >"$WIFI_DHCLIENT_LEASEFILE"
printf '%s\n' 5678 >"$WIFI_WIRED_DHCLIENT_PIDFILE"
ifconfig() {
  case "$*" in
    em0) printf '%s\n' 'ether 02:00:00:00:00:01' 'status: active' ;;
    *) return 1 ;;
  esac
}
route() {
  case "$*" in
    '-n get default')
      if [[ -f $work/wireless-default ]]; then
        printf '%s\n' 'interface: wlan0'
      else
        printf '%s\n' 'interface: em0'
      fi ;;
    '-q change default 192.0.2.1 -ifp wlan0') printf '%s\n' changed >"$work/wireless-default" ;;
    *) return 1 ;;
  esac
}
wifi_connect First example false
[[ $(<"$work/wireless-default") == changed && $(<"$work/killed-pid") == 4321 &&
   ! -e $work/wired-address && ! -e $work/error ]]
rm "$work/wireless-default"

# Pulling the cable can leave a DHCP address and default route behind. Once
# the Wi-Fi lease exists, the installer must release only that stale wired
# client and select the wireless gateway without asking for the password again.
port_address() { [[ $1 == em0 ]] && echo 192.0.2.8 || echo 192.0.2.5; }
ps() { printf '%s\n' 'dhclient: em0 (dhclient)'; }
ifconfig() {
  case "$*" in
    em0) printf '%s\n' 'ether 02:00:00:00:00:01' 'status: no carrier' ;;
    'em0 inet 192.0.2.8 delete') printf '%s\n' deleted >"$work/wired-address" ;;
    *) return 1 ;;
  esac
}
route() {
  case "$*" in
    '-n get default')
      if [[ -f $work/wireless-default ]]; then
        printf '%s\n' 'interface: wlan0'
      else
        printf '%s\n' 'interface: em0'
      fi ;;
    '-q delete default') : ;;
    '-q add default 192.0.2.1 -ifp wlan0') printf '%s\n' selected >"$work/wireless-default" ;;
    *) return 1 ;;
  esac
}
wifi_connect First example false
[[ $(<"$work/killed-pid") == 5678 ]]
[[ -f $work/wired-address && -f $work/wireless-default && ! -e $work/error ]]
route() { printf '%s\n' 'interface: wlan0'; }

rm "$work/status-checks" "$work/dhcp"
wpa_cli() { printf '%s\n' 'wpa_state=SCANNING'; }
if wifi_connect First example false; then
  echo 'Accepted a connection without completed WPA authentication' >&2
  exit 1
fi
grep -q '120 seconds (last state: SCANNING)' "$work/error"
[[ ! -e $work/dhcp ]]
echo 'PASS: repeated scan, delayed WPA, stale wired route and bounded failure reason'
