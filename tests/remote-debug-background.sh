#!/usr/local/bin/bash
# Native FreeBSD: remote debugging that keeps running through the install.
# The console listener is left in the background (b + Enter), survives the
# console's Ctrl-C and its own exit, and every new agent still needs console
# approval, given from the install screen with remote-debug pending/approve/deny
# (the C-b R window) instead of a second virtual console. Isolated from the
# system sshd; uses its own state directory and port.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /root/daemonarchy-debug-bg-qa.XXXXXX)
port=${DEBUG_TEST_PORT:-23461}
listener='' client=''
cleanup() {
  if [[ -x $work/remote-debug ]]; then "$work/remote-debug" unpair >/dev/null 2>&1 || true; fi
  [[ -z $client ]] || kill "$client" 2>/dev/null || true
  [[ -z $listener ]] || kill "$listener" 2>/dev/null || true
  rm -rf "$work"
}
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; cat "$work"/console* >&2 2>/dev/null || true; exit 1; }
wait_for() {
  local pattern=$1 file=$2 tries
  for ((tries=0; tries<200; tries++)); do
    if grep -q "$pattern" "$file" 2>/dev/null; then return; fi
    sleep .1
  done
  fail "timed out waiting for $pattern"
}
sed -e "s|^state=.*|state=$work/state|" \
    -e "s|^legacy=.*|legacy=$work/no-legacy|" \
    -e "s|^self=.*|self=$work/remote-debug|" \
    -e "s|^public_state=.*|public_state=$work/public.status|" \
    "$here/overlay/usr/local/libexec/daemonarchy-installer/remote-debug" >"$work/remote-debug"
cp "$here/overlay/usr/local/libexec/daemonarchy-installer/network-addresses" "$work/"
sed "s|^logs=.*|logs=$work/diagnostics|" \
  "$here/overlay/usr/local/libexec/daemonarchy-installer/debug-observe" >"$work/debug-observe"
cp "$here/overlay/usr/local/libexec/daemonarchy-installer/debug-events.py" "$work/"
chmod 700 "$work/debug-observe" "$work/remote-debug"
ssh-keygen -q -t ed25519 -N '' -f "$work/client"
ssh-keygen -q -t ed25519 -N '' -f "$work/other"
ssh_client() {
  ssh -n -p "$port" -i "$work/$1" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o LogLevel=ERROR root@127.0.0.1 "${@:2}"
}
pending_id() {
  local tries id
  for ((tries=0; tries<200; tries++)); do
    id=$("$work/remote-debug" pending | awk 'NR == 1 { print $1 }')
    [[ -n $id ]] && { printf '%s\n' "$id"; return; }
    sleep .1
  done
  fail 'no pending pairing request'
}

# 1. Start at the console, then keep it running in the background (b + Enter).
mkfifo "$work/input"
exec 9<>"$work/input"
# Its own process group stands in for the console's foreground group, so the
# signals below never reach this test or the session that runs it.
set -m
"$work/remote-debug" listen "$port" <"$work/input" >"$work/console" 2>&1 &
listener=$!
set +m
printf 'y\n' >&9
wait_for 'Type b and Enter to keep it running in the background' "$work/console"
listen_pgid=$(ps -o pgid= -p "$listener" | tr -d ' ')
[[ $listen_pgid == "$listener" && $listen_pgid != "$(ps -o pgid= -p $$ | tr -d ' ')" ]] || fail 'console stand-in shares the test process group'
sshd_pid=$(cat "$work/state/sshd.pid")
[[ $(ps -o pgid= -p "$sshd_pid" | tr -d ' ') != "$listen_pgid" ]] || fail 'listener shares the console process group'
kill -INT -- "-$listen_pgid"  # Ctrl-C at the console while the listener view is open
wait "$listener" || true  # Ctrl-C in the foreground view stops that view (exit 130) ...
listener=''
grep -q 'keeps running in the background' "$work/console" && fail 'Ctrl-C was taken as a background request'
# ... and, as before, revokes the session it started. Start again and keep it.
set -m
"$work/remote-debug" listen "$port" <"$work/input" >"$work/console" 2>&1 &
listener=$!
set +m
listen_pgid=$listener
printf 'y\n' >&9
wait_for 'Type b and Enter to keep it running in the background' "$work/console"
printf 'b\n' >&9
wait "$listener" || fail 'backgrounding the listener failed'
listener=''
grep -q 'keeps running in the background' "$work/console" || fail 'no background confirmation'
"$work/remote-debug" status || fail 'listener stopped when its console view exited'
# Later console Ctrl-C and hangups (for example in an installer prompt) reach
# the console's process group, never the background listener.
kill -INT -- "-$listen_pgid" 2>/dev/null || true
kill -HUP -- "-$listen_pgid" 2>/dev/null || true
sleep 1
"$work/remote-debug" status || fail 'console Ctrl-C or hangup stopped the background listener'

# 2. A new agent still needs console approval, given without the listener's console.
ssh_client client 'printf APPROVED_RESULT' >"$work/result" 2>&1 &
client=$!
request=$(pending_id)
"$work/remote-debug" pending | grep -q "^$request SHA256:" || fail 'pending request lacks its fingerprint'
"$work/remote-debug" approve "$request" | grep -q 'Agent approved' || fail 'approve failed'
wait "$client" || fail 'approved agent could not connect'
client=''
[[ $(cat "$work/result") == APPROVED_RESULT ]] || fail 'approved command output changed'
if "$work/remote-debug" approve "$request" 2>/dev/null; then fail 'a decided request was decided again'; fi
if "$work/remote-debug" approve ../../etc 2>/dev/null; then fail 'an invalid request ID was accepted'; fi
ssh_client other true >/dev/null 2>&1 &
client=$!
request=$(pending_id)
"$work/remote-debug" deny "$request" | grep -q 'Agent denied' || fail 'deny failed'
if wait "$client"; then fail 'denied agent connected'; fi
client=''

# 3. Attaching again shows the running listener; Enter leaves it running.
"$work/remote-debug" listen "$port" <<<'' >"$work/console-attach" 2>&1 || true
grep -q 'Attached to the remote access listener' "$work/console-attach" || fail 'attach did not reuse the listener'
"$work/remote-debug" status || fail 'leaving an attached view stopped the listener'
"$work/remote-debug" background "$port" >"$work/console-background" 2>&1
grep -q 'already running' "$work/console-background" || fail 'background started a second listener'

# 4. Stop revokes everything.
"$work/remote-debug" stop | grep -q 'Remote access stopped' || fail 'stop failed'
if "$work/remote-debug" status; then fail 'listener survived stop'; fi
[[ ! -e $work/state ]] || fail 'pairing state survived stop'
if ssh_client client true 2>/dev/null; then fail 'stopped listener still accepts connections'; fi

# 5. Start directly in the background (the configurator and C-b R path), then stop.
"$work/remote-debug" background "$port" >"$work/console-direct" 2>&1 || fail 'background start failed'
grep -q 'running in the background on port' "$work/console-direct" || fail 'no background start message'
grep -q 'Server fingerprint' "$work/console-direct" || fail 'no server fingerprint shown'
"$work/remote-debug" status || fail 'background listener is not running'
"$work/remote-debug" stop >/dev/null
echo 'PASS: background listener survives its console and Ctrl-C, console approval and denial without a second VT, attach, stop'
