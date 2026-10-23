#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
helper=$here/overlay/usr/local/libexec/daemonarchy-installer/remote-debug
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Load the actual listener and prompts without dispatching or starting SSH.
eval "$(sed '/^source /d; /^case ${1:-shell}/,$d' "$helper")"
state=$work/state
fsync() { :; } # Real durable writes are exercised by the native SSH fixtures.
mkdir -p "$state/requests"
printf 'SHA256:example\nssh-ed25519 example\n' >"$state/requests/example"
start_server() { echo "$1" >"$work/port"; server_pid=$$; }
show_status() { :; }
debug_listen 2207 <<'INPUT'
y
n

INPUT
[[ $(cat "$work/port") == 2207 && -f $state/example.denied ]]
rm "$state/example.denied" "$work/port"
debug_listen <<'INPUT'
y
y

INPUT
[[ $(cat "$work/port") == 2222 && -f $state/example.approved ]]
rm "$work/port"
debug_listen <<'INPUT'

INPUT
[[ ! -e $work/port ]]
# The real prerequisite fails before creating pairing state, even with CLI opt-in.
(
  eval "$(sed '/^source /d; /^case ${1:-shell}/,$d' "$helper")"
  state=$work/blocked
  id() { echo 0; }
  uname() { echo FreeBSD; }
  mount() { echo '/dev/cd0 / cd9660 ro 0 0'; }
  network_has_address() { return 1; }
  start_server 2222
) >"$work/error" 2>&1 && exit 1
[[ ! -e $work/blocked ]]
grep -q 'Configure the network from the debug shell' "$work/error"
echo 'PASS: CLI opt-in, custom/default ports, pairing approval/rejection, no-address guard'
