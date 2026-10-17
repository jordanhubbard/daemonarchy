#!/usr/local/bin/bash
# Real pkg signing, dependency resolution and repository identity in an offline root.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $(id -u) == 0 ]] || { echo 'Run as root on FreeBSD' >&2; exit 1; }
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/package-repository"
work=$(mktemp -d /var/tmp/daemonarchy-feed-test.XXXXXX)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/input/All" "$work/iso" "$work/repos" "$work/root" "$work/stable"
echo preserve >"$work/stable/sentinel"
openssl genrsa -out "$work/key" 2048 >/dev/null 2>&1
chmod 0400 "$work/key"
openssl rsa -in "$work/key" -pubout >"$work/public" 2>/dev/null

create_packages() {
  python3.12 - "$work" "$1" <<'PY'
import json
from pathlib import Path
import subprocess
import sys
root, version = Path(sys.argv[1]), sys.argv[2]
specs = [('omarchy', 'x11-wm/omarchy', '/usr/local/share/feed-test/app'),
         ('candidate-runtime', 'devel/candidate-runtime', '/usr/local/share/feed-test/runtime'),
         ('candidate-kernel', 'sysutils/candidate-kernel', '/boot/modules/feed-test.ko'),
         ('candidate-fetched', 'devel/candidate-fetched', '/usr/local/share/feed-test/fetched')]
for name, origin, path in specs:
    stage = root / ('stage-' + name)
    target = stage / path.lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(version)
    manifest = dict(name=name, version=version, origin=origin, comment='Disposable feed test',
                    desc='Disposable signed dependency test fixture', maintainer='test@example.invalid',
                    www='https://example.invalid', prefix='/', abi='FreeBSD:16:amd64',
                    arch='freebsd:16:x86:64', files={path: {'sum':'1', 'uname':'root', 'gname':'wheel', 'perm':'0644'}})
    if name == 'omarchy':
        manifest['deps'] = {'candidate-runtime': {'origin':'devel/candidate-runtime', 'version':version}}
    file = root / 'manifest.json'
    file.write_text(json.dumps(manifest))
    subprocess.run(['pkg','create','-M',str(file),'-r',str(stage),'-o',str(root/'input/All')],check=True)
PY
  printf 'devel/candidate-runtime candidate-runtime-%s 1\nsysutils/candidate-kernel candidate-kernel-%s 1\n' "$1" "$1" >"$work/built"
}
create_packages 2.0
if TAG=packages-16-amd64 PACKAGES_DIR="$work/input" BUILT_PACKAGES_FILE="$work/built" \
    OUT="$work/stable" KEY="$work/key" sh "$here/pkg-repo.sh" build; then
  echo 'Allowed rebuilt dependencies to replace the stable feed' >&2; exit 1
fi
[[ -f $work/stable/sentinel ]]
publish_fixture() {
  TAG=packages-16-amd64-test PACKAGES_DIR="$work/input" BUILT_PACKAGES_FILE="$work/built" \
    OUT="$work/feed" KEY="$work/key" sh "$here/pkg-repo.sh" build
  [[ -f $work/feed/omarchy-$1.pkg && -f $work/feed/candidate-runtime-$1.pkg ]]
  [[ ! -f $work/feed/candidate-kernel-$1.pkg && ! -f $work/feed/candidate-fetched-$1.pkg ]]
}
publish_fixture 2.0
cp "$work/input/All/omarchy-2.0.pkg" "$work/iso/"
pkg repo -q "$work/iso"
cat >"$work/repos/iso.conf" <<EOF
Daemonarchy: {url:"file://$work/iso",signature_type:"none",priority:10,enabled:yes}
EOF
cat >"$work/repos/dependencies.conf" <<EOF
Daemonarchy-Dependencies: {url:"file://$work/feed",signature_type:"pubkey",pubkey:"$work/public",priority:9,enabled:yes}
EOF
target_pkg() { pkg -r "$work/root" -o ABI=FreeBSD:16:amd64 -o REPOS_DIR="$work/repos" "$@"; }
target_pkg update -f
target_pkg install -y omarchy
[[ $(target_pkg query '%v' candidate-runtime) == 2.0 ]]
[[ $(target_pkg query '%R' omarchy) == Daemonarchy ]]
[[ $(target_pkg query '%R' candidate-runtime) == Daemonarchy-Dependencies ]]
package_repository_finalize_dependencies target_pkg
[[ $(target_pkg query '%R' candidate-runtime) == Daemonarchy ]]
rm "$work/repos/dependencies.conf"
cat >"$work/repos/iso.conf" <<EOF
Daemonarchy: {url:"file://$work/feed",signature_type:"pubkey",pubkey:"$work/public",priority:10,enabled:yes}
EOF
rm "$work/input/All/omarchy-2.0.pkg" "$work/input/All/candidate-runtime-2.0.pkg" \
  "$work/input/All/candidate-kernel-2.0.pkg" "$work/input/All/candidate-fetched-2.0.pkg"
create_packages 3.0
publish_fixture 3.0
target_pkg update -f
target_pkg upgrade -y
[[ $(target_pkg query '%v' omarchy) == 3.0 && $(target_pkg query '%v' candidate-runtime) == 3.0 ]]
[[ $(cat "$work/root/usr/local/share/feed-test/runtime") == 3.0 ]]
echo 'PASS: rebuilt dependency inclusion, kernel/fetched exclusion, stable guard, signed resolution and subsequent upgrades'
