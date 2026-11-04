# Daemonarchy 1.5.0 release notes

<!-- Template for the draft release pull request (scripts/prepare-release.py copies it to
docs/release-1.5.0.md). Written from what is merged on main when the template was made.
Before the release the owner re-checks every claim below against main and the evidence,
removes what did not ship and adds what did. The upper-case words between pairs of at-signs
are filled by scripts/fill-release.py (GUI001_EVIDENCE is given with --set). -->

Daemonarchy 1.5.0 is the release after 1.4.1. It adds Windows programs and Steam to the
Apps menu on amd64, the first part of a graphical package manager, sandboxed Lua installer
extensions, and a fix for a Wi-Fi stall on the MacBookPro16,1. It was re-scoped on 2026-11-03 to
what has evidence: the framework-executed goals (build speed, complete source and ports Components,
the development system, multi-machine workers) are in [1.5.1](roadmap/release-1.5.1.md), and support
for the NVIDIA RTX Spark laptop is deferred (see below). Published November 4, 2026. The
[GitHub release](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.5.0)
is the authority for the final images, asset hashes and publication state.

## What you download

- `daemonarchy-1.5.0-amd64.iso.xz` (1,592,500,128 bytes, SHA-256
  `6e18a512e9e2072f96d3e1941da7d57d95ec32aa62b3e2a7cd3493c31007cbfd`), the x86-64 image for BIOS or UEFI.
- `daemonarchy-1.5.0-aarch64.iso.xz` (958,319,980 bytes, SHA-256
  `6936c010949f88c5621018c149d141270d55adcc434b799528d30669ee6840b0`), the arm64 image, UEFI only. It is still a
  community-validation image: read [the aarch64 section](#aarch64-image-community-validation).
- `daemonarchy-hwtrace-1.5.0-amd64.img.xz` (20,073,092 bytes, SHA-256
  `c133741f936498af0daa32298ff405b7f71f77200a7013cb3b3abc396c60ac57`), the hardware bring-up trace image for machines that fail early
  in kernel start (amd64, UEFI). It is not an installer: it holds the ISO's own kernel
  and loader and carries no keys. See [the trace image](boottrace.md).
- `daemonarchy-hwtrace-1.5.0-aarch64.img.xz` (15043936 bytes, SHA-256
  `07c47a408733d69200086100e10d39cbc341a3c245ce58251fe9b85748e9c6e7`), the same trace image for arm64 (UEFI, `BOOTAA64.EFI`),
  built from the aarch64 ISO's kernel and loader. It was used on the RTX Spark laptop;
  see [the Spark note](application-note-rtx-spark.md).
- A `.sha256` file for each image, which covers the compressed file you download.
- The signed Secure Boot bundle `daemonarchy-1.5.0-boot.txz` with its detached `.sig`,
  and the public certificate in PEM and DER form. The bundle is the amd64 Secure Boot
  bundle; aarch64 has none.

Decompress an image before writing it:
`xz -dc daemonarchy-1.5.0-amd64.iso.xz | dd of=/dev/<usb-device> bs=1M`.

The base is FreeBSD 16.0-CURRENT, OSVERSION `1600029`, built from daemonarchy-src
`303b364`; the ports are daemonarchy-ports `e84b4c4c`. The installer commit is
`ea0432a0`. The signed application feeds are `packages-16-amd64-1.5.0-r2` and
`packages-16-aarch64-1.5.0-r2`; the optional source and ports checkouts are
`checkouts-16-amd64-1.5.0-r2` and `checkouts-16-aarch64-1.5.0-r3`.

## What changes

- **Windows programs and Steam in the Apps menu (amd64).** Two Apps menu entries,
  Steam (the Windows client, run under Wine) and Windows Programs. They are virtual apps
  like Cudalab: nothing of Wine's or Valve's is on the image. The first launch opens a
  window that installs `wine-devel` and its helpers from the system's repositories (one sudo
  prompt), checks the NVIDIA, Vulkan and Xwayland stack and warns about what is missing, creates
  a 64-bit Wine prefix with Wine Mono and DXVK (pinned, sha256-checked downloads from their
  authors) and, for Steam, downloads Valve's own installer over HTTPS and runs it. `install` and
  `run` do the same for any Windows program you supply, logging to a file. The recipe for Mono and
  DXVK was contributed by Sam Sheridan, from his experience running a .NET and DirectX 11 game
  launcher on FreeBSD. Design, licences, source offer
  and limits are in [windows-apps.md](windows-apps.md). **Verified:** on the build VM the
  real first run created the prefix, ran Valve's installer, and Steam updated itself and
  stayed running (headless, no GPU). **Not verified:** a Windows game, or Steam's window,
  on the MSI Raider 18 HX (NVIDIA OpenGL and Vulkan under Wine, sound, the first-run window
  on a real session).
- **Graphical package manager (GUI-001), partly.** `daemonarchy-pkg`, a GTK 4 window over
  the installer's own planner and parallel fetch, with a plan before every change, signed
  repository display and an offer to remove unused dependencies, is in the repository and
  packaged as `ports-mgmt/daemonarchy-pkg`. It has no real-desktop evidence in this release. OctoPkg remains the
  fallback manager until the new one has real-desktop evidence; see
  [gui-package-manager.md](gui-package-manager.md).
- **Faster login on the MSI Raider 18 HX.** `x11-toolkits/aquamarine`
  ([daemonarchy-ports #44](https://github.com/jordanhubbard/daemonarchy-ports/pull/44), port revision 2)
  force-probes display connectors only on hotplug and otherwise uses the kernel's cached status; the
  `nvidia-drm` connectors are probed as before. The cause was i915's DisplayPort detect on an unplugged port,
  waited out twice by Aquamarine (about 0.75 s each). **Measured:** on one MSI Raider 18 HX, login to the
  desktop shell 2.95 s to 1.32 s warm (about 1.6 s) with the first version of the patch; the shipped version
  was run once. **Not tested:** hotplug on Intel- and NVIDIA-wired ports, session resume, lid and VT switch.
  It is an application package: `pkg upgrade` delivers it.
- **MacBookPro16,1 Wi-Fi: a stall after association.** The BCM4364 driver ignored a
  firmware link-down after the handshake, so the interface stayed `associated` while no
  traffic moved. The driver (`if_brcmfmac-kmod`) now honours it
  ([daemonarchy-ports #37](https://github.com/jordanhubbard/daemonarchy-ports/pull/37)).
  It is a kernel-bound package on the ISO, so this release also carries a rebuilt module
  and a re-signed Secure Boot module inventory. **Evidence is fault injection only:** a
  synthetic link-down after the key was installed was honoured and recovered in 5 of 5
  tries on the MacBook, with no scan stall and no flapping. The real firmware-side loss
  was not reproduced, and a long physical retest was not done.
- **Sandboxed Lua installer extensions (EXT-002).** The installer's visual SDK (API 1.5) runs
  extensions in a sandbox, with a first fish-tank extension; built and tested on a build host,
  not yet exercised on a physical machine.
- **One signing session per release (SIGN-001, option A).** The signed inputs were frozen
  before signing and signed in the operator's key windows (the process is recorded in
  [mastering-1.5.0.md](mastering-1.5.0.md)). No key is on a build machine and none was
  copied into a VM or an artifact; the command count and wall-clock time are in the release record.
- **arm64 render nodes (QEMU evidence only; whether the aarch64 feed carries the package was not re-checked here).** `graphics/drm-612-kmod` builds
  the VirtIO GPU stack on aarch64 with one deliberate difference from upstream drm-kmod:
  an aarch64-only patch lets a render-node client create, map and destroy dumb buffers,
  which Mesa's software path needs and upstream refuses. It cannot become DRM master or
  set a mode, and it is not applied on amd64.
  [daemonarchy-ports #36](https://github.com/jordanhubbard/daemonarchy-ports/pull/36)
  holds the reasoning. Evidence is a QEMU guest reaching the SDDM greeter in software.
- **Testing.** The QEMU harness gained an emulated sound device on aarch64 with a check.

## What is not done, and why

None of these is claimed done by 1.5.0. They are carried in the
[1.5.0 plan](roadmap/release-1.5.0.md).

| Item | Why it is not in this release |
| --- | --- |
| BUILD-001, COMP-001, PERF-001, PERF-002, DEV-001 | Moved to [1.5.1](roadmap/release-1.5.1.md): they need the Literate AI framework to execute native components, and no framework 1.4.0 exists. No build-speed gain is claimed. |
| ADOPT-002, SRC-001, RELEASE-001 (native halves) | Only the delivered parts are in 1.5.0 (handler audit and binding records, the controller and capture work, the 1.4.x release gate and tooling). The native retained execution and release enforcement are planned as ADOPT-003, SRC-002 and RELEASE-002 for 1.5.1. |
| NVIDIA RTX Spark laptop (aarch64) | Tested, not yet working; support is deferred and the kernel fix is not in this release ([note](application-note-rtx-spark.md)). |
| DEBUG-003 | Foundations only. Bidirectional loader, mountroot and panic debugging needs boot-chain research and hardware. |
| HW-004 | T2 Touch ID is not in the image; it needs a Mac with enrolled fingers. |
| GUI-001 (complete) | The window is merged and packaged but has no evidence from a real desktop install, update and remove. |
| Wi-Fi 2.4 GHz channel-1 handshake | A candidate on the MacBook (AP `70:a7:41:81:16:e0` never completed the 4-way handshake), not investigated. |
| Windows game and Steam on the MSI | Needs the operator's hardware; see above. |
| Login speed | The Aquamarine change removes about 1.6 s on one MSI Raider 18 HX; hotplug, resume, lid and VT switch are untested, and a separate first-login delay is still under investigation. |

## aarch64 image: community validation

The aarch64 image is still released so that people with arm64 hardware can try it and tell
us what happens. In QEMU with an e1000e network card the final image installs (all 919 archives, about 20 minutes) and boots under UEFI, and the signed-repository, feed-URL and no-FreeBSD-repository checks pass. **Known issue:** with QEMU's default virtio-net card the install stalls during the package fetch: about a minute in, the guest stops servicing receive on vtnet0, so every lookup and download then times out; bringing the interface down and up revives it. Use `-device e1000e` until this is fixed. The automated desktop check first timed out on the e1000e run because the harness's QEMU `virt` guest had no keyboard to type the SDDM password with; with a USB keyboard added and nothing else changed it passed (graphical login, input, the Epiphany browser and the package manager). Nothing beyond QEMU boot and install is
claimed. The one physical aarch64 machine tried, the NVIDIA RTX Spark laptop, does not work yet
(support is deferred); sound, Wi-Fi, upgrade and the live desktop on real hardware were not run. The default browser is Epiphany. See
[aarch64.md](aarch64.md) for what was and was not verified and how to report results.

## Hardware status and limits

- **No Wi-Fi or Hyprland guarantees.** Wi-Fi depends on the chipset and firmware, and
  the desktop depends on the GPU driver. Nothing in this release promises either on
  any particular machine.
- Physical runs of the final amd64 image on the MSI Raider 18 HX and the MacBookPro16,1 were not made before publication; the hardware statements below describe earlier builds.
- **MSI Raider 18 HX and MacBookPro16,1.** The limits in the
  [1.4.0 notes](release-1.4.0.md#hardware-status-and-limits) stand: polling-mode MSI
  touchpad, only Arrow Lake-S I2C controller 0 recognised, no ARL004 VMD interrupt
  workaround, no MacBook sound, CUDA Unified Memory unsupported.
- **Not done in 1.5.0.** The exact-image network matrix, image-based upgrade and rollback,
  and the ten-times-faster target measured on both physical machines were not completed.

## Upgrading

Application packages update with `pkg upgrade` from the signed feed. The kernel-bound set
(the Wi-Fi driver module and the Secure Boot module inventory) is part of the image and
changes with a new image, not with a package update; upgrading an installed system through
the image has not been tested and is not supported.
