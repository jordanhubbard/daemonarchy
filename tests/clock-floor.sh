#!/usr/bin/env bash
# daemonarchy_clock: a clock that starts behind the last recorded time moves
# forward to it, a correct clock is left alone, and save records the time.
# Stubs stand in for rc.subr, stat(1) and date(1); the host clock is untouched.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
script=$here/overlay/usr/local/share/daemonarchy-installer/clock/daemonarchy_clock
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

sh -n "$script"
mkdir "$work/bin"
cat >"$work/rc.subr" <<'EOF'
load_rc_config() { :; }
run_rc_command() { eval "\$${1}_cmd"; }
EOF
# stat -f %m FILE prints the recorded time; date +%s prints the fake clock,
# and date -f %s N sets it.
cat >"$work/bin/stat" <<EOF
#!/bin/sh
[ -e "\$3" ] && cat "$work/recorded" 2>/dev/null
EOF
cat >"$work/bin/date" <<EOF
#!/bin/sh
case "\$1" in
  +%s) cat "$work/now" ;;
  -f) echo "\$3" >"$work/now"; echo set >>"$work/sets" ;;
  *) echo 'stub date' ;;
esac
EOF
cat >"$work/bin/touch" <<EOF
#!/bin/sh
cp "$work/now" "$work/recorded"; command -p touch "\$@"
EOF
chmod +x "$work/bin/"*
sed "s|^\. /etc/rc.subr|. $work/rc.subr|" "$script" >"$work/daemonarchy_clock"
run() {
  PATH=$work/bin:$PATH daemonarchy_clock_file=$work/db/clock sh "$work/daemonarchy_clock" "$1"
}

# First boot: no record yet, so start records one and changes nothing.
echo 1000 >"$work/now"
run start >/dev/null
[[ -e $work/db/clock && $(cat "$work/recorded") == 1000 ]] || fail 'first boot did not record the time'
[[ ! -e $work/sets ]] || fail 'first boot set the clock'

# The T2 case: the record says 1793157000 and the clock says January 1970.
echo 1793157000 >"$work/now"
run save
echo 1388943 >"$work/now"
out=$(run start)
[[ $(cat "$work/now") == 1793157000 ]] || fail 'a clock behind the record was not moved forward'
[[ $out == *'behind the last recorded time'* ]] || fail 'no console note'

# A clock already ahead of the record is left alone.
rm -f "$work/sets"
echo 1793160000 >"$work/now"
run start >/dev/null
[[ ! -e $work/sets && $(cat "$work/now") == 1793160000 ]] || fail 'a correct clock was changed'

# stop (shutdown) and the cron.d save both record the current time.
run stop
[[ $(cat "$work/recorded") == 1793160000 ]] || fail 'shutdown did not record the time'

# The installer installs the script, the cron.d entry and an initial record.
install=$here/overlay/usr/local/libexec/daemonarchy-installer/install
grep -q 'clock/daemonarchy_clock" "$TARGET/usr/local/etc/rc.d/daemonarchy_clock"' "$install" || fail 'installer does not install the rc script'
grep -q 'daemonarchy_clock save' "$install" || fail 'installer does not add the cron.d save'
echo 'PASS: clock floor moves a clock behind the record forward, leaves a correct clock, records at shutdown and from cron'
