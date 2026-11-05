#!/usr/bin/env bash
# A failed installation keeps an explanation and a menu on the screen; the
# installer's own status decides success; unattended installs never wait.
# Stubs are written in single quotes on purpose; A && B || fail is the check idiom.
# shellcheck disable=SC2015,SC2016
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lib=$here/overlay/usr/local/libexec/daemonarchy-installer
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

# Run a command on a pseudo-terminal, so it sees a console; print what it wrote.
on_tty() {
  python3 - "$@" <<'PY'
import os, pty, select, subprocess, sys, time
master, slave = pty.openpty()
child = subprocess.Popen(sys.argv[1:], stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
os.close(slave)
out, deadline = bytearray(), time.monotonic() + 15
while time.monotonic() < deadline:
    if select.select([master], [], [], 0.1)[0]:
        try:
            data = os.read(master, 65536)
        except OSError:
            data = b''
        if not data and child.poll() is not None:
            break
        out += data
    elif child.poll() is not None:
        break
if child.poll() is None:
    child.kill()
    sys.stdout.buffer.write(out)
    sys.exit('timed out: the command waited on the terminal')
sys.stdout.buffer.write(out)
sys.exit(child.wait())
PY
}

# ------------------------------------------------------------- the explanation

log=$work/install.log summary=$work/install.summary target=$work/mnt
{
  echo '@@phase disk'
  echo '@@phase base'
  for i in $(seq 1 20); do echo "early line $i"; done
  echo '@@phase packages'
  echo '@@step Installing packages'
  echo '@@progress {"schema":"x"}'
  for i in $(seq 1 30); do echo "late line $i"; done
  printf 'pkg progress\033[2K\r\n'
} >"$log"
printf '%s\n' 'DAEMONARCHY / SPECTRUM' 'Total time: 0:12:34' 'Installer stopped (exit 7); inspect the install log.' >"$summary"
mkdir -p "$target/var/db/daemonarchy/install" "$target/var/log"
echo failed >"$target/var/db/daemonarchy/install/status"
echo packages >"$target/var/db/daemonarchy/install/phase"
: >"$target/var/log/daemonarchy-install.log"
export DAEMONARCHY_INSTALL_TARGET=$target DAEMONARCHY_INSTALL_TRACE=$work/trace.jsonl \
  DAEMONARCHY_NETWORK_LOG=$work/network/log
: >"$work/trace.jsonl"

out=$(timeout 10 bash "$lib/install-failed" 7 "$log" "$summary" </dev/null) || fail 'report without a terminal did not return'
grep -qx 'THE INSTALLATION FAILED (installer exit status 7).' <<<"$out" || fail "no headline: $out"
grep -qx 'Last recorded stage: packages (step: Installing packages)' <<<"$out" || fail 'no last stage'
grep -qx 'Recorded on the target disk: status failed, stage packages' <<<"$out" || fail 'no target record'
grep -qx 'Total time: 0:12:34' <<<"$out" || fail 'no summary'
grep -qx -- "--- The last 30 lines of $log ---" <<<"$out" || fail 'no log heading'
grep -qx 'pkg progress\[2K' <<<"$out" && grep -qx 'late line 2' <<<"$out" || fail 'log end missing'
! grep -qx 'late line 1' <<<"$out" || fail 'more than 30 log lines'
! grep -q 'early line' <<<"$out" || fail 'more than 30 log lines'
! grep -q '^@@' <<<"$out" || fail 'progress markers shown'
! grep -q $'\033' <<<"$out" || fail 'terminal control characters reached the console'
for path in "$log" "$work/trace.jsonl" "$target/var/log/daemonarchy-install.log" "$target/var/db/daemonarchy/install"; do
  grep -q "^  $path/\?\$" <<<"$out" || fail "log location $path not listed"
done
grep -qx "  $work/network/log (not written)" <<<"$out" || fail 'missing network log not marked'
rm -rf "$target"
out=$(bash "$lib/install-failed" 1 "$log" "$work/none" </dev/null)
grep -qx '  /var/log/daemonarchy-install.log' <<<"$out" && grep -qx '  /var/db/daemonarchy/install/' <<<"$out" ||
  fail 'target log locations not named when the target is not mounted'
echo 'PASS: the failure explanation names the result, the stage, the log end and every log'

# ------------------------------------------------------------- the menu

copy=$work/libexec
mkdir -p "$copy" "$work/bin"
cp "$lib/install-failed" "$copy/"
printf '#!/bin/sh\necho "live-power $*" >>"%s/calls"\n' "$work" >"$copy/live-power"
# gum answers from a script; an empty answer is Escape.
printf '#!/bin/sh\necho "gum $*" >>"%s/calls"\nsed -n "$(( $(grep -c "^gum" "%s/calls") ))p" "%s/answers"\n' \
  "$work" "$work" "$work" >"$work/bin/gum"
printf '#!/bin/sh\necho "pager $*" >>"%s/calls"\n' "$work" >"$work/bin/pager"
chmod +x "$copy/live-power" "$work/bin/gum" "$work/bin/pager"
printf '%s\n' 'View the full install log' 'Reboot' 'Power off' '' >"$work/answers"
screen=$(PATH="$work/bin:$PATH" PAGER=pager TERM=dumb on_tty bash "$copy/install-failed" 3 "$log" "$summary") ||
  fail "menu did not return on Escape: $screen"
[[ $(grep -c '^gum choose' "$work/calls") == 4 ]] || fail "menu not offered again: $(cat "$work/calls")"
grep -q 'View the full install log' "$work/calls" && grep -q 'Open a shell' "$work/calls" ||
  fail 'menu entries missing'
! grep -qi 'retry' "$work/calls" || fail 'retry offered, but a second run in the same boot is not safe'
grep -qx "pager $log" "$work/calls" || fail 'log viewer not opened'
grep -qx 'live-power reboot' "$work/calls" && grep -qx 'live-power poweroff' "$work/calls" ||
  fail 'reboot or power off not run'
[[ $(grep -c 'THE INSTALLATION FAILED (installer exit status 3)' <<<"$screen") == 4 ]] ||
  fail 'explanation not shown again after each choice'
echo 'PASS: the failure menu views the log, reboots and powers off, and Escape leaves'

rm -f "$work/calls"
screen=$(PATH="$work/bin:$PATH" DAEMONARCHY_UNATTENDED=1 TERM=dumb on_tty bash "$copy/install-failed" 3 "$log" "$summary") ||
  fail "unattended failure waited: $screen"
grep -q 'THE INSTALLATION FAILED' <<<"$screen" || fail 'unattended failure not explained'
[[ ! -e $work/calls ]] || fail 'unattended failure offered a menu'
echo 'PASS: an unattended failure is explained and never waits for a key'

# ------------------------------------------------------------- launch

stubs=$work/stubs
mkdir -p "$stubs"
# The installer prints, then exits with INSTALL_EXIT.
printf '#!/bin/sh\necho installing\nsleep "${INSTALL_SECONDS:-0}"\nexit "${INSTALL_EXIT:-0}"\n' >"$stubs/install"
# A screen that exits 1 whatever happened (as a progress warning used to make it),
# writing its summary; SCREEN_LEFT leaves before the result.
cat >"$stubs/dashboard" <<'SH'
#!/bin/sh
log=$1 status=$2
[ "$3" = --summary-file ] || exit 9
[ -n "${SCREEN_LEFT:-}" ] && exit 130
while [ ! -s "$status" ]; do sleep 0.05; done
echo "summary for status $(cat "$status")" >"$4"
exit 1
SH
printf '#!/bin/sh\necho "install-failed $*"\n' >"$stubs/install-failed"
chmod +x "$stubs"/*
eval "$(sed -n '/^run_install() {$/,/^}$/p;/^install_failed() {$/,/^}$/p' "$lib/launch")"
declare -F run_install install_failed >/dev/null || fail 'launch functions not found'
# shellcheck disable=SC2034  # read by the functions from launch
ISO_LIBEXEC=$stubs log=$work/launch.log status_file=$work/launch.status summary_file=$work/launch.summary serial=()

out=$(INSTALL_EXIT=0 run_install) || fail 'a successful installer reported as failed because the screen exited 1'
[[ $out == 'summary for status 0' ]] || fail "success summary not printed: $out"
INSTALL_EXIT=7 run_install && fail 'a failed installer reported as success'
[[ $install_result == 7 ]] || fail "installer status not used: $install_result"
[[ $(install_failed) == "install-failed 7 $log $summary_file" ]] || fail "failure screen not opened: $(install_failed)"
grep -q installing "$log" || fail 'installer output not logged'
SCREEN_LEFT=1 INSTALL_SECONDS=2 INSTALL_EXIT=0 run_install && fail 'a screen left early reported success'
[[ -z $install_result ]] || fail 'a result invented before the installer finished'
grep -q 'still running' <<<"$(install_failed)" || fail 'running installation not explained'
wait

# Both front ends reach the failure screen, and the unattended one keeps its shell.
unattended=$(sed -n '/^if \[\[ ${DAEMONARCHY_LIVE:-} != 1 \]\] && find_cidata; then$/,/^fi$/p' "$lib/launch")
grep -q 'install_failed 2>&1 | tee' <<<"$unattended" || fail 'unattended failure not explained'
! grep -q 'gum' <<<"$unattended" || fail 'unattended path offers a menu'
grep -q 'exec /bin/sh' <<<"$unattended" || fail 'unattended path lost its shell'
[[ $(sed -n '/^"$ISO_LIBEXEC\/configurator"/,$p' "$lib/launch" | grep -c '^  install_failed$') == 1 ]] ||
  fail 'interactive failure does not open the failure screen'
echo 'PASS: launch follows the installer status, not the screen, and explains a failure'
