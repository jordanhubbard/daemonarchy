#!/bin/sh
# Run as the installed desktop user, after boot. No checkout mutations.
set -eu
ports=${1:?usage: installed-checkouts.sh true|false true|false}
src=${2:?usage: installed-checkouts.sh true|false true|false}
catalog=/usr/local/share/daemonarchy-installer/checkouts.json
test -x /usr/local/sbin/daemonarchy-checkouts
test -s "$catalog"
for kind in ports src; do
	selected=$ports
	[ "$kind" != src ] || selected=$src
	case "$selected" in true|false) ;; *) exit 2 ;; esac
	tree=/usr/$kind
	if [ "$selected" = false ]; then
		test ! -e "$tree/.git"
		echo "    ok    $kind checkout not selected"
		continue
	fi
	revision=$(jq -r --arg k "$kind" '.trees[$k].revision' "$catalog")
	branch=$(jq -r --arg k "$kind" '.trees[$k].branch' "$catalog")
	remote=$(jq -r --arg k "$kind" '.trees[$k].remote' "$catalog")
	tracking=$(jq -r --arg k "$kind" '.trees[$k] | .tracking_branch // .branch' "$catalog")
	test "$(stat -f %u "$tree")" = "$(id -u)"
	test "$(stat -f %u "$tree/.git")" = "$(id -u)"
	test -w "$tree/.git/config"
	test "$(git -C "$tree" rev-parse HEAD)" = "$revision"
	test "$(git -C "$tree" symbolic-ref --short HEAD)" = "$branch"
	test "$(git -C "$tree" rev-parse --is-shallow-repository)" = true
	test "$(git -C "$tree" rev-list --count HEAD)" = 1
	test "$(git -C "$tree" remote get-url origin)" = "$remote"
	test "$(git -C "$tree" config remote.origin.fetch)" = "+refs/heads/$tracking:refs/remotes/origin/$tracking"
	test "$(git -C "$tree" rev-parse '@{upstream}')" = "$revision"
	test -z "$(git -C "$tree" status --porcelain)"
	test ! -e "$tree/.git/objects/info/alternates"
	git -C "$tree" fsck --connectivity-only
	if [ "$kind" = src ]; then
		/usr/local/bin/bash -c 'source /usr/local/sbin/daemonarchy-checkouts; checkout_kernel_matches "$1" /boot/kernel/kernel' checkout-test "$revision"
	fi
	echo "    ok    $kind is a clean, owned, depth-1 checkout at $revision"
done
