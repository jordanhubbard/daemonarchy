#!/usr/local/bin/bash
# The debugger's state machine against a real sshd: an orphaned listener is cleared,
# a listener that accepts TCP but never speaks SSH is restarted, a dead attachment's
# lease expires, a console view leaves when the grant is removed elsewhere, and the
# published status always says which of these states is true.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /root/daemonarchy-debug-lease.XXXXXX)
public_dir=$(mktemp -d /tmp/daemonarchy-debug-lease-public.XXXXXX)
chmod 755 "$public_dir"
port=${DEBUG_LEASE_TEST_PORT:-23462}
client='' console=''
dbg=$work/remote-debug
status=$public_dir/status
cleanup() {
  [[ -z $client ]] || kill "$client" 2>/dev/null || true
  [[ -z $console ]] || kill "$console" 2>/dev/null || true
  [[ ! -x $dbg ]] || "$dbg" unpair >/dev/null 2>&1 || true
  pkill -CONT -f "$work/state/sshd_config" 2>/dev/null || true
  pkill -KILL -f "$work/state/sshd_config" 2>/dev/null || true
  rm -rf "$work" "$public_dir"
}
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; [[ ! -f $work/console ]] || cat "$work/console" >&2; exit 1; }
wait_for() {
  local pattern=$1 file=$2 tries
  for ((tries=0; tries<300; tries++)); do
    if grep -q "$pattern" "$file" 2>/dev/null; then return; fi
    sleep .1
  done
  fail "timed out waiting for $pattern in $file"
}
sed -e "s|^state=.*|state=$work/state|" -e "s|^legacy=.*|legacy=$work/no-legacy|" -e "s|^self=.*|self=$dbg|" \
  -e "s|^public_state=.*|public_state=$status|" -e 's|^lease_refresh=.*|lease_refresh=1|' -e 's|^lease_expiry=.*|lease_expiry=4|' \
  "$here/overlay/usr/local/libexec/daemonarchy-installer/remote-debug" >"$dbg"
cp "$here/overlay/usr/local/libexec/daemonarchy-installer/network-addresses" "$work/"
chmod 700 "$dbg"
listeners() { pgrep -f "sshd.*-f $work/state/sshd_config" || true; }
# True only when the port completes an SSH banner, as the status check does.
answers() {
  local line
  line=$(timeout 6 bash -c 'exec 3<>"/dev/tcp/127.0.0.1/$1" && IFS= read -r -t 4 line <&3 && printf "%s" "$line"' _ "$port" 2>/dev/null) || return 1
  [[ $line == SSH-2.0-* ]]
}
state_is() { grep -qx "state=$1" "$status"; }
approve() {
  local type key
  read -r type key _ <"$work/$1.pub"
  touch "$work/state/$(printf '%s %s' "$type" "$key" | sha256 -q).approved"
}
ssh_client() {
  timeout 30 ssh -n -p "$port" -i "$work/$1" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$work/known_hosts" \
    -o LogLevel=ERROR root@127.0.0.1 "${@:2}"
}
ssh-keygen -q -t ed25519 -N '' -f "$work/client"

# 1. A session whose state directory was removed leaves its listener running, with
#    no way to reach it. Status must say so; reconcile and a new pairing must clear it.
"$dbg" _start "$port" >"$work/start" || fail 'could not start a listener'
answers || fail 'fresh listener does not answer SSH'
"$dbg" publish-status
state_is listening || fail 'a healthy listener is not published as listening'
grep -qx 'listener=1' "$status" || fail 'listening state without listener=1'
rm -rf "$work/state"
[[ -n $(listeners) ]] || fail 'test setup: listener should outlive its state'
"$dbg" publish-status
state_is orphaned || fail 'orphaned listener not detected'
grep -qx 'grant=0' "$status" || fail 'orphan published a grant'
grep -qx 'listener=0' "$status" || fail 'orphan published as a listener'
"$dbg" status --details >"$work/details" && fail 'detailed status called an orphan healthy'
grep -qx 'State: orphaned' "$work/details" || fail 'detailed status omitted the orphaned state'
grep -q 'daemonarchy-debug reconcile' "$work/details" || fail 'detailed status omitted the recovery step'
"$dbg" reconcile
[[ -z $(listeners) ]] || fail 'reconcile left the orphaned listener running'
state_is unpaired || fail 'status did not return to unpaired'
answers && fail 'orphaned port still answers after reconcile'

# 2. A new pairing must not fail on a port an orphan still holds.
"$dbg" _start "$port" >"$work/start" || fail 'could not start a listener'
rm -rf "$work/state"
"$dbg" _start "$port" >"$work/start" || fail 'pairing failed on a port held by an orphan'
answers || fail 'new listener does not answer'
[[ $(listeners | wc -l) -eq 1 ]] || fail 'orphan and new listener both running'

# 3. A listener that accepts TCP but never answers is degraded, and reconcile
#    replaces it using the retained approval.
approve client
old=$(listeners)
kill -STOP "$old"
answers && fail 'a stopped listener still answers'
"$dbg" publish-status
state_is degraded || fail 'listener that does not answer was not marked degraded'
grep -qx 'listener=0' "$status" || fail 'degraded listener published as listening'
"$dbg" reconcile
new=$(listeners)
[[ -n $new && $new != "$old" ]] || fail 'reconcile did not replace the degraded listener'
kill -0 "$old" 2>/dev/null && fail 'stopped listener survived reconcile'
answers || fail 'replacement listener does not answer'
state_is listening || fail 'status did not recover to listening'
grep -Eq '^updated=[0-9]{10}$' "$status" || fail 'status has no timestamp'

# 4. An attachment holds a lease. When it stops being renewed the attachment ends.
ssh_client client 'sleep 300' >"$work/client-result" 2>&1 &
client=$!
for ((i=0; i<100; i++)); do
  "$dbg" publish-status
  state_is attached && break
  sleep .2
done
state_is attached || fail 'a live attachment was not published as attached'
grep -qx 'connected=1' "$status" || fail 'attached without connected=1'
marker=$(ls "$work"/state/connected/* | head -1)
helper=$(cat "$marker")
[[ $helper =~ ^[0-9]+$ ]] || fail 'attachment marker does not name its heartbeat'
sleep 3
"$dbg" publish-status
state_is attached || fail 'a renewed lease lapsed'
kill -STOP "$helper"
sleep 6
"$dbg" publish-status
grep -qx 'connected=0' "$status" || fail 'a lapsed lease still shows as connected'
state_is listening || fail 'a lapsed lease did not return to listening'
kill -CONT "$helper" 2>/dev/null || true
wait "$client" || true
client=''

# 5. A console view that owns the listener leaves when the grant is removed elsewhere.
"$dbg" unpair >/dev/null
[[ -z $(listeners) ]] || fail 'unpair left a listener'
mkfifo "$work/input"
exec 9<>"$work/input"
"$dbg" listen "$port" <"$work/input" >"$work/console" 2>&1 &
console=$!
printf 'y\n' >&9
wait_for 'Waiting for an authenticated agent' "$work/console"
"$dbg" unpair >/dev/null
wait_for 'stopped from elsewhere' "$work/console"
wait "$console" || true
console=''
[[ -z $(listeners) ]] || fail 'listener survived the console view'
state_is unpaired || fail 'status not unpaired after removal'

echo 'PASS: orphan reaped, degraded listener replaced, lease expiry, console view leaves, status truthful'
