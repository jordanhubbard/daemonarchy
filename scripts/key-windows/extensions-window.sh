#!/bin/sh
# The operator's key window for the extension feeds (release $RELEASE), run on madmax (where the key lives):
#
#   ssh jkh@madmax.local 'sh ~/daemonarchy-builder-vm/key-windows/extensions-window.sh'
#
# It puts pkg-repo-next.key in a tmpfs on the build VM (memory, swap off), compares the sha256 on both sides, runs
# /root/key-windows/extensions-run.sh there (which checks that the key belongs to the pinned public key, signs extensions-16-amd64-$RELEASE
# and extensions-16-aarch64-$RELEASE with scripts/extension-bundle.py, and verifies both with the pinned public key), and
# whatever happens removes the key, unmounts the tmpfs and turns swap back on. Nothing is copied through another machine
# and nothing is printed except hashes and log lines.
#
# Safety rules, each tested with TEST=1 (a generated throwaway key; the real staged feeds are copied to a scratch
# directory and signed there; no real key moves, no real feed is touched):
#   - the key must belong to the pinned public key (DER sha256 of its public half), checked on madmax before anything moves
#     and again on the VM tmpfs copy by the runner;
#   - nothing is written until /var/keytmp-ext is verified to be a tmpfs mount this script made;
#   - swapoff -a may fail when swap is already off, but active swap afterwards refuses the window;
#   - the hash must match on both sides; another key window (boot or arm64 feed window open, or a held lock) refuses this one.
# TEST=1 FAULT=mount|notmpfs|swap|hash|lock|bootwindow|feedwindow|wrongkey|derbad|vmpin|tampered|signed injects a failure to prove the refusal.
set -eu
W=$HOME/daemonarchy-builder-vm/ssh-worker.sh
ENVFILE=${KEYWINDOW_ENV:-$HOME/daemonarchy-builder-vm/key-windows.env}   # release-specific values: see key-windows.env.example
[ ! -f "$ENVFILE" ] || . "$ENVFILE"
MNT=/var/keytmp-ext
BOOT_MNT=/var/keytmp
FEED_MNT=/var/keytmp-feed
LOCK=/var/run/keywindow.lock
NAME=pkg-repo-next.key
PUBLOCAL=$HOME/daemonarchy-builder-vm/pkg-repo-1.3.1.pub     # the pinned public key (public)
PUBDER=${PIN_PUB_DER_SHA256:-}                  # DER sha256 of the public half of the pinned key, from key-windows.env
FAULT=${FAULT:-}
RELEASE=${RELEASE:?RELEASE (X.Y.Z) is not set: put it in key-windows.env}
VMROOT=${WORK:?WORK (the release working directory on the VM) is not set: put it in key-windows.env}
EXT_DIR=${EXT_DIR:?EXT_DIR (the staged extension feeds under WORK) is not set}
EXT_TOOL=${EXT_TOOL:-$VMROOT/ext-tool}
EXT_REUSE=${EXT_REUSE:-reusable-signatures}     # directory under EXT_DIR holding earlier signatures of unchanged bundles
PIN_PUB_VM=${PIN_PUB_VM:?PIN_PUB_VM (the pinned public key file on the VM) is not set}
TESTROOT=/tmp/ext-feedtest

vm() { "$W" "$1"; }
pubder() { openssl pkey -pubin -in "$1" -pubout -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1; }
keyder() { openssl pkey -in "$1" -pubout -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1; }

if [ "${TEST:-}" = 1 ]; then
  T=$(mktemp -d)
  src=$T/$NAME
  openssl genrsa -out "$src" 4096 2>/dev/null                 # a throwaway private key named like the key: not the real one
  openssl rsa -in "$src" -pubout -out "$T/test.pub" 2>/dev/null
  openssl genrsa 2048 2>/dev/null | openssl rsa -pubout -out "$T/other.pub" 2>/dev/null
  case "$FAULT" in wrongkey) usepub=$T/other.pub ;; *) usepub=$T/test.pub ;; esac
  usepubder=$(pubder "$usepub")
else
  [ -z "$FAULT" ] || { echo "FAULT is only for TEST=1" >&2; exit 2; }
  src=$HOME/daemonarchy-keys/$NAME
  usepub=$PUBLOCAL
  usepubder=$PUBDER
  [ -n "$PUBDER" ] || { echo "PIN_PUB_DER_SHA256 is not set in $ENVFILE: refusing a real run" >&2; exit 1; }
  [ "$(pubder "$PUBLOCAL")" = "$PUBDER" ] || { echo "$PUBLOCAL is not the pinned public key: refusing" >&2; exit 1; }
fi
[ -f "$src" ] || { echo "no key at $src" >&2; exit 1; }
want=$(sha256sum "$src" | cut -d' ' -f1)
echo "key sha256 on madmax before: $want"
[ "$(keyder "$src")" = "$usepubder" ] || { echo "this key does not belong to the pinned public key: refusing" >&2; [ "${TEST:-}" != 1 ] || rm -rf "$T"; exit 1; }

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

# The data to sign must already be on the VM (staged, unsigned).
if [ "${TEST:-}" != 1 ]; then
  vm "[ -d $VMROOT/$EXT_DIR/extensions-16-amd64-$RELEASE ] && [ -d $VMROOT/$EXT_DIR/extensions-16-aarch64-$RELEASE ] && [ -f $VMROOT/$EXT_DIR/SHA256SUMS ] && [ -d $EXT_TOOL/scripts ]" \
    || { echo "no staged extension feeds for $RELEASE at $VMROOT/$EXT_DIR: refusing" >&2; exit 1; }
fi

# Refuse overlapping windows before anything is placed.
if [ "$FAULT" = bootwindow ]; then vm "mkdir -p $BOOT_MNT && mount -t tmpfs -o size=1m tmpfs $BOOT_MNT" || true; fi
if [ "$FAULT" = feedwindow ]; then vm "mkdir -p $FEED_MNT && mount -t tmpfs -o size=1m tmpfs $FEED_MNT" || true; fi
for pair in "$BOOT_MNT:boot" "$FEED_MNT:arm64 feed"; do
  m=${pair%%:*}; label=${pair#*:}
  if vm "mount | grep -q ' on $m '" 2>/dev/null; then
    if [ "$FAULT" = bootwindow ] || [ "$FAULT" = feedwindow ]; then vm "umount $m; rmdir $m" || true; fi
    echo "the $label key window is open on the VM ($m mounted): refusing" >&2; exit 1
  fi
done
if [ "$FAULT" = lock ]; then vm "mkdir $LOCK" || true; fi
if vm "[ -e $LOCK ]"; then
  [ "$FAULT" != lock ] || vm "rmdir $LOCK" || true
  echo "$LOCK exists on the VM: another key window is open, refusing" >&2; exit 1
fi

# TEST only: copy the staged feeds (without any signatures, so the rehearsal also works after the real window) to a scratch directory, and give the VM the throwaway public key to verify against.
runner_env=
if [ "${TEST:-}" = 1 ]; then
  vm "set -e; rm -rf $TESTROOT; mkdir -p $TESTROOT; cd $VMROOT/$EXT_DIR; cp -R extensions-16-amd64-$RELEASE extensions-16-aarch64-$RELEASE SHA256SUMS $TESTROOT/; [ ! -d $EXT_REUSE ] || cp -R $EXT_REUSE $TESTROOT/; rm -f $TESTROOT/extensions-16-*-$RELEASE/*.sig; echo '   test feeds copied:' \$(find $TESTROOT -type f | wc -l) files"
  [ "$FAULT" != tampered ] || vm "echo x >> $TESTROOT/extensions-16-amd64-$RELEASE/ext-wyrm-1.0.0.tar.xz"
  [ "$FAULT" != signed ] || vm "touch $TESTROOT/extensions-16-amd64-$RELEASE/extensions-index.json.xz.sig"
  vmpub=$usepub; expder=$usepubder
  [ "$FAULT" != vmpin ] || { vmpub=$T/other.pub; expder=$(pubder "$T/other.pub"); }       # the VM pins a key this one does not belong to
  [ "$FAULT" != derbad ] || expder=$(printf '%064d' 0)
  "$W" "cat > $TESTROOT/test.pub" <"$vmpub"
  runner_env="SIGN_ROOT=$TESTROOT SIGN_TOOL=$EXT_TOOL SIGN_REUSE=$TESTROOT/$EXT_REUSE SIGN_PUB=$TESTROOT/test.pub SIGN_PUBDER=$expder SIGN_LOG=$TESTROOT/sign.log"
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
  out=$(vm "SIGN_RELEASE=$RELEASE $runner_env sh /root/key-windows/extensions-run.sh $MNT/$NAME $want" 2>&1) && rc=0 || rc=$?
  echo "$out" | sed 's/^/   runner: /' | cut -c1-200
else
  vm "SIGN_ROOT=$VMROOT/$EXT_DIR SIGN_TOOL=$EXT_TOOL SIGN_REUSE=$VMROOT/$EXT_DIR/$EXT_REUSE SIGN_PUB=$PIN_PUB_VM SIGN_PUBDER=$PUBDER SIGN_RELEASE=$RELEASE sh /root/key-windows/extensions-run.sh $MNT/$NAME $want" && rc=0 || rc=$?
fi
[ "$rc" = 0 ] || { echo "the signing runner failed (exit $rc)" >&2; exit "$rc"; }
