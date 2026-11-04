# Installer reference

What the Daemonarchy installer does, how to drive it without a keyboard, and the optional extras it offers. These sections used to sit in the middle of the README; the README now tells the story for a newcomer and this page keeps the detail. For the step-by-step first install, read the [getting-started guide](getting-started.md) first.

## The installer

Since 1.1, the installer retains installation output on the target disk and
provides a [console rescue menu](rescue-console.md) when installation is
interrupted or graphical login fails. It offers logs, a local shell, and the
same console-approved remote debugging used by the installer. Recovery actions
require the password selected during installation. Since 1.1.1, option 2 toggles pairing and unpairing, including removal of stale pairing state after a reset; see the [rescue guide](rescue-console.md).

The installer includes **Remote agent debug** in its welcome
menu. Since 1.3.1, an approval and the agent's identity survive reboot until revoked. It displays an IP address and configurable SSH port (default 2222), then
asks you to approve the agent's temporary key fingerprint. This lets an agent
inspect or operate a machine booted from USB before installation. See the
[remote debug guide](remote-agent-debug.md) for the handoff and pairing
steps.

For machines that hang or reset during kernel startup, developers and
agentic researchers use a separate **hardware bring-up trace image**
(`daemonarchy-hwtrace-<version>-amd64.img`, not the install ISO). It records
each startup step in UEFI NVRAM, files every boot's trace on the stick and
boots the next queued experiment unattended; see
[the hardware trace guide](boottrace.md).

`overlay/usr/local/libexec/daemonarchy-installer/configurator` keeps the Omarchy ISO configurator's screens and look, and sources Omarchy's own setup form (`install/provisioning/setup-form.sh`, taken from the `omarchy` package at build time) so the questions and validation are identical. Two steps are FreeBSD's own: a network step, since packages are downloaded during the install (wired networks are configured by DHCP at boot; otherwise it scans for Wi-Fi, joins the chosen network, and carries the setting over to the installed system), and the disk step: pick a disk, optionally encrypt it.

`overlay/usr/local/libexec/daemonarchy-installer/install` lays the disk out as an EFI system partition, swap, and a ZFS pool (GELI-encrypted with the user's password when asked) using bsdinstall's dataset layout, so ZFS boot environments take the place of Omarchy's Snapper snapshots. It extracts the base system, installs the FreeBSD loader with a Daemonarchy brand, and writes the system configuration that the `x11-wm/omarchy` port's install message asks for: D-Bus, seatd and SDDM enabled, the DRM driver for the detected Intel or AMD GPU, fdescfs and linprocfs mounts, the user in `wheel`, `video`, `audio`, and `operator`, and `/etc/vconsole.conf` for Omarchy's Hyprland keyboard layout. Then `pkg` installs `daemonarchy`, the meta-port for the whole desktop. As on Arch, an encrypted install logs straight into the desktop; otherwise SDDM asks for the password.

### Unattended installs

Like the Arch ISO, the installer runs without a keyboard when it finds its answers on a second drive labeled `CIDATA` (an MS-DOS, ISO 9660, or UFS volume). Put an `daemonarchy-install.conf` on it:

```sh
disk=nda0
encrypt_installation=false
keyboard=us
username=tester
password=changeme
full_name="Daemonarchy User"
email_address=user@example.com
hostname=daemonarchy
timezone=America/Los_Angeles
```

The machine powers off when the install finishes.

*Since 1.4.0*: before touching the disk, an unattended install runs the same network check as the interactive installer, without asking anything. The check probes every cabled port for DHCP and checks DNS with direct lookups and the clock with network time. It uses Wi-Fi only if no cable works. It honors these optional answers:

```sh
net_mode=static            # or dhcp (the default) or wifi
net_if=em0                 # the port to use; for wifi, the radio, for example iwlwifi0
net_addr=192.168.1.50/24   # static only
net_gw=192.168.1.1         # static only
net_dns=192.168.1.53       # tried first; it is used only if it answers
wifi_ssid="Home"           # joined when no cable works, or with net_mode=wifi
wifi_psk="password"
wifi_hidden=false
```

If no connection, DNS server or clock works, the install stops before any disk change. It says why and points to `/tmp/daemonarchy-network/log`. Enterprise Wi-Fi is joined from the interactive installer only.

### Optional live checkouts

The installer offers `/usr/ports` and `/usr/src` separately, both off
by default. These are shallow Git checkouts (depth 1), pinned to the release
ports tree and kernel sources. They support fetching updates and making commits;
fetch more history explicitly with `git fetch --deepen=100` when needed.
Set `install_ports=true` and/or `install_src=true` for unattended installation.

On an installed system, they can also be added later:

```sh
sudo daemonarchy-checkouts ports "$USER"
sudo daemonarchy-checkouts src "$USER"
```

Existing nonempty directories are preserved. The installer displays each
option's download size and additional space allowance. See
[the packaging instructions](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#building-live-checkout-packages) for
release pinning and validation details.

### CUDA and cudalab (NVIDIA)

On a machine with a supported NVIDIA display GPU the installer offers CUDA 13.2
and the cudalab demos, selected by default. They are downloaded over the
network during installation, not carried on the media, and need about 16 GiB of
extra space. A failed download does not fail the install; run
`sudo daemonarchy-linux-cuda setup && sudo daemonarchy-linux-cuda prepare-cudalab "$USER"`
after the first boot to try again. An unattended install takes the default; set
`install_cuda=false` to skip it. Unified Memory (`cudaMallocManaged`) is not
supported. Without an NVIDIA GPU the option is not shown and
`install_cuda=true` is refused.

cudalab has no FreeBSD package: it is a Linux program built with CUDA. The
Cudalab entry in Apps is a launcher, `daemonarchy-cudalab`, that works as a
virtual app. It builds a pinned cudalab under the Linuxulator for the user the
first time it is needed (the installer's CUDA step does that, so a machine that
took the offer has it ready), and every launch after that opens the built app
directly. In 1.4.0 the launcher rebuilt cudalab on every launch and then exited
at once on machines with no sound device, so it appeared to open nothing; the
virtual app of 1.4.1 replaces it.

The wrapper stays in `/usr/local/bin`; the built program is a side binary under
`~/.local/share/cudalab`. A first build uses a pinned cudalab revision known to
build and run here. `daemonarchy-cudalab --update` moves past it: if the checkout
has no local changes it fetches, fast-forwards to the tip of upstream's default
branch, rebuilds, and keeps that build (later launches and `--rebuild` stay on it;
a failed update leaves the previous build working). Local changes in the checkout
are never touched. Deleting the side binary or running `daemonarchy-cudalab
--rebuild` rebuilds it, and `daemonarchy-cudalab --status` says which commit is
built and whether it is pinned, updated or has local changes.

The app's output is kept in `~/.local/state/cudalab/app.log`, and a notification
says so if it stops with an error. Started from a terminal it detaches, so that
window closes (`CUDALAB_FOREGROUND=1` keeps it attached). Under the
Linuxulator, with the UVM shim and no real `nvidia-uvm`, CUDA reports no memory pools
(measured on an RTX 5080, driver 595.104.02), so `cudaMallocAsync` fails with "operation not supported";
the launcher builds a small library that falls back to `cudaMalloc` and preloads
it, which is what lets the Choreograph demo start. Sound goes through PulseAudio
(the desktop's PipeWire answers on its socket, which the launcher hands to
libpulse by path) when the Linux SDL was built with it, which needs the client headers that `daemonarchy-linux-cuda setup` installs;
otherwise, or if that driver fails at start, Cudalab runs with SDL's silent driver.
