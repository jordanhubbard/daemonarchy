#!/bin/sh
# Refuse an image whose closure feed cannot do its job (PKG-002).
#
# The installer prefers the signed upstream snapshot hosted as GitHub release
# feeds; pkg.FreeBSD.org is only the fallback. Before an ISO is built from a
# release, this checks that the feed is real: every shard answers, pkg accepts
# its signed catalogue against the release's public key, and the installer's
# roots resolve from the ISO's packages, our application feed and the shards
# alone, with pkg.FreeBSD.org disabled. Run on a FreeBSD build host. Nothing is
# installed or fetched beyond catalogues.
#
#   ISO_REPO=dir PUBKEY=file MIRROR_URLS="url ..." ABI=FreeBSD:16:amd64 \
#       [DEPENDENCIES_URL=url] [EXTRA_ROOTS="name ..."] scripts/check-closure-feed.sh

set -eu

: "${ISO_REPO:?the ISO's package repository directory}"
: "${PUBKEY:?the release's public key}"
: "${MIRROR_URLS:?the closure feed shard URLs}"
: "${ABI:?the package ABI}"

fail() { echo "closure feed refused: $*" >&2; exit 1; }

[ -s "$PUBKEY" ] || fail "public key $PUBKEY is missing"
[ -d "$ISO_REPO/All" ] || fail "ISO repository $ISO_REPO/All is missing"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/repos" "$work/root" "$work/db" "$work/cache"

printf 'FreeBSD: { enabled: no }\n' >"$work/repos/FreeBSD.conf"
cat >"$work/repos/iso.conf" <<EOF
Daemonarchy: {
  url: "file://$ISO_REPO",
  signature_type: "none",
  priority: 10,
  enabled: yes
}
EOF
if [ -n "${DEPENDENCIES_URL:-}" ]; then
	cat >"$work/repos/dependencies.conf" <<EOF
Daemonarchy-Dependencies: {
  url: "$DEPENDENCIES_URL",
  signature_type: "pubkey",
  pubkey: "$PUBKEY",
  priority: 9,
  enabled: yes
}
EOF
fi
number=0
for url in $MIRROR_URLS; do
	case "$url" in
	https://github.com/jordanhubbard/daemonarchy/releases/download/packages-16-*-?*) ;;
	*) fail "$url is not one of our release feeds" ;;
	esac
	fetch -q -T 30 -o /dev/null "$url/meta.conf" || fail "shard $url does not answer"
	number=$((number + 1))
	cat >"$work/repos/mirror$number.conf" <<EOF
Daemonarchy-Mirror-$number: {
  url: "$url",
  signature_type: "pubkey",
  pubkey: "$PUBKEY",
  priority: 5,
  enabled: yes
}
EOF
done
[ "$number" -gt 0 ] || fail "no shard URLs"

pkg_run() {
	env ASSUME_ALWAYS_YES=yes IGNORE_OSVERSION=yes pkg -r "$work/root" -o REPOS_DIR="$work/repos" \
	    -o ABI="$ABI" -o PKG_DBDIR="$work/db" -o PKG_CACHEDIR="$work/cache" "$@"
}

# pkg checks each catalogue's signature against the key while updating.
pkg_run update -f >"$work/update.log" 2>&1 || {
	tail -n 12 "$work/update.log" >&2
	fail "a shard's catalogue is unsigned, signed with another key, or unreadable"
}

# The roots the installer resolves: the fixed set, plus every GPU, Wi-Fi and
# firmware package the ISO carries (its own packages need their dependencies too).
roots="pkg bash sudo daemonarchy octopkg wifi-firmware-kmod xwayland vulkan-loader mesa-dri ${EXTRA_ROOTS:-}"
# chromium has no aarch64 package: the installer selects epiphany there instead.
case ${ARCH:-amd64} in aarch64) roots="$roots epiphany" ;; *) roots="$roots chromium" ;; esac
for file in "$ISO_REPO"/All/*.pkg; do
	name=$(pkg query -F "$file" '%n')
	case "$name" in
	drm-612-kmod | nvidia-driver | nvidia-kmod | nvidia-drm-612-kmod | linux-nvidia-libs | if_brcmfmac-kmod | gpu-firmware-* | wifi-firmware-*)
		roots="$roots $name" ;;
	esac
done
# shellcheck disable=SC2086
pkg_run install -n -y $roots >"$work/plan.log" 2>&1 || {
	tail -n 20 "$work/plan.log" >&2
	fail "the installer's roots do not resolve without pkg.FreeBSD.org"
}
grep -q 'Number of packages to be installed' "$work/plan.log" || fail "the dry run planned nothing"
count=$(sed -n 's/^Number of packages to be installed: //p' "$work/plan.log" | head -n 1)
echo "closure feed accepted: $number shard(s), $count packages resolve with pkg.FreeBSD.org disabled"
