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
and no root-ownership warning may appear. Offline diagnostics, synchronized
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
