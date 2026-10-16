#!/bin/sh
# Native cache boundaries: offline reuse, repair, and failed-download retention.
set -eu
[ "$(uname -s)" = FreeBSD ] || { echo 'Run on FreeBSD' >&2; exit 1; }
here=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir "$work/upstream" "$work/cache" "$work/payload"
for set in base kernel lib32; do
    printf '%s\n' "$set fixture" > "$work/payload/$set"
    tar -czf "$work/upstream/$set.txz" -C "$work/payload" "$set"
    printf '%s.txz %s\n' "$set" "$(sha256 -q "$work/upstream/$set.txz")" >> "$work/upstream/MANIFEST"
done
run_cache() {
    SET_CACHE_DIR="$work/cache" SNAPSHOT_URL="$1" sh "$here/scripts/cache-release-sets.sh"
}
run_cache "file://$work/upstream"
for set in base kernel lib32; do
    cmp "$work/upstream/$set.txz" "$work/cache/$set.txz"
done
before=$(stat -f '%i:%m' "$work/cache/base.txz")
run_cache http://127.0.0.1:9
[ "$(stat -f '%i:%m' "$work/cache/base.txz")" = "$before" ]

printf '%s\n' damaged > "$work/cache/kernel.txz"
run_cache "file://$work/upstream"
cmp "$work/upstream/kernel.txz" "$work/cache/kernel.txz"
[ "$(stat -f '%i:%m' "$work/cache/base.txz")" = "$before" ]

printf '%s\n' retained > "$work/cache/kernel.txz"
printf '%s\n' corrupt-download > "$work/upstream/kernel.txz"
if run_cache "file://$work/upstream" > "$work/rejected.log" 2>&1; then
    echo 'Accepted a corrupt release-set download' >&2
    exit 1
fi
grep -q 'kernel.txz checksum mismatch' "$work/rejected.log"
[ "$(cat "$work/cache/kernel.txz")" = retained ]
[ -z "$(find "$work/cache" -name '.*.txz.*' -print)" ]
printf '%s\n' 'PASS: authoring cache fetch, offline reuse, damaged-entry repair and atomic checksum rejection'
