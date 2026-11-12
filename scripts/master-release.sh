#!/usr/local/bin/bash
# Master a Daemonarchy release image: packages, signed feed, ISO, verification, QEMU QA
# and the USB sticks, in resumable steps. docs/mastering-1.4.1.md explains each step.
#
#   master-release.sh [--dry-run] [--force] [--config FILE] STEP...
#
#   preflight   tools, the main commit, disk space, the state file     (builder)
#   packages    kernel-bound modules, NVIDIA, omarchy, daemonarchy      (builder, hours)
#   secureboot  regenerate the module inventory; re-sign the boot bundle only if it changed (builder)
#   feed        collect and sign the application feed, print the upload plan (builder)
#   resolve     prove the MSI and MacBook selections resolve from the image's own repositories (builder)
#   catalogue   check the checkout catalogue against the source and ports revisions (builder)
#   iso         build the ISO from a clean checkout of MAIN_COMMIT      (builder, ~26 min)
#   inspect     hashes, budget and static image contents; no native admission (controller)
#   verify      static checks plus required native Python import from planned 1.6 (builder)
#   hwtrace     build the hardware trace image from the verified ISO's own kernel and loader (builder, ~10 s)
#   qa          copy the ISO to QA_HOST and run test-qemu.sh there      (QA host, ~35 min)
#   sticks      write verified single/split media to named USB sticks and read back (workstation)
#   all         preflight packages secureboot feed resolve catalogue iso verify hwtrace qa  (never sticks, never publishes)
#   status      print the state file
#
# Nothing here uploads to GitHub or signs with a release key except `feed`, which signs
# on the builder with the key already there. Publishing is a separate, approved step.
#
# sticks takes explicit devices, each with the serial the operator read from the machine:
#   master-release.sh sticks --iso FILE.iso.xz --raw-sha256 HEX --raw-size N \
#       --device /dev/sdb:SERIAL --device /dev/sdc:SERIAL
# Or use --manifest FILE.iso.parts.json.xz --manifest-sha256 HEX instead of --iso.
# Split selection also requires the exact --raw-sha256 and --raw-size.
# It refuses a device that is not a whole USB disk, is mounted, is too small, is larger
# than STICK_MAX_BYTES, is on the deny list (the scratch disk), or whose serial differs.
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
DRY_RUN=false
FORCE=false
CONFIG=${MASTER_CONFIG:-}

# ---- configuration (override in the config file or the environment) ------------------
WORK=${WORK:-/usr/daemonarchy/rev2-20261030}
REPO_URL=${REPO_URL:-https://github.com/jordanhubbard/daemonarchy.git}
MAIN_COMMIT=${MAIN_COMMIT:-}
JAIL=${JAIL:-16r2303b36}
PTREE=${PTREE:-daports141}
SET_CACHE_DIR=${SET_CACHE_DIR:-$WORK/inputs/source-sets}
RELEASE=${RELEASE:-1.5.0}                            # the release being mastered: names its feeds and boot bundle
CLOSURE_SHARD_TAG=${CLOSURE_SHARD_TAG:-packages-16-amd64-1.4.1-upstream}   # the signed upstream snapshot the image prefers
CHECKOUT_CATALOG=${CHECKOUT_CATALOG:-$WORK/checkout-feed-$RELEASE/checkouts.json}
SOURCE_REVISION=${SOURCE_REVISION:-303b3646270ffa4bf7cec65c5c1d28bd8000cbce}
PORTS_REVISION=${PORTS_REVISION:-b7f50a91973f73db047775a010237cae3455596a}
PACKAGE_REPOSITORY_TAG=${PACKAGE_REPOSITORY_TAG:-packages-16-amd64-$RELEASE}
SECUREBOOT_BUNDLE=${SECUREBOOT_BUNDLE:-/usr/daemonarchy/sb16/daemonarchy-$RELEASE-boot.txz}
SECUREBOOT_CERTIFICATE=${SECUREBOOT_CERTIFICATE:-/usr/daemonarchy/boot-replacement-candidate-public-20261024/daemonarchy-1.3.1.pem}
SIGN_KEY=${SIGN_KEY:-/usr/local/etc/daemonarchy/pkg-repo-next.key}
BUILT_PACKAGES_FILE=${BUILT_PACKAGES_FILE:-$WORK/built-141.txt}
CLOSURE_DIR=${CLOSURE_DIR:-/tmp/closure/out/$CLOSURE_SHARD_TAG}
# resolve can run against the published releases instead of the staged directories:
APP_FEED_URL=${APP_FEED_URL:-}
CLOSURE_URL=${CLOSURE_URL:-}
REQUIRE_PACKAGE_MIRROR=${REQUIRE_PACKAGE_MIRROR:-yes}
SB_DIR=${SB_DIR:-/usr/daemonarchy/sb16}
XZ_BUDGET=${XZ_BUDGET:-2147483648}                # a GitHub release asset must stay under 2 GiB
# An explicit planned-1.6 split selection; never infer it from a failed single-file gate.
MEDIA_MANIFEST=${MEDIA_MANIFEST:-}
MEDIA_MANIFEST_SHA256=${MEDIA_MANIFEST_SHA256:-}
ASSETS_DIR=${ASSETS_DIR:-$WORK/assets-$RELEASE}      # where the release assets this script builds (the hwtrace image) are collected
QA_HOST=${QA_HOST:-madmax.local}
QA_USER=${QA_USER:-jkh}
QA_DIR=${QA_DIR:-/tmp/daemonarchy-qa}
QA_VIRGL_RENDER_NODE=${QA_VIRGL_RENDER_NODE:-/dev/dri/renderD128}   # the desktop check renders through VirGL
STICK_MAX_BYTES=${STICK_MAX_BYTES:-137438953472}  # 128 GiB: refuses the 239 GB scratch disk and anything larger
DENY_SERIALS=${DENY_SERIALS:-03A0423110011698}    # sda "toolscratch" (Samsung, 239 GB): never written
LSBLK=${LSBLK:-lsblk}

fail() { echo "master-release: $*" >&2; exit 1; }

run() {
  printf '+ %s\n' "$*"
  $DRY_RUN || "$@"
}

master_python() {
  if command -v python3 >/dev/null; then python3 "$@"; else python3.12 "$@"; fi
}

short() { printf '%s' "${MAIN_COMMIT:0:12}"; }

native_verify_required() {
  [[ $RELEASE =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'release version must be X.Y.Z'
  local major minor
  IFS=. read -r major minor <<<"${RELEASE%.*}"
  [ "$major" -gt 1 ] || { [ "$major" -eq 1 ] && [ "$minor" -ge 6 ]; }
}

# ---- state: each step records when it last succeeded, so a rerun resumes -------------
state_key() {
  case $1 in
    inspect | verify | hwtrace | qa)
      if [ -n "$MEDIA_MANIFEST" ]; then
        printf '%s:xz-parts@1:%s:packed-content@2:%s:%s:%s' "$1" "$MEDIA_MANIFEST_SHA256" "$MAIN_COMMIT" "$RELEASE" "${ARCH:-amd64}"
        return
      elif native_verify_required; then
        local pin=unselected candidates=("$WORK/out-$(short)"/*.iso.xz)
        if [ "${#candidates[@]}" -eq 1 ] && [ -f "${candidates[0]}" ] && [ ! -L "${candidates[0]}" ]; then
          pin=$(sha256_of <"${candidates[0]}")
        fi
        printf '%s:single-xz:%s:packed-content@2:%s:%s:%s' "$1" "$pin" "$MAIN_COMMIT" "$RELEASE" "${ARCH:-amd64}"
        return
      fi ;;
  esac
  printf '%s' "$1"
}

state_mark() { $DRY_RUN || { mkdir -p "$(dirname "$STATE")"; printf '%s\tok\t%s\n' "$(state_key "$1")" "$(date -u +%FT%TZ)" >>"$STATE"; }; }
state_done() { [ -f "$STATE" ] && awk -F '\t' -v key="$(state_key "$1")" '$1 == key && $2 == "ok" { found = 1 } END { exit !found }' "$STATE"; }
step_enabled() {
  # Fresh single-file inspection also checks any cached raw ISO against its stream.
  case $1 in
    inspect | verify)
      if [ -z "$MEDIA_MANIFEST" ] && native_verify_required; then echo "== $1"; return 0; fi ;;
  esac
  # Skip a step already done unless --force; a dry run always shows it.
  if ! $FORCE && ! $DRY_RUN && state_done "$1"; then
    case $1 in
      inspect | verify | hwtrace | qa)
        if [ -n "$MEDIA_MANIFEST" ]; then
          split_selection
          master_python "$here/scripts/master-media.py" "$MEDIA_MANIFEST" --sha256 "$MEDIA_MANIFEST_SHA256" \
            --image "$SELECTED_NAME" >/dev/null || fail 'previous split step input no longer verifies'
        fi ;;
    esac
    echo "== $1: done before (use --force to redo)"; return 1
  fi
  echo "== $1"
}

# ---- steps ---------------------------------------------------------------------------
step_preflight() {
  step_enabled preflight || return 0
  local tool
  for tool in git xz jq; do command -v "$tool" >/dev/null || fail "missing tool: $tool"; done
  command -v sha256 >/dev/null || command -v sha256sum >/dev/null || fail 'missing sha256/sha256sum'
  [[ $MAIN_COMMIT =~ ^[0-9a-f]{40}$ ]] || fail 'MAIN_COMMIT must be the full 40-hex commit to master'
  if ! $DRY_RUN; then
    git ls-remote "$REPO_URL" "$MAIN_COMMIT" >/dev/null || fail "cannot reach $REPO_URL"
    [ -d "$WORK" ] || fail "work directory $WORK does not exist"
    local free_kb
    free_kb=$(df -k "$WORK" | awk 'NR == 2 { print $4 }')
    [ "$free_kb" -gt 31457280 ] || fail "less than 30 GB free in $WORK"
  fi
  state_mark preflight
}

fetch_product() {
  local dir=$WORK/product-$(short)
  [ -d "$dir" ] && return 0
  run git clone -q "$REPO_URL" "$dir.git"
  run git -C "$dir.git" checkout -q "$MAIN_COMMIT"
  run mkdir -p "$dir"
  if ! $DRY_RUN; then
    git -C "$dir.git" archive HEAD | tar -xf - -C "$dir"
    echo "$MAIN_COMMIT" >"$dir/.selected-commit"
  fi
}

step_packages() {
  step_enabled packages || return 0
  fetch_product
  local product=$WORK/product-$(short)
  for sub in origins seed plan bulk built identity; do
    run env WORK="$WORK" JAIL="$JAIL" PTREE="$PTREE" BUILT_OUT="$BUILT_PACKAGES_FILE" "$product/scripts/build-release-packages.sh" "$sub"
  done
  state_mark packages
}

step_secureboot() {
  step_enabled secureboot || return 0
  fetch_product
  local product=$WORK/product-$(short)
  run env S="$SB_DIR" CACHE="$SET_CACHE_DIR" PACKAGES="$WORK/poudriere-data/packages/$JAIL-$PTREE/.latest/All" \
      REV="$SOURCE_REVISION" "$product/scripts/resign-boot-bundle.sh" sign
  state_mark secureboot
}

step_resolve() {
  step_enabled resolve || return 0
  fetch_product
  local product=$WORK/product-$(short)
  run "$product/scripts/check-install-resolution.sh" "$WORK/poudriere-data/packages/$JAIL-$PTREE" "${APP_FEED_URL:-$FEED_OUT}" "${CLOSURE_URL:-$CLOSURE_DIR}" all
  state_mark resolve
}

step_feed() {
  step_enabled feed || return 0
  # pkg-repo.sh build empties its output directory first: never aim it at a staged feed.
  if ! $DRY_RUN && [ -n "$(ls -A "$FEED_OUT" 2>/dev/null)" ]; then
    fail "$FEED_OUT already holds a staged feed; use another PACKAGE_REPOSITORY_TAG or FEED_OUT"
  fi
  fetch_product
  local product=$WORK/product-$(short) plan=$FEED_OUT.plan.txt
  run env ARCH=amd64 JAIL="$JAIL" PTREE="$PTREE" TAG="$PACKAGE_REPOSITORY_TAG" KEY="$SIGN_KEY" OUT="$FEED_OUT" \
      PACKAGES_DIR="$WORK/poudriere-data/packages/$JAIL-$PTREE" \
      BUILT_PACKAGES_FILE="$BUILT_PACKAGES_FILE" sh "$product/pkg-repo.sh" build
  if ! $DRY_RUN; then
    {
      echo "Application feed $PACKAGE_REPOSITORY_TAG (stage only; nothing uploaded)"
      echo "directory: $FEED_OUT"
      echo "assets: $(ls "$FEED_OUT" | wc -l | tr -d ' '), bytes: $(du -sk "$FEED_OUT" | cut -f1) KiB"
      ( cd "$FEED_OUT" && for f in *; do printf '%s  %s\n' "$(sha256 -q "$f" 2>/dev/null || sha256sum "$f" | cut -d' ' -f1)" "$f"; done )
      echo "upload: gh release create $PACKAGE_REPOSITORY_TAG --latest=false, then every package, then the catalogue files"
    } >"$plan"
    echo "upload plan: $plan"
  fi
  state_mark feed
}

step_catalogue() {
  step_enabled catalogue || return 0
  if $DRY_RUN; then echo "+ jq checks of $CHECKOUT_CATALOG against $SOURCE_REVISION and $PORTS_REVISION"; return 0; fi
  [ -s "$CHECKOUT_CATALOG" ] || fail "no checkout catalogue at $CHECKOUT_CATALOG"
  jq -e --arg src "$SOURCE_REVISION" --arg ports "$PORTS_REVISION" \
      '.schema == 1 and .trees.src.revision == $src and .trees.ports.revision == $ports' "$CHECKOUT_CATALOG" >/dev/null \
    || fail "$CHECKOUT_CATALOG does not name source $SOURCE_REVISION and ports $PORTS_REVISION: rebuild the checkout feed (scripts/build-checkout-packages.py, make-checkout-catalog.py) and stage it first"
  state_mark catalogue
}

step_iso() {
  step_enabled iso || return 0
  fetch_product
  local product=$WORK/product-$(short) out=$WORK/out-$(short)
  run mkdir -p "$out"
  if $DRY_RUN; then
    echo "+ (cd $product && env JAIL=$JAIL PTREE=$PTREE PACKAGE_MIRROR_URLS=$PACKAGE_MIRROR_URLS REQUIRE_PACKAGE_MIRROR=$REQUIRE_PACKAGE_MIRROR ... sh ./build-iso.sh)"
    return 0
  fi
  ( cd "$product" && env \
      JAIL="$JAIL" PTREE="$PTREE" \
      POUDRIERE_ETC="$WORK/poudriere-etc" POUDRIERE_DATA="$WORK/poudriere-data" \
      PACKAGES_DIR="$WORK/poudriere-data/packages/$JAIL-$PTREE" \
      SET_CACHE_DIR="$SET_CACHE_DIR" OUTDIR="$out" ISO_STAGE_PARENT="$WORK/stage" \
      CHECKOUT_CATALOG="$CHECKOUT_CATALOG" \
      PACKAGE_REPOSITORY_TAG="$PACKAGE_REPOSITORY_TAG" \
      PACKAGE_MIRROR_URLS="$PACKAGE_MIRROR_URLS" REQUIRE_PACKAGE_MIRROR="$REQUIRE_PACKAGE_MIRROR" \
      PACKAGE_REPOSITORY_PUBLIC_KEY="$product/keys/pkg-repo-1.3.1.pub" \
      SECUREBOOT_BUNDLE="$SECUREBOOT_BUNDLE" SECUREBOOT_SIGNATURE="$SECUREBOOT_BUNDLE.sig" \
      SECUREBOOT_CERTIFICATE="$SECUREBOOT_CERTIFICATE" \
      sh ./build-iso.sh ) >"$WORK/evidence/build-iso-$(short).log" 2>&1 || fail "build-iso.sh failed; see $WORK/evidence/build-iso-$(short).log"
  state_mark iso
}

# On a FreeBSD builder as root: mount the built image read-only and import sqlite3 with the live
# root's own Python (parallel-fetch needs it for exact install-plan byte totals).
live_root_import_check() {
  local iso=$1 mode=${2:-required} md mnt status=1 ram_md='' ram_mnt='' selected_root=''
  if [ "$(uname -s)" != FreeBSD ] || [ "$(id -u)" != 0 ]; then
    echo "native live-root Python import unrun (needs a FreeBSD builder and root); static content checks do not replace it" >&2
    [ "$mode" != legacy-static ] || return 0
    return 77
  fi
  mnt=$(mktemp -d)
  md=$(mdconfig -a -t vnode -o readonly -f "$iso") || { rmdir "$mnt"; return 1; }
  if mount -t cd9660 -o ro "/dev/$md" "$mnt"; then
    if [ -f "$mnt/boot/mfsroot.uzip" ]; then
      ram_mnt=$(mktemp -d)
      if ram_md=$(mdconfig -a -t vnode -o readonly -f "$mnt/boot/mfsroot.uzip"); then
        if [ -c "/dev/$ram_md.uzip" ] && mount -t ufs -o ro "/dev/$ram_md.uzip" "$ram_mnt"; then
          selected_root=$ram_mnt
        else
          echo 'cannot mount packed live root read-only; native GEOM UZIP is required' >&2
        fi
      fi
    else
      selected_root=$mnt
    fi
    if [ -n "$selected_root" ]; then
      if master_python - "$selected_root" <<'NATIVE_SQLITE'
import subprocess, sys
try:
    subprocess.run(['chroot', sys.argv[1], '/usr/local/bin/python3.12', '-c',
                    'import sqlite3; c = sqlite3.connect(":memory:"); assert c.execute("select 42").fetchone()[0] == 42; print("native live root: import sqlite3 ok, sqlite", sqlite3.sqlite_version)'],
                   check=True, timeout=60)
except (subprocess.SubprocessError, OSError) as exc:
    print(f'native live-root import failed: {exc}', file=sys.stderr)
    raise SystemExit(1)
NATIVE_SQLITE
      then
        status=0
      fi
    fi
    if [ -n "$ram_mnt" ]; then
      if [ -n "$selected_root" ]; then umount "$ram_mnt" || status=1; fi
      [ -z "$ram_md" ] || mdconfig -d -u "${ram_md#md}" || status=1
      rmdir "$ram_mnt" 2>/dev/null || true
    fi
    umount "$mnt" || status=1
  fi
  mdconfig -d -u "${md#md}" || status=1
  rmdir "$mnt" 2>/dev/null || true
  return "$status"
}

# Quote one remote POSIX-shell argument (ssh joins its command arguments).
shell_quote() { printf "'%s'" "${1//\'/\'\\\'\'}"; }

split_selection() {
  [[ $MAIN_COMMIT =~ ^[0-9a-f]{40}$ ]] || fail 'split media requires a full selected MAIN_COMMIT'
  [[ $MEDIA_MANIFEST_SHA256 =~ ^[0-9a-f]{64}$ ]] || fail 'split media requires MEDIA_MANIFEST_SHA256'
  [[ $RELEASE =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'split media requires a release version'
  local major minor
  IFS=. read -r major minor <<<"${RELEASE%.*}"
  [ "$major" -gt 1 ] || { [ "$major" -eq 1 ] && [ "$minor" -ge 6 ]; } || fail 'split mastering begins with 1.6.0'
  case ${ARCH:-amd64} in amd64 | aarch64) ;; *) fail 'ARCH must be amd64 or aarch64' ;; esac
  SELECTED_NAME=daemonarchy-$RELEASE-${ARCH:-amd64}.iso
  [ "$(basename "$MEDIA_MANIFEST")" = "$SELECTED_NAME.parts.json.xz" ] || fail 'split manifest does not name the selected release and architecture'
}

materialize_split() {
  split_selection
  local tmp
  tmp=$(mktemp -d "$WORK/master-media.XXXXXX")
  SELECTED_ISO=$tmp/$SELECTED_NAME
  SELECTED_RECORD=$tmp/verified.json
  echo "split reconstruction/evidence retained in $tmp"
  master_python "$here/scripts/master-media.py" "$MEDIA_MANIFEST" --sha256 "$MEDIA_MANIFEST_SHA256" \
    --image "$SELECTED_NAME" --out "$SELECTED_ISO" >"$tmp/verified.json" || fail "split verification failed; retained $tmp"
  sh "$here/scripts/check-image-size.sh" "$SELECTED_ISO"
  echo "raw_sha256=$(jq -r '.image.sha256' "$tmp/verified.json") raw_size=$(jq -r '.image.bytes' "$tmp/verified.json")"
}

finish_image_checks() {
  local iso=$1 stage=$2 runtime_status=0 mode=required
  if [ "$stage" = inspect ]; then
    echo 'static image inspection passed; native Python import remains unqualified'
    state_mark inspect
    return 0
  fi
  native_verify_required || mode=legacy-static
  live_root_import_check "$iso" "$mode" || runtime_status=$?
  if [ "$runtime_status" -eq 77 ]; then
    echo 'native verification is unrun; no verify success recorded (inspect provides static checks)' >&2
    return 77
  fi
  [ "$runtime_status" -eq 0 ] || fail 'native import sqlite3 fails in the live root'
  state_mark verify
}

step_inspect() { step_verify inspect; }

step_verify() {
  local stage=${1:-verify}
  step_enabled "$stage" || return 0
  local out=$WORK/out-$(short) xz iso want got size version inspection
  if [ -n "$MEDIA_MANIFEST" ]; then
    split_selection
    if $DRY_RUN; then echo "+ verify/reconstruct pinned split $MEDIA_MANIFEST ($MEDIA_MANIFEST_SHA256), raw budget, version and live-root checks"; return 0; fi
    materialize_split
    iso=$SELECTED_ISO
    got=$(jq -r '.image.sha256' "$SELECTED_RECORD")
  else
    if $DRY_RUN; then echo "+ verify $out/*.iso.xz: xz -t, sha256, size under $XZ_BUDGET, version"; return 0; fi
    xz=$(ls "$out"/*.iso.xz 2>/dev/null | head -1) || true
    [ -n "$xz" ] || fail "no .iso.xz in $out"
    iso=${xz%.xz}
    xz -t "$xz" || fail 'xz stream is damaged'
    size=$(wc -c <"$xz" | tr -d ' ')
    [ "$size" -lt "$XZ_BUDGET" ] || fail "$xz is $size bytes, over the $XZ_BUDGET release asset budget"
    want=$(awk '{ print $1 }' "$xz.sha256")
    got=$(sha256 -q "$xz" 2>/dev/null || sha256sum "$xz" | cut -d' ' -f1)
    [ "$want" = "$got" ] || fail "sha256 of $xz does not match its .sha256 file"
    want=$(awk '{ print $1 }' "$iso.sha256" 2>/dev/null || true)
    got=$(xz -dc "$xz" | { sha256 -q 2>/dev/null || sha256sum | cut -d' ' -f1; })
    [ -z "$want" ] || [ "$want" = "$got" ] || fail 'decompressed image does not match the raw .sha256'
    echo "raw_sha256=$got raw_size=$(xz -l --robot "$xz" | awk '/^totals/ { print $5 }')"
  fi
  # The version of the commit being mastered, not of wherever this script runs from.
  version=$(tr -d '[:space:]' <"$WORK/product-$(short)/VERSION")
  if command -v bsdtar >/dev/null; then
    inspection=$(mktemp -d "$WORK/master-inspect.XXXXXX")
    bsdtar -tf "$iso" >"$inspection/members.txt" || fail "cannot inventory image; retained $inspection"
    if grep -E '^(\./)?boot/mfsroot\.uzip$' "$inspection/members.txt" >/dev/null; then
      [ "${ARCH:-amd64}" = aarch64 ] || fail 'packed ARM root requires ARCH=aarch64'
      [ "$version" = "$RELEASE" ] || fail 'selected product version differs from the planned packed release'
      master_python "$here/scripts/check-packed-installer.py" "$iso" --sha256 "$got" --version "$version" \
        >"$inspection/packed-inspection.json" || fail "packed ARM content inspection failed; retained $inspection"
      finish_image_checks "$iso" "$stage"
      return $?
    fi
    [ "$(bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/version 2>/dev/null | head -1)" = "$version" ] \
      || fail "the image's installer version is not $version"
    # parallel-fetch reads pkg's databases with the live Python's sqlite3 module (exact @@plan byte totals).
    grep '_sqlite3' "$inspection/members.txt" >/dev/null \
      || fail "the image's live Python has no sqlite3 module: add py312-sqlite3 to the live packages"
  else
    [ -z "$MEDIA_MANIFEST" ] || fail 'bsdtar is required for split image content verification'
    echo "bsdtar not found: image version not checked" >&2
  fi
  finish_image_checks "$iso" "$stage"
}

step_hwtrace() {
  step_enabled hwtrace || return 0
  [ -z "$MEDIA_MANIFEST" ] || split_selection
  fetch_product
  local product=$WORK/product-$(short) out=$WORK/out-$(short) iso xz tmp name=daemonarchy-hwtrace-$RELEASE-${ARCH:-amd64}.img.xz
  if [ -n "$MEDIA_MANIFEST" ]; then split_selection; fi
  if $DRY_RUN; then
    [ -z "$MEDIA_MANIFEST" ] || echo "+ reconstruct pinned split $MEDIA_MANIFEST ($MEDIA_MANIFEST_SHA256) for hwtrace"
    echo "+ (cd $out && nice -n 19 sh $product/build-hwtrace-image.sh -I ISO -k boot/kernel/kernel -l boot/loader_lua.efi -L boot/lua -V $RELEASE -Z -a ${ARCH:-amd64} -o TMP)  # from the ISO, minus brand-daemonarchy.lua and local.lua"
    echo "+ cp TMP/$name TMP/$name.sha256 $ASSETS_DIR/"
    return 0
  fi
  if [ -n "$MEDIA_MANIFEST" ]; then
    materialize_split
    iso=$SELECTED_ISO
  else
    xz=$(ls "$out"/*.iso.xz 2>/dev/null | head -1) || true
    [ -n "$xz" ] || fail "no .iso.xz in $out"
    iso=${xz%.xz}
  fi
  [ ! -e "$ASSETS_DIR/$name" ] || fail "$ASSETS_DIR/$name exists: published tags are immutable, move it away first"
  tmp=$(mktemp -d "$WORK/hwtrace.XXXXXX")
  [ -f "$iso" ] || { iso=$tmp/image.iso; xz -dc "$xz" >"$iso"; }
  # The image carries the ISO's own boottrace kernel and loader, so its provenance is the final ISO.
  # The Daemonarchy brand and a local.lua stay out: the trace image has its own loader screen.
  # boot/loader_lua.efi is a hard link to boot/loader.efi in the ISO: extract the target too, or tar refuses the link.
  tar -xf "$iso" -C "$tmp" boot/kernel/kernel boot/loader.efi boot/loader_lua.efi boot/lua
  rm -f "$tmp/boot/lua/brand-daemonarchy.lua" "$tmp/boot/lua/local.lua"
  mkdir "$tmp/out"
  nice -n 19 sh "$product/build-hwtrace-image.sh" -I "$iso" -k "$tmp/boot/kernel/kernel" -l "$tmp/boot/loader_lua.efi" \
      -L "$tmp/boot/lua" -V "$RELEASE" -Z -a "${ARCH:-amd64}" -o "$tmp/out" >"$WORK/evidence/build-hwtrace-$(short).log" 2>&1 \
    || fail "build-hwtrace-image.sh failed; see $WORK/evidence/build-hwtrace-$(short).log"
  [ -s "$tmp/out/$name" ] && [ -s "$tmp/out/$name.sha256" ] || fail "no $name with its .sha256 in $tmp/out"
  mkdir -p "$ASSETS_DIR"
  cp "$tmp/out/$name" "$tmp/out/$name.sha256" "$ASSETS_DIR/"
  rm -rf "$tmp"
  echo "hwtrace: $ASSETS_DIR/$name $(wc -c <"$ASSETS_DIR/$name" | tr -d ' ') bytes, $(cat "$ASSETS_DIR/$name.sha256")"
  state_mark hwtrace
}

qa_split() {
  split_selection
  local qa_arch tmp remote_dir manifest_name name qa_status=0 files=()
  [[ $QA_DIR == /* && $QA_DIR != *$'\n'* ]] || fail 'split QA requires an absolute QA_DIR without newlines'
  case ${ARCH:-amd64} in amd64) qa_arch=x86_64 ;; aarch64) qa_arch=aarch64 ;; esac
  if $DRY_RUN; then
    echo "+ verify pinned split $MEDIA_MANIFEST; transfer exact parts and transport tools to a new private QA directory; reconstruct; ARCH=$qa_arch test-qemu.sh with the desktop check"
    return 0
  fi
  tmp=$(mktemp -d "$WORK/master-qa.XXXXXX")
  master_python "$here/scripts/master-media.py" "$MEDIA_MANIFEST" --sha256 "$MEDIA_MANIFEST_SHA256" \
    --image "$SELECTED_NAME" >"$tmp/verified.json" || fail "split QA input failed; retained $tmp"
  manifest_name=$(basename "$MEDIA_MANIFEST")
  files+=("$manifest_name" "$manifest_name.sha256")
  while IFS= read -r name; do files+=("$name"); done < <(jq -r '.parts[].name' "$tmp/verified.json")
  remote_dir=$(ssh "$QA_USER@$QA_HOST" "umask 077; mktemp -d $(shell_quote "$QA_DIR.split.XXXXXX")") || fail 'cannot create private QA directory'
  [[ $remote_dir == "$QA_DIR.split."* && $remote_dir != *$'\n'* ]] || fail 'unexpected QA directory reply'
  printf '%s\n' "$remote_dir" >"$tmp/remote-directory.txt"
  echo "split QA evidence retained in $tmp and $QA_HOST:$remote_dir"
  ssh "$QA_USER@$QA_HOST" "mkdir $(shell_quote "$remote_dir/repo") $(shell_quote "$remote_dir/transport-tools")"
  tar -cf - -C "$WORK/product-$(short)" . | ssh "$QA_USER@$QA_HOST" "tar -xf - -C $(shell_quote "$remote_dir/repo")"
  tar -cf - -C "$here/scripts" master-media.py split-media.py | ssh "$QA_USER@$QA_HOST" "tar -xf - -C $(shell_quote "$remote_dir/transport-tools")"
  tar -cf - -C "$(dirname "$MEDIA_MANIFEST")" "${files[@]}" | ssh "$QA_USER@$QA_HOST" "tar -xf - -C $(shell_quote "$remote_dir")"
  ssh "$QA_USER@$QA_HOST" "sh -s -- $(shell_quote "$remote_dir") $(shell_quote "$MEDIA_MANIFEST_SHA256") $(shell_quote "$SELECTED_NAME") $(shell_quote "$qa_arch") $(shell_quote "$PACKAGE_REPOSITORY_TAG") $(shell_quote "$QA_VIRGL_RENDER_NODE")" <<'REMOTE_SPLIT_QA' || qa_status=$?
set -eu
root=$1 pin=$2 image=$3 arch=$4 feed=$5 render=$6
if command -v python3 >/dev/null; then qa_python=python3; else qa_python=python3.12; fi
"$qa_python" "$root/transport-tools/master-media.py" "$root/$image.parts.json.xz" --sha256 "$pin" \
  --image "$image" --out "$root/$image" >"$root/reconstructed.json"
cd "$root/repo"
env ARCH="$arch" EXPECTED_PACKAGE_REPOSITORY_TAG="$feed" \
  POST_INSTALL_CHECK="$root/repo/tests/qemu-desktop.py" VIRGL_RENDER_NODE="$render" \
  WORK="$root/work" sh ./test-qemu.sh "$root/$image"
REMOTE_SPLIT_QA
  [ "$qa_status" -eq 0 ] || fail "split QEMU QA failed ($qa_status); retained $remote_dir"
  state_mark qa
}

step_qa() {
  step_enabled qa || return 0
  [ -z "$MEDIA_MANIFEST" ] || split_selection
  fetch_product
  local product=$WORK/product-$(short) out=$WORK/out-$(short) xz
  if [ -n "$MEDIA_MANIFEST" ]; then qa_split; return; fi
  run ssh "$QA_USER@$QA_HOST" "rm -rf $QA_DIR && mkdir -p $QA_DIR"
  if $DRY_RUN; then
    echo "+ scp image and $product to $QA_HOST:$QA_DIR; test-qemu.sh with EXPECTED_PACKAGE_REPOSITORY_TAG=$PACKAGE_REPOSITORY_TAG POST_INSTALL_CHECK=$QA_DIR/repo/tests/qemu-desktop.py VIRGL_RENDER_NODE=$QA_VIRGL_RENDER_NODE"
    return 0
  fi
  xz=$(ls "$out"/*.iso.xz | head -1)
  scp -q "$xz" "$QA_USER@$QA_HOST:$QA_DIR/"
  tar -cf - -C "$product" . | ssh "$QA_USER@$QA_HOST" "mkdir -p $QA_DIR/repo && tar -xf - -C $QA_DIR/repo"
  ssh "$QA_USER@$QA_HOST" "cd $QA_DIR && xz -dk $(basename "$xz") && cd repo && \
      EXPECTED_PACKAGE_REPOSITORY_TAG=$PACKAGE_REPOSITORY_TAG POST_INSTALL_CHECK=$QA_DIR/repo/tests/qemu-desktop.py VIRGL_RENDER_NODE=$QA_VIRGL_RENDER_NODE \
      WORK=$QA_DIR/work sh ./test-qemu.sh ../$(basename "${xz%.xz}")" || fail 'QEMU QA failed'
  state_mark qa
}

# ---- sticks --------------------------------------------------------------------------
# Echo "SIZE_BYTES TRAN SERIAL TYPE" for one device, or fail.
stick_info() {
  local dev=$1 name line
  name=${dev#/dev/}
  line=$("$LSBLK" -dnbo NAME,SIZE,TRAN,SERIAL,TYPE "/dev/$name" 2>/dev/null) || return 1
  [ -n "$line" ] || return 1
  # NAME SIZE TRAN SERIAL TYPE (SERIAL may be empty: collapse by position from the ends)
  set -- $line
  local n=$#
  local size=$2 tran=$3 serial=- type
  type=${!n}
  if [ "$n" -ge 5 ]; then serial=$4; fi
  echo "$size $tran $serial $type"
}

stick_check() {
  local dev=$1 want_serial=$2 raw_size=$3 info size tran serial type s
  [[ $dev =~ ^/dev/(sd[a-z]+|nvme[0-9]+n[0-9]+|mmcblk[0-9]+)$ ]] || fail "$dev is not a whole-disk device path (no partitions)"
  info=$(stick_info "$dev") || fail "cannot read $dev (is it attached?)"
  read -r size tran serial type <<<"$info"
  [ "$type" = disk ] || fail "$dev is a $type, not a whole disk"
  [ "$tran" = usb ] || fail "$dev is not a USB device (transport '$tran')"
  for s in $DENY_SERIALS; do [ "$serial" != "$s" ] || fail "$dev is on the deny list (serial $serial): never written"; done
  [ "$size" -le "$STICK_MAX_BYTES" ] || fail "$dev is $size bytes, over the $STICK_MAX_BYTES limit for a stick"
  [ "$size" -ge "$raw_size" ] || fail "$dev is $size bytes, smaller than the $raw_size byte image"
  [ "$serial" = "$want_serial" ] || fail "$dev has serial '$serial', not the '$want_serial' you named"
  if grep -qE "^${dev}[0-9p]* " /proc/mounts 2>/dev/null || mount 2>/dev/null | grep -E "^${dev}[0-9p]* " >/dev/null; then
    fail "$dev has a mounted filesystem; unmount it first"
  fi
}

sha256_of() { if command -v sha256sum >/dev/null; then sha256sum | cut -d' ' -f1; else sha256 -q; fi; }

step_sticks() {
  local iso='' manifest='' manifest_pin='' raw_sha='' raw_size='' devices=() spec raw_source='' tmp='' verified image_name
  while [ $# -gt 0 ]; do
    case $1 in
      --iso) iso=$2; shift 2 ;;
      --manifest) manifest=$2; shift 2 ;;
      --manifest-sha256) manifest_pin=$2; shift 2 ;;
      --raw-sha256) raw_sha=$2; shift 2 ;;
      --raw-size) raw_size=$2; shift 2 ;;
      --device) devices+=("$2"); shift 2 ;;
      *) fail "sticks: unknown option $1" ;;
    esac
  done
  if [ -n "$manifest" ]; then
    [ -z "$iso" ] || fail 'sticks: choose exactly one --iso or --manifest'
    [[ $manifest_pin =~ ^[0-9a-f]{64}$ ]] || fail 'sticks: --manifest-sha256 is required'
  else
    [ -z "$manifest_pin" ] || fail 'sticks: --manifest-sha256 requires --manifest'
    [ -f "$iso" ] || fail 'sticks: --iso FILE.iso.xz or --manifest FILE.parts.json.xz is required'
  fi
  [[ $raw_sha =~ ^[0-9a-f]{64}$ ]] || fail 'sticks: --raw-sha256 must be the 64-hex digest of the decompressed image'
  [[ $raw_size =~ ^[0-9]+$ ]] || fail 'sticks: --raw-size must be the image size in bytes'
  [ "${#devices[@]}" -gt 0 ] || fail 'sticks: name at least one --device /dev/sdX:SERIAL'
  for spec in "${devices[@]}"; do
    [[ $spec == /dev/*:* ]] || fail "sticks: '$spec' is not /dev/NAME:SERIAL"
    stick_check "${spec%%:*}" "${spec#*:}" "$raw_size"
  done
  if [ -n "$manifest" ]; then
    image_name=$(basename "${manifest%.parts.json.xz}")
    verified=$(master_python "$here/scripts/master-media.py" "$manifest" --sha256 "$manifest_pin" --image "$image_name") \
      || fail 'sticks: split media verification failed before writes'
    [ "$(jq -r '.image.sha256' <<<"$verified")" = "$raw_sha" ] && \
      [ "$(jq -r '.image.bytes' <<<"$verified")" = "$raw_size" ] || fail 'sticks: selected raw identity differs from the manifest'
    if $DRY_RUN; then
      raw_source=PRIVATE_RECONSTRUCTED_IMAGE
      echo '+ reconstruct verified split media in a new private directory before writing'
    else
      tmp=$(mktemp -d "${TMPDIR:-/tmp}/daemonarchy-sticks.XXXXXX")
      raw_source=$tmp/$image_name
      master_python "$here/scripts/master-media.py" "$manifest" --sha256 "$manifest_pin" --image "$image_name" \
        --out "$raw_source" >"$tmp/reconstructed.json" || fail "sticks: reconstruction failed; retained $tmp"
    fi
  else
    xz -t "$iso" || fail 'the image is damaged'
  fi
  echo "== writing ${#devices[@]} stick(s); every named device passed the safety checks"
  for spec in "${devices[@]}"; do
    local dev=${spec%%:*}
    if [ -n "$manifest" ]; then
      run sudo dd "if=$raw_source" "of=$dev" bs=4M iflag=fullblock conv=fsync status=none
    else
      if $DRY_RUN; then
        printf '+ xz -dc %q | sudo dd of=%q bs=4M iflag=fullblock conv=fsync status=none\n' "$iso" "$dev"
      else
        xz -dc "$iso" | sudo dd "of=$dev" bs=4M iflag=fullblock conv=fsync status=none
      fi
    fi
    run sync
    if ! $DRY_RUN; then
      local got
      got=$(sudo head -c "$raw_size" "$dev" | sha256_of)
      [ "$got" = "$raw_sha" ] || fail "$dev read back $got, not $raw_sha"
      echo "$dev: written and verified ($raw_sha)"
    fi
  done
  [ -z "$tmp" ] || echo "sticks: verified reconstruction/evidence retained in $tmp"
  state_mark "sticks"
}

main() {
  local steps=()
  while [ $# -gt 0 ]; do
    case $1 in
      --dry-run) DRY_RUN=true; shift ;;
      --force) FORCE=true; shift ;;
      --config) CONFIG=$2; shift 2 ;;
      sticks) shift; [ -z "$CONFIG" ] || . "$CONFIG"; STATE=${STATE:-$WORK/master-state.tsv}; step_sticks "$@"; return ;;
      -h | --help | help) sed -n '2,32p' "$0"; return 0 ;;
      *) steps+=("$1"); shift ;;
    esac
  done
  # shellcheck disable=SC1090
  [ -z "$CONFIG" ] || . "$CONFIG"
  # Defaults that follow the tag or the work directory come after the config, which sets them.
  STATE=${STATE:-$WORK/master-state.tsv}
  FEED_OUT=${FEED_OUT:-$WORK/feed-$PACKAGE_REPOSITORY_TAG}
  # A release image carries its closure feed (PKG-002): the installer prefers it to pkg.FreeBSD.org, and
  # build-iso.sh refuses the build unless that feed resolves the installer's packages on its own.
  # The closure shard is named explicitly (CLOSURE_SHARD_TAG): an application tag, plain or with a revision suffix, does not name one.
  PACKAGE_MIRROR_URLS=${PACKAGE_MIRROR_URLS:-https://github.com/jordanhubbard/daemonarchy/releases/download/$CLOSURE_SHARD_TAG}
  [ "${#steps[@]}" -gt 0 ] || { sed -n '2,32p' "$0" >&2; exit 2; }
  local s
  for s in "${steps[@]}"; do
    case $s in
      all) step_preflight; step_packages; step_secureboot; step_feed; step_resolve; step_catalogue; step_iso; step_verify; step_hwtrace; step_qa ;;
      status) [ -f "$STATE" ] && cat "$STATE" || echo 'no state yet' ;;
      preflight | packages | secureboot | feed | resolve | catalogue | iso | inspect | verify | hwtrace | qa) "step_$s" ;;
      *) fail "unknown step: $s" ;;
    esac
  done
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi
