# Daemonarchy 1.4.0 release notes

Daemonarchy 1.4.0 is the release after 1.3.1. It adds support for the MSI Raider
18 HX (Intel Arrow Lake-HX with an RTX 5080), a signed Secure Boot profile that
lets the MacBookPro16,1 install its Wi-Fi firmware again, a live desktop from the
installer media, a measured install screen, installer network bring-up that no
longer depends on a cable, and an optional CUDA and cudalab install on NVIDIA
hardware. The [GitHub release](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.4.0)
is the authority for the final image, asset hashes and publication state.

## What you download

- `daemonarchy-1.4.0-amd64.iso.xz`, xz-compressed. Decompress it before writing
  it: `xz -dc daemonarchy-1.4.0-amd64.iso.xz | dd of=/dev/<usb-device> bs=1M`.
- `daemonarchy-1.4.0-amd64.iso.xz.sha256`, which covers the compressed file you
  download.
- The signed Secure Boot bundle `daemonarchy-1.4.0-boot.txz` with its detached
  `.sig`, and the public certificate in PEM and DER form.

The base is FreeBSD 16.0-CURRENT, OSVERSION `1600029`, built from
daemonarchy-src `06e5befc`; the ports are daemonarchy-ports `b7857842`. The
signed application feed is `packages-16-amd64-1.4.0` (204 packages) and the
optional source and ports checkouts are `checkouts-16-amd64-1.4.0`.

## What changes

- **MSI Raider 18 HX support.** The installer now sees the NVMe drive behind
  Intel VMD (the factory RAID mode). The desktop starts on the Arrow Lake
  iGPU, the touchpad works, and the NVIDIA driver loads. See
  [hardware quirks](hardware-quirks.md#140-on-this-machine) for the four faults
  and their fixes.
- **MacBookPro16,1.** The image carries a signed Secure Boot boot profile, so the
  installer can stage the BCM4364 Wi-Fi firmware and verify its signature. The
  Apple T2's internal USB link no longer takes part in DHCP, and installed
  systems have a clock floor for the T2's clock.
- **Install screen and network.** The installer shows live, measured progress. It
  probes every cabled port, then Wi-Fi, checks DNS and the clock, and an
  installed system waits a bounded time for the first usable connection.
- **Live desktop.** The installer media can start a desktop that leaves the disk
  untouched.
- **CUDA and cudalab.** With a supported NVIDIA GPU the installer offers CUDA 13.2
  and the cudalab demos, selected by default, and downloads them over the
  network during installation. See the limits below.
- **Packages.** The signed feed changes 11 packages from 1.3.1 (cliamp, herdr,
  omacalc, omacut, omarchy-nvim, omasnap, omawrite, owe, owe-lockfeed, ttfx and
  usage); everything else is the 1.3.1 bytes.
- **Compressed image.** The ISO is published xz-compressed, about 1.6 GB.

## Hardware status and limits

- **MSI Raider 18 HX AI A2XWIG:** installs and runs the desktop; keyboard,
  touchpad and the NVIDIA driver work, on operator tests of the development
  images in this cycle, and the Intel Wi-Fi firmware loads. It was tested in
  the factory RAID (VMD enabled) mode; the VMD-disabled mode is the ordinary
  NVMe path and was not separately retested. The touchpad runs in polling mode.
  Linux's ARL004 interrupt-ordering workaround for the VMD controller is not
  ported, so heavy NVMe I/O on the RAID-mode controller has not been stress
  tested. Only I2C controller 0 (`8086:7f4c`) of the Arrow Lake-S PCH is
  recognised.
- **MacBookPro16,1:** installs; the Wi-Fi firmware upload passes its signature
  check. It has no sound: the T2 audio function (`106b:1803`) has no driver and the
  only audio devices are the six HDMI outputs. See the
  [application note](application-note-macbookpro16-1.md#sound).
- **CUDA:** CUDA 13.2 runs a kernel on the RTX 5080 through the Linuxulator with
  a UVM shim. Unified Memory (`cudaMallocManaged`) crashes and is not supported.
  cudalab is built against SDL 3.2, and its graphics demos need Xwayland, which
  the installer adds. A failed CUDA download does not fail the install; it
  prints the command to run again after the first boot.
- **aarch64 is not published.** An arm64 image builds and boots in QEMU, but
  its package feed lacks Chromium and Hyprland, so it has no desktop. It is
  development only.
- **Deferred to 1.4.1:** the exact-image installer network matrix and
  image-based upgrade and rollback. `pkg upgrade` of a running system is
  unaffected. See the [1.4.1 plan](roadmap/release-1.4.1.md), which also holds
  the target of a ten times faster install: fetching dominates the install time
  in the one measured run.
- **Physical results on the final image.** The MSI and MacBook results above come
  from the development images built during this cycle and from live changes made
  on the machines. The final image was run in a QEMU virtual machine against the
  public feeds; a physical rerun of the exact final image was not done before
  publication.

## Verification

The staged assets passed `scripts/verify-release-assets.py` (sizes, digests, the
ISO checksum file, matching PEM and DER, the detached boot-bundle signature and
its source and OSVERSION identity). A QEMU install of the final image against the
public application and checkout feeds, with the graphical login check, is
recorded in [the 1.4.0 test record](testing-1.4.0.md).
