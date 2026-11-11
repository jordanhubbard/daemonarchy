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


## Explicit candidate memory profiles

`pi5-bootstrap.py` keeps the existing command and **3 GiB** default. Select
`--memory-cap none` only for a separate experimental uncapped candidate. New
v1 manifests record `memory_profile.memory_cap`, the expected kernel cap in
bytes (or `null`), and `runtime_memory_verified: false`. Historical v1 bundles
without that metadata remain 3 GiB profiles; they cannot satisfy an explicit
uncapped request.

Each new bundle contains both `boot/loader.conf.local` and `queue.txt`. The
capped loader configuration and queue set `hw.physmem=3G`; the uncapped loader
configuration omits that assignment and its queue explicitly uses
`unset hw.physmem`. Both retain the four-CPU/FDT discovery selection. The
existing trace queue parser accepts the generated queue. Before copying boot
inputs or queuing an experiment, validate its requested profile and retained
bytes:

```sh
python3 tools/hwtrace/pi5-bootstrap.py --verify-bundle BUNDLE --memory-cap none \
  --queue-file BUNDLE/queue.txt
python3 tools/boottrace/stick.py queue NEW_REGULAR_IMAGE BUNDLE/queue.txt
```

`--queue-file PATH` compares the selected experiment source byte-for-byte with
the profile-bound bundle queue, before `stick.py queue` converts it into the
on-disk CNF format. Legacy bundles cannot use this optional comparison because
they have no profile-bound queue.

The validator rehashes every declared file and checks exact loader/profile/queue
consistency. It refuses changed files, extra members, explicit cap mismatches,
and conflicting settings even when their file hashes have been recomputed.
This is internal consistency and retained-input checking, not authenticated
provenance or a claim that the image boots. Legacy bundles have no generated
queue; their established 3 GiB queue must be retained separately.

The base UFS image is a separate layer. Copying the ESP files does **not**
install the bundle's loader configuration into UFS. Build a new base image with
matching effective settings in `/boot/loader.conf` and, when present,
`/boot/loader.conf.local`, then independently read back those actual UFS files
and the kernel before assembly. Record an absent local configuration explicitly. Check the
final ESP and actual experiment queue separately. An `unset` in the queue does
not establish that the UFS image has the intended profile, that firmware
exposes all RAM, or that native DMA is qualified.

Optionally, `--base-profile-audit FILE` retains an external native-readback
record inside the bundle. Its schema is
`daemonarchy/pi5-base-profile-audit@1`; required fields are `memory_cap`,
`image_sha256`, `kernel_sha256`, `loader_conf_sha256`, and
`loader_conf_local_sha256`. Hashes identify the independently inspected base
image, kernel and exact configuration files. A native check that proves the
local configuration is absent records `loader_conf_local_exists: false` and
`loader_conf_local_sha256: null`; it must not invent a file hash. The tool requires the cap and
kernel to match the bundle and binds the complete receipt bytes. It records
`external-readback-recorded` and `ufs_verified_by_this_tool: false`; supplying
JSON is not independent UFS verification. Without a receipt, the manifest
still explicitly requires independent base-UFS readback. Neither form claims
actual usable RAM or physical Pi 500 acceptance.

Host tests cover legacy default handling, both profile/queue selections,
explicit mismatch and tamper refusal, external audit binding and the actual
trace queue parser. They do not replace native image readback or hardware
qualification. Existing candidate images and their historical 3 GiB evidence
below remain unchanged.

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
kernel hash, `boottrace_capture_acpi="NO"`, a configured four-CPU limit and
initial **3 GiB kernel memory cap**, and root ownership of `/etc/login.conf`. ESP boot inputs were
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
15 of 15 checks, ten durable diagnostic files and a clean reset. Runtime output
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

## Conservative BCM2712 SDHCI follow-on, 2026-11-08

The generic compatibility match is not a complete controller attachment.
[Draft source PR #64](https://github.com/jordanhubbard/daemonarchy-src/pull/64),
code commit `57895db5c4b10d8608fd2183bf2cd34fcc2bf68e`, adds a distinct BSD
BCM2712 attachment. It claims both named host/CFG banks, enables the FDT
`sw_sdio` clock, handles optional 3.3 V rails and card-detect/write-protect
GPIOs, selects and reads back the conservative maximum-50-MHz CFG mode, and
unwinds owned resources on failure/detach. It retains the actual provider rate
for divisor calculation while limiting the card clock separately. UHS/tuned
modes and 1.8 V switching remain disabled; MMCCAM is refused explicitly until
its power/IOS path is qualified. Linux is a register/binding reference, not
implementation source. BSD attribution is preserved.

Independent review caught and corrected a capability-clock overwrite and a
silent MMCCAM start omission. The first native compile attempt failed on API
issues and is not accepted. The corrected build uses another fresh source
export and an empty object directory, compiles the actual new driver and links
a complete GENERIC kernel. Independent source/object/artifact readback agrees.
Portable CFG/clock policy checks pass on both the Linux controller and native
FreeBSD worker; these are bounded policy checks, not hardware lifecycle tests.

| Native follow-on artifact | SHA-256 |
| --- | --- |
| New driver object | `5a2c1813b6ef9b88a8cc51a12fa301bde928f70fe81ecf00ed18bd97cde10b6a` |
| Linked `kernel.full` | `e351d4a41346fefd73bb3f9e8c67bc097c3ec8504abf59a5c868ea8e0aa64537` |
| Stripped kernel | `79ebe4bfcb5f46bbe61c4611d0875beb876b6a523f5b7b187f3c49b0ee463eeb` |

Two fresh root-owned control images use that kernel with the previously
qualified loader/world/Lua. Native read-only UFS inspection verifies the actual
kernel bytes, ACPI setting, four-CPU limit and root-owned `login.conf`.
The Pi 4 FDT base image SHA-256 is
`b94b2573e017ba160f0b75f0a6bc1e6590afb1d06f7a35757f38d9b117914afb`;
the Pi 4 UEFI/USB image is
`60aaf3d087c56bb1ab68b5c05d6c29fb3864bd171b69d8560e21eb4b9c42a6f7`.

On exact simulator `c392d7c5…`, the new kernel passes both Pi 4 proxy controls:
FDT 15/15 and uninterrupted UEFI/ACPI/USB 19/19. Each saves ten durable files,
finishes all seven probes, activates four CPUs and synchronizes before reset.
The USB run has clean storage diagnostics; FDT has no new I/O failures versus
its existing control. Both original images remain unchanged. This establishes
boot/rescue-world compatibility on the partial BCM2711 model, not execution of
the new BCM2712 driver, physical SD performance, lifecycle rollback/fault
injection, full-RAM DMA or Pi 5 hardware acceptance.

The refreshed Pi 500 SD/FDT candidate is 389,056,000 bytes, SHA-256
`ef26d16a4c9849331a5a063cb9ce7cf2bbf120d90e47ad0c11214ac9fafad0b3`.
It retains the pinned U-Boot/DTB/loader inputs, selects the new kernel,
`boottrace_capture_acpi="NO"`, four CPUs, the initial 3 GiB cap and one fresh
`pi500-sd-glue-mmc0` experiment. Native read-only inspection verifies the actual
kernel/root ownership; every ESP input and all 211 trace slots are checked.
The UFS partition remains byte-identical to its freshly built native base.
The earlier candidate is preserved separately.

A separate input-shape guard checks the selected FDT `mmc0` node has named
608-byte host and 512-byte CFG resources, the `sw_sdio` clock, declared rails
and card-detect GPIO, and no unsupported power sequence. This is not native
provider or MMC-numbering evidence. Actual pinctrl/GPIO/regulator/clock
resolution, controller attachment, SD I/O and the EEPROM handoff remain open.
No physical boot or physical media write was performed.

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

## Integrated SD provider candidate, 2026-11-08

The next candidate contains the native-built kernel
`8ec36736678f4de5308164fe6dfe990119b6ff042bf6eec6887ddd3ee84c60c9`
from sealed source `91204d3c8f22504eb4a346e5304d682618aea0d6`. It adds the
selected D0 main/AON pinctrl and AON GPIO providers, checked pinctrl admission,
GPIO regulator settling and failure ownership; the same kernel includes the
[Pi4 ACPI USB DMA repair](testing-pi4-fullram-20261108.md). Source review is
[draft PR65](https://github.com/jordanhubbard/daemonarchy-src/pull/65), stacked
on draft PR64. Original upstream source notices remain intact.

The new regular-file Pi500 candidate is 389,056,000 bytes, SHA256
`96e7265b1df0060bc2855a6d04a4428998363e199a8b5ba2e0daa11a87a34e59`.
Native UFS readback verifies the actual kernel, established loader, root-owned
account files, ACPI-disabled four-CPU configuration and initial 3 GiB kernel
limit. Staged pinned U-Boot, board DTB, boot script, configuration and loader
all pass ESP byte readback; the 211-slot map passes and the native root
partition remains unchanged. Earlier candidates are preserved.

Pi4 FDT15, UEFI/USB19 and uncapped8GB USB20 compatibility checks pass with
that exact kernel. They do not execute BCM2712 drivers. No Pi500 boot was
attempted: MMC0 ordering, actual provider attachment, SD rail/card-detect
behavior, full-RAM BCM2712 DMA and RP1 remain unqualified. Physical boards
remain unattended and unchanged.
