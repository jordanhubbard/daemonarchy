#!/usr/local/bin/bash
# Exercise actual SSH after a simulated reboot, with durable approval and host pin.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /root/daemonarchy-debug-reboot.XXXXXX)
port=${DEBUG_REBOOT_TEST_PORT:-23452}
listener='' unrelated='' client=''
cleanup() {
  [[ ! -x $work/fresh-debug ]] || "$work/fresh-debug" unpair >/dev/null 2>&1 || true
  [[ ! -x $work/remote-debug ]] || "$work/remote-debug" unpair >/dev/null 2>&1 || true
  for pid in "$listener" "$unrelated" "$client"; do
    [[ -z $pid ]] || kill "$pid" 2>/dev/null || true
  done
  rm -rf "$work"
}
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; cat "$work/console" >&2; exit 1; }
wait_for() {
  local pattern=$1 file=$2 tries
  for ((tries=0; tries<200; tries++)); do
    if grep -q "$pattern" "$file" 2>/dev/null; then return; fi
    sleep .1
  done
  fail "timed out waiting for $pattern"
}
sed -e "s|^state=.*|state=$work/legacy|" -e "s|^legacy=.*|legacy=$work/no-legacy|" -e "s|^self=.*|self=$work/remote-debug|" \
  -e "s|^public_state=.*|public_state=$work/public-status|" \
  "$here/overlay/usr/local/libexec/daemonarchy-installer/remote-debug" >"$work/remote-debug"
cp "$here/overlay/usr/local/libexec/daemonarchy-installer/network-addresses" "$work/"
chmod 700 "$work/remote-debug"
# A live image may not have the durable parent directory yet.
sed -e "s|^state=.*|state=$work/absent-parent/state|" -e "s|^self=.*|self=$work/fresh-debug|" \
  -e "s|^public_state=.*|public_state=$work/fresh-public-status|" \
  "$work/remote-debug" >"$work/fresh-debug"
chmod 700 "$work/fresh-debug"
"$work/fresh-debug" _start "$((port + 1))" >"$work/fresh-start"
[[ -d $work/absent-parent/state ]] || fail 'first start could not create durable storage'
"$work/fresh-debug" unpair >/dev/null
for key in client unknown; do ssh-keygen -q -t ed25519 -N '' -f "$work/$key"; done
mkfifo "$work/input"
exec 9<>"$work/input"
"$work/remote-debug" listen "$port" <"$work/input" >"$work/console" 2>&1 &
listener=$!
printf 'y\n' >&9
wait_for 'Waiting for an authenticated agent' "$work/console"
ssh_client() {
  timeout 15 ssh -n -p "$port" -i "$work/$1" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$work/known_hosts" \
    -o LogLevel=ERROR root@127.0.0.1 "${@:2}"
}
ssh_client client true >"$work/client-result" 2>&1 &
client=$!
wait_for 'Does this match' "$work/console"
printf 'y\n' >&9
wait "$client"; client=''
printf 'pwd\n' | timeout 15 sftp -q -b - -P "$port" -i "$work/client" \
  -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  -o UserKnownHostsFile="$work/known_hosts" root@127.0.0.1 >"$work/sftp-result" 2>&1 ||
  fail 'approved agent cannot use SFTP after session tracking'
wait_for '^connected=0$' "$work/public-status"
grep -qx 'grant=1' "$work/public-status" || fail 'public grant indicator missing'
grep -qx 'listener=1' "$work/public-status" || fail 'public listener indicator missing'
grep -qx "port=$port" "$work/public-status" || fail 'public listener port missing'
[[ $(wc -l <"$work/public-status") -eq 6 ]] || fail 'public status exposed unexpected fields'
[[ $(stat -f %Lp "$work/public-status") == 644 ]] || fail 'public status is not readable by the desktop'
# Adopt the running legacy listener without changing its host pin or approval.
original_generation=$(cat "$work/legacy/generation")
sed -e "s|^state=.*|state=$work/state|" -e "s|^legacy=.*|legacy=$work/legacy|" "$work/remote-debug" >"$work/updated"
chmod 700 "$work/updated"
mv "$work/updated" "$work/remote-debug"
"$work/remote-debug" status || fail 'adopted listener identity was lost'
ssh_client client true
host=$(sha256 -q "$work/state/host_key.pub")
[[ $(cat "$work/state/generation") != "$original_generation" ]] || fail 'adoption reused legacy ownership'
"$work/remote-debug" _stop "$original_generation"
"$work/remote-debug" status || fail 'legacy EXIT cleanup revoked the adopted grant'
printf 'retained evidence\n' >"$work/state/retained-evidence"

# OS shutdown/terminal loss preserves approval; user stop/unpair still revokes.
kill -TERM "$listener"
wait "$listener" || [[ $? == 143 ]]
listener=''
[[ -f $work/state/active ]] || fail 'shutdown revoked approval'
compgen -G "$work/state/*.approved" >/dev/null || fail 'approved key lost'
[[ ! -f $work/state/console-approval ]] || fail 'unattended console approval remains enabled'
"$work/remote-debug" _suspend "$(cat "$work/state/generation")"
grep -qx 'grant=1' "$work/public-status" || fail 'shutdown discarded public grant indicator'
grep -qx 'listener=0' "$work/public-status" || fail 'shutdown left listener marked active'

# A retained PID now belongs to an unrelated process after reboot.
sleep 60 & unrelated=$!
printf '%s\n' "$unrelated" >"$work/state/sshd.pid"
"$work/remote-debug" resume </dev/null >"$work/resume-result" 2>&1
kill -0 "$unrelated" || fail 'resumption signaled a reused PID'
[[ $(sha256 -q "$work/state/host_key.pub") == "$host" ]] || fail 'host pin changed'
[[ $(cat "$work/state/retained-evidence") == 'retained evidence' ]] || fail 'retained evidence lost'
[[ $(cat "$work/state/generation") != "$original_generation" ]] || fail 'generation reused'
! grep -q 'Enable remote access\|Does this match' "$work/resume-result" || fail 'resume asked for confirmation'
ssh_client client 'printf RESUMED_WITHOUT_APPROVAL' >"$work/resumed-command"
[[ $(cat "$work/resumed-command") == RESUMED_WITHOUT_APPROVAL ]] || fail 'approved key cannot resume'
if ssh_client unknown true >"$work/unknown-result" 2>&1; then fail 'unknown key admitted'; fi

# Repeated automatic resume is idempotent; old teardown cannot stop a new generation.
current_pid=$(cat "$work/state/sshd.pid")
"$work/remote-debug" resume </dev/null
[[ $(cat "$work/state/sshd.pid") == "$current_pid" ]] || fail 'duplicate listener started'
"$work/remote-debug" _stop "$original_generation"
ssh_client client true
ssh_client client 'sleep 60' >"$work/active-command" 2>&1 & client=$!
wait_for '^connected=1$' "$work/public-status"
"$work/remote-debug" unpair
grep -qx 'grant=0' "$work/public-status" || fail 'unpair left public grant active'
grep -qx 'connected=0' "$work/public-status" || fail 'unpair left public connection active'
if wait "$client"; then fail 'unpair left an authenticated connection alive'; fi
client=''
[[ ! -e $work/state ]] || fail 'unpair retained approval'
"$work/remote-debug" resume </dev/null
if ssh_client client true 2>/dev/null; then fail 'revoked grant resumed'; fi
kill -0 "$unrelated" || fail 'unpair signaled unrelated process'
echo 'PASS: durable approval, stable host pin, retained evidence, stale PID/generation safety, unknown-key refusal and explicit revocation'
