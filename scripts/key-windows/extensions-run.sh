#!/bin/sh
# Sign the 1.5.0 extension feeds (amd64 and aarch64) in one key window, on the build VM (mudflap).
#
#   extensions-run.sh KEYFILE EXPECTED_SHA256
#
# KEYFILE must be a file on a tmpfs mounted at /var/keytmp-ext (memory only, swap off). The key is passed by path to
# scripts/extension-bundle.py sign (openssl dgst -sha256 -sign); it is never read into a variable, copied or printed here.
# Only hashes are logged: the sha256 the operator's command compared on both sides, and the sha256 of the key's PUBLIC
# half in DER form, which must equal the pinned key's (67986b40...). The key file is removed and the tmpfs unmounted
# on every exit path.
#
# Before signing, each staged file is hashed against SHA256SUMS and no feed may hold a signature. After signing, the
# six original files per feed must be unchanged, exactly twelve files must exist per feed, and each feed is verified with
# the pinned public key the way the installer does (extension-bundle.py verify --feed NAME). Log: $ROOT/sign-ext.log.
# The SIGN_* variables exist for the TEST=1 mechanics test.
set -eu
KEY=${1:?key file}
WANT=${2:?expected sha256}
REL=${SIGN_RELEASE:?SIGN_RELEASE: the release, X.Y.Z}
R=${SIGN_ROOT:?SIGN_ROOT: the staged unsigned extension feeds}
TOOL=${SIGN_TOOL:?SIGN_TOOL: the repo checkout holding scripts/extension-bundle.py and the daemonarchy_visual package}
REUSE=${SIGN_REUSE:-$R/reusable-signatures}     # earlier signatures of bundles that did not change
MNT=${SIGN_MNT:-/var/keytmp-ext}
LOCK=/var/run/keywindow.lock
LOG=${SIGN_LOG:-$R/sign-ext.log}
PUB=${SIGN_PUB:?SIGN_PUB: the public key the installer pins (keys/pkg-repo-1.3.1.pub), on this host}
PUBDER=${SIGN_PUBDER:?SIGN_PUBDER: DER sha256 of the public half of the pinned key}
PY=${SIGN_PY:-/usr/local/bin/python3.12}
FEEDS="extensions-16-amd64-$REL extensions-16-aarch64-$REL"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }
cleanup() {
  status=$?
  rm -f "$KEY" 2>/dev/null || true
  if mount | grep -q " on $MNT "; then umount "$MNT" 2>/dev/null || umount -f "$MNT" 2>/dev/null || true; fi
  if mount | grep -q " on $MNT "; then log "CLEANUP FAILED: $MNT is still mounted"; else log "cleanup: key file removed, $MNT unmounted"; fi
  rmdir "$LOCK" 2>/dev/null || true
  log "exit status $status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

mkdir -p "$(dirname "$LOG")"
log "sign-ext start (release $REL); key sha256 compared on both sides by the caller: $WANT"
# The window is exclusive: one key at a time on this VM.
mkdir "$LOCK" 2>/dev/null || { log "another key window holds $LOCK"; trap - EXIT; rm -f "$KEY"; exit 1; }

# The key must be in memory only: a tmpfs of ours, and no swap.
case $KEY in "$MNT"/*) ;; *) log "key file is not under $MNT"; exit 1 ;; esac
mount | grep -q "^tmpfs on $MNT (tmpfs" || { log "$MNT is not a tmpfs"; exit 1; }
[ -z "$(swapinfo 2>/dev/null | sed 1d)" ] || { log "swap is on"; exit 1; }
[ -f "$KEY" ] && [ -s "$KEY" ] || { log "no key file"; exit 1; }
[ "$(stat -f %Lp "$KEY")" = 400 ] || [ "$(stat -f %Lp "$KEY")" = 600 ] || { log "key file mode must be 0400 or 0600"; exit 1; }
[ -f "$PUB" ] || { log "missing the public key $PUB"; exit 1; }

# The private key must belong to the pinned public key: compare the DER hash of the PUBLIC halves. Only hashes are printed.
pin=$(openssl pkey -pubin -in "$PUB" -pubout -outform DER 2>/dev/null | sha256 -q)
[ "$pin" = "$PUBDER" ] || { log "the pinned public key file hashes to $pin, expected $PUBDER: refusing"; exit 1; }
have=$(openssl pkey -in "$KEY" -pubout -outform DER 2>/dev/null | sha256 -q)
log "public half of the key (DER sha256): $have; pinned: $pin"
[ "$have" = "$PUBDER" ] || { log "the key does not belong to the pinned public key: refusing"; exit 1; }

# Inputs: the staged files must be exactly what was staged, and unsigned.
check_staged() { # label
  bad=0; n=0
  while read -r h f; do
    n=$((n + 1)); g=$(sha256 -q "$R/$f" 2>/dev/null || true)
    [ "$g" = "$h" ] || { log "  $1: $f differs from SHA256SUMS"; bad=$((bad + 1)); }
  done < "$R/SHA256SUMS"
  [ "$n" = 12 ] && [ "$bad" = 0 ] || { log "$1: $n files listed, $bad differ"; return 1; }
  log "$1: all $n staged files match SHA256SUMS"
}
for d in $FEEDS; do
  [ -d "$R/$d" ] || { log "missing $R/$d"; exit 1; }
  [ "$(ls "$R/$d" | wc -l | tr -d ' ')" = 6 ] || { log "$d does not hold exactly 6 files"; exit 1; }
  [ -z "$(ls "$R/$d" | grep '\.sig$')" ] || { log "$d already holds signatures"; exit 1; }
done
check_staged "before signing" || exit 1

for d in $FEEDS; do
  log "signing $d"
  "$PY" -I "$TOOL/scripts/extension-bundle.py" sign "$R/$d" --key "$KEY" >>"$LOG" 2>&1 || { log "extension-bundle.py sign failed for $d"; exit 1; }
done
# The key is not needed any more: remove it before anything else runs.
rm -f "$KEY"
log "key file removed before verification"

# Signing may add .sig files only.
check_staged "after signing (original files unchanged)" || exit 1
for d in $FEEDS; do
  count=$(ls "$R/$d" | wc -l | tr -d ' ')
  sigs=$(ls "$R/$d" | grep -c '\.sig$' || true)
  [ "$count" = 12 ] && [ "$sigs" = 6 ] || { log "$d holds $count files ($sigs signatures), expected 12 (6)"; exit 1; }
  sizes=$(cd "$R/$d" && for s in *.sig; do stat -f %z "$s"; done | sort -u | tr '\n' ' ')
  log "$d: 12 files (6 payload + 6 signatures); signature size(s): $sizes"
done

# Verify the way the installer does: the pinned public key, the feed name, every bundle's size, hash and signature.
for d in $FEEDS; do
  out=$("$PY" -I "$TOOL/scripts/extension-bundle.py" verify "$R/$d" --pubkey "$PUB" --feed "$d" 2>&1) || { log "  $d DOES NOT VERIFY: $(echo "$out" | tail -2 | tr '\n' ' ')"; exit 1; }
  log "  $d verifies with the pinned public key: $(echo "$out" | tail -1)"
done
# The verifier must be able to fail: a wrong feed name must be refused.
if "$PY" -I "$TOOL/scripts/extension-bundle.py" verify "$R/extensions-16-amd64-$REL" --pubkey "$PUB" --feed "extensions-16-amd64-9.9.9" >/dev/null 2>&1; then
  log "the verifier accepted a wrong feed name: its result cannot be trusted"; exit 1
fi
log "  control: a wrong feed name is refused"

# Cross-checks (informational): RSA PKCS#1 v1.5 is deterministic, so a bundle that did not change must come out with the
# signature published earlier, and a bundle shared by both feeds must have one signature.
for arch in amd64 aarch64; do
  [ -d "$REUSE/$arch" ] || continue
  for old in "$REUSE/$arch"/*.sig; do
    [ -f "$old" ] || continue
    new="$R/extensions-16-$arch-$REL/$(basename "$old")"
    if [ ! -f "$new" ]; then log "  $arch/$(basename "$old"): no such signature in the new feed"
    elif cmp -s "$old" "$new"; then log "  $arch/$(basename "$old" .sig): new signature identical to the earlier one"
    else log "  WARN $arch/$(basename "$old" .sig): new signature DIFFERS from the earlier one"; fi
  done
done
for sig in "$R/extensions-16-amd64-$REL"/*.sig; do
  other="$R/extensions-16-aarch64-$REL/$(basename "$sig")"
  [ -f "$other" ] && cmp -s "$sig" "$other" && log "  $(basename "$sig" .sig): one signature serves both feeds" || true
done

# One list of every file's hash for the report and the copy-back.
: >"$R/signed-hashes.txt"
for d in $FEEDS; do ( cd "$R" && for f in $d/*; do printf '%s %s %s\n' "$(sha256 -q "$f")" "$(stat -f %z "$f")" "$f"; done ) >>"$R/signed-hashes.txt"; done
log "wrote signed-hashes.txt ($(wc -l < "$R/signed-hashes.txt" | tr -d ' ') files)"
log "both extension feeds signed and verified"
