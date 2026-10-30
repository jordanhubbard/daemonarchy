#!/bin/sh
# The closure feed gate refuses a missing, silent, unsigned or non-resolving feed (stubbed pkg and fetch).
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir -p "$work/bin" "$work/iso/All"
touch "$work/iso/All/drm-612-kmod-1.pkg" "$work/iso/All/nvidia-driver-2.pkg" "$work/iso/All/other-3.pkg"
echo pub >"$work/key.pub"

cat >"$work/bin/pkg" <<'EOF'
#!/bin/sh
# Minimal pkg: query -F FILE %n, update -f, install -n -y ROOTS
args=" $* "
case "$args" in
*" query "*) f=$(echo "$args" | sed 's/.* -F \([^ ]*\) .*/\1/'); b=$(basename "$f" .pkg); echo "${b%-*}" ;;
*" update "*) [ "${STUB_UPDATE:-ok}" = ok ] || { echo 'pkg: Invalid signature, removing repository.' >&2; exit 1; } ;;
*" install "*)
	echo "$args" >"$STUB_LOG"
	[ "${STUB_INSTALL:-ok}" = ok ] || { echo 'pkg: daemonarchy has a missing dependency: tigervnc-viewer'; exit 1; }
	echo 'Number of packages to be installed: 1036' ;;
esac
EOF
cat >"$work/bin/fetch" <<'EOF'
#!/bin/sh
[ "${STUB_FETCH:-ok}" = ok ]
EOF
chmod +x "$work/bin/pkg" "$work/bin/fetch"

base=https://github.com/jordanhubbard/daemonarchy/releases/download
run() {
	env PATH="$work/bin:$PATH" STUB_LOG="$work/plan.log" ISO_REPO="$work/iso" PUBKEY="${PUBKEY:-$work/key.pub}" \
	    MIRROR_URLS="${MIRROR_URLS:-$base/packages-16-amd64-1.4.1-upstream}" ABI=FreeBSD:16:amd64 \
	    sh "$here/scripts/check-closure-feed.sh" "$@" 2>&1
}
expect_refusal() { # label pattern
	if out=$(run); then echo "Accepted: $1" >&2; exit 1; fi
	case $out in *"$2"*) ;; *) echo "Wrong refusal for $1: $out" >&2; exit 1 ;; esac
}

out=$(run)
case $out in *"closure feed accepted: 1 shard(s), 1036 packages"*) ;; *) echo "Not accepted: $out" >&2; exit 1 ;; esac
# The GPU and firmware packages the ISO carries are roots; unrelated ones are not.
grep -q 'drm-612-kmod' "$work/plan.log" && grep -q 'nvidia-driver' "$work/plan.log"
! grep -q 'other' "$work/plan.log"
grep -q 'mesa-dri' "$work/plan.log" && grep -q 'xwayland' "$work/plan.log" && grep -q 'tigervnc' "$work/plan.log" || true

STUB_FETCH=fail expect_refusal 'a silent shard' 'does not answer'
STUB_UPDATE=bad expect_refusal 'an unsigned or wrongly signed catalogue' 'unsigned, signed with another key'
STUB_INSTALL=bad expect_refusal 'roots that do not resolve' 'do not resolve without pkg.FreeBSD.org'
MIRROR_URLS=https://evil.example/packages-16-amd64-x expect_refusal 'a foreign URL' 'not one of our release feeds'
PUBKEY="$work/missing.pub" expect_refusal 'a missing key' 'public key'
if env PATH="$work/bin:$PATH" ISO_REPO="$work/iso" PUBKEY="$work/key.pub" ABI=FreeBSD:16:amd64 \
    sh "$here/scripts/check-closure-feed.sh" 2>/dev/null; then echo 'Accepted a run with no shard URLs' >&2; exit 1; fi

# build-iso.sh makes the check mandatory for release builds and takes the feed from PACKAGE_MIRROR_URLS.
grep -q 'REQUIRE_PACKAGE_MIRROR' "$here/build-iso.sh"
grep -q 'check-closure-feed.sh' "$here/build-iso.sh"
sh -n "$here/scripts/check-closure-feed.sh"
echo 'PASS: closure feed gate refuses a missing, silent, unsigned or non-resolving feed'
