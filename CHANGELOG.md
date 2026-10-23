# Changelog

## Unreleased hardware debugging

- Preserve approved installed-system debugging keys, server identity and private
  state across reboot. Resume the existing session without Unpair or fresh
  confirmation; retain explicit revocation and unknown-key refusal. Keep
  retrying after slow network bring-up while the approved grant remains active.
- On MacBookPro16,1, correct the offset EFI framebuffer reservation in the
  Navi14 driver and skip stalled LED output reports for the built-in T2 keyboard.
  The refreshed graphics package and one-boot quirked kernel reached a visible
  Hyprland desktop: the operator entered a password, and the pointer worked
  after initial lag. These fixes are in draft source/ports contributions, not
  yet in a published image or a fully qualified normal-boot kernel.
- Record the MacBook Pro 16 fatal NVMe event reproduced during installer package
  extraction. Storage correction, BCM4364 Wi-Fi driver and firmware integration,
  sustained input acceptance, and full physical acceptance remain open.
- Identify the MacBook's BCM4364 revision 4, TCM geometry and B3 firmware path
  on physical hardware. A private FreeBSD-native diagnostic module reaches
  firmware protocol 7, attaches to net80211 and repeatedly scans nearby access
  points using the candidate `bali-HRPN-u` board data, Apple seed footer and
  matching CLM and TxCap blobs. The operator joined a WPA2 network from the
  desktop panel; the radio received DHCP address 10.11.101.63 and reached its
  gateway. The installer now retains a kernel-matched preview module and staged
  firmware on the installed target. Fresh-image boot, reconnect, maintainable
  driver integration and redistributable firmware acquisition remain open.
- Prepare a private MacBook preview ISO with the MacBook-tested Radeon package,
  updated Wi-Fi panel, keyboard LED tunable and a WPA completion wait before
  installer DHCP. The offline repository contains the exact refreshed packages;
  the image is for hardware testing, not public distribution.


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

## Unreleased

- Installer: replace elapsed-time progress estimates with measured milestones,
  archive and package observations; add bars, spectrum and scope views, plain
  output, reduced motion and terminal resize handling.

- Add bounded parallel authenticated package acquisition with separate native pkg
  databases, verified-byte progress and fresh retry. Preserve serial inputs.
  Native regression covers an eight-package historical subset; final release
  inputs, installation scheduling and installer/GUI integration remain pending.

- Preserve owned disposable-QEMU cleanup through repeated termination signals.
  Revoke inspection, finish the existing bounded shutdown and retain terminal
  evidence before returning an interrupted status. Controller regression checks
  cover the reproduced orphan-child defect; actual VM renewal remains separate.

- Authenticate frozen package catalogues with a pinned public key and verify
  fetched archives through native pkg, retaining exact payload inventories and
  independent SHA-256 hashes. Support read-only offline replay and reject
  diagnostics even when a native command exits zero. Installation and final
  release admission remain separate requirements.

- Compare native pkg dry-run proposals and imported package/dependency records
  with pinned selection graphs in fresh private databases. Keep metadata and
  partial failures, enforce internal process deadlines and reject mismatched
  plans. This development check does not install or authorize packages.

- Add read-only package dependency graphs from pinned repository catalogues,
  with exact archive identities, per-selection closure and space estimates,
  repository conflict and ABI/OSVERSION refusal checks. Native solver acceptance,
  transaction execution and safe parallel installation remain unfinished.

- Build tooling: select original source authority in place through a reviewed
  metadata-only plan and qualified combined Standard distribution. Preserve
  original source layout and receipt requirements; native execution profiles,
  current receipts and image qualification remain unfinished.

- Select an exact EFI/Lua pair for a loader-only live test image, verify both
  identities before image assembly and reject conflicting Secure Boot bundles.
  Controller/native staging controls pass; no new ISO or boot result is claimed.

- Allocate a fresh private staging directory for each installer ISO build, retaining
  preceding and failed attempts. This prepares parallel test-image authoring;
  it does not publish or qualify a new ISO.
- Repair fastfetch's OS Age on FreeBSD: replace the GNU stat invocation with an
  explicit native stat/date calculation and report `Unknown` for unusable times.
  Verified on the installed 1.1.1 desktop; [ports PR #8](https://github.com/jordanhubbard/daemonarchy-ports/pull/8) carries the package fix.
- Fix ignored EFI handoff errors and shared-NIC IPv4 fragment loss in the source
  fork. Native sanitizer checks and actual UEFI fragmented NFS/TFTP regressions
  pass; physical firmware and continuous kernel debugging remain release work.

- Harden the source fork's UEFI console against invalid firmware mode/frame
  sizes and refuse native kernel handoff when the debug NIC did not quiesce.
  The actual driver passes native scripted failure checks with address/undefined
  behavior sanitizers and explicit RX allocation balance; physical firmware,
  alternate handoffs and release acceptance remain pending.

- Make wired UEFI loader debugging a release blocker and state FreeBSD-only
  product acceptance explicitly. The source fork now passes a native EFI build
  and initial real UEFI console tests, including remote show/set/boot, replay
  refusal, reconnect and local recovery without a peer or NIC. Physical
  firmware/NIC and remaining netboot/fault checks still block acceptance.

- Inspect source-built compiler/sysroot package provenance and dependencies:
  verify 524 pkgbase manifests and locate compiler resources, C++ headers/runtime,
  startup objects and linker in a six-package candidate closure. Record both
  symbolic and hard-link custody requirements; SDK admission remains pending.

- Complete the unprivileged source world, kernel, package and installer-set build.
  All 537 recorded artifact hashes, phase logs and installer-manifest references
  independently verify. The source archive matches all 114,710 Git members and
  138 symlinks with root ownership and matching modes/bytes. Payload acceptance,
  SDK admission, ISO creation and boot testing remain open.

- Qualify the `6e370033` development wheel and its isolated FreeBSD installation,
  including 37 verified distributions, signing and SQLite. All 24 original
  source tests and 11 independent acceptance cases pass. Cleanup succeeds and a
  retained local-runtime receipt is admitted, with all 34 records verified.
  Canonical SDK, pkg and release qualification remain open.

- Reconcile the preceding traversal candidate's retained evidence: full controller
  regression and its exact wheel pass. Native installed lifecycle qualification
  and the subsequent private-prefix repair retain separate pending states.

- Preserve the preceding `587ad3f1` native lifecycle failure: compilation and documentation
  pass, but two of 24 original cases cannot launch through the private allocation
  directory. Record 16 passing native source-level checks of the scoped access
  repair separately from the subsequent successful installed retained run.

- Record native input-custody checks for all 114,710 tracked source-fork paths,
  including modes and 138 symlinks. Keep this evidence separate from complete
  Component registration, dependency resolution and package admission.
  Track the 28 toolchain aliases through the separate native SDK admission work.

- Renew the framework development candidate to `587ad3f1` in an isolated native
  environment after full Python 3.11 and exact installed-wheel checks. Verify
  offline dependencies, installed bytes, signing and SQLite; native source
  lifecycle, SDK admission and physical cut-over remain pending.

- Document POSIX ACL readiness for disposable retained-build workers and record
  the start of an unprivileged, KVM-backed source SDK baseline. Completed SDK
  admission, packaging and performance qualification remain pending.

- Clarify the 1.2 wired-debugging roadmap: existing loader UDP networking and
  panic-only kernel NetGDB require separate loader control, kernel debugging and
  early-driver qualification across the firmware handoff.

- Add a finite QEMU worker supervisor and FreeBSD inspection relay. Bind fresh
  read-only inspections to an operator-selected plan and actual owned process,
  QMP state, disk and seed. Preserve console/session records and enforce request
  deadlines and shutdown cleanup. Twelve controller checks and actual FreeBSD
  boot/root-relay inspection pass. Actual supervisor interruption also powers off
  the guest cleanly and removes its inspection socket while retaining evidence.
  Native automatic expiry and installed lifecycle qualification remain open.

- Record eleven passing native framework source checks for local orchestration,
  secondary-account access and cleanup-bound receipt admission. A separate live
  QEMU allocation-owner probe verifies fresh inspection and lifetime revocation.
  Prepare the source harness to use reviewed test views and the existing secondary
  account. Installed qualification and the complete source lifecycle remain open.

- Add tested numeric secondary identities and FreeBSD descriptor ACL custody
  in framework PR #87. Record live allocated-guest scope and read-only-view
  probes, preserving pending full SDK, installed lifecycle and package admission.

- Verify all 24 original parser/utility cases in a disposable FreeBSD guest,
  including root and explicitly unprivileged cases, with no skips. Preserve the
  failed fixture-inheritance probe and exact ACL/account/payload restoration.
  Installed framework permission management and lifecycle admission remain open.

- Record the qualified controller wheel and verified dependency bootstrap,
  reviewed source rebind, disposable native guest and isolated ACL-capability
  checks. Native dependency production and verified installation now pass on the
  build worker and disposable guest, including real cryptographic operations.
  Native focused checks pass (29 passed, one optional skip); installed input
  verification has a median of 9.23 seconds versus 19.79 seconds in three warm
  samples. Whole-build performance, scoped grants and package acceptance remain
  pending.

- Retain the renewed native source lifecycle's supervised exit and original
  test result: 23 pass, one required privileged skip, correctly refused before
  acceptance. Record the separate input-verification performance experiment
  without claiming full build or release qualification.

- Add an isolated build-worker framework preview with the tested strict-SBOM
  optimization and corrected source-version/linker inputs. Retain the first
  native run's 23-pass/one-root-skip result without awarding acceptance.

- Document the five-owner original-source retained build prototype and observed
  native products, preserving explicit missing acceptance, package and whole-tree
  qualification. Link the exact reviewed source entry point and CI evidence.

- Install the exact candidate common CLI on both native roles and validate the
  reviewed source/ports projects and all five native locks. Retain the preceding
  CLI aliases and active workspace selection; executable native profiles and
  current lifecycle receipts remain unfinished.

- Reopen the native LZ4 probe package in private staging and pass five CLI/library
  checks against its payload, without installing it on the worker. Canonical
  package admission and VM installation/recovery remain open.

- Run the original parser/utility ATF inventory against native probe products:
  23 cases pass and the root-required deallocation case remains explicitly
  skipped. Privileged and independent acceptance remain open.

- Establish reviewed original ports authority and two FreeBSD/pkg locks in
  [ports PR #7](https://github.com/jordanhubbard/daemonarchy-ports/pull/7), using
  the complete installed Standard evidence policy. Original implementations
  remain in place; deployment, native execution and per-unit qualification
  remain open.

- Add deployment and inspection for a parallel native workspace with independent
  pinned source/ports checkouts, upstream remotes and isolated output roots.
  Eight real-Git checks cover preserved local/failed state, independent object
  storage, upstream refresh and selection drift and pass on both FreeBSD roles.
  Both deployed workspaces use separate ZFS storage. Diagnostic make probes build
  the original parser/utility and build/test/package the LZ4 port. Installed
  Component execution, complete provenance and measured executor selection remain
  open.

- Prepare exact original-suite reporting and independent utility file-effect
  expectations in the source fork: 24 original cases and eleven verifier cases.
  Framework build-output command lookup passes its full local regression
  (1,809 passes, 42 skips); native/installed execution and actual source-unit
  qualification remain open in [framework PR #81](https://github.com/jordanhubbard/literate-ai/pull/81).

- Select explicit FreeBSD and pinned native-pkg policies for the initial source
  units. The framework candidate passes 1,805 local checks with 42 skips;
  native/installed renewal and original unit compilation remain open.

- Register and lock the first original source header/parser/utility contracts
  without moving the FreeBSD tree. Record explicit original authority and
  separate three authored units from zero admitted units or qualified packages.
  Native lifecycle and operator framework deployment remain open.

- Preserve exact original Kyua result states in retained test reports, including
  expected failures and root-required skips. Thirteen checks pass on FreeBSD,
  including actual Kyua/ATF fixtures. Complete original-unit compilation, tests
  and lifecycle admission remain open.

- Acquire the reviewed native compiler bootstrap seed with bounded byte, mode,
  link and linker-script custody. Ten refusal/capture checks pass on FreeBSD.
  The helper and documentation are available in the operator source checkout;
  SDK admission, original-source compilation and full Component lifecycle remain
  unqualified.

- Stream large filemon records without loading the whole record into memory;
  retain finite per-file and aggregate bounds, stable-file checks and immutable
  custody. Thirty tests pass on native FreeBSD, and the actual 39 MB source
  archive trace passes capture and hash verification. Preserve the full traced
  run as failed after its old collector limit; independently verify its 537
  artifacts and all eight release sets without claiming lifecycle acceptance.

- Establish the operator-development work item for conventional `/usr/src` and
  `/usr/ports` checkouts, isolated native outputs and a complete Literate AI
  incremental build/test/package/ISO/installation workflow. Rename the owned ports
  fork to `daemonarchy-ports`, preserving its branches and history. Full native
  Component lifecycle qualification remains open.

- Prepare optional native filemon/meta-mode tracing in the source controller,
  preserving source dependency files and retaining immutable phase observations.
  Seventeen controller checks pass locally and in controller CI; native tracing
  setup/execution and canonical action/package qualification remain pending.

- Preserve unqualified native directory references without treating dots inside
  source paths as machine contexts. Retain returned query output for diagnosis;
  unresolved references still refuse closure admission. Eleven portable checks
  pass and a native two-seed probe retains an unresolved legacy CSU reference.

- Add bounded native directory-dependency observation with explicit target/host
  contexts, shared Makefile inputs, dependency ordering and failure/cycle refusal.
  Ten portable checks pass; the native `bin/ls` observation resolves 19 directory
  nodes and 52 edges. Complete native action/Component/package admission remains open.

- Add pinned Git-tree discovery for complete source and ports input inventories,
  with nine refusal/identity tests and CI. Record 4,620 source/support candidates
  and 35,204 ports origins; native dependency resolution, canonical Component
  registration and per-unit pkg qualification remain open.
- Keep filemon meta-mode progress output quiet so crunchgen's structured make
  queries retain their original protocol. Preserve the failed full tracing
  attempt; all 27 controller/bootstrap checks pass on FreeBSD after the fix.

- Validate native filemon header-read capture, unchanged object reuse and
  changed-header invalidation with preserved trace snapshots. Audit the actual
  524-package pkgbase catalog and its 1,082 runtime dependency edges. Complete
  canonical compilation graphs and per-unit provenance remain open.

- Establish PERF-001 for measured native Component execution and faster ISO
  builds, permitting Bazel, Buck2 or another executor after correctness and
  end-to-end measurements. The recovered development build finished; no speedup is claimed.

- Add the owned FreeBSD source-build controller and GENERIC/diagnostic profiles
  in daemonarchy-src, with native pkgbase/installer-set preparation, isolated
  staging, resumable bounded phases and byte-verification records. Eleven
  controller checks pass locally, in CI and on FreeBSD; the first native baseline
  build finished after a retained set-phase failure and exact-plan resume. Its
  533 recorded artifacts and eight MANIFEST set hashes verify. Fix source/ports
  archive symlink handling and root ownership, and bind all MANIFEST-listed sets
  into artifact verification. The corrected full source archive matches all
  114,642 Git files; all 21 controller checks pass on FreeBSD. Package, boot and
  release qualification remain pending.
- Require the complete source and ports trees to be modeled as canonical Literate
  AI Components, including shared inputs, variants and selected native dependency
  closures. Full-tree Component registration and lifecycle acceptance are open
  work under COMP-001; two aggregate build wrappers do not satisfy this scope.

- Record the MSI startup video's last visible legacy-RTC warning and document a
  targeted one-boot RTC-disable comparison. The reset cause and workaround remain
  unconfirmed; no automatic boot setting changes.

- Adopt in-place Literate AI product goals, eight logical Component contracts,
  public integration boundaries, stable work IDs, documentation reachability and
  an acceptance inventory. Retain original source, native commands and published
  release identities. Native lifecycle execution and release enforcement remain
  separate, unqualified follow-up work; no current passing receipt is claimed.

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

- Add a [MacBook Pro application note](docs/application-note-macbookpro16-1.md)
  separating recognized Navi14 GPU hardware from failed initialization and
  documenting the unattached BCM4364 wireless controller and wired workaround.

- Refreshed native base and policy-kernel builds and isolated normal, enforced,
  unsigned-loader and altered-kernel boot checks are recorded. These component
  checks do not substitute for the final ISO installation matrix.
- All 749 source-package builds, 24 isolated native port checks and the final
  combined repository pass completed successfully. The final ISO passed BIOS and
  enforced UEFI boot plus its embedded boot-environment mount-policy fixture.
- The physical HP passed a coordinated base/kernel/package upgrade, rollback to
  its original base, return to 1.1.1, and AMD Wayland greeter rendering. The operator also confirmed that normal authenticated `jkh` login opens the
  desktop and that its applications work. All four preceding-image VM
  installation/desktop configurations passed, including actual Chromium and
  OctoPkg UI checks, matching boot/module profiles and optional source/ports
  checkouts in the UEFI plain case. A controller-only module-alias assertion was
  corrected and the affected installed system passed its actual profile/GUI
  recheck; the original failure remains recorded.
- All four disposable VMs also passed actual one-time clone boots and GUI checks
  after explicitly correcting their original root to `canmount=noauto`.
  The original root stayed inactive, devfs remained visible and the persistent
  original boot fallback remained unchanged. These preceding-image component and
  corrected-property results are not full installations from the final ISO; see
  [the exact scopes and receipts](docs/testing-1.1.1.md#actual-installation-desktop-and-corrected-root-clone-results).
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
