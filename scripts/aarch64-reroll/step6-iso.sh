#!/bin/sh
# ARCH-001 1.4.1 arm64 step 6: build the arm64 installer ISO (QA candidate, no closure mirror). Run as root.
set -eu
A=/home/jkh/a141
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $A/state; }
state iso-start
rm -rf $A/out $A/stage; mkdir -p $A/out $A/stage
cd $A/product
set +e
env ARCH=aarch64 JAIL=16aarch64r2 PTREE=daemonarchy141 \
  SET_CACHE_DIR=/var/cache/daemonarchy-iso-aarch64-303b364 OUTDIR=$A/out ISO_STAGE_PARENT=$A/stage \
  CHECKOUT_CATALOG=$A/checkout-feed/checkouts.json \
  PACKAGE_REPOSITORY_TAG=packages-16-aarch64-1.4.1 \
  PACKAGE_REPOSITORY_PUBLIC_KEY=$A/product/keys/pkg-repo-1.3.1.pub \
  timeout -k 60 14400 sh ./build-iso.sh > $A/iso.log 2>&1
st=$?
set -e
echo "iso-exit=$st" >> $A/state
state iso-done
ls -la $A/out > $A/iso-files.txt 2>&1 || true
tail -8 $A/iso.log | cut -c1-200 > $A/iso-tail.txt
[ "$st" = 0 ] && state done-step6 || exit $st
