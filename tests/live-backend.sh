#!/usr/bin/env bash
# The graphical installer's privileged backend against stubbed FreeBSD tools:
# it must write exactly the answer file the text configurator writes, refuse
# the same bad answers, keep the install medium out of the disk list, and
# start the same install engine only for the confirmed disk.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lib=$here/overlay/usr/local/libexec/daemonarchy-installer
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/bin" "$work/libexec" "$work/share/compat" "$work/state"
for file in "$lib"/*; do ln -s "$file" "$work/libexec/$(basename "$file")"; done
rm "$work/libexec/install"
cat >"$work/libexec/install" <<'EOF'
#!/usr/bin/env bash
source "$DAEMONARCHY_INSTALL_CONF"
echo '@@phase disk'
echo "@@progress {\"schema\":\"daemonarchy/installer-progress@1\",\"phase\":\"disk\",\"label\":\"Storage preparation milestones\",\"current\":1,\"total\":3,\"unit\":\"milestones\"}"
echo "installing to $disk"
exit "${FAKE_INSTALL_STATUS:-0}"
EOF
chmod +x "$work/libexec/install"
cp "$here/overlay/usr/local/share/daemonarchy-installer/checkouts.json" "$work/share/"
printf 'logo\n' >"$work/share/logo.txt"
printf '1.4.0 (test)\n' >"$work/share/version"
printf 'messagebus\n' >"$work/share/reserved-users"
# The rules Omarchy's setup form defines (the real form is extracted from the
# omarchy package when the image is built).
cat >"$work/share/setup-form.sh" <<'EOF'
OMARCHY_FORM_BACK=1
OMARCHY_KEYBOARD_LAYOUTS=$'English (US)|us\nGerman|de'
OMARCHY_USERNAME_PATTERN='^[a-z_][a-z0-9_-]*[$]?$'
OMARCHY_RESERVED_USERNAMES='^(root|bin|daemon|sddm)$'
OMARCHY_HOSTNAME_PATTERN='^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$'
OMARCHY_HOSTNAME_DEFAULT='daemonarchy'
omarchy_username_taken() { return 1; }
EOF
printf '#!/bin/sh\n[ "$1" = list-timezones ] && printf "UTC\\nEurope/Berlin\\nAmerica/Los_Angeles\\n"\n' >"$work/share/compat/timedatectl"
chmod +x "$work/share/compat/timedatectl"

stub() { printf '#!/usr/bin/env bash\n%s\n' "$2" >"$work/bin/$1"; chmod +x "$work/bin/$1"; }
stub id '[[ $1 == -u ]] && echo 0'
stub kenv 'exit 0'
stub pw '[[ $1 == usershow && $2 == live ]]'
stub sysctl 'case "$*" in "-n kern.disks") echo "ada0 da0 cd0" ;; "-n machdep.bootmethod") echo UEFI ;; *) exit 1 ;; esac'
stub glabel 'echo "iso9660/DAEMONARCHY  N/A  da0"'
stub diskinfo 'case "$1" in -s) echo SERIAL-$2 ;; ada0) echo "ada0 512 ${ADA0_BYTES:-64000000000} 125000000 0 0" ;; da0) echo "da0 512 32000000000 62500000 0 0" ;; *) exit 1 ;; esac'
stub geom 'printf "Geom name: %s\n   Mode: r0w0e0\n   descr: QEMU HARDDISK\n" "$3"'
stub gpart 'case "$1" in
  backup) printf "GPT 128\n1 efi 40 532480 efiboot0 0\n2 ms-basic-data 532520 104857600 data 0\n" ;;
  list) printf "Geom name: %s\nscheme: GPT\nstate: OK\n   Mode: r0w0e0\n" "$2" ;;
  show) printf "=>  40  125000000  %s  GPT\n" "$2" ;;
  *) exit 1 ;;
esac'
stub sha256 'sha256sum | cut -d" " -f1'
stub fetch '[[ ${FAKE_OFFLINE:-} != 1 ]] || { echo "fetch: Network is unreachable" >&2; exit 1; }'
stub route 'printf "   interface: vtnet0\n"'
stub ifconfig '[[ "$*" == "-l ether" ]] && echo vtnet0'
stub tzupdate 'exit 1'
stub stat '[[ $1 == -f ]] && echo "0:$(/usr/bin/stat -c %a "$3")"'
stub pgrep 'exit 1'
stub daemon 'shift; exec "$@"'
stub stty 'exit 1'
# check_shared_efi's read-only ESP probe.
stub mount '[[ "$*" == "-t msdosfs -o ro /dev/ada0p1 "* ]]'
stub umount 'exit 0'
stub df 'printf "Filesystem 1024-blocks Used Avail\n/dev/ada0p1 260000 1000 259000\n"'

backend() {
  env LIVE_BACKEND_TEST_PATH="$work/bin" ISO_LIBEXEC="$work/libexec" ISO_SHARE="$work/share" \
    LIVE_STATE="$work/state" DAEMONARCHY_INSTALL_CONF="$work/install.conf" \
    INSTALL_LOG="$work/install.log" INSTALL_STATUS="$work/install.status" \
    bash "$lib/live-backend" "$@"
}
snapshot=$(backend partitions ada0 | jq -er '.snapshot')
request() {
  jq -cn --arg snapshot "$snapshot" '{keyboard: "de", username: "alice", password: "s3cret pass",
    password_confirmation: "s3cret pass", full_name: "Alice Example", email_address: "alice@example.org",
    hostname: "", timezone: "Europe/Berlin", ssh_enable: true, install_ports: false, install_src: true,
    encrypt_installation: true, disk: "ada0", disk_snapshot: $snapshot, install_mode: "whole_disk"}' |
    jq -c "${1:-.}"
}
expect_invalid() {
  local filter=$1 field=$2 output
  if output=$(request "$filter" | backend write-conf); then
    echo "Accepted invalid answers: $filter" >&2; exit 1
  fi
  [[ $(jq -r .field <<<"$output") == "$field" ]] || { echo "Wrong field for $filter: $output" >&2; exit 1; }
  [[ ! -e $work/install.conf ]] || { echo "Wrote answers for $filter" >&2; exit 1; }
}

# Facts: the install medium (da0) and optical drives are never offered.
facts=$(backend facts)
[[ $(jq -c '[.disks[].name]' <<<"$facts") == '["ada0"]' ]]
[[ $(jq -r '.keyboards[1].code' <<<"$facts") == de ]]
jq -e '.timezones | index("Europe/Berlin")' <<<"$facts" >/dev/null
jq -e '.checkouts.ports.download_mib > 0 and .checkouts.src.extra_gib > 0' <<<"$facts" >/dev/null
parts=$(backend partitions ada0)
[[ $(jq -c '[.efi[].index, .partitions[].index]' <<<"$parts") == '[1,2]' ]]
if backend partitions da0 >/dev/null; then echo 'Offered the install medium' >&2; exit 1; fi

# Invalid answers are refused with the field to revisit, and nothing is written.
expect_invalid '.username = "Bad Name"' username
expect_invalid '.username = "root"' username
expect_invalid '.username = "live"' username
expect_invalid '.password_confirmation = "other"' password
expect_invalid '.password = "" | .password_confirmation = ""' password
expect_invalid '.hostname = "-bad-"' hostname
expect_invalid '.timezone = "Mars/Base"' timezone
expect_invalid '.keyboard = "xx"' keyboard
expect_invalid '.disk = "da0"' disk
expect_invalid '.disk_snapshot = ("0" * 64)' disk
expect_invalid '.install_mode = "everything"' install_mode
expect_invalid '.ssh_enable = "yes"' ssh_enable
expect_invalid '.full_name = "two\nlines"' full_name
expect_invalid '.install_mode = "partition" | .efi_index = "1" | .partition_index = "2" | .confirm_partition = "ada0p3"' confirm_partition
FAKE_OFFLINE=1 expect_invalid '.' network
if backend install ada0 >/dev/null; then echo 'Installed without answers' >&2; exit 1; fi

# Valid answers: the same file the text configurator writes for these answers.
backend write-conf < <(request) | jq -e '.ok' >/dev/null
[[ $(stat -c %a "$work/install.conf") == 600 ]]
(
  source "$work/install.conf"
  [[ $disk == ada0 && $install_mode == whole_disk && $keyboard == de && $username == alice ]]
  [[ $hostname == daemonarchy && $timezone == Europe/Berlin && $ssh_enable == true ]]
  [[ $install_ports == false && $install_src == true && $install_cuda == false && $encrypt_installation == true ]]
  [[ $net_mode == dhcp && $net_if == vtnet0 && $disk_snapshot == "$snapshot" ]]
  [[ $password == 's3cret pass' && $password_hash == '$6$'* ]]
  [[ $(printf '%s' "$password" | openssl passwd -6 -salt "$(cut -d'$' -f3 <<<"$password_hash")" -stdin) == "$password_hash" ]]
)
(
  ISO_SHARE=$work/share DAEMONARCHY_INSTALL_CONF=$work/expected.conf
  eval "$(sed -n '/^write_install_conf() {$/,/^}$/p' "$lib/configurator")"
  source "$work/install.conf"
  APPLE_FIRMWARE_STAGE=$apple_firmware_stage
  write_install_conf
)
diff <(grep -v '^password_hash=' "$work/expected.conf") <(grep -v '^password_hash=' "$work/install.conf")

# Shared-disk answers need the typed partition confirmation.
rm -f "$work/install.conf"
request '.install_mode = "partition" | .efi_index = "1" | .partition_index = "2" | .confirm_partition = "ada0p2"' |
  backend write-conf | jq -e '.ok' >/dev/null
grep -qx 'partition_index=2' "$work/install.conf"
grep -qx 'efi_index=1' "$work/install.conf"

# Install only the confirmed disk, through the same engine, log and result.
if backend install da0 >/dev/null; then echo 'Installed an unconfirmed disk' >&2; exit 1; fi
backend install ada0 | jq -e '.ok' >/dev/null
[[ $(cat "$work/install.status") == 0 ]]
grep -qx '@@phase disk' "$work/install.log"
grep -qx 'installing to ada0' "$work/install.log"
rm -f "$work/install.status"
FAKE_INSTALL_STATUS=3 backend install ada0 >/dev/null
[[ $(cat "$work/install.status") == 3 ]]
if backend power reboot >/dev/null; then echo 'Rebooted after a failed install' >&2; exit 1; fi

# Network changes and unknown commands are checked too.
if backend network-dhcp 'vtnet0;reboot' >/dev/null; then echo 'Accepted an invalid interface' >&2; exit 1; fi
if backend network-static vtnet0 192.168.1.5 192.168.1.1 1.1.1.1 >/dev/null; then echo 'Accepted an address without prefix' >&2; exit 1; fi
if backend terminal-step shell >/dev/null; then echo 'Accepted an unknown text step' >&2; exit 1; fi
if backend sh -c id >/dev/null; then echo 'Accepted an unknown command' >&2; exit 1; fi
stub id '[[ $1 == -u ]] && echo 1000'
if backend facts >/dev/null; then echo 'Ran without root' >&2; exit 1; fi
echo 'PASS: graphical backend writes the text installer answers, refuses bad input, installs only the confirmed disk'
