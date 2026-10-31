#!/bin/sh
# Sign the aarch64 application feed and checkout feed for a release in one key window, on the build VM (mudflap).
#
#   feeds-arm64-run.sh KEYFILE EXPECTED_SHA256
#
# KEYFILE must be a file on a tmpfs mounted at /var/keytmp-feed (memory only, swap off). The key is
# never read, hashed or printed here: it is passed by path to `pkg repo`, which signs with it. The
# hash the operator's command compared on both sides arrives as EXPECTED_SHA256 and is only logged.
# The key file is removed and the tmpfs unmounted on every exit path, success or failure.
#
# Before signing, every payload is hashed against its manifest (the arm64 worker's), and no feed may
# already hold a catalogue. After signing, the payloads are hashed again (pkg repo must not change
# them) and exactly four new files per feed must exist. Each catalogue is then verified the way a
# client does, against the pinned public key, under a repository name used once.
# Log: $R/sign-feeds-arm64.log.  The SIGN_* variables exist for the TEST=1 mechanics test.
set -eu
KEY=${1:?key file}
WANT=${2:?expected sha256}
R=${SIGN_ROOT:?SIGN_ROOT: where arm64-ingest.sh put the unsigned feeds and manifests}
MNT=${SIGN_MNT:-/var/keytmp-feed}
LOCK=/var/run/keywindow.lock
LOG=${SIGN_LOG:-$R/sign-feeds-arm64.log}
PUB=${SIGN_PUB:?SIGN_PUB: the public key the installer pins (keys/pkg-repo-1.3.1.pub), on this host}
APP=${SIGN_APP:-$R/app-feed}
CHK=${SIGN_CHK:-$R/checkout-feed}
APPMAN=${SIGN_APPMAN:-$R/manifest-app.sha256}
CHKMAN=${SIGN_CHKMAN:-$R/manifest-checkout.sha256}
ABI=${SIGN_ABI:-FreeBSD:16:aarch64}
REL=${SIGN_RELEASE:?SIGN_RELEASE: the release, X.Y.Z}                       # the release the feeds are for; the names below are labels for the log and checks:
APPNAME=${SIGN_APPNAME:-packages-16-aarch64-$REL}   # the catalogue itself holds no tag, so signing does not depend on it
CHKNAME=${SIGN_CHKNAME:-checkouts-16-aarch64-$REL}
CATS="meta meta.conf packagesite.pkg data.pkg"

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
log "sign-feeds-arm64 start; key sha256 compared on both sides by the caller: $WANT"
# The window is exclusive: one key at a time on this VM.
mkdir "$LOCK" 2>/dev/null || { log "another key window holds $LOCK"; trap - EXIT; rm -f "$KEY"; exit 1; }

# The key must be in memory only: a tmpfs of ours, mode 0700, and no swap.
case $KEY in "$MNT"/*) ;; *) log "key file is not under $MNT"; exit 1 ;; esac
mount | grep -q "^tmpfs on $MNT (tmpfs" || { log "$MNT is not a tmpfs"; exit 1; }
[ -z "$(swapinfo 2>/dev/null | sed 1d)" ] || { log "swap is on"; exit 1; }
[ -f "$KEY" ] && [ -s "$KEY" ] || { log "no key file"; exit 1; }
[ "$(stat -f %Lp "$KEY")" = 400 ] || [ "$(stat -f %Lp "$KEY")" = 600 ] || { log "key file mode must be 0400 or 0600"; exit 1; }
[ -f "$PUB" ] || { log "missing the public key $PUB"; exit 1; }

# payload_ok DIR MANIFEST: every file in DIR (catalogue files excluded) is listed with its hash, and nothing else is.
payload_ok() {
  [ -d "$1" ] && [ -f "$2" ] || { log "missing $1 or $2"; return 1; }
  ( cd "$1" && ls | grep -vE '^(meta|meta\.conf|packagesite\.pkg|data\.pkg)$' | sort | while IFS= read -r f; do
      printf '%s %s\n' "$(sha256 -q "$f")" "$f"; done ) >"$1.now.$$"
  sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' "$2" | sort -k2 >"$1.man.$$"
  if cmp -s "$1.now.$$" "$1.man.$$"; then rm -f "$1.now.$$" "$1.man.$$"; return 0; fi
  log "payload of $1 differs from $2: $(diff "$1.now.$$" "$1.man.$$" | head -3 | tr '\n' ' ')"
  rm -f "$1.now.$$" "$1.man.$$"; return 1
}

for pair in "$APP:$APPMAN" "$CHK:$CHKMAN"; do
  dir=${pair%%:*}; man=${pair#*:}
  [ -z "$(ls "$dir" 2>/dev/null | grep -E '^(meta|meta\.conf|packagesite\.pkg|data\.pkg)$')" ] || { log "$dir is already signed or holds catalogue files"; exit 1; }
  payload_ok "$dir" "$man" || exit 1
  log "payload of $dir matches $(basename "$man") ($(ls "$dir" | wc -l | tr -d ' ') files, $(ls -l "$dir" | awk 'NR>1{s+=$5} END{print s}') bytes)"
done

sign() { # dir name
  log "signing $2 ($(ls "$1" | grep -c '\.pkg$') package files)"
  pkg repo -q "$1" "$KEY" >/dev/null
  for f in $CATS; do
    [ -f "$1/$f" ] || { log "pkg repo wrote no $f in $1"; exit 1; }
    log "  $2/$f $(sha256 -q "$1/$f") $(stat -f %z "$1/$f") bytes"
  done
}
sign "$APP" "$APPNAME"
sign "$CHK" "$CHKNAME"

# The key is not needed any more: remove it before anything else runs.
rm -f "$KEY"
log "key file removed before verification"

# Signing must change nothing but add exactly the catalogue.
for pair in "$APP:$APPMAN" "$CHK:$CHKMAN"; do
  dir=${pair%%:*}; man=${pair#*:}
  payload_ok "$dir" "$man" || { log "pkg repo changed the payload of $dir"; exit 1; }
  count=$(ls "$dir" | wc -l | tr -d ' ')
  want=$(( $(sed -E 's/^[0-9a-f]{64} +\*?//' "$man" | wc -l | tr -d ' ') + 4 ))
  [ "$count" = "$want" ] || { log "$dir holds $count files, expected $want (manifest + four catalogue files)"; exit 1; }
done
log "payloads unchanged; exactly four catalogue files added per feed"

# Verify the way a client does: pkg with the pinned public key, on a throwaway database.
verify() { # dir name abi
  # pkg exits 0 even on "Invalid signature, removing repository", so read what it says. Each check has
  # its own repository name: pkg caches a repository's catalogue and would answer "up to date" next time.
  t=$(mktemp -d)
  mkdir -p "$t/repos"
  name=feedcheck$(od -An -N6 -tx1 /dev/urandom | tr -d " \n")   # unique per check: pkg caches a repository by name
  cat >"$t/repos/$name.conf" <<EOF
$name: {
  url: "file://$1",
  signature_type: "pubkey",
  pubkey: "$PUB",
  enabled: yes
}
EOF
  env IGNORE_OSVERSION=yes pkg -o REPOS_DIR="$t/repos" -o ABI="$3" update -f -r "$name" >"$t/out" 2>&1 || true
  rm -rf "/var/db/pkg/repos/$name"
  if grep -q 'Invalid signature' "$t/out" || ! grep -q "$name repository update completed" "$t/out"; then
    log "  $2 DOES NOT VERIFY: $(tail -3 "$t/out" | tr '\n' ' ')"; rm -rf "$t"; exit 1
  fi
  log "  $2 verifies with the pinned public key: $(grep 'packages processed' "$t/out" | tail -1)"
  rm -rf "$t"
}
# The application feed must be aarch64. The checkout feed holds architecture-independent source and ports data that is
# labelled with the amd64 ABI in every release (1.4.1 included), so it is verified with the ABI its own packages declare.
chk_abi=${SIGN_CHKABI:-$(tar -xOf "$CHK/packagesite.pkg" packagesite.yaml | head -1 | sed -n 's/.*"abi":"\([^"]*\)".*/\1/p')}
[ -n "$chk_abi" ] || { log "cannot read the ABI the checkout feed declares"; exit 1; }
log "verifying $APPNAME as $ABI and $CHKNAME as $chk_abi (the ABI its packages declare)"
verify "$APP" "$APPNAME" "$ABI"
verify "$CHK" "$CHKNAME" "$chk_abi"

# One list of the catalogue hashes for the report and the copy-back.
: >"$R/catalogue-hashes.txt" 2>/dev/null || true
for d in "$APP" "$CHK"; do for f in $CATS; do printf '%s %s %s\n' "$(sha256 -q "$d/$f")" "$(stat -f %z "$d/$f")" "$(basename "$d")/$f"; done; done | tee -a "$R/catalogue-hashes.txt" >>"$LOG"
log "both feeds signed and verified"
