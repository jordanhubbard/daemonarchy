#!/bin/sh
# ARCH-001 1.4.1 arm64 step 2: ports tree at the pin, new jail from the new sets, reused package repo, bulk dry run. Run as root.
set -eu
A=/home/jkh/a141
J=16aarch64r2; PT=daemonarchy141
cache=/var/cache/daemonarchy-iso-aarch64-303b364
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $A/state; }
P=/usr/local/poudriere
state ports-tree
poudriere ports -d -p $PT >/dev/null 2>&1 || true
poudriere ports -c -p $PT -m null -M $A/ports-0e8fb88
cp /usr/local/etc/poudriere.d/daemonarchy-poudriere.conf /usr/local/etc/poudriere.d/$PT-poudriere.conf
cp /usr/local/etc/poudriere.d/daemonarchy-make.conf /usr/local/etc/poudriere.d/$PT-make.conf
state jail
poudriere jail -d -j $J -y >/dev/null 2>&1 || true
poudriere jail -c -j $J -a arm64.aarch64 -v 16.0-CURRENT -m tar=$cache/base.txz > $A/jail.log 2>&1
jr=$P/jails/$J
tar -xpf $cache/kernel.txz -C $jr
[ -f $cache/lib32.txz ] && tar -xpf $cache/lib32.txz -C $jr || true
mkdir -p $jr/usr/src
tar -cf - --exclude .git -C /usr/src . | tar -xpf - -C $jr/usr/src
k=/usr/obj/usr/src/arm64.aarch64/sys/GENERIC/kernel
cmp $jr/boot/kernel/kernel $k && echo jail-kernel-is-built-kernel
state repo-copy
mkdir -p $P/data/packages
rm -rf $P/data/packages/$J-$PT
cp -Rp $P/data/packages/16aarch64-daemonarchy $P/data/packages/$J-$PT
# A tar-method jail's version is "16.0-CURRENT"; the src-method jails that built this repository
# recorded "16.0-CURRENT 1600029". Same OSVERSION: align the token or poudriere cleans every package.
for f in $P/data/packages/$J-$PT/.real_*/.jailversion; do echo "16.0-CURRENT" > "$f"; done
state dry-run
poudriere bulk -n -j $J -p $PT -b latest -f /var/log/daemonarchy-build/bulk-20261026/aarch64-ports.list > $A/bulk-dry.log 2>&1 || true
grep -E 'Queued|to be built|to be fetched|Would|Dry' $A/bulk-dry.log | tail -8
state done-step2
