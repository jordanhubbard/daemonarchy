#!/bin/sh
# Native installed-system checks; GUI/hardware acceptance remains separate.
set -eu
pkg info -e chromium
pkg info -e octopkg
command -v daemonarchy >/dev/null
command -v octopkg >/dev/null
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
for desktop in ('chromium-browser.desktop', 'octopkg.desktop', 'foot.desktop', 'imv.desktop', 'mpv.desktop'):
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
        assert 'cudalab' not in key, key
        assert not any(word in row.get('action', '') for word in ('plymouth', 'docker', 'windows-vm', 'install-dev-env')), key
    if 'install.package' in entries:
        assert entries['install.package']['action'] == 'uwsm-app -- octopkg'
print('    ok    native package menu and unqualified app exclusions')
for name in ('omarchy-network-band', 'omarchy-network-speedtest', 'omarchy-disk-speedtest',
             'omarchy-network-password'):
    result = subprocess.run([name], capture_output=True, text=True)
    assert result.returncode == 1 and 'not supported on FreeBSD' in result.stderr, (name, result)
print('    ok    unsupported Linux network and benchmark commands fail before running')
PY
