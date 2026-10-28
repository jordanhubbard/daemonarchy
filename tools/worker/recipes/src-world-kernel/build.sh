#!/bin/sh
# shellcheck disable=SC2154 # the worker supplies P_*, STEP*, JOB_ID, WORK_DIR and OUT_DIR
# Steps of the src-world-kernel recipe.  ACTION comes from the recipe; the
# typed parameters P_target_arch, P_kernconf and P_jobs from the job.  Nothing
# here needs root: the install uses -DNO_ROOT and records ownership in METALOG.
set -eu

src=$WORK_DIR/src
stage=$WORK_DIR/stage
case $P_target_arch in
amd64) target=amd64 ;;
aarch64) target=arm64 ;;
*) echo "unsupported TARGET_ARCH $P_target_arch" >&2; exit 1 ;;
esac
jobs=$P_jobs
[ "$jobs" -gt 0 ] || jobs=$(sysctl -n hw.ncpu 2>/dev/null || getconf _NPROCESSORS_ONLN)

export MAKEOBJDIRPREFIX="$WORK_DIR/obj"
export SRCCONF=/dev/null __MAKE_CONF=/dev/null
mk() { make -C "$src" -j"$jobs" TARGET="$target" TARGET_ARCH="$P_target_arch" KERNCONF="$P_kernconf" "$@"; }

started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
case $ACTION in
buildworld)
	mk buildworld
	;;
buildkernel)
	mk buildkernel
	;;
stage)
	rm -rf "$stage"
	mkdir -p "$stage/world" "$stage/kernel"
	mk -DNO_ROOT DESTDIR="$stage/world" METALOG="$stage/world/METALOG" installworld distribution
	mk -DNO_ROOT DESTDIR="$stage/kernel" METALOG="$stage/kernel/METALOG" installkernel
	;;
sets)
	(cd "$stage/world" && tar -cJf "$OUT_DIR/base.txz" --exclude ./usr/lib/debug @METALOG)
	(cd "$stage/kernel" && tar -cJf "$OUT_DIR/kernel.txz" @METALOG)
	{
		echo "recipe: src-world-kernel"
		echo "job: $JOB_ID"
		echo "src: $(cat "$OUT_DIR/src.commit")"
		echo "target: $target/$P_target_arch kernconf: $P_kernconf"
		echo "host: $(uname -n) $(uname -r)"
	} >"$OUT_DIR/build-info.txt"
	;;
*)
	echo "unknown ACTION $ACTION" >&2
	exit 1
	;;
esac
printf '%s %s %s\n' "$ACTION" "$started" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$OUT_DIR/$ACTION.done"
