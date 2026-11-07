#!/bin/sh
# SPDX-License-Identifier: BSD-2-Clause
# Exercise real timeout/kill behavior and simulated persistence checkpoints.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin" "$tmp/dumps" "$tmp/stable"
fail() { echo "FAIL: $*" >&2; exit 1; }
cat >"$tmp/bin/probe" <<'SH'
#!/bin/sh
name=${0##*/}
echo "$name $*"
case $name in
sysctl)
	case " $* " in *" -a "*|*" vm.phys_locality "*) exit 86 ;; esac
	[ "${TEST_FAILURE:-0}" = 0 ] || exit 7 ;;
acpidump) exit 88 ;;
usbconfig)
	# A late hang must not erase the completed earlier observations.
	for file in dmesg.txt kenv.txt sysctl.txt kldstat.txt pciconf.txt devinfo.txt; do
		[ -s "$TEST_STABLE/$file" ] || exit 87
	done
	if [ "${TEST_HANG:-0}" = 1 ]; then
		trap '' TERM
		sleep 60
	fi ;;
esac
exit 0
SH
cat >"$tmp/bin/sync" <<'SH'
#!/bin/sh
cp "$TEST_DUMPS/"* "$TEST_STABLE/"
SH
chmod +x "$tmp/bin/"*
for name in dmesg kenv sysctl kldstat pciconf devinfo usbconfig acpidump; do
	ln -s probe "$tmp/bin/$name"
done
PATH=$tmp/bin:$PATH
export PATH TEST_DUMPS=$tmp/dumps TEST_STABLE=$tmp/stable HWTRACE_CAPTURE_TIMEOUT=1
d=$TEST_DUMPS
. "$here/tools/hwtrace/capture.sh"
hwtrace_collect
grep -q '^finish usbconfig.txt status=0$' "$d/capture.log" || fail 'normal final probe'
[ ! -e "$d/acpidump.txt" ] || fail 'unsafe ACPI probe ran'
[ -s "$TEST_STABLE/done.txt" ] || fail 'completion not flushed'
rm -f "$d/"* "$TEST_STABLE/"*
export TEST_FAILURE=1 TEST_HANG=1
hwtrace_collect
grep -q '^finish sysctl.txt status=7$' "$d/capture.log" || fail 'probe failure not recorded'
grep -q '^finish kldstat.txt status=0$' "$d/capture.log" || fail 'stopped after probe failure'
grep -Eq '^finish usbconfig.txt status=(124|137)$' "$d/capture.log" || fail 'hung probe not killed'
[ -s "$TEST_STABLE/devinfo.txt" ] || fail 'earlier output lost on timeout'
[ -s "$TEST_STABLE/done.txt" ] || fail 'timeout prevented completion'
echo 'PASS: diagnostic failure and TERM-resistant hang preserve prior files and finish'
