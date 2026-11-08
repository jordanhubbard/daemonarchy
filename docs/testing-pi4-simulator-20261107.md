# Pi 4 simulator checkpoint, 2026-11-07

The operator made the existing uConsole emulator available while both physical
boards are unattended. Its machine is QEMU 10.2.4 `raspi4b`: BCM2711, four
Cortex-A72 CPUs, 2 GiB RAM. It is a partial Pi 4/CM4 simulation, not Pi 5,
BCM2712 or RP1. RPI-001 stays ahead of RPI-002. Neither board was rebooted or
reconfigured for these experiments.

## Results

An isolated qcow2 overlay booted the existing CM4 Linux `6.12.62-v8+` kernel,
mounted the actual SD root filesystem and completed an interactive probe:
four CPUs online, 64-bit userspace and 1,902,264 KiB MemTotal. It powered off
cleanly. This is a Linux control, not a FreeBSD result.

The [Pi 4 diagnostic candidate](testing-pi4-linux-20261107.md) was attached
through its own fresh 512 MiB qcow2 overlay. Its raw image and pftf UEFI v1.53
firmware were unchanged. Loading the armstub at zero and entering secondary
CPUs at `0x1000` reaches BL31 and UEFI. QEMU's `-bios` loads this firmware at
the wrong address and is not the tested boot contract.

| Experiment | Measured outcome |
| --- | --- |
| Existing uConsole model | UEFI write external abort at RNG200 threshold register `0xfe104010`; ESR_EL2 `0x96000050` |
| Functional RNG200 model added | UEFI passes that access, then read external abort at PCIe reset register `0xfd509210`; ESR_EL2 `0x96000010`, ELR_EL2 `0x3969f4d4` |

PCIe is not modeled. Neither experiment reaches the FreeBSD loader. These
register snapshots establish simulator gaps; they do not identify a FreeBSD
bug or explain the separate Spark CPU-startup hang.

The RNG200 change is retained in uConsole commit
`fecc814`, with the [reproduction and model limits](https://github.com/jordanhubbard/uConsole/blob/fecc814/docs/emulator-pi4-uefi.md).
It uses host-backed random words and implements enable/reset, counters,
write-one-to-clear status, IRQ and migration. Register/reset/IRQ checks and
real migration with reset asserted and deasserted pass. The 33 emulator host
tests and 11 source-cache tests also pass. Oscillator/entropy-health/timing
fidelity is not claimed; the ordinary Linux FDT fixture still disables the
RNG node, so the Linux control does not qualify that driver.

## Remaining work

The next UEFI step requires a defined PCIe model or a separately identified
firmware profile. Preserve the unchanged-firmware failure control rather than
silently skipping the failing MMIO. SD routing, GENET, PCIe/xHCI/DMA, 8 GB RAM,
firmware boot-chain behavior, native display/input and installed distribution
acceptance remain physical or explicitly modeled gates. A generic VM result
cannot close those gates or RPI-002's RP1 requirements.

Private UART/QMP/GDB captures and all writable overlays remain outside the
repositories. The existing uConsole workspace and physical media were not
modified by the simulator runs.

## Subsequent independent U-Boot/FDT bootstrap

The [2026-11-08 U-Boot/FDT control](testing-pi4-uboot-fdt-20261108.md) reaches
the actual FreeBSD EFI loader, four active SMP CPUs, the native SD UFS root,
init and all seven completed diagnostic probes. Offline readback verifies the
saved files after filesystem synchronization and reset. The explicit FDT
profile does not require ACPI capture; the EDK2 failure controls above remain
separate. A discovered image ownership defect was fixed and the corrected
candidate passed the same complete simulated boot/collection/reset control.
Physical and final-distribution acceptance remain open.
