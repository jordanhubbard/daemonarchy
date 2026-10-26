# shellcheck shell=sh
# Sourced by poudriere image (-A) after the live system is populated in
# ${WRKDIR}/world. Turns a plain FreeBSD image into the Daemonarchy installer:
# root logs in on the first console and that login starts the installer.

world=${WRKDIR}/world

# Enterprise Wi-Fi needs Python's runtime on the live image. Its development
# archive, regression suite and duplicate optimized caches are not used by the
# installer. Prune only this disposable live root after package installation;
# the downloaded Python package and the installed desktop remain complete.
for python_lib in "$world"/usr/local/lib/python3.[0-9]*; do
	[ -d "$python_lib" ] || continue
	[ ! -L "$python_lib" ] || { echo 'Refusing a symlinked live Python library' >&2; exit 1; }
	find "$python_lib" -type f \( -name '*.a' -o -name '*.opt-1.pyc' -o -name '*.opt-2.pyc' \) -delete
	[ ! -d "$python_lib/test" ] || rm -r "$python_lib/test"
done

# Autologin on ttyv0. The installer runs from a login rather than rc.local so
# it has a controlling terminal: gum draws on /dev/tty.
cat >>"$world/etc/gettytab" <<'EOF'

# Daemonarchy installer: log root in on the console.
al.Pc|Daemonarchy installer console:\
	:al=root:tc=Pc:
EOF
sed -i '' -E 's|^ttyv0[[:space:]].*|ttyv0	"/usr/libexec/getty al.Pc"	xterm	onifexists secure|' "$world/etc/ttys"

cat >>"$world/root/.profile" <<'EOF'

# Start the Daemonarchy installer once, on the first console. The loader's
# live entry first runs the live desktop; whenever it ends or cannot start,
# the text installer takes over this console.
if [ "$(tty)" = /dev/ttyv0 ] && [ ! -e /tmp/.daemonarchy-installer ]; then
	touch /tmp/.daemonarchy-installer
	export TERM=xterm-256color
	if [ "$(kenv -q daemonarchy_live 2>/dev/null)" = YES ]; then
		export DAEMONARCHY_LIVE=1
		/usr/local/libexec/daemonarchy-installer/live-session
	fi
	exec /usr/local/libexec/daemonarchy-installer/launch
fi
EOF

# The root filesystem is the read-only ISO: keep /var in memory and point the
# files DHCP rewrites at /tmp.
cat >"$world/etc/rc.conf" <<'EOF'
hostname="daemonarchy-installer"
root_rw_mount="NO"
varmfs="YES"
varsize="256m"
populate_var="YES"
ifconfig_DEFAULT="DHCP"
# HTTPS package downloads require a valid clock, including on machines whose
# hardware clock has reset. Allow ntpd's initial correction to exceed 1000s.
ntpd_enable="YES"
ntpd_sync_on_start="YES"
sendmail_enable="NONE"
cron_enable="NO"
update_motd="NO"
# Never use a disk for crash dumps or swap, and never import pools at boot,
# on either the text installer or the live desktop.
dumpdev="NO"
savecore_enable="NO"
zfs_enable="NO"
# Copies /etc, /usr/local/etc, /root and /home into memory, only after the
# loader's live desktop entry (see /etc/rc.d/daemonarchy_live).
daemonarchy_live_enable="YES"
EOF
if [ -f "$world/boot/modules/if_brcmfmac.ko" ]; then
    # Keep wireless DHCP behind WPA authentication on either firmware path.
    echo 'ifconfig_wlan0="NOAUTO"' >>"$world/etc/rc.conf"
fi
if [ -f "$world/boot/modules/if_brcmfmac.ko" ] &&
   [ -f "$world/boot/firmware/brcmfmac4364b3-pcie.bin" ]; then
    # A private preview can preload board firmware. Public images acquire it
    # in the installer before attaching the radio.
    echo 'kld_list="if_brcmfmac"' >>"$world/etc/rc.conf"
fi
ln -sf /tmp/resolv.conf "$world/etc/resolv.conf"
echo 'resolv_conf=/tmp/resolv.conf' >"$world/etc/resolvconf.conf"

cat >>"$world/boot/loader.conf" <<'EOF'
autoboot_delay="3"
loader_logo="none"
loader_brand="daemonarchy"
kern.vty="vt"
# Keep ordinary panic evidence visible during hardware qualification.
kern.panic_reboot_wait_time="-1"
debug.trace_on_panic="1"
# Offers "Try Daemonarchy (live desktop, disk untouched)" in the loader menu
# (brand-daemonarchy.lua). Return still boots the text installer.
daemonarchy_live_media="YES"
EOF
if [ -f "$world/boot/modules/if_brcmfmac.ko" ]; then
    # The diagnostic MacBook keyboard stalls on LED output reports. This
    # kernel's existing boot tunable keeps input usable during bring-up.
    echo 'hw.hid.hkbd.no_leds="1"' >>"$world/boot/loader.conf"
fi
cp "$world/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua" "$world/boot/lua/"

# Live desktop (LIVE-001). The service is a no-op unless the loader entry
# set daemonarchy_live=YES. Nothing on this path uses unionfs: a unionfs
# probe over this ISO's /etc stopped a FreeBSD 16-CURRENT host during pw's
# password database rename. Configuration is copied into tmpfs instead, and
# GPU payloads are only added on tmpfs layers.
install -m 0555 "$world/usr/local/libexec/daemonarchy-installer/live-service" "$world/etc/rc.d/daemonarchy_live"
mkdir -p "$world/live" "$world/home"
if [ -x "$world/usr/local/bin/Hyprland" ]; then
	live_uid=1000
	pw -R "$world" groupshow video >/dev/null || { echo 'The live root lacks the video group' >&2; exit 1; }
	if ! pw -R "$world" usershow live >/dev/null 2>&1; then
		pw -R "$world" useradd -n live -u "$live_uid" -c 'Daemonarchy live desktop' \
			-d /home/live -s /usr/local/bin/bash -G video -w no || exit 1
	fi
	install -d -o "$live_uid" -g "$live_uid" -m 0750 "$world/home/live" "$world/home/live/.config" "$world/home/live/.config/hypr"
	install -o "$live_uid" -g "$live_uid" -m 0644 \
		"$world/usr/local/share/daemonarchy-installer/live/hyprland.lua" "$world/home/live/.config/hypr/hyprland.lua"
	# The live desktop is a demo and installer that the person at the keyboard
	# controls completely, not a server: the live account gets passwordless
	# sudo (operator decision, LIVE-001). The text installer already runs as
	# root on ttyv0, and the graphical installer still calls only live-backend.
	install -d -m 0750 "$world/usr/local/etc/sudoers.d"
	printf '%s\n' 'live ALL=(ALL) NOPASSWD: ALL' \
		>"$world/usr/local/etc/sudoers.d/daemonarchy-live"
	chmod 0440 "$world/usr/local/etc/sudoers.d/daemonarchy-live"
	# Trim only this disposable live root: compiler toolchains, headers,
	# static archives and documentation that desktop packages pull in as
	# dependencies. Shared libraries stay; live-image-runtime.sh rejects any
	# retained executable or library whose dependencies no longer resolve.
	echo "Live /usr/local before desktop trim: $(du -sm "$world/usr/local" | cut -f1) MiB"
	for llvm in "$world"/usr/local/llvm[0-9]*; do
		[ -d "$llvm" ] && [ ! -L "$llvm" ] || continue
		rm -rf "$llvm/bin" "$llvm/include" "$llvm/libexec" "$llvm/share" "$llvm/lib/clang" "$llvm/lib/cmake"
		find "$llvm/lib" -type f -name '*.a' -delete
	done
	for gcc in "$world"/usr/local/libexec/gcc[0-9]* "$world"/usr/local/lib/gcc[0-9]*/gcc; do
		[ -d "$gcc" ] && [ ! -L "$gcc" ] || continue
		rm -rf "$gcc"
	done
	rm -rf "$world/usr/local/include" "$world/usr/local/share/doc" "$world/usr/local/share/gtk-doc" \
		"$world/usr/local/share/info" "$world/usr/local/share/examples"
	find "$world/usr/local/lib" -type f -name '*.a' -delete
	echo "Live /usr/local after desktop trim: $(du -sm "$world/usr/local" | cut -f1) MiB"
fi

secureboot_payload="$world/usr/local/share/daemonarchy-installer/secureboot"
if [ -d "$secureboot_payload" ]; then
    /usr/local/bin/python3.12 "$secureboot_payload/maintenance.py" install \
        "$secureboot_payload/bundle.txz" --signature "$secureboot_payload/bundle.txz.sig" \
        --certificate "$secureboot_payload/certificate.pem" --root "$world" || exit 1
fi

# Poudriere creates the EFI boot image from this live root after this hook.
# The selected loader and Lua entrypoint affect only the live medium, not sets.
test_loader="$world/usr/local/share/daemonarchy-installer/test-loader"
if [ -d "$test_loader" ]; then
    /usr/local/bin/python3.12 "$test_loader/install.py" install \
        --bundle "$test_loader" --root "$world" || exit 1
fi
