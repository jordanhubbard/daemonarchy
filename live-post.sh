# Sourced by poudriere image (-A) after the live system is populated in
# ${WRKDIR}/world. Turns a plain FreeBSD image into the Daemonarchy installer:
# root logs in on the first console and that login starts the installer.

world=${WRKDIR}/world

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
sendmail_enable="NONE"
cron_enable="NO"
update_motd="NO"
EOF
ln -sf /tmp/resolv.conf "$world/etc/resolv.conf"
echo 'resolv_conf=/tmp/resolv.conf' >"$world/etc/resolvconf.conf"

cat >>"$world/boot/loader.conf" <<'EOF'
autoboot_delay="3"
loader_logo="none"
loader_brand="daemonarchy"
kern.vty="vt"
EOF
cp "$world/usr/local/share/daemonarchy-installer/brand-daemonarchy.lua" "$world/boot/lua/"
