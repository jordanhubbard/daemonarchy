#!/bin/sh
# Which packages of the last release's application feed change with a new ports revision?
#
#   diff-release-packages.sh OLD_PORTS NEW_PORTS FEED.tsv [EXTRA_ORIGIN...]
#
# OLD_PORTS and NEW_PORTS are ports trees (the revision the feed was built from, and the one
# to release). FEED.tsv has one `origin<TAB>name-version` line per package in the published
# application feed; make it from the feed's catalogue:
#
#   fetch -o packagesite.pkg https://github.com/jordanhubbard/daemonarchy/releases/download/TAG/packagesite.pkg
#   tar -xOf packagesite.pkg packagesite.yaml | jq -r '[.origin, (.name + "-" + .version)] | @tsv' | sort > FEED.tsv
#
# It prints a line for each origin whose PKGNAME differs between the trees (DIFF), that is gone
# from the new tree (GONE), and for each EXTRA_ORIGIN that is new (NEW) or changed. It runs
# `make -V PKGNAME` only: nothing is built, nothing is signed, nothing is published. Kernel-bound
# packages are on the ISO and not in the feed, so list them as extra origins (for example
# net/if_brcmfmac-kmod) to see whether a signed module inventory has to move.
set -eu
[ $# -ge 3 ] || { sed -n '2,19p' "$0" >&2; exit 2; }
OLD=$1 NEW=$2 FEED=$3
shift 3
name_in() { # tree origin
  PORTSDIR=$1 make -C "$1/$2" -V PKGNAME 2>/dev/null || echo ERROR
}
tab=$(printf '\t')
while IFS="$tab" read -r origin pkg; do
  [ -d "$NEW/$origin" ] || { echo "GONE $origin $pkg"; continue; }
  old=$(name_in "$OLD" "$origin")
  new=$(name_in "$NEW" "$origin")
  [ "$old" = "$new" ] || echo "DIFF $origin $old -> $new (feed has $pkg)"
done <"$FEED"
for origin in "$@"; do
  if [ ! -d "$NEW/$origin" ]; then echo "GONE $origin"; continue; fi
  new=$(name_in "$NEW" "$origin")
  if [ ! -d "$OLD/$origin" ]; then echo "NEW $origin $new"; continue; fi
  old=$(name_in "$OLD" "$origin")
  [ "$old" = "$new" ] || echo "DIFF $origin $old -> $new"
done
