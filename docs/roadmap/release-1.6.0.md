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
   bounded wait never starts. This is consistent with an identical hang on 1.5.0 and 1.5.1. Linux starts
   the same core with the same PSCI call (below), so the question is what FreeBSD passes differently: the
   entry address, the context ID, the exception level and cache state the core enters with, or a firmware
   power-domain dependency (the SSPM `NVDA8400` device).
2. **The call returns and the core starts, then hangs the system** (for example by faulting while holding
   shared state). src#60 parks late arrivals, but not a core that checks in on time and then fails.

## Ground truth from the DGX Spark (2026-11-07)

Read on the lab's DGX Spark (`sparky`, GB10, Linux `7.0.0-1019-nvidia`), which boots all 20 cores:

| Fact | Value |
| --- | --- |
| Firmware interface | PSCI v1.1 (standard v0.2 function IDs), SMCCC v1.5, conduit from ACPI |
| MADT GICC entries | 20, all enabled; **parking-protocol version 0 and no mailbox on every core**, so every core is started by PSCI CPU_ON. The parking-protocol theory is ruled out on this SoC. |
| `0x400` | An ordinary entry, identical to `0x000`-`0x300` (efficiency class 0); Linux boots it with no special case |
| Cores | `0x000`-`0x400` and `0x10000`-`0x10400`: Cortex-A725 r0p1 (`0x410fd871`); `0x500`-`0x900` and `0x10500`-`0x10900`: Cortex-X925 r0p1 (`0x410fd851`) |
| Errata | Linux enables erratum 4193781 (X925, broken broadcast TLBI completion) when `0x500` comes up. FreeBSD has no such workaround; it is not the `0x400` hang but is needed for the X925 cores. |

Whether the laptop's tables match is checked by the last experiment below, which dumps its MADT.

## Plan

### 1. Evidence from the published 1.5.1 image (no new code)

A copy of the published `daemonarchy-hwtrace-1.5.1-aarch64` image carries these as a five-boot queue
([evidence/spark-151-queue.txt](evidence/spark-151-queue.txt); one boot each; power off a hung boot after photographing the whole screen; the last boot reaches init
and saves `dmesg`, `acpidump`, `pciconf` and `devinfo`):

| Setting | Question it answers |
| --- | --- |
| `boot -v` | Does a `failed to start` line or a per-CPU start time appear at all? If not, the hang is inside PSCI CPU_ON (explanation 1). |
| `hw.ncpu=4` | Does the 1.5.1 kernel still reach init on four CPUs (the baseline)? |
| `hw.mp.ap_timeout_ms=60000` | Only if a failure line appears: does the core arrive late (slow firmware power-up)? |
| `hw.mp.skip_mpidr=400`, `hw.mp.stop_on_failure=0` | Do the other 15 cores start? Is it that one core or everything after it? |
| `hw.mp.skip_mpidr=400,500,...,900`, `stop_on_failure=0` | Does the second cluster (`0x10000`-`0x10900`) start? |
| `hw.ncpu=4` (last) | The 1.5.1 baseline on four CPUs, and the laptop's own MADT, PPTT and DSDT. |

### 2. Linux on the same SoC

The DGX Spark facts above come from Linux on `sparky`; the laptop's own MADT comes from the last
experiment. Still to compare: what Linux passes to CPU_ON (entry point, context ID) and the state its
secondary entry code assumes, against FreeBSD's `mpentry` (`locore.S`) and `start_cpu()`. Linux and the
vendor tables are read, never copied or redistributed.

### 3. Fix

Depending on steps 1 and 2:

- **PSCI CPU_ON hangs for `0x400`:** make FreeBSD's call match what works under Linux (entry address,
  context ID, entry exception level and cache state), or the firmware power-domain order if that is the
  cause. A watchdog print from an already running CPU while the boot CPU is inside CPU_ON confirms the
  location in one boot.
- **The core starts and then fails:** extend src#60's stage reporting past `init_secondary()` and fix the
  fault it names.
- **The X925 cores:** add the erratum 4193781 workaround (repeat the TLBI sync) before claiming all 20 CPUs.
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

## Scope

**Operator decision, 2026-11-07: 1.6.0 is scoped to SPARK-001 only for now.** The other open issues on the
1.6.0 milestone (DEBUG-003 #33, PERF-002 #39, ARCH-001 #62, NET-001 #80, GPU-001 #101, INSTALL-PERF-001 #134,
VISUAL-SDK-001 #139, PKG-002 #142, EXT-001 #161) and the not-done rows of
[the 1.5.1 notes](../release-1.5.1.md#what-is-not-done-and-why) are not part of 1.6.0 unless the operator
adds them.

Signing follows SIGN-001 option A: freeze the signed inputs, finish QA, sign once.
