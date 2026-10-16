#!/bin/sh
# GitHub release assets must be smaller than 2 GiB. Check the final hybrid ISO,
# including filesystem/boot overhead, before issuing its release checksum.
set -eu
image=${1:?usage: check-image-size.sh image.iso}
[ -f "$image" ] || { echo "Image not found: $image" >&2; exit 1; }
bytes=$(wc -c <"$image" | tr -d '[:space:]')
limit=2147483648
if [ "$bytes" -ge "$limit" ]; then
    echo "Image is $bytes bytes; release assets must be smaller than $limit bytes." >&2
    exit 1
fi
echo "Image size: $bytes bytes; $((limit - bytes)) bytes below the release asset limit."
