#!/bin/sh
# The operator's key window for the FULL boot re-sign of a release (RELEASE), run on madmax (where the key lives):
#
#   ssh jkh@madmax.local 'sh ~/daemonarchy-builder-vm/key-windows/boot-full-window.sh'
#
# It puts boot-replacement-candidate-20261024.key in a tmpfs on the build VM (memory, swap off), compares the sha256 on both
# sides, runs /root/key-windows/boot-full-run.sh RELEASE there under the key-window lock (it rebuilds the boot tree from the commit's
# inputs, signs the manifest and loader, creates the bundle, and refuses unless only the expected files changed), and whatever
# happens removes the key, unmounts the tmpfs and turns swap back on. Nothing is copied through another machine and nothing is
# printed except hashes and log lines.
#
# Safety rules, each tested with TEST=1 (a throwaway key and certificate; the VM rehearses the whole sign-and-compare on a scratch
# copy; no real key moves and no real tree or bundle is touched):
#   - the key must be the expected one (sha256) and must belong to the release certificate, checked on madmax before it moves;
#   - nothing is written until /var/keytmp is verified to be a tmpfs mount this script made;
#   - swap off (failure tolerated only if none is active afterwards); hashes must match on both sides;
#   - the arm64 feed window, the extension window or a held lock refuses this one.
# TEST=1 FAULT=mount|notmpfs|swap|hash|lock|feedwindow|extwindow|wrongkey|inv|priorstale|frozen|noexpect injects a failure.
set -eu
W=$HOME/daemonarchy-builder-vm/ssh-worker.sh
ENVFILE=${KEYWINDOW_ENV:-$HOME/daemonarchy-builder-vm/key-windows.env}   # release-specific values: see key-windows.env.example
[ ! -f "$ENVFILE" ] || . "$ENVFILE"
MNT=/var/keytmp
OTHERS="/var/keytmp-feed:arm64 feed /var/keytmp-ext:extension"
LOCK=/var/run/keywindow.lock
NAME=boot-replacement-candidate-20261024.key
VMNAME=boot.key
REAL_EXPECT=${BOOT_KEY_SHA256:-}                 # sha256 of the boot signing key file, from key-windows.env
CERTLOCAL=${CERT_LOCAL:-}                        # the public release certificate on this host, from key-windows.env
CERTSHA=${CERT_SHA256:-}
FAULT=${FAULT:-}
RELEASE=${RELEASE:?RELEASE (X.Y.Z) is not set: put it in key-windows.env}
VMROOT=${WORK:?WORK (the release working directory on the VM) is not set: put it in key-windows.env}
PRODUCT=${BOOT_PRODUCT:?BOOT_PRODUCT (the commit inputs staged on the VM) is not set}
INVSHA=${INV_SHA256:?INV_SHA256 (the module inventory the previous bundle was signed with) is not set}
KMOD=${KMOD_SHA256:?KMOD_SHA256 (the kernel module the inventory must list) is not set}
SB=/usr/daemonarchy/sb16
TESTROOT=/tmp/bootfull-test
BLOG=$VMROOT/evidence/sign-boot-full-$RELEASE.log

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
  [ "$(sha256sum "$CERTLOCAL" | cut -d' ' -f1)" = "$CERTSHA" ] || { echo "$CERTLOCAL is not the release certificate: refusing" >&2; exit 1; }
fi
[ -f "$src" ] || { echo "no key at $src" >&2; exit 1; }
want=$(sha256sum "$src" | cut -d' ' -f1)
echo "key sha256 on madmax before: $want"
[ "$want" = "$EXPECT" ] || { echo "the key on madmax is not the expected one ($EXPECT): refusing" >&2; [ "${TEST:-}" != 1 ] || rm -rf "$T"; exit 1; }
[ "$(keypub "$src")" = "$(certpub "$usecert")" ] || { echo "this key does not belong to the release certificate: refusing" >&2; [ "${TEST:-}" != 1 ] || rm -rf "$T"; exit 1; }

cleanup() {
  status=$?
  # Idempotent: the runner removes the key on its own exit paths too. Only unmount what is a tmpfs.
  vm "[ -e $MNT/$VMNAME ] && { rm -P $MNT/$VMNAME 2>/dev/null; rm -f $MNT/$VMNAME; }; if mount | grep -q '^tmpfs on $MNT (tmpfs'; then umount $MNT; fi; rmdir $MNT 2>/dev/null; swapon -a 2>/dev/null; true" >/dev/null 2>&1 || true
  [ "${TEST:-}" != 1 ] || vm "rm -rf $TESTROOT; true" >/dev/null 2>&1 || true   # the lock belongs to the runner that took it
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

# The inputs must already be on the VM.
if [ "${TEST:-}" != 1 ]; then
  vm "[ -d $PRODUCT/secureboot ] && [ -d $SB/boot-tree ] && [ -f $SB/daemonarchy-$RELEASE-boot.txz ] && [ -f $SB/daemonarchy-$RELEASE-boot.txz.sig ] && [ -x /root/key-windows/boot-full-run.sh ]" \
    || { echo "the inputs for the full re-sign are not on the VM: refusing" >&2; exit 1; }
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

# TEST only: rehearse on a scratch copy. An OLD tree is prepared from the old product and signed with the throwaway key,
# then the runner must take it to the new inputs.
runner_env=
if [ "${TEST:-}" = 1 ]; then
  "$W" "mkdir -p $TESTROOT && cat > $TESTROOT/c.pem" <"$usecert"
  "$W" "cat > $TESTROOT/setup.key; chmod 400 $TESTROOT/setup.key" <"$src"
  setup=$(cat <<EOS
set -e
T=$TESTROOT; S=$SB; W=$VMROOT; PY=/usr/local/bin/python3.12; FW=/usr/daemonarchy/firmware-policy-guest-private-20261023/apple
mkdir -p \$T/sb/build
cp \$S/build/kernel \$S/build/loader_lua.efi \$S/build/loader_normal.efi \$T/sb/build/
\$PY -I -c "
import json,hashlib
r=json.load(open('\$S/build/build.json')); r['trust_anchor_sha256']=hashlib.sha256(open('\$T/c.pem','rb').read()).hexdigest()
json.dump(r,open('\$T/sb/build/build.json','w'),indent=2)"
/bin/sh \$S/product/secureboot/prepare-boot-tree.sh \$W/inputs/source-sets \$T/sb/build \$T/sb/boot-tree >/dev/null
\$PY \$S/product/secureboot/sign-boot-tree.py \$T/sb/boot-tree --loader \$T/sb/build/loader_lua.efi --build-receipt \$T/sb/build/build.json --kernel-path kernel.secure/kernel --module-inventory \$S/module-inventory.json --firmware-stage \$FW --certificate \$T/c.pem --key \$T/setup.key >/dev/null
\$PY \$S/product/secureboot/bundle.py \$T/sb/boot-tree --out \$T/sb/daemonarchy-$RELEASE-boot.txz --release $RELEASE --build-receipt \$T/sb/build/build.json --certificate \$T/c.pem --key \$T/setup.key
rm -f \$T/setup.key
echo "   rehearsal OLD tree + bundle signed with the throwaway key: \$(ls \$T/sb | tr '\n' ' ')"
EOS
)
  vm "$setup" 2>&1 | tail -3 | cut -c1-170
  prod=$PRODUCT
  case "$FAULT" in
    priorstale) vm "echo stale >> $TESTROOT/sb/boot-tree/boot/lua/local.lua" ;;
    frozen)     vm "rm -rf $TESTROOT/pbad && cp -R $PRODUCT $TESTROOT/pbad && echo '-- changed' >> $TESTROOT/pbad/secureboot/boot/local.lua"; prod=$TESTROOT/pbad ;;
  esac
  # noexpect: the brand lua differs but is not listed as expected, so the prepared-tree gate must refuse.
  exp=boot/lua/brand-daemonarchy.lua; [ "$FAULT" != noexpect ] || exp=none
  invsha=$(vm "sha256 -q $SB/module-inventory.json"); [ "$FAULT" != inv ] || invsha=$(printf '%064d' 0)
  runner_env="SB_WORK=$VMROOT SB_KMOD=$KMOD SB_S=$TESTROOT/sb SB_BUILD=$TESTROOT/sb/build SB_CERT=$TESTROOT/c.pem SB_PRODUCT=$prod SB_OLDPRODUCT=$SB/product SB_INV=$SB/module-inventory.json SB_INVSHA=$invsha SB_EXPECT=$exp SB_LOG=$TESTROOT/run.log"
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
if [ "$FAULT" = hash ]; then head -c 256 /dev/urandom | "$W" "umask 077; cat > $MNT/$VMNAME; chmod 400 $MNT/$VMNAME"
else "$W" "umask 077; cat > $MNT/$VMNAME; chmod 400 $MNT/$VMNAME" <"$src"; fi
got=$(vm "sha256 -q $MNT/$VMNAME")
echo "key sha256 on the VM:        $got"
[ "$got" = "$want" ] || { echo "hash mismatch: refusing to sign" >&2; exit 1; }

if [ "${TEST:-}" = 1 ]; then
  out=$(vm "$runner_env lockf -t 0 $LOCK /root/key-windows/boot-full-run.sh $RELEASE" 2>&1) && rc=0 || rc=$?
  echo "$out" | sed 's/^/   runner: /' | cut -c1-200
  vm "cut -c1-200 $TESTROOT/run.log | tail -22" | sed 's/^/   log: /'
else
  vm "SB_WORK=$VMROOT SB_PRODUCT=$PRODUCT SB_INVSHA=$INVSHA SB_KMOD=$KMOD SB_LOG=$BLOG lockf -t 0 $LOCK /root/key-windows/boot-full-run.sh $RELEASE" && rc=0 || rc=$?
  vm "tail -16 $BLOG | cut -c1-200"
fi
[ "$rc" = 0 ] || { echo "the signing runner failed (exit $rc)" >&2; exit "$rc"; }
