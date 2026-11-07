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
	# Broad enumeration entered vm.phys_locality on the Spark control.
	# Query only reviewed, bounded scalar observations.
	hwtrace_capture sysctl.txt sysctl kern.ostype kern.osrelease kern.version \
	    hw.machine hw.machine_arch hw.model hw.ncpu hw.physmem hw.pagesize \
	    kern.smp.cpus kern.smp.active kern.smp.disabled
	hwtrace_capture kldstat.txt kldstat -v
	hwtrace_capture pciconf.txt pciconf -lvbc
	hwtrace_capture devinfo.txt devinfo -vr
	hwtrace_capture usbconfig.txt usbconfig dump_device_desc
	# ACPI is captured by the loader before kernel entry and decoded offline.
	# A timeout cannot interrupt a kernel stall in acpidump's /dev/mem path.
	printf '%s\n' 'ACPI: see loader ACPI/INDEX.TXT; no live /dev/mem probe' \
	    >"$d/acpi-source.txt"
	sync
	date >"$d/done.txt"
	sync
}
