# Installer remote agent debug mode

Remote debug provides the handoff from a Windows or other existing machine
to an agent running on another computer. Boot the Daemonarchy live USB,
enable debug mode, and approve the agent's temporary SSH key. No installation
starts automatically and debug mode does not select or format a target disk.

This feature is in the 1.1 development installer; the published 1.0.1 image
and preview.2 do not contain the menu option.

## At the machine

1. Write the remote-debug preview ISO to a USB stick and boot it using the
   firmware's one-time boot menu. The preview currently requires Secure Boot
   to be disabled. Use Ethernet initially where possible.
2. Press Return at the welcome screen and choose **Remote agent debug**.
   This opens a root CLI immediately, even with no network connection. The
   network configuration screen also offers **Open debug shell**.
3. Inspect interfaces with `ifconfig -a`, `usbconfig`, `pciconf -lv`, and
   `sysctl net.wlan.devices`. Request DHCP with `dhclient ue0`, substituting
   the actual interface. Normal FreeBSD shell commands are available.
4. Once a usable IPv4 address exists, run `remote-debug listen` (port 2222)
   or `remote-debug listen 2207` for a different port. Answer `y` to enable
   remote access. Internet access is not required.
5. Give the agent the displayed IP address, port, and server fingerprint.
   Compare the agent's temporary key fingerprint when prompted, then type
   `y` to pair. Any other answer rejects the request.

Run `help` or `remote-debug help` for debugging instructions. Use `help cd`
(or another Bash builtin name) for shell command help. `exit` returns from the debug
shell to the installer screen that opened it. The shell itself does not
start a listener or require working networking.

The approved agent has a root shell and can inspect hardware, retrieve logs,
transfer files, or operate the installer. Agree on the intended disk or
partition before asking it to install. For Windows-preservation testing,
identify the replaceable partition or free space explicitly.

Press **Enter** on the debug screen to stop access and return to the debug shell.
This closes the listener and its SSH connections and discards pairing
approvals. Rebooting also discards them. Starting another debug session
requires pairing again. Stopping access does not undo work the agent performed.

## For the agent

Use a temporary key for the session and tell the user its SHA-256 fingerprint:

```sh
pair_dir=$(mktemp -d)
ssh-keygen -q -t ed25519 -N '' -f "$pair_dir/key"
ssh-keygen -l -f "$pair_dir/key.pub"
ssh -i "$pair_dir/key" -o IdentitiesOnly=yes \
    -o UserKnownHostsFile="$pair_dir/known_hosts" \
    -p 2222 root@MACHINE_IP
```

Replace the IP and port with the displayed values. Check the server host-key
fingerprint against the debug screen when SSH first asks to trust it. The
connection waits up to two minutes for console approval; reconnect if the
user needs more time. Reuse the same temporary key for subsequent commands
or `scp` transfers during this session. A rejected key stays rejected until
debug mode is stopped and restarted.

Start with read-only inventory such as `pciconf -lv`, `camcontrol devlist`,
`gpart show -lp`, and `ifconfig`. The installer entry point is
`/usr/local/libexec/daemonarchy-installer/launch`; use an interactive SSH
terminal (`ssh -t`) when running its forms. Debug pairing does not automatically
enable normal SSH or copy approved keys into the installed system.

## On an installed system

New installations also include `daemonarchy-debug`. At the root console, run
`daemonarchy-debug listen` to enable the same temporary-key pairing on port
2222, or `daemonarchy-debug listen 2207` to choose another port. It requires
FreeBSD, an unlocked root account and a usable network address. Confirm the
listener and the agent fingerprint at the console as above. This listener
uses its own SSH configuration; it does not enable the normal SSH service or
change password authentication in `/etc/ssh/sshd_config`.

The root shell is available through `daemonarchy-debug shell`. Press Enter
or Ctrl-C in the listener's console to close debug connections and discard
the temporary keys and approvals. No debug listener starts automatically at
boot. Older installed images need these tools copied in separately.

## Implementation

The SSH server is FreeBSD's base-system OpenSSH. It listens only while debug
mode is active, accepts public-key authentication only, and consults the
console pairing helper before accepting a new key. There is no shared
password, anonymous root login, or permanently installed agent service.
Server keys, requests and approvals live under `/var/run/daemonarchy-remote-debug`
and are removed when the listener stops. On the live ISO, `/var` is memory-backed.
Unattended `CIDATA` installation keeps its existing behavior and does not
enable debug mode.
