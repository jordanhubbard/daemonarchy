# Changelog

This history covers the installer repository from its first commit and all GitHub
release records. Dates below are GitHub publication dates in UTC; a date embedded
in a snapshot tag is the image's identifier and can differ from its publication
date. Entries describe the behavior and evidence recorded for that release, not
support guarantees for every machine. Related desktop and compatibility changes
are included where the corresponding release notes identify them.

**Current publication state:** 1.1.1 is the latest published stable installer. The superseded 1.1.0 and preview.13 drafts and the
previously published 1.1.0-rc.1 release assets were removed at the operator's
request on October 18 to avoid download confusion and reclaim storage.
Their historical entries and source tags are preserved. “1.1-release” in testing discussions refers to the 1.1
work; it is not a separate published tag in this repository. The proposed name
1.1-rc2 was replaced by 1.1.1 before publication.

## 1.1.1 — 2026-10-18

Status: published with operator-authorized deferral of further physical-hardware
and final installation-matrix evidence. The native ISO audit and release asset
integrity checks passed; outstanding qualification is not claimed as passing. The tag is
`daemonarchy-1.1.1`, with a versioned application feed
`packages-16-amd64-1.1.1`. See [the current evidence](docs/testing-1.1.1.md).

### Changed

- Refresh the FreeBSD source pin to
  `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` (`1600028`) and the ports integration
  to `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`, based on upstream ports
  `b1306594c4a601f98a3d28cbf6fc0569e218245f`. Kernel modules are rebuilt against
  the selected source. This CURRENT revision changes the driver ABI; packages
  alone cannot migrate an older kernel and its modules.
- Keep the selected source's existing Secure Boot policy patches and project
  enrollment certificate. Network debugging beyond the upstream GENERIC
  facilities is deferred to 1.2; this release does not introduce a source fork
  for loader or early-kernel network debugging.
- Select signed, versioned application and optional-checkout repositories rather
  than changing the existing unversioned stable application feed. Publish the
  pinned 1.1.1 checkout repository separately from the installer image.
- Accept exact shallow Git source identities during image construction while
  retaining checks for the selected revision and clean source state.
- Preserve dependency resolution from official repositories when adopting rebuilt
  candidate packages. Select already installed public-feed packages, force their
  candidate payloads into use, and preserve unrelated private-package selections.
- Reject application-feed adoption across incompatible base/driver ABI versions.
  Verify installed package integrity before an installation is marked complete.

### Fixed

- Create the original ZFS boot environment with `canmount=noauto` and explicitly
  mount it for installation. An inactive original root must not automatically
  cover a selected replacement environment or hide its `/dev` during boot.
- Rescue option 2 switches between pairing and unpairing a remote debugging
  agent. Unpairing disconnects active access, clears stale state, and permits a
  fresh pairing session.
- Draw the rescue menu after late boot output settles, without requiring the
  user to press Return to reveal it.
- Leave graphics unready when a requested DRM driver fails device attachment,
  even if module loading succeeds and DRM character nodes survive the failure.
  Check attached active devices and card/render nodes before permitting SDDM.
  These prerequisites do not certify compositor rendering.

### Debugging observability

- Start a bounded, private diagnostic collector after console-approved SSH
  authentication. Retain kernel-output deltas, recent system messages, process
  names, storage/memory statistics and named sensor probes; avoid broad sysctl
  enumeration and never consume the operator's console input.
- Add `daemonarchy-debug snapshot` and `daemonarchy-debug observe`. Restart a
  dead collector on a later approved connection and stop generation-bound
  collection when the pairing is revoked.
- Optionally capture passive devd broadcast events when Python and the event
  socket are available. This does not replace devd or enable network kernel
  debugging; unavailable events are recorded explicitly.
- Add `scripts/capture-remote-debug.py` to retain a finite SSH diagnostic stream
  on the controller with private, bounded log parts, periodic synchronization,
  idle notices and a final disconnect record. A reset can still occur before
  the target transmits its last output; this is not a guaranteed panic capture.

### Validation and limits

- Refreshed native base and policy-kernel builds and isolated normal, enforced,
  unsigned-loader and altered-kernel boot checks are recorded. These component
  checks do not substitute for the final ISO installation matrix.
- All 749 source-package builds, 24 isolated native port checks and the final
  combined repository pass completed successfully. Final-image tests, upgrade
  evidence and artifact publication remain tracked in the evidence document.
- The operator authorized publication without further physical-hardware evidence.
  Existing hardware failures and untested behavior remain limitations, including
  the MacBook Pro's repeated resets during package installation and its missing
  desktop. Authorization is not a passing hardware test.
- Record known Python IMAP/POP command-injection and setuptools path-traversal
  dependency advisories in the qualification record; build QA and signatures
  do not establish a vulnerability-free package set.

## 1.1.0 — Unpublished draft, removed

Former GitHub draft: `daemonarchy-1.1.0`.
The draft was created on 2026-10-17 and describes reusing the tested rc.1
artifacts. Commit `f69ac50` records that intended release, but neither a commit
message nor draft release notes establish publication. The draft and its assets were removed on October 18;
1.1.1 supersedes that unpublished promotion.

## 1.1.0-rc.1 — 2026-10-16

Status: published October 16; release record and assets removed October 18
at the operator's request. The source tag and this change history are retained.

### Added

- BIOS installation alongside UEFI, with plain ZFS and GELI/ZFS installation
  tests; selected GPT partition and free-space installation in addition to
  whole-disk installation.
- Optional depth-1 `/usr/ports` and `/usr/src` checkouts from signed, pinned
  download repositories, with ownership and revision checks after installation.
- Console-approved remote SSH debugging, authenticated session/activity feedback,
  explicit completion, and installed rescue/debugging tools.
- Manual-enrollment Secure Boot using the project's production certificate,
  signed loader and matching boot/module manifests. Retained boot environments
  support explicit update validation, activation and rollback.
- Native FreeBSD desktop defaults, Chromium, OctoPkg and the `daemonarchy`
  command; QEMU VirtIO/VirGL support for a real Hyprland desktop.
- HiDPI console handling, installer connectivity diagnostics and clock controls,
  persistent authoring caches, and matching 32-bit compatibility libraries.

### Changed

- Use the October 12 FreeBSD CURRENT snapshot,
  `3ceb5f150bc121f5e6a3e0cc8b289279338405a1` (`1600027`), with matching external
  drivers. Keep application-package updates distinct from base/kernel updates.
- Remove unsupported Linux/Arch-only menu actions. CUDA toolkit/menu entry
  installation remains disabled in the final candidate; an earlier development
  preview's Cudalab behavior is not a final-release capability claim.
- Add native enterprise Wi-Fi profile handling and an A2DP/SBC Bluetooth audio
  path while retaining explicit real-device qualification gaps.

### Recorded evidence and limits

- Exact candidate installation, reboot and graphical application checks passed
  in four QEMU configurations: enforced UEFI and BIOS, each plain and encrypted.
  The UEFI plain case also checked both optional working checkouts.
- Signed boot maintenance passed update, altered-candidate rejection, rollback
  and return; application-package upgrade and rollback from 1.0.1 passed.
- ASRock X570/RTX 4090 recovery failure, MSI Raider early resets and Apple T2
  recovery problems remained unresolved. Enterprise Wi-Fi authentication,
  Bluetooth headset/HID regressions and refreshed bhyve qualification remained
  open. The release notes retain the detailed scope of each result.

## 1.1.0-preview.13 — Unpublished draft, removed

Former GitHub draft: `daemonarchy-1.1.0-preview.13`, created 2026-10-16 and
removed with its assets on October 18. This hardware-testing draft selected the October 12 snapshot, matching drivers,
Chromium/OctoPkg, lib32 and signed downloadable checkouts. Its notes explicitly
left VM graphics, production Secure Boot and physical acceptance incomplete at
that point. It is not an additional published installer release.

## 1.1.0-preview.1 — 2026-10-15

Status: published source prerelease; **no ISO**.
[Release notes](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.1.0-preview.1).

- Tag installer source at `d276a75` while keeping 1.0.1 as the installable image.
- Introduce development work for selected-partition/free-space installs, BIOS
  boot code, optional shallow checkouts and console-approved remote debugging.
- Improve HiDPI consoles and Ethernet-only installation; stage GPU-specific
  Vulkan and NVIDIA/Linuxulator/Cudalab integration.
- The notes required matching `linux-nvidia-libs` before image construction and
  explicitly retained open acceptance items. Later 1.1 policy changes supersede
  this preview's optional CUDA/toolkit behavior.

## 1.0.1 — 2026-10-10

Status: published stable release.
[Release notes and assets](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.0.1).

- Move Daemonarchy artwork, SDDM theme, FreeBSD menu and tools into
  `jordanhubbard/daemonarchy-desktop`.
- Move `freebsdize`, compatibility tools, FreeBSD command overrides and session
  units into `jordanhubbard/omarchy-freebsd`. Ports fetch those releases instead
  of embedding their source files.
- Extend the development checkout tool and hacking guide to both repositories.
  The patched Quickshell change is now in upstream FreeBSD ports.
- Preserve desktop behavior from 1.0.0: Omarchy 4.0.4 on the October 5 FreeBSD
  CURRENT snapshot. Both ports passed `poudriere testport`; file comparisons
  found only license-source and build-time icon differences.
- The exact ISO passed unattended installation and all 20 recorded installed
  system checks. UEFI/Secure Boot off and whole-disk restrictions remained;
  graphical VM login, NVIDIA, enterprise Wi-Fi and Bluetooth audio remained
  outside the release's qualified behavior.

## 1.0.0 — 2026-10-09

Status: first published stable release using Daemonarchy's own semantic version.
[Release notes and assets](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.0.0).

- Move to the October 5 FreeBSD CURRENT snapshot used by the package builders,
  with Omarchy 4.0.4; report the Daemonarchy version in the installer and installed
  version file.
- Restore package-recorded owners after installation, repairing D-Bus helpers,
  desktop authorization and printing permissions.
- Rebuild target-system linker hints, GSettings schemas and GIO caches so GTK
  applications start correctly.
- Integrate native Wi-Fi/Bluetooth panel behavior, session audio and authorization
  startup; fix the Boot Environments menu and reduce idle panel polling.
- Add the beginner's installation guide and screenshots.
- The exact ISO passed all 20 recorded installed-system checks. Bare-metal
  evidence covered cold-boot sound, polkit, Bluetooth firmware and Wi-Fi network
  listing; Wi-Fi association and actual Bluetooth device pairing remained untested.

## 16.0-20261007 — 2026-10-07

Status: published snapshot release.
[Release notes and assets](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-16.0-20261007).

- Add the signed online `packages-16-amd64` repository so installed systems can
  receive Daemonarchy application updates between image releases.
- Retain the image's package repository as `Daemonarchy-ISO`, including driver
  modules tied to its kernel.
- Record migration from an older installation to the signed feed on bare metal;
  the exact ISO passed all 18 recorded installed-system checks.

## 16.0-20261002 — 2026-10-02

Status: published snapshot release.
[Release notes and assets](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-16.0-20261002).

- Add System > FreeBSD tools for boot environments, home snapshots/restoration,
  jails, bhyve virtual machines, DTrace and source-checkout development.
- Adapt AI-agent launchers to install their tools through FreeBSD packages or
  the Linux compatibility layer on first use.
- Repair sudo-rule locations, link `/bin/bash` to packaged Bash, remove a broken
  duplicate FreeBSD repository entry and fix the install progress counter.
- Add the QEMU installation harness and hacking guide; retain installed-system
  checks and bare-metal menu observations without claiming graphical VM login.

## 16.0-20261001-2 — 2026-10-02

Status: published corrective snapshot; the tag retains its October 1 identifier.
[Release notes and assets](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-16.0-20261001-2).

- Fix first login by configuring SDDM's user and full Omarchy session path; add
  the new account to `audio`.
- Always show network selection with Ethernet/Wi-Fi adapter states, DHCP,
  static addressing and hidden-network choices.
- Offer optional SSH, enable Avahi hostname discovery and preserve the chosen
  network configuration on the installed system.
- Add the install dashboard and retry failed package downloads. The package
  counter display bug was retained as a known issue for the next snapshot.
- The exact image passed unattended installation, reboot and recorded account,
  service and SDDM configuration checks. These were not graphical VM tests.

## 16.0-20261001 — 2026-10-01

Status: first published installer snapshot, subsequently superseded.
[Release notes and assets](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-16.0-20261001).

- Provide a UEFI amd64 live installer for Omarchy on FreeBSD 16.0-CURRENT, with
  keyboard/network/account configuration, whole-disk ZFS and optional GELI.
- Install from official packages plus bundled Omarchy and matching driver
  packages; add a bhyve unattended-install harness and patched Quickshell.
- **Known defects:** a fresh installed SDDM rejected passwords and audio group
  membership was missing. The next snapshot fixes these defects.
- Initial bhyve installation/boot checks and a separate bare-metal desktop
  observation did not qualify this exact ISO on physical hardware. BIOS,
  Secure Boot, NVIDIA and graphical VM login were not supported by this image.

## Initial development — 2026-09-30

Commit [`80879fa`](https://github.com/jordanhubbard/daemonarchy/commit/80879fa42a6012ac91b2946618128c9471eb91e3)
created the proof-of-concept installer, configurator, live overlay and bhyve
harness. Follow-up commits bundled patched Quickshell, enabled default NAT in
bhyve tests and rejected account names reserved by FreeBSD packages. There was
no separately published September 30 installer release.

## Supporting repository releases

These GitHub releases carry signed package/catalogue or optional-checkout data;
they are not additional installer versions. A published feed does not establish
that its corresponding installer has been released. Feed tags may be retained
while their assets are updated; use the catalogue and payload hashes for exact
artifact provenance.

| Published (UTC) | Tag | Purpose |
| --- | --- | --- |
| 2026-10-18 | [`packages-16-amd64-1.1.1`](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64-1.1.1) | 510 signed application/dependency packages for OSVERSION `1600028`; all 515 asset names, sizes and digests verified, with native public-catalogue/root-download and wrong-key checks. This feed does not upgrade an older base/kernel. |
| 2026-10-17 | [`checkouts-16-bdcfeac3e1cb-f7d7ee897405-v1`](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-bdcfeac3e1cb-f7d7ee897405-v1) | 1.1.1 source `bdcfeac3e1cb` (`1600028`) and ports `f7d7ee897405`; signed-catalogue, install, materialization, integrity and wrong-key checks recorded before publication. |
| 2026-10-16 | [`packages-16-amd64-1.1.0-candidate`](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64-1.1.0-candidate) | Versioned signed application feed for 1.1 candidate provenance. |
| 2026-10-16 | [`checkouts-16-3ceb5f150bc1-08a6370a019a-v1`](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-3ceb5f150bc1-08a6370a019a-v1) | October 12 source plus the combined final 1.1 ports baseline. |
| 2026-10-16 | [`checkouts-16-3ceb5f150bc1-28d8f145fbec-v1`](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-3ceb5f150bc1-28d8f145fbec-v1) | October 12 source plus an earlier preview ports baseline. |
| 2026-10-13 | [`checkouts-16-a52c50b4b7c2-6fb491f4c73a-v1`](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-a52c50b4b7c2-6fb491f4c73a-v1) | October 5 source plus the initial 1.1 development ports baseline. |
| 2026-10-07 | [`packages-16-amd64`](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64) | Original signed application update repository; distinct from the versioned 1.1.1 feed. |

## Maintaining this history

Add concrete user-visible changes under the next unreleased version. At release,
record the actual publication date and exact tag, then replace pending statements
with links to completed evidence or explicit limitations. Keep draft, prerelease,
installer and supporting-feed states distinct. Inspect both the installer Git
history and the pinned desktop/compatibility/ports inputs; a version bump alone
is not a behavior change. Never convert an operator's publication authorization
or a component test into a claim that the final image or physical hardware passed.
