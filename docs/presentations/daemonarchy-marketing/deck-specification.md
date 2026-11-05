# Daemonarchy for users and decision makers: deck specification

title: Daemonarchy: the Omarchy desktop on FreeBSD
footer: Daemonarchy | users | 1.5.1
subject: Marketing deck. Describes published 1.5.0 and the planned 1.5.1.
cover-footer: Edition for 1.5.1. Describes the published 1.5.0 release (2026-11-04) as documented in the repository; 1.5.1 items are plans, not shipped.

This file is the single source of the slide content. `build_deck.py` turns it into
the PowerPoint file; the narrative it follows is in the narrative specification
next to it. Every slide carries a `source:` line naming the repository document
its claims come from.

## Daemonarchy
layout: cover
kicker: Daemonarchy 1.5.x
lede: The Omarchy desktop, running on FreeBSD, installed the way the Omarchy ISO installs it on Arch.
notes: Open with the one-sentence definition. The name is a homage: Omarchy's -archy, ruled by the BSD daemon. Say up front that this deck describes what the repository documents for 1.5.0 and what 1.5.1 plans, and marks both honestly.

## An opinionated desktop on an operating system you can inspect
layout: bullets
kicker: What it is
image: ../../images/desktop.png
caption: The Daemonarchy desktop with the System > FreeBSD menu open (docs/images/desktop.png).
- **Omarchy's Hyprland desktop**, ported to FreeBSD. The Omarchy software comes unchanged apart from FreeBSD compatibility, from the `x11-wm/omarchy` port.
- **A bootable installer image** with the same welcome, keyboard, account, hostname and timezone questions as the Omarchy ISO.
- **FreeBSD 16.0-CURRENT underneath**, from a snapshot; each image is tied to the snapshot it was built from.
- **Independent.** Not affiliated with or endorsed by Omarchy, the FreeBSD Project or the FreeBSD Foundation.
source: README.md (intro, Names and marks)
notes: The screenshot shows fastfetch, btop, boot environments and home snapshots with the System > FreeBSD menu open.

## Two projects joined, neither claimed
layout: cards
kicker: Why it exists
lede: Daemonarchy is a union of two projects and says so wherever the system describes itself (About reads "Omarchy <version> on FreeBSD <release>").
### From Omarchy | red
- A keyboard-driven Hyprland desktop with one set of opinions.
- The installer's look and its setup form, sourced from Omarchy's own files so the questions and validation are identical.
- Its panels: network, Wi-Fi, Bluetooth, sound.
### From FreeBSD | blue
- ZFS with boot environments instead of Snapper snapshots.
- Jails, bhyve virtual machines and DTrace.
- Its own network, Wi-Fi (`wpa_supplicant`) and Bluetooth stacks, and the Ports/pkg package collection.
### Added by Daemonarchy | green
- An installer onto a whole disk, a selected GPT partition or free space.
- A signed package feed for what pkg.FreeBSD.org does not publish.
- Original artwork, login theme and the System > FreeBSD menu.
source: README.md (What FreeBSD adds, The installer, Names and marks)

## What stays the same as FreeBSD
layout: cards
kicker: Same
lede: It is FreeBSD, not a reimplementation: your FreeBSD knowledge and tools still apply.
### The base system | blue
- FreeBSD 16.0-CURRENT, OSVERSION `1600029` in 1.5.0.
- Base, kernel and 32-bit libraries come from a FreeBSD snapshot's `base.txz`, `kernel.txz` and `lib32.txz`.
- Built from the owned `daemonarchy-src` fork, which tracks upstream and sends useful fixes back.
### The tools | blue
- `pkg` and the official FreeBSD package collection: compatible packages come from pkg.FreeBSD.org.
- ZFS, boot environments, jails, bhyve and DTrace.
- Optional shallow `/usr/src` and `/usr/ports` Git checkouts, pinned to the release.
### The hardware layer | blue
- FreeBSD's drivers and Wi-Fi stack, with DRM and firmware kernel modules built for the snapshot kernel.
- Bluetooth keyboards and mice through FreeBSD's own stack.
- Linux programs only through FreeBSD's Linuxulator, and only once an exact version is qualified.
source: README.md (What the image contains, Source); docs/freebsd-application-policy.md

## What is different from stock FreeBSD
layout: table
kicker: Different
widths: 1.4,3,3.4
| Area | Stock FreeBSD | Daemonarchy |
| --- | --- | --- |
| Out of the box | A base system you build a desktop on | A finished Omarchy Hyprland desktop with SDDM, menus, theme and artwork |
| Installer | bsdinstall | Omarchy-style questions, a network step (packages download at install) and a disk step with optional encryption |
| Packages | pkg.FreeBSD.org | Also a signed Daemonarchy feed, published as GitHub release assets, with the Omarchy ports and snapshot-built GPU and Wi-Fi modules |
| Base and kernel source | Upstream FreeBSD | An owned fork, `daemonarchy-src`, pinned by full commit per release |
| Releases | FreeBSD's schedule | Its own semantic version; each image tied to one CURRENT snapshot |
| Upgrades | FreeBSD's own tools | `pkg upgrade` updates applications; base and kernel still arrive by a new image (network upgrade is planned for 1.5.1) |
source: README.md; HACKING.md (the upgrade model today); docs/roadmap/release-1.5.1.md

## FreeBSD's strengths, one menu away
layout: bullets
kicker: What you get
image: ../../images/freebsd.png
caption: Home snapshots in Files, a live DTrace view, the ZFS pool and the sound panel (docs/images/freebsd.png).
- **Boot environments.** Every Omarchy update first saves a bootable copy of the whole system; roll back from the menu or the boot loader.
- **Restore files.** Hourly and daily ZFS snapshots of home directories, kept for a day and a week.
- **Jails and virtual machines.** FreeBSD containers, and bhyve for Linux, Windows or the BSDs.
- **Trace the system** with live DTrace views.
- **Hack on Daemonarchy** from the same menu: fetch the sources and run the desktop from your own checkout.
source: README.md (What FreeBSD adds)

## New in 1.5.0, with the evidence stated
layout: cards
kicker: What shipped
lede: The release was re-scoped on 2026-11-03 to work that has evidence.
### Windows programs and Steam (amd64) | blue
- Apps menu entries that set up Wine, Wine Mono and DXVK on first launch.
- [verified] On a build VM the real first run created the prefix, ran Valve's installer, and Steam updated itself (headless).
- [not verified] A Windows game or Steam window on real hardware.
### Graphical package manager | blue
- `daemonarchy-pkg`: a GTK 4 window over the installer's planner, with a plan before every change.
- [limit] Packaged, but no real-desktop evidence yet; OctoPkg stays the fallback.
### Faster login on one machine | green
- Aquamarine probes connectors only on hotplug.
- [verified] MSI Raider 18 HX: login to the shell 2.95 s to 1.32 s warm, from the first version of the patch.
- [not verified] Hotplug, resume, lid and VT switch.
source: docs/release-1.5.0.md (What changes)

## How it installs
layout: diagram
kicker: Installing
lede: A USB stick, a network connection, and answers to the familiar questions.
box: a | 0,0 | Download | The `.iso.xz` and its `.sha256` from the GitHub release | blue
box: b | 1,0 | Write a stick | `xz -dc image.iso.xz \| dd of=/dev/<usb> bs=1M` | blue
box: c | 2,0 | Boot | Secure Boot off, or enroll the project certificate | blue
box: d | 3,0 | Answer | Welcome, keyboard, account, hostname, timezone, network, disk | red
box: e | 4,0 | Install | ZFS layout, base system, then `pkg` installs the desktop | green
arrow: a -> b
arrow: b -> c
arrow: c -> d
arrow: d -> e
- Whole-disk mode erases the disk; partition mode replaces only the partition you select. The installer needs a network: packages download during the install.
- Unattended installs read answers from a `CIDATA` drive. A console rescue menu and approved remote debugging help when something goes wrong.
source: README.md (Download, The installer, Unattended installs); docs/getting-started.md; docs/rescue-console.md

## Install weight: a measured, uncomfortable comparison
layout: bars
kicker: Honest numbers
lede: Measured at 1.4.0 and recorded in the repository; not re-measured for 1.5.0.
### Installed size (GiB)
bar: Omarchy v4.0.6 | 7.9 | GiB | 17 | slate
bar: Daemonarchy 1.4.0 | 16.8 | GiB | 17 | red
### Archive download (GiB)
bar: Omarchy v4.0.6 | 2.7 | GiB | 6 | slate
bar: Daemonarchy 1.4.0 | 5.55 | GiB | 6 | red
### Install fetch vs install (s, live8 run)
bar: Fetching packages | 2565 | s | 2700 | red
bar: Installing them | 141 | s | 2700 | green
---
- About 1,189 packages against about 918. Omarchy's ISO carries its whole mirror (6.19 GB); ours is a 1.59 GB `.iso.xz` and the rest comes over the network. Omarchy's "about ten minutes" is its documented figure, not reproduced here.
- Candidates to trim (about 5.3 GiB installed) are listed but not yet removed; 1.4.1 added a parallel package fetch.
source: docs/install-weight-vs-omarchy.md; docs/release-1.4.1.md
notes: These are the 2026-10-30 investigation figures for the 1.4.0 line. Say plainly that delivery, not package count, is the main gap, and that nothing here claims 1.5.0 is faster.

## What is verified, and what is not
layout: cards
kicker: Evidence
lede: Published does not mean physically qualified. The release notes keep the two apart.
### Evidence in hand | green
- Signed Daemonarchy package feeds, with the public key installed as `daemonarchy.pub`.
- amd64 image (BIOS or UEFI) and its signed Secure Boot bundle published with checksums.
- aarch64 image installs and boots under QEMU with an e1000e NIC (919 archives, about 20 minutes).
- Windows programs first run on a build VM, headless.
### Not verified | amber
- Physical runs of the final amd64 image on the MSI Raider 18 HX and the MacBookPro16,1 were not made before publication.
- No Windows game or Steam window on real hardware.
- Wi-Fi and Hyprland on any particular machine: no guarantee.
- Image-based upgrade and rollback; the exact-image network matrix.
source: docs/release-1.5.0.md (What is not done, Hardware status and limits)

## Architectures and hardware, plainly
layout: table
kicker: Status
widths: 1.6,1.3,5
| Target | Status | What the repository says |
| --- | --- | --- |
| amd64 (BIOS or UEFI) | Published | The primary image. Hardware results are per machine and per build; read the hardware quirks before choosing. |
| aarch64 (UEFI) | Community validation | Installs and boots in QEMU; a VirtIO GPU path reaches the SDDM greeter and session in software. Known issue: with QEMU's default virtio-net card the install stalls during package fetch, so use an e1000e card. The fix, daemonarchy-src PR #59, is merged and ships in 1.5.1. |
| NVIDIA RTX Spark laptop | Deferred | The first physical arm64 target: tested, not yet working. The kernel stops starting CPUs; support is deferred and no physical-desktop evidence is claimed. |
| Apple silicon laptops | Not a target | They cannot be install targets; Macs appear only as QEMU hosts. |
source: docs/release-1.5.0.md; docs/aarch64.md; docs/application-note-rtx-spark.md

## aarch64 today: it boots in QEMU
layout: bullets
kicker: Community validation
image: ../../images/aarch64-qemu-sddm-greeter.png
caption: The SDDM greeter in a QEMU guest, software rendering (docs/images/aarch64-qemu-sddm-greeter.png). Not physical hardware.
- **What was seen:** an installed disk reaching the SDDM greeter and the Omarchy session in software, in QEMU with a VirtIO GPU.
- **What was not:** hardware 3D, a physical GPU, sound, Wi-Fi, upgrade, or the live desktop on real hardware.
- **Help wanted:** if you have arm64 hardware, try it and report the machine, the image SHA-256 and the result. Success reports help as much as failures.
source: docs/aarch64.md (Status in 1.5.0)

## Trust and updates
layout: cards
kicker: Keeping it current, safely
### Signed by design | green
- Packages from the Daemonarchy feed are signed; the installer adds its public key.
- amd64 Secure Boot: a signed boot bundle and a published certificate.
- In 1.5.0 no signing key was on a build machine; each release is signed in one planned session.
### What `pkg upgrade` does | blue
- Updates applications from the signed feeds, with no new ISO.
- The desktop's Update saves a boot environment first (per the README; implemented in omarchy-freebsd).
### What it does not do | amber
- It does not upgrade the base, kernel, loader or trust anchors. No base or kernel feed is published yet.
- Moving to a release that changes the snapshot or kernel still needs the new ISO.
source: HACKING.md (the upgrade model today); docs/release-1.5.0.md (Upgrading); docs/mastering-1.5.0.md

## What 1.5.1 plans
layout: cards
kicker: Next
lede: Plans, not claims: each item needs retained evidence before it counts as done.
### Fix and upgrade | blue
- [planned] The aarch64 virtio-net receive stall fix (daemonarchy-src PR #59) ships.
- [planned] Network upgrade of base, kernel, modules and boot files with boot-environment rollback (NETUP-001), trust rotation (NETUP-002) and upgrade QA (NETUP-003).
### Fork and build | blue
- [planned] A fork guide and one configuration for publishing your own installer and feeds (FORK-001).
- [planned] Faster native builds through Literate AI (BUILD-001 and related). No speed-up is claimed today.
### Still open | amber
- [limit] RTX Spark laptop support, T2 Touch ID and complete GUI package manager evidence remain open.
source: docs/roadmap/release-1.5.1.md; docs/release-1.5.0.md

## Try it, report it, help
layout: bullets
kicker: Get started
lede: Daemonarchy is open source under the licenses listed in the repository.
- **Download** the latest release from github.com/jordanhubbard/daemonarchy and read its release notes and hardware limits first.
- **Follow** `docs/getting-started.md`: write the stick, install, and your first hour on the desktop.
- **Report** results with the machine, the image SHA-256 and what you ran. Open an issue on the repository.
- **Hack on it** with the engineering deck and `HACKING.md`: the repository maps its five repositories, the build loop and the release gates.
- **Remember** the limits: Wi-Fi and Hyprland are not guaranteed on any particular machine.
source: README.md; docs/getting-started.md; docs/aarch64.md (Reporting)
