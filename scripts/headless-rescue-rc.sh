#!/bin/sh
# PROVIDE: daemonarchy_headless
# REQUIRE: NETWORKING
# BEFORE: LOGIN
# KEYWORD: nojail
# Present only on an explicitly prepared, private rescue image.
. /etc/rc.subr
name=daemonarchy_headless
rcvar=daemonarchy_headless_enable
start_cmd=daemonarchy_headless_start
stop_cmd=daemonarchy_headless_stop
state=/var/run/daemonarchy-headless
payload=/usr/local/share/daemonarchy-installer/headless

daemonarchy_headless_start()
{
    [ -s "$payload/authorized_keys" ] && [ -s "$payload/host_key" ] || return 1
    umask 077
    mkdir -p "$state" /var/empty
    cp "$payload/authorized_keys" "$state/authorized_keys"
    cp "$payload/host_key" "$state/host_key"
    chmod 600 "$state/authorized_keys" "$state/host_key"
    cat >"$state/sshd_config" <<CONFIG
Port 2222
HostKey $state/host_key
PidFile $state/sshd.pid
AuthorizedKeysFile $state/authorized_keys
AuthorizedKeysCommand none
PermitRootLogin prohibit-password
AllowUsers root
AuthenticationMethods publickey
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
StrictModes yes
UseDNS no
LoginGraceTime 30
MaxStartups 3:30:10
DisableForwarding yes
PermitUserEnvironment no
Subsystem sftp internal-sftp
CONFIG
    /usr/sbin/sshd -t -f "$state/sshd_config" || return 1
    dmesg -a >/var/log/daemonarchy-headless-boot.log
    /usr/sbin/sshd -E /var/log/daemonarchy-headless-sshd.log -f "$state/sshd_config"
}

daemonarchy_headless_stop()
{
    [ ! -f "$state/sshd.pid" ] || kill "$(cat "$state/sshd.pid")"
}
load_rc_config "$name"
: "${daemonarchy_headless_enable:=YES}"
run_rc_command "$1"
