#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
eval "$(sed -n '/^console_font() {$/,/^}$/p' "$here/overlay/usr/local/libexec/daemonarchy-installer/launch")"
touch "$work/font" "$work/ttydev"
export DAEMONARCHY_CONSOLE_FONT=$work/font
export DAEMONARCHY_CONSOLE_TTY=$work/ttydev
vidcontrol() { printf '%s\n' "$*" >"$work/vidcontrol"; }
tty() { cat "$work/tty"; }
stty() { cat "$work/size"; }

printf '%s\n' /dev/ttyv0 >"$work/tty"
printf '%s\n' '140 448' >"$work/size"
rm -f "$work/vidcontrol"
console_font
[[ $(cat "$work/vidcontrol") == '-f terminus-b32' ]]

printf '%s\n' '40 80' >"$work/size"
rm -f "$work/vidcontrol"
console_font
[[ ! -e $work/vidcontrol ]]

printf '%s\n' '140 448' >"$work/size"
printf '%s\n' /dev/pts/0 >"$work/tty"
console_font
[[ ! -e $work/vidcontrol ]]

printf '%s\n' /dev/ttyv0 >"$work/tty"
DAEMONARCHY_CONSOLE_FONT=$work/missing console_font
[[ ! -e $work/vidcontrol ]]

echo 'PASS: Terminus 16x32 loads only on a wide console'
