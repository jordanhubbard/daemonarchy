#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# DRAFT retained-run wrapper for build-iso.sh: environment and output mapping.
#
#   sh tools/retained-draft/run-build-iso.sh OUTDIR
#
# The retained profile gives a command only argv, a private HOME/TMPDIR and a PATH of
# captured tool directories; it cannot set environment variables.  This wrapper maps the
# reviewed variables in build-iso.env onto build-iso.sh and sends every output (the ISO,
# its .xz and their .sha256 files) to OUTDIR, which the profile passes as
# {output_root}/images.  The ISO staging directory goes to the run's private TMPDIR.
#
# build-iso.sh needs root: poudriere image mounts and runs in a jail (build-iso.sh header
# "run as root").  The wrapper refuses to run otherwise.  It never reads, names or copies
# a signing key; build-iso.sh itself accepts only public secure-boot artifacts.
set -eu
[ $# -eq 1 ] || { echo 'usage: run-build-iso.sh OUTDIR' >&2; exit 2; }
out=$1
here=$(cd "$(dirname "$0")/../.." && pwd)
[ "$(id -u)" = 0 ] || { echo 'run-build-iso.sh: build-iso.sh requires root (poudriere image)' >&2; exit 1; }
case "$out" in /*) ;; *) echo 'OUTDIR must be absolute' >&2; exit 2 ;; esac
[ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ] || { echo 'the retained run must provide TMPDIR' >&2; exit 2; }
set -a
. "$here/tools/retained-draft/build-iso.env"
set +a
PACKAGE_REPOSITORY_PUBLIC_KEY=$here/keys/pkg-repo-1.3.1.pub
OUTDIR=$out
ISO_STAGE_PARENT=$TMPDIR
# Captured tools first; the base system directories follow only because poudriere's own
# helper commands are not all enumerated (UNKNOWN: see closure-inventory.json "ambient").
PATH=$here/closure/toolchain/bin:/sbin:/bin:/usr/sbin:/usr/bin
export PACKAGE_REPOSITORY_PUBLIC_KEY OUTDIR ISO_STAGE_PARENT PATH
mkdir -p "$OUTDIR"
cd "$here"
# Keep the build's own console output with the export (the verifier scans it for error text,
# not only the exit status) and install the deterministic verifier beside the ISO.
rc=0
sh ./build-iso.sh >"$OUTDIR/build-iso.log" 2>&1 || rc=$?
cat "$OUTDIR/build-iso.log"
install -m 0755 "$here/tools/retained-draft/daemonarchy-verify.sh" "$OUTDIR/daemonarchy-verify"
exit "$rc"
