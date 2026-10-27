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
# A long list after the chosen zones: a pipefail "| grep -q" check takes
# SIGPIPE here, as the real zone list did natively.
printf '#!/bin/sh\n[ "$1" = list-timezones ] && { printf "UTC\\nEurope/Berlin\\nAmerica/Los_Angeles\\n"; seq -f "Etc/Zone%%g" 1 8000; }\n' >"$work/share/compat/timedatectl"
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
# A fresh throwaway answer per run, with a space to exercise quoting.
answer="fixture $(openssl rand -hex 8)"
request() {
  jq -cn --arg snapshot "$snapshot" --arg answer "$answer" '{keyboard: "de", username: "alice", password: $answer,
    password_confirmation: $answer, full_name: "Alice Example", email_address: "alice@example.org",
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
  [[ $password == "$answer" && $password_hash == '$6$'* ]]
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

# ---------------------------------------------------------------- network
# The network page runs network-bringup's pipeline with the text installer's
# adoption rules. Each step runs from a recorded fake (as network-bringup's
# own tests shim the network), so both front-ends can be compared directly.
mkdir -p "$work/fake"
cat >"$work/fake/bringup" <<'EOF2'
#!/usr/bin/env bash
source "$REAL_LIB/network-bringup"
step=$1; shift
printf '%s %s\n' "$step" "$*" >>"$FAKE/steps"
lease() { printf 'status=lease\naddress=%s\ngateway=%s\ngateway_ok=yes\ndns=%s\n' "$2" "$3" "$4" >"$NB_STATE/dhcp/$1"; }
case $step in
  discover) nb_begin discover; nb_set wired 'em0 em1'; nb_say 'Wired adapters: em0, em1.' ;;
  dhcp)
    nb_begin dhcp
    lease em0 192.0.2.10 192.0.2.1 192.0.2.53
    lease em1 198.51.100.10 198.51.100.1 198.51.100.53
    nb_set primary "${1:-em0}"
    nb_say 'em0: address 192.0.2.10, gateway 192.0.2.1, DNS 192.0.2.53.'
    nb_say "Primary connection: ${1:-em0}."
    ;;
  primary) nb_begin dhcp; nb_set primary "$1"; nb_say "Primary connection: $1." ;;
  dns|dns-fallback)
    nb_begin dns
    if [[ -f $FAKE/dns-ok ]]; then
      nb_set dns "$(cat "$FAKE/dns-ok")"; nb_set dns_source dhcp
      nb_say "DNS answers through $(nb_get primary) at $(cat "$FAKE/dns-ok")."
    else
      nb_say 'None of 6 DNS servers answered a lookup of pkg.FreeBSD.org.'; exit 1
    fi
    ;;
  dns-try)
    nb_begin dns
    if [[ $1 == "$(cat "$FAKE/user-dns" 2>/dev/null)" ]]; then
      nb_set dns "$1"; nb_set dns_source user; nb_say "$1 answered; using it."
    else
      nb_say "$1 did not answer a lookup of pkg.FreeBSD.org; it was not used."; exit 1
    fi
    ;;
  clock)
    nb_begin clock
    if [[ -f $FAKE/ntp-ok ]]; then nb_set clock synchronized; nb_say 'Clock set from network time server pool.ntp.org.'
    else nb_set clock wrong; nb_say 'Network time synchronization did not answer.'; exit 1; fi
    ;;
  firmware) nb_begin firmware; nb_say 'Every network device has its firmware.' ;;
  wifi-prepare) nb_begin wifi-prepare; nb_say 'No Wi-Fi radio.'; exit 1 ;;
  static) nb_begin dhcp; nb_set primary "$1"; nb_say "Static address $2 on $1, gateway $3." ;;
  *) exit 2 ;;
esac
EOF2
chmod +x "$work/fake/bringup"
stub gum 'case $1 in spin) while [[ $1 != -- ]]; do shift; done; shift; exec "$@" ;; style) shift; printf "%s\n" "${@: -1}" ;; confirm) exit 1 ;; *) exit 1 ;; esac'
stub date 'case "$*" in *" -j "*|"-j "*) printf "%s\n" "${@: -2:1}" ;; "-u -f %Y-%m-%d %H:%M:%S "*) echo set >>"$FAKE/clock-set" ;; *) exec /bin/date "$@" ;; esac'
stub service 'exit 1'
network_env=(NB_EXEC="$work/fake/bringup" REAL_LIB="$lib" FAKE="$work/fake" NB_STATE="$work/nb" NB_LOG="$work/nb/log"
  NB_RESOLV_CONF="$work/resolv.conf" NB_SIGNING_CERTS="$work/none.pem")
net() { env "${network_env[@]}" bash -c 'backend "$@"' net "$@"; }
export -f backend
export work lib
reset_network() { rm -rf "$work/nb" "$work/state/network.state" "$work/fake/"{steps,dns-ok,ntp-ok,user-dns,clock-set}; : >"$work/resolv.conf"; }
# The text installer's own network_bringup_ui, with its screens stubbed.
tui_decisions() {
  env "${network_env[@]}" PATH="$work/bin:$PATH" ISO_SHARE="$work/share" bash -c '
    source "$(dirname "$0")/configurator" 2>/dev/null
    step() { :; }; say() { :; }
    network_bringup_ui >/dev/null 2>&1
    printf "%s|%s|%s|%s|%s|%s\n" "$net_mode" "$net_if" "$net_dns" "$net_dns_source" "$(nb_get primary)" "$(nb_get clock)"
  ' "$work/libexec/tui"
}
live_decisions() {
  (source "$work/state/network.state"
   printf '%s|%s|%s|%s|%s|%s\n' "$net_mode" "$net_if" "$net_dns" "$net_dns_source" "$(jq -r .primary <<<"$1")" "$(jq -r '.clock_state' <<<"$1")")
}

# Everything works: the same primary, DNS and clock as the text installer,
# with each step's plain-language report and the other leased port offered.
reset_network
echo 192.0.2.53 >"$work/fake/dns-ok"; touch "$work/fake/ntp-ok"
status=$(net network-check)
jq -e '.checked and .primary == "em0" and .alternatives == ["em1"] and .need == "" and .failure == ""' <<<"$status" >/dev/null
jq -e '.reports.dhcp | index("Primary connection: em0.")' <<<"$status" >/dev/null
jq -e '.reports.dns[0] == "DNS answers through em0 at 192.0.2.53."' <<<"$status" >/dev/null
jq -e '.reports.clock[0] | startswith("Clock set from network time")' <<<"$status" >/dev/null
live=$(live_decisions "$status")
[[ $live == 'dhcp|em0|192.0.2.53|dhcp|em0|synchronized' ]] || { echo "live decisions: $live" >&2; exit 1; }
reset_network; echo 192.0.2.53 >"$work/fake/dns-ok"; touch "$work/fake/ntp-ok"
[[ $(tui_decisions) == "$live" ]] || { echo "TUI decided $(tui_decisions), live $live" >&2; exit 1; }
# The primary-interface override, then DNS and the clock are proved again.
reset_network; echo 192.0.2.53 >"$work/fake/dns-ok"; touch "$work/fake/ntp-ok"
net network-check >/dev/null
: >"$work/fake/steps"
status=$(net network-primary em1)
[[ $(jq -r .primary <<<"$status") == em1 ]]
grep -qx 'net_if=em1' "$work/state/network.state"
[[ $(cut -d' ' -f1 "$work/fake/steps" | tr '\n' ' ') == 'primary dns clock ' ]]
[[ $(net network-primary em7 | jq -r .field) == primary ]]
if net network-primary 'em1;reboot' >/dev/null; then echo 'Accepted an invalid primary' >&2; exit 1; fi

# No DNS answers: the page asks for a server, which must answer before use.
reset_network; touch "$work/fake/ntp-ok"
status=$(net network-check)
jq -e '.need == "dns" and (.failure | startswith("No DNS server answered"))' <<<"$status" >/dev/null
live=$(live_decisions "$status")
reset_network; touch "$work/fake/ntp-ok"
[[ $(tui_decisions) == "$live" ]] || { echo "TUI decided $(tui_decisions), live $live (DNS)" >&2; exit 1; }
reset_network; touch "$work/fake/ntp-ok"; net network-check >/dev/null
[[ $(net network-dns 300.1.1.1 | jq -r .field) == dns ]]
[[ $(net network-dns 192.0.2.99 | jq -r .field) == dns ]]
echo 192.0.2.99 >"$work/fake/user-dns"
status=$(net network-dns 192.0.2.99)
jq -e '.need == "" and .dns == "192.0.2.99" and .dns_source == "user"' <<<"$status" >/dev/null
grep -qx 'net_dns_source=user' "$work/state/network.state"

# Network time fails: only then may the clock be set by hand, and only a
# usable time is accepted. A working clock is never set by hand.
reset_network; echo 192.0.2.53 >"$work/fake/dns-ok"
status=$(net network-check)
jq -e '.need == "clock" and .manual_clock and .clock_state == "wrong"' <<<"$status" >/dev/null
live=$(live_decisions "$status")
reset_network; echo 192.0.2.53 >"$work/fake/dns-ok"
[[ $(tui_decisions) == "$live" ]] || { echo "TUI decided $(tui_decisions), live $live (clock)" >&2; exit 1; }
reset_network; echo 192.0.2.53 >"$work/fake/dns-ok"; net network-check >/dev/null
[[ $(net clock-set 'yesterday' | jq -r .field) == clock ]]
[[ ! -e $work/fake/clock-set ]]
status=$(net clock-set "$(/bin/date -u '+%Y-%m-%d %H:%M:%S')")
jq -e '.clock_state == "manual" and .need == ""' <<<"$status" >/dev/null
[[ -s $work/fake/clock-set ]]
reset_network; echo 192.0.2.53 >"$work/fake/dns-ok"; touch "$work/fake/ntp-ok"; net network-check >/dev/null
[[ $(net clock-set "$(/bin/date -u '+%Y-%m-%d %H:%M:%S')" | jq -r .field) == clock ]]
[[ ! -e $work/fake/clock-set ]]
rm -f "$work/bin/gum" "$work/bin/date" "$work/bin/service"

# Network changes and unknown commands are checked too.
if backend network-dhcp 'vtnet0;reboot' >/dev/null; then echo 'Accepted an invalid interface' >&2; exit 1; fi
if backend network-static vtnet0 192.168.1.5 192.168.1.1 1.1.1.1 >/dev/null; then echo 'Accepted an address without prefix' >&2; exit 1; fi
if backend terminal-step shell >/dev/null; then echo 'Accepted an unknown text step' >&2; exit 1; fi
if backend sh -c id >/dev/null; then echo 'Accepted an unknown command' >&2; exit 1; fi
stub id '[[ $1 == -u ]] && echo 1000'
if backend facts >/dev/null; then echo 'Ran without root' >&2; exit 1; fi
echo 'PASS: graphical backend makes the text installer network decisions, writes its answers, refuses bad input, installs only the confirmed disk'
