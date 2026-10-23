#!/usr/bin/env bash
# Native FreeBSD pkg round trip, shallow Git use, and preservation checks.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $(id -u) == 0 ]] || { echo 'Run as root on FreeBSD' >&2; exit 1; }
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /var/tmp/daemonarchy-checkout-test.XXXXXX)
trap 'rm -rf "$work"' EXIT
source "$here/overlay/usr/local/sbin/daemonarchy-checkouts"
source "$here/overlay/usr/local/libexec/daemonarchy-installer/checkout-options"
git init -q -b preflight/macbook-test "$work/repo"
git -C "$work/repo" config user.name Test
git -C "$work/repo" config user.email test@example.invalid
for value in one two three; do
  echo "$value" >"$work/repo/file"
  git -C "$work/repo" add file
  git -C "$work/repo" commit -qm "$value"
done
# Force multiple package chunks to test ordered assembly.
dd if=/dev/urandom of="$work/repo/payload" bs=1m count=2 status=none
git -C "$work/repo" add payload
git -C "$work/repo" commit -qm payload
python3 "$here/scripts/build-checkout-packages.py" --kind ports --repo "$work/repo" --revision HEAD --branch preflight/macbook-test --remote https://github.com/jordanhubbard/freebsd-ports.git --out "$work/packages" --chunk-mib 1 >"$work/build.log"
jq '{schema:1,trees:{ports:.}}' "$work/packages/ports.json" >"$work/catalog.json"
mkdir -p "$work/root"
pkg -r "$work/root" -o ABI=FreeBSD:16:amd64 add "$work/packages"/*.pkg
jq '.trees.ports.branch = "bad..branch"' "$work/catalog.json" >"$work/invalid-branch.json"
if (checkout_materialize ports root "$work/invalid-branch.json" "$work/invalid" "$work/root"); then
  echo 'Accepted invalid checkout branch' >&2; exit 1
fi
[[ ! -e $work/invalid ]]
checkout_materialize ports root "$work/catalog.json" "$work/checkout" "$work/root"
[[ $(git -C "$work/checkout" rev-list --count HEAD) == 1 ]]
[[ $(git -C "$work/checkout" status --porcelain) == '' ]]
[[ $(git -C "$work/checkout" remote get-url origin) == https://github.com/jordanhubbard/freebsd-ports.git ]]
[[ $(git -C "$work/checkout" remote get-url upstream) == https://github.com/freebsd/freebsd-ports.git ]]
git -C "$work/checkout" remote set-url origin "$work/repo"
[[ $(git -C "$work/checkout" symbolic-ref --short HEAD) == preflight/macbook-test ]]
git -C "$work/checkout" fetch --deepen=1 origin
[[ $(git -C "$work/checkout" rev-list --count HEAD) == 2 ]]
echo edited >>"$work/checkout/file"
if (checkout_materialize ports root "$work/catalog.json" "$work/checkout" "$work/root"); then echo 'Overwrote local edits' >&2; exit 1; fi
grep -q edited "$work/checkout/file"
git -C "$work/checkout" -c user.name=Test -c user.email=test@example.invalid commit -qam local-edit
pkg -r "$work/root" delete -ay
[[ $(git -C "$work/checkout" log -1 --format=%s) == local-edit ]]
# Reinstall payloads, then tamper with one. Failure precedes extraction.
pkg -r "$work/root" -o ABI=FreeBSD:16:amd64 add "$work/packages"/*.pkg
part=$(jq -r '.trees.ports.parts[0].file' "$work/catalog.json")
printf bad >>"$work/root$part"
if (checkout_materialize ports root "$work/catalog.json" "$work/corrupt" "$work/root"); then echo 'Accepted corrupt payload' >&2; exit 1; fi
[[ -z $(ls -A "$work/corrupt") ]]
install_ports=false install_src=false
checkout_options_prepare "$work/catalog.json"
[[ $MIN_INSTALL_BYTES == 21474836480 ]]
install_ports=true
checkout_options_prepare "$work/catalog.json"
((MIN_INSTALL_BYTES > 21474836480))
install_src=invalid
if checkout_options_prepare "$work/catalog.json"; then echo 'Accepted invalid option' >&2; exit 1; fi
echo 'PASS: native pkg round trip, shallow clone, deepen, commit, uninstall preservation, checksum rejection and option sizing'
