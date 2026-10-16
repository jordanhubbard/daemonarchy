#!/usr/local/bin/bash
# Real SSH pairing and progress lifecycle, isolated from the system sshd.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /root/daemonarchy-debug-qa.XXXXXX)
port=${DEBUG_TEST_PORT:-23451}
listener='' client=''
cleanup() {
  [[ -z $client ]] || kill "$client" 2>/dev/null || true
  [[ -z $listener ]] || kill "$listener" 2>/dev/null || true
  [[ -z $listener ]] || wait "$listener" 2>/dev/null || true
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
sed -e "s|^state=.*|state=$work/state|" \
    -e "s|^self=.*|self=$work/remote-debug|" \
    "$here/overlay/usr/local/libexec/daemonarchy-installer/remote-debug" >"$work/remote-debug"
cp "$here/overlay/usr/local/libexec/daemonarchy-installer/network-addresses" "$work/"
chmod 700 "$work/remote-debug"
ssh-keygen -q -t ed25519 -N '' -f "$work/client"
ssh-keygen -q -t ed25519 -N '' -f "$work/rejected"
mkfifo "$work/input"
exec 9<>"$work/input"
"$work/remote-debug" listen "$port" <"$work/input" >"$work/console" 2>&1 &
listener=$!
printf 'y\n' >&9
wait_for 'Waiting for an authenticated agent' "$work/console"
ssh_client() {
  ssh -n -p "$port" -i "$work/$1" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o LogLevel=ERROR root@127.0.0.1 "${@:2}"
}
ssh_client rejected true >"$work/rejected-result" 2>&1 &
client=$!
wait_for 'Does this match' "$work/console"
printf 'n\n' >&9
if wait "$client"; then fail 'rejected key connected'; fi
client=''
[[ ! -d $work/state/connected ]] || fail 'rejection announced a connection'
ssh_client client 'printf PRIVATE_COMMAND_RESULT' >"$work/result" 2>&1 &
client=$!
# A second prompt must appear before answering the approved key's request.
for ((tries=0; tries<200; tries++)); do
  [[ $(grep -c 'Does this match' "$work/console") -ge 2 ]] && break
  sleep .1
done
[[ $(grep -c 'Does this match' "$work/console") -ge 2 ]] || fail 'no second pairing prompt'
printf 'y\n' >&9
wait "$client"
client=''
[[ $(cat "$work/result") == PRIVATE_COMMAND_RESULT ]] || fail 'forced command changed output'
wait_for 'Agent connected successfully' "$work/console"
ssh_client client "$work/remote-debug activity 'Checking Wi-Fi connectivity'"
wait_for 'Activity: Checking Wi-Fi connectivity' "$work/console"
ssh_client client true
sleep 2
if grep -q 'It is OK to stop\|PRIVATE_COMMAND_RESULT' "$work/console"; then
  fail 'command output leaked or disconnect marked completion'
fi
# The forced-command path must preserve the SFTP subsystem used by modern scp.
printf 'pwd\n' >"$work/sftp-batch"
sftp -P "$port" -i "$work/client" -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -b "$work/sftp-batch" root@127.0.0.1 >"$work/sftp-result" 2>&1
grep -q 'Remote working directory' "$work/sftp-result" || fail 'SFTP failed'
ssh_client client "$work/remote-debug done"
wait_for 'It is OK to stop this session' "$work/console"
ssh_client client 'sleep 60' >"$work/active-result" 2>&1 &
client=$!
sleep 1
printf '\n' >&9
wait "$listener"
listener=''
if wait "$client"; then fail 'stopping did not close an active connection'; fi
client=''
[[ ! -e $work/state ]] || fail 'pairing state survived stopping'
if ssh_client client true 2>/dev/null; then fail 'listener still accepts connections'; fi
echo 'PASS: native SSH rejection/approval, connection/activity/completion console feedback, reconnect, SFTP and stop cleanup'
