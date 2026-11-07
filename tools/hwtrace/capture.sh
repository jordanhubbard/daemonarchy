#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Sourced after mounting DATRACE synchronously. Keep a checkpoint before
# each probe: a kernel hang cannot be rescued by a userspace timeout.
hwtrace_capture() {
	hw_file=$1
	shift
	printf 'start %s\n' "$hw_file" >>"$d/capture.log"
	sync
	if timeout -k 2 "${HWTRACE_CAPTURE_TIMEOUT:-20}" "$@" >"$d/$hw_file" 2>&1; then
		hw_status=0
	else
		hw_status=$?
	fi
	printf 'finish %s status=%s\n' "$hw_file" "$hw_status" >>"$d/capture.log"
	sync
}

hwtrace_collect() {
	hwtrace_capture dmesg.txt dmesg -a
	hwtrace_capture kenv.txt kenv
	hwtrace_capture sysctl.txt sysctl -a
	hwtrace_capture kldstat.txt kldstat -v
	hwtrace_capture pciconf.txt pciconf -lvbc
	hwtrace_capture devinfo.txt devinfo -vr
	hwtrace_capture usbconfig.txt usbconfig dump_device_desc
	# -d needs iasl and writable temporary storage, absent in this root.
	# Do physical-memory access last, after the other evidence is durable.
	hwtrace_capture acpidump.txt acpidump -t
	date >"$d/done.txt"
	sync
}
