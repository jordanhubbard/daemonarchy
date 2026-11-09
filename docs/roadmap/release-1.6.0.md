# 1.6.0 plan: ARM platforms and upstream synchronization

- **Status:** active
- **Opened:** 2026-11-07; expanded from SPARK-001 to the ARM distribution program by operator direction
- **Owning queue item:** [ARM-001](active-work.md#arm-001-maintain-the-arm-platform-and-upstream-evidence-register)
- **Additional release goal:** [SYNC-001](active-work.md#sync-001-synchronize-current-upstream-omarchy-450-and-freebsd-current-source-and-ports-for-16)
- **GitHub issue and milestone:** [ARM-001 #295](https://github.com/jordanhubbard/daemonarchy/issues/295), [1.6.0](https://github.com/jordanhubbard/daemonarchy/milestone/5)
- **Completion / archival evidence:** research and the four-CPU diagnostic checkpoint only; implementation and final-distribution acceptance remain open

## Scope and release contract

**Operator direction, 2026-11-07: the theme for 1.6 is ARM, covering popular ARM
platforms, explicitly including Raspberry Pi 4 and Raspberry Pi 5. Pi 4 is a
separate porting target ahead of Pi 5 in the SBC implementation queue.** This
supersedes the earlier same-day SPARK-001-only scope. NVIDIA, Apple, Raspberry
Pi and other enrolled families require native FreeBSD implementation and actual
distribution results; the operating system remains FreeBSD.

The [research checkpoint](arm-research-20261107.md) records both requested
repositories and the Asahi/Aurora, NVIDIA/NixOS, Raspberry Pi/Debian/Linux and
BSD predecessor work. [Implementation tasks](arm-implementation.md) separate
hwtrace/prerequisite discovery, final implementation and validation for each
work item. The [active queue](active-work.md) and
[release goals](release-goals.json) register all fifteen ARM work IDs and the
additional upstream synchronization goal.

A family name, successful kernel build or another OS's support table does not
qualify a board. Every concrete model/revision/mode needs its own ledger row.
No blocked family, missing worker or unimplemented driver can disappear from
the release scope merely to make the release pass. Any change to the required
target set needs a recorded operator scope decision. A diagnostic-only image,
four-core workaround, detected device or console-only boot is not completion of
a desktop target. Existing amd64 products and regressions remain covered.

The older non-ARM backlog on the 1.6 milestone is not automatically added in
full. ARCH-001, NET-001, GPU-001, PKG-002, DEBUG-003 and the release/desktop
Components supply dependencies for the ARM work; unrelated backlog retains its
own scope. SIGN-001 option A still applies: freeze signed inputs, finish QA,
then conduct one operator signing session. Preserve published release bytes.

## Upstream synchronization goal (SYNC-001)

**Operator direction, 2026-11-08:** 1.6 also synchronizes with **current upstream Omarchy (4.5.0)**
and refreshes **FreeBSD-CURRENT src and ports**. This adds release scope to the
ARM program; it preserves the Pi 4-before-Pi 5 priority and existing amd64 coverage.
The operator clarified that the target is current upstream Omarchy, rather than
historical 1.5.x. The selected stable release is
[Omarchy v4.5.0](https://github.com/omacom/omarchy/releases/tag/v4.5.0), published
2026-11-05, tag object `97e664bd971fa5a8691d89440d3738143499c438`, commit
`ac2690cd7be4f47e4a255f5e2e78d904d436b068`. The currently packaged Omarchy
baseline is 4.0.4. Import, adaptation and native qualification remain open.

- [x] Select and pin the current upstream Omarchy release (identity above).
- [ ] Review its delta
  against the selected desktop and compatibility forks; port applicable desktop,
  configuration, application and service changes to native FreeBSD behavior.
  Record Linux-specific features requiring adaptation or an explicit limitation.
- [ ] Refresh the owned source fork from upstream FreeBSD src `main` (CURRENT)
  and the owned ports fork from upstream FreeBSD ports `main`. Record upstream
  and resulting fork commits, resolve conflicts, and preserve Daemonarchy fixes,
  board support, packaging and contribution history. Ports has its own revision;
  its compatibility must be tested against the selected CURRENT base and ABI.
- [ ] Rebuild and qualify the matched world, kernel, modules, source/ports seeds,
  packages and installer images for amd64 and aarch64. Record toolchain, ABI,
  upstream ancestry and exact artifact/feed identities before the release freeze.
- [ ] Retain exact-artifact desktop/login, application/menu/service, install,
  network update and rollback regression evidence, including ARM board-specific
  fixes and existing amd64 targets. Refresh documentation to the actual delivered
  behavior and disclose unresolved upstream differences.

SYNC-001 closes only with reviewed import/conflict records and passing native,
VM and required physical results for the selected artifacts. A newer revision,
successful merge or green documentation check alone does not establish acceptance.

## Initial platform matrix

All rows below are **planned/unqualified for 1.6**. The physical Spark diagnostic
checkpoint is recorded separately; it does not change these release states.
ARM-001 must expand each family into exact model/revision rows, allocate hardware
and owners, and refresh the inventory as popular platforms emerge.

| Family and initial named targets | Work item | Required discovery distinction |
| --- | --- | --- |
| ASUS ProArt P16 H7607BA / NVIDIA RTX Spark N1X laptop | SPARK-001 | Own Insyde firmware, MADT enabled flags, 18-core marketing versus 20 table entries; do not import DGX topology |
| NVIDIA DGX Spark FE and GB10 partners, starting with ASUS Ascent GX10 | SPARK-002 | FE versus partner firmware, 20-core reference, IORT/SMMU, networking/EC/display carveouts |
| Apple M1/M2 Mac mini and MacBook reference machines; M3, M4/A18 Pro, M5 and emerging-generation models as distinct rows | APPLE-001 | Per-board ADT/FDT, m1n1/U-Boot and per-OS firmware/stub, AIC/DART generations, display/GPU prerequisites |
| **Raspberry Pi 4B first**, then Pi 400 and CM4 carrier profiles | **RPI-001, P0** | BCM2711/RAM/EEPROM, SD/USB, UEFI versus FDT, full-memory DMA; Debian and Linux reference |
| **Raspberry Pi 5 after Pi 4**, with CM5 and Pi 500-family profiles | **RPI-002, P1** | BCM2712 C1/D0, RP1, newer EEPROM/UEFI compatibility, cooling, SD/USB/NVMe and persistence without runtime NVRAM |
| ROCK 5B, Orange Pi 5/5 Plus, RK3399/RK356x Pine64/Radxa families | SBC-001 | Exact board/carrier, vendor/mainline FDT versus ACPI, regulators/PCIe/DMA/display |
| CIX Orion O6-class, representative Allwinner, Amlogic and NXP i.MX8/MNT Reform boards | SBC-001 | Per-family CPU/firmware/driver gaps, exact model and boot container; no SoC-wide acceptance shortcut |
| Qualcomm 8cx Gen3 / ThinkPad X13s and Snapdragon X Elite/Plus laptops | QUALCOMM-001 | OEM firmware, ACPI versus board DTB, Oryon/PSCI, SMMU, storage/input/display/network firmware |
| Ampere Altra-class physical servers, AWS Graviton and an additional ARM cloud profile | ARM-007 | Physical versus provider firmware, NUMA/GIC/ITS, NVMe/ENA/virtio, console and recovery/provisioning |
| QEMU/HVF/KVM/UTM and VMware Fusion arm64 guests | ARM-007 | Hypervisor, virtual firmware and devices; a Mac-hosted VM is not native Apple support |
| Pi 3 / Zero 2 and maintained ARMv7/BeagleBone-class references; original Pi/Zero ARMv6 feasibility | ARM-008 with ARM-001 | CPU/ABI and memory budget, maintained FreeBSD baseline, desktop versus explicitly declared role; unsupported architectures stay visible |

The public matrix records boot, all enabled CPUs, memory/DMA, storage, display,
input, network, audio, power, installer, installed boot, update and recovery as
separate fields. Unknown, blocked and failed remain separate states. Platform
identity and a marketing core count never become feature verdicts.

## Implementation order

1. **ARM-001:** establish the model/source/firmware/evidence register and test
   owners; retain the current Linux and FreeBSD baselines without altering them.
2. **ARM-002:** make early-stage capture and isolated safe probes reliable on
   each boot chain. Export firmware tables before risky OS physical-memory
   probing; qualify reset and power-cycle survival rather than assuming NVRAM.
3. **ARM-003:** admit base/kernel/modules, page-size ABI and package closures.
   In parallel, run the platform discovery work. **RPI-001 precedes RPI-002** for
   SBC implementation and reusable installer/hwtrace infrastructure; Pi 5's
   independent source research need not wait.
4. **SPARK-001/SPARK-002/APPLE-001/RPI-001/RPI-002/SBC-001/QUALCOMM-001:**
   fix native CPU, interrupt, DMA, storage, firmware and peripheral prerequisites.
   ARM-007 owns server/cloud/VM profiles; ARM-008 resolves legacy ABI feasibility.
5. **ARM-004/ARM-005:** deliver actual graphics/input/network/power behavior,
   complete applications, board boot media, installer and recoverable matched
   boot-set updates. A shell boot does not close these tracks.
6. **ARM-006:** qualify the exact final distribution on all required rows,
   preserve amd64 behavior, refresh all user collateral and bind publication to
   the reviewed support/evidence ledger.

## Discovery requirements for every hwtrace run

Each run needs an image/source hash, queue epoch, model/SoC/board revision,
firmware and boot-chain identities, selected ABI/DTB, expected storage and
CPU topology, and a specific hypothesis with a control. Store raw evidence
privately; export redacted summaries, not serials, licensed tables or secrets.

Before ExitBootServices, capture validated ACPI and FDT/handoff metadata in
bounded records. Record usable CPU flags/MPIDRs, interrupt topology, memory
reservations, translation/DMA mappings and the selected console. On Apple,
include the per-OS ESP and both firmware identities. On Pi, include EEPROM,
boot order, SoC stepping, RP1 where present, config/overlays and media path.
On cloud/VM targets, include provider/hypervisor, virtual devices and console.

Persist milestones before/after CPU release, at secondary entry, MMU/interrupt
initialization, check-in, scheduling and first idle/resume. A loader may use
EFI BlockIo only while Boot Services are valid. A kernel cannot use EFI runtime
before that interface is initialized. If the earliest fault precedes disk and
runtime services, qualify a suitable serial/proxy, reserved-memory or other
platform backend and document exactly which resets it survives. Cold-power
survival is a separate test. A missing trace is not a location or cause.

Use allowlisted, isolated probes with committed start/result records and data
checksums. Preserve earlier output on command timeout, panic or hard reset.
Do not make broad `sysctl -a` or live `acpidump /dev/mem` probing the only way to
learn topology. Decode bounded raw tables offline. Test full/damaged media,
foreign queue epochs, absent NVRAM, exhausted budgets and interrupted collection.
The [ARM-002 detail](arm-implementation.md#arm-002-make-hwtrace-discovery-durable-across-arm-boot-chains)
owns implementation and failure acceptance.

## Spark evidence and remaining experiments

### What is known

The published 1.5.0 and 1.5.1 kernels hung after `Starting CPU 4 (400)`.
The candidate limiting startup to four CPUs reached init again in 3.294 s on
2026-11-07. The repaired collector preserved seven readable files: it timed
out broad sysctl enumeration and continued, then last recorded ACPI starting.
There is no ACPI finish record. This is a diagnostic milestone, not an install,
full-core result or proof that ACPI caused a kernel hang.

### What the 1.5.1 result says

The bounded AP check-in wait begins after PSCI CPU_ON returns. The old last
console line alone cannot distinguish a firmware call that never returns from
a secondary that starts and then faults or idles incorrectly. Persisted
pre-call/return/entry/check-in/idle markers are the next discriminator.

### Ground truth from the DGX Spark

The live Linux reference is a separate GB10 desktop: 20 enabled/online CPUs,
PSCI, zero parking-protocol versions and an enabled `0x400` MADT entry. The
Cortex-A725 and X925 clusters, 4 KiB pages, errata configs, downstream boot
arguments and SMMU state are recorded in the research checkpoint. The ASUS
laptop's MADT flags remain to be obtained safely; its marketing description
says 18 cores while FreeBSD counted 20 entries.

### 1. Evidence from the published 1.5.1 image (no new code)

The old five-boot queue is retained as
[evidence/spark-151-queue.txt](evidence/spark-151-queue.txt): default verbose,
60-second AP wait, skip `0x400`, skip the first-cluster tail, and four-CPU
control. The first four filed no kernel record. Repeating them unchanged does
not close the early-observation gap. The later synchronous-collector control
validated preservation of completed files; ARM-002 now replaces the unsafe
probe path and adds earlier instrumentation before further CPU experiments.

### 2. Linux on the same SoC

Compare the exact pinned NVIDIA implementation with the release's FreeBSD
source, including context zero versus logical-ID handling, entry address,
conduit, exception level, cache/translation state and power/start order.
Linux source is read for behavior, not pasted into BSD contributions. Test
one changed variable at a time with a working four-CPU control.

### 3. Fix

Fix the cause established by the milestones. Separately qualify Cortex-X925
4193781 / Linux config 4118414 TLB completion handling and the distinct A725/
X925 speculative-SSBS audit. Firmware versions and per-model quirks require
matching evidence; Apple's confirmed secondary-core firmware bug is a research
precedent, not a diagnosis for Insyde/NVIDIA. A reduced-core workaround is
not full CPU acceptance and needs an explicit scope decision if proposed for release.

### 4. Beyond boot

Install to selected NVMe without losing unrelated data, boot the installed
system to the real desktop, qualify the actual renderer/input and network
traffic, and test DMA, thermals, updates and recovery. The prior blanket
exclusions of GPU/audio/suspend are now tracked explicitly under ARM-004;
unsupported features remain visible and cannot be called working. No reviewed
source demonstrates a FreeBSD Blackwell GPU/CUDA implementation.

## Final distribution validation

For **each required model/revision/firmware/ABI/media profile**, retain:

- A reproducible source/firmware/toolchain manifest and matching image/package
  hashes. Verify the actual final image's kernel, modules, boot chain, DTB,
  libraries, licenses, firmware and signed feed closure.
- Cold and warm boot, every enabled usable CPU, full usable RAM, topology and
  correct clock/entropy behavior; concurrent memory/TLB/mmap/fork stress,
  storage/network DMA and thermal/idle transitions. Determine measurable
  responsiveness and resource budgets from a retained baseline before acceptance.
- Real install to the selected SD/eMMC/USB/NVMe disk and installed boot after
  removing the installer. Test preserve-data layouts, encrypted-root input
  where offered, live desktop and network failure/recovery paths.
- Graphical login, keyboard/pointer and native clipboard, terminal, browser,
  editor, file manager and graphical package operations. Record actual
  renderer and API/performance; firmware framebuffer, software render and
  accelerated GPU are different results.
- Ethernet/Wi-Fi traffic, reconnect and driver recovery; per-model display
  hotplug, protected audio, USB, battery/lid/suspend/resume and sleep drain.
  Any unimplemented feature has its own explicit state, not an inferred pass.
- Signed package and matched boot-set upgrade/rollback from the prior supported
  release, injected interrupted/corrupt/wrong-ABI failures and recovery. Apple
  tests preserve macOS/Recovery and the owned ESP; Pi tests preserve board
  firmware layout and qualify cold boot on each selected medium.
- ARM firmware-VM coverage and physical tests as different evidence, separate
  server/cloud roles, amd64 QEMU and MSI/MacBook regressions, and all current
  docs/README/release notes/tutorial/video/slides/collateral updated to the
  actual support matrix. No private diagnostics, credentials or test keys ship.

ARM-006 closes only when the final support ledger proves the required scope.
Planning, green metadata checks, a VM build worker and this research do not
provide those hardware or lifecycle receipts.
