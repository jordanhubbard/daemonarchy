#!/bin/bash
# Move an UNSIGNED aarch64 CHECKOUT feed from the arm64 builder to this host to the build VM, verifying every file against its
# manifest at each hop. No key is involved. Nothing is signed or uploaded. The application feed is not an input.
#
#   arm64-ingest-checkout.sh TAG CHKDIR CHKMAN          (the last two are paths on the arm64 builder)
#
#   TAG     short label for the destination directories, e.g. 150r2
#   CHKDIR  /home/jkh/..../checkout-feed-150r2         CHKMAN  its manifest (lines: "sha256 name", any spacing)
#
# Destinations (refused if they exist): ~/feed-stage-arm64-TAG-unsigned here, $WORK/arm64-TAG on the build VM (the manifest is
# stored as manifest-checkout.sha256). The arm64 builder is BARMY (default jkh@barmy.local), the key host MAD (default jkh@madmax.local).
set -euo pipefail
TAG=${1:?tag}; CHKDIR=${2:?}; CHKMAN=${3:?}
BARMY=${BARMY:-jkh@barmy.local}
MAD=${MAD:-jkh@madmax.local}
S=$HOME/feed-stage-arm64-$TAG-unsigned
R=${WORK:?WORK: the release working directory on the build VM}/arm64-$TAG
VMW='~/daemonarchy-builder-vm/ssh-worker.sh'
[ ! -e "$S" ] || { echo "$S exists: refusing" >&2; exit 1; }

echo "== 1. the arm64 builder: the feed must match its manifest and hold no catalogue yet"
ssh -o BatchMode=yes "$BARMY" 'sh -s' "$CHKDIR" "$CHKMAN" <<'REMOTE'
set -u
[ -d "$1" ] && [ -f "$2" ] || { echo "  missing $1 or $2"; exit 1; }
if ls "$1" | grep -qE '^(meta|meta\.conf|packagesite\.pkg|data\.pkg)$'; then echo "  $1 already holds catalogue files"; exit 1; fi
(cd "$1" && ls | sort | while IFS= read -r f; do printf '%s %s\n' "$(sha256 -q "$f")" "$f"; done) > /tmp/ing.live
sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' "$2" | sort -k2 > /tmp/ing.man
if cmp -s /tmp/ing.live /tmp/ing.man; then
  echo "  $1: $(wc -l < /tmp/ing.live | tr -d ' ') files, $(cd "$1" && ls -l | awk 'NR>1{s+=$5} END{print s}') bytes, manifest sha256 $(sha256 -q "$2")"; rc=0
else echo "  $1 DIFFERS from $2: $(diff /tmp/ing.live /tmp/ing.man | head -3 | tr '\n' ' ')"; rc=1; fi
rm -f /tmp/ing.live /tmp/ing.man; exit $rc
REMOTE

echo "== 2. the arm64 builder -> this host ($S)"
mkdir -p "$S/checkout-feed"
ssh -o BatchMode=yes "$BARMY" "tar -C '$CHKDIR' -cf - ." | tar -C "$S/checkout-feed" -xf -
ssh -o BatchMode=yes "$BARMY" "cat '$CHKMAN'" > "$S/manifest-checkout.sha256"
(cd "$S/checkout-feed" && ls | sort | while IFS= read -r f; do printf '%s %s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "$f"; done) > "$S/.l"
sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' "$S/manifest-checkout.sha256" | sort -k2 > "$S/.m"
cmp -s "$S/.l" "$S/.m" || { echo "  this host DIFFERS from the manifest"; diff "$S/.l" "$S/.m" | head -3; exit 1; }
echo "  this host: $(wc -l < "$S/.l") files MATCH the manifest, $(du -sb "$S/checkout-feed" | cut -f1) bytes"
rm -f "$S/.l" "$S/.m"

echo "== 3. this host -> the build VM ($R), through the key host in memory"
ssh -o BatchMode=yes "$MAD" "$VMW 'test ! -e $R && mkdir -p $R/checkout-feed'"
tar -C "$S/checkout-feed" -cf - . | ssh -o BatchMode=yes "$MAD" "$VMW 'tar -C $R/checkout-feed -xpf -'"
ssh -o BatchMode=yes "$MAD" "$VMW 'cat > $R/manifest-checkout.sha256'" < "$S/manifest-checkout.sha256"
ssh -o BatchMode=yes "$MAD" "$VMW 'sh -s'" <<REMOTE
R=$R
(cd \$R/checkout-feed && ls | sort | while IFS= read -r f; do printf '%s %s\n' "\$(sha256 -q "\$f")" "\$f"; done) > /tmp/ing.v
sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' \$R/manifest-checkout.sha256 | sort -k2 > /tmp/ing.vm
if cmp -s /tmp/ing.v /tmp/ing.vm; then echo "  build VM: \$(wc -l < /tmp/ing.v | tr -d ' ') files MATCH the manifest, \$(cd \$R/checkout-feed && ls -l | awk 'NR>1{s+=\$5} END{print s}') bytes, catalogue files: \$(ls \$R/checkout-feed | grep -cE '^(meta|meta\.conf|packagesite\.pkg|data\.pkg)\$')"
else echo "  build VM DIFFERS"; diff /tmp/ing.v /tmp/ing.vm | head -3; rm -f /tmp/ing.v /tmp/ing.vm; exit 1; fi
rm -f /tmp/ing.v /tmp/ing.vm
REMOTE
echo "== done: every file matched its manifest on the arm64 builder, this host and the build VM. Ready for checkout-arm64-window.sh with CHK_ARM_TAG=$TAG"
