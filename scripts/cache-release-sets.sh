#!/bin/sh
# Persistent authoring cache, also used when creating the poudriere jail.
set -eu
cache=${SET_CACHE_DIR:-/var/cache/daemonarchy-iso}
url=${SNAPSHOT_URL:-https://download.freebsd.org/snapshots/amd64/16.0-CURRENT}
case "$cache" in /*) ;; *) echo 'SET_CACHE_DIR must be an absolute path' >&2; exit 1 ;; esac
mkdir -p "$cache"
temporary=''
cleanup() { [ -z "$temporary" ] || rm -f "$temporary"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
if [ ! -f "$cache/MANIFEST" ]; then
    temporary=$(mktemp "$cache/.MANIFEST.XXXXXX")
    fetch -q -o "$temporary" "$url/MANIFEST"
    chmod 0644 "$temporary"
    # Keep an already-selected manifest if another authoring job got here first.
    if ! ln "$temporary" "$cache/MANIFEST"; then
        [ -f "$cache/MANIFEST" ] || exit 1
    fi
    rm -f "$temporary"
    temporary=''
fi
for set in base kernel lib32; do
    want=$(awk -v f="$set.txz" '$1 == f { print $2 }' "$cache/MANIFEST")
    [ "${#want}" = 64 ] || { echo "Missing or invalid $set.txz checksum in cached MANIFEST" >&2; exit 1; }
    case "$want" in *[!0-9a-f]*) echo "Invalid $set.txz checksum in cached MANIFEST" >&2; exit 1 ;; esac
    if [ -f "$cache/$set.txz" ] && [ "$(sha256 -q "$cache/$set.txz")" = "$want" ]; then
        echo "    Reusing verified $set.txz"
        continue
    fi
    echo "    Fetching $set.txz into authoring cache"
    temporary=$(mktemp "$cache/.$set.txz.XXXXXX")
    fetch -q -o "$temporary" "$url/$set.txz"
    [ "$(sha256 -q "$temporary")" = "$want" ] || { echo "$set.txz checksum mismatch" >&2; exit 1; }
    chmod 0644 "$temporary"
    mv -f "$temporary" "$cache/$set.txz"
    temporary=''
done
