#!/usr/local/bin/bash
# Native integration with the snapshot account tools and console configuration.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/rescue-setup"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/root" "$work/etc"
cp /etc/gettytab /etc/ttys "$work/etc/"
: >"$work/root/.profile"
for iteration in 1 2; do
  install_rescue_support "$work" "$here/overlay/usr/local/libexec/daemonarchy-installer" "$here/overlay/usr/local/sbin"
done
[[ $(grep -c '^daemonarchy.Pc|' "$work/etc/gettytab") == 1 ]]
[[ $(grep -c '# Daemonarchy rescue console' "$work/root/.profile") == 1 ]]
grep -q '^ttyv0.*getty daemonarchy.Pc.*onifexists secure' "$work/etc/ttys"
for command in daemonarchy-debug daemonarchy-rescue; do [[ -x $work/usr/local/sbin/$command ]]; done
[[ -x $work/usr/local/libexec/daemonarchy-installer/remote-debug ]]
[[ -x $work/usr/local/libexec/daemonarchy-installer/debug-observe ]]
[[ -r $work/usr/local/libexec/daemonarchy-installer/debug-events.py ]]
[[ -r $work/usr/local/libexec/daemonarchy-installer/network-addresses ]]
sh -n "$work/root/.profile"
echo 'PASS: native rescue installation, ttyv0 configuration and idempotent profile/getty setup'
