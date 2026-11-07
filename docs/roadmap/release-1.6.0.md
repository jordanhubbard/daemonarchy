# 1.6.0 plan: the NVIDIA RTX Spark laptop

- **Status:** active
- **Opened:** 2026-11-07, after 1.5.1 was published
- **Owning queue item:** [SPARK-001](active-work.md#spark-001-boot-install-and-run-the-desktop-on-the-nvidia-rtx-spark-laptop)
- **GitHub issue and milestone:** [#291](https://github.com/jordanhubbard/daemonarchy/issues/291), [1.6.0](https://github.com/jordanhubbard/daemonarchy/milestone/5)
- **Completion / archival evidence:** pending; nothing here is claimed done.

1.6.0 exists to make the NVIDIA RTX Spark laptop, the first physical arm64 target, boot, install and run
the desktop. It was deferred from 1.5.0 and again from 1.5.1: on 2026-11-06 the 1.5.1 arm64 release image
still hung after `Starting CPU 4 (400)`, as 1.5.0 did. The background is in
[the application note](../application-note-rtx-spark.md) and in daemonarchy-src
`docs/rtx-spark-bringup.md` (src#60).

## What is known

| Boot | Result |
| --- | --- |
| 1.5.0 stock kernel | Last console line `Starting CPU 4 (400)`; CPUs 1 to 3 started. |
| `kern.smp.disabled=1` | Reaches init on one CPU in 2.6 s. |
| Patched kernel with `hw.ncpu=4` | Reaches init in 2.8 s on CPUs 0 to 3; USB and the MediaTek Wi-Fi device attach. |
| Patched kernel, all CPUs (src#53 only) | Kernel panic; the text was not recorded. |
| 1.5.1 release image (src#53 and src#60) | Hangs after starting the fourth CPU, as 1.5.0 did (operator, 2026-11-06). |

## What the 1.5.1 result says

The 1.5.1 kernel carries the bounded wait (src#53) and stop-at-first-failure with stage reporting (src#60).
If the core at MPIDR `0x400` had merely failed to check in, the boot CPU would have printed
`CPU 4 (400) failed to start after 5000 ms (...)`, started no more CPUs and reached init on four, like
`hw.ncpu=4`. It hung instead. In `start_cpu()` the `Starting CPU` line is printed **before** the PSCI
CPU_ON call and nothing is printed when that call returns successfully; the timeout only begins after it
returns. Two explanations remain, and the first experiments separate them:

1. **The boot CPU never returns from PSCI CPU_ON for `0x400`.** The firmware call itself hangs, so the
   bounded wait never starts. This is consistent with an identical hang on 1.5.0 and 1.5.1. Possible
   causes: the MADT GICC entry for that core asks for something other than PSCI (the Linux kernel known
   to boot this SoC is built with the ACPI parking protocol; FreeBSD arm64 has no parking-protocol support
   and ignores those fields), a firmware power-domain dependency (the SSPM `NVDA8400` device), or a PSCI
   quirk.
2. **The call returns and the core starts, then hangs the system** (for example by faulting while holding
   shared state). src#60 parks late arrivals, but not a core that checks in on time and then fails.

The core-type theory is weak: on the DGX Spark (GB10, same 20-core layout under Linux) CPUs 0 to 4 are
all Cortex-A725 with one MIDR, so `0x400` would be the fifth core of the first, working cluster.

## Plan

### 1. Evidence from the published 1.5.1 image (no new code)

All at the loader prompt of the 1.5.1 arm64 stick, one boot each, with a photo of the last screen:

| Setting | Question it answers |
| --- | --- |
| `boot -v` | Does a `failed to start` line or a per-CPU start time appear at all? If not, the hang is inside PSCI CPU_ON (explanation 1). |
| `hw.ncpu=4` | Does the 1.5.1 kernel still reach init on four CPUs (the baseline)? |
| `hw.mp.skip_mpidr=0x400` | Does CPU `0x500` start, and do the other 15? This tells whether the fault is that one core or everything after it. |
| `hw.mp.ap_timeout_ms=60000` | Only if a failure line appears: does the core arrive late (slow firmware power-up)? |

The published `daemonarchy-hwtrace-1.5.1-aarch64` image can run the same settings as a hands-off queue
(src `docs/rtx-spark-queue6a.txt`, `6b.txt`) and keeps a 60 s panic hold for photos.

### 2. Ground truth from Linux on the same SoC

From a Linux boot on the laptop (a live USB) or, as a weaker substitute, the DGX Spark `sparky`: the
MADT (every GICC entry's flags, parking-protocol version and mailbox address, MPIDR), PPTT and DSDT
(`acpidump`), the PSCI version and features from `dmesg`, the boot method Linux used per core, MIDR per
core, and each secondary core's start time. Compare the `0x400` entry with `0x000` to `0x300`. Linux never
redistributes the vendor tables; neither do we.

### 3. Fix

Depending on steps 1 and 2:

- **PSCI CPU_ON hangs for `0x400`:** start each core the way the MADT says. If cores are parked, add ACPI
  parking-protocol support to `madt_handler()`/`start_cpu()` (Linux has the mechanism). If it is a
  firmware power-domain order, match it. A watchdog print from an already running CPU while the boot CPU
  is inside CPU_ON confirms the location in one boot.
- **The core starts and then fails:** extend src#60's stage reporting past `init_secondary()` and fix the
  fault it names.
- **Fallback, only if the root fix misses 1.6.0:** a quirk keyed on the ACPI OEM table ID that skips the
  failing cores by default, so the Spark boots on fewer CPUs. The release notes would then say how many
  CPUs run and why; this is not "supported".

Each fix goes upstream to FreeBSD as a short PR once it works on the Spark (see the upstream style rules).

### 4. Beyond boot

Install to the internal NVMe, boot the installed system and reach the desktop on `efifb` (software
rendering; there is no FreeBSD driver for the NVIDIA GPU). Wi-Fi: the mt7925 LinuxKPI driver and
`wifi-firmware-mt76-kmod@mt7925` already exist. Add `options IOMMU` (SMMUv3) only if NVMe or Wi-Fi DMA
fails once SMP works. Out of scope and stated as unsupported: the NVIDIA GPU, Bluetooth, audio, suspend.

## Acceptance (SPARK-001)

- The **release** arm64 image boots on the Spark to the installer with all 20 CPUs (or, with the fallback
  quirk, the stated subset, and the notes say so).
- An installation to the internal NVMe completes; the installed system boots to the Daemonarchy desktop on
  `efifb`; Wi-Fi associates and passes traffic.
- Records: `dmesg`, `sysctl hw`, `pciconf -lv`, `devinfo`, the hardware trace, photos of any failure, with
  exact image hashes. amd64 is unaffected (the QEMU and MSI/MacBook installs still pass).
- The release notes claim only what these records show.

## Other 1.6.0 candidates (not yet scoped)

The issues on the 1.6.0 milestone, moved from 1.5.1 on 2026-11-07: DEBUG-003 (#33), PERF-002 (#39),
ARCH-001 (#62), NET-001 (#80), GPU-001 (#101), INSTALL-PERF-001 (#134), VISUAL-SDK-001 (#139),
PKG-002 (#142) and EXT-001 (#161), plus the not-done rows of [the 1.5.1 notes](../release-1.5.1.md#what-is-not-done-and-why).
The operator decides which of them join SPARK-001 in 1.6.0; until then only SPARK-001 is committed.

Signing follows SIGN-001 option A: freeze the signed inputs, finish QA, sign once.
