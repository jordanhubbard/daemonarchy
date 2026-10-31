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
# The image ABI selects its architecture's feed family and refuses another's.
rm -f "$work/package-repository-tag" "$work/dependencies.conf"
echo FreeBSD:16:amd64 >"$work/ABI"
package_repository_prepare "$work"
[ "$package_repository_arch" = amd64 ] && [ "$package_repository_stable_tag" = packages-16-amd64 ]
[ "$package_repository_tag" = packages-16-amd64 ]
echo FreeBSD:16:aarch64 >"$work/ABI"
package_repository_prepare "$work"
[ "$package_repository_arch" = aarch64 ] && [ "$package_repository_tag" = packages-16-aarch64 ]
package_repository_write_dependencies "$work/dependencies.conf" /public/key
[ ! -e "$work/dependencies.conf" ]
printf '%s\n' packages-16-aarch64-1.4.0 >"$work/package-repository-tag"
package_repository_prepare "$work"
package_repository_write_dependencies "$work/dependencies.conf" /public/key
grep -q 'releases/download/packages-16-aarch64-1.4.0"' "$work/dependencies.conf"
rm -f "$work/dependencies.conf"
for tag in packages-16-amd64 packages-16-amd64-1.4.0; do
    printf '%s\n' "$tag" >"$work/package-repository-tag"
    if package_repository_prepare "$work" 2>/dev/null; then
        echo "aarch64 image accepted another architecture's feed: $tag" >&2
        exit 1
    fi
done
echo FreeBSD:16:amd64 >"$work/ABI"
printf '%s\n' packages-16-aarch64 >"$work/package-repository-tag"
if package_repository_prepare "$work" 2>/dev/null; then
    echo 'amd64 image accepted the aarch64 feed' >&2
    exit 1
fi
for abi in FreeBSD:16:arm64 FreeBSD:15:amd64 ''; do
    printf '%s\n' "$abi" >"$work/ABI"
    if package_repository_prepare "$work" 2>/dev/null; then
        echo "Accepted unsupported image ABI: $abi" >&2
        exit 1
    fi
done
package_repository_tag_validate packages-16-aarch64-1.4.0 aarch64
if package_repository_tag_validate packages-16-aarch64-1.4.0 2>/dev/null; then
    echo 'The default amd64 validation accepted an aarch64 tag' >&2
    exit 1
fi
# A signed snapshot of the upstream packages: preferred when listed, skipped
# (never fatal) when it does not answer, ignored when it is not one of ours.
base=https://github.com/jordanhubbard/daemonarchy/releases/download
package_mirror_probe() { case "$1" in *upstream-down) return 1 ;; *) return 0 ;; esac; }
rm -f "$work/mirror.conf"
package_repository_write_mirror "$work/mirror.conf" /public/key "$work/no-such-list"
[ ! -e "$work/mirror.conf" ]
printf '%s\n' "$base/packages-16-amd64-1.4.1-upstream-1" "$base/packages-16-amd64-1.4.1-upstream-down" \
    "$base/packages-16-amd64-1.4.1-upstream-2" 'https://evil.example/packages-16-amd64-x' \
    "$base/packages-16-aarch64-1.4.1-upstream-1" "$base/packages-16-amd64-bad;rm" '' >"$work/package-mirror"
package_repository_write_mirror "$work/mirror.conf" /public/key "$work/package-mirror" 2>"$work/mirror.err"
grep -qx 'Daemonarchy-Mirror-1: {' "$work/mirror.conf"
grep -qx 'Daemonarchy-Mirror-2: {' "$work/mirror.conf"
[ "$(grep -c '^Daemonarchy-Mirror-' "$work/mirror.conf")" = 2 ]
grep -q 'upstream-1"' "$work/mirror.conf" && grep -q 'upstream-2"' "$work/mirror.conf"
! grep -q 'upstream-down\|evil\|aarch64\|rm' "$work/mirror.conf"
grep -q 'signature_type: "pubkey"' "$work/mirror.conf" && grep -q 'pubkey: "/public/key"' "$work/mirror.conf"
grep -q 'priority: 5' "$work/mirror.conf"
grep -q 'did not answer' "$work/mirror.err" && grep -q 'not one of ours' "$work/mirror.err"
# aarch64 images take only aarch64 shards.
rm -f "$work/mirror.conf"
package_repository_write_mirror "$work/mirror.conf" /public/key "$work/package-mirror" aarch64 2>/dev/null
[ "$(grep -c '^Daemonarchy-Mirror-' "$work/mirror.conf")" = 1 ] && grep -q 'packages-16-aarch64-1.4.1-upstream-1' "$work/mirror.conf"
echo 'PASS: package mirror shards are preferred, validated, per architecture, and skipped when they do not answer'

# pkg takes the newest version across repositories, so the transaction turns pkg.FreeBSD.org off
# while a shard answers (a 1.4.1 candidate took 63 packages from it) and leaves it on otherwise.
[ "$(package_repository_freebsd_enabled "$work/mirror.conf")" = no ]
rm -f "$work/mirror.conf"
[ "$(package_repository_freebsd_enabled "$work/mirror.conf")" = yes ]
printf '%s\n' "$base/packages-16-amd64-1.4.1-upstream-down" >"$work/down-list"
package_repository_write_mirror "$work/mirror.conf" /public/key "$work/down-list" 2>/dev/null
[ "$(package_repository_freebsd_enabled "$work/mirror.conf")" = yes ]
installer=$here/overlay/usr/local/libexec/daemonarchy-installer/install
grep -q 'freebsd_enabled=\$(package_repository_freebsd_enabled "\$repos/mirror.conf")' "$installer"
grep -q '^  enabled: \$freebsd_enabled$' "$installer"
# Only the transaction's repository directory changes: the installed system's repository files
# are written elsewhere and never name the FreeBSD repository as disabled.
! grep -n 'enabled: no' "$installer"
echo 'PASS: the install transaction uses the upstream repository only when no mirror shard answers'
echo 'PASS: stable fallback, candidate feed selection and invalid metadata rejection'
echo 'PASS: per-architecture feed families never cross'
