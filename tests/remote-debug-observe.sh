#!/usr/bin/env bash
# Native probes, retention, collector restart and session-generation lifecycle.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $(id -u) == 0 ]] || { echo 'Run as root on FreeBSD' >&2; exit 1; }
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /var/tmp/daemonarchy-observe-test.XXXXXX)
collector=''
cleanup() {
  rm -f "$work/state/active"
  if [[ -n $collector ]]; then wait "$collector" 2>/dev/null || true; fi
  rm -rf "$work"
}
trap cleanup EXIT
eval "$(sed '/^case ${1:-snapshot}/,$d' "$here/overlay/usr/local/libexec/daemonarchy-installer/debug-observe")"
state=$work/state
logs=$work/logs
generation=fixture-generation
mkdir -m 700 "$state" "$logs"
touch "$state/active"
printf '%s\n' "$generation" >"$state/generation"
snapshot >"$work/snapshot"
grep -q -- '--- processes ---' "$work/snapshot"
grep -q -- '--- pool-io ---' "$work/snapshot"
grep -q 'Console text-buffer capture unavailable' "$work/snapshot" || grep -q -- '--- console-text ---' "$work/snapshot"
grep -q '=== END SNAPSHOT ===' "$work/snapshot"

# Oversized samples are explicitly bounded, including on the very first write.
dd if=/dev/zero of="$work/large" bs=1048576 count=5 2>/dev/null
rotate_append "$work/large"
[[ $(stat -f %z "$logs/observer.log") -le 1048576 ]]
grep -aq 'SAMPLE TRUNCATED' "$logs/observer.log"
limit=524288
printf 'next sample\n' >"$work/small"
rotate_append "$work/small"
[[ -f $logs/observer.previous.log ]]
limit=$((4 * 1024 * 1024))
collect >"$work/collector-errors" 2>&1 &
collector=$!
for ((attempt=0; attempt<40; attempt++)); do
  grep -aq 'HEARTBEAT' "$logs/observer.log" && break
  kill -0 "$collector"
  sleep 1
done
grep -aq 'HEARTBEAT' "$logs/observer.log"
grep -aq -- '--- kernel exit=0' "$logs/observer.log"
# A replacement generation must terminate this collector, without joining it.
printf 'replacement\n' >"$state/generation"
wait "$collector"
collector=''

# Exercise the real restart decision without touching the system listener.
eval "$(sed '/^source /d; /^case ${1:-shell}/,$d' "$here/overlay/usr/local/libexec/daemonarchy-installer/remote-debug")"
state=$work/state
self=$work/remote-debug
cat >"$work/debug-observe" <<'EOF'
#!/bin/sh
printf 'started\n' >>"$2/starts"
sleep 20
EOF
chmod +x "$work/debug-observe"
printf 'replacement\n' >"$state/generation"
create_observer replacement
first=$(cat "$state/observer.pid")
create_observer replacement
[[ $(cat "$state/observer.pid") == "$first" && $(wc -l <"$state/starts") -eq 1 ]]
# Kill only the fixture process we just created, then prove reconnect restarts.
kill "$first"
wait "$first" 2>/dev/null || true
create_observer replacement
collector=$(cat "$state/observer.pid")
[[ $collector != "$first" && $(wc -l <"$state/starts") -eq 2 ]]
kill "$collector"
wait "$collector" 2>/dev/null || true
collector=''
echo 'PASS: native snapshots, sample bounds, generation exit and collector restart'
