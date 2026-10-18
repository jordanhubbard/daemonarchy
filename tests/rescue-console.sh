#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/sbin/daemonarchy-rescue" --library
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
state_dir=$work/state
debug_state=$work/debug-session
mkdir "$state_dir"
echo in-progress >"$state_dir/status"
echo install >"$state_dir/phase"
desktop_ready() { echo 'unexpected GUI probe' >&2; exit 99; }
monitor_desktop >"$work/incomplete"
grep -q 'Installation did not complete.*install' "$work/incomplete"
rescue_log=$work/rescue.log
dmesg() { echo 'current boot kernel output'; }
rescue_record
grep -q 'Installation did not complete.*install' "$rescue_log"
grep -qx 'current boot kernel output' "$state_dir/rescue-kernel.log"
echo complete >"$state_dir/status"
startup_wait=3 failure_wait=2 poll_seconds=1 ticks=0
sleep() { ticks=$((ticks + 1)); }
desktop_ready() { return 1; }
monitor_desktop >"$work/failed"
[[ $ticks == 3 ]]
grep -q 'graphical login or desktop is not running' "$work/failed"
# A session that starts successfully and later crashes gets a fresh grace period.
ticks=0
desktop_ready() { [[ $ticks -lt 4 ]]; }
monitor_desktop >"$work/crashed"
[[ $ticks == 6 ]]
grep -q 'graphical login or desktop is not running' "$work/crashed"
# Public menu never calls a privileged action directly; it executes login.
(
  rescue_action() { echo 'UNAUTHENTICATED ACTION' >&2; exit 99; }
  exec() {
    [[ $* == '/usr/bin/login -p root' ]]
    [[ $DAEMONARCHY_RESCUE_ACTION == remote ]]
    exit 0
  }
  rescue_menu no <<<'2'
) >"$work/pairing"
grep -q 'password chosen during installation' "$work/pairing"
grep -q '2. Pair a remote debugging agent' "$work/pairing"
# A stale session still offers a way to revoke it, with the same authentication.
mkdir "$debug_state"
(
  rescue_action() { echo 'UNAUTHENTICATED ACTION' >&2; exit 99; }
  exec() {
    [[ $* == '/usr/bin/login -p root' ]]
    [[ $DAEMONARCHY_RESCUE_ACTION == unpair ]]
    exit 0
  }
  rescue_menu no <<<'2'
) >"$work/unpairing"
grep -q '2. Unpair remote debugging agent' "$work/unpairing"
# Returning to the menu after unpairing offers pairing again.
rescue_action() {
  echo "$1" >>"$work/toggle-actions"
  case $1 in unpair) rmdir "$debug_state" ;; remote) mkdir "$debug_state" ;; esac
}
rescue_menu yes <<<$'2\n2' >"$work/toggle-menu"
[[ $(cat "$work/toggle-actions") == $'unpair\nremote' ]]
grep -q '2. Unpair remote debugging agent' "$work/toggle-menu"
grep -q '2. Pair a remote debugging agent' "$work/toggle-menu"
# An authenticated root can use the menu directly.
rescue_action() { echo "$1" >"$work/action"; }
rescue_menu yes <<<'3' >/dev/null
[[ $(cat "$work/action") == logs ]]
# Late device probes must settle before the first console menu is drawn.
# No input is supplied to either the settling step or the initial menu render.
(
  tty() { echo /dev/ttyv0; }
  boot_quiet_wait=6 boot_quiet_seconds=2 ticks=0
  dmesg() { if ((ticks < 3)); then echo "probe $ticks"; else echo 'probe 3'; fi; }
  rescue_wait_boot_output </dev/null
  [[ $ticks == 5 ]]
  ticks=0
  dmesg() { echo "probe $ticks"; }
  rescue_wait_boot_output </dev/null
  [[ $ticks == 6 ]] # Continuous logging cannot postpone recovery indefinitely.
  ticks=0
  tty() { echo /dev/pts/1; }
  rescue_wait_boot_output </dev/null
  [[ $ticks == 0 ]]
  tty() { echo /dev/ttyv0; }
  rescue_font() { echo 'font sized'; }
  rescue_menu no </dev/null >"$work/first-menu"
  grep -q $'\033\\[2J\033\\[H' "$work/first-menu"
  grep -q 'Daemonarchy rescue' "$work/first-menu"
)
echo 'PASS: interrupted install, GUI timeout/crash, authenticated pairing/unpairing, menu toggle and boot-to-menu without input'
