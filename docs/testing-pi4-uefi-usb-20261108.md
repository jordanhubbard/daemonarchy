# Pi 4 UEFI/PCIe/USB bootstrap, 2026-11-08

This control uses pftf UEFI v1.53 and the actual FreeBSD ARM64 EFI loader,
ACPI kernel and rescue world on uConsole's partial BCM2711 model. It bypasses
the VideoCore/EEPROM boot chain. Physical Pi 4 and Pi 5 boards remain unattended
and unchanged; BCM2712/RP1 acceptance remains separate.

## Reproduce and judge the control

[`tools/hwtrace/pi4-uefi-simulator.py`](../tools/hwtrace/pi4-uefi-simulator.py)
requires explicit image, firmware and QEMU SHA-256 values. It refuses device
paths, stale source diagnostics and existing output directories. It copies the
regular input image, assigns a unique run label, queues one four-CPU experiment
and attaches a fresh qcow2 overlay through the modeled PCIe xHCI USB controller.
The source image retains its exact geometry and is checked again after the run.

The firmware profile enables GIC security extensions and the optional connected
PCIe endpoint. The ordinary direct-Linux/FDT profile remains independently
qualified. `--debug-control` adds a private QMP socket for live inspection;
QMP supervision still observes the actual guest stop and saves a framebuffer
snapshot before quitting. A timeout preserves partial evidence and fails.

Acceptance requires the actual loader's ACPI readback, checksummed tables from
the current queue generation with four enabled CPUs, native kernel ACPI/xHCI/
USB mass-storage attachment, UFS root, four active CPUs, 4096-byte pages, and
the unique label in the saved kernel environment. All seven bounded diagnostic
probes must finish with status zero, the completion marker must be nonempty,
and no root-ownership warning or failed storage I/O may appear. Offline
diagnostics, synchronized
guest reset, clean emulator exit and unchanged source-image hash are checked
separately. A firmware prompt, visible kernel text or exit zero cannot pass.

## Inputs and measured blockers

| Input | SHA-256 |
| --- | --- |
| Native-built ACPI/USB diagnostic image, 389,056,000 bytes | `185540e330ce8c9dbc6b74966adcf498cd15fd9221e93fa0128ceacc66715c3b` |
| pftf v1.53 `RPI_EFI.fd` | `8334d9d3c3fe5341fb9876f2ddf653eca7b260ee2cda669c5446a0dd7f0104c5` |
| Clean native kernel from owned source `b417aa10e466440c5c166f4e0b2ff4dcb52e32fd` | `86a8e6399e1f601bfcef2b3d42746066bb4dbba94c9a87c4046052a2a121b888` |
| ARM64 EFI loader | `efff8d8aea278198f600f3d3d2e8b9638147f47517765f8a16dd9dff46697d66` |

The first connected-PCIe probe reached the native xHCI driver, which faulted
because the ACPI resource reserves 4 KiB while the generic virtual controller
used 16 KiB. An opt-in compact layout keeps the standard QEMU xHCI engine,
places its runtime/doorbell banks inside that resource, and leaves generic
controller defaults unchanged. Independent real command/event-ring DMA, INTx,
reset and migration tests cover both layouts.

The second cold probe, with QEMU SHA-256
`b6c676c083bbe539514e635b3149d0ceacffecb866d4db0dc154ff24eff430a5`,
passed that attachment and faulted in ACPI thermal `_TMP`. An actual exception
snapshot and translation-table walk resolve its virtual fault address to the
BCM2711 AVS status register at physical `0xfd5d2200`. The original DSDT reads
that register using calibration `410040 - 487 * raw`. This is an observed
missing simulator device, not evidence that the native thermal driver is bad.
Both failed runs retain framebuffer, table and stopped-overlay evidence;
neither saved init diagnostics and neither is an accepted bootstrap result.


The third cold probe uses the added AVS model, QEMU SHA-256
`bb335a6d852cf52385a5a46aced84fd1c6c98f329b4db937ec790bcd11ffe5b2`.
It passes the thermal read and enumerates native xHCI, USB mass storage and
`da0`, with the expected 371 MiB source geometry. It has not completed init or
saved diagnostics. A live inspection found all four CPUs in idle and no active
or pending GIC interrupt, while exact-kernel symbol reads show the kernel has
left cold boot and its uptime advances. This does not establish a stopped
global timer; the remaining storage/root wait is still under investigation. Attaching a
debugger then stopped the VM; the supervisor recorded `paused` and refused
acceptance with no diagnostics. This was an observer-interrupted failed run,
not a natural guest reset or a timeout. A separate diagnostic-only observer
allows thread inspection without treating debugger stops as completion.

That exact binary also passes the independent FreeBSD FDT control (15 checks,
10 durable files, native SD UFS root, four CPUs and synchronized reset) and
Linux CM4 control (10 checks, actual ext4 SD root, four CPUs and natural
poweroff). All eight device-model suites pass against the extracted Linux
ARM64 native package, whose GUI/archive check also passes. These independent
controls preserve both original input images and do not substitute for the
unfinished ACPI/USB acceptance.


The diagnostic observer eventually reached init, saved all seven probes and
requested reset. No guest memory/register values or completion events were
injected; debugger attaches paused execution and detaches resumed it. This is
not a clean qualification run. Its saved dmesg shows the 720,896-byte CTF read
exhausted five CAM retries and failed with `g_vfs_done()` error 5 before init
continued. Collection completion therefore does not establish correct storage.
The runner now explicitly rejects that error, CAM request failures, exhausted
retries and I/O errors; an additional acceptance-guard test proves a complete
collector result cannot hide them.

Live transfer inspection found the first 64 KiB completion of a 128 KiB bulk-IN
transfer delivered and the second absent. An independent generic QEMU xHCI +
USB-storage fixture verifies the entire patterned 128 KiB payload arrived but
only the first completion event was emitted. QEMU's transfer-wide `reported`
latch suppresses the final IOC event. The xHCI specification requires an event
for each IOC-marked TRB, including intermediate chained TRBs. A bounded model
repair and a fresh uninterrupted boot with clean storage diagnostics remain
required; the observer's original successful collector checks do not close it.


## Accepted uninterrupted control

The bounded chained-IOC repair was then tested in a fresh, uninterrupted cold
boot with QEMU SHA-256
`c392d7c5b3a56f7afc01887a679e878c40953b0da0fde9dc0fd2edda4d31740d`.
The source image, firmware, loader and kernel retain the identities above.
No debugger socket or debugger attachment was used. All 19 runtime/readback
checks pass, including the new clean-storage check; the separate source-image
integrity check also passes. The only observed stop is the guest's synchronized
reset (`SHUTDOWN` reason `guest-reset`, followed by `STOP`).

The actual EFI loader captures current-generation ACPI tables with four enabled
CPUs. The native ACPI kernel attaches xHCI and USB mass storage, mounts the UFS
root, activates all four CPUs and reaches init. All seven bounded probes finish
with status zero. Offline readback preserves ten diagnostic files, including
the completion marker, after filesystem synchronization. The saved dmesg has
none of the earlier CAM failures, exhausted retries or UFS read errors.

This closes the simulated Pi 4 UEFI/ACPI/PCIe/USB bootstrap control. It does not
qualify the physical board, full RAM/DMA, Ethernet, display/input, installed
boot, updates/rollback, BCM2712/RP1 or the bypassed VideoCore/EEPROM chain.


The final `c392d7c5…` binary also repeats the independent Linux CM4 control
(10/10, actual ext4 SD root, four CPUs and natural poweroff) and FreeBSD FDT
control (15/15, native SD UFS root, four CPUs, ten durable files and reset).
Both original base images remain unchanged. The final extracted Linux ARM64
archive passes GUI/archive validation and all nine model suites, including
actual USB storage completion and migration continuation. These controls
complement the accepted ACPI/USB boot without expanding its hardware scope.
