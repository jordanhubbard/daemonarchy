#!/bin/sh
# shellcheck disable=SC2154 # the worker supplies P_*, STEP*, JOB_ID, WORK_DIR and OUT_DIR
# Shared step: fetch one pinned input repository into $WORK_DIR/$INPUT.
# The recipe step sets INPUT; the worker supplies PIN_<input> (a full commit
# hash the client pinned) and REMOTE_<input> (from the builder's own
# worker.conf, never from the client).  Writes $OUT_DIR/<input>.commit.
set -eu

: "${INPUT:?recipe step must set INPUT}"
eval "pin=\${PIN_$INPUT:-}"
eval "remote=\${REMOTE_$INPUT:-}"
[ -n "$pin" ] || { echo "no pin for input $INPUT" >&2; exit 1; }
[ -n "$remote" ] || { echo "builder has no remote_$INPUT in worker.conf" >&2; exit 1; }

dir=$WORK_DIR/$INPUT
if [ -d "$dir/.git" ] && [ "$(git -C "$dir" rev-parse HEAD 2>/dev/null)" = "$pin" ]; then
	echo "$INPUT already at $pin"
else
	rm -rf "$dir"
	git init -q "$dir"
	git -C "$dir" remote add origin "$remote"
	echo "fetching $INPUT $pin from $remote"
	git -C "$dir" fetch --depth 1 --no-tags origin "$pin"
	git -C "$dir" checkout -q --detach FETCH_HEAD
fi
got=$(git -C "$dir" rev-parse HEAD)
[ "$got" = "$pin" ] || { echo "fetched $got, wanted $pin" >&2; exit 1; }
printf '%s %s\n' "$pin" "$remote" >"$OUT_DIR/$INPUT.commit"
echo "$INPUT pinned at $pin"
