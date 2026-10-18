# Daemonarchy

![The Daemonarchy desktop: fastfetch, btop, boot environments and home snapshots, with the System > FreeBSD menu open](docs/images/desktop.png)

Daemonarchy is the [Omarchy](https://omarchy.org) desktop on FreeBSD: DHH's opinionated Hyprland desktop, ported to FreeBSD and installed the way the Omarchy ISO installs it on Arch. The name is a homage: Omarchy's *-archy*, ruled by the BSD daemon.

This repository builds a bootable FreeBSD 16.0-CURRENT image with the Daemonarchy installer: the same welcome screen, keyboard, account, hostname, and timezone questions as the Omarchy ISO, then an installation onto a whole disk, a selected GPT partition, or existing free space that boots into the desktop (partition selection is new in 1.1). Daemonarchy is not affiliated with Omarchy; the Omarchy software itself comes, unchanged apart from FreeBSD compatibility, from the `x11-wm/omarchy` port.

Each release is built from a FreeBSD 16.0-CURRENT snapshot. CURRENT moves daily, so an image is tied to the snapshot it was built from.

## Download

The latest stable release is **[Daemonarchy 1.0.1](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.0.1)**. The current public candidate is **[Daemonarchy 1.1.0-rc.1](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.1.0-rc.1)** (x86-64, BIOS or UEFI), with Omarchy 4.0.4 on the October 12 FreeBSD 16.0-CURRENT snapshot. A refreshed [1.1.1 is being prepared](docs/testing-1.1.1.md).

- [ISO](https://github.com/jordanhubbard/daemonarchy/releases/download/daemonarchy-1.1.0-rc.1/daemonarchy-1.1.0-amd64.iso): 2,098,395,136 bytes, under 2 GiB.
- [Checksum](https://github.com/jordanhubbard/daemonarchy/releases/download/daemonarchy-1.1.0-rc.1/daemonarchy-1.1.0-amd64.iso.sha256): `891fc6e6ee537bf92aecf035d4e855b8d526aeaf9c27be80166d689289c3acd9`.
- Adds partition selection, BIOS boot, QEMU/VirGL Hyprland, native FreeBSD app menus, Chromium, OctoPkg, remote-debug progress, and [manual-enrollment Secure Boot](docs/secure-boot.md).
- Read the [results and limits](docs/testing-1.1-final-image.md) before installing. Physical graphics/firmware, Bluetooth audio, enterprise Wi-Fi and refreshed bhyve remain unqualified. The ASRock, MSI Raider and T2 MacBook failures are documented.

Write it to a USB stick with `dd if=daemonarchy-1.1.0-amd64.iso of=/dev/<usb-device> bs=1m` (`bs=1M` on Linux). Boot with Secure Boot off, or follow the manual enrollment guide to enable verified boot. The installer needs a network connection. Whole-disk installation erases the selected disk; partition mode replaces only the explicitly selected partition.

New to Daemonarchy? [Getting started](docs/getting-started.md) walks through writing the stick, installing, and your first hour on the desktop: Wi-Fi, sound, Bluetooth, updates, and what FreeBSD adds. To build an image yourself or work on Daemonarchy, see [HACKING.md](HACKING.md).

Check the [hardware quirks](docs/hardware-quirks.md) for known boot blockers and
diagnostic notes, including the MSI Raider 18 HX AI A2XWIG early installer reset.

## 1.1.1 preparation

The requested next stable release is **1.1.1**. Its new base is FreeBSD CURRENT
`bdcfeac3e1cb` (OSVERSION `1600028`), paired with ports `f7d7ee897405` on
`daemonarchy-1.1.1`. The [qualification record](docs/testing-1.1.1.md) tracks
what has passed and what remains before publication; the download links above
continue to identify the available artifacts.

The refresh adds an explicit **Pair / Unpair remote debugging agent** toggle,
rescue-menu redraw after boot probes, and an installation integrity check that
refuses to report success with missing or damaged package files. Bounded
[continuous diagnostics](docs/remote-agent-debug.md#continuous-diagnostics)
retain evidence on the controller while SSH works. These tools do not observe
an early boot failure or recover networking after a hard reset. Loader and
early-kernel network debugging are deferred to **1.2**; 1.1.1 adds no new
source patches for that work.

The new application feed is versioned `packages-16-amd64-1.1.1`. Moving an older
installation to it requires a coordinated base, kernel and driver upgrade;
changing the package URL alone is insufficient. Existing stable-feed users
remain on their current feed. Physical GPU, firmware, radio and retained-OS
qualification remains explicitly recorded, rather than inferred from VM tests.

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
- A package repository with what pkg.FreeBSD.org does not publish: the Omarchy ports from the release-specific ports integration ([1.1 candidate](https://github.com/jordanhubbard/freebsd-ports/tree/daemonarchy-1.1-package-baseline), [1.1.1 refresh](https://github.com/jordanhubbard/freebsd-ports/tree/daemonarchy-1.1.1)), and the GPU and Wi-Fi kernel modules (`drm-612-kmod`, `gpu-firmware-*-kmod`, `wifi-firmware-*-kmod`) built for the snapshot kernel.

Other desktop dependencies are downloaded during installation. Compatible official packages come from pkg.FreeBSD.org; the 1.1.1 versioned feed also supplies ordinary dependencies rebuilt for its newer ports/base selection. Network access is required. Keeping those downloads off the ISO keeps each release asset below GitHub's 2 GiB limit; a complete offline desktop payload would exceed that budget.

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

**1.1.0-rc.1 is available for testing; 1.1.1 is in preparation.** See the [roadmap](ROADMAP.md) for remaining
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

Daemonarchy is four repositories:

- **[jordanhubbard/daemonarchy](https://github.com/jordanhubbard/daemonarchy)** (this one): the installer image, its build and test scripts, and these docs.
- **[jordanhubbard/daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop)**: Daemonarchy's artwork and login theme, and the System > FreeBSD tools. Its tags are Daemonarchy's version numbers.
- **[jordanhubbard/omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd)**: the FreeBSD compatibility layer that lets Omarchy run unchanged.
- **[jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports/tree/daemonarchy-1.1.1)**: the ports fork that packages all of it. The 1.1.1 refresh uses `daemonarchy-1.1.1`; the public 1.1 candidate retains `daemonarchy-1.1-package-baseline`. Upstream submissions continue independently of Daemonarchy releases.

## Building

On a FreeBSD 16.0-CURRENT host with poudriere: build the ports, build the image with `./build-iso.sh`, test it with `./test-bhyve.sh` (or `./test-qemu.sh` on a host without bhyve), and publish it. [HACKING.md](HACKING.md) walks through each step, the faster loops for changing the installer, the ports, and the artwork, and the pitfalls met so far.

## Historical limits of 1.0.1

- Whole-disk installs only; no dual boot.
- UEFI machines only, with Secure Boot turned off: the FreeBSD loader is not signed, and the installed disk has no BIOS boot code.
- The install needs a network connection (wired, or Wi-Fi with WPA-PSK or no password; no enterprise Wi-Fi). The desktop has FreeBSD Wi-Fi and Bluetooth panels; Bluetooth supports input devices only.
- NVIDIA GPUs get no driver.
- Virtual machines install and boot, but Hyprland needs a DRM driver, which FreeBSD VMs lack.

## Names and marks

Daemonarchy is a union of two projects and claims to be neither. Omarchy is the desktop and FreeBSD is the operating system underneath; both are credited by name wherever the system describes what it is (the About screen reads "Omarchy <version> on FreeBSD <release>"). Daemonarchy's own identity — the wordmark, the horned "A", the wallpaper, and the login theme's logo — is original artwork that lives in the `x11-wm/daemonarchy` port, apart from Omarchy's files, which are installed as Omarchy ships them. No FreeBSD or Arch Linux logo is used.

Daemonarchy is not affiliated with or endorsed by Omarchy, the FreeBSD Project, or The FreeBSD Foundation. FreeBSD is a registered trademark of The FreeBSD Foundation. Omarchy is used under the MIT license.
