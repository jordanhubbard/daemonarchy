# Default installation tracing and target-specific hardware bring-up

- **Status:** active
- **Owning queue item:** [TRACE-001](active-work.md#trace-001-make-installation-media-trace-every-boot-and-installation)
- **Completion / archival evidence:** implementation and exact-media persistence acceptance pending

## Operator direction

On 2026-11-09 the operator made automatic tracing a 1.6 requirement for normal
installation media, across architectures. Users who expected a machine to work
must receive useful early-boot and post-mortem evidence without choosing a
special “run experiment” menu item. A writable hwtrace volume is standard on
the installation medium and records every boot and installation.

For brand-new hardware, prefer a coding LLM plus a conversational description
of the exact machine to produce a customized hwtrace image. A generic image
without the board, firmware and boot-chain facts is a baseline, not a port or a
complete diagnostic plan. The Apple M2 reference is the allocated Mac mini
identified as Mac14,12. Remote console access can disappear during native boot;
collect evidence locally to the trace volume rather than depending on SSH.

These are planned 1.6 behaviors. The existing [1.5 trace tools](../boottrace.md)
and published images retain their original scope and bytes.

## Standard media and normal boot

Keep the established `DATRACE` FAT32 label and preallocated raw-map safeguards
where compatible. Add the writable partition to the default install/live USB
layout, including hybrid ISO images written to USB. The partition begins after
all original ISO bytes, not in a GPT gap which may contain ISO9660 payload.
Verify both GPT copies, filesystem bounds, the ESP/loader, original installer
payloads and raw-map readback after assembly. Image creation operates on fresh
regular files; writing a selected physical device remains a separate operation.

Select the trace partition belonging to the actual boot medium. A foreign or
duplicate label on another disk is not permission to write there. Bind records
to an image/payload identity, target descriptor, media identity and a fresh boot
session. Preserve earlier boots and failed attempts with bounded space and an
explicit exhausted/full/read-only state. Never erase a previous trace merely
because the current capture timed out.

Optical and read-only virtual media cannot persist writes to themselves. Detect
that condition and retain available output without redirecting writes to an
unrelated disk. The ordinary writable USB path must persist automatically;
read-only-media fallback and recovery need their own tested behavior.

Normal tracing observes the normal boot and installer. It does not consume an
experiment queue, apply speculative tunables, cap CPUs/RAM, force unattended
reboots, change the install target, start a network listener or grant remote
access. Active experiments remain a separately selected development workflow.
The normal path must not require users to discover or choose that workflow.

## Evidence through the boot boundary

| Stage | Required evidence and limits |
| --- | --- |
| Firmware/loader | Boot/image/profile identity, selected kernel/modules, bounded firmware and ACPI/FDT handoff facts, loader outcome and committed pre-exit checkpoints on the trace volume. |
| Early kernel | Per-CPU/startup milestones and console output in bounded buffers; persist through an admitted backend when available. Never call EFI Boot Services after ExitBootServices or runtime services before initialization. |
| Before disk/runtime support | State the exact observation/persistence gap. Qualify reserved-memory, proxy/serial or another platform transport separately; absent output is not a fault location. |
| Storage attached/init | Flush retained kernel evidence and record each bounded probe's start, exit status, timeout and durable completion. Keep completed files readable after an interrupted later probe. |
| Installation | Record phase boundaries, artifact/package identities, selected target identity and terminal success/failure without passwords, pairing keys, typed input or private configuration payloads. |
| Panic/reset/next boot | Recover the last committed checkpoint and prior session without silently treating missing data as success. Test warm reset and cold-power survival independently on each supported backend. |

Prefer the trace volume over firmware-variable storage for sustained evidence.
Bound NVRAM consumption and writes where it is used; unavailable or broken
runtime variables cannot prevent normal installation. Firmware/table reads must
be bounded and validated before use. Do not introduce broad `sysctl -a`, live
`acpidump /dev/mem` or speculative device probing into default boot.

## Target-described custom images

The user should be able to begin with ordinary language, for example:

> Help me bring up this exact machine with Daemonarchy. Here are its model,
> SoC/board revision, RAM, firmware and boot path, what appeared on screen,
> and the returned hwtrace volume. Identify unknown prerequisites, preserve
> the working OS and recovery path, and prepare a matched diagnostic image.

The coding LLM first resolves missing facts from bounded read-only observations
and pinned upstream/board evidence. Keep facts, hypotheses and proposed tests
distinct. Record image/source/loader/kernel/module/DTB/firmware identities and
redistribution constraints. Use a working control and one changed variable for
active experiments; do not guess another model's CPU count or DMA layout.

The output is a reviewable target descriptor, reproducible image recipe and
exact artifact identities. Boot it through the real target firmware, retrieve
the hwtrace volume, and use its last durable stage to select the next test.
Retain raw diagnostics privately and share a filtered summary when needed.
Apple recipes preserve macOS, Recovery and the selected OS-owned ESP; remote
access to macOS does not establish a usable native boot console.

## Publication and acceptance

The default installation images become the generic first-failure diagnostic
entrypoint once this path passes. Reassess separate generic pre-built hwtrace
assets for 1.6: retain a separate published diagnostic image only with an
explicit target/profile and demonstrated value. Keep the customization tools,
recipes and existing historical artifacts available. Do not remove required
assets from historical release verifiers or replace published tags/bytes.

TRACE-001 acceptance requires exact final media, not documentation or a partition
alone. Test both architectures and normal installer/live boots; no diagnostic
menu selection; normal install completion; loader/kernel/init/installer failures;
interrupted writes; corrupt/full/read-only trace volumes; foreign/duplicate
media; absent NVRAM; reset/power loss; and previous-session recovery. Inspect the
returned bytes, image/package identities and last durable checkpoints. Add real
Apple and other required physical results, keep remaining backend gaps visible,
and retain existing amd64 behavior and installation performance gates.

## First layout checkpoint

The partition helper's original free-gap allocation corrupted a real-tool hybrid
ISO fixture before the fix. It now appends after the original end of the image
and preserves BIOS boot code and filesystem payload; all 29 boottrace-tool
controls pass. A [real kernel-control ISO append](../../verification/install-trace-layout-20261109.json)
preserves every original filesystem byte and verifies 201 raw-map files on its
new 255 MiB FAT32 DATRACE partition. This is preparation only: automatic default
boot/install capture and augmented-image boot/persistence remain unqualified.

## Native builder and live-root persistence checkpoint

The EFI image builder now appends a 256 MiB DATRACE filesystem by default,
using native FreeBSD `makefs` and `mkimg` through
[`make-install-trace.py`](../../scripts/make-install-trace.py). It creates fresh
regular files, checks both GPT copies, preserves the original ISO payload and
ESP, and initializes and reads back all 201 raw-map files. `INSTALL.JSON` binds
the trace filesystem to the unmodified ISO payload hash. The native end-to-end
builder and six refusal/integrity controls passed; the full 29 boottrace-tool
controls now run in CI with their real filesystem utilities.

The [native checkpoint](../../verification/install-trace-native-20261109.json)
also retains an important failure. The augmented kernel-control image boots as
a writable USB disk, but mounting DATRACE for writing while the live root is
mounted directly from that same disk's ISO9660 provider returns `Operation not
permitted`. A read-only mount succeeds. The same filesystem passes native
write, filesystem checking and remount/readback from a separate worker, and
controller readback finds the committed file with the raw map intact. This
points to the shared raw-disk access boundary, rather than a broken FAT image.
Do not disable GEOM protections globally to evade it.

The default userspace trace design therefore needs a root arrangement that
releases the boot disk, such as the ARM RAM-root path, or another qualified
layout. The subsequent [eight-CPU ARM RAM control](../../verification/arm-ram-native-20261109.json)
does persist diagnostics to its own USB trace partition and passes controller
readback and a FAT check after orderly shutdown. That manual control proves
the RAM-root arrangement permits writes; it does not implement automatic
capture. A subsequent [LZMA/packed-root control](../../verification/arm-ram-handoff-20261109.json)
preserves every original filesystem byte, fits the unchanged raw-media budget,
boots and repeats manual same-medium readback. Its verified RTX Spark/M2 Pro
handoffs remain development assemblies using the retained installer world;
its compressed publication fails the existing asset limit and final-media
acceptance remains open. The amd64
BIOS/hybrid builder still needs integration; this helper deliberately refuses
layouts with partitions other than a single ESP. Automatic loader, kernel and
installer capture, interrupted writes and physical reset/power-loss acceptance
remain open. Neither a successful builder nor the independent write control
closes those gates.


## Boot-medium discovery checkpoint

[Source PR #81](https://github.com/jordanhubbard/daemonarchy-src/pull/81)
adds a read-only EFI discovery command that binds the loaded image's physical
GPT disk to a distinct tagged sibling partition. It refuses read-only,
ambiguous and malformed-tag media, ignores a foreign disk's tag, and leaves
optical boot unbound. Each renewal clears any stale writable identity.
Seventeen production-parser sanitizer controls pass on Linux and native
FreeBSD ARM64. The exact rebuilt ARM64 EFI passes six VM discovery cases;
returned UUID/GPT equality and zero disk writes are independently checked.
The [artifact-bound checkpoint](../../verification/install-trace-media-20261109.json)
retains an earlier invalid-GPT fixture and its unexpected startup writes,
followed by the corrected complete-GPT control with before/after write counts.

That earlier candidate was a capture prerequisite. It did not run automatically,
bind the image payload, validate a raw write map or persist a normal boot.
The RAM media checkpoint uses its original matched loader; it does not silently
inherit this new EFI candidate's discovery result. Automatic loader/kernel/init/
installer capture and all remaining TRACE-001 acceptance gates stay open.


## Automatic loader-start checkpoint

The [subsequent native checkpoint](../../verification/normal-boot-trace-20261109.json)
now saves `phase=loader-ready` automatically before the normal menu, without
keyboard input. The EFI builder hashes its actual input archive, creates a fresh
image UUID in matching boot/trace-id and INSTALL.ID files, enables observe-only
startup, and initializes 32 additional 16 KiB NORMAL slots. The new layout has
233 mapped files; the historical 201-file controls above remain unchanged.
The builder refuses EFI/Lua inputs lacking the new capability markers. This
preflight is a compatibility guard, not runtime qualification.

Capture binds to the loaded EFI image's own writable GPT sibling, validates the
identity and raw map against fresh FAT32 file/cluster metadata, and uses a
whole-disk flush/readback backend. It retains nonempty, corrupt and partial slots
and reports full after 32 occupied slots. A repeated call within the same loader
instance does not allocate another slot. Failure leaves normal startup available.
The normal dispatcher takes precedence over conflicting legacy autocycle flags;
STATE, the queued experiment and all 200 legacy trace slots remain unchanged.

An exact native-built ARM64 EFI control passes automatic write/readback,
idempotency, fresh-process restart and controlled warm reset after a committed
record. A synthetic partial first slot survives while the next slot is used.
Thirteen unsafe-media cases refuse with zero disk writes, including a validly
checksummed map with swapped slot extents. Controller comparison verifies every
changed byte lies within the expected NORMAL slots and the returned FAT checks
clean. These are minimal loader-only VM fixtures, not full installer boots.

The record labels its archive identity as declared and its early-kernel backend
as not enabled. Image/slot sessions and GPT UUIDs can be shared by clones; full
target identity and cross-stage boot identity remain unfinished. This metadata
checkpoint does not capture kernel/modules, pre-exit outcome, kernel console,
panic, init or installation. Relevant FAT metadata checks are not a general
filesystem repair or an exhaustive cross-link audit. Physical power loss and
actual interruption during a write remain untested. Earlier full RAM-root media
does not inherit the new loader's acceptance; exact full-media reconstruction,
amd64 BIOS integration and the unchanged publication-budget failure remain open.

Retrieve normal records with:

```sh
python3 tools/boottrace/stick.py normal TARGET --out FRESH_DIR
```

This read-only operation copies exact bytes, preserves damaged slots and produces
a hash-bearing manifest. Legacy experiment reset does not erase these records;
there is no automatic rotation or erase on failure.


The independent [amd64 EFI checkpoint](../../verification/normal-boot-trace-amd64-20261109.json)
uses the exact native CI loader and unchanged Lua files in a kernel-free fixture
under OVMF/TCG. It saves before keyboard input and passes whole-returned-image
comparison and FAT readback. Read-only, foreign-volume and swapped-map cases
leave every virtual disk and firmware variable store unwritten and keep the
normal menu available. This adds amd64 loader-only firmware evidence; full
amd64 OS/default-media and BIOS integration remain open.


The [full ARM RAM-root follow-up](../../verification/normal-full-arm-trace-20261109.json)
rebuilds the retained installer world with matching new EFI/Lua and the complete
Omarchy closure. It boots normally with eight CPUs and 16 GiB, saves the loader
checkpoint without menu input, renders the retained welcome screen and preserves
the exact 378-package inventory. After guest shutdown, controller comparison
finds only 304 changed bytes in NORMAL/0001.TXT, unchanged legacy state/traces,
an empty experiment queue, clean FAT and an unchanged source image. The new
3,732,947,456-byte ISO passes the unchanged raw budget by 25,148,928 bytes.
This is an independently rebuilt control; earlier full-media results are not
relabelled. It still uses the 1.5.0 world/UI and predates the source refresh in
PR #82. It proves persistence through a real kernel/init boot, not capture of
those stages' diagnostics or final installation/desktop/release acceptance.

## Independent pre-exit checkpoint

The [native ARM64 pre-exit record](../../verification/normal-preexit-20261110.json)
binds the exact new EFI, producer helpers and minimal kernel-control medium.
Each existing 16 KiB NORMAL file now has independent 4 KiB loader-ready and
pre-exit banks, with the final 8 KiB reserved. The pre-exit hook renews boot-medium,
identity, raw-map and FAT admission before writing only its derived bank. It
runs before the first GetMemoryMap call, outside the ExitBootServices retry
window. A record proves the callback was reached; successful firmware exit
requires separate observation. Legacy v1 files remain readable and occupied.

Native unprivileged stand construction and sanitizer controls pass. Initial and
fresh-process restart boots save both stages, enter the CURRENT kernel and
change only 607 bytes in the new session slot. Synthetic partial later data is
preserved while the next slot succeeds. Read-only media and a read-only trace-less
primary beside a writable foreign trace disk boot without saving records or
changing either image. No keyboard input or network device is used.

An earlier writable trace-less primary changed 81 bytes in backup GPT sectors;
the foreign trace disk remained unchanged. That preserved run does not pass
whole-primary preservation. The retry holds the primary read-only and does not
resolve firmware/GPT-repair attribution or establish the stronger writable-primary
claim. The exact record retains this failure and its limits.

The controller reads both versions and exports an intact loader-ready bank even
when pre-exit is partial or corrupt, preserving the complete raw slot. Extraction
reports partial evidence explicitly. Unknown reserved-bank changes are refused.
The builder accepts the explicit v1 or v2 EFI capability marker.

These are minimal boot controls held at a deliberately unavailable root, using
the af55 kernel and a separately rebuilt fe12c0bb loader. They do not qualify a
new whole world, installer or desktop. Native amd64 callback assertions are wired
into CI with results checked separately. Selected kernel/module identities,
bounded firmware facts, early kernel/panic/init/installer capture, clone-independent
identity, interrupted writes, power loss, amd64/BIOS, full refreshed media and
physical acceptance remain open. Pi 4, Pi 5 and Apple M2 remain untested physically.

A subsequent complete-GPT control also leaves both writable primary and foreign
disks byte-for-byte unchanged. Before boot, both GPT header checksums and
mirrored entry arrays pass independent validation. The first input lacked its
backup GPT and remains separately recorded. Exact a486e309 native amd64 CI now
passes the production handoff fixture in plain and sanitized modes and builds
the EFI; its outputs and feature manifest are retained and hash-verified.
This does not qualify an amd64 firmware boot, BIOS or final installation medium.


## BIOS/EFI hybrid layout preservation

The [native hybrid layout checkpoint](../../verification/hybrid-trace-layout-20261110.json)
extends the assembler from a single ESP to the standard amd64 layout with one
FreeBSD BIOS boot partition and one ESP. Other layouts remain refused. It keeps
the original disk GUID and complete occupied partition entries, including UUIDs,
names, attributes and holes. Smaller GPT tables are refused rather than expanded
over possible boot code.

The amd64 BIOS partition occupies LBAs 34 through 58, inside the ISO system
area. Assembly therefore copies only the protective MBR and exact GPT metadata,
preserving the MBR boot code and every original byte from LBA 34 onward. Copying
a whole 32 KiB system area would erase the BIOS loader. The previous assembler
refused this layout; it did not ship that destructive operation on amd64.

Native unprivileged FreeBSD assembly of the retained 1.5.1 amd64 payload adds
201 mapped legacy trace files. Independent full-byte comparison and a native
read-only FAT check pass. The exact output boots through both SeaBIOS and OVMF
under x86 TCG, reaches the kernel and userspace without keyboard input, and has
no network device. BIOS records zero disk writes. The EFI run creates a
10,213-byte NvVars file: all 1,336 changed bytes are inside the original ESP;
DATRACE remains unchanged. That is not a whole-image zero-write result.

The single-ESP path also passes native assembly with 32 NORMAL slots and 233
map entries. Its exact new output boots under native AArch64 KVM, records both
loader-ready and pre-exit checkpoints, enters the CURRENT control kernel, and
changes only 607 bytes in the expected session slot.

This checkpoint preserves an existing payload; it does not qualify final 1.6
media or automatic BIOS tracing. The default amd64 build path still needs matched
identity/loader integration. The augmented old amd64 image is 3,824,173,568 bytes
and fails the unchanged strict 3,758,096,384-byte raw budget. No compressed asset
is qualified, no features are dropped and no size limit is raised. Exact refreshed
world/ports/desktop media, complete boot/install/recovery and all remaining
TRACE-001 and physical acceptance gates stay open.
