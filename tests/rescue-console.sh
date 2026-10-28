#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/sbin/daemonarchy-rescue" --library
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
state_dir=$work/state
debug_state=$work/debug-session
debug_command=$work/debug-command
printf '#!/bin/sh\ncase "$1" in\nstatus) [ -f "$0.live" ] ;;\nresume) echo resume >>"$0.calls" ;;\n*) exit 1 ;;\nesac\n' >"$debug_command"
chmod +x "$debug_command"
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
# No supported desktop driver: the menu says why at once, without waiting.
graphics_nodriver=$work/nodriver
touch "$graphics_nodriver"
ticks=0
monitor_desktop >"$work/nodriver.out"
[[ $ticks == 0 ]]
grep -q 'No supported desktop graphics driver' "$work/nodriver.out"
rm "$graphics_nodriver"
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
# A stale session resumes without deleting the previous approval.
mkdir "$debug_state"
(
  exec() {
    [[ $* == '/usr/bin/login -p root' ]]
    [[ $DAEMONARCHY_RESCUE_ACTION == remote ]]
    exit 0
  }
  rescue_menu no <<<'2'
) >"$work/resuming"
grep -q '2. Resume remote debugging agent' "$work/resuming"
# A running listener still offers explicit revocation.
touch "$debug_command.live"
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
  case $1 in
    unpair) rmdir "$debug_state"; rm -f "$debug_command.live" ;;
    remote) mkdir "$debug_state"; touch "$debug_command.live" ;;
  esac
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
# Late DHCP readiness is retried without input; an absent grant does nothing.
(
  touch "$debug_state/active"
  rm -f "$debug_command.live" "$debug_command.calls"
  cat >"$debug_command" <<'MOCK'
#!/bin/sh
case $1 in
  resume) echo resume >>"$0.calls" ;;
  status) [ "$(wc -l <"$0.calls")" -ge 3 ] ;;
esac
MOCK
  ticks=0
  sleep() { ticks=$((ticks + 1)); [[ $ticks != 3 ]] || rm "$debug_state/active"; }
  rescue_resume_debug </dev/null
  [[ $(wc -l <"$debug_command.calls") -eq 3 && $ticks == 3 ]]
  rm "$debug_command.calls"
  rescue_resume_debug </dev/null
  [[ ! -e $debug_command.calls ]]
)
# The same approved grant also resumes when network readiness exceeds a minute.
(
  touch "$debug_state/active"
  rm -f "$debug_command.calls"
  cat >"$debug_command" <<'MOCK'
#!/bin/sh
case $1 in
  resume) echo resume >>"$0.calls" ;;
  status) [ "$(wc -l <"$0.calls")" -ge 62 ] ;;
esac
MOCK
  ticks=0
  sleep() { ticks=$((ticks + 1)); [[ $ticks != 62 ]] || rm "$debug_state/active"; }
  rescue_resume_debug </dev/null
  [[ $(wc -l <"$debug_command.calls") -eq 62 && $ticks == 62 ]]
  rm "$debug_command.calls"
)
# A listener that exits after a successful start is resumed with the old grant.
(
  touch "$debug_state/active"
  rm -f "$debug_command.calls" "$debug_command.live"
  cat >"$debug_command" <<'MOCK'
#!/bin/sh
case $1 in
  resume) echo resume >>"$0.calls"; touch "$0.live" ;;
  status) [ -f "$0.live" ] ;;
esac
MOCK
  ticks=0
  sleep() {
    ticks=$((ticks + 1))
    case $ticks in
      1) rm "$debug_command.live" ;; # Unexpected listener exit.
      2) rm "$debug_state/active" ;; # Explicit stop prevents another restart.
    esac
  }
  rescue_resume_debug </dev/null
  [[ $(wc -l <"$debug_command.calls") -eq 2 && $ticks == 2 ]]
  rm "$debug_command.calls" "$debug_command.live"
  rescue_resume_debug </dev/null
  [[ ! -e $debug_command.calls ]]
)
printf '#!/bin/sh\ncase "$1" in\nstatus) [ -f "$0.live" ] ;;\nresume) echo resume >>"$0.calls"; touch "$0.live" ;;\nesac\n' >"$debug_command"
touch "$debug_state/active"
rm -f "$debug_command.live" "$debug_command.calls"
# Boot resumption happens before desktop monitoring, including a healthy desktop.
(
  id() { echo 0; }
  sleep() { rm -f "$debug_state/active"; }
  monitor_desktop() { wait "$!"; grep -qx resume "$debug_command.calls"; }
  rescue_wait_boot_output() { :; }
  rescue_record() { :; }
  rescue_menu() { :; }
  rescue_main monitor
)
echo 'PASS: interrupted install, GUI timeout/crash, authenticated pairing/unpairing, menu toggle and boot-to-menu without input'
