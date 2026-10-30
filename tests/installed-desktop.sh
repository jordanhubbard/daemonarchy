#!/bin/sh
# Native installed-system checks; GUI/hardware acceptance remains separate.
set -eu
# chromium has no aarch64 package: an arm64 desktop's default browser is Epiphany.
if [ "$(uname -m)" = arm64 ]; then pkg info -e epiphany; else pkg info -e chromium; fi
pkg info -e octopkg
command -v daemonarchy >/dev/null
command -v octopkg >/dev/null
# Packages such as LLVM/Mesa require the snapshot's 32-bit base libraries.
[ -s /usr/lib32/libc++.so.1 ]
[ -x /libexec/ld-elf32.so.1 ]
# arm64's lib32 is AArch32 code, which Apple silicon (the QEMU host for the arm64 test) cannot execute:
# there the files above are all that can be checked.
if [ "$(uname -m)" != arm64 ]; then
  lib32_deps=$(ldd /usr/lib32/libc++.so.1)
  case "$lib32_deps" in *'not found'*) printf '%s\n' "$lib32_deps" >&2; exit 1 ;; esac
fi
daemonarchy --help | grep -q 'Daemonarchy command center'
daemonarchy checkouts --help | grep -q 'daemonarchy checkouts'
interpreter=$(head -n 1 /usr/local/bin/omarchy-launch-browser)
interpreter=${interpreter#\#!}
case "$interpreter" in
  /usr/local/bin/python3.[0-9]*) ;;
  *) echo 'Invalid packaged browser interpreter' >&2; exit 1 ;;
esac
"$interpreter" - <<'PY'
import json
from pathlib import Path
import shutil
import subprocess
import gi
gi.require_version('GioUnix', '2.0')
from gi.repository import GioUnix
import platform
browser = ('org.gnome.Epiphany.desktop',) if platform.machine() in ('arm64', 'aarch64') else ('chromium-browser.desktop',)
for desktop in browser + ('octopkg.desktop', 'foot.desktop', 'imv.desktop', 'mpv.desktop'):
    info = GioUnix.DesktopAppInfo.new(desktop)
    assert info is not None, desktop
    assert shutil.which(info.get_executable()), (desktop, info.get_executable())
    print('    ok    installed desktop command:', desktop)
root = Path('/usr/local/share/omarchy')
assert not (root / 'applications/Docker.desktop').exists()
for path in (root / 'default/omarchy/omarchy-menu.jsonc', root / 'vendor/omarchy-menu.jsonc'):
    entries = {}
    for line in path.read_text().splitlines():
        if line.strip().startswith('"'):
            entries.update(json.loads('{' + line.strip().rstrip(',') + '}'))
    for key, row in entries.items():
        assert not key.startswith(('install.aur', 'update.channel', 'setup.default.agent',
                                   'trigger.tests.network-speedtest', 'trigger.tests.disk-speedtest')), key
        # Cudalab is offered with an NVIDIA GPU and installed by default there.
        assert 'cudalab' not in key or Path('/usr/local/share/applications/cudalab.desktop').exists(), key
        assert not any(word in row.get('action', '') for word in ('plymouth', 'docker', 'windows-vm', 'install-dev-env')), key
    if 'install.package' in entries:
        assert entries['install.package']['action'] == 'uwsm-app -- octopkg'
print('    ok    native package menu and unqualified app exclusions')
routes = json.loads(subprocess.check_output(['daemonarchy', 'commands', '--json'], text=True))
visible = {row['binary'] for row in routes['commands']}
unsupported = ('omarchy-network-band', 'omarchy-network-speedtest', 'omarchy-disk-speedtest',
               'omarchy-network-password', 'omarchy-dev-install-ydoo', 'omarchy-dev-pkg-test',
               'omarchy-pkg-aur-add', 'omarchy-update-aur-pkgs', 'omarchy-plymouth-set',
               'omarchy-hibernation-setup', 'omarchy-reinstall-configs', 'omarchy-upgrade-to-quattro',
               'omarchy-refresh-limine', 'omarchy-refresh-pacman', 'omarchy-install-hermes-cli',
               'omarchy-launch-openclaw', 'omarchy-openclaw-onboard', 'omarchy-voxtype-install',
               'omarchy-install-service-sunshine', 'omarchy-remove-service-1password',
               'omarchy-install-gaming-gpu-lib32', 'omarchy-agent')
assert not visible.intersection(unsupported), visible.intersection(unsupported)
for name in ('omarchy-pkg-add', 'omarchy-refresh-hyprland', 'omarchy-battery-status',
             'omarchy-hyprland-monitor-scaling'):
    assert name in visible, name
for name in unsupported:
    result = subprocess.run([name], capture_output=True, text=True)
    assert result.returncode == 1 and 'not supported on FreeBSD' in result.stderr, (name, result)
manifest = json.loads((root / 'shell/plugins/bar/widgets/Indicators.manifest.json').read_text())
options = next(row['options'] for row in manifest['barWidget']['schema'] if row['key'] == 'items')
assert not {'Dictation', 'ScreenRecording'}.intersection(row['value'] for row in options)
print('    ok    unsupported Linux commands and bar choices excluded; portable commands retained')
PY
