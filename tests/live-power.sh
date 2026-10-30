#!/usr/bin/env bash
# Reboot and power-off must not need the install medium once prepared.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lp=$here/overlay/usr/local/libexec/daemonarchy-installer/live-power
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/rescue" "$work/bin"
# The crunched binary picks its behaviour from argv[0]; the stub records it.
printf '#!/bin/sh\necho "$(basename "$0") $*" >> "%s/calls"\n' "$work" >"$work/rescue/reboot"
chmod +x "$work/rescue/reboot"
printf '#!/bin/sh\necho "shutdown $*" >> "%s/calls"\n' "$work" >"$work/bin/shutdown"
chmod +x "$work/bin/shutdown"
export DAEMONARCHY_RESCUE_DIR=$work/rescue DAEMONARCHY_POWER_DIR=$work/power PATH="$work/bin:$PATH"

# Prepared, then the medium vanishes: the in-memory copies still work.
bash "$lp" prepare
[[ -x $work/power/reboot && -x $work/power/halt ]]
rm -rf "$work/rescue"
bash "$lp" reboot
bash "$lp" poweroff
[[ $(sed -n 1p "$work/calls") == 'reboot ' ]]
[[ $(sed -n 2p "$work/calls") == 'halt -p' ]]
[[ $(wc -l <"$work/calls") == 2 ]]

# Not prepared (no rescue tools): fall back to shutdown rather than fail.
rm -rf "$work/power" "$work/calls"
bash "$lp" prepare
bash "$lp" reboot
bash "$lp" poweroff
[[ $(sed -n 1p "$work/calls") == 'shutdown -r now' ]]
[[ $(sed -n 2p "$work/calls") == 'shutdown -p now' ]]

# Every reboot path in the installer goes through it.
for f in launch live-backend; do
  ! grep -nE '(^|[^-_a-z])shutdown -[rp] now' "$here/overlay/usr/local/libexec/daemonarchy-installer/$f" \
    || { echo "$f still calls shutdown directly" >&2; exit 1; }
done
grep -q 'live-power" prepare' "$here/overlay/usr/local/libexec/daemonarchy-installer/launch"
! bash "$lp" bogus 2>/dev/null
echo 'live-power checks passed'
