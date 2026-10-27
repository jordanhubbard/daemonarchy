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

here=$(cd "$(dirname "$0")" && pwd)
# ARCH (amd64 or aarch64) selects every architecture default below. The build
# host must be a native worker of that architecture.
ARCH=${ARCH:-amd64}
. "$here/scripts/image-architecture.sh"
image_architecture_select "$ARCH"
JAIL=${JAIL:-$image_jail}
PTREE=${PTREE:-omarchyiso}
SNAPSHOT_URL=${SNAPSHOT_URL:-$image_snapshot_url}
SET_CACHE_DIR=${SET_CACHE_DIR:-$image_set_cache_dir}
# POUDRIERE_DATA must match the selected Poudriere configuration's own
# setting, so an isolated configuration reads its own package repository.
POUDRIERE_DATA=${POUDRIERE_DATA:-/usr/local/poudriere/data}
OUTDIR=${OUTDIR:-$POUDRIERE_DATA/images}
ABI=${ABI:-$image_abi}
[ "$ABI" = "$image_abi" ] || { echo "ABI $ABI does not match ARCH $ARCH" >&2; exit 1; }
POUDRIERE_ETC=${POUDRIERE_ETC:-}

poudriere_run() {
  if [ -n "$POUDRIERE_ETC" ]; then
    poudriere -e "$POUDRIERE_ETC" "$@"
  else
    poudriere "$@"
  fi
}

. "$here/overlay/usr/local/libexec/daemonarchy-installer/package-repository"
PACKAGE_REPOSITORY_TAG=${PACKAGE_REPOSITORY_TAG:-$image_package_repository_tag}
package_repository_tag_validate "$PACKAGE_REPOSITORY_TAG" "$ARCH"
PACKAGE_REPOSITORY_PUBLIC_KEY=${PACKAGE_REPOSITORY_PUBLIC_KEY:-}
if [ -n "$PACKAGE_REPOSITORY_PUBLIC_KEY" ]; then
    [ "$PACKAGE_REPOSITORY_TAG" != "$image_package_repository_tag" ] || {
        echo 'An alternate package key requires a versioned repository tag' >&2
        exit 1
    }
    [ -s "$PACKAGE_REPOSITORY_PUBLIC_KEY" ] || {
        echo 'PACKAGE_REPOSITORY_PUBLIC_KEY must name a nonempty public key' >&2
        exit 1
    }
    openssl pkey -pubin -in "$PACKAGE_REPOSITORY_PUBLIC_KEY" -noout >/dev/null 2>&1 || {
        echo 'PACKAGE_REPOSITORY_PUBLIC_KEY is not a valid public key' >&2
        exit 1
    }
fi
CHECKOUT_CATALOG=${CHECKOUT_CATALOG:-$here/overlay/usr/local/share/daemonarchy-installer/checkouts.json}
packages=$POUDRIERE_DATA/packages/$JAIL-$PTREE
[ -d "$packages/All" ] || { echo "No package repository at $packages; set POUDRIERE_DATA to the configuration's data directory" >&2; exit 1; }
[ -n "$CHECKOUT_CATALOG" ] && [ -s "$CHECKOUT_CATALOG" ] || {
  echo 'Set CHECKOUT_CATALOG to the published, signed checkout repository catalogue' >&2
  exit 1
}
jq -e '.schema == 1 and (.trees.ports.depth >= 1) and (.trees.src.depth >= 1)' "$CHECKOUT_CATALOG" >/dev/null
# I keep each attempt private and retain its staging for inspection on failure.
. "$here/scripts/iso-stage.sh"
stage=$(iso_stage_create)
echo "==> ISO staging: $stage"
cache=$SET_CACHE_DIR

. "$here/origins.sh"

mkdir -p "$cache" "$OUTDIR"
cp -R "$here/overlay" "$stage/overlay"
mkdir -p "$stage/overlay/boot/firmware"
if [ -n "${LIVE_EXTRA_OVERLAY:-}" ]; then
    [ -d "$LIVE_EXTRA_OVERLAY" ] || { echo 'LIVE_EXTRA_OVERLAY must be a directory' >&2; exit 1; }
    cp -R "$LIVE_EXTRA_OVERLAY/." "$stage/overlay/"
fi
share=$stage/overlay/usr/local/share/daemonarchy-installer
cp "$CHECKOUT_CATALOG" "$share/checkouts.json"
printf '%s\n' "$PACKAGE_REPOSITORY_TAG" >"$share/package-repository-tag"
if [ -n "$PACKAGE_REPOSITORY_PUBLIC_KEY" ]; then
    cp "$PACKAGE_REPOSITORY_PUBLIC_KEY" "$share/daemonarchy.pub"
fi

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
# The Apple T2 BCM4364 driver is an amd64-only (Intel Mac) port.
[ "$ARCH" != amd64 ] || ls "$share"/repo/All/if_brcmfmac-kmod-*.pkg >/dev/null 2>&1 || {
  echo 'The kernel-matched BCM4364 driver package is absent from this ISO build' >&2
  exit 1
}
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
# The installer's network check treats a clock earlier than the build as wrong.
echo "${SOURCE_DATE_EPOCH:-$(date -u +%s)}" >"$share/build-epoch"
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
cp "$here/scripts/import-apple-bcm4364-firmware.py" "$share/import-apple-bcm4364-firmware.py"
# Use the helper's actual interpreter dependency, rather than a moving Python
# default that could disagree with its package's rewritten shebang.
live_python=$(pkg query -F "$omarchy_pkg" '%dn' | awk '/^python3[0-9]+$/ { print }')
case "$live_python" in python3[0-9][0-9]) ;; *) echo 'Need one Python interpreter dependency for enterprise Wi-Fi' >&2; exit 1 ;; esac
live_python_exe=$(printf '%s' "$live_python" | sed -E 's/^python3([0-9][0-9])$/python3.\1/')
sed -i '' "1s@^.*\$@#!/usr/local/bin/$live_python_exe@" "$share/import-apple-bcm4364-firmware.py"
sed -i '' "1s@^.*\$@#!/usr/local/bin/$live_python_exe@" "$stage/overlay/usr/local/libexec/daemonarchy-installer/live-installer"
chmod 0755 "$share/omarchy-wifi-enterprise" "$share/import-apple-bcm4364-firmware.py"
rm -rf "$extract"

if [ -n "${TEST_LOADER_BUNDLE:-}" ]; then
    [ -z "${SECUREBOOT_BUNDLE:-}${SECUREBOOT_SIGNATURE:-}${SECUREBOOT_CERTIFICATE:-}" ] || {
        echo 'TEST_LOADER_BUNDLE cannot be combined with Secure Boot artifacts' >&2; exit 1;
    }
    /usr/local/bin/python3.12 "$here/scripts/test-loader.py" prepare \
        --bundle "$TEST_LOADER_BUNDLE" --destination "$share/test-loader"
fi

# Only public, already signed artifacts belong on the authoring worker/image.
# The private release key is never an input to this script.
if [ -n "${SECUREBOOT_BUNDLE:-}${SECUREBOOT_SIGNATURE:-}${SECUREBOOT_CERTIFICATE:-}" ]; then
    [ "$ARCH" = amd64 ] || { echo 'Secure Boot artifacts are built and qualified for amd64 only' >&2; exit 1; }
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
jail_root=$(poudriere_run jail -l -q | awk -v j="$JAIL" '$1 == j { print $NF }')
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
kernel_identity=$(tar -xOf "$cache/kernel.txz" ./boot/kernel/kernel | strings | awk '/^FreeBSD [^[:space:]]+ #[0-9]+ / { if (!found++) print }')
if ! bash -c 'source "$1"; checkout_kernel_identity_matches "$2" "$3"' \
    kernel-check "$here/overlay/usr/local/sbin/daemonarchy-checkouts" "$source_revision" "$kernel_identity"; then
  echo "Source checkout $source_revision does not match image kernel: $kernel_identity" >&2
  exit 1
fi

# Keep NVIDIA and AMD/Intel on the same explicit DRM family. Validate every
# kernel module against the snapshot ABI before generating the image.
sh "$here/scripts/check-gpu-packages.sh" "$share/repo/All" "$set_version" "$ABI" >"$share/gpu-packages"

chmod 0755 "$stage"/overlay/usr/local/libexec/daemonarchy-installer/* \
	"$stage"/overlay/usr/local/bin/* "$stage"/overlay/usr/local/sbin/* \
	"$share/keymap" "$share/compat/timedatectl"

echo "==> Building the image"
# shellcheck disable=SC2086 # the architecture's kernel driver packages, if any
printf '%s\n' bash gum tmux jq ttfx tzupdate pkg wifi-firmware-kmod $image_kernel_packages 7-zip >"$stage/live-packages"
printf '%s\n' "$live_python" >>"$stage/live-packages"
# The minimal live desktop (LIVE-001): compositor, seat and session bus, Mesa
# for the open drivers (GPU kernel modules come from the ISO repository at
# boot), a terminal, fonts, and GTK 3 with Python bindings for the graphical
# installer. GTK 4 is avoided: its media dependencies roughly double the set.
printf '%s\n' hyprland seatd dbus sudo mesa-dri foot dejavu gtk3 \
    "py$(printf '%s' "$live_python" | sed 's/^python//')-pygobject" >>"$stage/live-packages"
# poudriere image installs these from the bulk repository; name a missing
# one here instead of failing inside the image build.
while read -r live_package; do
    ls "$packages/All/$live_package"-[0-9]*.pkg >/dev/null 2>&1 || {
        echo "The live package $live_package is not in $packages; bulk-build ISO_ORIGINS and LIVE_ORIGINS" >&2
        exit 1
    }
done <"$stage/live-packages"
# Trim only the live root. The untouched base.txz still installs a complete
# development system, and optional source/ports checkouts remain downloadable.
cp "$here/scripts/live-image-excludes" "$stage/exclude"

# poudriere image names (also the ISO volume label) are alphanumeric only.
rm -f "$OUTDIR/$NAME.iso.sha256" "$OUTDIR/$NAME.iso.xz" "$OUTDIR/$NAME.iso.xz.sha256"
if [ "$image_type" = hybridiso ]; then
poudriere_run image -t hybridiso -j "$JAIL" -p "$PTREE" -n "$image" \
	-h daemonarchy-installer -c "$stage/overlay" -f "$stage/live-packages" \
	-A "$here/live-post.sh" -X "$stage/exclude" -o "$OUTDIR"
else
	# poudriere's ISO types embed x86 BIOS boot code. Build the same live root
	# as a tar image, then a UEFI-only hybrid ISO with this architecture's loader.
	poudriere_run image -t tar -j "$JAIL" -p "$PTREE" -n "$image" \
		-h daemonarchy-installer -c "$stage/overlay" -f "$stage/live-packages" \
		-A "$here/live-post.sh" -X "$stage/exclude" -o "$stage"
	rm -f "$OUTDIR/$image.iso"
	sh "$here/scripts/make-efi-iso.sh" "$stage/$image.txz" "$image" "$OUTDIR/$image.iso" \
		"$stage/efi-iso" "$image_efi_boot_file"
fi

iso=$OUTDIR/$NAME.iso
[ "$image" = "$NAME" ] || mv "$OUTDIR/$image.iso" "$iso"
# The raw budget fails before compression; the published .xz is checked below.
sh "$here/scripts/check-image-size.sh" "$iso"
digest=$(sha256 -q "$iso")
printf '%s  %s\n' "$digest" "$(basename "$iso")" >"$iso.sha256"

# Releases publish the image xz-compressed with a checksum of the compressed
# bytes. Keep the raw image and its checksum for local VM QA and native evidence.
echo "==> Compressing the image"
xz -T0 -9 -k "$iso"
xz -t "$iso.xz"
if [ "$(xz -dc "$iso.xz" | sha256 -q)" != "$digest" ]; then
  echo "$iso.xz does not decompress to the built image" >&2
  exit 1
fi
sh "$here/scripts/check-image-size.sh" "$iso" "$iso.xz"
printf '%s  %s\n' "$(sha256 -q "$iso.xz")" "$(basename "$iso.xz")" >"$iso.xz.sha256"
ls -lh "$iso" "$iso.xz"
cat "$iso.sha256" "$iso.xz.sha256"
