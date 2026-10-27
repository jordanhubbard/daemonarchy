#!/usr/bin/env bash
# Charm and sound wiring in the configurator, the network pipeline and the
# install engine: the right flourish and sound for each real result, the
# sound choice carried into the installed system, and nothing that can fail.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lib=$here/overlay/usr/local/libexec/daemonarchy-installer
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

# The network pipeline reports every step's status to the result hook, before its report.
(
  # shellcheck source=/dev/null
  source "$lib/network-bringup"
  nb_hook_run() { [[ $1 == dns ]]; }
  nb_hook_show() { echo "show $1" >>"$work/order"; }
  nb_hook_result() { echo "result $1 $2" >>"$work/order"; }
  nb_run discover || true
  nb_run dns || true
)
[[ $(cat "$work/order") == $'result discover 1\nshow discover\nresult dns 0\nshow dns' ]] || fail "pipeline order: $(cat "$work/order")"

# The configurator marks each result with charm: ok or fail, a readable label.
for function in nb_hook_result sound_step write_install_conf; do
  eval "$(sed -n "/^$function() {$/,/^}$/p" "$lib/configurator")"
done
PADDING_LEFT=3
CHARM=$work/charm SOUND=$work/sound
printf '#!/bin/sh\necho "charm $*" >>%s/calls\n' "$work" >"$CHARM"
printf '#!/bin/sh\necho "sound $*" >>%s/calls\n[ "$1" = label ] && echo "♪ 70%%"\nexit 0\n' "$work" >"$SOUND"
chmod +x "$CHARM" "$SOUND"
nb_hook_result dhcp 0
nb_hook_result clock 2
nb_hook_result firmware 0
nb_hook_result unknown-step 0
grep -qx 'charm result ok Wired addresses (DHCP) --left 3' "$work/calls" || fail 'DHCP ok mark'
grep -qx 'charm result fail System clock --left 3' "$work/calls" || fail 'clock failure mark'
grep -qx 'charm result ok Device firmware --left 3' "$work/calls" || fail 'firmware mark'
[[ $(grep -c '^charm result' "$work/calls") == 3 ]] || fail 'an unknown step is not announced'

# The sound option sets the player's mode and the installed system's default.
step() { :; }
say() { :; }
sleep() { :; }
gum() { echo "Quiet (only the moments that matter)"; }
sound_mode=''
sound_step >/dev/null
[[ $sound_mode == quiet ]] || fail "sound_mode=$sound_mode"
grep -qx 'sound ctl mode=quiet' "$work/calls" || fail 'mode not applied'
gum() { echo Back; }
sound_step >/dev/null
[[ $sound_mode == quiet ]] || fail 'Back changed the choice'
gum() { return 1; }
sound_step >/dev/null  # Escape keeps the choice and never aborts the installer.
DAEMONARCHY_INSTALL_CONF=$work/install.conf
for name in disk install_mode partition_index efi_index free_start install_size_mib disk_snapshot \
  encrypt_installation keyboard username password password_hash full_name email_address hostname timezone \
  net_mode net_if net_addr net_gw net_dns net_dns_source wifi_ssid wifi_psk wifi_hidden \
  wifi_enterprise_profile APPLE_FIRMWARE_STAGE ssh_enable install_ports install_src install_cuda; do
  printf -v "$name" '%s' x
done
write_install_conf
grep -qx 'sound=quiet' "$work/install.conf" || fail 'install.conf lacks the sound choice'

# The installed system: the chime's loader default, USB audio, the rc script and raw chimes.
target=$work/target
mkdir -p "$target/boot/kernel"
: >"$target/boot/kernel/snd_uaudio.ko"
: >"$target/boot/loader.conf"
ISO_SHARE=$here/overlay/usr/local/share/daemonarchy-installer
install() { command install "$@"; }
# shellcheck source=/dev/null
source "$lib/sound-setup"
sound=quiet sound_install_target "$target"
grep -qx 'daemonarchy.sound="quiet"' "$target/boot/loader.conf" || fail 'loader default'
grep -qx 'snd_uaudio_load="YES"' "$target/boot/loader.conf" || fail 'USB audio module'
[[ -x $target/usr/local/etc/rc.d/daemonarchy_greeting ]] || fail 'rc script'
[[ -e $target/var/db/daemonarchy/first-boot-greeting ]] || fail 'first-boot marker'
for cue in boot greeting; do
  [[ $(wc -c <"$target/usr/local/share/daemonarchy/sounds/$cue.u8") -gt 4000 ]] || fail "raw $cue chime"
done
for file in sound.py charm.py progress-dashboard.py progress-model.py; do
  [[ -f $target/usr/local/libexec/daemonarchy/$file ]] || fail "missing $file"
done
# Unattended without a request: the installed system stays silent too.
: >"$target/boot/loader.conf"
sound='' DAEMONARCHY_UNATTENDED=1 sound_install_target "$target"
grep -qx 'daemonarchy.sound="off"' "$target/boot/loader.conf" || fail 'unattended default'
# A broken target never fails the install.
sound=on sound_install_target "$work/no-such-target" >/dev/null || fail 'sound setup failed the install'
sh -n "$here/overlay/usr/local/share/daemonarchy-installer/greeting/daemonarchy_greeting"
echo 'PASS: network result marks, sound choice, installed chime and first-boot welcome, never fatal'
