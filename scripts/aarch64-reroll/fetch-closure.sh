#!/bin/sh
# ARCH-001: fetch the 552 hosted upstream aarch64 archives into a pkg cache on daemon.local, then stage the signed shard. Run as root.
set -eu
W=/home/jkh/a141-stage
PY=/usr/local/bin/python3.12
state() { echo "$1 $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $W/state; }
state fetch-start
rm -rf $W/root $W/repos $W/cache $W/out
mkdir -p $W/root/usr/share/keys $W/repos $W/cache
cp -R /usr/share/keys/pkg $W/root/usr/share/keys/
cat > $W/repos/FreeBSD.conf <<EOF
FreeBSD: {
  url: "pkg+https://pkg.FreeBSD.org/\${ABI}/latest",
  mirror_type: "srv",
  signature_type: "fingerprints",
  fingerprints: "/usr/share/keys/pkg",
  enabled: yes
}
EOF
PKG="env ASSUME_ALWAYS_YES=yes IGNORE_OSVERSION=yes pkg -r $W/root -o REPOS_DIR=$W/repos -o ABI=FreeBSD:16:aarch64 -o PKG_DBDIR=$W/root/db -o PKG_CACHEDIR=$W/cache"
$PKG update -f > $W/update.log 2>&1
nice -n 10 $PY $W/parallel-fetch --plan $W/hosted-plan.txt --cache $W/cache --workers 4 --repo-workers FreeBSD=4 -- $PKG > $W/fetch.log 2>&1 || { echo "fetch-exit=$?" >> $W/state; exit 1; }
state fetch-done
ls $W/cache | wc -l > $W/cache-count.txt
du -sk $W/cache | cut -f1 > $W/cache-kb.txt
state done-fetch
