#!/bin/bash
# Move an UNSIGNED aarch64 feed pair from barmy to sparky to the build VM (mudflap), verifying every file against
# the manifests at each hop. No key is involved. Nothing is signed or uploaded.
#
#   arm64-ingest.sh TAG APPDIR CHKDIR APPMAN CHKMAN       (the last four are paths on barmy)
#
#   TAG      short label for the destination directories, e.g. 150
#   APPDIR   /home/jkh/..../app-feed       CHKDIR  /home/jkh/..../checkout-feed
#   APPMAN   manifest for APPDIR           CHKMAN  manifest for CHKDIR   (lines: "sha256 name", any spacing)
#
# Destinations (refused if they exist): ~/feed-stage-arm64-TAG-unsigned on sparky,
# $WORK/arm64-TAG on the build VM (manifests stored as manifest-app.sha256 / manifest-checkout.sha256).
set -euo pipefail
TAG=${1:?tag}; APPDIR=${2:?}; CHKDIR=${3:?}; APPMAN=${4:?}; CHKMAN=${5:?}
BARMY=${BARMY:-jkh@barmy.local}
MAD=${MAD:-jkh@madmax.local}
S=$HOME/feed-stage-arm64-$TAG-unsigned
R=${WORK:?WORK: the release working directory on the build VM}/arm64-$TAG
VMW='~/daemonarchy-builder-vm/ssh-worker.sh'
[ ! -e "$S" ] || { echo "$S exists: refusing" >&2; exit 1; }
CAT='^(meta|meta\.conf|packagesite\.pkg|data\.pkg)$'

echo "== 1. barmy: the feeds must match their manifests and hold no catalogue yet"
ssh -o BatchMode=yes "$BARMY" 'sh -s' "$APPDIR" "$CHKDIR" "$APPMAN" "$CHKMAN" <<'REMOTE'
set -u
check() { # dir manifest
  [ -d "$1" ] && [ -f "$2" ] || { echo "  missing $1 or $2"; return 1; }
  if ls "$1" | grep -qE '^(meta|meta\.conf|packagesite\.pkg|data\.pkg)$'; then echo "  $1 already holds catalogue files"; return 1; fi
  (cd "$1" && ls | sort | while IFS= read -r f; do printf '%s %s\n' "$(sha256 -q "$f")" "$f"; done) > /tmp/ing.live
  sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' "$2" | sort -k2 > /tmp/ing.man
  if cmp -s /tmp/ing.live /tmp/ing.man; then
    echo "  $1: $(wc -l < /tmp/ing.live | tr -d ' ') files, $(cd "$1" && ls -l | awk 'NR>1{s+=$5} END{print s}') bytes, manifest sha256 $(sha256 -q "$2")"
  else echo "  $1 DIFFERS from $2: $(diff /tmp/ing.live /tmp/ing.man | head -3 | tr '\n' ' ')"; return 1; fi
}
check "$1" "$3" && check "$2" "$4"; rc=$?; rm -f /tmp/ing.live /tmp/ing.man; exit $rc
REMOTE

echo "== 2. barmy -> sparky ($S)"
mkdir -p "$S/app-feed" "$S/checkout-feed"
ssh -o BatchMode=yes "$BARMY" "tar -C '$APPDIR' -cf - ." | tar -C "$S/app-feed" -xf -
ssh -o BatchMode=yes "$BARMY" "tar -C '$CHKDIR' -cf - ." | tar -C "$S/checkout-feed" -xf -
ssh -o BatchMode=yes "$BARMY" "cat '$APPMAN'" > "$S/manifest-app.sha256"
ssh -o BatchMode=yes "$BARMY" "cat '$CHKMAN'" > "$S/manifest-checkout.sha256"
verify_local() { # dir manifest
  (cd "$1" && ls | sort | while IFS= read -r f; do printf '%s %s\n' "$(sha256sum "$f" | cut -d' ' -f1)" "$f"; done) > /tmp/ing.l
  sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' "$2" | sort -k2 > /tmp/ing.m
  cmp -s /tmp/ing.l /tmp/ing.m && echo "  sparky $(basename "$1"): $(wc -l < /tmp/ing.l) files MATCH the manifest, $(du -sb "$1" | cut -f1) bytes" \
    || { echo "  sparky $(basename "$1") DIFFERS"; diff /tmp/ing.l /tmp/ing.m | head -3; rm -f /tmp/ing.l /tmp/ing.m; return 1; }
  rm -f /tmp/ing.l /tmp/ing.m
}
verify_local "$S/app-feed" "$S/manifest-app.sha256"
verify_local "$S/checkout-feed" "$S/manifest-checkout.sha256"

echo "== 3. sparky -> mudflap ($R), through madmax in memory"
ssh -o BatchMode=yes "$MAD" "$VMW 'test ! -e $R && mkdir -p $R/app-feed $R/checkout-feed'"
for f in app-feed checkout-feed; do
  tar -C "$S/$f" -cf - . | ssh -o BatchMode=yes "$MAD" "$VMW 'tar -C $R/$f -xpf -'"
done
for m in app checkout; do ssh -o BatchMode=yes "$MAD" "$VMW 'cat > $R/manifest-$m.sha256'" < "$S/manifest-$m.sha256"; done
ssh -o BatchMode=yes "$MAD" "$VMW 'sh -s'" <<REMOTE
R=$R
for pair in "app-feed manifest-app.sha256" "checkout-feed manifest-checkout.sha256"; do
  set -- \$pair
  (cd \$R/\$1 && ls | sort | while IFS= read -r f; do printf '%s %s\n' "\$(sha256 -q "\$f")" "\$f"; done) > /tmp/ing.v
  sed -E 's/^([0-9a-f]{64}) +\*?/\1 /' \$R/\$2 | sort -k2 > /tmp/ing.vm
  if cmp -s /tmp/ing.v /tmp/ing.vm; then echo "  mudflap \$1: \$(wc -l < /tmp/ing.v | tr -d ' ') files MATCH the manifest, \$(cd \$R/\$1 && ls -l | awk 'NR>1{s+=\$5} END{print s}') bytes, catalogue files: \$(ls \$R/\$1 | grep -cE '$CAT')"
  else echo "  mudflap \$1 DIFFERS"; diff /tmp/ing.v /tmp/ing.vm | head -3; exit 1; fi
done
rm -f /tmp/ing.v /tmp/ing.vm
REMOTE
echo "== done: every file matched its manifest on barmy, sparky and mudflap. Ready for the arm64 key window with SIGN_ROOT=$R"
