#!/bin/sh
# Refuse a checkout feed whose packages declare another ABI than the image's.
#
#   check-checkout-feed-abi.sh FEED_DIR ABI        e.g. FEED_DIR=checkout-feed-150  ABI=FreeBSD:16:aarch64
#
# pkg will not read a repository whose packages declare a different ABI ("wrong architecture"), so a
# checkout feed built with the wrong label installs fine and then fails the first time a user chooses a
# ports or source checkout (daemonarchy-checkouts). FEED_DIR is the directory the image's checkouts.json
# comes from: the signed catalogue (packagesite.pkg) sits beside it. Without one there is nothing to
# check (the default overlay catalogue of a development image) and the check says so.
set -eu

feed=${1:?the checkout feed directory}
abi=${2:?the image ABI}

fail() { echo "checkout feed refused: $*" >&2; exit 1; }

catalogue=$feed/packagesite.pkg
if [ ! -s "$catalogue" ]; then
	echo "checkout feed ABI not checked: no signed catalogue beside the checkout catalogue in $feed" >&2
	exit 0
fi
entries=$(tar -xOf "$catalogue" packagesite.yaml 2>/dev/null) || fail "$catalogue is unreadable"
[ -n "$entries" ] || fail "$catalogue lists no packages"
abis=$(printf '%s\n' "$entries" | jq -r '.abi // empty' | sort -u)
[ -n "$abis" ] || fail "no package in $catalogue declares an ABI"
[ "$abis" = "$abi" ] || fail "its packages declare $(echo $abis) but this image is $abi (build the checkout feed with build-checkout-packages.py --abi $abi)"
echo "checkout feed accepted: every package declares $abi"
