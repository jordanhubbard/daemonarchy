# Daemonarchy 1.4.2 release notes

<!-- Template for the draft release pull request (scripts/prepare-release.py copies it to
docs/release-1.4.2.md). Written from what is merged on main when the template was made.
Before the release the owner re-checks every claim below against main and the evidence,
removes what did not ship and adds what did. The upper-case words between pairs of at-signs
are filled by scripts/fill-release.py (GUI001_EVIDENCE is given with --set). -->

Daemonarchy 1.4.2 is the release after 1.4.1. It adds Windows programs and Steam to the
Apps menu on amd64, the first part of a graphical package manager, and a fix for a
Wi-Fi stall on the MacBookPro16,1. Published @@PUBLISHED_DATE@@. The
[GitHub release](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.4.2)
is the authority for the final images, asset hashes and publication state.

## What you download

- `daemonarchy-1.4.2-amd64.iso.xz` (@@AMD64_ISO_BYTES@@ bytes, SHA-256
  `@@AMD64_ISO_SHA256@@`), the x86-64 image for BIOS or UEFI.
- `daemonarchy-1.4.2-aarch64.iso.xz` (@@AARCH64_ISO_BYTES@@ bytes, SHA-256
  `@@AARCH64_ISO_SHA256@@`), the arm64 image, UEFI only. It is still a
  community-validation image: read [the aarch64 section](#aarch64-image-community-validation).
- A `.sha256` file for each image, which covers the compressed file you download.
- The signed Secure Boot bundle `daemonarchy-1.4.2-boot.txz` with its detached `.sig`,
  and the public certificate in PEM and DER form. The bundle is the amd64 Secure Boot
  bundle; aarch64 has none.

Decompress an image before writing it:
`xz -dc daemonarchy-1.4.2-amd64.iso.xz | dd of=/dev/<usb-device> bs=1M`.

The base is FreeBSD 16.0-CURRENT, OSVERSION `1600029`, built from daemonarchy-src
`303b364`; the ports are daemonarchy-ports `@@PORTS_SHORT@@`. The installer commit is
`@@INSTALLER_SHORT@@`. The signed application feeds are `@@PACKAGES_AMD64_FEED@@` and
`@@PACKAGES_AARCH64_FEED@@`; the optional source and ports checkouts are
`@@CHECKOUTS_AMD64_FEED@@` and `@@CHECKOUTS_AARCH64_FEED@@`.

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
  packaged as `ports-mgmt/daemonarchy-pkg`. @@GUI001_EVIDENCE@@ OctoPkg remains the
  fallback manager until the new one has real-desktop evidence; see
  [gui-package-manager.md](gui-package-manager.md).
- **MacBookPro16,1 Wi-Fi: a stall after association.** The BCM4364 driver ignored a
  firmware link-down after the handshake, so the interface stayed `associated` while no
  traffic moved. The driver (`if_brcmfmac-kmod`) now honours it
  ([daemonarchy-ports #37](https://github.com/jordanhubbard/daemonarchy-ports/pull/37)).
  It is a kernel-bound package on the ISO, so this release also carries a rebuilt module
  and a re-signed Secure Boot module inventory. **Evidence is fault injection only:** a
  synthetic link-down after the key was installed was honoured and recovered in 5 of 5
  tries on the MacBook, with no scan stall and no flapping. The real firmware-side loss
  was not reproduced, and a long physical retest was not done.
- **arm64 render nodes (include only if it shipped).** `graphics/drm-612-kmod` now builds
  the VirtIO GPU stack on aarch64 with one deliberate difference from upstream drm-kmod:
  an aarch64-only patch lets a render-node client create, map and destroy dumb buffers,
  which Mesa's software path needs and upstream refuses. It cannot become DRM master or
  set a mode, and it is not applied on amd64.
  [daemonarchy-ports #36](https://github.com/jordanhubbard/daemonarchy-ports/pull/36)
  holds the reasoning. Evidence is a QEMU guest reaching the SDDM greeter in software.
- **Testing.** The QEMU harness gained an emulated sound device on aarch64 with a check.

## What is not done, and why

None of these is claimed done by 1.4.2. They are carried in the
[1.4.2 plan](roadmap/release-1.4.2.md).

| Item | Why it is not in this release |
| --- | --- |
| ADOPT-002, RELEASE-001, COMP-001, PERF-002, DEV-001 | Blocked on the external Literate AI framework, which this repository cannot execute or fake. |
| SRC-001 | Partly done: the hand pipeline builds the base and the kernel. Owned, repeatable source builds are not finished. |
| DEBUG-003 | Foundations only. Bidirectional loader, mountroot and panic debugging needs boot-chain research and hardware. |
| HW-004 | T2 Touch ID is not in the image; it needs a Mac with enrolled fingers. |
| GUI-001 (complete) | The window is merged and packaged but has no evidence from a real desktop install, update and remove. |
| Wi-Fi 2.4 GHz channel-1 handshake | A candidate on the MacBook (AP `70:a7:41:81:16:e0` never completed the 4-way handshake), not investigated. |
| Windows game and Steam on the MSI | Needs the operator's hardware; see above. |
| Slow first login | The display-driver sleeps of about 1.6 seconds and a first-login delay are under investigation. |

## aarch64 image: community validation

The aarch64 image is still released so that people with arm64 hardware can try it and tell
us what happens. @@AARCH64_FINAL_QEMU_STATUS@@ Nothing beyond QEMU boot and install is
claimed: no physical aarch64 machine was tested, and sound, Wi-Fi, upgrade and the live
desktop on real hardware were not run. The default browser is Epiphany. See
[aarch64.md](aarch64.md) for what was and was not verified and how to report results.

## Hardware status and limits

- **No Wi-Fi or Hyprland guarantees.** Wi-Fi depends on the chipset and firmware, and
  the desktop depends on the GPU driver. Nothing in this release promises either on
  any particular machine.
- @@PHYSICAL_STATUS@@
- **MSI Raider 18 HX and MacBookPro16,1.** The limits in the
  [1.4.0 notes](release-1.4.0.md#hardware-status-and-limits) stand: polling-mode MSI
  touchpad, only Arrow Lake-S I2C controller 0 recognised, no ARL004 VMD interrupt
  workaround, no MacBook sound, CUDA Unified Memory unsupported.
- **Not done in 1.4.2.** The exact-image network matrix, image-based upgrade and rollback,
  and the ten-times-faster target measured on both physical machines were not completed.

## Upgrading

Application packages update with `pkg upgrade` from the signed feed. The kernel-bound set
(the Wi-Fi driver module and the Secure Boot module inventory) is part of the image and
changes with a new image, not with a package update; upgrading an installed system through
the image has not been tested and is not supported.
