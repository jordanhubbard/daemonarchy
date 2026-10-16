#!/bin/sh
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
ssh-keygen -q -t ed25519 -N '' -f "$work/operator"
"$here/scripts/prepare-headless-rescue.sh" "$work/operator.pub" "$work/overlay" >"$work/output"
payload=$work/overlay/usr/local/share/daemonarchy-installer/headless
cmp "$work/operator.pub" "$payload/authorized_keys"
ssh-keygen -l -f "$payload/host_key.pub" >/dev/null
[ -x "$work/overlay/usr/local/etc/rc.d/daemonarchy-headless" ]
grep -q '^devmatch_blocklist=.*apple_bce.*amdgpu' "$work/overlay/boot/loader.conf.local"
[ "$(find "$work/overlay" -type f | wc -l | tr -d ' ')" = 5 ]
if "$here/scripts/prepare-headless-rescue.sh" "$work/operator.pub" "$work/overlay" >/dev/null 2>&1; then echo "Unexpected acceptance" >&2; exit 1; fi
if "$here/scripts/prepare-headless-rescue.sh" "$work/operator" "$work/private-rejected" >/dev/null 2>&1; then echo "Unexpected acceptance" >&2; exit 1; fi
cat "$work/operator.pub" "$work/operator.pub" >"$work/two.pub"
if "$here/scripts/prepare-headless-rescue.sh" "$work/two.pub" "$work/multiple-rejected" >/dev/null 2>&1; then echo "Unexpected acceptance" >&2; exit 1; fi
printf 'command="id" ' >"$work/options.pub"
cat "$work/operator.pub" >>"$work/options.pub"
if "$here/scripts/prepare-headless-rescue.sh" "$work/options.pub" "$work/options-rejected" >/dev/null 2>&1; then echo "Unexpected acceptance" >&2; exit 1; fi
echo 'PASS: explicit single-key rescue overlay, host identity and invalid-input rejection'
