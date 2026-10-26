#!/bin/sh
# Releases publish the hybrid ISO xz-compressed. GitHub release assets must be
# smaller than 2 GiB, so that limit applies to the published .iso.xz. The raw
# ISO must still fit a nominal 4 GB USB stick (4,000,000,000 bytes, often
# slightly less usable), so it keeps a stated 3.5 GiB budget.
set -eu
usage='usage: check-image-size.sh image.iso [image.iso.xz]'
image=${1:?$usage}
compressed=${2:-}
[ $# -le 2 ] || { echo "$usage" >&2; exit 2; }
raw_limit=3758096384      # 3.5 GiB raw image budget for 4 GB USB media
asset_limit=2147483648    # GitHub release asset limit for the published .xz

check() { # path limit description
    [ -f "$1" ] || { echo "Image not found: $1" >&2; exit 1; }
    bytes=$(wc -c <"$1" | tr -d '[:space:]')
    if [ "$bytes" -ge "$2" ]; then
        echo "$3 is $bytes bytes; it must be smaller than $2 bytes." >&2
        exit 1
    fi
    echo "$3 size: $bytes bytes; $(($2 - bytes)) bytes below its $2-byte limit."
}

check "$image" "$raw_limit" 'Raw image'
if [ -n "$compressed" ]; then
    case $compressed in
        *.xz) ;;
        *) echo "Published image must be the .xz asset: $compressed" >&2; exit 2 ;;
    esac
    check "$compressed" "$asset_limit" 'Published .xz image'
fi
