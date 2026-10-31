#!/bin/sh
# The operator's key window for the aarch64 feeds (release $RELEASE), run on madmax (where the key lives):
#
#   ssh jkh@madmax.local 'sh ~/daemonarchy-builder-vm/key-windows/feeds-arm64-window.sh'
#
# It puts pkg-repo-next.key in a tmpfs on the build VM (memory, swap off), compares the sha256 on both
# sides, runs /root/key-windows/feeds-arm64-run.sh there (which signs packages-16-aarch64-$RELEASE and
# checkouts-16-aarch64-$RELEASE and verifies each against the pinned public key), and whatever happens
# removes the key, unmounts the tmpfs and turns swap back on. Nothing is copied through another machine
# and nothing is printed except hashes and log lines.
#
# Safety rules, each tested with TEST=1 (a generated throwaway key and two tiny real aarch64 packages; no
# real key moves and no real feed is touched):
#   - the key must belong to the pinned public key (compared on madmax before anything moves);
#   - nothing is written until /var/keytmp-feed is verified to be a tmpfs mount this script made;
#   - swapoff -a may fail when swap is already off, but active swap afterwards refuses the window;
#   - the hash must match on both sides; another key window (the boot window, or a held lock) refuses this one.
# ARM_TAG selects the ingested data (arm64-ingest.sh TAG). TEST=1 FAULT=mount|notmpfs|swap|hash|lock|bootwindow|wrongkey|vmpub|signed|payload injects a failure to prove the refusal.
set -eu
W=$HOME/daemonarchy-builder-vm/ssh-worker.sh
ENVFILE=${KEYWINDOW_ENV:-$HOME/daemonarchy-builder-vm/key-windows.env}   # release-specific values: see key-windows.env.example
[ ! -f "$ENVFILE" ] || . "$ENVFILE"
MNT=/var/keytmp-feed
BOOT_MNT=/var/keytmp
LOCK=/var/run/keywindow.lock
NAME=pkg-repo-next.key
PUBLOCAL=$HOME/daemonarchy-builder-vm/pkg-repo-1.3.1.pub     # the pinned public key (public)
PUBSHA=${PIN_PUB_SHA256:-}                       # sha256 of keys/pkg-repo-1.3.1.pub, from key-windows.env
FAULT=${FAULT:-}
RELEASE=${RELEASE:?RELEASE (X.Y.Z) is not set: put it in key-windows.env}
ARM_TAG=${ARM_TAG:?ARM_TAG (the arm64-ingest.sh destination tag) is not set}
VMROOT=${WORK:?WORK (the release working directory on the VM) is not set: put it in key-windows.env}
PIN_PUB_VM=${PIN_PUB_VM:?PIN_PUB_VM (the pinned public key file on the VM) is not set}
TESTROOT=/tmp/arm64-feedtest

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
  vm "[ -d $VMROOT/arm64-$ARM_TAG/app-feed ] && [ -d $VMROOT/arm64-$ARM_TAG/checkout-feed ] && [ -f $VMROOT/arm64-$ARM_TAG/manifest-app.sha256 ] && [ -f $VMROOT/arm64-$ARM_TAG/manifest-checkout.sha256 ]" \
    || { echo "no unsigned feeds at $VMROOT/arm64-$ARM_TAG (run arm64-ingest.sh first): refusing" >&2; exit 1; }
fi

# Refuse overlapping windows before anything is placed.
if [ "$FAULT" = bootwindow ]; then vm "mkdir -p $BOOT_MNT && mount -t tmpfs -o size=1m tmpfs $BOOT_MNT" || true; fi
if vm "mount | grep -q ' on $BOOT_MNT '" 2>/dev/null; then
  [ "$FAULT" != bootwindow ] || vm "umount $BOOT_MNT; rmdir $BOOT_MNT" || true
  echo "the boot key window is open on the VM ($BOOT_MNT mounted): refusing" >&2; exit 1
fi
if [ "$FAULT" = lock ]; then vm "mkdir $LOCK" || true; fi
if vm "[ -e $LOCK ]"; then
  [ "$FAULT" != lock ] || vm "rmdir $LOCK" || true
  echo "$LOCK exists on the VM: another key window is open, refusing" >&2; exit 1
fi

# TEST only: two tiny real aarch64 packages as two tiny feeds, with manifests, and the public key to verify against.
if [ "${TEST:-}" = 1 ]; then
  vm "set -e; rm -rf $TESTROOT; mkdir -p $TESTROOT/app $TESTROOT/chk; cd $VMROOT/arm64-testpkgs; set -- \$(ls -S *.pkg | tail -4); cp \$1 \$2 $TESTROOT/app/; cp \$3 \$4 $TESTROOT/chk/; for d in app chk; do (cd $TESTROOT/\$d && for f in *.pkg; do echo \"\$(sha256 -q \$f) \$f\"; done > ../manifest-\$d.sha256); done; ls -l $TESTROOT/app $TESTROOT/chk | awk 'NR>1 && \$5 {print \"   test feed file\", \$5, \$9}'"
  [ "$FAULT" != signed ] || vm "touch $TESTROOT/app/meta"
  [ "$FAULT" != payload ] || vm "echo x >> $TESTROOT/app/\$(ls $TESTROOT/app | head -1)"
  vmpub=$usepub; [ "$FAULT" != vmpub ] || vmpub=$T/other.pub      # vmpub: the VM verifies against a key this one did not sign for
  "$W" "cat > $TESTROOT/test.pub" <"$vmpub"
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
  out=$(vm "SIGN_ROOT=$TESTROOT SIGN_APP=$TESTROOT/app SIGN_CHK=$TESTROOT/chk SIGN_APPMAN=$TESTROOT/manifest-app.sha256 SIGN_CHKMAN=$TESTROOT/manifest-chk.sha256 SIGN_PUB=$TESTROOT/test.pub SIGN_LOG=$TESTROOT/sign.log SIGN_RELEASE=$RELEASE sh /root/key-windows/feeds-arm64-run.sh $MNT/$NAME $want" 2>&1) && rc=0 || rc=$?
  echo "$out" | sed 's/^/   runner: /' | cut -c1-190
else
  vm "SIGN_ROOT=$VMROOT/arm64-$ARM_TAG SIGN_PUB=$PIN_PUB_VM SIGN_RELEASE=$RELEASE sh /root/key-windows/feeds-arm64-run.sh $MNT/$NAME $want" && rc=0 || rc=$?
fi
[ "$rc" = 0 ] || { echo "the signing runner failed (exit $rc)" >&2; exit "$rc"; }
