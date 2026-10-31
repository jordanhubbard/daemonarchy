#!/bin/sh
# Sign the aarch64 CHECKOUT feed alone in one key window, on the build VM. The application feed is not touched.
#
#   checkout-arm64-run.sh KEYFILE EXPECTED_SHA256
#
# For a checkout feed that is rebuilt after the application feed was signed (for example with the right ABI label).
# KEYFILE must be a file on a tmpfs mounted at /var/keytmp-feed (memory only, swap off). The key is never read, hashed
# or printed here: it is passed by path to `pkg repo`. The hash the operator's command compared on both sides arrives
# as EXPECTED_SHA256 and is only logged. The key file is removed and the tmpfs unmounted on every exit path.
#
# Everything is refused BEFORE the key is used unless the staged feed is exactly what is expected:
#   - no catalogue file is present yet, and every payload file matches its manifest;
#   - every package declares exactly SIGN_ABI (default FreeBSD:16:aarch64) in its own manifest: pkg refuses a
#     repository whose packages declare another ABI ("wrong architecture"), so a mislabelled feed installs fine and
#     fails the first time a user chooses a checkout. This is the rule scripts/check-checkout-feed-abi.sh applies to
#     the signed catalogue, applied to the packages before signing and to the catalogue after;
#   - checkouts.json names the release the feed will be published under: SIGN_BASE_URL/SIGN_TAG.
# After signing: the payloads are unchanged and exactly four catalogue files were added; the catalogue's packages all
# declare the expected ABI; the catalogue verifies with the pinned public key under that ABI, and is refused under another
# one (a control that proves the check can fail). Log: $SIGN_ROOT/sign-checkout-arm64.log.
set -eu
KEY=${1:?key file}
WANT=${2:?expected sha256}
R=${SIGN_ROOT:?SIGN_ROOT: where the unsigned checkout feed and its manifest were ingested}
MNT=${SIGN_MNT:-/var/keytmp-feed}
LOCK=/var/run/keywindow.lock
LOG=${SIGN_LOG:-$R/sign-checkout-arm64.log}
PUB=${SIGN_PUB:?SIGN_PUB: the public key the installer pins (keys/pkg-repo-1.3.1.pub), on this host}
CHK=${SIGN_CHK:-$R/checkout-feed}
CHKMAN=${SIGN_CHKMAN:-$R/manifest-checkout.sha256}
ABI=${SIGN_ABI:-FreeBSD:16:aarch64}
TAG=${SIGN_TAG:?SIGN_TAG: the release tag the feed will be published under, for example checkouts-16-aarch64-1.5.0-r2}
BASE=${SIGN_BASE_URL:-https://github.com/jordanhubbard/daemonarchy/releases/download}
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
log "checkout-arm64 start (feed $TAG, ABI $ABI); key sha256 compared on both sides by the caller: $WANT"
# The window is exclusive: one key at a time on this VM.
mkdir "$LOCK" 2>/dev/null || { log "another key window holds $LOCK"; trap - EXIT; rm -f "$KEY"; exit 1; }

# The key must be in memory only: a tmpfs of ours, and no swap.
case $KEY in "$MNT"/*) ;; *) log "key file is not under $MNT"; exit 1 ;; esac
mount | grep -q "^tmpfs on $MNT (tmpfs" || { log "$MNT is not a tmpfs"; exit 1; }
[ -z "$(swapinfo 2>/dev/null | sed 1d)" ] || { log "swap is on"; exit 1; }
[ -f "$KEY" ] && [ -s "$KEY" ] || { log "no key file"; exit 1; }
[ "$(stat -f %Lp "$KEY")" = 400 ] || [ "$(stat -f %Lp "$KEY")" = 600 ] || { log "key file mode must be 0400 or 0600"; exit 1; }
[ -f "$PUB" ] || { log "missing the public key $PUB"; exit 1; }
command -v jq >/dev/null 2>&1 || { log "jq is required to read the ABI labels"; exit 1; }

# 1. The staged feed: unsigned, and exactly what its manifest lists.
[ -d "$CHK" ] && [ -f "$CHKMAN" ] || { log "missing $CHK or $CHKMAN"; exit 1; }
[ -z "$(ls "$CHK" | grep -E '^(meta|meta\.conf|packagesite\.pkg|data\.pkg)$')" ] || { log "$CHK is already signed or holds catalogue files"; exit 1; }
# payload_ok DIR MANIFEST: every file in DIR (catalogue files excluded) is listed with its hash, and nothing else is.
payload_ok() {
  ( cd "$1" && ls | grep -vE '^(meta|meta\.conf|packagesite\.pkg|data\.pkg)$' | sort | while IFS= read -r f; do
      printf '%s %s\n' "$(sha256 -q "$f")" "$f"; done ) >"$1.now.$$"
  sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' "$2" | sort -k2 >"$1.man.$$"
  if cmp -s "$1.now.$$" "$1.man.$$"; then rm -f "$1.now.$$" "$1.man.$$"; return 0; fi
  log "payload of $1 differs from $2: $(diff "$1.now.$$" "$1.man.$$" | head -3 | tr '\n' ' ')"
  rm -f "$1.now.$$" "$1.man.$$"; return 1
}
payload_ok "$CHK" "$CHKMAN" || exit 1
log "payload of $CHK matches $(basename "$CHKMAN") ($(ls "$CHK" | wc -l | tr -d ' ') files, $(ls -l "$CHK" | awk 'NR>1{s+=$5} END{print s}') bytes)"

# 2. Every package declares exactly the expected ABI in its own manifest.
n=0; bad=0
for p in "$CHK"/*.pkg; do
  [ -f "$p" ] || continue
  n=$((n + 1))
  got=$(tar -xOf "$p" +COMPACT_MANIFEST 2>/dev/null | jq -r '.abi // empty' 2>/dev/null || true)
  if [ "$got" != "$ABI" ]; then bad=$((bad + 1)); log "  $(basename "$p") declares '${got:-no ABI}', not $ABI"; fi
done
[ "$n" -gt 0 ] || { log "$CHK holds no packages"; exit 1; }
[ "$bad" = 0 ] || { log "$bad of $n packages do not declare $ABI: refusing (rebuild the feed with build-checkout-packages.py --abi $ABI)"; exit 1; }
log "all $n packages declare $ABI"

# 3. checkouts.json names the release this feed is published under.
[ -f "$CHK/checkouts.json" ] || { log "no checkouts.json in $CHK"; exit 1; }
url=$(jq -r '.repository_url // empty' "$CHK/checkouts.json" 2>/dev/null || true)
[ "$url" = "$BASE/$TAG" ] || { log "checkouts.json repository_url is '$url', expected $BASE/$TAG: refusing"; exit 1; }
log "checkouts.json repository_url is $url"

# 4. Sign. The application feed is not an input.
log "signing $TAG ($n package files)"
pkg repo -q "$CHK" "$KEY" >/dev/null
for f in $CATS; do
  [ -f "$CHK/$f" ] || { log "pkg repo wrote no $f in $CHK"; exit 1; }
  log "  $TAG/$f $(sha256 -q "$CHK/$f") $(stat -f %z "$CHK/$f") bytes"
done
# The key is not needed any more: remove it before anything else runs.
rm -f "$KEY"
log "key file removed before verification"

# 5. Signing changes nothing but adds exactly the catalogue.
payload_ok "$CHK" "$CHKMAN" || { log "pkg repo changed the payload"; exit 1; }
count=$(ls "$CHK" | wc -l | tr -d ' ')
want=$(( $(sed -E 's/^[0-9a-f]{64} +\*?//' "$CHKMAN" | wc -l | tr -d ' ') + 4 ))
[ "$count" = "$want" ] || { log "$CHK holds $count files, expected $want (manifest + four catalogue files)"; exit 1; }
log "payload unchanged; exactly four catalogue files added"

# 6. The signed catalogue declares only the expected ABI (the rule of scripts/check-checkout-feed-abi.sh).
abis=$(tar -xOf "$CHK/packagesite.pkg" packagesite.yaml 2>/dev/null | jq -r '.abi // empty' | sort -u | tr '\n' ' ' | sed 's/ $//')
[ "$abis" = "$ABI" ] || { log "the catalogue's packages declare '$abis', not $ABI: refusing"; exit 1; }
log "the catalogue's packages all declare $ABI"

# 7. Verify the way a client does: pkg with the pinned public key, under the feed's ABI; a different ABI must be refused.
check() { # abi
  t=$(mktemp -d); mkdir -p "$t/repos"
  name=feedcheck$(od -An -N6 -tx1 /dev/urandom | tr -d " \n")   # unique per check: pkg caches a repository by name
  cat >"$t/repos/$name.conf" <<EOF
$name: {
  url: "file://$CHK",
  signature_type: "pubkey",
  pubkey: "$PUB",
  enabled: yes
}
EOF
  env IGNORE_OSVERSION=yes pkg -o REPOS_DIR="$t/repos" -o ABI="$1" update -f -r "$name" >"$t/out" 2>&1 || true
  rm -rf "/var/db/pkg/repos/$name"
  # pkg exits 0 even on "Invalid signature, removing repository", so read what it says.
  if grep -q 'Invalid signature' "$t/out" || ! grep -q "$name repository update completed" "$t/out"; then rc=1; else rc=0; fi
  last=$(grep 'packages processed' "$t/out" | tail -1 || true); [ -n "$last" ] || last=$(tail -2 "$t/out" | tr '\n' ' ')
  rm -rf "$t"; return "$rc"
}
if check "$ABI"; then log "  $TAG verifies with the pinned public key as $ABI: $last"; else log "  $TAG DOES NOT VERIFY as $ABI: $last"; exit 1; fi
other=FreeBSD:16:amd64; [ "$ABI" != "$other" ] || other=FreeBSD:16:aarch64
if check "$other"; then log "the catalogue was accepted as $other too: the ABI check cannot be trusted"; exit 1; fi
log "  control: the same catalogue is refused as $other"

# One list of the catalogue hashes for the report and the copy-back.
: >"$R/catalogue-hashes-checkout.txt" 2>/dev/null || true
for f in $CATS; do printf '%s %s %s\n' "$(sha256 -q "$CHK/$f")" "$(stat -f %z "$CHK/$f")" "$(basename "$CHK")/$f"; done | tee -a "$R/catalogue-hashes-checkout.txt" >>"$LOG"
log "the checkout feed is signed and verified"
