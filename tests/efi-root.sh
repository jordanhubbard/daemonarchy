#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
fixture_bootfs=''
fixture_guid=17326164631689436972
zpool() {
  case "$*" in
    'get -H -o value bootfs daemonarchy-test') printf '%s\n' "$fixture_bootfs" ;;
    'get -H -o value guid daemonarchy-test') printf '%s\n' "$fixture_guid" ;;
    *) return 1 ;;
  esac
}
for fixture_bootfs in daemonarchy-test/ROOT/default daemonarchy-test/ROOT/upgrade; do
  [[ $(efi_root_environment daemonarchy-test) == "rootdev=zfs:$fixture_bootfs:" ]]
done
for fixture_bootfs in - daemonarchy-test other/ROOT/default 'daemonarchy-test/ROOT/bad name'; do
  if efi_root_environment daemonarchy-test; then
    echo "FAIL: accepted invalid bootfs $fixture_bootfs" >&2
    exit 1
  fi
done
[[ $(efi_root_environment daemonarchy-test true) == "daemonarchy_rootpool=$fixture_guid" ]]
for fixture_guid in - 0 bad '1 rootdev=other'; do
  if efi_root_environment daemonarchy-test true; then
    echo "FAIL: accepted invalid pool GUID $fixture_guid" >&2
    exit 1
  fi
done
echo 'PASS: EFI root selects the installed boot environment and rejects invalid bootfs'
