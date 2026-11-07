#!/bin/sh
# Re-sign the boot bundle of a release whose kernel, modules or Secure Boot build changed, on the build VM (mudflap),
# in one key window. boot-relabel-run.sh only relabels and boot-full-run.sh refuses a changed module inventory; this one
# signs a new kernel.
#
#   boot-resign-run.sh RELEASE --freeze     no key: print the frozen inputs and the sha256 of that listing
#   boot-resign-run.sh RELEASE              in the key window: refuse unless the inputs still hash to SB_FREEZE, then run
#                                           scripts/resign-boot-bundle.sh sign and verify the result
#
# The frozen inputs are the Secure Boot build (receipt, policy kernel, loaders), the release's source sets, every product
# file the boot tree and the signing tools come from, the release certificate and the module inventory regenerated from
# the release's package set. The operator records the --freeze sha256 in key-windows.env when QA is done; any later
# change to an input refuses the window. The new bundle is daemonarchy-RELEASE-boot.txz, which must not exist yet;
# resign-boot-bundle.sh keeps the previous boot tree beside the new one. The key must be a file on a tmpfs at
# /var/keytmp (memory only, swap off); it is passed by path, never read or printed, and is removed, the tmpfs unmounted
# and swap restored on every exit path. Run under the key-window lock:
#   lockf -t 0 /var/run/keywindow.lock /root/key-windows/boot-resign-run.sh RELEASE
# The SB_* variables exist for the throwaway mechanics test (SB_TEST=1 skips the tmpfs and swap checks).
set -eu
LC_ALL=C; export LC_ALL
REL=${1:?release, X.Y.Z}
MODE=${2:-sign}
S=${SB_S:-/usr/daemonarchy/sb16}
CACHE=${SB_CACHE:?SB_CACHE: the release source sets (base.txz, kernel.txz, MANIFEST)}
PACKAGES=${SB_PACKAGES:?SB_PACKAGES: the release package directory (.../All)}
REV=${SB_REV:?SB_REV: the 40-hex source revision of the release}
CERT=${SB_CERT:-/usr/daemonarchy/boot-replacement-candidate-public-20261024/daemonarchy-1.3.1.pem}
FW=${SB_FW:-/usr/daemonarchy/firmware-policy-guest-private-20261023/apple}
KT=${SB_KEYMNT:-/var/keytmp}
KEY=${SB_KEY:-$KT/boot.key}
PY=${SB_PY:-/usr/local/bin/python3.12}
OSVERSION=${SB_OSVERSION:-1600029}
P=$S/product
BUNDLE=$S/daemonarchy-$REL-boot.txz
case $REL in [0-9]*.[0-9]*.[0-9]*) ;; *) echo "release must look like X.Y.Z" >&2; exit 1 ;; esac

# The frozen inputs, one "sha256 path" line each, in a fixed order.
freeze() {
  inv=$(mktemp)
  $PY "$P/secureboot/module-inventory.py" "$PACKAGES" --source-revision "$REV" --osversion "$OSVERSION" >"$inv"
  printf '%s %s\n' "$(sha256 -q "$inv")" "module-inventory(regenerated)"
  rm -f "$inv"
  for f in "$S/build/build.json" "$S/build/kernel" "$S/build/loader_lua.efi" "$S/build/loader_normal.efi" \
           "$CACHE/MANIFEST" "$CACHE/base.txz" "$CACHE/kernel.txz" "$CERT" \
           "$P/overlay/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua" \
           "$P/scripts/import-apple-bcm4364-firmware.py" "$P/scripts/resign-boot-bundle.sh"; do
    printf '%s %s\n' "$(sha256 -q "$f")" "$f"
  done
  find "$P/secureboot" -type f | sort | while IFS= read -r f; do printf '%s %s\n' "$(sha256 -q "$f")" "$f"; done
}

# The receipt must name this release's source and certificate.
receipt_ok() {
  [ "$(jq -r .base_source "$S/build/build.json")" = "$REV" ] || { echo "the Secure Boot build receipt is not for $REV"; return 1; }
  [ "$(jq -r .trust_anchor_sha256 "$S/build/build.json")" = "$(sha256 -q "$CERT")" ] || { echo "the Secure Boot build receipt names another certificate"; return 1; }
}

if [ "$MODE" = --freeze ]; then
  receipt_ok >&2
  listing=$(freeze)
  printf '%s\n' "$listing"
  echo "freeze sha256: $(printf '%s\n' "$listing" | sha256 -q)"
  exit 0
fi
[ "$MODE" = sign ] || { echo "unknown mode $MODE" >&2; exit 2; }

WANTFREEZE=${SB_FREEZE:?SB_FREEZE: the sha256 that --freeze printed when the inputs were frozen}
LOG=${SB_LOG:?SB_LOG: where to write the log}
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

cleanup() {
  status=$?
  if [ "${SB_TEST:-}" != 1 ]; then
    [ ! -e "$KEY" ] || { rm -P "$KEY" 2>/dev/null || true; rm -f "$KEY"; }
    if mount | grep -q "^tmpfs on $KT (tmpfs"; then umount "$KT" 2>/dev/null || true; fi
    rmdir "$KT" 2>/dev/null || true
    swapon -a 2>/dev/null || true
  else
    rm -f "$KEY"
  fi
  if [ "$status" != 0 ] && [ "${created:-0}" = 1 ]; then
    rm -f "$BUNDLE" "$BUNDLE.sig"; log "the new bundle was removed because a check failed"
  fi
  log "cleanup: key $( [ -e "$KEY" ] && echo PRESENT || echo gone ), $KT mounts: $(mount | grep -c " on $KT " || true); exit status $status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

mkdir -p "$(dirname "$LOG")"
: >"$LOG"
log "boot-resign start: release $REL, source $REV; key sha256 (on VM): $(sha256 -q "$KEY" 2>/dev/null || echo none)"
if [ "${SB_TEST:-}" != 1 ]; then
  mount | grep -q "^tmpfs on $KT (tmpfs" || { log "$KT is not a tmpfs"; exit 1; }
  [ -z "$(swapinfo 2>/dev/null | sed 1d)" ] || { log "swap is on"; exit 1; }
fi
[ -f "$KEY" ] && [ -s "$KEY" ] || { log "no key file"; exit 1; }
[ "$(stat -f %Lp "$KEY")" = 400 ] || [ "$(stat -f %Lp "$KEY")" = 600 ] || { log "key file mode must be 0400 or 0600"; exit 1; }
[ ! -e "$BUNDLE" ] && [ ! -e "$BUNDLE.sig" ] || { log "$BUNDLE already exists: a release's bundle is signed once"; exit 1; }

# 1. FREEZE: the inputs are exactly the ones recorded when QA finished.
r=$(receipt_ok) || { log "$r"; exit 1; }
listing=$(freeze)
got=$(printf '%s\n' "$listing" | sha256 -q)
printf '%s\n' "$listing" | while IFS= read -r l; do log "  input $l"; done
[ "$got" = "$WANTFREEZE" ] || { log "FREEZE: the inputs hash to $got, not the recorded $WANTFREEZE: refusing"; exit 1; }
log "inputs match the recorded freeze ($got)"
wantinv=$(printf '%s\n' "$listing" | awk '$2=="module-inventory(regenerated)"{print $1}')

# 2. Rebuild the tree, sign the manifest and loader, bundle and verify (scripts/resign-boot-bundle.sh sign).
created=1
env S="$S" CACHE="$CACHE" PACKAGES="$PACKAGES" REV="$REV" RELEASE="$REL" OSVERSION="$OSVERSION" PY="$PY" FW="$FW" CERT="$CERT" KEY="$KEY" \
  /usr/local/bin/bash "$P/scripts/resign-boot-bundle.sh" sign >>"$LOG" 2>&1 || { log "resign-boot-bundle.sh sign failed"; exit 1; }
rm -f "$KEY"
log "key file removed after signing"

# 3. What was made is what was frozen, and verifies.
[ -f "$BUNDLE" ] && [ -f "$BUNDLE.sig" ] || { log "nothing was signed: the inventory did not change, so this release needs a relabel, not a re-sign"; exit 1; }
[ "$(sha256 -q "$S/module-inventory.json")" = "$wantinv" ] || { log "the signed module inventory is not the frozen one"; exit 1; }
$PY "$P/secureboot/maintenance.py" verify "$BUNDLE" --signature "$BUNDLE.sig" --certificate "$CERT" --root "$S/boot-tree" >>"$LOG" 2>&1 \
  || { log "the new bundle does not verify against the new tree"; exit 1; }
if tar -tf "$BUNDLE" | grep -E 'firmware/|\.key$|\.pem$'; then log "PRIVATE MATERIAL IN PUBLIC BUNDLE"; exit 1; fi
t=$(mktemp -d)
tar -xf "$BUNDLE" -C "$t" bundle.json boot/manifest.certs boot/runtime.manifest.certs
[ "$(jq -r .release "$t/bundle.json")" = "$REL" ] || { rm -rf "$t"; log "the bundle does not carry release $REL"; exit 1; }
cmp -s "$t/boot/manifest.certs" "$CERT" && cmp -s "$t/boot/runtime.manifest.certs" "$CERT" || { rm -rf "$t"; log "the certificate in the bundle is not the release certificate"; exit 1; }
rm -rf "$t"
created=0
log "created $(basename "$BUNDLE") $(stat -f %z "$BUNDLE") bytes sha256 $(sha256 -q "$BUNDLE")"
log "created $(basename "$BUNDLE").sig $(stat -f %z "$BUNDLE.sig") bytes sha256 $(sha256 -q "$BUNDLE.sig")"
log "module inventory $(sha256 -q "$S/module-inventory.json"); certificate $(sha256 -q "$CERT")"
log "PASS: boot bundle re-signed for $REL from the frozen inputs and verified"
