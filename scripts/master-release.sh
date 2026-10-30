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
#   verify      xz test, hashes, size budget, version string, ISO contents (builder)
#   qa          copy the ISO to QA_HOST and run test-qemu.sh there      (QA host, ~35 min)
#   sticks      write the ISO to the named USB sticks and verify by read-back (workstation)
#   all         preflight packages secureboot feed resolve catalogue iso verify qa  (never sticks, never publishes)
#   status      print the state file
#
# Nothing here uploads to GitHub or signs with a release key except `feed`, which signs
# on the builder with the key already there. Publishing is a separate, approved step.
#
# sticks takes explicit devices, each with the serial the operator read from the machine:
#   master-release.sh sticks --iso FILE.iso.xz --raw-sha256 HEX --raw-size N \
#       --device /dev/sdb:SERIAL --device /dev/sdc:SERIAL
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
CHECKOUT_CATALOG=${CHECKOUT_CATALOG:-$WORK/checkout-feed-1.4.1/checkouts.json}
SOURCE_REVISION=${SOURCE_REVISION:-303b3646270ffa4bf7cec65c5c1d28bd8000cbce}
PORTS_REVISION=${PORTS_REVISION:-b785784219af455a9ce4fd70c59bc96ba77f469f}
PACKAGE_REPOSITORY_TAG=${PACKAGE_REPOSITORY_TAG:-packages-16-amd64-1.4.1}
SECUREBOOT_BUNDLE=${SECUREBOOT_BUNDLE:-/usr/daemonarchy/sb16/daemonarchy-1.4.1-boot.txz}
SECUREBOOT_CERTIFICATE=${SECUREBOOT_CERTIFICATE:-/usr/daemonarchy/boot-replacement-candidate-public-20261024/daemonarchy-1.3.1.pem}
SIGN_KEY=${SIGN_KEY:-/usr/local/etc/daemonarchy/pkg-repo-next.key}
BUILT_PACKAGES_FILE=${BUILT_PACKAGES_FILE:-$WORK/built-141.txt}
FEED_OUT=${FEED_OUT:-$WORK/feed-$PACKAGE_REPOSITORY_TAG}
CLOSURE_DIR=${CLOSURE_DIR:-/tmp/closure/out/packages-16-amd64-1.4.1-upstream}
SB_DIR=${SB_DIR:-/usr/daemonarchy/sb16}
XZ_BUDGET=${XZ_BUDGET:-2147483648}                # a GitHub release asset must stay under 2 GiB
QA_HOST=${QA_HOST:-madmax.local}
QA_USER=${QA_USER:-jkh}
QA_DIR=${QA_DIR:-/tmp/daemonarchy-qa}
STICK_MAX_BYTES=${STICK_MAX_BYTES:-137438953472}  # 128 GiB: refuses the 239 GB scratch disk and anything larger
DENY_SERIALS=${DENY_SERIALS:-03A0423110011698}    # sda "toolscratch" (Samsung, 239 GB): never written
LSBLK=${LSBLK:-lsblk}
STATE=${STATE:-$WORK/master-state.tsv}

fail() { echo "master-release: $*" >&2; exit 1; }

run() {
  printf '+ %s\n' "$*"
  $DRY_RUN || "$@"
}

short() { printf '%s' "${MAIN_COMMIT:0:12}"; }

# ---- state: each step records when it last succeeded, so a rerun resumes -------------
state_mark() { $DRY_RUN || { mkdir -p "$(dirname "$STATE")"; printf '%s\t%s\t%s\n' "$1" "ok" "$(date -u +%FT%TZ)" >>"$STATE"; }; }
state_done() { [ -f "$STATE" ] && grep -q "^$1	ok	" "$STATE"; }
step_enabled() {
  # Skip a step already done unless --force; a dry run always shows it.
  if ! $FORCE && ! $DRY_RUN && state_done "$1"; then echo "== $1: done before (use --force to redo)"; return 1; fi
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
  run "$product/scripts/check-install-resolution.sh" "$WORK/poudriere-data/packages/$JAIL-$PTREE" "$FEED_OUT" "$CLOSURE_DIR" all
  state_mark resolve
}

step_feed() {
  step_enabled feed || return 0
  fetch_product
  local product=$WORK/product-$(short) plan=$FEED_OUT.plan.txt
  run env ARCH=amd64 JAIL="$JAIL" PTREE="$PTREE" TAG="$PACKAGE_REPOSITORY_TAG" KEY="$SIGN_KEY" OUT="$FEED_OUT" \
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
    echo "+ (cd $product && env JAIL=$JAIL PTREE=$PTREE ... sh ./build-iso.sh)"
    return 0
  fi
  ( cd "$product" && env \
      JAIL="$JAIL" PTREE="$PTREE" \
      POUDRIERE_ETC="$WORK/poudriere-etc" POUDRIERE_DATA="$WORK/poudriere-data" \
      PACKAGES_DIR="$WORK/poudriere-data/packages/$JAIL-$PTREE" \
      SET_CACHE_DIR="$SET_CACHE_DIR" OUTDIR="$out" ISO_STAGE_PARENT="$WORK/stage" \
      CHECKOUT_CATALOG="$CHECKOUT_CATALOG" \
      PACKAGE_REPOSITORY_TAG="$PACKAGE_REPOSITORY_TAG" \
      PACKAGE_REPOSITORY_PUBLIC_KEY="$product/keys/pkg-repo-1.3.1.pub" \
      SECUREBOOT_BUNDLE="$SECUREBOOT_BUNDLE" SECUREBOOT_SIGNATURE="$SECUREBOOT_BUNDLE.sig" \
      SECUREBOOT_CERTIFICATE="$SECUREBOOT_CERTIFICATE" \
      sh ./build-iso.sh ) >"$WORK/evidence/build-iso-$(short).log" 2>&1 || fail "build-iso.sh failed; see $WORK/evidence/build-iso-$(short).log"
  state_mark iso
}

step_verify() {
  step_enabled verify || return 0
  local out=$WORK/out-$(short) xz iso want got size version
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
  version=$(tr -d '[:space:]' <"$here/VERSION")
  if command -v bsdtar >/dev/null; then
    [ "$(bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/version 2>/dev/null | head -1)" = "$version" ] \
      || fail "the image's installer version is not $version"
  else
    echo "bsdtar not found: image version not checked" >&2
  fi
  state_mark verify
}

step_qa() {
  step_enabled qa || return 0
  fetch_product
  local product=$WORK/product-$(short) out=$WORK/out-$(short) xz
  run ssh "$QA_USER@$QA_HOST" "rm -rf $QA_DIR && mkdir -p $QA_DIR"
  if $DRY_RUN; then
    echo "+ scp image and $product to $QA_HOST:$QA_DIR; test-qemu.sh with EXPECTED_PACKAGE_REPOSITORY_TAG=$PACKAGE_REPOSITORY_TAG POST_INSTALL_CHECK=tests/qemu-desktop.py"
    return 0
  fi
  xz=$(ls "$out"/*.iso.xz | head -1)
  scp -q "$xz" "$QA_USER@$QA_HOST:$QA_DIR/"
  tar -cf - -C "$product" . | ssh "$QA_USER@$QA_HOST" "mkdir -p $QA_DIR/repo && tar -xf - -C $QA_DIR/repo"
  ssh "$QA_USER@$QA_HOST" "cd $QA_DIR && xz -dk $(basename "$xz") && cd repo && \
      EXPECTED_PACKAGE_REPOSITORY_TAG=$PACKAGE_REPOSITORY_TAG POST_INSTALL_CHECK=tests/qemu-desktop.py \
      WORK=$QA_DIR/work sh ./test-qemu.sh ../$(basename "${xz%.xz}")" || fail 'QEMU QA failed'
  state_mark qa
}

# ---- sticks --------------------------------------------------------------------------
# Echo "SIZE_BYTES TRAN SERIAL TYPE" for one device, or fail.
stick_info() {
  local dev=$1 name line
  name=${dev#/dev/}
  line=$($LSBLK -dnbo NAME,SIZE,TRAN,SERIAL,TYPE "/dev/$name" 2>/dev/null) || return 1
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
  if grep -qE "^$dev[0-9p]* " /proc/mounts 2>/dev/null || mount 2>/dev/null | grep -qE "^$dev[0-9p]* "; then
    fail "$dev has a mounted filesystem; unmount it first"
  fi
}

sha256_of() { if command -v sha256sum >/dev/null; then sha256sum | cut -d' ' -f1; else sha256 -q; fi; }

step_sticks() {
  local iso='' raw_sha='' raw_size='' devices=() spec
  while [ $# -gt 0 ]; do
    case $1 in
      --iso) iso=$2; shift 2 ;;
      --raw-sha256) raw_sha=$2; shift 2 ;;
      --raw-size) raw_size=$2; shift 2 ;;
      --device) devices+=("$2"); shift 2 ;;
      *) fail "sticks: unknown option $1" ;;
    esac
  done
  [ -f "$iso" ] || fail 'sticks: --iso FILE.iso.xz is required'
  [[ $raw_sha =~ ^[0-9a-f]{64}$ ]] || fail 'sticks: --raw-sha256 must be the 64-hex digest of the decompressed image'
  [[ $raw_size =~ ^[0-9]+$ ]] || fail 'sticks: --raw-size must be the image size in bytes'
  [ "${#devices[@]}" -gt 0 ] || fail 'sticks: name at least one --device /dev/sdX:SERIAL'
  for spec in "${devices[@]}"; do
    [[ $spec == /dev/*:* ]] || fail "sticks: '$spec' is not /dev/NAME:SERIAL"
    stick_check "${spec%%:*}" "${spec#*:}" "$raw_size"
  done
  xz -t "$iso" || fail 'the image is damaged'
  echo "== writing ${#devices[@]} stick(s); every named device passed the safety checks"
  for spec in "${devices[@]}"; do
    local dev=${spec%%:*}
    run sh -c "xz -dc '$iso' | sudo dd of='$dev' bs=4M iflag=fullblock conv=fsync status=none"
    run sync
    if ! $DRY_RUN; then
      local got
      got=$(sudo head -c "$raw_size" "$dev" | sha256_of)
      [ "$got" = "$raw_sha" ] || fail "$dev read back $got, not $raw_sha"
      echo "$dev: written and verified ($raw_sha)"
    fi
  done
  state_mark "sticks"
}

main() {
  local steps=()
  while [ $# -gt 0 ]; do
    case $1 in
      --dry-run) DRY_RUN=true; shift ;;
      --force) FORCE=true; shift ;;
      --config) CONFIG=$2; shift 2 ;;
      sticks) shift; [ -z "$CONFIG" ] || . "$CONFIG"; step_sticks "$@"; return ;;
      -h | --help | help) sed -n '2,32p' "$0"; return 0 ;;
      *) steps+=("$1"); shift ;;
    esac
  done
  # shellcheck disable=SC1090
  [ -z "$CONFIG" ] || . "$CONFIG"
  [ "${#steps[@]}" -gt 0 ] || { sed -n '2,32p' "$0" >&2; exit 2; }
  local s
  for s in "${steps[@]}"; do
    case $s in
      all) step_preflight; step_packages; step_secureboot; step_feed; step_resolve; step_catalogue; step_iso; step_verify; step_qa ;;
      status) [ -f "$STATE" ] && cat "$STATE" || echo 'no state yet' ;;
      preflight | packages | secureboot | feed | resolve | catalogue | iso | verify | qa) "step_$s" ;;
      *) fail "unknown step: $s" ;;
    esac
  done
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi
