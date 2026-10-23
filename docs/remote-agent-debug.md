# Installer remote agent debug mode

Remote debug provides the handoff from a Windows or other existing machine
to an agent running on another computer. Boot the Daemonarchy live USB,
enable debug mode, and approve the agent's temporary SSH key. No installation
starts automatically and debug mode does not select or format a target disk.

The 1.1 installer introduced pairing. The 1.1.1 refresh adds Pair/Unpair recovery
and continuous diagnostics. Older images need the matching helpers copied in
before these newer commands are available; installing a newer kernel is not
required for these debugging tools.

## At the machine

1. Write the selected release ISO to a USB stick and boot it using the
   firmware's one-time boot menu. Follow that release's
   [Secure Boot instructions](secure-boot.md); do not assume an old preview's
   firmware requirements apply to a newer signed image. Use Ethernet initially
   where possible.
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
approvals. From another local console, `daemonarchy-debug unpair` performs the
same revocation, including terminating the listener's SSH connections.
Development images now retain an installed-system debugging grant across reboot.
The recovery console restarts the listener when networking is available, keeping
the same server fingerprint and approved client keys. The agent reconnects with
its existing key; no new approval is required. An SSH disconnect or reboot does
not end a hardware bring-up session. The boot console continues checking an
active grant after the listener starts, and retries if that listener later exits.
Explicit stop or Unpair removes the active grant and ends this retry. New keys
still require console approval.
On a fully booted desktop the rescue menu is not visible, so it cannot show
whether a debugging grant, listener or active agent connection remains. A
desktop menu-bar status and revocation control are tracked in DEBUG-002; until
that is implemented, `remote-debug status` checks whether the listener is
running and `remote-debug unpair` revokes the grant from a local root shell.

If networking is not ready at startup, rescue option 2 offers **Resume remote
debugging agent**. This reuses the retained grant without first deleting it.
A running session offers **Unpair remote debugging agent** instead. Explicit
Unpair, Enter or Ctrl-C in the interactive listener revokes access and clears
approval. The process identity is checked before any PID is signaled, so a
reused PID cannot terminate an unrelated process. Existing diagnostic logs are
retained. Older 1.1.1 helpers require Unpair/Pair after a stale session; update
both `remote-debug` and `daemonarchy-rescue` to obtain resumption.

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

The console reports successful authentication. Keep the operator informed with
`daemonarchy-debug activity 'Checking Wi-Fi connectivity'` from SSH, then run
`daemonarchy-debug done` when the whole task is finished. Activity descriptions
appear on the local console: keep them brief and omit credentials and private
command output. Closing an individual SSH connection does not mark completion.
The completion message says it is OK to stop, but leaves access enabled until
the operator presses Enter or Ctrl-C. These feedback commands require an image
newer than preview.13; on older images report the same states directly.

## Continuous diagnostics

In 1.1.1, the first approved SSH connection starts a read-only diagnostics
collector for that pairing. It captures an initial kernel-message snapshot,
then kernel-message differences and recent `/var/log/messages` output at roughly
two-second intervals. Every fifth cycle also records process IDs, parent IDs,
owners, elapsed times, states and wait channels; memory counters, ZFS cache and
pool state, storage activity, loaded modules, named CPU temperature sensors,
AC/battery state, and the agent's current activity. Where Python 3 and the devd broadcast socket
are available, a separate passive reader also records device/ACPI events; it
does not replace devd or take events away from other clients. Otherwise the
missing event capability is recorded explicitly. Process command arguments,
environment variables, key material and password databases are not collected.
Unavailable sensors and failed probes are recorded with their exit status.
Individual external probes have a three-second timeout; a slow probe can delay
the next sample. This is periodic observation, not an instruction-level trace.

The collector starts only after approved authentication, not at boot or when
the console merely opens a shell. Its private target logs are
`/var/log/daemonarchy-debug/observer.log` and `observer.previous.log`, each at
most 4 MiB. Passive device events use `events.log` and
`events.previous.log`, also at most 4 MiB each. An individual sample is capped at 1 MiB with an explicit truncation
record. Logs survive an ordinary installed-system reboot; the live ISO's
memory-backed logs do not. Unpairing ends collection after its current bounded
cycle; a previous collector cannot attach to a newly paired session. Reconnecting
restarts a failed collector. Startup errors remain in
`/var/db/daemonarchy/remote-debug/observer-startup.log` until unpairing.

Before any operation that could reset the target, retain a stream **on the
controlling computer**. From an approved shell, these commands are available:

```sh
daemonarchy-debug snapshot    # one read-only state snapshot
daemonarchy-debug observe     # initial state and continuously followed logs
```

For a retained capture, create an executable SSH wrapper on the controller
using the approved temporary key, strict host-key checking and the verified
`known_hosts` file. The wrapper must forward its arguments to SSH, for example:

```sh
#!/bin/sh
exec ssh -i /PRIVATE/PAIR/key -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/PRIVATE/PAIR/known_hosts \
  -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 \
  -p 2222 root@MACHINE_IP "$@"
```

Run the repository's receiver on a Linux or macOS controller (Python 3 standard
library; native Windows process-group handling is not implemented):

```sh
python3 scripts/capture-remote-debug.py \
  --ssh-wrapper /PRIVATE/PAIR/ssh-wrapper \
  --output /PRIVATE/PAIR/evidence --duration 1800
```

It writes private capture parts and timestamped connection/idle/exit events,
flushes received bytes to controller storage about once per second, and records
the SSH exit status. Each invocation stops after the requested duration or
128 MiB; it does not delete previous captures. It also stops on connection loss
and does not trust replacement host keys automatically. Verify a new pairing's
displayed fingerprint before restarting capture. Keep this connection running
alongside the shell doing the work. Target log rotation remains bounded even
if no controller is connected. Inspect the capture and last durable repair
checkpoint after a reset before starting another package transaction.

Kernel output in the message buffer is available independently of verbose boot.
The current `vt` console has no supported text-buffer dump through `vidcontrol`;
the snapshot explicitly records this limit. On supported `syscons` consoles,
the collector can capture the visible text buffer. It never reads console input.
The stream cannot capture firmware output, a hard reset, or panic messages emitted
after the kernel/network stops responding. Empty crash-dump records do not prove
that no kernel fault occurred. Serial/BMC capture or kernel network-debug support
is needed for that boundary; source/loader work is planned for 1.2.

Validate reboot resumption with `tests/remote-debug-reboot.sh` as root on FreeBSD.
Validate observation with `tests/remote-debug-observe.sh` as root on FreeBSD and
`python3 tests/remote-debug-capture.py` on the controller. The existing pairing
and unpairing lifecycle checks remain separate from these diagnostics checks.

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
the retained keys and approvals. A previously approved installed-system grant
resumes at boot; without that prior opt-in no listener starts. Older installed
images need these tools copied in separately.

## Implementation

The SSH server is FreeBSD's base-system OpenSSH. It listens only while an
operator-approved debugging grant is active, accepts public-key authentication only, and consults the
console pairing helper before accepting a new key. There is no shared
password, anonymous root login, or permanently installed agent service.
Server keys, requests, the selected port and approvals live in the root-only
`/var/db/daemonarchy/remote-debug` directory. Runtime listener and collector
identities are refreshed after reboot without discarding the grant. A background
resumed listener accepts only previously approved keys. Explicit revocation
removes the grant and terminates its owned SSH connections. On the live ISO,
`/var` is memory-backed, so live-USB approval does not survive reboot or transfer
automatically to an installed target.
Unattended `CIDATA` installation keeps its existing behavior and does not
enable debug mode.

## Keyboard-free rescue image

For a machine that cannot provide a usable console, prepare a separate private
rescue image with one preauthorized operator key. This mode is absent from the
public image and does not use interactive pairing.

```sh
scripts/prepare-headless-rescue.sh operator.pub /path/to/new-rescue-overlay
# On the FreeBSD image builder, using that overlay:
LIVE_EXTRA_OVERLAY=/path/to/new-rescue-overlay \
  NAME=daemonarchy-headless-rescue-amd64 \
  PREVIEW_LABEL='private headless rescue' sh build-iso.sh
```

The helper accepts one plain Ed25519 public key and generates a separate server
host key. It never copies the operator's private key. Keep the overlay and image
private; they contain the rescue server's private host key. Record its printed
fingerprint before writing the image to USB.

The rescue boot uses DHCP on Ethernet, starts a dedicated root SSH listener on
port 2222, and accepts only the selected key. Password login and forwarding are
disabled. T2 `apple_bce` and desktop GPU module autoloading are blocked so those
drivers can be investigated after establishing access. No installer path runs,
even if an old autoinstall CIDATA drive remains attached. The installed system is
not automatically mounted or changed. Console input is not needed.

Connect with the operator key and verify the server against the host key from
the overlay. Boot logs are `/var/log/daemonarchy-headless-boot.log` and
`/var/log/daemonarchy-headless-sshd.log`. The listener and authorizations disappear
when this rescue system shuts down; they are not installed on the target disk.

Native boot/authentication testing is a separate gate from the helper's key and
file-validation tests. A rescue boot with drivers blocked does not qualify those
drivers or the graphical desktop.
New live images retain ordinary panic output with
`kern.panic_reboot_wait_time=-1` and `debug.trace_on_panic=1`. Firmware resets
and faults before panic handling can still reboot immediately. Older images
need these settings entered at the loader prompt when collecting a trace.
The [QEMU rescue check record](testing-1.1-headless-rescue.md) covers key
authentication, ignored unattended media and a target disk with zero writes.
Audit private images with `tests/live-image-runtime.sh image.iso headless`;
the default public-image audit rejects their preauthorized rescue payload.

## Keeping recovery ahead of graphics

New installations load their selected desktop GPU modules in
`daemonarchy-graphics`, ordered after normal SSH startup and before SDDM. GPU
modules are excluded from automatic devmatch loading and the early `kld_list`.
If SSH was selected but did not start, graphical startup is withheld. Module
errors go to `/var/log/daemonarchy-graphics.log`; SDDM requires the service's
ready marker. A requested DRM driver must have an attached active device in
non-verbose `devinfo` and DRM card/render character nodes before that marker is
written. Module-load success and device nodes alone can survive a failed GPU
attach. These checks establish startup prerequisites; they do not prove that
Xorg, a greeter or a compositor can render. NVIDIA's attached-device check covers
its parent driver and does not independently test DRM ioctls.

FreeBSD Safe Mode (`boot_safe=YES`) and the loader setting
`set daemonarchy_rescue=YES` skip this graphics service and SDDM. Normal network
and configured SSH startup can still run. This does not enable SSH where the
operator declined it, and does not prevent unrelated kernel or device-driver
panics. The private headless USB mode additionally blocks T2 BCE autoloading.

At boot, resumption retries for up to 60 seconds in the background while USB
Ethernet/DHCP becomes ready. The recovery menu remains usable throughout. If
networking becomes available later, choose Resume to retry the retained grant.
