# Pi 5-family SD/FDT bootstrap preparation, 2026-11-07

This records a distinct Pi 500 D0 bootstrap candidate and the Pi 5-family
source prerequisites. It is not a physical FreeBSD boot result. The Pi 4/CM4
simulator cannot emulate BCM2712 or RP1. Both physical boards remain running
with their existing boot files and EEPROM unchanged; no candidate was written
to their storage.

## Maintained boot path and staged candidate

The selected initial path is the board EEPROM loading upstream U-Boot
v2026.10, then the FreeBSD ARM64 EFI loader with the firmware-provided FDT.
This avoids selecting the unmaintained Pi 5 UEFI reference as the sole future
boot path. It does not establish that a particular EEPROM and U-Boot profile
works together on the enrolled board.

[U-Boot commit `5508406582f6f7120dce0c4b3059819a41788db2`](https://github.com/u-boot/u-boot/tree/5508406582f6f7120dce0c4b3059819a41788db2)
includes Pi 500 board code `0x19`, its separate DTB name, and Pi 5 C1/D0 DTB
selection. `rpi_arm64_defconfig` uses the firmware-supplied control FDT. Its
default embedded DTB name is not a claim that Pi 4 DTBs support Pi 5.

The built diagnostic profile retains SD, firmware FDT and EFI loading. It
disables capsule updates, persistent FAT environment storage and automatic
PCIe/USB preboot. Its boot command selects `mmc 0:1` and executes `boot.scr`;
the script refuses a missing firmware FDT and passes `${fdt_addr}` to
`bootefi`. The physical Pi 500 MMC numbering is **unverified**. The proved
Pi 4 simulator uses a different MMC index, so that result cannot establish
the Pi 500 ordering.

The [bundle staging tool](../tools/hwtrace/pi5-bootstrap.py) verifies exact
input hashes, clean pinned U-Boot source/configuration, AArch64 ELF/EFI
headers and the DTB root board/SoC compatibility. It creates a new private
directory and refuses an existing output. It retains U-Boot license texts
and file hashes. `boot.scr` uses the source commit timestamp for reproducible
metadata. Pi 5B C1, Pi 5B D0 and Pi 500 have explicit, separate selections.
The bundle needs the matching hwtrace Lua/rootfs/trace-map support before it
can become an image.

| Selected input | SHA-256 |
| --- | --- |
| SD-only U-Boot `u-boot.bin`, 919,616 bytes | `6016da23bfe2f142982e606621d13104a991f8b710150df2336b3d0514c837b9` |
| Resolved U-Boot configuration | `9cb914f33d77ed487c0e8347665c6fa84d1c5aedc06b4d9b5b6c0a06fee0d076` |
| Enrolled Pi 500 `/boot/firmware/bcm2712-rpi-500.dtb` | `400b2da08abb8fd0ffd65085d1e0e1e6c6d01cadd27385403ea3a3fd5a1537f4` |
| Existing tested ARM EFI loader | `efff8d8aea278198f600f3d3d2e8b9638147f47517765f8a16dd9dff46697d66` |
| Newly built stripped FreeBSD kernel | `86a8e6399e1f601bfcef2b3d42746066bb4dbba94c9a87c4046052a2a121b888` |

The DTB was copied read-only and still matches the
[enrolled Linux reference](testing-pi500-linux-20261107.md). The U-Boot profile
built on Linux ARM64 with the system GCC/toolchain. Starting from the pinned
source, reproduce the profile with an out-of-source build:

```sh
make O=../u-boot-build rpi_arm64_defconfig
scripts/config --file ../u-boot-build/.config \
  --disable EFI_RUNTIME_UPDATE_CAPSULE --disable EFI_CAPSULE_FIRMWARE_RAW \
  --disable TOOLS_MKEFICAPSULE --disable ENV_IS_IN_FAT \
  --enable ENV_IS_NOWHERE --disable USE_PREBOOT --enable USE_BOOTCOMMAND \
  --set-str BOOTCOMMAND 'if mmc dev 0; then if fatload mmc 0:1 ${scriptaddr} boot.scr; then source ${scriptaddr}; fi; fi'
make O=../u-boot-build olddefconfig
make O=../u-boot-build -j8
```

The final private regular image is 389,056,000 bytes, SHA-256
`87a2909797dada689cc1e61974470a3b29c5de6e2512d9776fbb0c21ed3f4d70`.
Its native-built base was assembled with the new kernel, matching existing
1.5.1 hwtrace world/Lua support, root-owned filesystem metadata and explicit
FDT discovery configuration. A read-only native UFS mount verified the actual
kernel hash, `boottrace_capture_acpi="NO"`, four CPUs, an initial **3 GiB kernel
memory cap**, and root ownership of `/etc/login.conf`. ESP boot inputs were
copied and read back, one Pi 500 experiment queued, and all 211 fixed trace
slots checked. The UFS partition stayed byte-identical during final ESP/queue
assembly. Neither the EEPROM boot chain nor MMC numbering has been tested.

## Owned FreeBSD SDHCI change and build evidence

The Pi 500 firmware describes `brcm,bcm2712-sdhci`, which the prior owned
generic FDT SDHCI compatibility table did not recognize. Owned source commit
[`b417aa10e466440c5c166f4e0b2ff4dcb52e32fd`](https://github.com/jordanhubbard/daemonarchy-src/commit/b417aa10e466440c5c166f4e0b2ff4dcb52e32fd)
adds that match and description, preserving the original BSD source/license.
Its predecessor is [FreeBSD draft D59098](https://reviews.freebsd.org/D59098).
This selects existing generic behavior; it does not prove controller quirks,
clock/reset, voltage/tuning or DMA correctness. Review remains
[draft PR #63](https://github.com/jordanhubbard/daemonarchy-src/pull/63).

The accepted native build starts in an **empty** object directory against
source base `9eb753c98a1264c38e0e51a7781994c5ad8811db` plus that commit. It
regenerates GENERIC and completes `make -j6 kernel.full`, followed by
`make kernel`, on FreeBSD 16-CURRENT ARM64 with FreeBSD clang 21.1.8. The log
contains the changed source compilation, and both new binding and description
strings are present in the linked kernel. A separate reviewer recomputed the
source, object and final artifact hashes. This is conventional native build
evidence, not per-unit framework qualification.

The new kernel also completed the proved Pi 4 U-Boot/FDT simulation control:
15 of 15 checks, ten durable probe files and a clean reset. Runtime output
identifies the new kernel's clean build, four CPUs and 4096-byte pages. That
checks the boot artifact and its basic compatibility with the existing world;
it does not exercise the BCM2712 SDHCI controller or qualify Pi 5 hardware.

| Native artifact | SHA-256 |
| --- | --- |
| Changed `sdhci_fdt.c` | `3d1a906487b3ae5fdb9659933f6467862ca7c94f02bb928d81fa9cdd294bfeaa` |
| Newly compiled `sdhci_fdt.o` | `b0eacd6a3d87bdbf046ebd8c44e6da2c77f2ab570538d4d85fca80caa695694f` |
| Linked `kernel.full` | `bea3fb28f2aa5c97f1f0211ca05db80e33eab7f72b0fb9013df561d7bdefdbae` |
| Extracted GENERIC configuration | `be073065fb6024d3a5d9bd130b1d920ef03a6b7df635d01154cfee0bb26b1fda` |

An earlier incremental attempt was rejected: copying an object tree gave a
stale object a newer timestamp and omitted the changed source. Its kernel
hash is not accepted as selected-source evidence. Readback detected that
error before selecting the final image; the clean build above replaces it.

Five host tests cover wrong-board FDTs, wrong ELF/EFI architecture, changed
input hashes, device-file inputs and truncated FDTs. Real bundle staging
passed, repeated staging produced identical file/manifest identities, and
an existing output was refused. These do not count as a Pi 5 boot test.

## Remaining RP1 and native work

The [OpenBSD `rpone(4)` predecessor](https://man.openbsd.org/rpone.4) separates
the PCI endpoint/simplebus and MSI-X translation from its child drivers.
The FreeBSD predecessor stack is still draft, with no accepted native result:

| Draft | Scope to audit |
| --- | --- |
| [D59093](https://reviews.freebsd.org/D59093) | RP1 BAR/simplebus mapping, child resource lifetimes and interrupt forwarding |
| [D59095](https://reviews.freebsd.org/D59095) | RP1 clocks |
| [D59096](https://reviews.freebsd.org/D59096) | BCM2712 MSI interrupt controller |
| [D59097](https://reviews.freebsd.org/D59097) | Cadence GEM binding and PHY delays; does not alone establish RP1 DMA/clock correctness |
| [D59099](https://reviews.freebsd.org/D59099) | VideoCore/ARM address mappings; the proposed ranges need independent address-translation review |
| [D59100](https://reviews.freebsd.org/D59100) | BCM2712 PCIe host/controller changes |

Several downloaded new-driver drafts omit copyright/license headers despite
describing OpenBSD ports. They were retained privately for comparison, not
imported into owned source. The original OpenBSD RP1 source retains Mark
Kettenis's 2025 ISC permission notice; source custody and port modifications
must be resolved before admitting a derivative.

Next physical work requires an attended handoff: verify MMC numbering and
firmware/FDT handoff, collect serial and durable loader/init checkpoints, then
audit SD/USB/NVMe, full-RAM DMA, RP1 clocks/interrupts and Cadence GEM. Pi 5
revision profiles, Pi 500 input, actual graphics, installed boot and recovery
remain separate gates. The initial cap and staging result close none of them.
