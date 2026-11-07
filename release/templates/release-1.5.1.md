# Daemonarchy 1.5.1 release notes

<!-- Template for the draft release pull request (scripts/prepare-release.py copies it to
docs/release-1.5.1.md). Written on 2026-11-05 from what is merged on main, daemonarchy-src
`daemonarchy` and daemonarchy-ports `main` at that time. Before the release the owner re-checks
every claim below against main and the evidence, removes what did not ship and adds what did.
The upper-case words between pairs of at-signs are filled by scripts/fill-release.py.
For the published result use docs/release-1.5.1.md and release/current.json. -->

Daemonarchy 1.5.1 is the release after 1.5.0. It makes a failed installation explain itself,
keeps console messages from corrupting the install screen, fixes the arm64 virtio-net receive
stall, and rewrites the documentation for newcomers. Published @@PUBLISHED_DATE@@. The
[GitHub release](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.5.1)
is the authority for the final images, asset hashes and publication state.

## What you download

- `daemonarchy-1.5.1-amd64.iso.xz` (@@AMD64_ISO_BYTES@@ bytes, SHA-256
  `@@AMD64_ISO_SHA256@@`), the x86-64 image for BIOS or UEFI.
- `daemonarchy-1.5.1-aarch64.iso.xz` (@@AARCH64_ISO_BYTES@@ bytes, SHA-256
  `@@AARCH64_ISO_SHA256@@`), the arm64 image, UEFI only. It is still a
  community-validation image: read [the aarch64 section](#aarch64-image-community-validation).
- `daemonarchy-hwtrace-1.5.1-amd64.img.xz` (@@HWTRACE_BYTES@@ bytes, SHA-256
  `@@HWTRACE_SHA256@@`) and `daemonarchy-hwtrace-1.5.1-aarch64.img.xz`
  (@@HWTRACE_AARCH64_BYTES@@ bytes, SHA-256 `@@HWTRACE_AARCH64_SHA256@@`), the hardware
  bring-up trace images. They are not installers: each holds its ISO's own kernel and loader
  and carries no keys. See [the trace image](boottrace.md).
- A `.sha256` file for each image, which covers the compressed file you download.
- The signed Secure Boot bundle `daemonarchy-1.5.1-boot.txz` with its detached `.sig`,
  and the public certificate in PEM and DER form (amd64; aarch64 has none).

Decompress an image before writing it:
`xz -dc daemonarchy-1.5.1-amd64.iso.xz | dd of=/dev/<usb-device> bs=1M`.

The base is FreeBSD 16.0-CURRENT, OSVERSION `1600029`, built from daemonarchy-src
`cb38d64` (the 1.5.0 snapshot `303b364` plus the kernel changes below); the ports are
daemonarchy-ports `@@PORTS_SHORT@@`. The installer commit is `@@INSTALLER_SHORT@@`. The signed
application feeds are `@@PACKAGES_AMD64_FEED@@` and `@@PACKAGES_AARCH64_FEED@@`; the optional
source and ports checkouts are `@@CHECKOUTS_AMD64_FEED@@` and `@@CHECKOUTS_AARCH64_FEED@@`.

## What changes

- **A failed installation explains itself** ([#257](https://github.com/jordanhubbard/daemonarchy/issues/257),
  [#281](https://github.com/jordanhubbard/daemonarchy/pull/281)). Instead of a bare shell after
  `[exited]`, the installer stops on a failure screen with the end of the install log, the last
  recorded stage and the log locations, and a menu: view the log, open a shell, reboot or power off.
  The installer's own exit status decides the outcome, so a progress warning no longer turns a
  successful installation into a failure. Unattended installs do not wait. **Verified:** tests on
  Linux with tmux. **Not verified:** @@INSTALLER_FAILURE_EVIDENCE@@
- **Console messages no longer shift the install screen** ([#244](https://github.com/jordanhubbard/daemonarchy/issues/244),
  [#282](https://github.com/jordanhubbard/daemonarchy/pull/282)). The live image keeps syslog
  messages off the console, the install screen redraws itself every 12 seconds (and at once on
  `C-b r`), ntpd tolerates a large clock step, and a wrapped header row is indented. The installed
  system's `syslog.conf` is unchanged.
- **A 10-second boot menu** ([#290](https://github.com/jordanhubbard/daemonarchy/pull/290)). The image and
  the installed system wait 10 seconds instead of 3 at the boot menu, long enough to read it and choose.
- **arm64 virtio-net receive stall fixed in the kernel**
  ([daemonarchy-src #59](https://github.com/jordanhubbard/daemonarchy-src/pull/59), carried to the
  kernel branch by [#61](https://github.com/jordanhubbard/daemonarchy-src/pull/61)). The virtqueue
  notification checks now use a full barrier on every architecture, so a QEMU arm64 guest no longer
  stalls during the package fetch with the default virtio network card. @@VIRTIO_EVIDENCE@@
- **arm64 secondary CPU start is bounded and reported**
  ([daemonarchy-src #53](https://github.com/jordanhubbard/daemonarchy-src/pull/53),
  [#60](https://github.com/jordanhubbard/daemonarchy-src/pull/60)). A CPU that never checks in no
  longer hangs the boot forever: the wait gives up after two seconds, reports the stage the CPU
  reached and, by default (`hw.mp.stop_on_failure=1`), starts no more CPUs. This makes the NVIDIA
  RTX Spark failure observable; it does not fix it. On the Spark the 1.5.1 image still hangs after
  starting the fourth CPU, as 1.5.0 did, so Spark support moves to 1.6.
- **Documentation for newcomers.** A rewritten README for users, a narrative-first HACKING guide
  that compares the FreeBSD way with the Daemonarchy way, an [installer reference](installer-reference.md),
  and user and engineering [slide decks](presentations/README.md).
- **Licensing.** Each repository has a project statement (`LICENSE.daemonarchy`, BSD-2-Clause for
  Daemonarchy-original work) and a `licenses/` index; FreeBSD's own `COPYRIGHT` files are unchanged.
- **Graphical package manager in the menu.** The Packages menu entries open `daemonarchy-pkg`,
  with OctoPkg kept as **Packages (OctoPkg)**
  ([daemonarchy-desktop #1](https://github.com/jordanhubbard/daemonarchy-desktop/pull/1), shipped by
  moving `x11-wm/daemonarchy` to daemonarchy-desktop `85322f5` in
  [daemonarchy-ports #53](https://github.com/jordanhubbard/daemonarchy-ports/pull/53)). It is an
  application package: `pkg upgrade` delivers it.

## What is not done, and why

1.5.1 was released with what has evidence. The rest of the
[1.5.1 plan](roadmap/release-1.5.1.md) stays open and is not claimed.

| Item | Why it is not in this release |
| --- | --- |
| NETUP-001, NETUP-002, NETUP-003 | Upgrading the base, kernel, modules, boot files and trust over the network, and qualifying upgrade paths, are not implemented. A new base still arrives with a new image. |
| FORK-001 | No fork guide or single fork configuration yet. |
| BUILD-001, COMP-001, PERF-001, PERF-002, DEV-001, ADOPT-003, SRC-002, RELEASE-002 | Need native execution by a later Literate AI runtime and native qualification. |
| DEBUG-003 | Loader, forced `mountroot>` and panic network control are still open. |
| HW-004 | T2 Touch ID needs a Mac with enrolled fingers. |
| NVIDIA RTX Spark (aarch64) | The 1.5.1 image still hangs after starting the fourth CPU, as 1.5.0 did. Planned for 1.6. |
| GUI-001, EXT-002, DESKTOP-001, SIGN-001 | Their 1.5.0 carry-over acceptance is not complete. |
| ARCH-001, LIVE-001, NET-001, NET-002, GPU-001, INSTALL-PERF-001, PKG-002, VISUAL-SDK-001, EXT-001 | Open queue items; their partial delivery is as in earlier releases. |

## aarch64 image: community validation

The aarch64 image is still released so that people with arm64 hardware can try it and tell
us what happens. @@AARCH64_FINAL_QEMU_STATUS@@ The NVIDIA RTX Spark laptop still hangs after
starting its fourth CPU and is deferred to 1.6; no physical aarch64 install is claimed. See [aarch64.md](aarch64.md).

## Hardware status and limits

- **No Wi-Fi or Hyprland guarantees.** Wi-Fi depends on the chipset and firmware, and
  the desktop depends on the GPU driver.
- @@PHYSICAL_STATUS@@
- **MSI Raider 18 HX and MacBookPro16,1.** The limits in the
  [1.4.0 notes](release-1.4.0.md#hardware-status-and-limits) stand.

## Upgrading

Application packages update with `pkg upgrade` from the signed feed. The kernel changes in this
release (virtio and arm64 CPU start) arrive only with the new image; upgrading an installed system
through the image has not been tested and is not supported.
