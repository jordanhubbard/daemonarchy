#!/bin/sh
# shellcheck disable=SC2154 # the worker supplies P_*, STEP*, JOB_ID, WORK_DIR and OUT_DIR
# Step script for "sample-long": each step prints progress every few seconds
# for P_step_seconds seconds, then writes tick-NN.txt.  It ignores nothing:
# SIGTERM ends it, so cancel takes effect at once.
set -eu

name=$STEP_NAME
echo "sample-long $name starting (step $STEP, ${P_step_seconds}s)"
i=0
while [ "$i" -lt "$P_step_seconds" ]; do
	sleep 1
	i=$((i + 1))
	case $((i % 5)) in 0) echo "$name: ${i}s of ${P_step_seconds}s" ;; esac
done
if [ "$P_fail_step" = "$STEP" ]; then
	marker=$WORK_DIR/.failed-once-$STEP
	if [ "$P_fail_mode" = always ] || [ ! -e "$marker" ]; then
		: >"$marker"
		echo "$name failing on request" >&2
		exit 1
	fi
fi
echo "$name finished at $(date -u +%Y-%m-%dT%H:%M:%SZ) on $(uname -n)" >"$OUT_DIR/$name.txt"
if [ "$STEP" = 10 ]; then
	cat "$OUT_DIR"/tick-*.txt >"$OUT_DIR/sample-long-output.txt"
fi
echo "sample-long $name done"
