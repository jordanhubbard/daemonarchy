#!/bin/sh
# The checkout feed ABI gate accepts a matching feed and refuses a mislabelled, empty, unreadable or mixed one.
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
gate=$here/scripts/check-checkout-feed-abi.sh

# A catalogue is a tar of packagesite.yaml, one JSON package per line; plain tar reads like pkg's.
feed() { # name abi...
	dir=$work/$1; shift
	mkdir -p "$dir"
	: >"$dir/packagesite.yaml"
	n=0
	for abi in "$@"; do
		n=$((n + 1))
		printf '{"name":"daemonarchy-ports-checkout-%03d","abi":"%s"}\n' "$n" "$abi" >>"$dir/packagesite.yaml"
	done
	tar -cf "$dir/packagesite.pkg" -C "$dir" packagesite.yaml
	rm "$dir/packagesite.yaml"
}
refuses() { # label pattern dir abi
	if out=$(sh "$gate" "$3" "$4" 2>&1); then echo "Accepted: $1" >&2; exit 1; fi
	case $out in *"$2"*) ;; *) echo "Wrong refusal for $1: $out" >&2; exit 1 ;; esac
}

feed aarch64 FreeBSD:16:aarch64 FreeBSD:16:aarch64 FreeBSD:16:aarch64
feed amd64 FreeBSD:16:amd64
feed mixed FreeBSD:16:aarch64 FreeBSD:16:amd64
feed noabi
mkdir "$work/none" "$work/broken"
echo 'not a catalogue' >"$work/broken/packagesite.pkg"

out=$(sh "$gate" "$work/aarch64" FreeBSD:16:aarch64 2>&1)
case $out in *"accepted: every package declares FreeBSD:16:aarch64"*) ;; *) echo "Not accepted: $out" >&2; exit 1 ;; esac
sh "$gate" "$work/amd64" FreeBSD:16:amd64 >/dev/null 2>&1

# the 1.5.0 aarch64 checkout feed: amd64-labelled packages in an aarch64 image
refuses 'an amd64-labelled feed in an aarch64 image' 'declare FreeBSD:16:amd64 but this image is FreeBSD:16:aarch64' "$work/amd64" FreeBSD:16:aarch64
refuses 'an aarch64-labelled feed in an amd64 image' 'declare FreeBSD:16:aarch64 but this image is FreeBSD:16:amd64' "$work/aarch64" FreeBSD:16:amd64
refuses 'a feed mixing ABIs' 'declare' "$work/mixed" FreeBSD:16:aarch64
refuses 'a catalogue with no ABI' 'no package' "$work/noabi" FreeBSD:16:aarch64
refuses 'an unreadable catalogue' 'unreadable' "$work/broken" FreeBSD:16:aarch64
# no catalogue beside the checkout catalogue: nothing to check, and it says so
out=$(sh "$gate" "$work/none" FreeBSD:16:aarch64 2>&1)
case $out in *"not checked"*) ;; *) echo "Silent skip: $out" >&2; exit 1 ;; esac

# build-iso.sh runs it for the catalogue it embeds.
grep -q 'check-checkout-feed-abi.sh' "$here/build-iso.sh"
sh -n "$gate"
echo 'PASS: checkout feed ABI gate refuses a feed built for another architecture'
