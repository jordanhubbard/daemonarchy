#!/usr/local/bin/bash
# Real pkg signing, dependency resolution and repository identity in an offline root.
set -euo pipefail
[[ $(uname -s) == FreeBSD && $(id -u) == 0 ]] || { echo 'Run as root on FreeBSD' >&2; exit 1; }
here=$(cd "$(dirname "$0")/.." && pwd)
source "$here/overlay/usr/local/libexec/daemonarchy-installer/package-repository"
source "$here/scripts/adopt-candidate-packages.sh"
work=$(mktemp -d /var/tmp/daemonarchy-feed-test.XXXXXX)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/input/All" "$work/iso" "$work/official" "$work/repos" "$work/root" "$work/stable"
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
                    annotations={'FreeBSD_version':subprocess.check_output(['uname','-U'],text=True).strip()},
                    arch='freebsd:16:x86:64', files={path: {'sum':'1', 'uname':'root', 'gname':'wheel', 'perm':'0644'}})
    if name == 'omarchy':
        # A real NO_ARCH catalogue entry need not declare an OSVERSION.
        manifest.update(abi='FreeBSD:16:*', arch='freebsd:16:*')
        manifest.pop('annotations')
        manifest['deps'] = {'candidate-runtime': {'origin':'devel/candidate-runtime', 'version':version}}
    if name == 'candidate-runtime' and version != '1.0':
        manifest['deps'] = {'candidate-fetched': {'origin':'devel/candidate-fetched', 'version':'1.0'}}
    file = root / ('manifest-' + name + '.json')
    file.write_text(json.dumps(manifest))
    subprocess.run(['pkg','create','-M',str(file),'-r',str(stage),'-o',str(root/'input/All')],check=True)
PY
  printf 'devel/candidate-runtime candidate-runtime-%s 1\nsysutils/candidate-kernel candidate-kernel-%s 1\n' "$1" "$1" >"$work/built"
}
create_packages 1.0
mv "$work/input/All/candidate-runtime-1.0.pkg" "$work/official/"
mv "$work/input/All/candidate-fetched-1.0.pkg" "$work/official/"
rm "$work/input/All/omarchy-1.0.pkg" "$work/input/All/candidate-kernel-1.0.pkg"
pkg repo -q "$work/official"
create_packages 2.0
if TAG=packages-16-amd64 PACKAGES_DIR="$work/input" BUILT_PACKAGES_FILE="$work/built" \
    OUT="$work/stable" KEY="$work/key" sh "$here/pkg-repo.sh" build; then
  echo 'Allowed rebuilt dependencies to replace the stable feed' >&2; exit 1
fi
[[ -f $work/stable/sentinel ]]
publish_fixture() {
  TAG=packages-16-amd64-test PACKAGES_DIR="$work/input" BUILT_PACKAGES_FILE="$work/built" \
    OUT="$work/unsigned/All" KEY="$work/unavailable-key" sh "$here/pkg-repo.sh" collect
  [[ -f $work/unsigned/All/omarchy-$1.pkg && -f $work/unsigned/All/candidate-runtime-$1.pkg ]]
  [[ ! -f $work/unsigned/All/candidate-kernel-$1.pkg && ! -f $work/unsigned/All/candidate-fetched-$1.pkg ]]
  TAG=packages-16-amd64-test PACKAGES_DIR="$work/unsigned" BUILT_PACKAGES_FILE="$work/built" \
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
cat >"$work/repos/official.conf" <<EOF
Official: {url:"file://$work/official",signature_type:"none",priority:0,enabled:yes}
EOF
target_pkg() { pkg -r "$work/root" -o ABI=FreeBSD:16:amd64 -o "OSVERSION=$(uname -U)" -o REPOS_DIR="$work/repos" "$@"; }
target_pkg update -f
# A pre-existing official dependency needs an explicit candidate transition.
mkdir -p "$work/upgrade-root" "$work/upgrade-repos"
cat >"$work/upgrade-repos/official.conf" <<EOF
FreeBSD: {url:"file://$work/official",signature_type:"none",priority:0,enabled:yes}
EOF
cat >"$work/upgrade-repos/candidate.conf" <<EOF
Daemonarchy: {url:"file://$work/feed",signature_type:"pubkey",pubkey:"$work/public",priority:10,enabled:yes}
EOF
upgrade_pkg() { pkg -r "$work/upgrade-root" -o ABI=FreeBSD:16:amd64 -o "OSVERSION=$(/usr/bin/env -u UNAME_U /usr/bin/uname -U)" -o REPOS_DIR="$work/upgrade-repos" "$@"; }
upgrade_pkg update -f
upgrade_pkg install -y -r FreeBSD candidate-runtime
[[ $(upgrade_pkg query '%v %R' candidate-runtime) == '1.0 FreeBSD' ]]
# The actual signed catalogue must stop adoption before repository annotations,
# even though pkg's automatic yes and OS overrides permit the same packages.
mkdir "$work/incompatible"
for requirement in newer missing malformed; do
  python3.12 - "$work" "$requirement" <<'PY'
import json,subprocess,sys
from pathlib import Path
w,mode=Path(sys.argv[1]),sys.argv[2]
m=json.loads((w/'manifest-candidate-runtime.json').read_text())
if mode=='newer':
    versions=[int(subprocess.check_output(['uname',flag],text=True)) for flag in ('-K','-U')]
    m['annotations']['FreeBSD_version']=str(max(versions)+1)
elif mode=='missing':
    m.pop('annotations')
else:
    m['annotations']['FreeBSD_version']='invalid'
(w/'incompatible-manifest.json').write_text(json.dumps(m))
subprocess.run(['pkg','create','-M',str(w/'incompatible-manifest.json'),'-r',str(w/'stage-candidate-runtime'),'-o',str(w/'incompatible')],check=True)
PY
  pkg repo -q "$work/incompatible" "$work/key"
  cat >"$work/upgrade-repos/candidate.conf" <<EOF
Daemonarchy: {url:"file://$work/incompatible",signature_type:"pubkey",pubkey:"$work/public",priority:10,enabled:yes}
EOF
  if IGNORE_OSVERSION=yes ASSUME_ALWAYS_YES=yes UNAME_K=99999999 UNAME_U=99999999 \
      candidate_adopt_installed_packages upgrade_pkg >"$work/refusal-$requirement.log" 2>&1; then
    echo "Adopted $requirement OS metadata despite incompatible/unknown base" >&2; exit 1
  fi
  grep -q 'Candidate adoption refused:' "$work/refusal-$requirement.log"
  grep -q 'Upgrade the FreeBSD base and kernel together' "$work/refusal-$requirement.log"
  [[ $(upgrade_pkg query '%v %R' candidate-runtime) == '1.0 FreeBSD' ]]
  [[ $(cat "$work/upgrade-root/usr/local/share/feed-test/runtime") == 1.0 ]]
done
cat >"$work/upgrade-repos/candidate.conf" <<EOF
Daemonarchy: {url:"file://$work/feed",signature_type:"pubkey",pubkey:"$work/public",priority:10,enabled:yes}
EOF
candidate_adopt_installed_packages upgrade_pkg
[[ $(upgrade_pkg query '%v %R' candidate-runtime) == '2.0 Daemonarchy' ]]
[[ $(upgrade_pkg query '%v %R' candidate-fetched) == '1.0 FreeBSD' ]]
if upgrade_pkg info -e omarchy; then echo 'Installed an unrelated feed package during adoption' >&2; exit 1; fi
# Rebuilt metadata can retain the official package's version. Force the
# candidate identity even when both repositories offer the same version.
mkdir "$work/old-official"
mv "$work/official/candidate-runtime-1.0.pkg" "$work/old-official/"
printf official-2.0 >"$work/stage-candidate-runtime/usr/local/share/feed-test/runtime"
pkg create -M "$work/manifest-candidate-runtime.json" -r "$work/stage-candidate-runtime" -o "$work/official"
pkg repo -q "$work/official"
upgrade_pkg update -f -r FreeBSD
upgrade_pkg install -f -y -r FreeBSD candidate-runtime
[[ $(upgrade_pkg query '%v %R' candidate-runtime) == '2.0 FreeBSD' ]]
[[ $(cat "$work/upgrade-root/usr/local/share/feed-test/runtime") == official-2.0 ]]
candidate_adopt_installed_packages upgrade_pkg
[[ $(upgrade_pkg query '%v %R' candidate-runtime) == '2.0 Daemonarchy' ]]
[[ $(cat "$work/upgrade-root/usr/local/share/feed-test/runtime") == 2.0 ]]
upgrade_pkg annotate -y -M candidate-runtime repository Private
if candidate_adopt_installed_packages upgrade_pkg; then echo 'Replaced a private repository override' >&2; exit 1; fi
[[ $(upgrade_pkg query '%v %R' candidate-runtime) == '2.0 Private' ]]
upgrade_pkg install -y -r Daemonarchy -r FreeBSD omarchy
upgrade_pkg add -f "$work/old-official/candidate-runtime-1.0.pkg"
upgrade_pkg annotate -y -M candidate-runtime repository Private
candidate_adopt_installed_packages upgrade_pkg
[[ $(upgrade_pkg query '%v %R' candidate-runtime) == '1.0 Private' ]]
[[ $(cat "$work/upgrade-root/usr/local/share/feed-test/runtime") == 1.0 ]]
[[ $(upgrade_pkg query '%v %R' omarchy) == '2.0 Daemonarchy' ]]
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
echo 'PASS: signed OS metadata guards, override resistance, rebuilt dependencies, kernel/fetched exclusion, stable guard, official-only dependencies, same-version adoption, private overrides and subsequent upgrades'
