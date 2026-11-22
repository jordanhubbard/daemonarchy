# SPDX-License-Identifier: BSD-2-Clause
# Opt-in EFI framebuffer software desktop control for private hwtrace images.
# The capsule has its own accounts and libraries in a volatile tmpfs; it does
# not install packages or change the rescue root. Native rendering/input and
# physical board qualification remain separate from successful process launch.
hwtrace_desktop_start() {
	local control=/sbin/hwtrace-desktop-control root=/var/tmp/daemonarchy-desktop-boot
	local payload=/usr/local/share/hwtrace/desktop-runtime.tar.gz output pid
	[ -x "$control" ] && [ -r "$payload" ] || return 1
	# Load after kernel subsystem initialization, rather than in loader.conf.
	for module in lindebugfs linuxkpi_hdmi linuxkpi_video dmabuf drm efifb_drm; do
		kldstat -q -n "$module.ko" || kldload "/boot/modules/$module.ko" || return 1
	done
	[ -c /dev/dri/card0 ] || return 1
	"$control" init "$root" || return 1
	LC_ALL=C tar -xzf "$payload" -C "$root" || return 1
	# Keep the verified capsule's original Pi 4 control configuration intact.
	cat >"$root/usr/local/etc/daemonarchy-display-lab/boot.conf" <<'CONF'
font pango:DejaVu Sans Mono 12
output * bg "#203040" solid_color
xwayland disable
bindsym Mod4+Return exec /usr/local/bin/foot
bindsym Mod4+Shift+e exit
exec /usr/local/bin/foot --title='Daemonarchy Pi display control' /bin/sh -c 'printf "Daemonarchy Pi display control\nWayland software rendering\nSuper+Enter: terminal; Super+Shift+E: exit\n"; /usr/bin/uname -m; exec /bin/sh'
CONF
	"$control" devfs "$root" || return 1
	"$control" launch-root "$root" /usr/local/bin/seatd -g video -l debug || return 1
	"$control" wait-socket "$root" var/run/seatd.sock 15 || return 1
	output=$("$control" launch-user "$root" /usr/local/bin/sway -d \
	    -c /usr/local/etc/daemonarchy-display-lab/boot.conf) || return 1
	printf '%s\n' "$output"
	pid=${output#pid=}; pid=${pid%% *}
	case $pid in ''|*[!0-9]*) return 1 ;; esac
	"$control" wait-socket "$root" "var/run/displaytest/sway-ipc.1001.$pid.sock" 20 || return 1
	HW_DESKTOP_PID=$pid
	return 0
}
