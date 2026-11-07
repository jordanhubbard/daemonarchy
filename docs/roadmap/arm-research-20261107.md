# ARM research for the 1.6 distribution, 2026-11-07

- **Status:** active
- **Owning queue item:** [ARM-001](active-work.md#arm-001-maintain-the-arm-platform-and-upstream-evidence-register)
- **Completion / archival evidence:** research checkpoint below; target implementation and acceptance remain open

This records the requested investigation of `omacom/omarchy-mac` and
`RageLtd/linux-dgx-spark`, their directly relevant predecessors, and additional
sources needed for Raspberry Pi 5 and the broader ARM scope. The
[release plan](release-1.6.0.md) converts the findings into work and gates.
This is source research, not a FreeBSD driver port or new hardware qualification.

## Sources and method

Snapshots inspected on 2026-11-07:

| Source | Revision / scope inspected | Evidence boundary |
| --- | --- | --- |
| [Omarchy Mac quattro](https://github.com/omacom/omarchy-mac/tree/7cb792ebafe08505f2617b28bb866da4732d3c1a) | `7cb792ebafe08505f2617b28bb866da4732d3c1a`; Apple hardware scripts, package-source policy, E2E collector, install/update docs | Desktop/distribution integration on an existing Linux boot stack |
| [Omarchy Mac quattro-upstream](https://github.com/omacom/omarchy-mac/tree/a76179cdcf1e844251eecac2708b687c486aa497) | `a76179cdcf1e844251eecac2708b687c486aa497`; compared with default branch; 249 branch names and 760 issue/PR records surveyed | Branches diverge; closed PRs are not necessarily merged |
| [RageLtd linux-dgx-spark](https://github.com/RageLtd/linux-dgx-spark/tree/2f74023ce225559d1da4d71795274dedab1fc32c) | `2f74023ce225559d1da4d71795274dedab1fc32c`; all five commits, build/config scripts, PKGBUILD, config and development log; no issue/PR records | Package build evidence; its development log still requests hardware boot testing |
| [nixos-dgx-spark](https://github.com/graham33/nixos-dgx-spark/tree/c646a19a5df3316c1b0e79e2025d59f8deb704de) | `c646a19a5df3316c1b0e79e2025d59f8deb704de`; kernel module/config, boot check, firmware notes; 198 issue/PR records surveyed | More recent NVIDIA source lineage; selected reports are hardware observations by their authors |
| [NVIDIA kernel](https://github.com/NVIDIA/NV-Kernels/tree/ae07646a606b3f18707246b0762464452cb40cbe) | `ae07646a606b3f18707246b0762464452cb40cbe`; PSCI, SMP, secondary entry, errata, TLB maintenance, ACPI IORT/SRAT and arm64 boot requirements | Read source for behavior; do not copy Linux implementations into BSD contributions |
| [Aurora Linux](https://github.com/omacom/linux-aurora/tree/6a08a08e57558083f552733a5276d71b1a4d8ff6) | `6a08a08e57558083f552733a5276d71b1a4d8ff6`; 404 issue/PR records surveyed, selected CPU/idle/firmware discussions and merged change #147 | A separate development fork; its results are not Asahi-wide or FreeBSD acceptance |
| [M5 Pro bring-up](https://github.com/rolotrealanis98/m5pro-linux/tree/14644aca21263af9b702acc11631453737082d94) | `14644aca21263af9b702acc11631453737082d94`; dated status, redacted SMP log and follow-up discussion | One J716s machine; report distinguishes hardware-tested, merely booted and design-only work |
| [Asahi documentation](https://github.com/AsahiLinux/docs/tree/ed6f9d6ac4ac49a09924224ac07e7341a71e1e45) | `ed6f9d6ac4ac49a09924224ac07e7341a71e1e45`; boot interoperability, m1n1, page-size constraints, distribution guidance and generation feature matrices | Official Asahi status and platform contracts; refresh before implementation |
| [Pi 5 UEFI](https://github.com/worproject/rpi5-uefi/tree/a6135b06d661b5f11bbf4bd742b42a1919b264dc) | `a6135b06d661b5f11bbf4bd742b42a1919b264dc`; maintenance notice and hardware/OS tables | README ends support even though GitHub's archived flag was false when checked |
| [Pi 4 UEFI](https://github.com/pftf/RPi4/tree/873b00dfd6f437a7d91950fe0695f7e9f75d93c6) | `873b00dfd6f437a7d91950fe0695f7e9f75d93c6`; boot modes and RAM/DMA constraints | Different firmware and controller baseline from Pi 5 |
| [Raspberry Pi Linux](https://github.com/raspberrypi/linux/tree/31a34885388835dce2460744d7961f2b9e7dc416) | `rpi-6.18.y` at `31a34885388835dce2460744d7961f2b9e7dc416`; Pi 4/5 arm64 defconfigs and official kernel-build documentation; 6.12 reference at `2569533d6c33c15231fbc21704c87fcebc67173c` | Downstream Linux reference; compare against resolved Debian/Pi OS binaries and upstream Linux, not just a moving branch name |
| [RK3588 UEFI](https://github.com/edk2-porting/edk2-rk3588/tree/2f3f8265590f77901ac6a1af5c963f957a844158) | `2f3f8265590f77901ac6a1af5c963f957a844158`; board, firmware and ACPI/FDT support matrices | Firmware functionality is distinct from each OS's driver support |

Issue/PR **indices** were surveyed and the cited conversations read; this is not
a claim to have validated every proposal or every discussion's attachment.
Raw captures remain private. Public records omit serials, MAC addresses,
credentials, licensed ACPI payloads and private worker addresses.

## NVIDIA: concrete comparisons for SPARK-001 and SPARK-002

1. **Follow the source chain, not just the Arch package name.** Rage's checked-in
   metadata names NVIDIA's 6.17 source series; its generated config comes from
   NixOS deltas. The newer NixOS pin names NVIDIA's 7.0.14 source through an
   immutable commit. Its [source selector](https://github.com/graham33/nixos-dgx-spark/blob/c646a19a5df3316c1b0e79e2025d59f8deb704de/kernel-configs/nvidia-kernel-source.nix)
   warns that downstream branch heads are rewritten. Record original source,
   downstream patch series, resolved configuration and actual boot arguments.
   Rage's [PKGBUILD](https://github.com/RageLtd/linux-dgx-spark/blob/2f74023/PKGBUILD)
   tolerates patch failures with `|| true`: a completed package is not proof that
   every intended patch applied. Future comparison builds must reject unexplained
   rejects and preserve the effective source/config hashes.
2. **PSCI context differs.** NVIDIA's
   [arm64 PSCI entry](https://github.com/NVIDIA/NV-Kernels/blob/ae07646a606b3f18707246b0762464452cb40cbe/arch/arm64/kernel/psci.c)
   supplies the secondary entry's physical address; the
   [firmware wrapper](https://github.com/NVIDIA/NV-Kernels/blob/ae07646a606b3f18707246b0762464452cb40cbe/drivers/firmware/psci/psci.c)
   supplies zero as context. FreeBSD uses a logical CPU ID. Both are legitimate
   PSCI designs; the difference is a controlled experiment, not a proven defect.
   Compare conduit/function width, MPIDR, entry address/alignment, context,
   exception level, translation/cache state, barriers and the CPU-start order.
   A different context requires an entry path that can identify the CPU safely;
   changing only the argument can break FreeBSD's secondary lookup.
3. **Two errata classes must not be conflated.** NVIDIA's
   [errata table](https://github.com/NVIDIA/NV-Kernels/blob/ae07646a606b3f18707246b0762464452cb40cbe/Documentation/arch/arm64/silicon-errata.rst)
   maps Cortex-X925 erratum **4193781** to config **ARM64_ERRATUM_4118414**.
   The [CPU matching](https://github.com/NVIDIA/NV-Kernels/blob/ae07646a606b3f18707246b0762464452cb40cbe/arch/arm64/kernel/cpu_errata.c)
   and [TLB completion path](https://github.com/NVIDIA/NV-Kernels/blob/ae07646a606b3f18707246b0762464452cb40cbe/arch/arm64/include/asm/tlbflush.h)
   implement an additional invalidation/completion sequence, not merely an extra
   delay. The same table lists Cortex-A725 **3456106** and X925 **3324334** under
   **3194386**, the speculative-SSBS class; that is a separate audit. Neither
   proves why the fifth A725 stalls. Audit every affected BSD TLB path and
   every online CPU's MIDR, including heterogeneous and late-online cases.
4. **Effective settings matter.** The working lab DGX was read live: Linux
   `7.0.0-1019-nvidia`, 4 KiB pages, both erratum config options above enabled,
   20 online CPUs, 20 enabled MADT GICC entries and parking version zero throughout.
   MPIDR `0x400` is enabled. This rules out a parking-protocol requirement on
   that DGX; the laptop's own table still must be captured. Its effective command
   line includes `iommu.passthrough=0`, overriding the Nix config's passthrough
   default. Do not prescribe disabling translation from a config fragment alone.
5. **Firmware is part of the baseline.** NixOS
   [issue #32](https://github.com/graham33/nixos-dgx-spark/issues/32#issuecomment-4182117621)
   reports other distributions booting after a DGX firmware update; the original
   reporter changed both build host and firmware, so it is not a clean causal
   A/B test. NVIDIA's [release notes](https://docs.nvidia.com/dgx/dgx-spark/release-notes.html)
   explicitly limit their firmware-version table to Founders Edition. Capture
   UEFI, EC, SoC, PD and board identifiers separately. Never apply DGX FE firmware
   instructions to the ASUS laptop merely because both are ARM NVIDIA systems.
6. **Downstream boot workarounds are leads with different stages.** The Nix
   [module](https://github.com/graham33/nixos-dgx-spark/blob/c646a19a5df3316c1b0e79e2025d59f8deb704de/modules/dgx-spark.nix)
   mirrors `pci=pcie_bus_safe`, suppresses the Tegra CBB probe, and disables Kexec
   HandOver. All three were also present on the working DGX. PCIe payload policy,
   shared-fabric probing and memory reservations deserve review; Linux parameter
   strings are not FreeBSD tunables. KHO's long-term memory-pinning issue and
   [system76-power's later boot reset](https://github.com/graham33/nixos-dgx-spark/pull/196)
   do not establish a pre-userland PSCI hang's cause.
7. **Drivers and packaging still need separate work.** Rage enables simpledrm
   early and ships an uncompressed ARM64 image for Limine. It explicitly adds
   MT7925 and MediaTek PCIe hotplug after the baseline config; the committed base
   config alone therefore understates the final selection. SMMUv3/SVA, IORT
   mappings, ConnectX-7 power/hotplug and FF-A EC support are independent bring-up
   areas. Nix [issue #198](https://github.com/graham33/nixos-dgx-spark/issues/198)
   reports a config-delta/baseline mismatch in SVA: prove the resolved closure.
   Its [boot VM check](https://github.com/graham33/nixos-dgx-spark/blob/c646a19a5df3316c1b0e79e2025d59f8deb704de/checks/dgx-spark-boot-vm.nix)
   excludes physical GPU behavior. No reviewed source establishes a FreeBSD
   Blackwell GPU or CUDA implementation. The 64 KiB variant remains an experiment;
   the live 4 KiB baseline disproves any assumption that GB10 requires 64 KiB to boot.

## Apple: useful mechanisms and important separations

- **Omarchy is above the boot/kernel layer.** The default Mac branch installs on
  Asahi ALARM. Its `install/hardware/apple/` directory also contains Intel-only
  T2, older SPI-keyboard and NVMe suspend scripts. Gate on architecture, exact
  SoC/board and driver capability; never apply `intel_iommu` or T2 assumptions
  to Apple Silicon. Its [HID race repair](https://github.com/omacom/omarchy-mac/blob/7cb792ebafe08505f2617b28bb866da4732d3c1a/install/hardware/apple/fix-asahi-hid-race.sh)
  moves the relevant drivers before input-device registration. This is a useful
  ordering requirement for FreeBSD's installer and encrypted-root keyboard path,
  not a systemd script to transplant.
- **A USB stick is not the initial Apple boot provisioner.** Asahi's
  [interoperability contract](https://asahilinux.org/docs/platform/open-os-interop/)
  describes per-OS APFS stub/Recovery policy, m1n1 stages and an OS-owned ESP
  identified through `asahi,efi-system-partition`. Its
  [m1n1 guide](https://asahilinux.org/docs/sw/m1n1-user-guide/)
  documents stage-2 payload/DTB selection and USB proxy/hypervisor tools. Keep the
  macOS recovery path, bind each DTB and loader to the exact board, preserve
  firmware-provided reservations and define recovery from a bad stage-2 update.
- **A confirmed firmware precedent now exists.** Apple's
  [macOS 27.3 beta release notes](https://developer.apple.com/documentation/macos-release-notes/macos-27_3-release-notes)
  identify a third-party raw-boot secondary-core restriction on M5 Pro/Max/Ultra
  (182898702 / FB23916610). The
  [J716s report and SMP log](https://github.com/rolotrealanis98/m5pro-linux/blob/14644aca21263af9b702acc11631453737082d94/docs/status-2026-11-05.md)
  distinguish system firmware from the OS stub's stage-2 firmware, and report
  all 18 CPUs after rebuilding the stub from newer firmware. The untethered
  path also needs relocation/entry-trampoline reservations. This supports a
  firmware/handoff experiment design; it does not show the NVIDIA laptop has
  the same bug. The cited Apple release is beta, not an instruction to upgrade
  an operator's main machine or rewrite its boot policy.
- **Read the end of an investigation.** Aurora
  [issue #293](https://github.com/omacom/linux-aurora/issues/293)
  contains an early claim that secondary-core execution could not be enabled,
  followed by the firmware result above and later feature reports. Its
  [November 7 follow-up](https://github.com/omacom/linux-aurora/issues/293#issuecomment-6710416717)
  describes idle, SMC, sleep and wireless work on one J716s. These are model-
  and revision-specific reports; the older status file's design-only entries
  must not be promoted wholesale to current tested support.
- **CPU idle is another distinct failure boundary.** Merged Aurora
  [PR #147](https://github.com/omacom/linux-aurora/pull/147)
  selects a register-preserving WFI path and suppresses timed waits on affected
  Apple M4+ cores. Plan milestones before and after secondary entry, GIC/AIC,
  check-in, scheduling and first idle/resume. Audit register and SIMD preservation
  on Apple by MIDR; do not apply this vendor-specific behavior to Cortex-A725/X925.
- **Generations and forks have different status.** Official
  [M1](https://asahilinux.org/docs/platform/feature-support/m1/),
  [M2](https://asahilinux.org/docs/platform/feature-support/m2/),
  [M3](https://asahilinux.org/docs/platform/feature-support/m3/),
  [M4/A18](https://asahilinux.org/docs/platform/feature-support/m4/) and
  [M5](https://asahilinux.org/docs/platform/feature-support/m5/) tables separate
  stable, work-in-progress and unstarted blocks. Aurora has additional work.
  Mac [PR #343](https://github.com/omacom/omarchy-mac/pull/343) is **closed without
  merge**; its generation detection and software-rendering proposal is useful
  design evidence, not shipped default-branch support. Software rendering still
  requires a working display/compositor path. Existing FreeBSD `std.apple`,
  AIC, pinctrl, watchdog and UART source is a starting point, not proof of
  complete M1 support, later AIC generations, DART, ANS/NVMe or AGX graphics.
  See the retained [FreeBSD Apple platform config](https://github.com/jordanhubbard/daemonarchy-src/blob/cb38d6498a24/sys/arm64/conf/std.apple)
  and its actual driver/dependency closure before deciding what must be ported.
- **Page size is an ABI and DMA problem.** Asahi's
  [page-size explanation](https://asahilinux.org/docs/sw/broken-software/)
  describes 16 KiB IOMMU alignment and incompatible ELF load alignment.
  Measure CPU, IOMMU and userspace granules separately; qualify the complete
  FreeBSD base/modules/pkg closure and mmap/JIT/device-DMA behavior. Linux's
  `muvm`, FEX or experimental userspace-page options are not FreeBSD fixes.
- **Peripheral presence is not acceptance.** The Mac
  [audio integration](https://github.com/omacom/omarchy-mac/blob/7cb792ebafe08505f2617b28bb866da4732d3c1a/install/hardware/apple/audio.sh)
  includes speaker-protection requirements. Wi-Fi
  [resume issue #197](https://github.com/omacom/omarchy-mac/issues/197),
  [backend issue #781](https://github.com/omacom/omarchy-mac/issues/781) and
  [sleep-drain issue #779](https://github.com/omacom/omarchy-mac/issues/779)
  show why association, scan results, wake-up and usable battery life need
  different checks. [Issue #743](https://github.com/omacom/omarchy-mac/issues/743)
  distinguishes a visible passphrase prompt from an actually usable USB keyboard.
  Use FreeBSD drivers/services and per-chip evidence; keep unqualified speakers muted.
- **Carry forward the evidence discipline.** The Mac
  [E2E collector](https://github.com/omacom/omarchy-mac/blob/7cb792ebafe08505f2617b28bb866da4732d3c1a/docs/e2e-collector.md)
  separates identity, detected devices and human-verified behavior, and preserves
  partial/redacted results. Its
  [package-source policy](https://github.com/omacom/omarchy-mac/blob/7cb792ebafe08505f2617b28bb866da4732d3c1a/docs/arm-package-sources.md)
  illustrates a coherent graphics-stack selection. Apply those requirements to
  signed FreeBSD feeds, not Arch/AUR packages. A Mac VM remains a separate target.

## Raspberry Pi and other ARM families

**Operator ordering:** Pi 4 is an additional, independent porting target and
precedes Pi 5. Use Pi 4B to establish the SBC boot/media/hwtrace/installer path;
keep Pi 400 and CM4 carrier variants separate. This priority does not remove
Pi 5, and Pi 5 source research can proceed without waiting for Pi 4 acceptance.

Use both Debian Linux and the Debian-based Raspberry Pi OS as reference
systems, with the exact image and actually running kernel/config/firmware
recorded. The [Raspberry Pi OS documentation](https://www.raspberrypi.com/documentation/computers/os.html)
describes that Debian lineage; the
[Debian image test ledger](https://raspi.debian.net/tested-images/) records
per-model and per-image observations, including differing Pi 400 display
results. Those older records are not a current blanket qualification of all
Debian images or peripherals. The Debian wiki returned HTTP 403 during this
pass; no claim here depends on having read its inaccessible content.

Raspberry Pi's [kernel guide](https://www.raspberrypi.com/documentation/computers/linux_kernel.html)
distinguishes `bcm2711_defconfig`/`kernel8.img` (4 KiB, including Pi 4 and usable
on Pi 5) from the Pi 5-optimized `bcm2712_defconfig`/`kernel_2712.img` (16 KiB).
The checked
[Pi 4 config](https://github.com/raspberrypi/linux/blob/31a34885388835dce2460744d7961f2b9e7dc416/arch/arm64/configs/bcm2711_defconfig)
and [Pi 5 config](https://github.com/raspberrypi/linux/blob/31a34885388835dce2460744d7961f2b9e7dc416/arch/arm64/configs/bcm2712_defconfig)
also identify memory/CPU, PCIe, USB, GENET, Broadcom wireless, display/V3D and
thermal dependencies. They are research inputs for separate FreeBSD drivers
and bindings, not configurations that can be applied to a BSD kernel.

Pi 4 [UEFI documentation](https://github.com/pftf/RPi4/blob/873b00dfd6f437a7d91950fe0695f7e9f75d93c6/Readme.md)
defaults to a 3 GiB RAM cap because full-memory DMA needs OS support. Test
4/8 GiB boards with the intended cap policy and full DMA address range rather
than counting a limited-memory boot as complete. Investigate BCM2711 mailbox,
SDHCI, GENET and xHCI/PCIe handoff independently of Pi 5's RP1.

The [Pi 5 UEFI README](https://github.com/worproject/rpi5-uefi/blob/a6135b06d661b5f11bbf4bd742b42a1919b264dc/README.md)
ends maintenance, limits its tested hardware to BCM2712 C1, and reports D0/newer
EEPROM display problems. Its OS table lists an older FreeBSD boot, but its UEFI
table leaves RP1 Ethernet/GPIO/PWM and proper EEPROM-backed NVRAM incomplete.
None of that qualifies a present-day Pi 5 distribution. Capture stepping,
RAM, EEPROM, firmware, ACPI/FDT mode, RP1 revision and media path; test C1/D0
and large-memory variants separately. Do not rely exclusively on EFI variables
for early trace survival. Validate SD, USB and NVMe boot separately.

Raspberry Pi's [boot documentation](https://github.com/raspberrypi/documentation/blob/21d772e7ee022e36a8f43c3ee75e20ca359fb832/documentation/asciidoc/computers/config_txt/boot.adoc)
requires a Pi 5 `config.txt` and describes firmware/RP1 handoff. FreeBSD's
[firmware update review](https://reviews.freebsd.org/D58197)
tests GPT boot on Pi 4, not full Pi 5 support. The Foundation's
[CM5/RP1 work](https://freebsdfoundation.org/blog/freebsd-foundation-intern-jim-huang-chen-on-raspberry-pi-support-and-open-source/)
is a direct upstream contact point. Inventory current FreeBSD commits and
RP1 driver gaps instead of treating imported Linux DTBs as functioning drivers.

[RK3588 UEFI](https://github.com/edk2-porting/edk2-rk3588/blob/2f3f8265590f77901ac6a1af5c963f957a844158/README.md)
lists ROCK 5/Orange Pi 5 and other boards, but says its ACPI development is
Windows-focused. Board-specific regulator, firmware-storage and DTB choices
still matter. A working UEFI USB/NVMe device is not automatically a working
FreeBSD device after ExitBootServices. Its SD/eMMC firmware-storage caveat also
affects runtime variable persistence. Qualify ACPI and FDT as separate profiles.

[OpenBSD's arm64 matrix](https://www.openbsd.org/arm64.html) is a useful BSD
predecessor for Apple, Pi 5, Rockchip, Qualcomm, CIX, NXP, Allwinner, Amlogic and
Ampere bring-up. It is **OpenBSD** support, not FreeBSD support. Trace licensed
driver and binding provenance before reuse; match SoC revision and exact board.
[FreeBSD's platform tiers](https://www.freebsd.org/platforms/) qualify an
architecture, not every board: aarch64 Tier 1 does not grant any of these boards
automatic product acceptance. Legacy ARMv7 and unsupported ARMv6 also need an
explicit ABI/build feasibility decision rather than being hidden by the ARM theme.

## Immediate implications from the returned Spark stick

The private physical run of candidate `1.5.1-spark-dumps1`, image SHA256
`ce37ca07978fb11d5b7d6ad6b41f4ec719191fe7989e06fb7e3985acc40b6576`,
reached init with four CPUs in 3.294 seconds. CPUs at MPIDRs `0x100`–`0x300`
checked in after 0 ms. Seven files survived, validating synchronous FAT
checkpoints. Broad `sysctl -a` timed out after its `vm.phys_locality` prefix;
collection continued. The last checkpoint was ACPI, with zero bytes and no
finish/done marker. That identifies the last started probe, not a proven
ACPI subsystem fault or proof that the operator waited for the timeout.

The machine identifies as ASUS ProArt P16 H7607BA, Insyde H7607BA.303, with
an 18-core marketing description while the kernel counted 20 ACPI entries.
The DGX has 20 enabled CPUs; the laptop's enabled flags and actual topology
remain unresolved. Count usable cores from the laptop's own validated tables.
The first four full-CPU/skip experiments left no kernel NVRAM trace, so absence
cannot locate their stalls. Next work: capture tables before kernel probing,
replace broad enumeration with isolated allowlisted probes, and establish an
early-persistence channel before attempting the PSCI comparison matrix.

No 1.6 implementation item is closed by this research. Track source changes,
recheck upstream status before implementation, and attach exact-artifact
FreeBSD and physical results to each target's release ledger.

### Physical Pi 500 follow-up

The [2026-11-07 Linux reference](../testing-pi500-linux-20261107.md) identifies
a Pi 500 with a 64-bit 4 KiB kernel, 32-bit armhf userspace and a verified
4 MiB round trip through built-in Ethernet. It corrects the first task list:
RP1 Ethernet uses Cadence GEM/macb (`raspberrypi,rp1-gem`, `cdns,macb`), whereas
Pi 4 uses GENET. Kernel options containing both drivers do not identify which
one is bound. Audit the existing FreeBSD CGEM predecessor and RP1 nexus/IRQ,
clock/reset and DMA prerequisites; no FreeBSD qualification follows from this
Linux result. Pi 4 remains ahead of Pi 5-family implementation.
