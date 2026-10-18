#!/bin/sh
# Candidate feed selection and malformed image metadata, without installing a system.
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
. "$here/overlay/usr/local/libexec/daemonarchy-installer/package-repository"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
package_repository_prepare "$work"
[ "$package_repository_tag" = packages-16-amd64 ]
package_repository_write_dependencies "$work/dependencies.conf" /public/key
[ ! -e "$work/dependencies.conf" ]
for tag in packages-16-amd64 packages-16-amd64-1.1.1 packages-16-amd64-1.1.0-rc.2; do
    printf '%s\n' "$tag" >"$work/package-repository-tag"
    package_repository_prepare "$work"
    [ "$package_repository_tag" = "$tag" ]
done
printf '%s\n' packages-16-amd64-1.1.1 >"$work/package-repository-tag"
package_repository_prepare "$work"
package_repository_write_dependencies "$work/dependencies.conf" /public/key
grep -qx 'Daemonarchy-Dependencies: {' "$work/dependencies.conf"
grep -q 'signature_type: "pubkey"' "$work/dependencies.conf"
grep -q 'packages-16-amd64-1.1.1' "$work/dependencies.conf"
grep -q 'pubkey: "/public/key"' "$work/dependencies.conf"
grep -q 'priority: 9' "$work/dependencies.conf"
for tag in '' packages-16-amd64- other-repository 'packages-16-amd64-../bad' 'packages-16-amd64-bad tag'; do
    printf '%s\n' "$tag" >"$work/package-repository-tag"
    if package_repository_prepare "$work" 2>/dev/null; then
        echo "Accepted invalid repository tag: $tag" >&2
        exit 1
    fi
done
printf 'packages-16-amd64-rc2\nunexpected\n' >"$work/package-repository-tag"
if package_repository_prepare "$work" 2>/dev/null; then
    echo 'Accepted multiline repository metadata' >&2
    exit 1
fi
echo 'PASS: stable fallback, candidate feed selection and invalid metadata rejection'
