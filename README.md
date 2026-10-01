# Daemonarchy (proof of concept)

Daemonarchy is the [Omarchy](https://omarchy.org) desktop on FreeBSD: DHH's opinionated Hyprland desktop, ported to FreeBSD and installed the way the Omarchy ISO installs it on Arch. The name is a homage: Omarchy's *-archy*, ruled by the BSD daemon.

This repository builds a bootable FreeBSD 16.0-CURRENT image with the Daemonarchy installer: the same welcome screen, keyboard, account, hostname, and timezone questions as the Omarchy ISO, then a whole-disk install that boots into the desktop. Daemonarchy is not affiliated with Omarchy; the Omarchy software itself comes, unchanged apart from FreeBSD compatibility, from the `x11-wm/omarchy` port.

This is a snapshot-based proof of concept. CURRENT moves daily, so an image is tied to the snapshot it was built from.

## What the image contains

- A live FreeBSD system (from the snapshot) that logs root in on the first console and starts the installer.
- The installer: `configurator` asks the questions, `install` installs, `launch` ties them together.
- The snapshot's `base.txz` and `kernel.txz`, which become the installed system.
- A package repository with what pkg.FreeBSD.org does not publish: the Omarchy ports from [jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports) (`omarchy` branch), and the GPU and Wi-Fi kernel modules (`drm-66-kmod`, `gpu-firmware-*-kmod`, `wifi-firmware-*-kmod`) built for the snapshot kernel.

Everything else the desktop needs (Hyprland, Qt, browsers, ...) is downloaded from pkg.FreeBSD.org during the install, so the machine needs network access. That keeps the image well under GitHub's 2 GiB release asset limit; a fully offline image would be 7-8 GB.

## The installer

`overlay/usr/local/libexec/daemonarchy-installer/configurator` keeps the Omarchy ISO configurator's screens and look, and sources Omarchy's own setup form (`install/provisioning/setup-form.sh`, taken from the `omarchy` package at build time) so the questions and validation are identical. Two steps are FreeBSD's own: a network step, since packages are downloaded during the install (wired networks are configured by DHCP at boot; otherwise it scans for Wi-Fi, joins the chosen network, and carries the setting over to the installed system), and the disk step: pick a disk, optionally encrypt it.

`overlay/usr/local/libexec/daemonarchy-installer/install` lays the disk out as an EFI system partition, swap, and a ZFS pool (GELI-encrypted with the user's password when asked) using bsdinstall's dataset layout, so ZFS boot environments take the place of Omarchy's Snapper snapshots. It extracts the base system, installs the FreeBSD loader with an Omarchy brand, and writes the system configuration that the `x11-wm/omarchy` port's install message asks for: D-Bus, seatd and SDDM enabled, the DRM driver for the detected Intel or AMD GPU, fdescfs and linprocfs mounts, the user in `wheel`, `video`, and `operator`, and `/etc/vconsole.conf` for Omarchy's Hyprland keyboard layout. Then `pkg` installs `daemonarchy`, the meta-port for the whole desktop. As on Arch, an encrypted install logs straight into the desktop; otherwise SDDM asks for the password.

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

On a FreeBSD 16.0-CURRENT host with poudriere, as root:

1. Create a jail from the snapshot to install, and extract the snapshot's `kernel.txz` into it (poudriere's `url` method fetches no kernel).
2. Create a ports tree at the commit the official `latest` package set was built from (the `ports_top_git_hash` annotation on any package from it), cherry-pick the Omarchy ports onto it, and bulk-build them together with `graphics/drm-66-kmod`, `graphics/gpu-firmware-kmod`, and `net/wifi-firmware-kmod` using `-b latest`. With `PACKAGE_FETCH_BLACKLIST="drm-*-kmod gpu-firmware-* wifi-firmware-*"` the kernel modules are built for the jail's kernel while every other dependency is the official binary, so the Omarchy packages match what the installer fetches.
3. Run `./build-iso.sh` (see the variables at its top). The image and its `.sha256` land in `/usr/local/poudriere/data/images`.

## Limits of the proof of concept

- Whole-disk installs only; no dual boot.
- UEFI machines only, with Secure Boot turned off: the FreeBSD loader is not signed, and the installed disk has no BIOS boot code.
- The install needs a network connection (wired, or Wi-Fi with WPA-PSK or no password; no enterprise Wi-Fi). After the install, Omarchy's Wi-Fi and Bluetooth panels stay empty: they need NetworkManager and BlueZ, which FreeBSD does not have.
- NVIDIA GPUs get no driver.
- Virtual machines install and boot, but Hyprland needs a DRM driver, which FreeBSD VMs lack.

## Names and marks

Daemonarchy is a union of two projects and claims to be neither. Omarchy is the desktop and FreeBSD is the operating system underneath; both are credited by name wherever the system describes what it is (the About screen reads "Omarchy <version> on FreeBSD <release>"). Daemonarchy's own identity — the wordmark, the horned "A", the wallpaper, and the login theme's logo — is original artwork that lives in the `x11-wm/daemonarchy` port, apart from Omarchy's files, which are installed as Omarchy ships them. No FreeBSD or Arch Linux logo is used.

Daemonarchy is not affiliated with or endorsed by Omarchy, the FreeBSD Project, or The FreeBSD Foundation. FreeBSD is a registered trademark of The FreeBSD Foundation. Omarchy is used under the MIT license.
