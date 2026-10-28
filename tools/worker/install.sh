#!/bin/sh
# Install the Daemonarchy remote worker under DESTDIR (default /):
#   /usr/local/bin/daemonarchy-worker, /usr/local/bin/daemonarchy-remote,
#   /usr/local/etc/rc.d/daemonarchy_worker, the recipes and a sample config.
# Installing enables nothing: run 'daemonarchy-worker enable' to turn it on.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
destdir=${DESTDIR:-}
prefix=$destdir/usr/local

mkdir -p "$prefix/bin" "$prefix/etc/rc.d" "$prefix/etc/daemonarchy-worker" \
    "$prefix/share/daemonarchy-worker"
sed 's/^WORKER_INSTALLED=0$/WORKER_INSTALLED=1/' "$here/daemonarchy-worker" >"$prefix/bin/daemonarchy-worker.new"
grep -q '^WORKER_INSTALLED=1$' "$prefix/bin/daemonarchy-worker.new"
chmod 0555 "$prefix/bin/daemonarchy-worker.new"
mv -f "$prefix/bin/daemonarchy-worker.new" "$prefix/bin/daemonarchy-worker"
install -m 0555 "$here/daemonarchy-remote" "$prefix/bin/daemonarchy-remote"
install -m 0555 "$here/rc.d/daemonarchy_worker" "$prefix/etc/rc.d/daemonarchy_worker"
install -m 0644 "$here/worker.conf.sample" "$prefix/etc/daemonarchy-worker/worker.conf.sample"
rm -rf "$prefix/share/daemonarchy-worker/recipes.new"
cp -R "$here/recipes" "$prefix/share/daemonarchy-worker/recipes.new"
find "$prefix/share/daemonarchy-worker/recipes.new" -type f -exec chmod 0444 {} +
find "$prefix/share/daemonarchy-worker/recipes.new" -type d -exec chmod 0555 {} +
chmod -R u+w "$prefix/share/daemonarchy-worker/recipes" 2>/dev/null || :
rm -rf "$prefix/share/daemonarchy-worker/recipes"
mv "$prefix/share/daemonarchy-worker/recipes.new" "$prefix/share/daemonarchy-worker/recipes"
echo "installed daemonarchy-worker into ${destdir}/usr/local (not enabled)"
