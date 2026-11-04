#!/bin/sh
# The operator's key window for the aarch64 CHECKOUT feed alone (feed $CHK_TAG), run on madmax (where the key lives):
#
#   ssh jkh@madmax.local 'sh ~/daemonarchy-builder-vm/key-windows/checkout-arm64-window.sh'
#
# For a checkout feed that is rebuilt after the application feed was signed. The application feed is not touched.
# It puts pkg-repo-next.key in a tmpfs on the build VM (memory, swap off), compares the sha256 on both sides, runs
# /root/key-windows/checkout-arm64-run.sh there, and whatever happens removes the key, unmounts the tmpfs and turns swap back
# on. The runner refuses, before the key is used, unless every package declares the expected ABI (FreeBSD:16:aarch64), the
# payload matches its manifest and checkouts.json names the release the feed is published under. Nothing is copied through
# another machine and nothing is printed except hashes and log lines.
#
# Safety rules, each tested with TEST=1 (a generated throwaway key and tiny real packages; no real key moves, no real feed is touched):
#   - the key must belong to the pinned public key, checked on madmax before anything moves;
#   - nothing is written until /var/keytmp-feed is verified to be a tmpfs mount this script made;
#   - swap off (failure tolerated only if none is active afterwards); hashes must match on both sides;
#   - the boot window, the extension window, the other feed window or a held lock refuses this one.
# TEST=1 FAULT=mount|notmpfs|swap|hash|lock|bootwindow|extwindow|wrongkey|vmpub|signed|payload|abi|wildcard|url injects a failure.
set -eu
W=$HOME/daemonarchy-builder-vm/ssh-worker.sh
ENVFILE=${KEYWINDOW_ENV:-$HOME/daemonarchy-builder-vm/key-windows.env}   # release-specific values: see key-windows.env.example
[ ! -f "$ENVFILE" ] || . "$ENVFILE"
MNT=/var/keytmp-feed
BOOT_MNT=/var/keytmp
EXT_MNT=/var/keytmp-ext
LOCK=/var/run/keywindow.lock
NAME=pkg-repo-next.key
PUBLOCAL=$HOME/daemonarchy-builder-vm/pkg-repo-1.3.1.pub     # the pinned public key (public)
PUBSHA=${PIN_PUB_SHA256:-}                       # sha256 of keys/pkg-repo-1.3.1.pub, from key-windows.env
FAULT=${FAULT:-}
ARM_TAG=${CHK_ARM_TAG:?CHK_ARM_TAG (the arm64-ingest.sh destination tag of the checkout feed) is not set}
CHK_TAG=${CHK_TAG:?CHK_TAG (the release tag the checkout feed is published under) is not set}
CHK_ABI=${CHK_ABI:-FreeBSD:16:aarch64}
BASE_URL=${CHK_BASE_URL:-https://github.com/jordanhubbard/daemonarchy/releases/download}
VMROOT=${WORK:?WORK (the release working directory on the VM) is not set: put it in key-windows.env}
PIN_PUB_VM=${PIN_PUB_VM:?PIN_PUB_VM (the pinned public key file on the VM) is not set}
TESTROOT=/tmp/checkout-feedtest

vm() { "$W" "$1"; }
pubhash() { openssl pkey -pubin -in "$1" -pubout 2>/dev/null | sha256sum | cut -d' ' -f1; }
keypubhash() { openssl pkey -in "$1" -pubout 2>/dev/null | sha256sum | cut -d' ' -f1; }

if [ "${TEST:-}" = 1 ]; then
  T=$(mktemp -d)
  src=$T/$NAME
  openssl genrsa -out "$src" 2048 2>/dev/null                 # a throwaway private key named like the key: not the real one
  openssl rsa -in "$src" -pubout -out "$T/test.pub" 2>/dev/null
  openssl genrsa 2048 2>/dev/null | openssl rsa -pubout -out "$T/other.pub" 2>/dev/null
  case "$FAULT" in wrongkey) usepub=$T/other.pub ;; *) usepub=$T/test.pub ;; esac
else
  [ -z "$FAULT" ] || { echo "FAULT is only for TEST=1" >&2; exit 2; }
  src=$HOME/daemonarchy-keys/$NAME
  usepub=$PUBLOCAL
  [ -n "$PUBSHA" ] || { echo "PIN_PUB_SHA256 is not set in $ENVFILE: refusing a real run" >&2; exit 1; }
  [ "$(sha256sum "$PUBLOCAL" | cut -d' ' -f1)" = "$PUBSHA" ] || { echo "$PUBLOCAL is not the pinned public key: refusing" >&2; exit 1; }
fi
[ -f "$src" ] || { echo "no key at $src" >&2; exit 1; }
want=$(sha256sum "$src" | cut -d' ' -f1)
echo "key sha256 on madmax before: $want"
[ "$(keypubhash "$src")" = "$(pubhash "$usepub")" ] || { echo "this key does not belong to the pinned public key: refusing" >&2; [ "${TEST:-}" != 1 ] || rm -rf "$T"; exit 1; }

cleanup() {
  status=$?
  # Idempotent: the runner removes the key on its own exit paths too. Only unmount what is a tmpfs.
  vm "[ -e $MNT/$NAME ] && { rm -P $MNT/$NAME 2>/dev/null; rm -f $MNT/$NAME; }; if mount | grep -q '^tmpfs on $MNT (tmpfs'; then umount $MNT; fi; rmdir $MNT 2>/dev/null; swapon -a 2>/dev/null; true" >/dev/null 2>&1 || true
  [ "${TEST:-}" != 1 ] || vm "rm -rf $TESTROOT; true" >/dev/null 2>&1 || true   # the lock belongs to the runner that took it
  if vm "mount | grep -q ' on $MNT '" 2>/dev/null; then echo "WARNING: $MNT is still mounted on the VM" >&2; ok=0; else ok=1; fi
  if vm "[ -e $MNT/$NAME ]" 2>/dev/null; then echo "WARNING: key file still present on the VM" >&2; ok=0; fi
  [ "$ok" = 1 ] && echo "VM: key file gone, $MNT not mounted, swap $(vm 'swapinfo | sed 1d | wc -l | tr -d " "' 2>/dev/null) device(s) active"
  echo "key sha256 on madmax after:  $(sha256sum "$src" 2>/dev/null | cut -d' ' -f1)"
  [ "${TEST:-}" != 1 ] || rm -rf "$T"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

# The data to sign must already be on the VM (arm64-ingest.sh), and unsigned.
if [ "${TEST:-}" != 1 ]; then
  vm "[ -d $VMROOT/arm64-$ARM_TAG/checkout-feed ] && [ -f $VMROOT/arm64-$ARM_TAG/manifest-checkout.sha256 ] && [ -x /root/key-windows/checkout-arm64-run.sh ]" \
    || { echo "no unsigned checkout feed at $VMROOT/arm64-$ARM_TAG (run arm64-ingest.sh first): refusing" >&2; exit 1; }
fi

# Refuse overlapping windows before anything is placed.
[ "$FAULT" != bootwindow ] || vm "mkdir -p $BOOT_MNT && mount -t tmpfs -o size=1m tmpfs $BOOT_MNT" || true
[ "$FAULT" != extwindow ] || vm "mkdir -p $EXT_MNT && mount -t tmpfs -o size=1m tmpfs $EXT_MNT" || true
for m in $BOOT_MNT $EXT_MNT; do
  if vm "mount | grep -q ' on $m '" 2>/dev/null; then
    if [ "$FAULT" = bootwindow ] || [ "$FAULT" = extwindow ]; then vm "umount $m; rmdir $m" || true; fi
    echo "another key window is open on the VM ($m mounted): refusing" >&2; exit 1
  fi
done
if [ "$FAULT" = lock ]; then vm "mkdir $LOCK" || true; fi
if vm "[ -e $LOCK ]"; then
  [ "$FAULT" != lock ] || vm "rmdir $LOCK" || true
  echo "$LOCK exists on the VM: another key window is open, refusing" >&2; exit 1
fi

# TEST only: tiny real aarch64 packages as a tiny checkout feed, with a checkouts.json and a manifest, and the public key to verify against.
runner_env=
if [ "${TEST:-}" = 1 ]; then
  fix=$VMROOT/arm64-checkout-testpkgs
  vm "set -e; rm -rf $TESTROOT; mkdir -p $TESTROOT/chk; cp $fix/aarch64/*.pkg $TESTROOT/chk/; printf '{\"schema\":1,\"repository_url\":\"$BASE_URL/$CHK_TAG\",\"trees\":{}}\n' > $TESTROOT/chk/checkouts.json"
  case "$FAULT" in
    abi)      vm "cp $fix/amd64/*.pkg $TESTROOT/chk/" ;;
    wildcard) vm "cp $fix/wildcard/*.pkg $TESTROOT/chk/" ;;
    url)      vm "printf '{\"schema\":1,\"repository_url\":\"$BASE_URL/checkouts-16-aarch64-OLD\",\"trees\":{}}\n' > $TESTROOT/chk/checkouts.json" ;;
  esac
  vm "cd $TESTROOT/chk && for f in *; do echo \"\$(sha256 -q \$f) \$f\"; done > ../manifest-chk.sha256"      # the manifest is made after the fixture, as the arm64 worker's is
  [ "$FAULT" != signed ] || vm "touch $TESTROOT/chk/meta"
  [ "$FAULT" != payload ] || vm "echo x >> $TESTROOT/chk/checkouts.json"
  vmpub=$usepub; [ "$FAULT" != vmpub ] || vmpub=$T/other.pub      # vmpub: the VM verifies against a key this one did not sign for
  "$W" "cat > $TESTROOT/test.pub" <"$vmpub"
  runner_env="SIGN_ROOT=$TESTROOT SIGN_CHK=$TESTROOT/chk SIGN_CHKMAN=$TESTROOT/manifest-chk.sha256 SIGN_PUB=$TESTROOT/test.pub SIGN_LOG=$TESTROOT/sign.log SIGN_TAG=$CHK_TAG SIGN_ABI=$CHK_ABI SIGN_BASE_URL=$BASE_URL"
fi

# Memory only: no swap, and a 1 MiB tmpfs that is verified before any byte of the key is written.
vm "swapoff -a 2>/dev/null; true"
if [ "$FAULT" = swap ]; then echo "(fault: pretending swap is still active)" >&2; swapleft=1
else swapleft=$(vm "swapinfo | sed 1d | wc -l | tr -d ' '"); fi
[ "$swapleft" = 0 ] || { echo "swap is still active on the VM: refusing" >&2; exit 1; }
if vm "mount | grep -q ' on $MNT '"; then echo "$MNT is already mounted: refusing" >&2; exit 1; fi
case "$FAULT" in
  mount)   vm "mkdir -p $MNT && mount -t nosuchfs -o size=1m tmpfs $MNT" || echo "(fault: the mount failed)" >&2 ;;
  notmpfs) vm "mkdir -p $MNT" ;;                 # a plain directory on the VM's disk
  *)       vm "mkdir -p $MNT && mount -t tmpfs -o size=1m,mode=700 tmpfs $MNT" ;;
esac
vm "mount | grep -q '^tmpfs on $MNT (tmpfs'" || { echo "$MNT is not a tmpfs mount on the VM: refusing to write the key" >&2; exit 1; }
vm "mount | grep ' on $MNT '"

# The stream: madmax to the VM only. The remote shell reads the key from stdin and never echoes it.
if [ "$FAULT" = hash ]; then head -c 256 /dev/urandom | "$W" "umask 077; cat > $MNT/$NAME; chmod 400 $MNT/$NAME"
else "$W" "umask 077; cat > $MNT/$NAME; chmod 400 $MNT/$NAME" <"$src"; fi
got=$(vm "sha256 -q $MNT/$NAME")
echo "key sha256 on the VM:        $got"
[ "$got" = "$want" ] || { echo "hash mismatch: refusing to sign" >&2; exit 1; }

if [ "${TEST:-}" = 1 ]; then
  out=$(vm "$runner_env sh /root/key-windows/checkout-arm64-run.sh $MNT/$NAME $want" 2>&1) && rc=0 || rc=$?
  echo "$out" | sed 's/^/   runner: /' | cut -c1-200
else
  vm "SIGN_ROOT=$VMROOT/arm64-$ARM_TAG SIGN_PUB=$PIN_PUB_VM SIGN_TAG=$CHK_TAG SIGN_ABI=$CHK_ABI SIGN_BASE_URL=$BASE_URL sh /root/key-windows/checkout-arm64-run.sh $MNT/$NAME $want" && rc=0 || rc=$?
fi
[ "$rc" = 0 ] || { echo "the signing runner failed (exit $rc)" >&2; exit "$rc"; }
