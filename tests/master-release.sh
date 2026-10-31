#!/usr/bin/env bash
# The mastering runbook: dry run shows every step, and the stick writer refuses unsafe devices.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
script=$here/scripts/master-release.sh
bash -n "$script"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
commit=0123456789abcdef0123456789abcdef01234567

# --- dry run: every step is shown, nothing runs or is created --------------------------
out=$(WORK=$work/w MAIN_COMMIT=$commit bash "$script" --dry-run preflight packages secureboot feed resolve catalogue iso verify qa 2>&1)
for expect in '== packages' 'build-release-packages.sh' ' seed' ' bulk' ' identity' '== feed' 'pkg-repo.sh' \
              '== secureboot' 'resign-boot-bundle.sh' '== resolve' 'check-install-resolution.sh' '== catalogue' '== iso' 'build-iso.sh' '== verify' '== qa' 'test-qemu.sh' \
              "EXPECTED_PACKAGE_REPOSITORY_TAG=packages-16-amd64-1.5.0" \
              "POST_INSTALL_CHECK=/tmp/daemonarchy-qa/repo/tests/qemu-desktop.py" \
              "PACKAGE_MIRROR_URLS=https://github.com/jordanhubbard/daemonarchy/releases/download/packages-16-amd64-1.4.1-upstream" \
              "REQUIRE_PACKAGE_MIRROR=yes" "VIRGL_RENDER_NODE=/dev/dri/renderD128"; do
  grep -qF -- "$expect" <<<"$out" || { echo "dry run is missing '$expect'" >&2; echo "$out" >&2; exit 1; }
done
[[ ! -e $work/w ]]
# A revision tag set by the config names its own feed directory and keeps the release's closure shard.
printf 'PACKAGE_REPOSITORY_TAG=packages-16-amd64-1.4.1-r2\n' >"$work/r2.env"
out=$(WORK=$work/w MAIN_COMMIT=$commit bash "$script" --config "$work/r2.env" --dry-run feed iso 2>&1)
for expect in "OUT=$work/w/feed-packages-16-amd64-1.4.1-r2 " "TAG=packages-16-amd64-1.4.1-r2" \
              "PACKAGE_MIRROR_URLS=https://github.com/jordanhubbard/daemonarchy/releases/download/packages-16-amd64-1.4.1-upstream"; do
  grep -qF -- "$expect" <<<"$out" || { echo "r2 dry run is missing '$expect'" >&2; echo "$out" >&2; exit 1; }
done
# A feed step never empties a directory that already holds a staged feed.
mkdir -p "$work/w/feed-packages-16-amd64-1.4.1-r2" && : >"$work/w/feed-packages-16-amd64-1.4.1-r2/x.pkg"
refused=$(WORK=$work/w MAIN_COMMIT=$commit bash "$script" --config "$work/r2.env" feed 2>&1 || true)
grep -qF 'already holds a staged feed' <<<"$refused" || { echo "feed did not refuse a staged directory: $refused" >&2; exit 1; }
[[ -e $work/w/feed-packages-16-amd64-1.4.1-r2/x.pkg ]]
rm -rf "$work/w"
# A bad commit is refused before anything else.
! MAIN_COMMIT=nothex WORK=$work/w bash "$script" preflight >/dev/null 2>&1
! bash "$script" bogus >/dev/null 2>&1

# --- sticks -----------------------------------------------------------------------------
# A fake lsblk: name -> "NAME SIZE TRAN SERIAL TYPE".
cat >"$work/lsblk" <<'EOF'
#!/bin/sh
for last; do :; done
case $last in
  /dev/sdb) echo 'sdb 125829120000 usb GOODSERIAL1 disk' ;;
  /dev/sdc) echo 'sdc 8053063680 usb GOODSERIAL2 disk' ;;
  /dev/sdd) echo 'sdd 125829120000 sata SATASERIAL disk' ;;
  /dev/sda) echo 'sda 256060514304 usb 03A0423110011698 disk' ;;
  /dev/sde) echo 'sde 1000000 usb TINYSERIAL disk' ;;
  /dev/sdf) echo 'sdf 125829120000 usb GOODSERIAL3 part' ;;
  /dev/sdg) echo 'sdg 500107862016 usb BIGSERIAL disk' ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$work/lsblk"
printf 'daemonarchy test image\n' | xz -c >"$work/image.iso.xz"
sha=$(printf 'x' | sha256sum | cut -d' ' -f1)
refuse() {
  local why=$1; shift
  if LSBLK=$work/lsblk STATE=$work/state bash "$script" --dry-run sticks --iso "$work/image.iso.xz" \
       --raw-sha256 "$sha" --raw-size 3553460224 "$@" >"$work/refused" 2>&1; then
    echo "accepted ($why): $*" >&2; cat "$work/refused" >&2; exit 1
  fi
  grep -q "$why" "$work/refused" || { echo "wrong refusal for $*: wanted '$why'" >&2; cat "$work/refused" >&2; exit 1; }
}
refuse 'deny list' --device /dev/sda:03A0423110011698
refuse 'not a USB' --device /dev/sdd:SATASERIAL
refuse 'smaller than' --device /dev/sde:TINYSERIAL
refuse 'not a whole disk' --device /dev/sdf:GOODSERIAL3
refuse 'over the' --device /dev/sdg:BIGSERIAL
refuse "not the 'WRONG' you named" --device /dev/sdc:WRONG
refuse 'whole-disk device path' --device /dev/sdb1:GOODSERIAL1
refuse 'cannot read' --device /dev/sdx:NOPE
refuse 'at least one'
refuse '/dev/NAME:SERIAL' --device sdb:GOODSERIAL1
# One bad device in the list stops the whole run before any write.
refuse 'deny list' --device /dev/sdc:GOODSERIAL2 --device /dev/sda:03A0423110011698

# Two good sticks: the dry run prints the writes (and reads back) and writes nothing.
good=$(LSBLK=$work/lsblk STATE=$work/state bash "$script" --dry-run sticks --iso "$work/image.iso.xz" \
        --raw-sha256 "$sha" --raw-size 3553460224 --device /dev/sdb:GOODSERIAL1 --device /dev/sdc:GOODSERIAL2 2>&1)
grep -q 'of=./dev/sdb' <<<"$good" && grep -q 'of=./dev/sdc' <<<"$good"
! grep -q 'sda' <<<"$good"
echo 'master-release checks passed'
