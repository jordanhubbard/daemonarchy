#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/sbin/daemonarchy-checkouts"
revision=bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf
for label in main-n290100-bdcfeac3e1cb main-bdcfeac3e1cb bdcfeac3e1cb n1-bdcfeac3e1cb topic/testing-n1-bdcfeac3e1cb; do
  checkout_kernel_identity_matches "$revision" "FreeBSD 16.0-CURRENT #0 $label: build date"
done
for label in main-n290063-3ceb5f150bc1 bdcfeac3e1cb-dirty main-n1-bdcfeac3e1cb-dirty bdcfeac3e1c; do
  if checkout_kernel_identity_matches "$revision" "FreeBSD 16.0-CURRENT #0 $label: build date"; then
    echo "Accepted mismatched or modified kernel: $label" >&2; exit 1
  fi
done
if checkout_kernel_identity_matches "$revision" 'FreeBSD Foundation'; then exit 1; fi
if checkout_kernel_identity_matches '' 'FreeBSD 16.0-CURRENT #0 : date'; then exit 1; fi
echo 'PASS: full, shallow and detached kernel identities; wrong revisions and dirty trees rejected'
