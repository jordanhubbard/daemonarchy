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

# Start the Daemonarchy installer once, on the first console.
if [ "$(tty)" = /dev/ttyv0 ] && [ ! -e /tmp/.daemonarchy-installer ]; then
	touch /tmp/.daemonarchy-installer
	export TERM=xterm-256color
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
EOF
if [ -f "$world/boot/modules/if_brcmfmac.ko" ]; then
    # The preview image carries a kernel-matched Broadcom module and firmware.
    # Load it after the live root is mounted, before netif enumerates radios.
    echo 'kld_list="if_brcmfmac"' >>"$world/etc/rc.conf"
    # ifconfig_DEFAULT=DHCP is for ready-to-use wired adapters. The installer
    # starts wireless DHCP only after wpa_supplicant authenticates wlan0.
    echo 'ifconfig_wlan0="NOAUTO"' >>"$world/etc/rc.conf"
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
EOF
if [ -f "$world/boot/modules/if_brcmfmac.ko" ]; then
    # The diagnostic MacBook keyboard stalls on LED output reports. This
    # kernel's existing boot tunable keeps input usable during bring-up.
    echo 'hw.hid.hkbd.no_leds="1"' >>"$world/boot/loader.conf"
fi
cp "$world/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua" "$world/boot/lua/"

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
