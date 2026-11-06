#!/bin/sh
# The operator's key window for the boot bundle of a release whose kernel or modules changed (RELEASE), run on madmax
# (where the key lives):
#
#   ssh jkh@madmax.local 'sh ~/daemonarchy-builder-vm/key-windows/boot-resign-window.sh'
#
# It puts boot-replacement-candidate-20261024.key in a tmpfs on the build VM (memory, swap off), compares the sha256 on both
# sides, runs /root/key-windows/boot-resign-run.sh RELEASE there under the key-window lock (it refuses unless the frozen inputs
# still hash to RESIGN_FREEZE_SHA256, then rebuilds the boot tree, signs the manifest and loader, creates and verifies the bundle),
# and whatever happens removes the key, unmounts the tmpfs and turns swap back on. Nothing is copied through another machine
# and nothing is printed except hashes and log lines.
#
# Before the window: on the VM, `boot-resign-run.sh RELEASE --freeze` (with the same SB_CACHE, SB_PACKAGES and SB_REV) prints
# the frozen inputs and their sha256; record it as RESIGN_FREEZE_SHA256 in key-windows.env.
#
# Safety rules, each tested with TEST=1 (a throwaway key and certificate; the VM rehearses the whole re-sign on a scratch copy
# of the real inputs; no real key moves and no real tree or bundle is touched):
#   - the key must be the expected one (sha256) and must belong to the release certificate, checked on madmax before it moves;
#   - nothing is written until /var/keytmp is verified to be a tmpfs mount this script made;
#   - swap off (failure tolerated only if none is active afterwards); hashes must match on both sides;
#   - the arm64 feed window, the extension window or a held lock refuses this one;
#   - a changed input (freeze) or an existing bundle for the release refuses the signature.
# TEST=1 FAULT=mount|notmpfs|swap|hash|lock|feedwindow|extwindow|wrongkey|frozen|exists injects a failure.
set -eu
W=$HOME/daemonarchy-builder-vm/ssh-worker.sh
ENVFILE=${KEYWINDOW_ENV:-$HOME/daemonarchy-builder-vm/key-windows.env}   # release-specific values: see key-windows.env.example
[ ! -f "$ENVFILE" ] || . "$ENVFILE"
MNT=/var/keytmp
OTHERS="/var/keytmp-feed:arm64 feed /var/keytmp-ext:extension"
LOCK=/var/run/keywindow.lock
NAME=boot-replacement-candidate-20261024.key
VMNAME=boot.key
REAL_EXPECT=${BOOT_KEY_SHA256:-}
CERTLOCAL=${CERT_LOCAL:-}
CERTSHA=${CERT_SHA256:-}
FAULT=${FAULT:-}
RELEASE=${RELEASE:?RELEASE (X.Y.Z) is not set: put it in key-windows.env}
VMROOT=${WORK:?WORK (the release working directory on the VM) is not set: put it in key-windows.env}
CACHE=${RESIGN_CACHE:?RESIGN_CACHE (the release source sets on the VM) is not set}
PACKAGES=${RESIGN_PACKAGES:?RESIGN_PACKAGES (the release package directory .../All on the VM) is not set}
REV=${RESIGN_REV:?RESIGN_REV (the release source revision) is not set}
FREEZE=${RESIGN_FREEZE_SHA256:-}
SB=/usr/daemonarchy/sb16
TESTROOT=/tmp/bootresign-test
BLOG=$VMROOT/evidence/sign-boot-resign-$RELEASE.log
RUN=/root/key-windows/boot-resign-run.sh

vm() { "$W" "$1"; }
certpub() { openssl x509 -in "$1" -noout -pubkey 2>/dev/null | sha256sum | cut -d' ' -f1; }
keypub() { openssl pkey -in "$1" -pubout 2>/dev/null | sha256sum | cut -d' ' -f1; }

if [ "${TEST:-}" = 1 ]; then
  T=$(mktemp -d)
  src=$T/$NAME
  openssl genrsa -out "$src" 4096 2>/dev/null                       # a throwaway key named like the key: not the real one
  openssl req -new -x509 -key "$src" -days 3650 -subj /CN=throwaway -out "$T/test.pem" 2>/dev/null
  openssl genrsa 2048 2>/dev/null | openssl req -new -x509 -key /dev/stdin -days 30 -subj /CN=other -out "$T/other.pem" 2>/dev/null
  case "$FAULT" in wrongkey) usecert=$T/other.pem ;; *) usecert=$T/test.pem ;; esac
  EXPECT=$(sha256sum "$src" | cut -d' ' -f1)
else
  [ -z "$FAULT" ] || { echo "FAULT is only for TEST=1" >&2; exit 2; }
  src=$HOME/daemonarchy-keys/$NAME
  usecert=$CERTLOCAL
  EXPECT=${EXPECT:-$REAL_EXPECT}
  [ -n "$EXPECT" ] && [ -n "$CERTLOCAL" ] && [ -n "$CERTSHA" ] || { echo "BOOT_KEY_SHA256, CERT_LOCAL and CERT_SHA256 must be set in $ENVFILE for a real run: refusing" >&2; exit 1; }
  [ -n "$FREEZE" ] || { echo "RESIGN_FREEZE_SHA256 must be set in $ENVFILE (boot-resign-run.sh $RELEASE --freeze): refusing" >&2; exit 1; }
  [ "$(sha256sum "$CERTLOCAL" | cut -d' ' -f1)" = "$CERTSHA" ] || { echo "$CERTLOCAL is not the release certificate: refusing" >&2; exit 1; }
fi
[ -f "$src" ] || { echo "no key at $src" >&2; exit 1; }
want=$(sha256sum "$src" | cut -d' ' -f1)
echo "key sha256 on madmax before: $want"
[ "$want" = "$EXPECT" ] || { echo "the key on madmax is not the expected one ($EXPECT): refusing" >&2; [ "${TEST:-}" != 1 ] || rm -rf "$T"; exit 1; }
[ "$(keypub "$src")" = "$(certpub "$usecert")" ] || { echo "this key does not belong to the release certificate: refusing" >&2; [ "${TEST:-}" != 1 ] || rm -rf "$T"; exit 1; }

cleanup() {
  status=$?
  vm "[ -e $MNT/$VMNAME ] && { rm -P $MNT/$VMNAME 2>/dev/null; rm -f $MNT/$VMNAME; }; if mount | grep -q '^tmpfs on $MNT (tmpfs'; then umount $MNT; fi; rmdir $MNT 2>/dev/null; swapon -a 2>/dev/null; true" >/dev/null 2>&1 || true
  [ "${TEST:-}" != 1 ] || vm "rm -rf $TESTROOT; true" >/dev/null 2>&1 || true
  if vm "mount | grep -q ' on $MNT '" 2>/dev/null; then echo "WARNING: $MNT is still mounted on the VM" >&2; ok=0; else ok=1; fi
  if vm "[ -e $MNT/$VMNAME ]" 2>/dev/null; then echo "WARNING: key file still present on the VM" >&2; ok=0; fi
  [ "$ok" = 1 ] && echo "VM: key file gone, $MNT not mounted, swap $(vm 'swapinfo | sed 1d | wc -l | tr -d " "' 2>/dev/null) device(s) active"
  echo "key sha256 on madmax after:  $(sha256sum "$src" 2>/dev/null | cut -d' ' -f1)"
  [ "${TEST:-}" != 1 ] || rm -rf "$T"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

vm "[ -x $RUN ] && [ -d $SB/build ] && [ -d $SB/product/secureboot ] && [ -f $CACHE/MANIFEST ] && [ -d $PACKAGES ]" \
  || { echo "the inputs for the re-sign are not on the VM: refusing" >&2; exit 1; }
if [ "${TEST:-}" != 1 ] && vm "[ -e $SB/daemonarchy-$RELEASE-boot.txz ]"; then
  echo "$SB/daemonarchy-$RELEASE-boot.txz already exists: refusing" >&2; exit 1
fi

# Refuse overlapping windows before anything is placed.
[ "$FAULT" != feedwindow ] || vm "mkdir -p /var/keytmp-feed && mount -t tmpfs -o size=1m tmpfs /var/keytmp-feed" || true
[ "$FAULT" != extwindow ] || vm "mkdir -p /var/keytmp-ext && mount -t tmpfs -o size=1m tmpfs /var/keytmp-ext" || true
for pair in $OTHERS; do
  m=${pair%%:*}
  if vm "mount | grep -q ' on $m '" 2>/dev/null; then
    if [ "$FAULT" = feedwindow ] || [ "$FAULT" = extwindow ]; then vm "umount $m; rmdir $m" || true; fi
    echo "another key window is open on the VM ($m mounted): refusing" >&2; exit 1
  fi
done
if [ "$FAULT" = lock ]; then vm "mkdir $LOCK" || true; fi
if vm "[ -e $LOCK ]"; then
  [ "$FAULT" != lock ] || vm "rmdir $LOCK" || true
  echo "$LOCK exists on the VM: another key window is open, refusing" >&2; exit 1
fi

# TEST only: a scratch copy of the real inputs whose build receipt names the throwaway certificate; the runner signs that.
common="SB_CACHE=$CACHE SB_PACKAGES=$PACKAGES SB_REV=$REV"
if [ "${TEST:-}" = 1 ]; then
  "$W" "mkdir -p $TESTROOT && cat > $TESTROOT/c.pem" <"$usecert"
  setup=$(cat <<EOS
set -e
T=$TESTROOT; S=$SB; PY=/usr/local/bin/python3.12
mkdir -p \$T/sb/build
cp \$S/build/kernel \$S/build/loader_lua.efi \$S/build/loader_normal.efi \$T/sb/build/
\$PY -I -c "
import json,hashlib
r=json.load(open('\$S/build/build.json')); r['trust_anchor_sha256']=hashlib.sha256(open('\$T/c.pem','rb').read()).hexdigest()
json.dump(r,open('\$T/sb/build/build.json','w'),indent=2)"
cp -R \$S/product \$T/sb/product
echo "   rehearsal scratch copy: \$(ls \$T/sb | tr '\n' ' ')"
EOS
)
  vm "$setup" 2>&1 | tail -2 | cut -c1-170
  [ "$FAULT" != exists ] || vm "touch $TESTROOT/sb/daemonarchy-$RELEASE-boot.txz"
  testenv="$common SB_TEST=1 SB_S=$TESTROOT/sb SB_CERT=$TESTROOT/c.pem SB_LOG=$TESTROOT/run.log"
  FREEZE=$(vm "$testenv $RUN $RELEASE --freeze" | sed -n 's/^freeze sha256: //p')
  echo "   rehearsal freeze sha256: $FREEZE"
  [ "$FAULT" != frozen ] || vm "echo '-- changed' >> $TESTROOT/sb/product/secureboot/boot/local.lua"
  runner_env="$testenv SB_FREEZE=$FREEZE"
fi

# Memory only: no swap, and a 1 MiB tmpfs that is verified before any byte of the key is written.
vm "swapoff -a 2>/dev/null; true"
if [ "$FAULT" = swap ]; then echo "(fault: pretending swap is still active)" >&2; swapleft=1
else swapleft=$(vm "swapinfo | sed 1d | wc -l | tr -d ' '"); fi
[ "$swapleft" = 0 ] || { echo "swap is still active on the VM: refusing" >&2; exit 1; }
if vm "mount | grep -q ' on $MNT '"; then echo "$MNT is already mounted: refusing" >&2; exit 1; fi
case "$FAULT" in
  mount)   vm "mkdir -p $MNT && mount -t nosuchfs -o size=1m tmpfs $MNT" || echo "(fault: the mount failed)" >&2 ;;
  notmpfs) vm "mkdir -p $MNT" ;;
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
  out=$(vm "$runner_env SB_KEY=$MNT/$VMNAME lockf -t 0 $LOCK $RUN $RELEASE" 2>&1) && rc=0 || rc=$?
  echo "$out" | grep -v '  input ' | sed 's/^/   runner: /' | cut -c1-200
else
  vm "$common SB_FREEZE=$FREEZE SB_LOG=$BLOG lockf -t 0 $LOCK $RUN $RELEASE" && rc=0 || rc=$?
  vm "grep -v '  input ' $BLOG | tail -12 | cut -c1-200"
fi
[ "$rc" = 0 ] || { echo "the signing runner failed (exit $rc)" >&2; exit "$rc"; }
