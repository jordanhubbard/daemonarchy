#!/bin/sh
# ARCH-001 1.4.1 arm64 step 4: product checkout, src+ports checkout packages and the arm64 checkout catalogue. Run as root.
set -eu
A=/home/jkh/a141
REV=303b3646270ffa4bf7cec65c5c1d28bd8000cbce
PREV=582675f016b0b0d8e8760852767443841075e825
PY=/usr/local/bin/python3.12
TAG=checkouts-16-aarch64-1.4.1
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $A/state; }
state checkout-start
rm -rf $A/product $A/src-full $A/checkout-repo $A/checkout-feed
git clone -q --depth 1 https://github.com/jordanhubbard/daemonarchy.git $A/product
git -C $A/product rev-parse HEAD > $A/product-rev.txt
git clone -q --depth 1 --single-branch --branch daemonarchy https://github.com/jordanhubbard/daemonarchy-src.git $A/src-full
[ "$(git -C $A/src-full rev-parse HEAD)" = "$REV" ]
mkdir -p $A/checkout-repo
nice -n 10 $PY $A/product/scripts/build-checkout-packages.py --kind src --repo $A/src-full --revision $REV --branch daemonarchy --remote https://github.com/jordanhubbard/daemonarchy-src.git --out $A/checkout-repo > $A/checkout-src.log 2>&1
state checkout-src-done
nice -n 10 $PY $A/product/scripts/build-checkout-packages.py --kind ports --repo $A/ports-0e8fb88 --revision $PREV --branch main --remote https://github.com/jordanhubbard/daemonarchy-ports.git --out $A/checkout-repo > $A/checkout-ports.log 2>&1
state checkout-ports-done
mkdir -p $A/checkout-feed
cp -p $A/checkout-repo/* $A/checkout-feed/
$PY $A/product/scripts/make-checkout-catalog.py $A/checkout-feed --url https://github.com/jordanhubbard/daemonarchy/releases/download/$TAG --ports-tracking-branch main > $A/checkout-feed/checkouts.json.tmp
jq '.trees.src.tracking_branch = "daemonarchy"' $A/checkout-feed/checkouts.json.tmp > $A/checkout-feed/checkouts.json
rm -f $A/checkout-feed/checkouts.json.tmp
jq -e ".schema == 1 and .trees.src.revision == \"$REV\" and .trees.ports.revision == \"$PREV\"" $A/checkout-feed/checkouts.json
ls -l $A/checkout-feed
state done-step4
