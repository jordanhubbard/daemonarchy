#!/usr/local/bin/bash
# Build the amd64 release packages that must change with a new kernel or a new
# Daemonarchy/Omarchy version, without rebuilding the retained userland.
#
#   build-release-packages.sh origins   write the bulk origins list from origins.sh
#   build-release-packages.sh seed      new package set: hard links of the previous
#                                       release's, minus what must be rebuilt
#   build-release-packages.sh plan      poudriere dry run: what would be built, deleted
#   build-release-packages.sh bulk      the real poudriere bulk (long; run it detached)
#   build-release-packages.sh built     write BUILT_PACKAGES_FILE for pkg-repo.sh collect
#   build-release-packages.sh identity  old/new kernel-bound module hashes (KBI evidence)
#   build-release-packages.sh must-rebuild ORIGIN   exit 0 if ORIGIN is rebuilt
#
# Run as root on the amd64 builder. Why it is not a plain `poudriere bulk`: the
# retained 1.4.0 set holds builds (chromium, cef, ...) made against an older
# harfbuzz than the pinned ports tree carries. A plain bulk would call them stale
# and rebuild chromium. `-S` stops that recursion; the Omarchy ports that were
# newer than the tree come from an overlay (`-O`), exactly as in 1.4.0.
#
# Kernel-bound packages (modules, firmware, the NVIDIA stack) are rebuilt for every
# new kernel even when the module sources did not change, so that the evidence of
# what they were built against is the new jail.
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
WORK=${WORK:-/usr/daemonarchy/rev2-20261030}
JAIL=${JAIL:-16r2303b36}
PTREE=${PTREE:-daports141}
OVERLAY=${OVERLAY:-daports31}
FROM_SET=${FROM_SET:-16r2303b36-macbookefb8}          # previous release's package set name
POUDRIERE_ETC=${POUDRIERE_ETC:-$WORK/poudriere-etc}
POUDRIERE_DATA=${POUDRIERE_DATA:-$WORK/poudriere-data}
ORIGINS_FILE=${ORIGINS_FILE:-$WORK/origins-141.txt}
PREVIOUS_BUILT=${PREVIOUS_BUILT:-}                      # the previous release's BUILT_PACKAGES_FILE
BUILT_OUT=${BUILT_OUT:-$WORK/built-141.txt}
EVIDENCE=${EVIDENCE:-$WORK/evidence}
packages_dir() { echo "$POUDRIERE_DATA/packages/$JAIL-$PTREE"; }

# Origins whose packages are tied to the kernel, or are the ones this release changes.
must_rebuild_origin() {
  case $1 in
    x11-wm/daemonarchy | x11-wm/omarchy | x11/linux-nvidia-libs | x11/nvidia-driver | x11/nvidia-kmod) return 0 ;;
    graphics/nvidia-drm* | *kmod*) return 0 ;;
    *) return 1 ;;
  esac
}

cmd_origins() {
  # shellcheck disable=SC1091
  . "$here/origins.sh"
  for origin in $ISO_ORIGINS $LIVE_ORIGINS; do echo "$origin"; done | sort -u >"$ORIGINS_FILE"
  echo "$ORIGINS_FILE: $(wc -l <"$ORIGINS_FILE" | tr -d ' ') origins"
}

cmd_seed() {
  local src dst real list n=0 repopath origin
  src=$POUDRIERE_DATA/packages/$FROM_SET
  dst=$(packages_dir)
  [ -d "$src" ] || { echo "No previous package set at $src" >&2; exit 1; }
  [ ! -e "$dst" ] || { echo "$dst already exists; remove it deliberately to reseed" >&2; exit 1; }
  cp -Rpl "$src" "$dst"
  real=$(readlink "$dst/.latest")
  list=$(mktemp)
  tar -xOf "$src/packagesite.pkg" packagesite.yaml | jq -r '[.origin, .repopath] | @tsv' >"$list"
  while IFS=$'\t' read -r origin repopath; do
    if must_rebuild_origin "$origin"; then
      rm -f "$dst/$real/$repopath"
      n=$((n + 1))
    fi
  done <"$list"
  rm -f "$list"
  echo "$dst: removed $n packages to rebuild; $(ls "$dst/$real/All" | wc -l | tr -d ' ') retained"
}

cmd_plan() {
  mkdir -p "$EVIDENCE"
  poudriere -e "$POUDRIERE_ETC" bulk -n -S -O "$OVERLAY" -b latest -j "$JAIL" -p "$PTREE" -f "$ORIGINS_FILE" \
    | tee "$EVIDENCE/bulk-plan.log" | grep -E 'Deleting|Would build|Ports to build' | cut -c1-220
}

cmd_bulk() {
  mkdir -p "$EVIDENCE"
  date -u '+start %Y-%m-%dT%H:%M:%SZ' >"$EVIDENCE/bulk.times"
  local code=0
  poudriere -e "$POUDRIERE_ETC" bulk -S -O "$OVERLAY" -b latest -j "$JAIL" -p "$PTREE" -f "$ORIGINS_FILE" \
    >"$EVIDENCE/bulk.log" 2>&1 || code=$?
  date -u '+end %Y-%m-%dT%H:%M:%SZ' >>"$EVIDENCE/bulk.times"
  echo "$code" >"$EVIDENCE/bulk.exit"
  return "$code"
}

cmd_built() {
  local logroot records
  logroot=$POUDRIERE_DATA/logs/bulk/$JAIL-$PTREE
  # Every bulk run for this set (a second pass after a fix counts): their records are a union.
  records=$(ls "$logroot"/20*/.poudriere.ports.built 2>/dev/null || true)
  [ -n "$records" ] || { echo "No successful-build records under $logroot" >&2; exit 1; }
  { [ -z "$PREVIOUS_BUILT" ] || cat "$PREVIOUS_BUILT"; cat $records; } \
    | awk 'NF >= 2 { print $1, $2 }' | sort -u >"$BUILT_OUT"
  # A package superseded in this run leaves the old name behind: keep only names present in the set.
  local keep
  keep=$(mktemp)
  while read -r origin name; do
    [ -e "$(packages_dir)/All/$name.pkg" ] && echo "$origin $name"
  done <"$BUILT_OUT" >"$keep" || true
  mv "$keep" "$BUILT_OUT"
  echo "$BUILT_OUT: $(wc -l <"$BUILT_OUT" | tr -d ' ') built packages present in the set"
}

# Old and new kernel-bound packages side by side: identical module hashes mean the
# rebuild reproduced the previous modules bit for bit; different ones need the Secure
# Boot module inventory regenerated and the boot bundle re-signed.
cmd_identity() {
  local old new out f name oldf oldsha newsha same=0 diff=0 added=0
  old=$POUDRIERE_DATA/packages/$FROM_SET/All
  new=$(packages_dir)/All
  out=$EVIDENCE/kmod-identity.tsv
  mkdir -p "$EVIDENCE"
  printf 'package\tmodule\told_sha256\tnew_sha256\tresult\n' >"$out"
  for f in "$new"/*.pkg; do
    name=$(basename "$f")
    pkg query -F "$f" '%Fp' 2>/dev/null | grep -q '^/boot/modules/.*\.ko$' || continue
    # The same file name in the previous set if there is one (same version), else the previous version.
    if [ -e "$old/$name" ]; then oldf=$old/$name
    else oldf=$(ls "$old"/"${name%%-[0-9]*}"-[0-9]*.pkg 2>/dev/null | head -1 || true); fi
    while read -r path; do
      newsha=$(tar -xOf "$f" "$path" 2>/dev/null | sha256 -q)
      oldsha=-
      [ -z "$oldf" ] || oldsha=$(tar -xOf "$oldf" "$path" 2>/dev/null | sha256 -q || echo -)
      if [ "$oldsha" = - ]; then result=new; added=$((added + 1))
      elif [ "$oldsha" = "$newsha" ]; then result=identical; same=$((same + 1))
      else result=DIFFERENT; diff=$((diff + 1)); fi
      printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$path" "$oldsha" "$newsha" "$result" >>"$out"
    done < <(pkg query -F "$f" '%Fp' | grep '^/boot/modules/.*\.ko$')
  done
  echo "$out: $same identical, $diff different, $added new modules"
  [ "$diff" -eq 0 ] || echo "Modules changed: regenerate the Secure Boot module inventory and re-sign the boot bundle." >&2
}

main() {
  case ${1:-} in
    origins) cmd_origins ;;
    seed) cmd_seed ;;
    plan) cmd_plan ;;
    bulk) cmd_bulk ;;
    built) cmd_built ;;
    identity) cmd_identity ;;
    must-rebuild) must_rebuild_origin "${2:?origin}" ;;
    *) sed -n '2,20p' "$0" >&2; exit 2 ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi
