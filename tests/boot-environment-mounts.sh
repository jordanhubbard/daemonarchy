#!/usr/local/bin/bash
# Native test: only the memory disk and pool created here are modified.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || {
  echo 'Run this test on FreeBSD as root.' >&2
  exit 1
}
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d /tmp/daemonarchy-be-mounts.XXXXXX)
POOL="daemonarchy-be-mounts-$$"
TARGET="$work/root"
md=''
pool_created=no
devfs_mounted=no
cleanup() {
  if [[ $devfs_mounted == yes ]]; then umount "$TARGET/dev"; fi
  if [[ $pool_created == yes ]]; then zpool destroy "$POOL"; fi
  if [[ -n $md ]]; then mdconfig -d -u "${md#md}"; fi
  rm -rf "$work"
}
trap cleanup EXIT
! zpool list "$POOL" >/dev/null 2>&1
mkdir "$TARGET"
md=$(mdconfig -a -t swap -s 128m)
[[ $md =~ ^md[0-9]+$ ]]
zpool create -o altroot="$TARGET" -m none "$POOL" "$md"
pool_created=yes
zfs create -o mountpoint=none "$POOL/ROOT"
# Execute the real installer commands, without invoking its disk installer.
# Both policy and the initial explicit mount are required: a one-line noauto
# change would otherwise leave the installer writing outside ROOT/default.
commands=$(awk '
  /^zfs create .*"\$POOL\/ROOT\/default"$/ {
    print
    if (getline && /^zfs mount "\$POOL\/ROOT\/default"$/) print
    exit
  }' "$here/overlay/usr/local/libexec/daemonarchy-installer/install")
[[ -n $commands ]]
eval "$commands"
[[ $(zfs get -H -o value canmount "$POOL/ROOT/default") == noauto ]]
[[ $(zfs get -H -o value mounted "$POOL/ROOT/default") == yes ]]
[[ $(mount -p | awk -v ds="$POOL/ROOT/default" '$1 == ds { print $2 }') == "$TARGET" ]]
printf 'original\n' > "$TARGET/marker"
zfs snapshot "$POOL/ROOT/default@fixture"
zfs clone -o canmount=noauto -o mountpoint=/ "$POOL/ROOT/default@fixture" "$POOL/ROOT/candidate"
zfs unmount "$POOL/ROOT/default"
zfs mount "$POOL/ROOT/candidate"
printf 'candidate\n' > "$TARGET/marker"
mkdir "$TARGET/dev"
mount -t devfs devfs "$TARGET/dev"
devfs_mounted=yes
[[ $(cat "$TARGET/marker") == candidate && -c $TARGET/dev/null ]]
[[ $(zfs get -H -o value mounted "$POOL/ROOT/default") == no ]]
[[ $(zfs get -H -o value canmount "$POOL/ROOT/default") == noauto ]]
[[ $(zfs get -H -o value canmount "$POOL/ROOT/candidate") == noauto ]]
# No global zfs mount -a: its noauto exclusion is checked directly, without
# ever asking it to mount unrelated host datasets.
echo 'PASS: installer mounts its initial noauto root; candidate switch leaves original root inactive and devfs visible'
