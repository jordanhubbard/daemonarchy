#!/bin/sh

# Publish Daemonarchy's own packages as a signed pkg(8) repository, so
# installed systems get updates to them with pkg upgrade (and Omarchy's
# update) instead of waiting for the next ISO.
#
# The repository is the assets of one GitHub release ($TAG), laid out flat:
# meta.conf, packagesite.pkg, data.pkg and the packages side by side, since
# release assets cannot be in subdirectories. It holds the ports listed in
# OMARCHY_ORIGINS (origins.sh); everything else comes from pkg.FreeBSD.org.
#
#   pkg-repo.sh keygen          on the build host, as root, once
#   pkg-repo.sh build           on the build host, as root: collect and sign
#   pkg-repo.sh upload <dir>    anywhere with gh: replace the release's assets
#   pkg-repo.sh publish         from a workstation with gh: copy this
#                               script to $BUILD_HOST, build there over
#                               ssh, then upload
#
# The signing key stays on the build host. Its public half is
# overlay/usr/local/share/daemonarchy-installer/daemonarchy.pub, which the
# installer copies to /usr/local/etc/pkg/keys on the installed system.

set -eu

JAIL=${JAIL:-16amd64}
PTREE=${PTREE:-omarchyiso}
TAG=${TAG:-packages-16-amd64}
GH_REPO=${GH_REPO:-jordanhubbard/daemonarchy}
BUILD_HOST=${BUILD_HOST:-freebsd.local}
BUILD_DIR=${BUILD_DIR:-daemonarchy}
KEY=${KEY:-/usr/local/etc/daemonarchy/pkg-repo.key}
OUT=${OUT:-/usr/local/poudriere/data/daemonarchy-repo/$TAG}

here=$(cd "$(dirname "$0")" && pwd)
packages=/usr/local/poudriere/data/packages/$JAIL-$PTREE
. "$here/origins.sh"

keygen() {
	if [ -e "$KEY" ]; then
		echo "$KEY already exists" >&2
		exit 1
	fi
	mkdir -p "$(dirname "$KEY")"
	(umask 077 && openssl genrsa -out "$KEY" 4096 2>/dev/null)
	chmod 0400 "$KEY"
	openssl rsa -in "$KEY" -pubout 2>/dev/null
}

build() {
	rm -rf "$OUT"
	mkdir -p "$OUT"
	for pkgfile in "$packages"/All/*.pkg; do
		origin=$(pkg query -F "$pkgfile" '%o')
		case " $(echo $OMARCHY_ORIGINS) " in
		# GitHub renames assets with characters outside [A-Za-z0-9._-],
		# such as the comma of an epoch (daemonarchy-1.0.0,1). pkg finds a
		# package by the path the catalogue records, not by its name, so
		# give the file a name GitHub keeps.
		*" $origin "*) cp "$pkgfile" "$OUT/$(basename "$pkgfile" | tr -c 'A-Za-z0-9._\n-' '.')" ;;
		esac
	done
	pkg repo -q "$OUT" "$KEY" >/dev/null
	echo "$OUT: $(ls "$OUT"/*.pkg | grep -cvE '/(packagesite|data|meta)\.pkg$') packages"
}

upload() {
	dir=$1
	if ! gh release view "$TAG" -R "$GH_REPO" >/dev/null 2>&1; then
		gh release create "$TAG" -R "$GH_REPO" --latest=false \
		    --title "Daemonarchy packages for FreeBSD 16 (amd64)" \
		    --notes "The pkg repository installed Daemonarchy systems update from: the Omarchy ports and the fixes the official FreeBSD packages lack yet, signed with Daemonarchy's key. There is nothing here to download by hand; \`pkg upgrade\` uses it."
	fi
	# Packages first, then the catalogue that names them, so a client never
	# sees a catalogue whose packages are missing.
	for f in "$dir"/*.pkg; do
		case ${f##*/} in
		packagesite.pkg | data.pkg | meta.pkg) ;;
		*) gh release upload "$TAG" -R "$GH_REPO" --clobber "$f" ;;
		esac
	done
	for f in meta meta.conf meta.pkg packagesite.pkg data.pkg; do
		if [ -e "$dir/$f" ]; then
			gh release upload "$TAG" -R "$GH_REPO" --clobber "$dir/$f"
		fi
	done
	# Then drop packages the catalogue no longer names.
	gh release view "$TAG" -R "$GH_REPO" --json assets --jq '.assets[].name' |
	while read -r name; do
		if [ ! -e "$dir/$name" ]; then
			gh release delete-asset "$TAG" "$name" -R "$GH_REPO" -y
		fi
	done
}

publish() {
	tmp=$(mktemp -d)
	scp -q "$here/origins.sh" "$here/pkg-repo.sh" "$BUILD_HOST:$BUILD_DIR/"
	ssh "$BUILD_HOST" "cd $BUILD_DIR && sudo sh pkg-repo.sh build"
	scp -q "$BUILD_HOST:$OUT/*" "$tmp/"
	upload "$tmp"
	rm -rf "$tmp"
}

case ${1:-} in
keygen) keygen ;;
build) build ;;
upload) upload "${2:?usage: pkg-repo.sh upload <dir>}" ;;
publish) publish ;;
*)
	echo "usage: pkg-repo.sh keygen | build | upload <dir> | publish" >&2
	exit 1
	;;
esac
