#!/bin/sh
# ARCH-001 1.4.1 arm64 step 5: collect the unsigned application feed from every package poudriere built. Run as root.
set -eu
A=/home/jkh/a141
B=/usr/local/poudriere/data/logs/bulk
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $A/state; }
state collect
for d in 16aarch64-daemonarchy 16aarch64-daemonarchy-drift 16aarch64-daemonarchy-drift2 16aarch64r2-daemonarchy141; do
  for r in $B/$d/20*/; do
    [ -f $r/.poudriere.ports.built ] && cat $r/.poudriere.ports.built
  done
done | awk 'NF>=2 {print $1, $2}' | sort -u > $A/built-packages.txt
wc -l < $A/built-packages.txt
ARCH=aarch64 JAIL=16aarch64r2 PTREE=daemonarchy141 TAG=${PACKAGE_TAG:-packages-16-aarch64-1.4.1} \
  BUILT_PACKAGES_FILE=$A/built-packages.txt OUT=$A/app-feed \
  sh $A/product/pkg-repo.sh collect
ls $A/app-feed | wc -l
du -sh $A/app-feed | cut -f1
ls $A/app-feed | grep -E '^(daemonarchy|omarchy|hyprland|quickshell|owe|cliamp)-' | head -12
state done-step5
