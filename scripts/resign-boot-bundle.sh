#!/usr/local/bin/bash
# Regenerate the Secure Boot module inventory for a rebuilt package set and, only if it
# changed, re-sign the boot bundle. Run as root on the builder after
# `build-release-packages.sh bulk`, before the ISO is built.
#
#   resign-boot-bundle.sh check   inventory for the new set vs the current one (exit 1 if different)
#   resign-boot-bundle.sh sign    check, then rebuild the boot tree and bundle if different
#
# The boot manifest the bundle signs carries the module hashes, so a rebuilt module that
# is not bit-identical to the one in the current inventory invalidates the old bundle.
# The signing key and the private firmware stage stay where they are; nothing private
# enters the public bundle (the script refuses if it finds any).
set -euo pipefail

S=${S:-/usr/daemonarchy/sb16}                           # Secure Boot work dir (build/, boot-tree/, product/)
CACHE=${CACHE:-/usr/daemonarchy/rev2-20261030/inputs/source-sets}
PACKAGES=${PACKAGES:?PACKAGES: the new package directory (.../All)}
REV=${REV:?REV: the source revision (40 hex)}
RELEASE=${RELEASE:-1.4.1}
OSVERSION=${OSVERSION:-1600029}
PY=${PY:-/usr/local/bin/python3.12}
FW=${FW:-/usr/daemonarchy/firmware-policy-guest-private-20261023/apple}
CERT=${CERT:-/usr/daemonarchy/boot-replacement-candidate-public-20261024/daemonarchy-1.3.1.pem}
KEY=${KEY:-/usr/local/etc/daemonarchy/boot-replacement-candidate-20261024.key}
P=$S/product/secureboot
B=$S/build
ROOT=$S/boot-tree
INV=$S/module-inventory.json
BUNDLE=$S/daemonarchy-$RELEASE-boot.txz

[ -d "$PACKAGES" ] || { echo "no package directory $PACKAGES" >&2; exit 1; }
[ -f "$B/build.json" ] || { echo "no secure boot build receipt at $B/build.json" >&2; exit 1; }

check() {
  local new
  new=$(mktemp)
  $PY "$P/module-inventory.py" "$PACKAGES" --source-revision "$REV" --osversion "$OSVERSION" >"$new"
  if [ -f "$INV" ] && cmp -s "$INV" "$new"; then
    echo "module inventory unchanged ($(wc -l <"$INV" | tr -d ' ') lines): the current boot bundle stays valid"
    rm -f "$new"
    return 0
  fi
  echo "module inventory changed: the boot bundle must be re-signed"
  mv "$new" "$INV.new"
  return 1
}

sign() {
  if check; then return 0; fi
  [ -d "$FW" ] && [ -f "$CERT" ] && [ -f "$KEY" ] || { echo 'missing firmware stage, certificate or key' >&2; exit 1; }
  umask 077
  local stamp
  stamp=$(date +%Y%m%d%H%M%S)
  # prepare-boot-tree.sh needs a fresh staging root: keep the previous one beside it.
  if [ -e "$ROOT" ]; then mv "$ROOT" "$ROOT.before-$stamp"; fi
  /bin/sh "$P/prepare-boot-tree.sh" "$CACHE" "$B" "$ROOT"
  mv "$INV.new" "$INV"
  $PY "$S/product/scripts/import-apple-bcm4364-firmware.py" --verify-stage --model MacBookPro16,1 --destination "$FW"
  $PY "$P/sign-boot-tree.py" "$ROOT" --loader "$B/loader_lua.efi" --build-receipt "$B/build.json" \
      --kernel-path kernel.secure/kernel --module-inventory "$INV" --firmware-stage "$FW" --certificate "$CERT" --key "$KEY"
  $PY "$P/bundle.py" "$ROOT" --out "$BUNDLE.new" --release "$RELEASE" --build-receipt "$B/build.json" --certificate "$CERT" --key "$KEY"
  $PY "$P/maintenance.py" verify "$BUNDLE.new" --signature "$BUNDLE.new.sig" --certificate "$CERT" --root "$ROOT"
  if tar -tf "$BUNDLE.new" | grep -E 'firmware/|\.key$|\.pem$'; then
    echo 'PRIVATE MATERIAL IN PUBLIC BUNDLE' >&2
    exit 1
  fi
  if [ -f "$BUNDLE" ]; then
    cp -p "$BUNDLE" "$BUNDLE.before-$stamp"
    cp -p "$BUNDLE.sig" "$BUNDLE.sig.before-$stamp" 2>/dev/null || true
  fi
  mv "$BUNDLE.new" "$BUNDLE"
  mv "$BUNDLE.new.sig" "$BUNDLE.sig"
  umask 022
  ls -l "$BUNDLE" "$BUNDLE.sig"
}

case ${1:-} in
  check) check ;;
  sign) sign ;;
  *) sed -n '2,12p' "$0" >&2; exit 2 ;;
esac
