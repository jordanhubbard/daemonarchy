# Daemonarchy

![The Daemonarchy desktop: fastfetch, btop, boot environments and home snapshots, with the System > FreeBSD menu open](docs/images/desktop.png)

Daemonarchy is the [Omarchy](https://omarchy.org) desktop on FreeBSD: DHH's opinionated Hyprland desktop, ported to FreeBSD and installed the way the Omarchy ISO installs it on Arch. The name is a homage: Omarchy's *-archy*, ruled by the BSD daemon.

This repository builds a bootable FreeBSD 16.0-CURRENT image with the Daemonarchy installer: the same welcome screen, keyboard, account, hostname, and timezone questions as the Omarchy ISO, then an installation onto a whole disk, a selected GPT partition, or existing free space that boots into the desktop (partition selection is new in 1.1). Daemonarchy is not affiliated with Omarchy; the Omarchy software itself comes, unchanged apart from FreeBSD compatibility, from the `x11-wm/omarchy` port.

Each release is built from a FreeBSD 16.0-CURRENT snapshot. CURRENT moves daily, so an image is tied to the snapshot it was built from.

Product goals and adoption status are in [PROJECT.md](PROJECT.md). The
[active work queue](docs/roadmap/active-work.md) tracks stable tasks and evidence;
[the architecture](docs/architecture/design-traceability.md) maps Component contracts
to the retained implementation.

[CHANGELOG.md](CHANGELOG.md) records the changes, publication state and migration
limits for every release, including the initial installer snapshots.

## Download

The latest stable release is **[Daemonarchy 1.3.1](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.3.1)** (x86-64, BIOS or UEFI), published October 25, 2026, on FreeBSD 16.0-CURRENT, OSVERSION `1600029`. Version 1.2.0 was not published; 1.3.1 follows 1.1.1.

- [ISO](https://github.com/jordanhubbard/daemonarchy/releases/download/daemonarchy-1.3.1/daemonarchy-1.3.1-amd64.iso): 2,041,176,064 bytes, under 2 GiB.
- [Checksum](https://github.com/jordanhubbard/daemonarchy/releases/download/daemonarchy-1.3.1/daemonarchy-1.3.1-amd64.iso.sha256): `ef5b1bec2189350e1ae194d251c35b959a39d7e4993b6a0f4deb7dcb30365735`.
- The release also carries the signed Secure Boot bundle (`daemonarchy-1.3.1-boot.txz` and its `.sig`) and the public certificate in PEM and DER form. The package-signing key was rotated for 1.3.1; see the [key rotation record](docs/package-repository-key-rotation-1.3.1.md).
- Read the [1.3.1 release notes](docs/release-1.3.1.md) and their hardware status and limits before installing. The MacBookPro16,1 passed pre-production checks by operator confirmation; an additional physical run of the final ISO was waived. The MSI Raider 18 HX still resets during early kernel startup.

Write it to a USB stick with `dd if=daemonarchy-1.3.1-amd64.iso of=/dev/<usb-device> bs=1m` (`bs=1M` on Linux). Boot with Secure Boot off, or follow the manual enrollment guide to enable verified boot. The installer needs a network connection. Whole-disk installation erases the selected disk; partition mode replaces only the explicitly selected partition.

New to Daemonarchy? [Getting started](docs/getting-started.md) walks through writing the stick, installing, and your first hour on the desktop: Wi-Fi, sound, Bluetooth, updates, and what FreeBSD adds. To build an image yourself or work on Daemonarchy, see [HACKING.md](HACKING.md).

Check the [hardware quirks](docs/hardware-quirks.md) for known boot blockers and
diagnostic notes, including the MSI Raider 18 HX AI A2XWIG early installer reset.

## 1.3.1 release

The current stable release is **1.3.1**. Its base is the Daemonarchy FreeBSD
source fork at `d63d77f4` (FreeBSD CURRENT through `a3d1d4e8`, OSVERSION
`1600029`), with ports at `b7857842`. The [release notes](docs/release-1.3.1.md)
cover everything since 1.1.1, including MacBookPro16,1 support (Navi14
graphics, T2 keyboard and trackpad, and BCM4364 Wi-Fi with firmware acquired
from Apple recovery media), remote-debugging approval that survives reboot, and
the rotated package-signing key. [CHANGELOG.md](CHANGELOG.md) keeps the detailed
history, and the previous release's [1.1.1 qualification record](docs/testing-1.1.1.md)
remains available.

Moving an older installation to the 1.3.1 application feed requires a
coordinated base, kernel and driver upgrade; changing the package URL alone is
insufficient. Physical GPU, firmware, radio and retained-OS qualification
remains explicitly recorded rather than inferred from VM tests.

## What FreeBSD adds

Daemonarchy is the Omarchy desktop with FreeBSD underneath, and it puts FreeBSD's strengths in the Omarchy menu under **System > FreeBSD**:

- **Boot environments.** The system lives on ZFS, and every Omarchy update first saves a boot environment: a bootable copy of the whole system. Roll back to any of them from the menu or the boot loader.
- **Restore files.** Hourly and daily ZFS snapshots of home directories, kept for a day and a week; open one in the file manager and copy back what you lost.
- **Jails.** Lightweight FreeBSD containers, each with its own FreeBSD system and packages.
- **Virtual machines.** Run Linux, Windows, or the BSDs with bhyve, FreeBSD's hypervisor.
- **Trace the system.** Live views of what the system is doing, through DTrace.
- **Hack on Daemonarchy.** Fetch the sources and run the desktop from your own checkout of Omarchy; see [HACKING.md](HACKING.md).

![Hourly snapshots of a home directory in Files, a live DTrace view of system calls, the ZFS pool, and the sound panel](docs/images/freebsd.png)

Omarchy's panels work on FreeBSD too. Wi-Fi runs through FreeBSD's `wpa_supplicant`, sound through PipeWire, and Bluetooth keyboards and mice through FreeBSD's own Bluetooth stack:

![The network panel: Ethernet status, DNS, and nearby Wi-Fi networks (names blurred)](docs/images/network.png)

Install software from FreeBSD's package collection through OctoPkg (**Install > Packages**) or `pkg`. Chromium is installed by default. Linux-only applications and automatic agent downloads are withheld until their exact versions pass native Linuxulator qualification; see the [application policy](docs/freebsd-application-policy.md).

## What the image contains

- A live FreeBSD system (from the snapshot) that logs root in on the first console and starts the installer.
- The installer: `configurator` asks the questions, `install` installs, `dashboard` shows its progress, `launch` ties them together.
- The snapshot's `base.txz`, `kernel.txz` and `lib32.txz`, which become the installed system. The 32-bit compatibility libraries also satisfy native package dependencies such as LLVM/Mesa.
- A package repository with what pkg.FreeBSD.org does not publish: the Omarchy ports from the release's ports fork ([daemonarchy-ports](https://github.com/jordanhubbard/daemonarchy-ports) `b7857842` for 1.3.1), and the GPU and Wi-Fi kernel modules (`drm-612-kmod`, `gpu-firmware-*-kmod`, `wifi-firmware-*-kmod`) built for the snapshot kernel.

Other desktop dependencies are downloaded during installation. Compatible official packages come from pkg.FreeBSD.org; the release's versioned feed also supplies ordinary dependencies rebuilt for its newer ports/base selection. Network access is required. Keeping those downloads off the ISO keeps each release asset below GitHub's 2 GiB limit; a complete offline desktop payload would exceed that budget.

## Updates

Application packages update with `pkg upgrade` (which Omarchy's update runs). This does not update the FreeBSD base/kernel or make kernel modules compatible with another snapshot. FreeBSD's packages come from pkg.FreeBSD.org. Daemonarchy's own packages (the Omarchy ports and the patched Quickshell) come from a signed repository published as the assets of the [`packages-16-amd64`](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64) release. The installer adds its key as `/usr/local/etc/pkg/keys/daemonarchy.pub`, so fixes reach you without a new ISO. The image's own packages stay on the disk as a fallback repository, `Daemonarchy-ISO`, since the GPU and Wi-Fi modules built for its kernel are only there.

A system installed from an image dated 2026-10-02 or earlier has only the on-disk repository. To move it to the online one, run as root:

```
mkdir -p /usr/local/etc/pkg/keys
fetch -o /usr/local/etc/pkg/keys/daemonarchy.pub https://raw.githubusercontent.com/jordanhubbard/daemonarchy/main/overlay/usr/local/share/daemonarchy-installer/daemonarchy.pub
cat >/usr/local/etc/pkg/repos/Daemonarchy.conf <<'EOF'
Daemonarchy: {
  url: "https://github.com/jordanhubbard/daemonarchy/releases/download/packages-16-amd64",
  signature_type: "pubkey",
  pubkey: "/usr/local/etc/pkg/keys/daemonarchy.pub",
  priority: 10,
  enabled: yes
}
Daemonarchy-ISO: {
  url: "file:///var/db/daemonarchy/repo",
  signature_type: "none",
  priority: 5,
  enabled: yes
}
EOF
pkg upgrade
```

## Roadmap

**1.3.1 is available with documented qualification gaps; 1.4.0 is in development.** See the [roadmap](ROADMAP.md) for remaining
graphics, Bluetooth, enterprise Wi-Fi, installation and boot support, upstream
ports work, and the checks required before release. The
[partition preview guide](docs/testing-1.1-partitions.md) covers installing into
an existing OS/data partition or creating a new one in free space.

## The installer

The 1.1 installer retains installation output on the target disk and
provide a [console rescue menu](docs/rescue-console.md) when installation is
interrupted or graphical login fails. It offers logs, a local shell, and the
same console-approved remote debugging used by the installer. Recovery actions
require the password selected during installation. In the 1.1.1 refresh, option 2 toggles pairing and unpairing, including removal of stale pairing state after a reset; see the [rescue guide](docs/rescue-console.md).

The 1.1 development installer includes **Remote agent debug** in its welcome
menu. It displays an IP address and configurable SSH port (default 2222), then
asks you to approve the agent's temporary key fingerprint. This lets an agent
inspect or operate a machine booted from USB before installation. See the
[remote debug guide](docs/remote-agent-debug.md) for the handoff and pairing
steps.

For machines that hang or reset during kernel startup, developers and
agentic researchers use a separate **hardware bring-up trace image**
(`daemonarchy-hwtrace-<version>-amd64.img`, not the install ISO). It records
each startup step in UEFI NVRAM, files every boot's trace on the stick and
boots the next queued experiment unattended; see
[the hardware trace guide](docs/boottrace.md).

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

Before touching the disk, an unattended install runs the same network check as the interactive installer, without asking anything. The check probes every cabled port for DHCP and checks DNS with direct lookups and the clock with network time. It uses Wi-Fi only if no cable works. It honors these optional answers:

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

The development installer offers `/usr/ports` and `/usr/src` separately, both off
by default. These are shallow Git checkouts (depth 1), pinned to the release
ports tree and kernel sources. They support fetching updates and making commits;
fetch more history explicitly with `git fetch --deepen=100` when needed.
Set `install_ports=true` and/or `install_src=true` for unattended installation.

On a system installed with this development image, they can also be added later:

```sh
sudo daemonarchy-checkouts ports "$USER"
sudo daemonarchy-checkouts src "$USER"
```

Existing nonempty directories are preserved. The installer displays each
option's download size and additional space allowance. See
[the packaging instructions](HACKING.md#building-live-checkout-packages) for
release pinning and validation details.

## Source

Daemonarchy is built from these repositories:

- **[jordanhubbard/daemonarchy](https://github.com/jordanhubbard/daemonarchy)** (this one): the installer image, its build and test scripts, and these docs.
- **[jordanhubbard/daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop)**: Daemonarchy's artwork and login theme, and the System > FreeBSD tools. Its tags are Daemonarchy's version numbers.
- **[jordanhubbard/omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd)**: the FreeBSD compatibility layer that lets Omarchy run unchanged.
- **[jordanhubbard/daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src)**: the owned FreeBSD source fork the image's base system and kernel are built from. 1.3.1 uses `d63d77f4`; review work lands on its `daemonarchy` integration branch.
- **[jordanhubbard/daemonarchy-ports](https://github.com/jordanhubbard/daemonarchy-ports)**: the ports fork that packages all of it. 1.3.1 uses `b7857842`; review work lands on its `daemonarchy` integration branch. Releases through 1.1.1 used [jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports/tree/daemonarchy-1.1.1) (`daemonarchy-1.1.1`, and `daemonarchy-1.1-package-baseline` for the 1.1 candidate). Upstream submissions continue independently of Daemonarchy releases.

## Building

On a FreeBSD 16.0-CURRENT host with poudriere: build the ports, build the image with `./build-iso.sh`, test it with `./test-bhyve.sh` (or `./test-qemu.sh` on a host without bhyve), and publish it. [HACKING.md](HACKING.md) walks through each step, the faster loops for changing the installer, the ports, and the artwork, and the pitfalls met so far.

## Release Engineers

- `jordanhubbard`

## Historical limits of 1.0.1

- Whole-disk installs only; no dual boot.
- UEFI machines only, with Secure Boot turned off: the FreeBSD loader is not signed, and the installed disk has no BIOS boot code.
- The install needs a network connection (wired, or Wi-Fi with WPA-PSK or no password; no enterprise Wi-Fi). The desktop has FreeBSD Wi-Fi and Bluetooth panels; Bluetooth supports input devices only.
- NVIDIA GPUs get no driver.
- Virtual machines install and boot, but Hyprland needs a DRM driver, which FreeBSD VMs lack.

## Names and marks

Daemonarchy is a union of two projects and claims to be neither. Omarchy is the desktop and FreeBSD is the operating system underneath; both are credited by name wherever the system describes what it is (the About screen reads "Omarchy <version> on FreeBSD <release>"). Daemonarchy's own identity — the wordmark, the horned "A", the wallpaper, and the login theme's logo — is original artwork that lives in the `x11-wm/daemonarchy` port, apart from Omarchy's files, which are installed as Omarchy ships them. No FreeBSD or Arch Linux logo is used.

Daemonarchy is not affiliated with or endorsed by Omarchy, the FreeBSD Project, or The FreeBSD Foundation. FreeBSD is a registered trademark of The FreeBSD Foundation. Omarchy is used under the MIT license.
