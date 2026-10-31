# Daemonarchy 1.4.1 release notes

Daemonarchy 1.4.1 is the release after 1.4.0, published before 1.4.0 was announced.
It makes installation faster and independent of pkg.FreeBSD.org, adds the first
installer extensions (four arcade games) on a new visual SDK, fixes the install
failure 1.4.0 had on NVIDIA hardware, and adds an aarch64 image for community
validation. The
[GitHub release](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.4.1)
is the authority for the final images, asset hashes and publication state.

## What you download

- `daemonarchy-1.4.1-amd64.iso.xz` (1,592,484,392 bytes, SHA-256
  `ea0b6d9ed435a30c75ee4b5acc70f2095d09c243adbc08532d2f8ab41e0014ca`), the x86-64 image for BIOS or UEFI.
- `daemonarchy-1.4.1-aarch64.iso.xz` (957,807,376 bytes, SHA-256
  `eef5e9bb3b100365513a6ca3dce6d483142886c65b70411ef0a9db2aa994b076`), the arm64 image, UEFI only. **It is a
  community-validation image; read [the aarch64 section](#aarch64-image-community-validation)
  before using it.**
- A `.sha256` file for each image, which covers the compressed file you download.
- The signed Secure Boot bundle `daemonarchy-1.4.1-boot.txz` with its detached `.sig`,
  and the public certificate in PEM and DER form. The bundle is the amd64 Secure Boot
  bundle; aarch64 has none.

Decompress an image before writing it:
`xz -dc daemonarchy-1.4.1-amd64.iso.xz | dd of=/dev/<usb-device> bs=1M`.

The base is FreeBSD 16.0-CURRENT, OSVERSION `1600029`, built from daemonarchy-src
`303b364`; the ports are daemonarchy-ports `dd277aff`. The installer commit is
`567870bb`. The signed application feeds are `packages-16-amd64-1.4.1-r2` and
`packages-16-aarch64-1.4.1-r2`; the optional source and ports checkouts are
`checkouts-16-amd64-1.4.1-r2` and `checkouts-16-aarch64-1.4.1-r2`.

## What changes

- **Parallel fetch and our own package distribution.** The installer fetches the
  whole resolved package closure up front with a pool of parallel connections
  (16 for our GitHub feeds, 4 for the pkg.FreeBSD.org fallback) instead of one
  archive at a time. The packages are zstd-compressed and come from signed,
  versioned Daemonarchy feeds on GitHub; pkg.FreeBSD.org is only a fallback: while one of our closure shards answers, the
  install transaction does not use it at all (the installed system keeps it for
  updates). In the release-image QEMU runs no package came from pkg.FreeBSD.org.
  pkg.FreeBSD.org dropped a package a day after 1.4.0 and every fresh install
  failed, so the whole installer closure, upstream packages included, is now hosted
  by us for both architectures (the `-upstream` feeds below). Parallel fetch was
  measured 5.2 times faster than the single-connection fetch against a real mirror,
  and an aarch64 QEMU install went from 39 minutes to 11 against a local package
  cache. The release image fetching everything over public GitHub, at about 2.4 MB/s
  from the test host, took 36 minutes; the amd64 release image installed in a QEMU
  guest in 13 minutes. No 10x figure is claimed: the physical-machine baselines for the MSI and MacBook that the plan
  asked for were not completed.
- **Install trace and metrics.** Every installation writes a microsecond-resolution
  trace of its timed events (phases, storage operations, each package download and
  unpack, device events, samples, DNS and TLS probes) and records the source of every
  archive. See [install-trace.md](install-trace.md).
- **Installer on the visual SDK.** The installer's rendering, palettes, animation,
  input and audio now come from a separately packaged visual SDK, so the installer
  is the SDK's first consumer and has no private rendering path beside it.
- **Four arcade games as installer extensions.** The Extensions menu in the
  installer opens classic-arcade homages in their own windows while the install
  continues in the background; prompts, errors and the result always preempt play.
  Extensions are not on the ISO: they come from the signed, compressed feeds
  `extensions-16-amd64-1.4.1` and `extensions-16-aarch64-1.4.1` when you choose
  one. See [installer-extensions.md](installer-extensions.md) and
  [extension-feed.md](extension-feed.md).
- **Closure feeds.** The signed upstream snapshots `packages-16-amd64-1.4.1-upstream`,
  `packages-16-aarch64-1.4.1-upstream` and `packages-16-aarch64-1.4.1-upstream-2`
  (the five packages Epiphany adds) hold the installer's upstream packages. They are
  separate, non-latest releases; the ISO build refuses a feed that is missing,
  unsigned or does not resolve the installer's packages.
- **Cudalab as a virtual app.** The `daemonarchy-cudalab` launcher builds a pinned
  cudalab once, in a first-run window, and later launches open it directly. Found
  on the MSI and fixed: the Choreograph demo made the whole app exit because the
  FreeBSD driver lacks `cudaMallocAsync` (a preloaded fallback to `cudaMalloc`
  handles it); the app no longer runs inside the terminal that launched it; it has
  an icon; its audio is fixed; and `--update` builds the newest upstream cudalab and
  keeps it. These were found by running the app on the MSI.
- **Remote debugger.** Debug sessions take leases and read their state from reality,
  orphaned sessions are cleaned up, and a watchdog ends a session whose holder is
  gone. See [remote-agent-debug.md](remote-agent-debug.md).
- **Live power fix.** Rebooting or powering off the live system no longer needs the
  install stick, so pulling the stick no longer ends in a panic.
- **Integrity before CUDA.** The 1.4.0 image failed on the MSI Raider at the final
  package integrity check when the default CUDA offer was accepted, because the CUDA
  phase replaced files owned by packages. Package verification now runs before the
  optional CUDA and desktop additions.
- **Desktop.** tigervnc and fltk are carried in the feed (upstream dropped them), and
  the Aquamarine exit-time fault is fixed (`aquamarine` has a new port revision).
- **Upstream sync.** daemonarchy-src is synced to FreeBSD at `303b364`, which
  includes the vtnet WITNESS fix. The ports revision is the one named above.

## aarch64 image: community validation

The aarch64 image is released so that people with arm64 hardware can try it and tell
us what happens. The bar it met is: it boots and installs in a QEMU virtual machine.
Nothing beyond that is claimed.

What was verified (records:
[`verification/aarch64-1.4.1-staging-20261030-development.json`](../verification/aarch64-1.4.1-staging-20261030-development.json)
and [aarch64.md](aarch64.md)):

- On a QEMU 11.1.2 guest with HVF on an Apple silicon Mac (machine `virt`, AArch64
  edk2, virtio-gpu), a QA candidate image installed 1,157 packages and the installed
  system booted under UEFI. The first run took 39 minutes (single-connection
  fetch); a second run on a later candidate with parallel fetch took 11 minutes.
  Both runs passed 23 checks and failed 2.
- The two failed checks: `sddm running` (the guest has no DRM/KMS driver, so the
  desktop's login manager does not start; the base `virtio_gpu` driver is console
  only) and `updates from the signed Daemonarchy repository` (that run was before
  the public feed URLs existed).
- The aarch64 package feeds are signed, and a client with the pinned key accepts
  them and refuses a different key.

What was not verified:

- **Real arm64 hardware.** No physical aarch64 machine was tested. Apple silicon
  Macs are not install targets at all; they can only host virtual machines.
- **Graphics.** There is no DRM/KMS driver for any aarch64 GPU in the package set, so
  there is no hardware-accelerated desktop and SDDM did not run in the VM. A
  graphical desktop was not seen on aarch64.
- **Sound, Wi-Fi, upgrade, rollback, network debugging and the live desktop** were
  not run on aarch64.
- **The release image itself** was not the image used in the QEMU runs above: those
  were QA candidates. The release image itself was then installed in the same QEMU setup from the public feeds: it took 36 minutes, booted under UEFI and passed 33 of 34 checks; the one failure is the known `sddm running` (no DRM device in the guest), and no package came from pkg.FreeBSD.org.
- **Omitted on aarch64:** `chromium` (no aarch64 package), `aether` (no arm64
  build of its frontend dependencies), `mise` (marked broken on aarch64) and
  `edk2@bhyve`. The default browser is **Epiphany**, because no Chromium or Firefox
  exists in FreeBSD's aarch64 packages; omarchy's web-app launchers, which run
  `chromium --app`, do not yet follow the installed browser.

How to report results: open an issue at
<https://github.com/jordanhubbard/daemonarchy/issues> (the repository has no issue
template). Give the machine or VM, the exact image SHA-256, what you ran and what
happened, and attach `/tmp/daemonarchy-network/log` and the install trace if you
have them. Reports of success are as useful as failures.

## Hardware status and limits

- **No Wi-Fi or Hyprland guarantees.** Wi-Fi depends on the chipset and firmware, and
  the desktop depends on the GPU driver. Nothing in this release promises either on
  any particular machine.
- **MacBookPro16,1 Wi-Fi can stall.** The BCM4364 driver can enter a dead associated
  state: the interface reports `associated` and no traffic moves. The fix is
  drafted in [daemonarchy-ports #37](https://github.com/jordanhubbard/daemonarchy-ports/pull/37)
  and is not in this release; it is deferred to 1.4.2 because it changes a kernel
  module and needs a Secure Boot inventory update and a physical retest.
- **Slow first login.** Display-driver sleeps of about 1.6 seconds occur at login,
  and a first-login delay is under investigation. It is a known limitation, not
  fixed.
- **MSI Raider 18 HX and MacBookPro16,1.** The limits in the
  [1.4.0 notes](release-1.4.0.md#hardware-status-and-limits) stand: polling-mode MSI
  touchpad, only Arrow Lake-S I2C controller 0 recognised, no ARL004 VMD interrupt
  workaround, no MacBook sound, CUDA Unified Memory unsupported.
  Installs of the final amd64 image on the MSI Raider 18 HX and the MacBookPro16,1 had not been completed when these notes were written; the image passed a QEMU install and graphical-desktop check.
- **Not done in 1.4.1.** The exact-image network matrix, image-based upgrade and
  rollback, and the ten-times-faster target measured on both physical machines were
  not completed. Nine queue items (ADOPT-002, GUI-001, SRC-001, RELEASE-001,
  COMP-001, PERF-002, DEV-001, DEBUG-003 and HW-004) and the Wi-Fi fix are
  planned for the [1.5.0 plan](roadmap/release-1.5.0.md); none is claimed done. The
  1.4.0 notes said these checks were deferred to 1.4.1; that was not completed.

## Upgrading

Moving a 1.4.0 installation to the 1.4.1 application feed still requires a
coordinated base, kernel and driver upgrade; changing the package URL alone is
insufficient.
