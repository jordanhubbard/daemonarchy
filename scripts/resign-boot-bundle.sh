#!/usr/local/bin/bash
# Regenerate the Secure Boot module inventory for a rebuilt package set and, only if it
# changed, re-sign the boot bundle. Run as root on the builder after
# `build-release-packages.sh bulk`, before the ISO is built.
#
#   resign-boot-bundle.sh check     inventory for the new set vs the current one (exit 1 if different)
#   resign-boot-bundle.sh sign      check, then rebuild the boot tree and bundle if different
#   resign-boot-bundle.sh rebundle  new release label over the already signed boot tree: PRIOR=<bundle> RELEASE=X.Y.Z
#
# `sign` does nothing when the inventory is unchanged, so it cannot relabel a release. `rebundle` can: the signed
# `release` field of bundle.json must equal the release record's version (verify-release-assets.py checks it), and a
# rename changes no module. It re-runs only secureboot/bundle.py on the tree the PRIOR bundle was made from, so the
# one private-key operation is the detached signature over the new tar; the manifests and the signed loader do not
# change. It refuses unless the tree still matches PRIOR, never replaces an existing bundle, and checks that the new
# bundle differs from PRIOR only in `release` in bundle.json. It does not use PACKAGES or REV.
#
# The boot manifest the bundle signs carries the module hashes, so a rebuilt module that
# is not bit-identical to the one in the current inventory invalidates the old bundle.
# The signing key and the private firmware stage stay where they are; nothing private
# enters the public bundle (the script refuses if it finds any).
set -euo pipefail

S=${S:-/usr/daemonarchy/sb16}                           # Secure Boot work dir (build/, boot-tree/, product/)
CACHE=${CACHE:-/usr/daemonarchy/rev2-20261030/inputs/source-sets}
PACKAGES=${PACKAGES:-}                                  # check and sign: the new package directory (.../All)
REV=${REV:-}                                            # check and sign: the source revision (40 hex)
RELEASE=${RELEASE:-$(tr -d "[:space:]" <"$(dirname "$0")/../VERSION" 2>/dev/null || echo 1.5.0)}
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

[ -f "$B/build.json" ] || { echo "no secure boot build receipt at $B/build.json" >&2; exit 1; }

check() {
  [ -n "$PACKAGES" ] && [ -n "$REV" ] || { echo "PACKAGES (the new package directory, .../All) and REV (the 40-hex source revision) are required" >&2; exit 1; }
  [ -d "$PACKAGES" ] || { echo "no package directory $PACKAGES" >&2; exit 1; }
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

# sum256 FILE: the digest on the builder (sha256) and anywhere else (sha256sum).
sum256() { sha256 -q "$1" 2>/dev/null || sha256sum "$1" | cut -d' ' -f1; }

rebundle() {
  local prior=${PRIOR:?PRIOR: the previous signed bundle made from the current boot tree}
  case $RELEASE in [0-9]*.[0-9]*.[0-9]*) ;; *) echo "RELEASE must look like X.Y.Z, not $RELEASE" >&2; exit 1 ;; esac
  [ -f "$prior" ] && [ -f "$prior.sig" ] || { echo "no previous signed bundle $prior" >&2; exit 1; }
  [ -d "$ROOT" ] && [ -f "$CERT" ] && [ -f "$KEY" ] || { echo 'missing boot tree, certificate or key' >&2; exit 1; }
  [ ! -e "$BUNDLE" ] && [ ! -e "$BUNDLE.sig" ] || { echo "$BUNDLE already exists: preserve existing signed artifacts" >&2; exit 1; }
  [ ! -e "$BUNDLE.new" ] && [ ! -e "$BUNDLE.new.sig" ] || { echo "$BUNDLE.new exists: remove the leftover deliberately" >&2; exit 1; }
  # The boot tree must still be exactly what PRIOR was made from: otherwise a relabel is not enough.
  $PY "$P/maintenance.py" verify "$prior" --signature "$prior.sig" --certificate "$CERT" --root "$ROOT" >/dev/null \
    || { echo "the boot tree does not match $prior: a full re-sign is needed, not a relabel" >&2; exit 1; }
  umask 077
  trap 'rm -f "$BUNDLE.new" "$BUNDLE.new.sig"' EXIT
  $PY "$P/bundle.py" "$ROOT" --out "$BUNDLE.new" --release "$RELEASE" --build-receipt "$B/build.json" --certificate "$CERT" --key "$KEY"
  $PY "$P/maintenance.py" verify "$BUNDLE.new" --signature "$BUNDLE.new.sig" --certificate "$CERT" --root "$ROOT"
  if tar -tf "$BUNDLE.new" | grep -E 'firmware/|\.key$|\.pem$'; then
    echo 'PRIVATE MATERIAL IN PUBLIC BUNDLE' >&2
    exit 1
  fi
  # Only bundle.json may differ from PRIOR, and only in `release`.
  local t differ
  t=$(mktemp -d)
  mkdir "$t/old" "$t/new"
  tar -xf "$prior" -C "$t/old"
  tar -xf "$BUNDLE.new" -C "$t/new"
  differ=$(cd "$t" && { diff -rq old new || true; } | sed -E 's/^Files old\/(.*) and new\/.* differ$/\1/' | tr '\n' ' ')
  [ "$differ" = "bundle.json " ] || { echo "unexpected differences from $prior: $differ" >&2; rm -rf "$t"; exit 1; }
  $PY -I - "$t/old/bundle.json" "$t/new/bundle.json" "$RELEASE" <<'PYEOF' || { rm -rf "$t"; exit 1; }
import json, sys
a, b = (json.load(open(path)) for path in sys.argv[1:3])
if b.get("release") != sys.argv[3]:
    sys.exit("the new bundle does not carry the requested release label")
a.pop("release"), b.pop("release")
if a != b:
    sys.exit("bundle.json differs beyond the release label")
PYEOF
  rm -rf "$t"
  mv "$BUNDLE.new" "$BUNDLE"
  mv "$BUNDLE.new.sig" "$BUNDLE.sig"
  trap - EXIT
  umask 022
  echo "relabelled $(basename "$prior") as $(basename "$BUNDLE"): only bundle.json differs, and only in release"
  echo "$(sum256 "$BUNDLE")  $(basename "$BUNDLE")"
  echo "$(sum256 "$BUNDLE.sig")  $(basename "$BUNDLE").sig"
}

case ${1:-} in
  check) check ;;
  sign) sign ;;
  rebundle) rebundle ;;
  *) sed -n '2,22p' "$0" >&2; exit 2 ;;
esac
