# Daemonarchy

Daemonarchy is the [Omarchy](https://omarchy.org) desktop on FreeBSD: DHH's opinionated Hyprland desktop, ported to FreeBSD and installed the way the Omarchy ISO installs it on Arch. The name is a homage: Omarchy's *-archy*, ruled by the BSD daemon.

This repository builds a bootable FreeBSD 16.0-CURRENT image with the Daemonarchy installer: the same welcome screen, keyboard, account, hostname, and timezone questions as the Omarchy ISO, then a whole-disk install that boots into the desktop. Daemonarchy is not affiliated with Omarchy; the Omarchy software itself comes, unchanged apart from FreeBSD compatibility, from the `x11-wm/omarchy` port.

Each release is built from a FreeBSD 16.0-CURRENT snapshot. CURRENT moves daily, so an image is tied to the snapshot it was built from.

## Download

The current installable image is **[daemonarchy-16.0-20261007](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-16.0-20261007)** (UEFI, x86-64, 1.7 GB):

- ISO: [daemonarchy-16.0-20261007.iso](https://github.com/jordanhubbard/daemonarchy/releases/download/daemonarchy-16.0-20261007/daemonarchy-16.0-20261007.iso)
- SHA-256: `1b4695920a2164aac60776c11a71ddf4aac4bbb9d980242ec355f3ac4805f539` ([checksum file](https://github.com/jordanhubbard/daemonarchy/releases/download/daemonarchy-16.0-20261007/daemonarchy-16.0-20261007.iso.sha256))

Write it to a USB stick with `dd if=daemonarchy-16.0-20261007.iso of=/dev/<usb-device> bs=1m` (`bs=1M` on Linux), turn Secure Boot off, and boot from the stick. The install erases the disk you choose and downloads about 1,000 packages, so it needs a network connection. Every image, with its release notes, is on the [releases page](https://github.com/jordanhubbard/daemonarchy/releases).

To build an image yourself or work on Daemonarchy, see [HACKING.md](HACKING.md).

## What FreeBSD adds

Daemonarchy is the Omarchy desktop with FreeBSD underneath, and it puts FreeBSD's strengths in the Omarchy menu under **System > FreeBSD**:

- **Boot environments.** The system lives on ZFS, and every Omarchy update first saves a boot environment: a bootable copy of the whole system. Roll back to any of them from the menu or the boot loader.
- **Restore files.** Hourly and daily ZFS snapshots of home directories, kept for a day and a week; open one in the file manager and copy back what you lost.
- **Jails.** Lightweight FreeBSD containers, each with its own FreeBSD system and packages.
- **Virtual machines.** Run Linux, Windows, or the BSDs with bhyve, FreeBSD's hypervisor.
- **Trace the system.** Live views of what the system is doing, through DTrace.
- **Hack on Daemonarchy.** Fetch the sources and run the desktop from your own checkout of Omarchy; see [HACKING.md](HACKING.md).

Omarchy's AI coding agents work here too: Claude Code, Codex, Crush, and the GitHub CLI come from FreeBSD's own packages, and Linux-only tools such as the Cursor CLI and OpenCode run under FreeBSD's Linux compatibility, each installed the first time you run it.

## What the image contains

- A live FreeBSD system (from the snapshot) that logs root in on the first console and starts the installer.
- The installer: `configurator` asks the questions, `install` installs, `dashboard` shows its progress, `launch` ties them together.
- The snapshot's `base.txz` and `kernel.txz`, which become the installed system.
- A package repository with what pkg.FreeBSD.org does not publish: the Omarchy ports from [jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports) (`omarchy` branch), and the GPU and Wi-Fi kernel modules (`drm-66-kmod`, `gpu-firmware-*-kmod`, `wifi-firmware-*-kmod`) built for the snapshot kernel.

Everything else the desktop needs (Hyprland, Qt, browsers, ...) is downloaded from pkg.FreeBSD.org during the install, so the machine needs network access. That keeps the image well under GitHub's 2 GiB release asset limit; a fully offline image would be 7-8 GB.

## Updates

An installed system keeps itself current with `pkg upgrade` (which Omarchy's update runs). FreeBSD's packages come from pkg.FreeBSD.org. Daemonarchy's own packages (the Omarchy ports and the patched Quickshell) come from a signed repository published as the assets of the [`packages-16-amd64`](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64) release. The installer adds its key as `/usr/local/etc/pkg/keys/daemonarchy.pub`, so fixes reach you without a new ISO. The image's own packages stay on the disk as a fallback repository, `Daemonarchy-ISO`, since the GPU and Wi-Fi modules built for its kernel are only there.

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

## The installer

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

## Building

On a FreeBSD 16.0-CURRENT host with poudriere: build the ports, build the image with `./build-iso.sh`, test it with `./test-bhyve.sh` (or `./test-qemu.sh` on a host without bhyve), and publish it. [HACKING.md](HACKING.md) walks through each step, the faster loops for changing the installer, the ports, and the artwork, and the pitfalls met so far.

## Limits

- Whole-disk installs only; no dual boot.
- UEFI machines only, with Secure Boot turned off: the FreeBSD loader is not signed, and the installed disk has no BIOS boot code.
- The install needs a network connection (wired, or Wi-Fi with WPA-PSK or no password; no enterprise Wi-Fi). After the install, Omarchy's Wi-Fi and Bluetooth panels stay empty: they need NetworkManager and BlueZ, which FreeBSD does not have.
- NVIDIA GPUs get no driver.
- Virtual machines install and boot, but Hyprland needs a DRM driver, which FreeBSD VMs lack.

## Names and marks

Daemonarchy is a union of two projects and claims to be neither. Omarchy is the desktop and FreeBSD is the operating system underneath; both are credited by name wherever the system describes what it is (the About screen reads "Omarchy <version> on FreeBSD <release>"). Daemonarchy's own identity — the wordmark, the horned "A", the wallpaper, and the login theme's logo — is original artwork that lives in the `x11-wm/daemonarchy` port, apart from Omarchy's files, which are installed as Omarchy ships them. No FreeBSD or Arch Linux logo is used.

Daemonarchy is not affiliated with or endorsed by Omarchy, the FreeBSD Project, or The FreeBSD Foundation. FreeBSD is a registered trademark of The FreeBSD Foundation. Omarchy is used under the MIT license.
