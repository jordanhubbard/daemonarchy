#!/usr/bin/env bash
# A tour of the installer's flourishes and sounds, in the order an
# installation meets them: the welcome screen (attract mode and boot chime),
# screen transitions, network check results, the firmware result, the disk
# commit warning and confirmation, then a celebration. Run it on a terminal
# (on FreeBSD with an audio device to hear it), or record it with
#   scripts/installer-visuals-demo.py /dev/null --command scripts/installer-charm-tour.sh --seconds 20 --cast tour.cast
# Nothing here touches a disk or the network: these are the same charm.py and
# sound.py commands the configurator calls, fed with example results.
set -u
lib=$(cd "$(dirname "$0")/../overlay/usr/local/libexec/daemonarchy-installer" && pwd)
share=$(cd "$lib/../../share/daemonarchy-installer" && pwd)
export DAEMONARCHY_SOUND=${DAEMONARCHY_SOUND:-on}
charm() { "$lib/charm" "$@"; }
"$lib/sound" ensure
cols=$(tput cols 2>/dev/null || echo 80)
left=$(((cols - 75) / 2)); ((left < 0)) && left=0
printf '\033[?25l\033[2J'
"$lib/sound" play boot
# Started directly (not through the function) so $! is the animation itself.
"$lib/charm" attract --logo "$share/logo.txt" --top 2 &
anim=$!
sleep 3
kill "$anim" 2>/dev/null; wait "$anim" 2>/dev/null
printf '\033[0m\033[2J\033[H\n'
charm transition 'Checking the network' --left "$left"
echo
sleep 0.4
for result in 'ok Network adapters' 'ok Wired addresses (DHCP)' 'fail DNS' 'ok DNS' 'ok System clock' 'ok Device firmware'; do
  charm result ${result%% *} "${result#* }" --left "$left"
  sleep 0.45
done
sleep 0.6
printf '\033[2J\033[H\n'
charm transition 'MacBook Wi-Fi firmware' --left "$left"
echo
charm result ok 'MacBook Wi-Fi firmware verified and the radio attached' --left "$left"
sleep 1
printf '\033[2J\033[H\n'
charm transition 'Ready to install' --left "$left"
echo
charm warn 'All partitions and data on nda0 will be destroyed.' --left "$left"
sleep 0.8
"$lib/sound" play commit
printf '%*s\033[1mInstall Daemonarchy\033[0m (confirmed)\n' "$left" ''
sleep 1.2
charm cheer 'Welcome to Daemonarchy' "Omarchy's desktop on FreeBSD's daemon"
sleep 1
printf '\033[?25h\033[0m'
