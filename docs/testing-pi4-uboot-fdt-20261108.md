# Pi 4 U-Boot/FDT bootstrap, 2026-11-08

RPI-001 now has a distinct simulated FreeBSD bootstrap control. This uses the
partial BCM2711 `raspi4b` model from uConsole. It bypasses the VideoCore/EEPROM
boot chain and does not establish EDK2/ACPI, Pi 5/RP1, PCIe, Ethernet or physical
board acceptance. Both physical boards remained running and unchanged.

## Boot contract and inputs

The existing EDK2 failure control is retained separately. U-Boot provides EFI
services and the FDT to the actual FreeBSD EFI loader; it does not provide the
ACPI tables required by the original discovery preset. A fresh image was
therefore assembled by the native FreeBSD worker with these explicit settings:

```conf
boottrace_capture_acpi="NO"
hw.ncpu="4"
boottrace_label="pi4-simulator-uboot-fdt"
```

This changes the selected firmware/profile, not the original diagnostic image.
The resulting base image is 389,056,000 bytes, SHA-256
`01f2ba29d51e22e943a3e7cb9b9782d07d2731642935360fb836f9edd014cf9e`.
It retains the native-built loader and existing kernel/world inputs:

| Input | SHA-256 |
| --- | --- |
| FreeBSD kernel, `16.0-CURRENT`, build `cb38d6498a24` | `7da10c3ce3bc41330ef8ad3183be5b41ecaae64a93d900083ca687e163ba89f4` |
| FreeBSD ARM64 EFI loader, revision 3.1 | `efff8d8aea278198f600f3d3d2e8b9638147f47517765f8a16dd9dff46697d66` |
| Ubuntu `u-boot-rpi` package `2025.10-0ubuntu0.24.04.4`, extracted locally | `ac1325244b9cb4d013555f1f6fdb11e38c28977388f7ccbf3fe4e4c273c2ea72` |
| Package `rpi_4/u-boot.bin` | `1a525be3184c718ade3c1c5414137d8691ae265aff391449677ad38859364eaa` |
| Existing CM4 Linux DTB fixture before profile fixups | `c9d70ba0e397c772fca8ce18e187fd1762bba082cad82445f314603c42bca7e7` |

The Linux DTB fixture uses `arm,pl011-axi`, which this U-Boot build does not
bind. The separate simulator DTB selects the modeled PL011 as the console and
uses the compatible `arm,pl011`, `arm,primecell` binding. That resolves the
observed silent serial console. The source fixture is preserved. Its CM4
identity remains explicit; this is not a physical Pi 4B device-tree result.

QEMU loads U-Boot through `-kernel`, supplies the DTB through `-dtb` and attaches
only an isolated SD qcow2 overlay. U-Boot finds the EFI loader on `mmc 1`.
The empty `mmc 0` is reported, not treated as a successful device. QEMU disables
unsupported PCIe, GENET, RNG200 and thermal FDT nodes in this existing build.
Networking is disabled for the control.

## Observed runtime

The independent initial control reached the actual FreeBSD EFI loader and
kernel, checked in CPUs 1–3 and reported four active SMP CPUs. FreeBSD attached
SDHCI and `mmcsd0`, mounted `ufs:/dev/gpt/HWTROOT` read-only and reached
`/sbin/init`. The collector saved all seven bounded probes with status zero,
wrote `done.txt`, synced/unmounted the filesystem and requested reset. Offline
readback of the stopped overlay retained all diagnostic files. The captured
scalar sysctls report four active CPUs and 4096-byte pages.

That initial control selected the FDT setting at the loader prompt after the
original ACPI-required preset stopped as designed. The reproducible profile
uses the freshly assembled FDT image above, so it does not rely on overriding
a required capture failure interactively.

The first freshly assembled FDT image exposed an existing image-builder defect:
`makefs` inherited the unprivileged staging user's ownership, and init rejected
`/etc/login.conf` as not owned by root. The builder now supplies an explicit
mtree ownership specification for every root-filesystem path, preserving its
mode and time. Native read-only UFS inspection confirms `login.conf` changes
from the staging UID to root/wheel while retaining mode `0644`, size and mtime.
The corrected image identity is the one recorded above.

The final automated run of that exact image passes all 15 runtime/readback
checks, including the absence of the earlier ownership warning. It retains
10 diagnostic files under `DUMPS/0001`, including seven completed probe files,
the capture log, the FDT/ACPI-source note and the completion marker. The original
image hash is unchanged. Three host guard tests cover partial collection,
incorrect profile/SMP/reset evidence, input-device/hash refusal and GPT bounds.

The same complete control was then repeated with the newly built RNG200,
no-link PCIe and GENET-control QEMU generation, and repeated again after its
final reset/register/migration changes. The final `qemu-system-aarch64`
SHA-256 is `cf65cb291e517a6a3db41bd3db5990006da003f7eb5d90fb66ae901be1f30eec`.
All 15 checks pass again, including four active CPUs, native SD UFS root,
all completed probes, 10 durable diagnostic files and synchronized reset.
This is a regression check of the existing working FDT path. The fixture still
disables GENET, so it does not exercise its network datapath or qualify the
new device models as physical hardware equivalents.

Finally, the same Pi 4 simulation booted the newly compiled owned kernel from
source commit `b417aa10e466440c5c166f4e0b2ff4dcb52e32fd`, which adds the BCM2712
SDHCI compatibility binding. The separate hwtrace base image SHA-256 is
`c88196bbe5369c29649b899c91c6c933549f3b09c63a5a9270ae249f1afa3d1c`; its kernel
SHA-256 is `86a8e6399e1f601bfcef2b3d42746066bb4dbba94c9a87c4046052a2a121b888`.
All 15 boot/collection/reset checks pass with the final QEMU binary, and the
captured kernel version identifies the clean native build. This verifies basic
boot and rescue-world compatibility of the new kernel artifact on the Pi 4
model. It does not exercise BCM2712 or the new SDHCI binding on Pi 5 hardware.

## Reproduce the isolated control

[`tools/hwtrace/pi4-simulator.py`](../tools/hwtrace/pi4-simulator.py) requires
explicit image, U-Boot and DTB hashes. It refuses devices and existing output
directories, copies the input image, queues one four-CPU FDT control and uses a
new qcow2 overlay. Supply the pinned inputs above and the existing uConsole
QEMU binaries; `--help` lists all required arguments. Run with a new private
output directory and a consistent QEMU library environment.

The runner stops QEMU on the guest's reset request, converts its stopped overlay
for offline FAT readback, and checks actual loader/kernel/SMP/SD-root/init,
completed capture, disk synchronization and reset evidence. It checks the saved
FDT setting and all seven probe statuses and confirms the original source image
is unchanged. Logs, derived DTB, overlay, complete diagnostics and `result.json`
remain private in that directory. A timeout or missing marker fails the run and
retains its evidence; a live QEMU process alone cannot pass it.

The 512 MiB virtual SD capacity is rounded up from the raw image, so FreeBSD
reports that the backup GPT is not at the final virtual LBA and that partitions
are not aligned to its preferred erase size. This control does not qualify
partition geometry, full 8 GB DMA, native USB/network/display/input, installed
boot, updates or rollback. Those physical and final-distribution gates stay open.
