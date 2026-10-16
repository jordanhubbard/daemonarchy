#!/bin/sh
# Make a private live-image overlay; never copy an operator's private key.
set -eu
key=${1:?usage: prepare-headless-rescue.sh operator.pub new-overlay-directory}
overlay=${2:?usage: prepare-headless-rescue.sh operator.pub new-overlay-directory}
[ -f "$key" ] && [ ! -e "$overlay" ] || { echo 'Need a public key and a new output directory' >&2; exit 1; }
awk 'NF { n++; if ($1 != "ssh-ed25519" || NF < 2) bad=1 } END { exit n != 1 || bad }' "$key" || {
    echo 'Use one plain Ed25519 public key, without authorized_keys options' >&2; exit 1;
}
ssh-keygen -l -f "$key" >/dev/null
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
umask 077
payload=$overlay/usr/local/share/daemonarchy-installer/headless
mkdir -p "$payload" "$overlay/usr/local/etc/rc.d" "$overlay/boot"
# Only the key directory is private; SSH privilege separation must still be
# able to traverse the ordinary system directories in the image.
chmod 755 "$overlay" "$overlay/usr" "$overlay/usr/local" "$overlay/usr/local/share" \
    "$overlay/usr/local/share/daemonarchy-installer" "$overlay/usr/local/etc" \
    "$overlay/usr/local/etc/rc.d" "$overlay/boot"
cp "$key" "$payload/authorized_keys"
ssh-keygen -q -t ed25519 -N '' -f "$payload/host_key"
install -m 755 "$here/headless-rescue-rc.sh" "$overlay/usr/local/etc/rc.d/daemonarchy-headless"
cat >"$overlay/boot/loader.conf.local" <<'CONFIG'
# This rescue image must not initialize T2 BCE or desktop GPU drivers.
apple_bce_load="NO"
devmatch_blocklist="apple_bce amdgpu radeonkms i915kms nvidia nvidia-modeset nvidia-drm"
CONFIG
printf 'Private rescue overlay: %s\nServer host-key fingerprint:\n' "$overlay"
ssh-keygen -l -f "$payload/host_key.pub"
echo 'Use LIVE_EXTRA_OVERLAY with build-iso.sh. Do not publish this private image.'
