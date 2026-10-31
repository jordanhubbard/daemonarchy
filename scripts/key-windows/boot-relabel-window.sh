#!/bin/sh
# The operator's key window for the boot-bundle signature of a release (RELEASE), run on madmax
# (where the key lives):
#
#   ssh jkh@madmax.local 'sh ~/daemonarchy-builder-vm/key-windows/boot-relabel-window.sh'
#
# It puts boot-replacement-candidate-20261024.key in a tmpfs on the build VM (memory, swap off), compares
# the sha256 on both sides, runs /root/key-windows/boot-relabel-run.sh RELEASE there under the key-window lock (it re-creates
# the signed boot bundle with that release label from the already signed boot tree: one signature), and whatever happens removes the key, unmounts the tmpfs and turns swap back on.
# Nothing is copied through another machine and nothing is printed except hashes and log lines.
#
# Safety rules, each tested with TEST=1 (a random 256-byte file named like the key; no key moves, nothing is signed):
#   - nothing is written until /var/keytmp is verified to be a tmpfs mount that this script made;
#   - swapoff -a may fail when swap is already off, but active swap afterwards refuses the window;
#   - the key's hash must equal the expected one (EXPECT, default the real key's) and match on the VM;
#   - another key window (the feed window, or a held lock) refuses this one.
# TEST=1 FAULT=mount|notmpfs|swap|hash|lock|feedwindow injects the named failure to prove the refusal.
set -eu
W=$HOME/daemonarchy-builder-vm/ssh-worker.sh
ENVFILE=${KEYWINDOW_ENV:-$HOME/daemonarchy-builder-vm/key-windows.env}   # release-specific values: see key-windows.env.example
[ ! -f "$ENVFILE" ] || . "$ENVFILE"
MNT=/var/keytmp
FEED_MNT=/var/keytmp-feed
LOCK=/var/run/keywindow.lock
NAME=boot-replacement-candidate-20261024.key     # the file's name on madmax
VMNAME=boot.key                                  # what /root/key-windows/boot-relabel-run.sh expects on the VM
REAL_EXPECT=${BOOT_KEY_SHA256:-}                 # sha256 of the boot signing key file, from key-windows.env
FAULT=${FAULT:-}
RELEASE=${RELEASE:?RELEASE (X.Y.Z) is not set: put it in key-windows.env}
WORK=${WORK:?WORK (the release working directory on the VM) is not set: put it in key-windows.env}
BLOG=$WORK/evidence/sign-bundle-$RELEASE.log

vm() { "$W" "$1"; }

if [ "${TEST:-}" = 1 ]; then
  src=$(mktemp -d)/$NAME
  head -c 256 /dev/urandom > "$src"              # random bytes named like the key: tests the mechanics, is not a key
  EXPECT=$(sha256sum "$src" | cut -d' ' -f1)
else
  [ -z "$FAULT" ] || { echo "FAULT is only for TEST=1" >&2; exit 2; }
  src=$HOME/daemonarchy-keys/$NAME
  EXPECT=${EXPECT:-$REAL_EXPECT}
  [ -n "$EXPECT" ] || { echo "BOOT_KEY_SHA256 is not set in $ENVFILE: refusing a real run without the expected key hash" >&2; exit 1; }
fi
[ -f "$src" ] || { echo "no key at $src" >&2; exit 1; }
want=$(sha256sum "$src" | cut -d' ' -f1)
echo "key sha256 on madmax before: $want"
[ "$want" = "$EXPECT" ] || { echo "the key on madmax is not the expected one ($EXPECT): refusing" >&2; exit 1; }

cleanup() {
  status=$?
  # Idempotent: the runner removes the key on its own exit paths too. Only unmount what is a tmpfs.
  vm "[ -e $MNT/$VMNAME ] && { rm -P $MNT/$VMNAME 2>/dev/null; rm -f $MNT/$VMNAME; }; if mount | grep -q '^tmpfs on $MNT (tmpfs'; then umount $MNT; fi; rmdir $MNT 2>/dev/null; swapon -a 2>/dev/null; true" >/dev/null 2>&1 || true
  if vm "mount | grep -q ' on $MNT '" 2>/dev/null; then echo "WARNING: $MNT is still mounted on the VM" >&2; ok=0; else ok=1; fi
  if vm "[ -e $MNT/$VMNAME ]" 2>/dev/null; then echo "WARNING: key file still present on the VM" >&2; ok=0; fi
  [ "$ok" = 1 ] && echo "VM: key file gone, $MNT not mounted, swap $(vm 'swapinfo | sed 1d | wc -l | tr -d " "' 2>/dev/null) device(s) active"
  echo "key sha256 on madmax after:  $(sha256sum "$src" 2>/dev/null | cut -d' ' -f1)"
  [ "${TEST:-}" != 1 ] || rm -rf "$(dirname "$src")"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

# Refuse overlapping windows before anything is placed.
if [ "$FAULT" = feedwindow ]; then vm "mkdir -p $FEED_MNT && mount -t tmpfs -o size=1m tmpfs $FEED_MNT" || true; fi
if vm "mount | grep -q ' on $FEED_MNT '" 2>/dev/null; then
  [ "$FAULT" != feedwindow ] || vm "umount $FEED_MNT; rmdir $FEED_MNT" || true
  echo "the feed key window is open on the VM ($FEED_MNT mounted): refusing" >&2; exit 1
fi
if [ "$FAULT" = lock ]; then
  # Hold the lock in the background on the VM for the duration of the test.
  vm "nohup lockf -k $LOCK sleep 60 >/dev/null 2>&1 </dev/null &" || true
  sleep 2
fi
vm "lockf -t 0 $LOCK true" || { echo "$LOCK is held on the VM: refusing" >&2; exit 1; }

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
if [ "$FAULT" = hash ]; then head -c 256 /dev/urandom | "$W" "umask 077; cat > $MNT/$VMNAME; chmod 400 $MNT/$VMNAME"
else "$W" "umask 077; cat > $MNT/$VMNAME; chmod 400 $MNT/$VMNAME" <"$src"; fi
got=$(vm "sha256 -q $MNT/$VMNAME")
echo "key sha256 on the VM:        $got"
[ "$got" = "$want" ] || { echo "hash mismatch: refusing to sign" >&2; exit 1; }

if [ "${TEST:-}" = 1 ]; then
  echo "TEST=1: the throwaway key is in place; skipping the signing runner"
else
  vm "SB_PRIOR=${RELABEL_PRIOR:?RELABEL_PRIOR (the previous signed bundle of this tree) is not set} SB_LOG=$BLOG lockf -t 0 $LOCK /root/key-windows/boot-relabel-run.sh $RELEASE" && rc=0 || rc=$?
  vm "tail -14 $BLOG | cut -c1-200"
  [ "$rc" = 0 ] || { echo "the signing runner failed (exit $rc)" >&2; exit "$rc"; }
fi
