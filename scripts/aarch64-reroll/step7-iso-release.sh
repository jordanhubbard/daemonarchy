#!/bin/sh
# ARCH-001 1.4.1 arm64 step 7: the release ISO, built from a fresh clone of main with BOTH published
# closure shards as its package mirror. REQUIRE_PACKAGE_MIRROR=yes makes the build fail unless every
# installer root resolves from the shards, so run it only after the application feed (PACKAGE_REPOSITORY_TAG)
# is staged at the final ports revision. Run as root.
set -eu
A=/home/jkh/a141
R=https://github.com/jordanhubbard/daemonarchy/releases/download
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $A/state; }
state iso-release-start
# A build leaves system-immutable files in its stage; clear the flags before removing it.
chflags -R noschg,nosunlnk $A/stage-release 2>/dev/null || true
rm -rf $A/product-release $A/out-release $A/stage-release; mkdir -p $A/out-release $A/stage-release
git clone -q --depth 1 https://github.com/jordanhubbard/daemonarchy.git $A/product-release
git -C $A/product-release rev-parse HEAD > $A/product-release-rev.txt
cd $A/product-release
set +e
env ARCH=aarch64 JAIL=16aarch64r2 PTREE=daemonarchy141 \
  SET_CACHE_DIR=/var/cache/daemonarchy-iso-aarch64-303b364 OUTDIR=$A/out-release ISO_STAGE_PARENT=$A/stage-release \
  CHECKOUT_CATALOG=$A/${CHECKOUT_FEED_DIR:-checkout-feed}/checkouts.json \
  PACKAGE_REPOSITORY_TAG=${PACKAGE_REPOSITORY_TAG:-packages-16-aarch64-1.4.1} \
  PACKAGE_REPOSITORY_PUBLIC_KEY=$A/product-release/keys/pkg-repo-1.3.1.pub \
  PACKAGE_MIRROR_URLS="$R/packages-16-aarch64-1.4.1-upstream $R/packages-16-aarch64-1.4.1-upstream-2" \
  REQUIRE_PACKAGE_MIRROR=yes \
  timeout -k 60 14400 sh ./build-iso.sh > $A/iso-release.log 2>&1
st=$?
set -e
echo "iso-release-exit=$st" >> $A/state
state iso-release-done
ls -la $A/out-release > $A/iso-release-files.txt 2>&1 || true
tail -8 $A/iso-release.log | cut -c1-200 > $A/iso-release-tail.txt
[ "$st" = 0 ] && state done-step7 || exit $st
