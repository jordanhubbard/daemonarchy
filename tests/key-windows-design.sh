#!/usr/bin/env bash
# The key-window scripts keep their safety design, and carry no release-specific value. The live mechanics test (TEST=1 with
# throwaway keys, on the key host and the build VM) is described in docs/mastering-1.5.0.md; this is the part that needs neither.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
dir=$here/scripts/key-windows
fail() { echo "FAIL: $*" >&2; exit 1; }
has() { grep -qE -- "$2" "$1" || fail "$(basename "$1") lacks: $3"; }
hasnt() { ! grep -nE -- "$2" "$1" >&2 || fail "$(basename "$1"): $3"; }

windows=(boot-relabel-window boot-full-window feeds-arm64-window checkout-arm64-window extensions-window)
runners=(boot-relabel-run boot-full-run feeds-arm64-run checkout-arm64-run extensions-run)
for f in "${windows[@]}" "${runners[@]}" arm64-ingest arm64-ingest-checkout; do bash -n "$dir/$f.sh" || fail "$f.sh does not parse"; done

for w in "${windows[@]}"; do
  f=$dir/$w.sh
  has "$f" '^set -eu' 'set -eu'
  has "$f" 'FAULT is only for TEST=1' 'real mode must refuse FAULT'
  has "$f" 'trap cleanup EXIT' 'a cleanup trap'
  has "$f" "mount \| grep -q '\^tmpfs on" 'a check that the mount is a tmpfs before the key is written'
  has "$f" 'swapoff -a' 'swap turned off'
  has "$f" 'swapon -a' 'swap restored in the trap'
  has "$f" 'hash mismatch: refusing' 'a hash comparison on both sides'
  has "$f" 'key sha256 on madmax after' 'the hash after'
  has "$f" 'KEYWINDOW_ENV' 'release values from the env file'
  has "$f" 'RELEASE:\?|CHK_TAG:\?' 'a required release or feed tag'
  has "$f" 'WORK:\?' 'a required WORK'
  has "$f" 'key window is open|another key window' 'a refusal when another window is open'
  has "$f" 'keywindow.lock' 'the shared lock'
  # the key is only hashed, checked with openssl and streamed; it is never printed or copied around
  hasnt "$f" '(^|[^A-Za-z_])(cat|base64|tee|xxd|od)([^A-Za-z_][^|<]*)?\$\{?src\b|\$\( *< *"?\$\{?src' 'the key file is read into something (only its hash, its path and a stream to the VM are allowed)'
  hasnt "$f" '[0-9a-f]{64}' 'a hard-coded 64-hex value (release values belong in key-windows.env)'
  # TEST=1 injects every failure the header lists, and the same code is used in real mode
  for fault in $(grep -E '^# TEST=1 FAULT=' "$f" | sed -E 's/^# TEST=1 FAULT=([^ ]*).*/\1/' | tr '|' ' ' | tr -d '.'); do
    grep -qE "FAULT\"? (=|!=) $fault([^A-Za-z]|$)|[ (]$fault\)" "$f" || fail "$w.sh lists FAULT=$fault but never handles it"
  done
done

for r in "${runners[@]}"; do
  f=$dir/$r.sh
  has "$f" '^set -eu' 'set -eu'
  has "$f" 'trap cleanup EXIT' 'a cleanup trap'
  has "$f" 'rm -f "\$KEY"' 'the key removed'
  has "$f" '\^tmpfs on' 'a tmpfs check'
  has "$f" 'swapinfo' 'a swap check'
  has "$f" 'stat -f %Lp "\$KEY"' 'a key mode check'
  hasnt "$f" '(^|[^A-Za-z_])(cat|base64|tee)([^A-Za-z_][^|]*)?"?\$KEY"?([^A-Za-z_/]|$)|< *"?\$KEY' 'the key is read or copied'
  hasnt "$f" '[0-9a-f]{64}' 'a hard-coded 64-hex value'
  hasnt "$f" 'rev2-[0-9]{8}' 'a hard-coded release directory'
  hasnt "$f" ':-1\.[0-9]+\.[0-9]+\}' 'a hard-coded release default'
done
for r in boot-relabel-run boot-full-run extensions-run feeds-arm64-run checkout-arm64-run; do has "$dir/$r.sh" 'keywindow\.lock' 'the key-window lock'; done

# Every variable a script requires is documented in the example env file, and the example holds no key material.
env=$dir/key-windows.env.example
for var in $(grep -ohE '\$\{[A-Z_0-9]+:\?' "$dir"/*-window.sh | sed -E 's/\$\{(.*):\?/\1/' | sort -u); do
  grep -qE "^$var=" "$env" || fail "$var is required by a window but missing from key-windows.env.example"
done
! grep -qE 'BEGIN|PRIVATE' "$env" || fail "the example env file holds key material"

# The boot full re-sign refuses anything but the expected change, and keeps the previous bundle.
has "$dir/boot-full-run.sh" 'FREEZE:' 'the freeze check on tools and inputs'
has "$dir/boot-full-run.sh" 'differ from the previous signed tree' 'the prepared-tree gate'
has "$dir/boot-full-run.sh" '\.previous' 'the previous bundle kept'
has "$dir/boot-full-run.sh" 'PRIVATE MATERIAL IN PUBLIC BUNDLE' 'the leak check'
# The checkout-only signing refuses a mislabelled feed before the key is used.
has "$dir/checkout-arm64-run.sh" "tar -xOf .*\+COMPACT_MANIFEST" 'a read of each package'"'"'s own ABI label before signing'
has "$dir/checkout-arm64-run.sh" 'do not declare' 'a refusal when a package declares another ABI'
has "$dir/checkout-arm64-run.sh" 'repository_url' 'a check that checkouts.json names the release'
has "$dir/checkout-arm64-run.sh" 'control: the same catalogue is refused' 'an ABI control that proves the check can fail'
echo 'key-windows design checks passed'
