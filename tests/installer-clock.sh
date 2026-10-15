#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
for function in valid_clock_time set_clock_manually wait_for_clock_sync sync_clock_network; do
  eval "$(sed -n "/^$function() {$/,/^}$/p" "$here/overlay/usr/local/libexec/daemonarchy-installer/configurator")"
done
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Exercise BSD date's actual parser without changing the host clock.
valid_clock_time '2028-02-29 23:59:59'
for invalid in '2026-02-29 12:00:00' '2026-04-31 12:00:00' '2026-10-15 25:00:00' '2026-10-15 12:00:00 trailing' ''; do
  ! valid_clock_time "$invalid"
done
step() { :; }
say() { :; }
notice() { printf '%s\n' "$*" >>"$work/notices"; }
service() {
  echo "$*" >>"$work/services"
  case $2 in
    onestatus) return "$running_status" ;;
    onestop) return "$stop_status" ;;
    onestart) return "$start_status" ;;
  esac
}
date() {
  if [[ $1 == -j || $# == 2 ]]; then command date "$@"; else
    printf '%s\n' "$*" >>"$work/set-clock"
    return "$set_status"
  fi
}
gum() {
  case $1 in
    input) echo '2026-10-15 17:30:00'; return "$input_status" ;;
    confirm) return "$confirm_status" ;;
    spin) [[ $* == *'timeout 30 bash -c'* ]]; return "$sync_status" ;;
  esac
}
running_status=1 stop_status=0 start_status=0 set_status=0
input_status=0 confirm_status=0 sync_status=0
set_clock_manually
[[ $(cat "$work/set-clock") == '-u -f %Y-%m-%d %H:%M:%S 2026-10-15 17:30:00' ]]
! grep -q onestart "$work/services"
rm "$work/set-clock"
input_status=1
set_clock_manually
[[ ! -e $work/set-clock ]]
input_status=0 confirm_status=1
set_clock_manually
[[ ! -e $work/set-clock ]]
confirm_status=0 running_status=0 stop_status=1
set_clock_manually
[[ ! -e $work/set-clock ]]
grep -q 'Could not stop' "$work/notices"
stop_status=0 set_status=1
set_clock_manually
grep -q 'Could not set' "$work/notices"
running_status=1
sync_clock_network
grep -q onestart "$work/services"
grep -q 'Network time synchronized:' "$work/notices"
sync_status=124
sync_clock_network
grep -q 'did not complete' "$work/notices"
start_status=1
sync_clock_network
grep -q 'Could not start' "$work/notices"
ntpq() { echo 'leap=00, stratum=3,'; }
wait_for_clock_sync
echo 'PASS: calendar validation, offline clock setting, cancellation, service failures and bounded network sync'
