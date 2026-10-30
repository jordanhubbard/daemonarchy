# 1.4.1 plan: deferred from 1.4

- **Status:** active
- **Owning queue item:** [INSTALL-PERF-001](active-work.md#install-perf-001-make-exact-image-installation-at-least-10x-faster)
- **Supporting queue items:** [PKG-001](active-work.md#pkg-001-implement-the-release-package-dag-and-safe-parallel-transactions),
  [PKG-002](active-work.md#pkg-002-self-host-the-installers-package-closure-for-both-architectures),
  [NET-001](active-work.md#net-001-make-the-installer-network-bring-up-proactive-and-robust),
  [VISUAL-SDK-001](active-work.md#visual-sdk-001-extract-a-reusable-installer-visual-sdk-and-plugin-runtime),
  [GAME-001](active-work.md#game-001-add-playable-classic-arcade-games-to-the-installer)
- **Completion / archival evidence:** pending exact-image MSI, MacBookPro16,1
  and VM baselines; 10x physical improvement; exact network matrix; integrity,
  desktop and failure/recovery acceptance; independently consumable visual SDK;
  exact-image plugin/game isolation and no-regression evidence.

Opened on 2026-10-29 by operator decision; 1.4.0 is published.

The measured installation target is tracked as
[INSTALL-PERF-001](active-work.md#install-perf-001-make-exact-image-installation-at-least-10x-faster)
and [issue #134](https://github.com/jordanhubbard/daemonarchy/issues/134).

1.4 supports forward installs and `pkg`-based upgrades of a running system. The
items below were 1.4 acceptance rows. They moved here so they no longer block
1.4. None of them is claimed as done by 1.4.

## Scope

- **Reusable visual SDK and plugin runtime**
  ([VISUAL-SDK-001](active-work.md#visual-sdk-001-extract-a-reusable-installer-visual-sdk-and-plugin-runtime),
  [issue #139](https://github.com/jordanhubbard/daemonarchy/issues/139)).
  Split the shared text and graphical renderer, palettes, animation/effects,
  input actions, resize/reduced-motion behavior and audio cues out of the
  installer into a separately packaged, versioned SDK. Define trusted,
  content-identified animation/effect, visualizer and game plugins with bounded
  resources, explicit capabilities and preemptible lifecycle. Prove the SDK in
  a non-installer host. The installer remains the authoritative privileged host:
  plugins cannot mutate progress, hide prompts or outcomes, or import ambient
  executable content. The installer uses the SDK for all of its own
  visualization, so it is the SDK's first consumer and no private rendering
  path remains beside it.

- **Playable classic-arcade interludes**
  ([GAME-001](active-work.md#game-001-add-playable-classic-arcade-games-to-the-installer),
  [issue #137](https://github.com/jordanhubbard/daemonarchy/issues/137)). Ship at
  least four (aiming for five or six) small original arcade homages in the
  installer, including a Space Invaders-style fixed shooter; four distinct
  games are what prove the SDK design. Load them through the
  VISUAL-SDK-001 game plugin contract rather than direct installer imports or a
  parallel UI stack. Installation continues
  authoritatively in the background; prompts, approvals, errors, diagnostics and
  completion preempt play. Qualify vt(4), the graphical installer, small/16-color
  terminals, mute/no-device behavior, game failure recovery and bounded resource
  use. Do not ship ROMs, copied assets, protected names or incompatible code.

- **Exact-image installer network matrix** ([ledger A14](1.4-coverage-ledger.md),
  [NET-001](active-work.md#net-001-make-the-installer-network-bring-up-proactive-and-robust)).
  VM runs on the final image for several NICs with one DHCP server, broken DHCP
  DNS, blocked public DNS with a user resolver, blocked ICMP, a wrong clock
  (fixed by NTP, then by hand) and an unattended CIDATA install, with the
  retained `/tmp/daemonarchy-network/log`. Then the no-cable MacBookPro16,1
  run. No VM-level harness exists yet; `tests/network-bringup.sh` covers each
  case only against shimmed commands.
- **Upgrade of an existing Daemonarchy system through the installation image,
  and rollback** (part of [ledger A11](1.4-coverage-ledger.md)). Nice to have.
  `pkg upgrade` of a running system is unaffected and stays in scope for every
  release.
- **Faster package installation in the installer.** Installing packages takes
  hours, and `pkg install` fetches and extracts them largely in sequence. The
  plan: fetch in parallel up front (a worker pool over the whole closure,
  since downloads have no ordering constraint), then install along the
  dependency DAG from the leaves up, so a package never waits on one that is
  not yet installed and independent subtrees run together. The catalogue
  closure tooling in `tests/package-dag.py` and `scripts/` already computes the
  DAG. Open questions to settle first: whether `pkg add` of many packages
  concurrently is safe (it takes a database lock, so extraction may need to be
  parallel while registration is serialised), where the time actually goes
  (network fetch, ZFS extraction, post-install scripts or `ldconfig` runs;
  measure on the installer before designing), and whether to ship a
  pre-extracted tree for the largest packages instead.
- **Why an Omarchy install takes about ten minutes and ours takes much
  longer.** The retained live8 GPU-backed QEMU disk now has a
  [content-identified recovered observation](../../verification/installer-live8-recovered-baseline-development.json):
  the fetch phase took 2,565 s and package installation 141 s of a 2,747 s
  terminal diagnostic interval. The event pipe measured 784 of 930 network
  archives and 3,778,340,358 bytes; exact native catalogues identify the 1,189
  installed packages as a 5,553,478,434-byte archive closure and 16,847,424,955
  installed bytes. The original run did not measure its host link, so this is a
  historical design observation, not the required equivalent-link VM baseline.
  On that run the time is the download, not the install, and
  the DAG-ordered install above would save little by itself; parallel fetch
  and a smaller or local package set matter more. The ISO already carries
  the Daemonarchy repository (`file://`); the bulk comes from
  `pkg.FreeBSD.org`. A first source-level comparison at Omarchy `quattro`
  commit `225dcb80ef1ced9436f27eb34ff140659d3956dd` finds 163 explicit packages
  in the x86 default `omarchy-base.packages`; Omarchy documents that x86
  installs this base list alone and that its ISO builder creates an offline
  mirror from the package lists. Daemonarchy's 1,189 figure is a resolved
  installed closure, so 163 versus 1,189 is not yet a valid package-count
  ratio. Retain and compare Omarchy's resolved dependency closure, archive and
  installed bytes, offline-media coverage, compression and default/optional
  categories against Daemonarchy's content-identified closure before drawing
  conclusions. Also compare parallel downloads and mirror locality. Hours on real hardware
  (Wi-Fi, one connection) are reported but not measured here; the next step is
  resolving that manifest and timing equivalent fetch/install paths on the MSI
  and MacBook, then choosing between parallel fetch, a smaller default set, and
  shipping the large packages on the ISO.
- **Network speed first, measured by an installer trace.** The download is the
  long pole in installing large packages, so the fetch phase is the first
  10x lever: fetch the resolved closure with bounded parallel workers from a
  signed feed we control, not `pkg fetch -d` one archive at a time. Every
  installation now writes a microsecond-resolution trace of its timed events
  (phases, filesystem and storage operations, base extraction, each package
  download and unpack, device events, network/disk/CPU samples, DNS/TLS probes;
  [install-trace.md](../install-trace.md)) so each change is judged on the same
  per-operation numbers. The comparison with Omarchy is in
  [install-weight-vs-omarchy.md](../install-weight-vs-omarchy.md): it installs
  about 918 packages (v4.0.6; 7.9 GiB installed), mostly up front, but from local media; our 1,189 packages (16.8 GiB installed) are fetched.
- **Self-hosted packages for both architectures**
  ([PKG-002](active-work.md#pkg-002-self-host-the-installers-package-closure-for-both-architectures),
  [issue #142](https://github.com/jordanhubbard/daemonarchy/issues/142)). The
  installer still takes everything the ISO does not carry from
  `pkg.FreeBSD.org/${ABI}/latest`. Packages are already zstd-compressed on
  both sides, so the lever is where they come from. Publish the exact signed
  closure per architecture as GitHub release feeds, sharded under the release
  limits, and keep the FreeBSD mirror only as a fallback. First measurement
  (`scripts/package-mirror-plan.py`): the amd64 closure of the fixed installer
  roots is 1,004 packages and 5.13 GiB of archives, of which 811 packages and
  3.47 GiB come from pkg.FreeBSD.org and fit one release shard. On aarch64 the
  upstream catalogue lacks `chromium` and `hyprland`, so mirroring alone does
  not fix the arm64 install: those packages must also be built. Licences for
  redistribution are checked before anything is published.
- **Target: install at least 10 times faster.** Baseline first: time the
  whole install (fetch, extraction, registration, post-install) on the MSI,
  the MacBookPro16,1 and a VM, with a fixed package set and a recorded link
  speed, and keep the numbers in `docs/`. The 10x is measured against that
  baseline, not against the 45 minutes of the one VM run above. The VM run
  shows why a faster scheduler alone cannot reach it: 3.78 GB at 1.5 MB/s is
  most of the time. The plan, in order of expected gain: (1) take the
  download out of the install path by carrying the closure on the ISO or an
  attached local cache, so a first install reads from media; (2) fetch
  whatever remains in parallel from a nearby mirror; (3) extract in parallel
  along the dependency DAG and serialise only registration; (4) trim the
  default package set (1186 packages, 16 GiB installed) so the install does
  less. Acceptance: the 10x figure on both physical machines, the signed-feed
  verification unchanged, and the package set still installing a working
  desktop.

- **Install failure on NVIDIA hardware, fixed before announcement.** The 1.4.0
  image failed on the MSI Raider at the final package integrity check when the
  default CUDA offer was accepted: the installer had replaced the desktop's
  vendor menu and the CUDA phase's Rocky `dnf` had replaced files owned by
  `linux-rl9` packages, so verification reported them as corrupt and `pkg
  check` aborted on a path that had become a directory. The MacBook, with no
  NVIDIA GPU, never ran either step. Verification now runs before those
  additions ([#144](https://github.com/jordanhubbard/daemonarchy/pull/144)).
  Acceptance: a complete install of the rebuilt image on the MSI with CUDA
  and cudalab. QEMU has no NVIDIA GPU, so only that run covers it. 1.4.0 was
  published but not announced; 1.4.1 is the patch-before-announce release.
- **Every other open queue item moves here.** 1.4.0 closed with its
  remaining acceptance rows open; by operator decision on 2026-10-30 all open
  items in [active-work.md](active-work.md) carry `Release: 1.4.1`:
  ADOPT-002, UI-001, PKG-001, GUI-001, SRC-001, DEBUG-001, HW-001, RELEASE-001, COMP-001, PERF-001, PERF-002, DEV-001, TESTISO-001, HW-002, HW-003, DEBUG-002, DEBUG-003, ARCH-001, LIVE-001, NET-001, DEBUG-004, GPU-001, NET-002, HW-004, WORKER-001. None is claimed done by 1.4.0. They keep their own
  evidence requirements; this list is scope, not progress.
- **Loose ends found in 1.4.0.** The MSI touchpad runs in polling mode (the I2C-HID
  interrupt is not wired through). Only I2C controller 0 (`8086:7f4c`) of the
  Arrow Lake-S PCH is recognised in `ig4`, so a touchpad on another function would
  not attach. Linux's ARL004 interrupt-ordering workaround for the VMD controller
  is not ported; stress the RAID-mode NVMe path before relying on it. The VMD-
  disabled mode was not retested. CUDA Unified Memory (`cudaMallocManaged`)
  crashes through the Linuxulator, and cudalab builds against SDL 3.2 because 3.4
  needs a newer libXi than Rocky 9. The CUDA step of the installer ran only by
  hand on a running system; run it inside the installer on an NVIDIA machine.
  Physical reruns of the exact 1.4.0 image on the MSI and MacBook are still owed.

## Not changed

Fresh installs, signature and feed verification, the physical matrix and
publication remain 1.4 acceptance.
