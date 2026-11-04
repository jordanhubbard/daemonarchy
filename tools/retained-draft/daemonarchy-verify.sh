#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Deterministic acceptance verifier for the retained installer-image build, exported by the build.
#
#   daemonarchy-verify IMAGES_DIR CHECK     (IMAGES_DIR is the sealed {output_root}/images)
#
# run-build-iso.sh installs this file into the images export (regular file, mode 0755) next to the
# ISO and a copy of the build's own console output (build-iso.log).  The Literate AI acceptance
# policy runs it once per CHECK as an independent case against the sealed outputs.  Every check
# compares against the PINNED expectation below and treats error TEXT as failure, not just exit
# status: any text a tool it runs writes to stderr, and any error pattern in build-iso.log, is
# reported on stderr and fails the case.  On success it prints exactly one fixed line on stdout and
# nothing on stderr.  It never writes into the export, boots nothing, signs nothing, reads no key.
# The pinned values change only with a reviewed change to this file.
set -u
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
export PATH LC_ALL=C

VERSION=1.5.0
ARCH=amd64
ABI=FreeBSD:16:amd64
TAG=packages-16-amd64-1.5.0
RAW_LIMIT=3758096384   # scripts/check-image-size.sh: 3.5 GiB
XZ_LIMIT=2147483648    # 2 GiB
# Error patterns searched for in the captured build output (extended regular expressions).
# The one benign pkg(8) notice the FreeBSD 16.0-CURRENT image build prints for every package it
# installs (pinned exactly, including OSVERSION): lines equal to this are not errors; any other
# `pkg:` line, or this notice with another OSVERSION, still fails.
KNOWN_NOTICE='pkg: Setting ABI requires setting OSVERSION, guessing the OSVERSION as: 1600000'
PATTERNS='(^|[^[:alnum:]])(Error|ERROR|error):|Error code|FAILED|Segmentation fault|Stop\.$|\*\*\* \[|^pkg: |: undefined reference|cc: error|ld: error'

dir=${1:-}; check=${2:-}
[ -n "$dir" ] && [ -d "$dir" ] && [ -n "$check" ] || { echo 'usage: daemonarchy-verify IMAGES_DIR CHECK' >&2; exit 2; }
iso=$dir/daemonarchy-$VERSION-$ARCH.iso
xz=$iso.xz
log=$dir/build-iso.log
problems=0
fail() { printf 'daemonarchy-verify image:%s: %s\n' "$check" "$*" >&2; problems=$((problems + 1)); }
# stderr_of CMD...: run a tool and fail on ANY stderr text, whatever its exit status.
quiet() { _e=$("$@" 2>&1 >/dev/null); [ -z "$_e" ] || fail "$1 wrote to stderr: $_e"; }

# Every check first refuses a build whose own console output carried error text.
if [ -f "$log" ]; then
	hits=$(grep -En "$PATTERNS" "$log" 2>/dev/null | grep -vF ":$KNOWN_NOTICE" | head -n 20)
	[ -z "$hits" ] || fail "error text in build-iso.log: $hits"
else
	fail "build-iso.log missing from the export"
fi

sidecar() { sed -n '1s/[[:space:]].*//p' "$1.sha256" 2>/dev/null; }
case $check in
present)
	[ -f "$iso" ] && [ -f "$xz" ] || fail "$(basename "$iso") or its .xz missing" ;;
sidecar-iso)
	[ -f "$iso" ] || fail "iso missing"
	quiet sha256 -q "$iso"
	[ "$(sha256 -q "$iso" 2>/dev/null)" = "$(sidecar "$iso")" ] || fail "iso sha256 differs from its sidecar" ;;
sidecar-xz)
	[ -f "$xz" ] || fail "xz missing"
	quiet sha256 -q "$xz"
	[ "$(sha256 -q "$xz" 2>/dev/null)" = "$(sidecar "$xz")" ] || fail "xz sha256 differs from its sidecar" ;;
xz-roundtrip)
	[ -f "$xz" ] && [ -f "$iso" ] || fail "iso or xz missing"
	quiet xz -dc "$xz"
	[ "$(xz -dc "$xz" 2>/dev/null | sha256 -q)" = "$(sha256 -q "$iso" 2>/dev/null)" ] || fail "xz does not decompress to the raw iso" ;;
budget-raw)
	[ "$(stat -f %z "$iso" 2>/dev/null || echo "$RAW_LIMIT")" -lt "$RAW_LIMIT" ] || fail "iso is not under $RAW_LIMIT bytes" ;;
budget-xz)
	[ "$(stat -f %z "$xz" 2>/dev/null || echo "$XZ_LIMIT")" -lt "$XZ_LIMIT" ] || fail "xz is not under $XZ_LIMIT bytes" ;;
iso9660)
	quiet dd if="$iso" bs=1 skip=32768 count=7 status=none
	[ "$(dd if="$iso" bs=1 skip=32768 count=7 status=none 2>/dev/null | od -An -tx1 | tr -d ' \n')" = 01434430303101 ] \
		|| fail "no ISO 9660 primary volume descriptor" ;;
image-version)
	quiet bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/version
	v=$(bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/version 2>/dev/null | head -n 1 | sed 's/ (.*//')
	[ "$v" = "$VERSION" ] || fail "image version is '$v', expected $VERSION" ;;
image-abi)
	quiet bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/ABI
	v=$(bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/ABI 2>/dev/null | head -n 1)
	[ "$v" = "$ABI" ] || fail "image ABI is '$v', expected $ABI" ;;
image-tag)
	quiet bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/package-repository-tag
	v=$(bsdtar -xOf "$iso" ./usr/local/share/daemonarchy-installer/package-repository-tag 2>/dev/null | head -n 1)
	[ "$v" = "$TAG" ] || fail "package repository tag is '$v', expected $TAG" ;;
live-sqlite3)
	quiet bsdtar -tf "$iso"
	bsdtar -tf "$iso" 2>/dev/null | grep -q _sqlite3 || fail "live root lacks the _sqlite3 module" ;;
*)
	echo "daemonarchy-verify: unknown check '$check'" >&2; exit 2 ;;
esac

if [ "$problems" -ne 0 ]; then
	printf 'daemonarchy-verify image:%s: FAILED problems=%d\n' "$check" "$problems" >&2
	exit 1
fi
printf 'daemonarchy-verify image:%s OK errors=0\n' "$check"
