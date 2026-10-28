#!/bin/sh
# shellcheck disable=SC2154 # the worker supplies P_*, STEP*, JOB_ID, WORK_DIR and OUT_DIR
# Cleanup hook for the sample recipes.  A real recipe detaches memory disks,
# unmounts file systems and stops jails or VMs here.  This one records that it
# ran, so tests can see the hook fire on fail, cancel and interrupt.
echo "cleanup hook: step $STEP ($STEP_NAME) result $STEP_RESULT"
echo "$STEP $STEP_NAME $STEP_RESULT" >>"$WORK_DIR/cleanup.log"
