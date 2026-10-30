#!/usr/bin/env bash
# Completion must follow package verification and durable target-pool writes.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/install-integrity"
work=$(mktemp -d "${TMPDIR:-/tmp}/daemonarchy-integrity.XXXXXX")
trap 'rm -rf "$work"' EXIT
mode=good
pool_failure=no
fake_pkg() {
  case "$*" in
    'check -d -n -a') [[ $mode != dependencies ]] ;;
    'check -s -a')
      case $mode in
        corrupt) echo 'fixture: checksum mismatch for /fixture' ;;
        missing) echo 'fixture: /fixture not found' ;;
        error) return 74 ;;
      esac ;;
    *) echo "Unexpected pkg command: $*" >&2; return 99 ;;
  esac
}
zpool() {
  printf 'pool:%s\n' "$*" >>"$work/order"
  [[ $pool_failure != yes ]]
}
diagnostics_result() {
  printf 'result:%s\n' "$*" >>"$work/order"
  touch "$work/complete"
}
for mode in dependencies corrupt missing error; do
  : >"$work/order"
  if install_record_verified_completion fixture "$work/check" fake_pkg; then
    echo "Incorrectly accepted $mode" >&2; exit 1
  fi
  [[ ! -e $work/complete && ! -s $work/order ]]
done
mode=good
pool_failure=yes
if install_record_verified_completion fixture "$work/check" fake_pkg; then
  echo 'Accepted failed pool flush' >&2; exit 1
fi
[[ ! -e $work/complete ]]
pool_failure=no
: >"$work/order"
install_record_verified_completion fixture "$work/check" fake_pkg
printf 'pool:sync fixture\nresult:complete 0\npool:sync fixture\n' >"$work/expected"
cmp "$work/expected" "$work/order"

# The optional CUDA additions replace package-owned files (the vendor menu, and
# files linux-rl9 packages own through Rocky's dnf). Package verification must
# run before them, and completion must not re-verify afterwards.
install=$here/overlay/usr/local/libexec/daemonarchy-installer/install
line() { grep -n -m1 -- "$1" "$install" | cut -d: -f1; }
verify=$(line '^traced package_integrity ')
support=$(line '^cuda_install_support ')
cuda=$(line '^  phase cuda ')
record=$(line '^traced pool_sync_commit ')
[[ -n $verify && -n $support && -n $cuda && -n $record ]]
(( verify < support && support < cuda && cuda < record ))
[[ $(grep -c '^cuda_install_support ' "$install") == 1 ]]
! grep -q 'install_record_verified_completion' "$install"
: >"$work/order"
rm -f "$work/complete"
mode=corrupt
install_record_completion fixture
printf 'pool:sync fixture\nresult:complete 0\npool:sync fixture\n' >"$work/expected"
cmp "$work/expected" "$work/order"
mode=good

# A package the repositories no longer provide must fail before the download
# loop, not after five retries blamed on the network.
resolve=$(line '^if ! traced pkg_resolve ')
fetch=$(line '^for attempt in 1 2 3 4 5')
[[ -n $resolve && -n $fetch ]] && (( resolve < fetch ))

if [[ $(uname -s) == FreeBSD && $(id -u) == 0 ]]; then
  mkdir -p "$work/stage/usr/local/share/daemonarchy-integrity-fixture" "$work/packages" "$work/root"
  printf 'verified package payload\n' >"$work/stage/usr/local/share/daemonarchy-integrity-fixture/payload"
  cat >"$work/manifest" <<'EOF'
name: daemonarchy-integrity-fixture
version: "1"
origin: misc/daemonarchy-integrity-fixture
comment: Disposable installer integrity fixture
desc: Disposable installer integrity fixture
maintainer: test@example.invalid
www: https://example.invalid
prefix: /
files: {"/usr/local/share/daemonarchy-integrity-fixture/payload": "1"}
EOF
  /usr/local/sbin/pkg create -M "$work/manifest" -r "$work/stage" -o "$work/packages"
  /usr/local/sbin/pkg -r "$work/root" add -I "$work/packages/daemonarchy-integrity-fixture-1.pkg"
  real_pkg() { /usr/local/sbin/pkg -r "$work/root" "$@"; }
  install_verify_package_integrity "$work/real-check" real_pkg
  : >"$work/root/usr/local/share/daemonarchy-integrity-fixture/payload"
  rm "$work/complete"
  : >"$work/order"
  if install_record_verified_completion fixture "$work/real-check" real_pkg; then
    echo 'Accepted truncated actual package payload' >&2; exit 1
  fi
  [[ ! -e $work/complete && ! -s $work/order ]]
  grep -q 'checksum mismatch' "$work/real-check"
fi
echo 'Installer integrity checks passed'
