# Application note: NVIDIA RTX Spark laptop (aarch64)

Updated November 3, 2026. The **NVIDIA RTX Spark** ARM laptop is an official
Daemonarchy target for 1.5.0 and the first physical aarch64 machine the project
tests. **It does not yet boot to a desktop.** For 1.5.0 this hardware is released
as *tested, not yet working*: the support added so far stays in the tree, and the
kernel fix is not part of 1.5.0. This note records what has been observed and what
has not; it is not a support statement for any release.

## Status

The 1.5.0 aarch64 image has not been shown to work on this machine as of the table above. Since then the operator booted the
patched kernel by hand: it boots further than the stock kernel and then panics in
the kernel. The panic has not been analysed yet; the fix stays a draft and is
not scoped into 1.5.0. What the
operator has run so far:

| Step | Result |
| --- | --- |
| UEFI loader from a USB stick | Runs. The kernel starts, prints its banner and sizes memory. |
| Firmware and tables | UEFI with ACPI. The kernel reports 20 CPUs in the ACPI tables, about 15.3 GB of RAM (15,274 MB real, 14,901 MB available) and a 3840x2400 EFI framebuffer. |
| Stock boot | Stops after `Starting CPU 4 (400)`, the last line of the boot console. The boot CPU never continues. |
| `kern.smp.disabled=1` | Boots to init in 2.6 seconds on one CPU (hardware trace 0003, kernel `FreeBSD 16.0-CURRENT #2 303b3646270f`). |
| `kern.smp.maxcpus=5` | No effect on arm64: it behaved like the stock boot. Use `hw.ncpu` to limit CPUs. |

Not tested: installation, the graphics stack, the desktop, Wi-Fi, Bluetooth,
sound, suspend and any NVIDIA GPU driver. The post-init diagnostics from the one
boot that reached init (`dmesg`, `sysctl`, `pciconf`, `devinfo`, `acpidump`) were
lost because the machine was powered off before the stick's filesystem was
flushed, so the CPU model and topology are not yet recorded here.

## Cause

Reading `sys/arm64/arm64/mp_machdep.c`: `start_cpu()` prints `Starting CPU n
(mpidr)`, asks PSCI to power the core on, then waits with no timeout for the
core to report in. The line after `Starting CPU 4 (400)` never appears, so the
core at MPIDR `0x400` was powered on but never reached the kernel's startup code,
while cores 1 to 3 did. The fork's arm64 code is identical to upstream FreeBSD
at the merge point, and upstream has no timeout either. Which core type that is,
and where it stops, has not been established.

A bounded-wait patch ([daemonarchy-src #53](https://github.com/jordanhubbard/daemonarchy-src/pull/53))
makes the boot CPU give up after two seconds, report `CPU n (mpidr) failed to
start`, and continue with the CPUs that did start. It is a draft and has not run
on this machine.

## Workaround

At the loader prompt (press Escape at the boot menu, then choose the loader
prompt), set `kern.smp.disabled=1` and boot. The machine then runs on one CPU.
`hw.ncpu=4` should start only the cores that did come up, but has not been
tested here.

## Hardware trace image

The hardware bring-up image (`build-hwtrace-image.sh`) can be built for aarch64
([daemonarchy #256](https://github.com/jordanhubbard/daemonarchy/pull/256)). It
carries the boottrace loader and a queue of loader experiments, and files a
trace per boot on the stick. A boot that hangs before EFI runtime services start,
as this one does, files no kernel steps: use the console and the queued
experiments instead. When an experiment reaches init, leave the machine alone
for the hold time (`hwtrace.hold`) so its diagnostics are flushed before power is
removed.

## What 1.5.0 will say

1.5.0 lists this machine as a target. Whether it ships working depends on the
core-start fix and a real boot of the release image. Until the release image
has been booted on this machine, its release notes cannot call it supported.
