# Implementation and discovery work for the 1.6 ARM distribution

- **Status:** active
- **Owning queue item:** [ARM-001](active-work.md#arm-001-maintain-the-arm-platform-and-upstream-evidence-register)
- **Completion / archival evidence:** pending implementation and exact final-distribution acceptance

The [release plan](release-1.6.0.md) owns scope, target matrix, ordering and the
common release gates. The [research checkpoint](arm-research-20261107.md) gives
source revisions and the evidence behind these tasks. The original target
requirements below remain open. Separately marked software controls do not close
physical or final-distribution validation. Source research alone closes neither.

**SBC priority:** RPI-001 (Pi 4) precedes RPI-002 (Pi 5), by operator decision
on 2026-11-07. Pi 5 research can proceed concurrently; its additional RP1 and
firmware work does not delay the Pi 4 reference port.

## ARM-001 — Maintain the ARM platform and upstream evidence register

- **Priority:** P0
- **Owner:** ARM release integration
- **Depends on:** none
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/295
- **Queue:** [ARM-001](active-work.md#arm-001-maintain-the-arm-platform-and-upstream-evidence-register)

### Hwtrace and prerequisite discovery

- [ ] Enroll exact board/SoC revisions, RAM sizes, firmware, boot mode, storage path, owner and test hardware. Include every family in the release matrix; absent hardware remains an explicit dependency.
- [ ] Refresh Omarchy Mac, Rage, Asahi/Aurora, NVIDIA/NixOS, Raspberry Pi/Debian/Linux and BSD predecessors at immutable revisions; label code, proposals, measurements and hypotheses separately.

### Final implementation

- [ ] Maintain per-model prerequisite and feature states; separate physical machines, VMs and cloud instances, and stable/default from experimental branches.
- [ ] Keep original code ownership and licenses; cite Linux behavior without copying its implementation into BSD changes.

### Validation

- [ ] Every enrolled row links source identity, discovery evidence, implementation dependencies and final-image acceptance.
- [ ] Changing or dropping a target requires a recorded scope decision; an unavailable board or driver cannot silently disappear.

## ARM-002 — Make hwtrace discovery durable across ARM boot chains

- **Priority:** P0
- **Owner:** Diagnostics and owned FreeBSD loader/kernel
- **Depends on:** ARM-001
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/296
- **Queue:** [ARM-002](active-work.md#arm-002-make-hwtrace-discovery-durable-across-arm-boot-chains)

### Hwtrace and prerequisite discovery

- [ ] Capture ACPI APIC/PPTT/FADT/IORT/SRAT/SLIT and FDT/Apple handoff data before risky kernel probes, with bounded lengths, checksums, address-range validation and private raw custody.
- [ ] Measure reset and power-cycle survival of EFI variables, raw-block slots, reserved RAM and available serial/proxy transports on every firmware profile. Missing runtime NVRAM is a supported diagnostic outcome.

### Final implementation

- [ ] Add platform-selected discovery presets and pre-call/return/secondary-entry/MMU/interrupt/check-in/scheduler/idle milestones. Never invoke EFI Boot Services after ExitBootServices or assume EFI runtime is callable before its initialization.
- [ ] Replace broad sysctl -a and default acpidump /dev/mem access with isolated allowlisted probes and offline ACPI decoding. Preserve command output and status at each checkpoint; distinguish timeout, kernel stall, incomplete collection and complete capture.
- [ ] Retain synchronous FAT/checksum/readback safeguards; add recovery after interruption, foreign-epoch completion, exhausted queues, full media and trace-budget failure. Provide explicit fallback transport when earliest CPU failure precedes any disk driver.

### Validation

- [ ] Native and firmware-VM fault injection plus physical warm reset and power-cycle records preserve the last committed checkpoint and earlier files.
- [ ] A deliberately hung probe cannot erase completed evidence; early CPU and firmware-stage gaps are reported instead of inferred from absent records.

## SPARK-001 — Boot, install and run the desktop on the NVIDIA RTX Spark laptop

- **Priority:** P0
- **Owner:** Owned FreeBSD arm64 source and release integration
- **Depends on:** ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/291
- **Queue:** [SPARK-001](active-work.md#spark-001-boot-install-and-run-the-desktop-on-the-nvidia-rtx-spark-laptop)

### Hwtrace and prerequisite discovery

- [ ] Start from the four-CPU physical baseline and capture the laptop MADT enabled flags, MPIDRs, MIDRs, PPTT, IORT and firmware. Resolve its 18-core marketing versus 20 ACPI-entry discrepancy without importing the DGX count.
- [ ] Compare Linux and FreeBSD PSCI conduit/function width, context zero versus logical ID, physical entry address, EL/cache/translation state and startup order. Establish a persistent pre-call and return checkpoint before trying the next full-core boot.

### Final implementation

- [ ] Run one-variable experiments with a known-good four-CPU control; instrument already-online CPUs to distinguish a non-returning firmware call from a late secondary fault or first-idle failure. A context-zero test needs a matching secondary identification path.
- [ ] Independently implement and validate required Cortex-X925 4193781 TLBI completion handling (Linux config 4118414), and audit A725/X925 speculative-SSBS errata. Match MIDRs and all BSD TLB paths; do not call these the proven CPU4 cause.
- [ ] Repair the identified CPU, NUMA, firmware mapping or driver defect; upstream a minimal BSD change. Qualify SMMUv3/DMA, NVMe, MT7925, display, input and installed boot rather than stopping at a four-core workaround.

### Validation

- [ ] All firmware-enabled usable cores pass cold/warm boot, concurrent load, TLB/mmap/fork stress and idle transitions; core count is bound to the laptop tables.
- [ ] Exact release media installs to selected NVMe, preserves unrelated data, boots the desktop, and passes real Wi-Fi/network traffic and the shared ARM acceptance matrix. A reduced-core fallback remains a limitation until explicitly accepted.

## SPARK-002 — Qualify DGX Spark and GB10 partner systems separately

- **Priority:** P1
- **Owner:** Owned arm64 source and NVIDIA platform integration
- **Depends on:** ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/297
- **Queue:** [SPARK-002](active-work.md#spark-002-qualify-dgx-spark-and-gb10-partner-systems-separately)

### Hwtrace and prerequisite discovery

- [ ] Read a working Linux DGX baseline: exact NVIDIA source/config, effective cmdline, firmware components, topology, memory carveouts, IORT/SMMU and PCIe/EC inventory. Treat Founders Edition, Ascent GX10 and other partner boards as distinct rows.
- [ ] Investigate factory-firmware reports, CBB probe suppression, PCIe payload policy, KHO memory reservations, SVA/config-baseline mismatches and later power-daemon resets by boot stage; do not transplant Linux parameters.

### Final implementation

- [ ] Implement demonstrated BSD firmware/CPU/NUMA/IOMMU/PCIe fixes with board and MIDR qualification. Keep 4 KiB as the proven baseline; gate any 64 KiB experiment on the complete ABI/module closure.
- [ ] Qualify built-in networking, ConnectX-7 power/hotplug where fitted, storage, firmware framebuffer and EC/thermal behavior. Keep Blackwell GPU/CUDA claims open unless an actual FreeBSD implementation and runtime result exists.

### Validation

- [ ] Each named partner model boots all enabled CPUs and passes sustained CPU/memory/storage/network load on the final distribution.
- [ ] Record display renderer and thermals, model-specific firmware baseline, DMA faults and rollback/recovery; a DGX result never qualifies the N1X laptop.

## RPI-001 — Port Raspberry Pi 4 before Raspberry Pi 5

- **Priority:** P0
- **Owner:** SBC boot, owned FreeBSD source and release integration
- **Depends on:** ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/298
- **Queue:** [RPI-001](active-work.md#rpi-001-port-raspberry-pi-4-before-raspberry-pi-5)

### Software checkpoint, 2026-11-08

- [x] Pi 4 defaults: SD and USB-only FDT/GENET at 2/8 GiB, plus uncapped 8 GiB UEFI/ACPI USB pass with source `4cf77572` / kernel `d520d762`; see the [scoped evidence and candidate plan](../testing-pi-bootstrap-checkpoint-20261108.md).
- [x] Versioned D520 regular-file candidates have passed the scoped assembly/readback controls recorded in that checkpoint.
- [ ] Attended physical validation and the original final-distribution requirements remain open; software controls do not close them.

### Hwtrace and prerequisite discovery

- [ ] First SBC bring-up target by operator decision: Pi 4B; record BCM2711 stepping, RAM variant, EEPROM, power supply, U-Boot/EDK2, DTB/ACPI mode and SD/USB boot. Enroll Pi 400 and CM4 as separate carrier/model records.
- [ ] Use a known-good Debian or Debian-based Raspberry Pi OS run, upstream Linux and Raspberry Pi downstream source as behavioral references. Record exact image, resolved config, DTB/overlays, firmware and feature results rather than assuming every Debian image is equivalent.

### Final implementation

- [ ] Establish the standard SBC hwtrace SD/USB layout and deterministic firmware handoff. Match BCM2711 clocks, mailbox/interrupts, SDHCI, GENET Ethernet, xHCI PCIe/DMA and framebuffer; preserve the distinction between firmware-visible and OS-driven devices.
- [ ] Test the UEFI 3 GiB memory cap and full-RAM DMA correctness explicitly, including 4/8 GiB variants. Build native storage/network/input plus the actual desktop path, then package boot firmware and DTBs as retained inputs.
- [ ] Finish Pi 4 media, installer, installed boot and recovery first; reuse the common infrastructure for Pi 5 without treating Pi 4 drivers as RP1 support.

### Validation

- [ ] Pi 4B completes the shared exact-image install/desktop/network/update/rollback suite, cold/warm boots and full-RAM USB/storage DMA stress.
- [ ] Pi 400/CM4 extensions require their own input, carrier, network and storage evidence; Pi 4 completion does not close the Pi 5 item.

## RPI-002 — Port Raspberry Pi 5 and resolve RP1 and firmware quirks

- **Priority:** P1
- **Owner:** SBC boot and owned FreeBSD RP1/BCM2712 source
- **Depends on:** RPI-001, ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/299
- **Queue:** [RPI-002](active-work.md#rpi-002-port-raspberry-pi-5-and-resolve-rp1-and-firmware-quirks)

### Software checkpoint, 2026-11-08

- [x] Selected synthetic PCIe2 MSI-X and MSI: native USB data, message-bound interrupts, reset and finite UART overflow recovery pass with source `4cf77572` / kernel `d520d762`; see the [scoped evidence and candidate plan](../testing-pi-bootstrap-checkpoint-20261108.md).
- [x] Versioned D520 regular-file candidates have passed the scoped assembly/readback controls recorded in that checkpoint.
- [ ] Attended physical validation and the original final-distribution requirements remain open; software controls do not close them.

### Hwtrace and prerequisite discovery

- [ ] Follow Pi 4 in the SBC implementation queue while researching Pi 5 independently. Inventory C1/D0 stepping, RAM, EEPROM, power/cooling, RP1 and SD/USB/NVMe paths; include CM5 and Pi 500-family carrier/input differences.
- [ ] Compare working Debian/Raspberry Pi OS images, upstream Linux and Raspberry Pi downstream RP1/BCM2712 drivers and bindings. Preserve the reference kernel/config/DTB and EEPROM identities; distinguish mainline gaps from downstream support.
- [ ] Investigate the unmaintained UEFI reference, newer EEPROM display regressions, missing runtime-variable persistence and ACPI/FDT differences. Compare Linux bcm2711 4 KiB and bcm2712 16 KiB builds without assuming Pi 5 requires 16 KiB.

### Final implementation

- [ ] Implement the required RP1 PCIe nexus, interrupts, clock/reset, USB, pinctrl/PWM and Cadence GEM Ethernet support, plus SD/NVMe, display and cooling. Do not equate a DTB import or old UEFI boot report with these drivers.
- [ ] Choose and retain a maintained boot path per revision; qualify fallback trace persistence without EFI variables, boot-order behavior and power-cycle recovery.
- [ ] Deliver the board-specific final image and installed boot, default application/graphics stack and working network; document peripherals still under development per model.

### Validation

- [ ] Pi 5 C1 and D0 plus enrolled RAM variants pass final-image boot, full memory/DMA, SD/USB/NVMe, desktop/input, network, thermal and update/rollback tests.
- [ ] RP1 Ethernet and cooling are exercised natively; USB adapters or manual fan settings do not establish built-in-device acceptance. CM5/Pi 500 results remain separate.

## APPLE-001 — Bring up native Apple Silicon across board generations

- **Priority:** P0
- **Owner:** Owned FreeBSD Apple platform and boot integration
- **Depends on:** ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/300
- **Queue:** [APPLE-001](active-work.md#apple-001-bring-up-native-apple-silicon-across-board-generations)

### Hwtrace and prerequisite discovery

- [ ] Enroll M1/M2 reference Macs first and maintain explicit M3/M4/A18 Pro/M5 and emerging-generation rows. Capture board/SoC IDs, ADT/FDT, AIC/DART generation, enabled cores, reservations, firmware and per-OS ESP/Recovery ownership.
- [ ] Record both system firmware and the OS stub stage-2 firmware. Investigate the Apple-confirmed M5 Pro/Max/Ultra raw-boot core restriction using the newer-stub J716s report; do not assume a main macOS update refreshes the stub or apply beta firmware automatically.
- [ ] Use m1n1 proxy/tethered capture and BSD predecessors where appropriate. Separate the default Asahi matrix, Aurora work and unmerged proposals; inspect the latest results rather than an early dead-end claim.

### Final implementation

- [ ] Deliver a recoverable APFS-stub/m1n1/U-Boot/FreeBSD EFI path that preserves macOS and Recovery, identifies the correct ESP and binds board DTB, kernel, firmware payload and loader versions. No generic whole-disk wipe.
- [ ] Audit existing FreeBSD T8103 support, then implement missing AIC generations, CPU start/idle, DART/busdma, ANS/NVMe, RTKit/SMC and USB/HID before claiming later SoCs. Check entry trampolines and reserved regions in untethered boots.
- [ ] Implement graphics/display, input and platform services under ARM-004; examine Apple M4+ WFI register/SIMD state preservation by MIDR independently of PSCI experiments on NVIDIA. Keep new-generation firmware/display/GPU prerequisites open until proven.

### Validation

- [ ] Each enrolled Mac passes native cold and untethered boot, all enabled cores, idle/SIMD stress, storage and working input before encrypted-root prompts; a QEMU/HVF guest is a different result.
- [ ] Exact distribution installs without destroying Apple recovery, reaches a usable desktop and network, updates and rolls back its matched boot set, and passes per-model power/peripheral validation.

## SBC-001 — Port other popular ARM boards with model-specific profiles

- **Priority:** P1
- **Owner:** Owned FreeBSD FDT/ACPI board support
- **Depends on:** ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/301
- **Queue:** [SBC-001](active-work.md#sbc-001-port-other-popular-arm-boards-with-model-specific-profiles)

### Hwtrace and prerequisite discovery

- [ ] Enroll ROCK 5B and Orange Pi 5/5 Plus (RK3588), RK3399/RK356x Pine64/Radxa boards, CIX Orion O6-class boards, and representative Allwinner, Amlogic and NXP i.MX8/MNT Reform boards. Record exact carrier and SoC, not just the family name.
- [ ] Compare maintained board firmware, Linux bindings and BSD implementations for regulator/clock/reset, CPU, memory, PCIe/USB/storage and display/network dependencies. Treat Windows-oriented RK3588 ACPI and mainline/vendor FDT modes as separate profiles.

### Final implementation

- [ ] Implement model-specific boot containers/DTBs, clocks/regulators, interrupts, DMA, storage, network and display. Preserve firmware-storage reservations and document runtime NVRAM limitations on SD/eMMC firmware.
- [ ] Qualify external peripherals and safe board recovery without reusing another model firmware or voltage tables merely because its SoC matches. Integrate each board into the common media and desktop tracks.

### Validation

- [ ] Every enrolled board has physical final-image results for its own firmware/mode, media, full RAM, I/O, desktop and network.
- [ ] Neither RK3588 firmware support nor an OpenBSD/Linux result qualifies FreeBSD; unresolved board prerequisites remain visible in 1.6.

## QUALCOMM-001 — Bring up Qualcomm ARM laptops as distinct hardware targets

- **Priority:** P1
- **Owner:** Owned FreeBSD Qualcomm platform and desktop integration
- **Depends on:** ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/302
- **Queue:** [QUALCOMM-001](active-work.md#qualcomm-001-bring-up-qualcomm-arm-laptops-as-distinct-hardware-targets)

### Hwtrace and prerequisite discovery

- [ ] Enroll a Snapdragon 8cx Gen3/X13s and Snapdragon X Elite/Plus laptop profile with exact model and SoC. Inventory firmware, ACPI versus Linux-selected DTB, PSCI, memory/SMMU, UFS/NVMe, USB/HID, WLAN and display.
- [ ] Use upstream Linux/board firmware and BSD predecessor evidence. Existing FreeBSD Qualcomm router drivers or aarch64 architecture support are not evidence for an Oryon laptop.

### Final implementation

- [ ] Implement missing interrupt/CPU/clock/reset/IOMMU and storage/input prerequisites, then native GPU/display and firmware-dependent networking. Retain OEM recovery and a known-good boot entry.
- [ ] Integrate native installed boot, graphical installer, battery/lid/suspend and public firmware/package dependencies into the final release profiles.

### Validation

- [ ] Each model boots all enabled cores, installs, reaches a usable desktop, passes network traffic, device DMA and sleep/resume tests on final media.
- [ ] Document firmware and driver blockers by model rather than representing VM or another Snapdragon generation as acceptance.

## ARM-003 — Qualify ARM base, page-size ABIs and package closures

- **Priority:** P0
- **Owner:** FreeBSD base/ports, native build and package release
- **Depends on:** ARM-001
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/303
- **Queue:** [ARM-003](active-work.md#arm-003-qualify-arm-base-page-size-abis-and-package-closures)

### Hwtrace and prerequisite discovery

- [ ] Inventory CPU translation granules, IOMMU granules, ELF alignment and actual page size for every profile; distinguish Apple 16 KiB DMA constraints, working DGX 4 KiB, optional DGX 64 KiB and Pi 5 optimized Linux 16 KiB from its 4 KiB-capable baseline.
- [ ] Capture resolved kernel configs, effective boot arguments, dependencies and downstream patch results. Reject silent config-delta losses, patch rejects and wrong target builds.

### Final implementation

- [ ] Choose supported FreeBSD kernel/world/module/package variants through measured compatibility, retaining exact toolchain and source identities. Do not assume Linux user4k or FEX/muvm behavior exists in FreeBSD.
- [ ] Build and qualify the complete signed base, desktop, compatibility, DRM/firmware, checkout and application closures for each admitted ABI. Check ELF segment alignment, mmap/shared-memory/JIT and DMA behavior.
- [ ] Require native aarch64 worker and actual target tests; distinguish cross-build correctness from emulated or hardware runtime. Keep variants isolated in feeds and upgrade selection.

### Validation

- [ ] Native boot and application evidence covers each admitted page-size/ABI variant; incompatible modules and feeds are refused before installation.
- [ ] Package solving and offline/online installs use the pinned signed closure, with correct missing-application reporting and no x86-only substitutes claimed as native ARM.

## ARM-004 — Deliver ARM graphics, input, network and power integration

- **Priority:** P0
- **Owner:** Desktop, compatibility, owned drivers and ports
- **Depends on:** ARM-003, ARM-002
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/304
- **Queue:** [ARM-004](active-work.md#arm-004-deliver-arm-graphics-input-network-and-power-integration)

### Hwtrace and prerequisite discovery

- [ ] Record real DRM/KMS renderer/API capabilities and firmware-framebuffer fallback separately; inventory keyboard/trackpad/external USB, WLAN/Ethernet, audio, cameras, Bluetooth, display outputs and power features per board.
- [ ] Carry forward Mac HID registration order, early encrypted-root input, Broadcom scan-versus-association/resume distinctions, speaker protection and measured sleep drain; separate all Intel T2-only workarounds.

### Final implementation

- [ ] Implement missing native drivers and package matching firmware/Mesa/compositor components; qualify software rendering only with a working display/input path and explicitly record its performance/limitations.
- [ ] Wire FreeBSD services for network, battery/thermals, lid, safe speaker audio and recovery after peripheral/display loss. Gate features by capability and device revision, with bounded failure behavior and no Linux service substitution.
- [ ] Provide default browser, terminal, editor, file manager and graphical package manager workflows on every desktop profile; keep headless server roles separately declared.

### Validation

- [ ] Real input, native clipboard, display/hotplug, renderer evidence and actual default applications work on each final desktop profile.
- [ ] Network transfers, Wi-Fi reconnect, audio safety, USB/input after boot/resume and measured idle/suspend drain pass per-model tests; enumerated devices alone never pass.

## ARM-005 — Ship coherent ARM discovery, installer and recovery media

- **Priority:** P0
- **Owner:** Installer, verified boot and release engineering
- **Depends on:** ARM-001, ARM-002, ARM-003
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/305
- **Queue:** [ARM-005](active-work.md#arm-005-ship-coherent-arm-discovery-installer-and-recovery-media)

### Hwtrace and prerequisite discovery

- [ ] Determine board-specific first-stage prerequisites, EFI/FDT/ACPI boot paths, owned ESP, disk/media layout and firmware redistribution rights. Enumerate raw SD/USB, EFI ISO and platform bootstrap outputs explicitly.
- [ ] Bind source, firmware, DTBs, board revision, ABI, loader/kernel/modules and signed package closures in a manifest; keep diagnostics separate from the install/live product.

### Final implementation

- [ ] Build platform-selected hwtrace and install/live media without pretending one generic USB image provisions every ARM platform. Reuse common payloads while retaining board boot containers and Apple recovery ownership.
- [ ] Implement SD/eMMC/USB/NVMe selection, preserve-data installs and installed boot, with clear model discovery and unsupported-device explanations. Wrong firmware/board/ABI combinations fail before destructive writes.
- [ ] Qualify signed upgrades/rollback and atomic matched boot-set updates (loader, DTB, kernel, modules and firmware). Retain recovery entries and diagnostics; preserve published bytes and follow the one-session signing rule.

### Validation

- [ ] Fresh and retained-data installs, installed cold boot, interrupted install/download, checksum/signature/ABI rejection and boot-set rollback pass on exact final media per board.
- [ ] Release manifests and public feeds match downloaded artifacts; packaged image contents and every distributed firmware/license are verified, with no test keys or private captures.

## ARM-006 — Qualify and document the complete 1.6 ARM distribution

- **Priority:** P0
- **Owner:** Release QA and documentation
- **Depends on:** ARM-001, ARM-002, ARM-003, ARM-004, ARM-005
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/306
- **Queue:** [ARM-006](active-work.md#arm-006-qualify-and-document-the-complete-16-arm-distribution)

### Hwtrace and prerequisite discovery

- [ ] Allocate a real worker/owner and baseline for every enrolled matrix row, including Pi 4 before Pi 5. Keep evidence identities, missing hardware and upstream prerequisites visible.
- [ ] Design failure cases for reset persistence, malformed firmware tables, NVRAM/media exhaustion, probe hangs, corrupt downloads, wrong ABI, loss of network/input and interrupted upgrades.

### Final implementation

- [ ] Run the discovery/driver matrix and the final exact-image suite as distinct gates; rerun affected checks after changes to signed inputs. Keep native hardware, VM, cloud and synthetic evidence separate.
- [ ] Refresh hardware support tables, getting-started/install/recovery guides, release notes, README, tutorial/video/slides and other collateral around the actual 1.6 artifacts and limitations. Audit all current support/version claims without rewriting historical records.
- [ ] Retain amd64 install/desktop/network regressions and the required release security/signing workflow. Plan publication only after every claimed target has the required release ledger evidence.

### Validation

- [ ] All required per-target final-distribution checklists have exact artifact/firmware/source identifiers and observed results; no research, four-core workaround or installer exit substitutes for acceptance.
- [ ] Every unresolved target or feature remains explicitly open; it cannot be silently dropped to make the release green. Published support claims match the reviewed ledger and signed downloaded artifacts.

## ARM-007 — Qualify ARM servers, cloud systems and virtual machines

- **Priority:** P1
- **Owner:** Server platform, native workers and release QA
- **Depends on:** ARM-002, ARM-003, ARM-005
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/307
- **Queue:** [ARM-007](active-work.md#arm-007-qualify-arm-servers-cloud-systems-and-virtual-machines)

### Hwtrace and prerequisite discovery

- [ ] Enroll an Ampere Altra/ARM server profile, AWS Graviton, and a supported ARM cloud alternative; separately retain QEMU/HVF/KVM/UTM and VMware Fusion guest profiles. Record provider instance, virtual firmware, devices and console/recovery channel.
- [ ] Discover NUMA, GIC/ITS, SMMU, PCIe, NVMe, virtio/ENA/network, balloon/entropy/timekeeping and virtual GPU dependencies. A VM on Apple hardware does not test native Apple SoC support.

### Final implementation

- [ ] Implement native boot, cloud/disk-image provisioning, serial/provider-console discovery and recovery, network/storage/device drivers and signed package/bootstrap workflows. Validate large-memory/core-count and page-size behavior.
- [ ] Qualify headless operation and remote administration explicitly; where a desktop profile is offered, test the real virtual/physical DRM path and input rather than reusing a console-only build worker result.

### Validation

- [ ] Exact provider/physical/VM profiles pass boot, all expected CPUs/memory, sustained I/O/network load, timekeeping, update and recovery.
- [ ] Physical-server, cloud-instance and VM results retain separate scope; desktop claims require the shared graphical acceptance.

## ARM-008 — Resolve legacy ARM32 coverage and feasibility explicitly

- **Priority:** P2
- **Owner:** Architecture and base/ports release engineering
- **Depends on:** ARM-001
- **Release target:** 1.6.0
- **GitHub issue:** https://github.com/jordanhubbard/daemonarchy/issues/308
- **Queue:** [ARM-008](active-work.md#arm-008-resolve-legacy-arm32-coverage-and-feasibility-explicitly)

### Hwtrace and prerequisite discovery

- [ ] Inventory still-popular ARMv7 boards and older Pi/Zero/BeagleBone-class devices separately from aarch64-capable Pi 3/Zero 2. Record available FreeBSD versions, toolchains, drivers, RAM/storage and intended desktop or headless role.
- [ ] FreeBSD lists ARMv7 separately and newer releases do not support ARMv6. Establish the actual native baseline and product feasibility; do not relabel aarch64 support as all ARM.

### Final implementation

- [ ] Prototype an ARMv7 base/kernel/boot/package pipeline only against an admitted maintained FreeBSD baseline, and measure whether the complete distribution is usable within device resources.
- [ ] Present any unsupported ARMv6 or infeasible desktop target as an explicit scope decision with source evidence and prerequisites; retain it in the inventory rather than inventing successful coverage.

### Validation

- [ ] Each claimed ARM32 target has native boot, working application/role, package/update and recovery evidence for its actual ABI.
- [ ] Unsupported architectures and unresolved feasibility are disclosed in the 1.6 support matrix and are never hidden by the ARM theme.
