#!/bin/sh
# shellcheck disable=SC2154 # the worker supplies P_*, STEP*, JOB_ID, WORK_DIR and OUT_DIR
# Cleanup hook for the stage step: an interrupted -DNO_ROOT install leaves
# only files under work/stage, which the next attempt replaces.  Remove it so
# a cancelled job does not hold the space.
echo "cleanup: removing partial staging root ($STEP_RESULT)"
chmod -R u+w "$WORK_DIR/stage" 2>/dev/null
rm -rf "$WORK_DIR/stage"
