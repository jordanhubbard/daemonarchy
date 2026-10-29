# Daemonarchy roadmap

Product goals and completeness are owned by [PROJECT.md](PROJECT.md).
Use [the active queue](docs/roadmap/active-work.md) for stable work IDs and
acceptance status, and [the architecture](docs/architecture/design-traceability.md)
for Component ownership. This file remains the release and feature overview.

## 1.4.1: faster installation and playable arcade interludes

Make the exact-image installer at least ten times faster on both physical
targets by retaining equivalent baselines and removing bulk network delivery
from the critical path without weakening package identity, integrity or
recovery. See [the 1.4.1 plan](docs/roadmap/release-1.4.1.md) and
[INSTALL-PERF-001](docs/roadmap/active-work.md#install-perf-001-make-exact-image-installation-at-least-10x-faster).

Add a curated set of approximately five or six playable classic-arcade homages
during installation, including a Space Invaders-style fixed shooter. Games use
the installer's existing ANSI/fancy graphical renderer, palette, input, resize,
reduced-motion and sound infrastructure. Installation continues in the
background and always owns critical prompts, errors, progress, diagnostics and
the final result. Original names, code and assets avoid ROM, trademark and
licensing problems. See
[GAME-001](docs/roadmap/active-work.md#game-001-add-playable-classic-arcade-games-to-the-installer)
and [issue #137](https://github.com/jordanhubbard/daemonarchy/issues/137).

## 1.4.0: P0 network debugging and an incremental release graph

First deliver bidirectional plain-mode network debugging across boot blocks,
loader, a forced `mountroot>` prompt, early kernel startup and panic, with
bounded polled transport and safe native-NIC takeover. Qualify an exact native
VM fault matrix before claiming physical MSI support. Preserve every published
1.3.1 artifact and retained package/build/cache output. See
[DEBUG-003 and the 1.4 plan](docs/roadmap/release-1.4.0.md).

Use Literate AI's parallel workers to coordinate build, test, package and release
creation across the selected Daemonarchy product, source, ports, desktop and
FreeBSD compatibility forks. The plan admits exact cross-repository dependencies
and lets FreeBSD make, Poudriere/pkg, ISO tools and a measured Bazel or other
executor perform their native actions. LitAI owns action custody, safe
dependency-ready scheduling, cache invalidation, evidence and publication.
Wrapping the current serial release script as one opaque action does not
deliver that result. See [PERF-002 and its 1.4.0 plan](docs/roadmap/release-1.4.0.md).
This build work supports the 1.4 debugger and follows the published 1.3.1
release. The earlier 1.3.2 network plan is historical.

Support aarch64 as well as amd64 in 1.4, with separate products, feeds, images
and evidence for each architecture. Qualify aarch64 on virtual machines first;
Apple M1-M4 laptops join as test machines once the virtualized image passes.
See [ARCH-001](docs/roadmap/active-work.md#arch-001-add-aarch64-as-a-second-supported-architecture-for-140).

Offer a live desktop from the installer media again, as FreeBSD's own media
does: a minimal desktop that runs from the ISO and RAM without touching any
disk, enough to check that the desktop boots and to run the installation
graphically. See [LIVE-001](docs/roadmap/active-work.md#live-001-offer-a-live-desktop-from-the-installer-media-without-touching-the-disk).

Make the installer's network step proactive: probe every adapter for DHCP at
once, prove DNS with direct lookups, make the clock usable, fetch missing
firmware and fall back to Wi-Fi first when no cable works, in one pipeline for
the text, graphical and unattended installers. See [NET-001](docs/roadmap/active-work.md#net-001-make-the-installer-network-bring-up-proactive-and-robust).

Add cross-vendor GPU diagnostics with glmark2 and an impressive Daemonarchy
showcase, recording the actual renderer, vendor, driver, API, FPS and frame
times on physical AMD, NVIDIA and Intel MacBook FreeBSD systems. Software
fallback is explicit and does not qualify GPU acceleration (GPU-001, issue #101).

Make installed boot use the first usable connected interface without waiting
for missing or unplugged Ethernet: bounded parallel DHCP, one route/DNS owner,
bounded offline boot and retained failure diagnostics. Trace installed boot
separately from installer NET-001 (NET-002, issue #102, related to #80).
These are planned 1.4 items; DEBUG-003 remains P0.

## Unpublished 1.2.0 plan: owned source builds and complete Component coverage

No 1.2.0 production release was published. The 1.3.1 changelog covers work
since 1.1.1, including this plan's completed development, while the remaining
Component and executor obligations stay in the active queue and 1.4.0 roadmap.

Build our pinned FreeBSD-CURRENT fork through the [owned source workflow](docs/source-builds.md),
then represent all selected `/usr/src` and `/usr/ports` inputs and native units as
canonical Literate AI Components. Ports origins, source programs/libraries,
kernel/loader units and shared build/support inputs need explicit ownership,
target/options variants and dependencies. Whole-tree build wrappers are preparation;
full catalog coverage and qualification of the selected release closure remain
open under [COMP-001](docs/roadmap/freebsd-components.md). The
[1.2.0 ledger](docs/roadmap/release-1.2.0.md) retains the complete release scope.

The current [build-performance program](docs/roadmap/build-performance.md) will
execute the established graph as literal Literate AI Components, producing
per-unit pkg products with provenance and dependencies. Make is the baseline;
Bazel, Buck2 or another suitable executor may replace it when measurements and
native correctness demonstrate substantial improvement.

## 1.1.1 refresh

The stable release preceding 1.3.1 was **1.1.1**. Its source is
`bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` (OSVERSION `1600028`), with ports
`f7d7ee897405dcb8ce87e674588a4e1b3bfba00e` on `daemonarchy-1.1.1`.
Matching world, kernel, jail and driver builds replace the older OSVERSION
`1600027` set. The new versioned application feed is
`packages-16-amd64-1.1.1`; the unversioned stable feed stays unchanged.
The [preparation and qualification record](docs/testing-1.1.1.md) is the authority
for completed checks and publication status. Component boot results alone do
not qualify the final ISO.

The installer work includes Pair/Unpair for live or stale remote sessions,
automatic rescue-menu redraw after late boot probes, package-file integrity
checking before success, original-root `canmount=noauto` with explicit installer
mounting to protect selected boot environments, and bounded [continuous diagnostics](docs/remote-agent-debug.md#continuous-diagnostics).
The adoption helper independently checks both kernel and userland versions
before selecting rebuilt packages; `pkg install -y` itself accepts a newer-OS
package and is not that guard. Existing base migrations must preserve a rollback
boot environment and keep drivers on the new snapshot.

Upstream [#640](https://github.com/freebsd/freebsd-ports/pull/640),
[#641](https://github.com/freebsd/freebsd-ports/pull/641) and
[#642](https://github.com/freebsd/freebsd-ports/pull/642) are ready for upstream
review after refreshed native validation. The first two submissions match the
qualified release port files; #642 passed separate native DRM and NVIDIA DRM
testports at its exact head without the downstream VirtIO patch. Upstream merge is separate from shipping
the qualified fork.

The operator authorized release publication without further final installation-matrix
evidence and with the remaining physical,
Bluetooth, enterprise Wi-Fi and bhyve limitations disclosed. Those limitations
remain open qualification work. The physical HP at `daemon.local` passed coordinated upgrade, rollback, return
boot and AMD Wayland greeter rendering. The operator confirmed that normal
authenticated `jkh` login opens the desktop and its applications work.
The MacBook investigation remains open. Final-ISO BIOS and enforced UEFI boot
and embedded root-mount-policy checks passed; the four full VM runs use the
preceding image and have their scope recorded separately.

## Planned: Winamp-inspired visuals and parallel package management

Bring Omarchy's 1980s visual character—screensavers, wallpapers and the
Omarchy/Daemonarchy logos—into installation and package management. The goal
is useful, creative, colorful feedback with the energy of a Winamp visualizer.
This is planned work for a future release, not functionality shipped in the published 1.3.1.

### ANSI installer visualizers

Use ANSI color and terminal graphics to animate real installation activity at
each stage, with a consistent Daemonarchy palette and recognizable logo motifs.
Explore several visualizer styles rather than one repeating progress spinner:

- **Disk skyline:** neon blocks rise as files fill the target, with actual used,
  free and required space alongside the animation. Change the scene for disk
  preparation, base extraction, packages and final verification.
- **Package equalizer:** Winamp-style bars and falling peaks respond to active
  downloads and package work. A dependency constellation lights up as packages
  become ready, install and complete; identify the current packages in text.
- **Network waveform:** scrolling ANSI scopes, spectrum-like bars or a neon
  tunnel respond to measured transfer rates, showing received bytes, active
  transfers, retries and genuine idle periods.
- **Stage transitions:** short logo reveals, pixel trails and distinct palettes
  celebrate completed stages. Failed or stalled work stays clearly visible and
  never receives a success animation.

Every animation must correspond to measured state; decorative motion must not
masquerade as progress. Keep stage names, counts, errors and available estimates
readable. Mark uncertain totals or estimates explicitly, and distinguish
network waiting, verification and installation from a hung process. Preserve
ordinary diagnostic logs independently of screen redraws.

Support the physical FreeBSD console, small terminals and SSH/serial sessions.
Provide 16-color and 256-color rendering as available, restrained refresh rates,
resize handling and a reduced-motion/plain-text option. Animation must not
consume input, hide an approval prompt or meaningfully slow installation.

### Complete package DAG and safe parallel execution

For each release, generate and retain the complete package dependency DAG for
every supported installation selection, including all transitive dependencies,
GPU-specific packages and optional components. Record exact package identities,
versions, origins/flavors, repository provenance, hashes, dependency edges,
download sizes and installed-space estimates. Include dependencies supplied by
official repositories as well as Daemonarchy's own feed. Missing, conflicting or
changed catalogue inputs must trigger an explicit re-plan or rejection rather
than silently making the recorded graph incomplete.

Before writes, resolve the user's selections into a concrete install plan from
that release graph. Make the graph and structured progress events available to
both humans and agents, and use them as the source for progress totals, space
planning and the visualizers.

Pursue parallel **downloads and installation of independent leaf-node packages**.
Define readiness by completed prerequisites: the scheduler's ready frontier may
run independent work together while preserving dependency order. Bound workers
by memory, CPU, network and free-space budgets; prioritize work that unblocks
other packages and avoid downloading or installing shared dependencies twice.

Design one transaction coordinator for package-database changes, file ownership,
shared directories, install scripts, triggers and service/cache updates. Package
independence in the dependency graph alone does not establish that those side
effects can run concurrently. Investigate the required native pkg interfaces or
upstream extensions; do not implement parallel installation by starting competing
pkg transactions against the same database. Parallel fetch and verified staging
can proceed while unsafe commit/script operations remain serialized. Actual
parallel installation remains an explicit goal requiring evidence of safe
concurrency, rather than relabeling parallel downloads as parallel installation.

Retain signature/hash verification, installed-file checks, automatic/manual
package identities, actionable failures and boot-environment recovery. Failed
workers must stop dependent work, retain useful logs and permit a well-defined
retry without reporting partial completion as success.

### Colorful, fast graphical package manager

Apply the same visual identity and DAG-based engine to graphical package
management: clear dependency previews, meaningful download/install animations,
parallel ready-work scheduling, live disk/network activity and readable errors.
Support install, update and removal plans, with explicit effects on dependencies
and recoverable failures. Keep the interface responsive and offer reduced motion.

Evaluate extending the current graphical package manager first. If it cannot
support the intended experience and execution model, build a suitable application
and contribute it as a FreeBSD port, with source, licensing, packaging and native
validation ready for upstream review. Share the planner, scheduler and structured
progress protocol with the installer so the GUI and terminal report the same
transaction and completion state.

### Acceptance and delivery

1. Prototype several ANSI styles using recorded progress events, then demonstrate
   them on a real FreeBSD console and SSH/serial terminals. Review creativity,
   legibility, resize behavior and animation cost with real installation stages.
2. Produce the complete release graph and test every supported selection for
   dependency closure, exact package identity, conflict detection and space
   planning before enabling concurrent execution.
3. Measure serial and parallel runs on the same package set. Report download,
   staging, actual install/commit and total elapsed time separately, plus peak
   resource use; establish speed improvements without weakening integrity.
4. Exercise shared dependencies, conflicting files, script/trigger side effects,
   low disk space, network interruption, worker failure and retry on native
   FreeBSD. Verify package/file integrity and boot-environment recovery afterward.
5. Qualify the shared engine and graphical application, contribute any needed
   pkg changes and the application port upstream, and retain terminal/GUI evidence
   that actual parallel installation and accurate progress work as claimed.

## 1.1.0 candidate: retained scope and evidence

The table and checks below describe the October 16 candidate, not the new
1.1.1 source/package set. Their outstanding qualification work carries forward.

Daemonarchy **1.1.0-rc.1** was published; its release assets and the unpublished
**1.1.0** stable draft were removed when superseded by 1.1.1. On October 16 the operator approved stable publication after the
remaining hardware, Bluetooth, enterprise Wi-Fi and bhyve limitations were
reported, but publication was not completed. Those gaps remain open
qualification work, not passing results.
All four final QEMU installation/desktop configurations and production-key
maintenance/recovery passed.

Existing 1.0 application packages remain upgradeable through their compatible feed. `pkg upgrade` does not migrate the FreeBSD base/kernel; 1.1.1 requires its matching base and drivers before changing to the new feed.
New installation modes are optional and must preserve the existing whole-disk
installation path.

On October 16 the operator asked that release work proceed while the community
investigates the ASRock X570/RTX 4090 system's unresolved failure to reach an OS
or usable firmware setup. This defers that machine's physical acceptance result;
it does not turn the result into a pass. Keep the failure in release notes and
the [hardware observations](docs/testing-1.1-hardware-observations.md).

| Work | Implementation scope | Required acceptance evidence | Status |
| --- | --- | --- | --- |
| NVIDIA graphics | Detect supported GPUs, package kernel-matched drivers, configure modesetting and the desktop session, and explain unsupported models. | Install and reboot on NVIDIA hardware; SDDM login, Hyprland rendering, external displays, and suspend/resume; Intel/AMD regression checks. | In progress: RTX 4090 native/Linux nvidia-smi and Linuxulator CUDA kernel execution passed; Linux64 package-install blocker fixed and physical installation recovered; installed desktop/display/suspend and regression matrix pending |
| Graphical VM desktops | Provide Hyprland through a supported virtual graphics path and configure the login session for it. An alternate desktop does not satisfy this requirement. | Boot the installed image into usable Hyprland in each advertised hypervisor; verify rendering, keyboard, pointer, resizing, and reboot. SSH-only checks do not qualify. | In progress: isolated QEMU/VirGL Hyprland rendering, keyboard, pointer, mode switching, packaged SDDM password login and reboot passed; native DRM/core testport and all four final QEMU plain/GELI, BIOS/enforced-UEFI desktop configurations passed; refreshed bhyve and physical graphics remain unqualified |
| Bluetooth beyond input devices | Add audio device pairing, connection, output selection, reconnect, and removal to the FreeBSD backend and panel. Document the supported audio profiles. | Real headset/speaker playback, volume, disconnect/reconnect, and reboot persistence; existing keyboard/mouse pairing still works. | In progress: native A2DP/SBC backend and desktop routing implemented; native testport/package QA and real OSS/PipeWire bridge checks with null transport passed; real headset/HID/reboot qualification pending |
| Enterprise Wi-Fi | Support certificate-validated 802.1X connections in the installer and desktop panel, including PEAP/MSCHAPv2 and EAP-TLS. Preserve credentials and certificate files securely across installation. | Join a test enterprise network with each supported EAP method, reject an untrusted server certificate, reconnect after reboot, and check that credentials stay out of logs. | In progress: profile helper, installer/panel integration, native parser and credential-transfer tests; real EAP exchanges and reboot qualification remain open because the operator has no enterprise test network |
| Remote debug session feedback | Show when an approved agent actually connects, a short description of its current activity, and an explicit completion message telling the operator it is safe to stop the session. Keep the display readable without streaming every command or sensitive data. | Exercise pairing, successful connection, activity changes, reconnects and explicit completion on the local console. An SSH disconnect between commands must not be mistaken for completion; stopping access must still close connections and discard approvals. | Implemented: native SSH lifecycle and console feedback tests passed; final production image audit confirms inclusion |
| Dual boot and partition selection | Show existing partitions; replace only an explicitly selected OS/data partition or create one in selected free space; preserve existing EFI loaders and entries. Never resize an existing filesystem implicitly. | Disposable disks containing another OS survive installation with partition/data checks and both operating systems booting; insufficient space and invalid selections fail before writes. | In progress: native preservation tests pass for both selection modes; physical Windows boot tests pending |
| Legacy BIOS boot | Add BIOS image boot and installed-system boot code, alongside the UEFI path. | Boot the ISO, install, and reboot in BIOS and UEFI VMs, including encrypted installations. | Implemented: final production ISO passed BIOS and enforced UEFI installation/reboot, each plain/GELI, with actual Hyprland/browser/package-manager checks; UEFI plain also passed both optional checkout checks |
| Secure Boot | Establish a signed FreeBSD boot chain with manual certificate enrollment, preserving existing OEM/Windows trust entries, and a documented key-enrollment/update process. | Install and boot with Secure Boot enabled; reject an untrusted boot component and verify signed updates and recovery. | In progress: development-key ZFS/GELI enforcement, signed update, rejected driver update, rollback and installed QEMU desktop passed; production-authority UFS runtime, disabled-enforcement boot, unenrolled-loader rejection and tampered-kernel rejection passed; production enforced UEFI/GELI install, signed update, altered-candidate rejection, rollback and graphical return passed; final enforced plain-ZFS install and both optional checkouts also passed; physical enrollment remains unqualified |
| Ports and source refresh | Refresh the Daemonarchy ports fork from upstream FreeBSD ports and re-sync system sources with FreeBSD CURRENT before selecting the release snapshot. Preserve Daemonarchy changes and reconcile ports with the selected package set. | Record pinned ports/source revisions; rebuild the snapshot jail, packages, and kernel modules together; clean `poudriere testport` and installation against the selected package set. | In progress: snapshot/source 3ceb5f150bc1 pinned; selected ports 08a6370a019a on daemonarchy-1.1-package-baseline; desktop 1.1.0 and core 4.0.4_22 passed native testport and final two-package bulk with no failures/skips; kernel-matched modules retained; all four final production ISO configurations passed, including both public optional checkout downloads |

The released 1.1 packages come from [jordanhubbard/freebsd-ports, branch `daemonarchy-1.1-package-baseline`](https://github.com/jordanhubbard/freebsd-ports/tree/daemonarchy-1.1-package-baseline), revision `08a6370a019a35ae791c549fa1da9a3ce9bd5b33`. The published preview.13 uses the earlier baseline recorded with that image.
System sources track [FreeBSD CURRENT (`freebsd-src`, branch `main`)](https://github.com/freebsd/freebsd-src/tree/main); pin the source revision that produced the selected image snapshot.
Desktop sources live in [daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop)
and [omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd).
Daemonarchy publishes its packages through its own [signed package repository](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64).

Upstream reviews: [supporting ports #630](https://github.com/freebsd/freebsd-ports/pull/630)
and [desktop ports #635](https://github.com/freebsd/freebsd-ports/pull/635).
Both original submissions were closed without merging on October 15. Their refreshed replacements are #640 and #641, with the LinuxKPI header fix in #642; 1.1 ships the qualified fork.

### Delivery order

1. Deliver the partition-selection preview for existing-partition and free-space testing; establish hardware and VM coverage.
2. Implement graphics, networking, and Bluetooth in their owning repositories;
   update the ports and installer integration together.
3. Complete physical Windows preservation and boot checks; validate the remaining boot modes.
4. Refresh the ports fork from upstream and re-sync sources with FreeBSD CURRENT.
   Select and record the new snapshot/source revision and package-compatible ports
   baseline, then rebuild the jail, packages, and kernel modules together.
5. Build the release candidate, exercise upgrades from 1.0.1, and complete the
   acceptance matrix before publishing 1.1.0.

### Release gates

- [ ] Every feature above has implementation and retained native test evidence.
- [x] Ports fork refreshed from upstream and system sources re-synced with FreeBSD CURRENT; exact selected revisions recorded.
- [x] Kernel modules match the image's exact FreeBSD snapshot; native inventory and production-image audit passed, followed by enforced installed-driver/desktop checks.
- [x] Changed ports pass `poudriere testport`; final desktop and compatibility checks passed, followed by a clean combined bulk build.
- [ ] Unattended installation passes the existing QEMU and bhyve checks. Final production ISO BIOS and enforced UEFI QEMU installation/reboot and GUI checks passed with and without encryption. Unencrypted UEFI bhyve passed with both shallow checkouts; encrypted bhyve and repetition against the refreshed snapshot remain pending.
- [ ] Graphical VM and physical-hardware checks pass.
- [ ] Existing installations upgrade successfully; failed updates remain recoverable. [Exact final application-package upgrade, reboot, ZFS rollback and return from 1.0.1 passed](docs/testing-1.1-upgrade.md), as did development-key signed boot maintenance, injected driver failure and rollback; production-authority GELI/ZFS signed maintenance, altered-candidate rejection, rollback and graphical return also passed; physical upgrade checks remain unqualified.
- [x] Documentation states supported GPUs, hypervisors, Bluetooth profiles,
      EAP methods, and boot/install combinations precisely.
- [x] Candidate package repository, ISO, checksum, public certificate and release notes verified together; all 26 package-feed and six installer asset hashes/sizes match. The unpublished stable 1.1.0 draft was later removed. Operator-approved publication deferrals do not close the unchecked qualification items above.

Feature status and evidence belong here as work progresses. If a platform
dependency prevents a feature from shipping, record the blocker and agree on
any scope change before calling 1.1.0 complete.

### Implementation notes

- Remote agent debug: the live installer menu can open a temporary SSH
  listener (default port 2222, configurable), with console approval of the
  agent's key fingerprint. This provides the USB-to-agent handoff for physical
  test machines. Pairing, rejection, custom ports, reconnecting and stopping
  access passed native live-VM checks. See the [handoff guide](docs/remote-agent-debug.md)
  and [validation record](docs/testing-1.1-remote-debug.md).
  New builds announce authenticated connection and display agent-provided
  `daemonarchy-debug activity` updates and explicit `daemonarchy-debug done`
  completion. Preview.13 and older lack that feedback. A closed SSH connection
  never marks the overall task complete.
  For 1.3.1, the installed desktop's network menu provides **Pair**, **Resume**
  and **Unpair** controls and shows the approved listener, connected agent,
  address and port. The Pair action remains available without an active grant.
  The installed debugger retains an authenticated Wi-Fi profile with its grant
  and can restore wireless DHCP before resuming after a reboot with no address.

- BIOS: the installer now adds a 512 KiB `freebsd-boot` partition in the gap
  before the EFI partition and writes the target snapshot's `pmbr` and
  `gptzfsboot`. Native disposable-disk tests passed with both 512-byte and
  4 KiB sectors. A QEMU SeaBIOS smoke test reached the snapshot's FreeBSD loader
  and loaded its kernel from ZFS; the development ISO also built successfully.
  The QEMU installation harness accepts `BOOT_MODE=bios` or `BOOT_MODE=uefi`.
  Full BIOS and UEFI QEMU installation/reboot checks now pass with and without
  GELI encryption. The harness detects the BIOS bootcode's early VGA password
  prompt as well as the UEFI loader's serial prompt. See the
  [development check record](docs/testing-1.1-bios.md).
- VM graphics: `graphics/virtio-gpu-qemu-kmod` in the current ports tree exposes
  a framebuffer for Xorg's `scfb` driver, not the DRM interface needed by
  Hyprland. Installing that port alone does not satisfy this feature. A separate
  VirtIO DRM/VirGL integration now renders Hyprland in an isolated QEMU guest;
  see the [development check record](docs/testing-1.1-vm-graphics.md).
- NVIDIA: the image explicitly packages `nvidia-drm-612-kmod` alongside
  `drm-612-kmod`, keeping the NVIDIA and AMD/Intel payloads on one DRM core. NVIDIA
  595.104.02 userland and kernel packages are built for the selected snapshot.
  An NVIDIA install also loads `linux.ko`, enables the Linuxulator, and
  installs `linux-nvidia-libs` at that same driver version. After the first
  boot, `daemonarchy-linux-cuda setup` installs the Rocky Linux CUDA 13.2
  toolkit inside `/compat/linux` without a Linux kernel driver. CUDA 13.3 and
  later need a newer driver branch than 595.104.02. `daemonarchy-linux-cuda cudalab`
  builds and runs [cudalab](https://github.com/jordanhubbard/cudalab.git) as a
  Linux program for development qualification. Installer selection and application
  menu entries remain disabled until version-specific native Linuxulator evidence
  is recorded. AMD firmware and Radeon/AMDGPU selection remain included.
  Supported AMD (`amdgpu`), Intel (`i915kms`), and NVIDIA installs also
  install `vulkan-loader` and `mesa-dri`. That is the common Vulkan layer:
  RADV, ANV, and NVIDIA's ICD from `nvidia-driver`. Legacy `radeonkms` does
  not get it. CUDA stays a NVIDIA-only extra and does not replace Vulkan.
  Native package admission and policy tests do not replace physical display,
  login, suspend, or cudalab qualification.
- Installer console: the live installer loads Terminus 16×32 (`terminus-b32`)
  when the console is wider than 200 columns. That is the face the Linux
  console selects on a HiDPI panel. The 16-inch MacBook's 3584×2240 EFI
  console is otherwise 448 columns of the default 8×16 font.
- The physical X570/Ryzen desktop has an NVIDIA RTX 4090, confirmed in the
  preview.13 live installer. Detection does not qualify the installed driver or
  Hyprland. Separate Intel/AMD graphics regression coverage remains required.
  No physical Windows dual-boot acceptance result is recorded yet; the inspected
  internal disks have no usable unallocated space.
- Partition selection: see the [preview test guide](docs/testing-1.1-partitions.md).
  Shared-disk installs preserve the existing EFI filesystem and add a separate
  loader/firmware entry. They require UEFI/GPT and do not resize filesystems.
- Updates: Daemonarchy installations must identify themselves as Daemonarchy,
  link to Daemonarchy releases/support, and check its own package catalog.
  FreeBSD dependency repositories remain identified separately.
- The upstream ports review's request to move bundled files into source
  repositories was addressed in 1.0.1. Both original upstream PRs were closed unmerged;
  upstream acceptance is tracked separately from release qualification of the fork.

### Optional development trees

Space planning for installer selections that populate `/usr/ports` and `/usr/src`
is recorded in [the sizing report](docs/optional-source-sizing.md). The live
packages now contain depth-1 shallow Git checkouts, superseding the original
source-only estimate. Separate installer selections and the runtime
`daemonarchy-checkouts` command are implemented; native package round-trip tests
pass. A complete unencrypted UEFI bhyve ISO installation and reboot with both
options selected also passed on bare metal, including post-boot checkout
verification; see the [test record](docs/testing-1.1-live-checkouts.md).
Later 1.1 QEMU results are recorded in [the final candidate record](docs/testing-1.1-final-image.md). The refreshed 1.1.1 sizes and public catalogue are recorded in [the sizing report](docs/optional-source-sizing.md); its final-image checks remain separate.


## Historical 1.3.2 network bootloader plan

The earlier operator direction assigned the complete bootloader environment and
MSI early-kernel capture to 1.3.2. The current 1.4 P0 scope adds mountroot and
panic interaction. [DEBUG-003 and the historical plan](docs/roadmap/release-1.3.2.md) cover plain wired
console control without SSH or additional authentication, variables, disk and
network kernel/module loading, downloaded Lua execution, actual pre-driver
networking and physical MSI acceptance. Prior release and prerequisite evidence
retain their original scope. The implementation is incomplete.

## 1.2: earlier network debugging

The following records the earlier scope and inspection baseline; use the 1.4
plan above for current implementation status and scheduling.

Loader and early-kernel network-debugging changes are deferred to **1.2**.
The selected GENERIC already includes DEBUGNET, NETDUMP and NETGDB; those
facilities require a supported, initialized wired NIC and do not provide a
loader-to-early-kernel transport. The owned source fork and an explicitly selected
debug profile need separate design, privacy/trust boundaries, matching symbols,
and native transport/crash qualification. None of those new source changes is
part of 1.1.1. Its approved-session SSH diagnostics retain evidence while
userland/networking works and explicitly report the limits after a hard reset.

Source inspection confirms two distinct foundations. The EFI loader uses firmware
Simple Network Protocol with the standalone UDP stack for network boot; a remote
loader command/console stub is not implemented. Kernel NetGDB uses UDP through a
proxy and currently refuses activation before a panic. Boot `-d` or `-g` flags do
not select a NIC or turn it into an early-boot network listener. See the
[NetGDB contract](https://man.freebsd.org/cgi/man.cgi?query=netgdb&sektion=4).

Qualify loader variable/console/boot control first, then supported kernel
NetGDB/netdump operation, then early-kernel transport. UEFI networking ends at
`ExitBootServices`; the kernel must initialize its own driver. Carrying the same
NIC identity and addresses across that boundary does not by itself cover failures
before driver initialization. The latter phase needs explicit early-driver and
debugger work, with retained traffic and matching symbols rather than inferred
coverage from a successful network boot.
