#!/bin/sh
# Image size gates, checked on the final hybrid ISO including filesystem and
# boot overhead, before its checksums are issued.
#
#   check-image-size.sh image.iso            raw image only
#   check-image-size.sh image.iso image.xz   raw image and published asset
#
# The published release asset is the .xz, and GitHub release assets must be
# smaller than 2 GiB. The raw image carries the live desktop uncompressed, so
# it has its own budget: at most 3.5 GiB, which fits a nominal 4 GB USB stick
# (4,000,000,000 bytes) with room to spare.
set -eu
image=${1:?usage: check-image-size.sh image.iso [image.iso.xz]}
compressed=${2:-}
raw_limit=3758096384
asset_limit=2147483648
size_of() {
    [ -f "$1" ] || { echo "Image not found: $1" >&2; exit 1; }
    wc -c <"$1" | tr -d '[:space:]'
}
bytes=$(size_of "$image")
if [ "$bytes" -gt "$raw_limit" ]; then
    echo "Image is $bytes bytes; the raw image budget is $raw_limit bytes (3.5 GiB, a 4 GB USB stick)." >&2
    exit 1
fi
echo "Image size: $bytes bytes; $((raw_limit - bytes)) bytes within the raw image budget."
if [ -n "$compressed" ]; then
    bytes=$(size_of "$compressed")
    if [ "$bytes" -ge "$asset_limit" ]; then
        echo "Published image is $bytes bytes; release assets must be smaller than $asset_limit bytes." >&2
        exit 1
    fi
    echo "Published image size: $bytes bytes; $((asset_limit - bytes)) bytes below the release asset limit."
fi
