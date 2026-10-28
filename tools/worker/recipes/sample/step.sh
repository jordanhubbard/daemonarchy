#!/bin/sh
# shellcheck disable=SC2154 # the worker supplies P_*, STEP*, JOB_ID, WORK_DIR and OUT_DIR
# Step script for the "sample" recipe.  Everything it knows arrives in the
# environment the worker builds: STEP, STEP_NAME, WORK_DIR, OUT_DIR and the
# typed parameters P_delay, P_fail_step, P_fail_mode, P_label, P_note.
set -eu

echo "sample step $STEP ($STEP_NAME) of job $JOB_ID starting"
mkdir -p "$(dirname "$P_note")"
echo "step $STEP ran at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$P_note"

i=0
while [ "$i" -lt "$P_delay" ]; do
	sleep 1
	i=$((i + 1))
	echo "step $STEP: $i/$P_delay"
done

if [ "$P_fail_step" = "$STEP" ]; then
	marker=$WORK_DIR/.failed-once-$STEP
	if [ "$P_fail_mode" = always ] || [ ! -e "$marker" ]; then
		: >"$marker"
		echo "step $STEP failing on request (fail_mode=$P_fail_mode)" >&2
		exit 1
	fi
	echo "step $STEP already failed once; succeeding now"
fi

case $STEP_NAME in
prepare)
	echo "$P_label" >"$WORK_DIR/label"
	;;
compute)
	printf '%s computed %s\n' "$(cat "$WORK_DIR/label")" "$(uname -m)" >"$OUT_DIR/compute.txt"
	;;
package)
	{
		echo "daemonarchy-worker sample output"
		echo "job: $JOB_ID"
		echo "label: $(cat "$WORK_DIR/label")"
		cat "$OUT_DIR/compute.txt"
	} >"$OUT_DIR/sample-output.txt"
	;;
esac
echo "sample step $STEP ($STEP_NAME) done"
