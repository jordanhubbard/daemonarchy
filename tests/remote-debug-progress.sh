#!/usr/bin/env bash
# Exercise progress state and the actual forced command without starting sshd.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
helper=$here/overlay/usr/local/libexec/daemonarchy-installer/remote-debug
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
eval "$(sed '/^source /d; /^case ${1:-shell}/,$d' "$helper")"
state=$work/state
mkdir "$state"
touch "$state/active"
id() { echo 0; }
(SSH_ORIGINAL_COMMAND="printf 'command result'" debug_session) >"$work/result"
[[ $(cat "$work/result") == 'command result' ]]
# shellcheck disable=SC2034
last_progress=''
show_progress >"$work/console"
grep -q 'Agent connected successfully' "$work/console"
debug_activity $'Checking Wi-Fi\n\033[2J' >/dev/null
show_progress >>"$work/console"
grep -q 'Activity: Checking Wi-Fi ' "$work/console"
if LC_ALL=C grep -q $'\033' "$work/console"; then exit 1; fi
# Ordinary reconnects and completed commands preserve task-level activity.
(SSH_ORIGINAL_COMMAND=true debug_session)
[[ $(cat "$state/progress") == 'Activity: Checking Wi-Fi [2J' ]]
before=$(wc -l <"$work/console")
show_progress >>"$work/console"
[[ $(wc -l <"$work/console") == "$before" ]]
write_progress 'Remote debugging complete. It is OK to stop this session (press Enter).'
show_progress >>"$work/console"
grep -q 'It is OK to stop' "$work/console"
[[ -f $state/active ]]
rm "$state/active"
if (debug_activity 'Should fail') 2>/dev/null; then exit 1; fi
if (SSH_ORIGINAL_COMMAND=true debug_session) 2>/dev/null; then exit 1; fi
echo 'PASS: authenticated command, activity sanitization, reconnect, explicit completion, stopped access'
