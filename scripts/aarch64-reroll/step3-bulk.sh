#!/bin/sh
# ARCH-001 1.4.1 arm64 step 3: poudriere bulk of the arm64 package list at the ports pin. Run as root.
set -eu
A=/home/jkh/a141
J=16aarch64r2; PT=daemonarchy141
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $A/state; }
state bulk
timeout -k 300 21600 poudriere bulk -j $J -p $PT -b latest -J 2 -f /var/log/daemonarchy-build/bulk-20261026/aarch64-ports.list > $A/bulk.log 2>&1 || echo "bulk-nonzero $?" >> $A/state
state bulk-done
tail -n 25 $A/bulk.log | cut -c1-200 > $A/bulk-tail.txt
D=/usr/local/poudriere/data/packages/$J-$PT
ls $D/.latest/All | wc -l > $A/pkg-count.txt
ls -la $D/.latest/All/daemonarchy-*.pkg > $A/daemonarchy-pkg.txt
state done-step3
