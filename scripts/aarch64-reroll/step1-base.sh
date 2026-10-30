#!/bin/sh
# ARCH-001 1.4.1 arm64 step 1: update /usr/src to the post-1.4 sync, incremental world, kernel and release sets. Run as root.
set -eu
A=/home/jkh/a141; mkdir -p $A
REV=303b3646270ffa4bf7cec65c5c1d28bd8000cbce
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $A/state; }
G="git -c safe.directory=/usr/src"
cd /usr/src
state fetch
$G fetch --depth 1 origin $REV
$G checkout -q -f --detach $REV
[ "$($G rev-parse HEAD)" = "$REV" ]
$G diff --quiet HEAD && echo clean-source
state world
nice -n 5 make -j8 buildworld > $A/world.log 2>&1
state kernel
nice -n 5 make -j8 KERNCONF=GENERIC buildkernel > $A/kernel.log 2>&1
state sets
rm -rf /usr/obj/usr/src/arm64.aarch64/release
nice -n 5 make -C release -j8 NOSRC=yes NOPORTS=yes NODOC=yes packagesystem > $A/release.log 2>&1
rel=/usr/obj/usr/src/arm64.aarch64/release
cache=/var/cache/daemonarchy-iso-aarch64-303b364
rm -rf $cache; mkdir -p $cache
for n in base kernel; do cp -p $rel/$n.txz $cache/; done
[ -f $rel/lib32.txz ] && cp -p $rel/lib32.txz $cache/ || true
cp -p $rel/MANIFEST $cache/
(cd $cache && for f in *.txz; do want=$(awk -v t=$f '$1==t{print $2}' MANIFEST); [ "$(sha256 -q $f)" = "$want" ] || { echo "MANIFEST mismatch $f"; exit 1; }; done)
tar -xOf $cache/kernel.txz ./boot/kernel/kernel | strings | grep -m1 -E '^FreeBSD .* #[0-9]+ ' > $A/kernel-ident.txt || true
cat $A/kernel-ident.txt
ls -l $cache
state done-step1
