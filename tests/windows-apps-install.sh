#!/usr/bin/env bash
# The installer's part of the Windows programs and Steam virtual apps: launchers, desktop
# entries, icons and menu entries go in on amd64, never on aarch64, and nothing of
# Wine's or Valve's is installed.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
lib=$here/overlay/usr/local/libexec/daemonarchy-installer
share=$here/overlay/usr/local/share/daemonarchy-installer
source "$lib/windows-apps"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
never() { if "$@"; then echo "unexpected success: $*" >&2; exit 1; fi; }

target_with_menu() { # a new target holding the vendor menu cuda_install_support wrote
  rm -rf "$work/target"
  mkdir -p "$work/target/usr/local/bin" "$work/target/usr/local/share/omarchy/vendor" \
           "$work/target/usr/local/share/applications"
  cp "$share/omarchy-menu.jsonc" "$work/target/usr/local/share/omarchy/vendor/omarchy-menu.jsonc"
  : >"$work/target/usr/local/share/applications/daemonarchy-steam.desktop"
}
menu=$work/target/usr/local/share/omarchy/vendor/omarchy-menu.jsonc

# amd64: everything lands, with the right modes, and the menu keeps its entries
target_with_menu
windows_apps_install_support "$work/target" "$share" "$here/overlay" amd64
for name in daemonarchy-wine daemonarchy-steam; do
  [[ -x $work/target/usr/local/bin/$name ]]
  cmp "$here/overlay/usr/local/bin/$name" "$work/target/usr/local/bin/$name"
  [[ $(stat -c %a "$work/target/usr/local/share/applications/$name.desktop") == 644 ]]
  cmp "$share/$name.desktop" "$work/target/usr/local/share/applications/$name.desktop"
  cmp "$share/$name.svg" "$work/target/usr/local/share/icons/hicolor/scalable/apps/$name.svg"
done
grep -q '"system.freebsd.steam":' "$menu"
grep -q '"system.freebsd.wine":' "$menu"
cmp "$share/omarchy-menu.jsonc" "$menu"
echo 'PASS: amd64 gets the launchers, desktop entries, icons and menu entries'

# nothing of Wine's or Valve's: no package, no download, only the files above
[[ -z $(find "$work/target" -type f | grep -v -E 'daemonarchy-(wine|steam)|omarchy-menu.jsonc') ]]
never grep -q -E 'pkg |curl|fetch' "$lib/windows-apps"
echo 'PASS: the installer installs no Wine and downloads nothing'

# aarch64: the entries are taken out, including ones left by an earlier step
target_with_menu
install -m 0755 "$here/overlay/usr/local/bin/daemonarchy-wine" "$work/target/usr/local/bin/daemonarchy-wine"
windows_apps_install_support "$work/target" "$share" "$here/overlay" aarch64
[[ ! -e $work/target/usr/local/bin/daemonarchy-wine && ! -e $work/target/usr/local/bin/daemonarchy-steam ]]
[[ ! -e $work/target/usr/local/share/applications/daemonarchy-steam.desktop ]]
[[ ! -e $work/target/usr/local/share/applications/daemonarchy-wine.desktop ]]
[[ ! -e $work/target/usr/local/share/icons/hicolor/scalable/apps/daemonarchy-steam.svg ]]
never grep -q 'steam\|wine' "$menu"
# the rest of the menu is untouched, and still the same JSON-with-comments file
grep -q '"system.freebsd.dtrace":' "$menu"
grep -q '"system.freebsd.jails":' "$menu"
check=$(grep -c '"system.freebsd' "$share/omarchy-menu.jsonc")
[[ $(grep -c '"system.freebsd' "$menu") == $((check - 2)) ]]
echo 'PASS: aarch64 never shows Windows programs or Steam'

# no vendor menu on the target is not an error
rm -rf "$work/target"
mkdir -p "$work/target"
windows_apps_install_support "$work/target" "$share" "$here/overlay" aarch64
echo 'PASS: a target without a vendor menu is left alone'

# the installer calls it after the CUDA step, with the image's architecture
install=$lib/install
grep -q '^source "\$(dirname "\$0")/windows-apps"$' "$install"
cuda_line=$(grep -n '^cuda_install_support "\$TARGET" "\$ISO_SHARE"$' "$install" | cut -d: -f1)
windows_line=$(grep -n '^windows_apps_install_support "\$TARGET" "\$ISO_SHARE" "" "\$image_arch"$' "$install" | cut -d: -f1)
[[ -n $cuda_line && -n $windows_line && $windows_line -gt $cuda_line ]]
bash -n "$lib/windows-apps"
echo 'PASS: the installer runs it after the CUDA step with the image architecture'
echo 'Windows apps installer checks passed'
