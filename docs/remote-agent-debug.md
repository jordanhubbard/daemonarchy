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
   The network screen opens first: choose DHCP, Wi-Fi, or manual settings.
   Continue becomes available once an active interface has an IPv4 address.
   Remote debug only needs connectivity to the agent, not internet access.
   **Back to installer menu** cancels without starting remote access.
   The screen shows interface names and kernel hardware descriptions. If it
   reports no supported Wi-Fi adapter, FreeBSD has not exposed one to the
   installer; a supported USB network adapter may be needed. For diagnosis,
   use **Exit to shell** and inspect `ifconfig -a`, `sysctl net.wlan.devices`,
   and `pciconf -lv`.
3. Accept port **2222** or enter another port, then enable debug mode.
4. Give the agent the IP address and port displayed on screen.
5. The agent generates a temporary SSH key and tells you its fingerprint.
   When the pairing request appears, compare it and choose **Pair with agent**.

The approved agent has a root shell and can inspect hardware, retrieve logs,
transfer files, or operate the installer. Agree on the intended disk or
partition before asking it to install. For Windows-preservation testing,
identify the replaceable partition or free space explicitly.

Press **Enter** on the debug screen to stop access and return to the menu.
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
terminal (`ssh -t`) when running its forms. Remote debug is live-environment
access only: it does not automatically enable SSH or copy pairing keys into
the installed system.

## Implementation

The SSH server is FreeBSD's base-system OpenSSH. It listens only while debug
mode is active, accepts public-key authentication only, and consults the
console pairing helper before accepting a new key. There is no shared
password, anonymous root login, or permanently installed agent service.
Server keys, requests and approvals live in the ISO's memory-backed `/var`.
The helper refuses to run on an installed system rather than an ISO root.
Unattended `CIDATA` installation keeps its existing behavior and does not
enable debug mode.
