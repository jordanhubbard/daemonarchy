#!/bin/sh

# Build the Daemonarchy installer ISO with poudriere image.
#
# Prerequisites on the build host (run as root):
#   - a poudriere jail ($JAIL) made from the FreeBSD snapshot the ISO installs,
#     with its kernel and 32-bit libraries (kernel.txz/lib32.txz) extracted
#   - a ports tree ($PTREE) pinned to the commit of the official package set
#     plus the Omarchy ports, bulk-built with -b latest so only the Omarchy
#     ports and the GPU and Wi-Fi kernel modules are built locally
#
# The ISO carries the live installer, the snapshot's base and kernel sets,
# and a package repository with what pkg.FreeBSD.org does not publish (the
# Omarchy ports, and GPU modules built for this kernel). Everything else is
# fetched from pkg.FreeBSD.org during the install.

set -eu

JAIL=${JAIL:-16amd64}
PTREE=${PTREE:-omarchyiso}
SNAPSHOT_URL=${SNAPSHOT_URL:-https://download.freebsd.org/snapshots/amd64/16.0-CURRENT}
SET_CACHE_DIR=${SET_CACHE_DIR:-/var/cache/daemonarchy-iso}
OUTDIR=${OUTDIR:-/usr/local/poudriere/data/images}
ABI=${ABI:-FreeBSD:16:amd64}
ARCH=${ARCH:-amd64}

here=$(cd "$(dirname "$0")" && pwd)
CHECKOUT_CATALOG=${CHECKOUT_CATALOG:-$here/overlay/usr/local/share/daemonarchy-installer/checkouts.json}
packages=/usr/local/poudriere/data/packages/$JAIL-$PTREE
[ -n "$CHECKOUT_CATALOG" ] && [ -s "$CHECKOUT_CATALOG" ] || {
  echo 'Set CHECKOUT_CATALOG to the published, signed checkout repository catalogue' >&2
  exit 1
}
jq -e '.schema == 1 and (.trees.ports.depth >= 1) and (.trees.src.depth >= 1)' "$CHECKOUT_CATALOG" >/dev/null
stage=/var/tmp/daemonarchy-iso-stage
cache=$SET_CACHE_DIR

. "$here/origins.sh"

rm -rf "$stage"
mkdir -p "$stage" "$cache" "$OUTDIR"
cp -R "$here/overlay" "$stage/overlay"
if [ -n "${LIVE_EXTRA_OVERLAY:-}" ]; then
    [ -d "$LIVE_EXTRA_OVERLAY" ] || { echo 'LIVE_EXTRA_OVERLAY must be a directory' >&2; exit 1; }
    cp -R "$LIVE_EXTRA_OVERLAY/." "$stage/overlay/"
fi
share=$stage/overlay/usr/local/share/daemonarchy-installer
cp "$CHECKOUT_CATALOG" "$share/checkouts.json"

echo "==> Collecting the Omarchy package repository"
mkdir -p "$share/repo/All"
for pkgfile in "$packages"/All/*.pkg; do
	origin=$(pkg query -F "$pkgfile" '%o')
	case " $(echo $ISO_ORIGINS) " in
	*" $origin "*) cp "$pkgfile" "$share/repo/All/" ;;
	*)
		# GPU and Wi-Fi firmware modules, built for this kernel.
		case "$origin" in
		graphics/gpu-firmware-*-kmod | net/wifi-firmware-*-kmod | net/wifi-firmware-kmod)
			cp "$pkgfile" "$share/repo/All/" ;;
		esac
		;;
	esac
done
pkg repo -q "$share/repo" >/dev/null
echo "    $(ls "$share/repo/All" | wc -l | tr -d ' ') packages"
echo "$ABI" >"$share/ABI"

# Accounts the packages create, which the installer must not hand to a user.
for pkgfile in "$packages"/All/*.pkg; do
	pkg query -F "$pkgfile" '%U'
done | sort -u >"$share/reserved-users"
echo "    $(wc -l <"$share/reserved-users" | tr -d ' ') package accounts reserved"

echo "==> Taking the setup form from the omarchy package"
# Releases are numbered by the daemonarchy package's version (semantic
# versioning, Daemonarchy's own), without its epoch or port revision.
daemonarchy_pkg=$(ls "$share"/repo/All/daemonarchy-[0-9]*.pkg | head -n 1)
VERSION=$(pkg query -F "$daemonarchy_pkg" '%v' | sed -e 's/,[0-9]*$//' -e 's/_[0-9]*$//')
NAME=${NAME:-daemonarchy-$VERSION-$ARCH}
image=$(printf '%s' "$NAME" | tr -cd '[:alnum:]')
[ -n "$image" ] && [ "${#image}" -le 32 ] || {
    echo 'NAME must produce an alphanumeric ISO volume label of 1..32 characters' >&2; exit 1;
}
echo "$VERSION${PREVIEW_LABEL:+ ($PREVIEW_LABEL)}" >"$share/version"
echo "    Daemonarchy $VERSION"

omarchy_pkg=$(ls "$share"/repo/All/omarchy-[0-9]*.pkg | head -n 1)
extract=$(mktemp -d)
tar -xf "$omarchy_pkg" -C "$extract" \
	/usr/local/share/omarchy/install/provisioning/setup-form.sh \
	/usr/local/libexec/omarchy/compat/timedatectl \
	/usr/local/bin/omarchy-wifi-enterprise
# Same questions as the Omarchy ISO; only the suggested hostname differs.
sed -e "s/OMARCHY_HOSTNAME_DEFAULT='omarchy'/OMARCHY_HOSTNAME_DEFAULT='daemonarchy'/" \
	-e "s/(or return for 'omarchy')/(or return for 'daemonarchy')/" \
	"$extract/usr/local/share/omarchy/install/provisioning/setup-form.sh" >"$share/setup-form.sh"
mkdir -p "$share/compat"
cp "$extract/usr/local/libexec/omarchy/compat/timedatectl" "$share/compat/"
cp "$extract/usr/local/bin/omarchy-wifi-enterprise" "$share/omarchy-wifi-enterprise"
# Use the helper's actual interpreter dependency, rather than a moving Python
# default that could disagree with its package's rewritten shebang.
live_python=$(pkg query -F "$omarchy_pkg" '%dn' | awk '/^python3[0-9]+$/ { print }')
case "$live_python" in python3[0-9][0-9]) ;; *) echo 'Need one Python interpreter dependency for enterprise Wi-Fi' >&2; exit 1 ;; esac
chmod 0755 "$share/omarchy-wifi-enterprise"
rm -rf "$extract"

# Only public, already signed artifacts belong on the authoring worker/image.
# The private release key is never an input to this script.
if [ -n "${SECUREBOOT_BUNDLE:-}${SECUREBOOT_SIGNATURE:-}${SECUREBOOT_CERTIFICATE:-}" ]; then
    [ "$live_python" = python312 ] || { echo 'The verified boot helper requires Python 3.12' >&2; exit 1; }
    for input in "${SECUREBOOT_BUNDLE:-}" "${SECUREBOOT_SIGNATURE:-}" "${SECUREBOOT_CERTIFICATE:-}"; do
        [ -n "$input" ] && [ -s "$input" ] || { echo 'Set all three SECUREBOOT public artifact paths' >&2; exit 1; }
    done
    if grep -q 'PRIVATE KEY' "$SECUREBOOT_CERTIFICATE"; then
        echo 'SECUREBOOT_CERTIFICATE must contain public material only' >&2; exit 1
    fi
    mkdir -p "$share/secureboot"
    cp "$SECUREBOOT_BUNDLE" "$share/secureboot/bundle.txz"
    cp "$SECUREBOOT_SIGNATURE" "$share/secureboot/bundle.txz.sig"
    cp "$SECUREBOOT_CERTIFICATE" "$share/secureboot/certificate.pem"
    cp "$here/secureboot/maintenance.py" "$share/secureboot/maintenance.py"
fi

echo "==> Collecting the cached FreeBSD release sets"
# The sets must be the snapshot the jail was made from, since the packages and
# kernel modules on the image are built against it. $SNAPSHOT_URL always has
# the newest snapshot, so the sets are fetched once and kept. Use a separate
# SET_CACHE_DIR when moving to a new snapshot, retaining the older inputs.
SET_CACHE_DIR="$cache" SNAPSHOT_URL="$SNAPSHOT_URL" sh "$here/scripts/cache-release-sets.sh"
mkdir -p "$stage/overlay/usr/freebsd-dist"
for set in base kernel lib32; do
	cp "$cache/$set.txz" "$stage/overlay/usr/freebsd-dist/"
done
cp "$cache/MANIFEST" "$stage/overlay/usr/freebsd-dist/"
jail_root=$(poudriere jail -l -q | awk -v j="$JAIL" '$1 == j { print $NF }')
version() { awk '/^#define __FreeBSD_version/ { print $3 }'; }
jail_version=$(version <"$jail_root/usr/include/sys/param.h")
set_version=$(tar -xOf "$cache/base.txz" ./usr/include/sys/param.h | version)
if [ "$set_version" != "$jail_version" ]; then
	echo "base.txz is FreeBSD $set_version but jail $JAIL is $jail_version: empty $cache, or update the jail and rebuild the packages" >&2
	exit 1
fi

# The optional source checkout must describe the kernel in these release sets.
source_revision=$(jq -er '.trees.src.revision' "$CHECKOUT_CATALOG")
# Extract only the embedded build identity, not the build worker's running kernel.
kernel_identity=$(tar -xOf "$cache/kernel.txz" ./boot/kernel/kernel | strings | awk '/^FreeBSD .*main-n[0-9]+-[0-9a-f]+:/ { if (!found++) print }')
case "$kernel_identity" in
  *"-$(printf '%.12s' "$source_revision"):"*) ;;
  *) echo "Source checkout $source_revision does not match image kernel: $kernel_identity" >&2; exit 1 ;;
esac

# Keep NVIDIA and AMD/Intel on the same explicit DRM family. Validate every
# kernel module against the snapshot ABI before generating the image.
sh "$here/scripts/check-gpu-packages.sh" "$share/repo/All" "$set_version" >"$share/gpu-packages"

chmod 0755 "$stage"/overlay/usr/local/libexec/daemonarchy-installer/* \
	"$stage"/overlay/usr/local/bin/* "$stage"/overlay/usr/local/sbin/* \
	"$share/keymap" "$share/compat/timedatectl"

echo "==> Building the image"
printf '%s\n' bash gum jq ttfx tzupdate pkg wifi-firmware-kmod >"$stage/live-packages"
printf '%s\n' "$live_python" >>"$stage/live-packages"
# Trim only the live root. The untouched base.txz still installs a complete
# development system, and optional source/ports checkouts remain downloadable.
cp "$here/scripts/live-image-excludes" "$stage/exclude"

# poudriere image names (also the ISO volume label) are alphanumeric only.
rm -f "$OUTDIR/$NAME.iso.sha256"
poudriere image -t hybridiso -j "$JAIL" -p "$PTREE" -n "$image" \
	-h daemonarchy-installer -c "$stage/overlay" -f "$stage/live-packages" \
	-A "$here/live-post.sh" -X "$stage/exclude" -o "$OUTDIR"

iso=$OUTDIR/$NAME.iso
[ "$image" = "$NAME" ] || mv "$OUTDIR/$image.iso" "$iso"
sh "$here/scripts/check-image-size.sh" "$iso"
digest=$(sha256 -q "$iso")
printf '%s  %s\n' "$digest" "$(basename "$iso")" >"$iso.sha256"
ls -lh "$iso"
cat "$iso.sha256"
