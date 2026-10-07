#!/bin/sh

# Build the Daemonarchy installer ISO with poudriere image.
#
# Prerequisites on the build host (run as root):
#   - a poudriere jail ($JAIL) made from the FreeBSD snapshot the ISO installs,
#     with its kernel (kernel.txz) extracted into it
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
OUTDIR=${OUTDIR:-/usr/local/poudriere/data/images}
ABI=${ABI:-FreeBSD:16:amd64}
NAME=${NAME:-daemonarchy-$(date +%Y%m%d)}

here=$(cd "$(dirname "$0")" && pwd)
packages=/usr/local/poudriere/data/packages/$JAIL-$PTREE
stage=/var/tmp/daemonarchy-iso-stage
cache=/var/cache/daemonarchy-iso

. "$here/origins.sh"

rm -rf "$stage"
mkdir -p "$stage" "$cache" "$OUTDIR"
cp -R "$here/overlay" "$stage/overlay"
share=$stage/overlay/usr/local/share/daemonarchy-installer

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
omarchy_pkg=$(ls "$share"/repo/All/omarchy-[0-9]*.pkg | head -n 1)
extract=$(mktemp -d)
tar -xf "$omarchy_pkg" -C "$extract" \
	/usr/local/share/omarchy/install/provisioning/setup-form.sh \
	/usr/local/libexec/omarchy/compat/timedatectl
# Same questions as the Omarchy ISO; only the suggested hostname differs.
sed -e "s/OMARCHY_HOSTNAME_DEFAULT='omarchy'/OMARCHY_HOSTNAME_DEFAULT='daemonarchy'/" \
	-e "s/(or return for 'omarchy')/(or return for 'daemonarchy')/" \
	"$extract/usr/local/share/omarchy/install/provisioning/setup-form.sh" >"$share/setup-form.sh"
mkdir -p "$share/compat"
cp "$extract/usr/local/libexec/omarchy/compat/timedatectl" "$share/compat/"
rm -rf "$extract"

echo "==> Fetching the FreeBSD base and kernel sets"
fetch -q -o "$cache/MANIFEST" "$SNAPSHOT_URL/MANIFEST"
mkdir -p "$stage/overlay/usr/freebsd-dist"
for set in base kernel; do
	want=$(awk -v f="$set.txz" '$1 == f { print $2 }' "$cache/MANIFEST")
	if [ ! -f "$cache/$set.txz" ] || [ "$(sha256 -q "$cache/$set.txz")" != "$want" ]; then
		fetch -q -o "$cache/$set.txz" "$SNAPSHOT_URL/$set.txz"
	fi
	[ "$(sha256 -q "$cache/$set.txz")" = "$want" ] || { echo "$set.txz checksum mismatch" >&2; exit 1; }
	cp "$cache/$set.txz" "$stage/overlay/usr/freebsd-dist/"
done
cp "$cache/MANIFEST" "$stage/overlay/usr/freebsd-dist/"

chmod 0755 "$stage"/overlay/usr/local/libexec/daemonarchy-installer/* "$share/keymap" "$share/compat/timedatectl"

echo "==> Building the image"
printf '%s\n' bash gum jq ttfx tzupdate pkg wifi-firmware-kmod >"$stage/live-packages"
printf '%s\n' usr/src usr/lib/debug usr/tests usr/lib32 usr/libexec/ld-elf32.so.1 >"$stage/exclude"

# poudriere image names (also the ISO volume label) are alphanumeric only.
image=$(echo "$NAME" | tr -cd '[:alnum:]')
poudriere image -t hybridiso -j "$JAIL" -p "$PTREE" -n "$image" \
	-h daemonarchy-installer -c "$stage/overlay" -f "$stage/live-packages" \
	-A "$here/live-post.sh" -X "$stage/exclude" -o "$OUTDIR"

iso=$OUTDIR/$NAME.iso
[ "$image" = "$NAME" ] || mv "$OUTDIR/$image.iso" "$iso"
sha256 -r "$iso" | sed "s|$OUTDIR/||" >"$iso.sha256"
ls -lh "$iso"
cat "$iso.sha256"
