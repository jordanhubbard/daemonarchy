#!/usr/local/bin/bash
# Build a disposable partial-install boot fixture, never a host installation.
# Usage: sudo bash tests/rescue-boot-image.sh /new/output /snapshot/base.txz /snapshot/root
set -euo pipefail
[[ $(uname -s) == FreeBSD && $EUID == 0 ]] || exit 1
output=${1:?Specify a new output directory}
base=${2:?Specify base.txz}
snapshot=${3:?Specify snapshot root with /boot}
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/disk-layout"
source "$here/overlay/usr/local/libexec/daemonarchy-installer/rescue-setup"
source "$here/overlay/usr/local/libexec/daemonarchy-installer/install-diagnostics"
mkdir -m 700 "$output"
output=$(realpath "$output")
md='' pool="dmrescue$$" created=false mounted=false
cleanup_fixture() {
  diagnostics_stop || true
  if $mounted; then umount "$output/root/boot/efi"; fi
  if $created; then zpool export "$pool"; fi
  [[ -z $md ]] || mdconfig -d -u "${md#md}"
}
trap cleanup_fixture EXIT
truncate -s 3g "$output/disk.img"
md=$(mdconfig -a -t vnode -f "$output/disk.img")
[[ $md =~ ^md[0-9]+$ ]] || exit 1
gpart create -s gpt "$md"
gpart add -t efi -a 1m -s 64m "$md"
gpart add -t freebsd-zfs -a 1m "$md"
mkdir "$output/root"
zpool create -o cachefile=none -o altroot="$output/root" -m none "$pool" "/dev/${md}p2"
created=true
zfs create -o mountpoint=none "$pool/ROOT"
zfs create -o mountpoint=/ "$pool/ROOT/default"
zpool set bootfs="$pool/ROOT/default" "$pool"
tar -xpf "$base" -C "$output/root" --exclude './usr/tests' --exclude './usr/lib/debug' \
  --exclude './usr/share/man' --exclude './usr/share/doc'
cp -R "$snapshot/boot" "$output/root/"
diagnostics_begin "$output/root" jkh true /nonexistent/fixture-log
diagnostics_phase install
echo 'RESCUE TEST: desktop package transaction interrupted'
# Public fixture credential, never used on a real installed system.
fixture_hash=$(printf 'rescue-test-only' | openssl passwd -6 -stdin)
create_recovery_accounts "$output/root" jkh 'Rescue Test User' <<<"$fixture_hash"
install_rescue_support "$output/root" "$here/overlay/usr/local/libexec/daemonarchy-installer" "$here/overlay/usr/local/sbin"
# Exercise the same getty/profile path through a QEMU serial console.
# This fixture-only substitution does not claim physical VGA validation.
sed -i '' -E 's|^ttyu0[[:space:]].*|ttyu0 "/usr/libexec/getty daemonarchy.Pc" vt100 on secure|' "$output/root/etc/ttys"
sed -i '' 's|/dev/ttyv0|/dev/ttyu0|' "$output/root/root/.profile"
cat >"$output/root/etc/rc.conf" <<'EOF'
hostname="rescue-fixture"
zfs_enable="YES"
ifconfig_DEFAULT="DHCP"
sendmail_enable="NONE"
update_motd="NO"
EOF
cat >"$output/root/boot/loader.conf" <<'EOF'
console="comconsole"
autoboot_delay="1"
beastie_disable="YES"
zfs_load="YES"
EOF
newfs_msdos -F 32 -c 1 "/dev/${md}p1" >/dev/null
mkdir -p "$output/root/boot/efi"
mount -t msdosfs "/dev/${md}p1" "$output/root/boot/efi"
mounted=true
write_efi_loader "$output/root" "$pool" false
{
  echo 'console=comconsole'
  efi_root_environment "$pool"
} >"$output/root/boot/efi/EFI/FreeBSD/loader.env"
echo 'RESCUE TEST: logging drained before pool export'
diagnostics_stop
umount "$output/root/boot/efi"
mounted=false
zpool export "$pool"
created=false
mdconfig -d -u "${md#md}"
md=''
gzip -1 -c "$output/disk.img" >"$output/disk.img.gz"
echo "Boot $output/disk.img with UEFI QEMU and -serial stdio."
echo 'Expected: incomplete-install menu; root actions require rescue-test-only.'
echo 'Remote pairing requires the small bash package first; base-only local rescue works without it.'
