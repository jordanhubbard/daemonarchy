#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/target/var/log"
printf 'early disk setup\n' >"$work/live.log"
(
  source "$here/overlay/usr/local/libexec/daemonarchy-installer/install-diagnostics"
  sync() { :; }
  dmesg() { echo 'retained kernel messages'; }
  diagnostics_begin "$work/target" jkh true "$work/live.log"
  diagnostics_phase install
  echo 'package output before interruption'
  diagnostics_result failed 17
  diagnostics_stop
  echo 'after log closure'
) >"$work/stdout"
state=$work/target/var/db/daemonarchy/install
[[ $(cat "$state/status") == failed && $(cat "$state/exit-code") == 17 ]]
[[ $(cat "$state/phase") == install && $(cat "$state/requested-user") == jkh ]]
[[ $(cat "$state/ssh-requested") == true ]]
grep -qx 'retained kernel messages' "$state/kernel-install.log"
grep -qx 'early disk setup' "$work/target/var/log/daemonarchy-install.log"
grep -qx 'package output before interruption' "$work/target/var/log/daemonarchy-install.log"
! grep -q 'after log closure' "$work/target/var/log/daemonarchy-install.log"
grep -qx 'package output before interruption' "$work/stdout"
grep -qx 'after log closure' "$work/stdout"
# An abrupt exit leaves an honest incomplete marker and already-written output.
(
  source "$here/overlay/usr/local/libexec/daemonarchy-installer/install-diagnostics"
  sync() { :; }
  diagnostics_begin "$work/target" jkh false "$work/live.log"
  echo 'last completed package'
  diagnostics_stop
) >/dev/null
[[ $(cat "$state/status") == in-progress ]]
[[ ! -f $state/exit-code && ! -f $state/updated-utc ]]
grep -qx 'last completed package' "$work/target/var/log/daemonarchy-install.log"
echo 'PASS: persistent output, phase/kernel capture, failure/incomplete state, drained logger'
