#!/bin/sh
# Re-create the signed boot bundle under a new release label, on the build VM (mudflap), in one key window.
#
#   boot-relabel-run.sh RELEASE          e.g. 1.5.0
#
# scripts/resign-boot-bundle.sh only signs when the module inventory changed, so it cannot do this: the
# bundle's signed `release` field must equal the release record's version (scripts/verify-release-assets.py
# checks it), and a rename changes no module. This re-runs only secureboot/bundle.py on the ALREADY SIGNED
# boot tree, so the one private-key operation is the detached signature over the new tar. The boot manifest,
# runtime manifest and signed loader are not touched.
#
# The key must be a file on a tmpfs at /var/keytmp (memory only, swap off). It is passed by path, never read,
# hashed or printed here, and is removed, the tmpfs unmounted and swap restored on every exit path.
# Run it under the key-window lock: lockf -t 0 /var/run/keywindow.lock /root/key-windows/boot-relabel-run.sh 1.5.0
# The SB_* variables exist for the throwaway mechanics test (SB_TEST=1 also skips the tmpfs and swap checks).
set -eu
REL=${1:?release, e.g. 1.5.0}
S=${SB_S:-/usr/daemonarchy/sb16}
B=${SB_BUILD:-$S/build}
ROOT=${SB_ROOT:-$S/boot-tree}
CERT=${SB_CERT:-/usr/daemonarchy/boot-replacement-candidate-public-20261024/daemonarchy-1.3.1.pem}
KT=${SB_KEYMNT:-/var/keytmp}
KEY=${SB_KEY:-$KT/boot.key}
PRIOR=${SB_PRIOR:?SB_PRIOR: a bundle already signed from this very tree}
PY=${SB_PY:-/usr/local/bin/python3.12}
P=${SB_PRODUCT:-$S/product/secureboot}
OUT=$S/daemonarchy-$REL-boot.txz
LOG=${SB_LOG:?SB_LOG: where to write the log}
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

cleanup() {
  status=$?
  if [ "${SB_TEST:-}" != 1 ]; then
    [ ! -e "$KEY" ] || { rm -P "$KEY" 2>/dev/null || true; rm -f "$KEY"; }
    if mount | grep -q "^tmpfs on $KT (tmpfs"; then umount "$KT" 2>/dev/null || true; fi
    rmdir "$KT" 2>/dev/null || true
    swapon -a 2>/dev/null || true
  fi
  rm -f "$OUT.new" "$OUT.new.sig" 2>/dev/null || true
  log "cleanup: key $( [ -e "$KEY" ] && echo PRESENT || echo gone ), $KT mounts: $(mount | grep -c " on $KT " || true); exit status $status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

mkdir -p "$(dirname "$LOG")"
: >"$LOG"
log "sign-bundle start: release $REL; key sha256 (on VM): $(sha256 -q "$KEY" 2>/dev/null || echo none)"
case $REL in [0-9]*.[0-9]*.[0-9]*) ;; *) log "release must look like X.Y.Z"; exit 1 ;; esac
if [ "${SB_TEST:-}" != 1 ]; then
  mount | grep -q "^tmpfs on $KT (tmpfs" || { log "$KT is not a tmpfs"; exit 1; }
  [ -z "$(swapinfo 2>/dev/null | sed 1d)" ] || { log "swap is on"; exit 1; }
  [ "$(stat -f %Lp "$KEY")" = 400 ] || [ "$(stat -f %Lp "$KEY")" = 600 ] || { log "key file mode must be 0400 or 0600"; exit 1; }
fi
[ -f "$KEY" ] && [ -s "$KEY" ] || { log "no key file"; exit 1; }
[ ! -e "$OUT" ] && [ ! -e "$OUT.sig" ] || { log "$OUT already exists: preserve existing signed artifacts"; exit 1; }
[ -f "$PRIOR" ] && [ -f "$PRIOR.sig" ] || { log "no prior signed bundle $PRIOR"; exit 1; }

# The boot tree must still be exactly what the prior bundle was made from (so nothing needs signing but the bundle).
$PY "$P/maintenance.py" verify "$PRIOR" --signature "$PRIOR.sig" --certificate "$CERT" --root "$ROOT" >>"$LOG" 2>&1 \
  || { log "the boot tree does not match the prior bundle: a full re-sign is needed, not a re-label"; exit 1; }
log "boot tree matches the prior bundle $(basename "$PRIOR")"

$PY "$P/bundle.py" "$ROOT" --out "$OUT.new" --release "$REL" --build-receipt "$B/build.json" \
    --certificate "$CERT" --key "$KEY" >>"$LOG" 2>&1 || { log "bundle.py failed"; exit 1; }
rm -f "$KEY"
log "key file removed after signing"
$PY "$P/maintenance.py" verify "$OUT.new" --signature "$OUT.new.sig" --certificate "$CERT" --root "$ROOT" >>"$LOG" 2>&1 \
  || { log "the new bundle does not verify against the boot tree"; exit 1; }
if tar -tf "$OUT.new" | grep -E 'firmware/|\.key$|\.pem$'; then log "PRIVATE MATERIAL IN PUBLIC BUNDLE"; exit 1; fi

# Only bundle.json may differ from the prior bundle, and only in `release`.
t=$(mktemp -d)
mkdir "$t/old" "$t/new"
tar -xf "$PRIOR" -C "$t/old"; tar -xf "$OUT.new" -C "$t/new"
diffs=$(cd "$t" && diff -rq old new | sed -E 's/^Files old\/(.*) and new\/.* differ$/\1/' | tr '\n' ' ')
[ "$diffs" = "bundle.json " ] || { log "unexpected differences from the prior bundle: $diffs"; rm -rf "$t"; exit 1; }
rel_old=$($PY -I -c "import json,sys;print(json.load(open(sys.argv[1]))['release'])" "$t/old/bundle.json")
rel_new=$($PY -I -c "import json,sys;print(json.load(open(sys.argv[1]))['release'])" "$t/new/bundle.json")
other=$($PY -I -c "
import json,sys
a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2]))
a.pop('release'); b.pop('release'); print('same' if a==b else 'DIFFERENT')" "$t/old/bundle.json" "$t/new/bundle.json")
rm -rf "$t"
[ "$rel_new" = "$REL" ] && [ "$other" = same ] || { log "bundle.json differs beyond the release label ($rel_old -> $rel_new, rest $other)"; exit 1; }
log "only bundle.json differs, and only in release: $rel_old -> $rel_new"

mv "$OUT.new" "$OUT"; mv "$OUT.new.sig" "$OUT.sig"
log "created $(basename "$OUT") $(stat -f %z "$OUT") bytes sha256 $(sha256 -q "$OUT")"
log "created $(basename "$OUT").sig $(stat -f %z "$OUT.sig") bytes sha256 $(sha256 -q "$OUT.sig")"
log "PASS: re-labelled bundle signed and verified"
