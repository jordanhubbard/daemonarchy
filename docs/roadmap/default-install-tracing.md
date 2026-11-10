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


## Shared default amd64 and ARM assembler

The [default-builder checkpoint](../../verification/default-hybrid-trace-20261110.json)
changes build-iso.sh to request a complete Poudriere live-root tar archive on
both architectures, then uses the shared trace-aware assembler. The actual
archive hash and a fresh image identity are placed in the boot filesystem and
owned DATRACE volume. AMD64 selects BIOS/EFI mode; ARM keeps EFI-only mode.
All selected live packages, installer sets, repository and driver checks remain.

BIOS/EFI mode creates both El Torito entries and the USB BIOS boot partition.
It selects the explicit EFI catalogue entry, rather than mistaking the first
BIOS entry for the ESP. Regular BIOS boot files are required, and an isoboot
larger than the 15 KiB system-area allowance is refused before image creation.
Existing output images, checksums, compressed assets and dangling links are
preserved; repeat authoring requires fresh output paths.

Native unprivileged assembly passes with 32 NORMAL slots and 233 mapped files.
Six exact amd64 boot controls pass: writable EFI captures both stages and enters
the kernel with only 607 changed bytes in its session slot; BIOS enters the
kernel with the whole image unchanged; read-only and foreign-disk EFI cases
refuse capture and preserve the writable foreign disk; both El Torito optical
paths enter the kernel without writes. EFI uses separate private pflash
variables. The returned trace FAT passes independent read-only checking; its
free-cluster summary is uninitialized and no repair is performed.

The same new assembler's default ARM path also passes native construction and
KVM boot, recording both stages with only 607 session-slot bytes changed. An
initial ARM harness attempt exceeded the Unix socket path limit before QEMU
started; that failure is retained separately from the passing short-path retry.
Native oversized/symlink-isoboot controls refuse before output and preserve
their source archive and failed staging.

These are boot-only fixtures. AMD64 retains the earlier kernel and BIOS products
with the exact new EFI/Lua; ARM retains its separately qualified control inputs.
They stop at an intentionally unavailable root. The full selected Poudriere
closure, refreshed world and final default-media installation have not been
composed or qualified by this checkpoint. Automatic BIOS tracing, deeper stage
capture, final size budgets, signing, lifecycle and physical gates remain open.
The previous full augmented amd64 payload's raw-budget failure remains; the
smaller boot-only control does not resolve it.


## Boot correlation across cloned media

The [native nonce checkpoint](../../verification/normal-boot-identity-20261110.json)
adds v3 records with a cached 256-bit firmware-RNG nonce shared by both banks.
The product decoder reads all three versions, checks later-bank nonce equality,
and retains earlier evidence when the later bank is malformed. New EFI
construction accepts the explicit v3 capability marker. Slot/map geometry and
the experiment queue remain unchanged.

Both native-built ARM64 and amd64 EFI controls boot the exact same cloned input
with different nonces, preserve the same nonce across their two stages, and enter
the kernel. Only 809 bytes in each current session slot change. ARM restart
retains its first slot and records a new nonce in the next slot. Removing the RNG
device on each architecture records boot_nonce=unavailable and
boot_identity=unavailable, changes only 701 slot bytes and still enters the
kernel. No clock, image ID or counter is promoted to an independent nonce.

The nonce is public correlation metadata, with only its hash in this public
record. It does not authenticate a target or establish firmware entropy quality.
Stable hardware descriptors, actual kernel/userspace handoff querying and
backend-specific identity acceptance remain open. These tests stop at a
deliberately unavailable root and do not qualify full media, init, installation,
desktop, physical reset/power loss or the remaining release gates.


## Native kernel and userspace handoff control

The [subsequent RAM-root controls](../../verification/normal-boot-userspace-handoff-20261110.json)
boot the exact v3 EFI on ARM64 and amd64, run native init/rc, and query the
partition, session, capture status and boot nonce with kenv. All four controls
(with and without RNG on each architecture) match the actual persisted ready
record and its decoder-bound pre-exit bank. Each guest syncs and powers down;
independent whole-disk comparison finds only 809 current-slot bytes changed
with RNG or 701 without. No keyboard input or network device is used.

ARM64 uses the matched CURRENT base/kernel at OSVERSION 1600031. AMD64 uses
the retained 1600029 runtime/kernel and the new EFI. Versions are established by
input/worker provenance; an ancillary uname call was absent from the minimal
runtime and supplies no version result. These UFS2 memory-disk fixtures prove
the environment handoff through the kernel into userspace. They do not capture
kernel/init/installer diagnostics or qualify refreshed whole media, a desktop,
BIOS tracing, hardware identity, physical targets or final release. Initial
fixture assembly and readback-harness failures remain recorded. Pi 4, Pi 5 and
Apple M2 remain untested physically.


## Complete retained live-root control

The [full RAM-root checkpoint](../../verification/full-ram-live-control-20261110.json)
retains all original payload paths and both owned Lua hooks, verifies the actual
nested UZIP filesystem, and boots the corrected amd64 image through EFI USB.
All 269 live package identities survive the writable var mount; SQLite imports,
userspace kenv matches the ready/pre-exit nonce, and manual same-medium files
survive shutdown. Only 20,816 DATRACE bytes change; legacy traces, state, queue
and unused normal slots are preserved. Native FreeBSD and Linux FAT checks pass.
The 2,554,348,032-byte raw image and 1,883,066,408-byte xz asset pass existing
budgets, including exact decompression identity.

The shared [RAM authoring helper](../ram-live-images.md) preserves archive
ownership and the packaged var seed. An earlier preparation omitted the brand
and profile hooks; the corrected helper now refuses that input, and complete
readback requires every original path. BIOS attempts remain unqualified: the old
emulator aborted on its host lock assertion, while the private new-emulator VM
ended before acceptance. The retained 1.5.1 world/kernel control does not qualify
final CURRENT media, ARM shared-helper boot, installation, desktop, signing,
lifecycle, performance or physical targets. Default archive production is unchanged.


## Large BIOS handoff and root-inode correction

The [BIOS control](../../verification/bios-large-ram-handoff-20261110.json)
exposes and corrects a one-GiB bootstrap mapping alias: metadata after the large
RAM filesystem was read through the first physical GiB. Native BIOS/EFI CI and
sanitized table-walk checks pass with a two-GiB mapping using ordinary two-MiB
pages. The exact corrected outer BIOS boot reaches FreeBSD init, verifies 269
packages and SQLite, and preserves manual writes with only 19,962 DATRACE bytes
changed. All normal slots and legacy data remain unchanged.

This also reveals an input error in the earlier per-entry audit: archive
extraction omitted the original ISO root inode, leaving mode 0700. Root QA
passed while non-root service execution failed. The helper now requires an
explicit root entry, validates its root ownership and mode, and applies that
entry's final owner/group/mode after extraction. Native refusal and restoration
controls pass; a complete repaired image is rebuilding. The original shutdown
console-oracle failure remains recorded. Final BIOS runtime, CURRENT media,
automatic BIOS tracing, non-root services, desktop and physical gates remain open.


The [repaired full-root follow-up](../../verification/full-ram-root-corrected-20261110.json)
includes the root inode in all 62,776 independently inspected entries and restores
its exact original ISO metadata. BIOS USB boot now passes root and UID-65534
package/SQLite checks. The guest shutdown event and actual final VGA buffer
confirm sync; readback changes only 19,892 DATRACE bytes and both FAT checkers
pass. Raw/xz budgets and exact decompression pass. The earlier malformed inputs
and partial outcomes remain retained. Same-image EFI USB boot now passes the
root and UID-65534 inventory/SQLite checks, v3 loader/userspace correlation, synced
shutdown and both FAT checkers, with only 20,430 DATRACE bytes changed. Final
CURRENT media, automatic BIOS/deeper-stage capture, installation, desktop,
lifecycle, signing and physical qualification remain open.


## Versioned userspace-bank decoder preparation

The [v4 decoder controls](../../verification/normal-userspace-codec-20261110.json)
reserve four independent 4 KiB banks in the existing 16 KiB normal slot:
loader-ready, pre-exit, init-ready and installer. The latter two carry at most
2 KiB of canonical-base64 content, its retained-byte SHA-256 and an explicit
truncation flag. Each bank binds the declared image/archive, trace partition,
slot and boot nonce. Invalid or torn later content cannot erase a valid earlier
checkpoint. The extractor retains exact raw bytes and reports partial sessions.

All 23 decoder/extraction controls pass on Linux and native FreeBSD ARM64 without
skips. They reject malformed/oversized content and replayed identities while
retaining v1-v3 reads. Version 3 reserved space keeps its old refusal semantics;
existing records are not relabeled or changed.

This checkpoint preceded the matching v4 producer below. Safe native userspace
boot-medium selection, bounded bank writes, init/installer hooks and exact-image
runtime/failure/power-loss acceptance remain open. Bounded
bank content is not a complete kernel-console or installer-log retention result.


## Native v4 loader-to-init handoff

The [v4 handoff record](../../verification/normal-v4-kernel-handoff-20261110.json)
binds source PR #86 and its native EFI export to all 779 stand input hashes.
Independent inspection of the actual ISO and ESP matches that loader. The kernel
matches the prior retained x86 fixture; its minimal RAM root adds the actual x86
uname binary and a strict kernel-version probe. The initial missing-command
probe and refused source-path repair remain recorded.

Both corrected x86 TCG boots reach kernel/init without keyboard input, save v4
ready/pre-exit banks, compare partition/session/capture/nonce through kenv, and
report kernel OSVERSION 1600029 before synchronized shutdown. With firmware RNG,
only 809 bytes change; without it, 701 bytes change and nonce absence is explicit.
All changes are inside the current normal slot. Original images and all earlier,
unused and legacy data remain intact. Both returned FAT filesystems pass Linux
and native FreeBSD read-only checks.

Init/installer banks remain empty. This qualifies the loader format through the
retained kernel/userspace boundary, not automatic userspace writes, full CURRENT
media, USB-specific v4 behavior, physical hardware or release acceptance. Native
medium admission, writers/hooks and failure/power-loss controls remain required.


A subsequent boot of that actual returned v4 medium reserves slot 2 with a fresh
nonce, preserves slot 1 byte-for-byte, repeats the kernel-version/kenv handoff
and synchronizes before shutdown. Only 809 bytes in slot 2 change; both native
and Linux FAT checks pass. This is another boot through the same returned-media
bytes, not physical cold-power or warm-reset qualification.


## Read-only userspace boot-medium selection

The [selection checkpoint](../../verification/boot-medium-selection-20261110.json)
adds bounded GEOM metadata and v4 kernel/session correlation policy. It selects
one GPT DATRACE extent through its physical DISK provider, preserving an explicit
read-only result. A real retained x86 boot exposed the same GPT through both
vtbd0 and an ISO LABEL alias. The first observer refused it; the corrected
resolver collapses only a proven zero-offset, whole-provider alias with the
same partition geometry. Duplicate UUIDs on another disk remain refused.

Eleven test groups pass on Linux and native FreeBSD ARM64. The actual x86
kernel snapshot and v4 ready/pre-exit/kenv observations also replay natively,
selecting the physical partition with one equivalent alias. The private raw
snapshot, first refusal and corrected replay remain retained.

This library admits no device writes. Raw GPT/FAT/map validation, mounted/busy
state, identity checks around opening devices, writers/hooks and full trace
retention remain work. Missing fresh entropy is an explicit correlation gap;
it must not prevent ordinary boot or installation.

## Raw GPT observation validation

The [raw GPT checkpoint](../../verification/boot-medium-gpt-20261110.json)
adds bounded primary/backup header and partition-table checksum validation,
copy agreement, usable-space bounds, unique partition identities and overlap
refusal. The raw trace partition must match the kernel-selected UUID, index,
type, exact label, attributes and extent. Expanded media may retain an original
backup location; this read-only policy validates that pair without repairing it.

All 18 selection and GPT test groups pass on Linux and native FreeBSD ARM64.
Raw GPT blocks from the actual returned x86 v4 control medium also replay
natively with the same result. This is observation replay, not native device
opening or writable-device admission. FAT/map validation, mounted/busy and
open-identity checks, userspace writers/hooks and full trace retention remain
required.

## Read-only FAT allocation and map validation

The [FAT checkpoint](../../verification/boot-medium-fat-20261110.json)
adds a bounded FAT32 observation policy. It requires matching boot-sector and
allocation-table copies, a clean allocation state, bounded directory traversal,
valid long-name sequences and unique short names. Every allocated cluster must
belong to exactly one live directory or file; cycles, cross-links, orphaned
allocations and invalid chains are refused. All required trace files must have
their exact preallocated sizes and contiguous extents. SLOTS.MAP must match
the canonical map reconstructed from those actual extents.

Seven independent corruption-test groups pass on Linux and native FreeBSD
ARM64. Metadata from the actual returned x86 v4 medium also replays natively:
233 mapped files and 1,876 allocated clusters are accounted for. The first
development probe refused the formatter's archive-marked volume label; the
policy now accepts that standard root-label attribute combination.

This remains read-only metadata validation. Native device opening and identity
revalidation, mounted/busy checks, userspace writers/hooks and complete bounded
kernel/installer evidence remain required. No final CURRENT media, physical
hardware or release acceptance follows from this checkpoint.

## Native read-only device observation

The [native observer checkpoint](../../verification/native-boot-medium-observer-20261110.json)
connects GEOM, GPT, FAT/map and v4 kernel/session observations through an actual
FreeBSD character-device descriptor. It opens only the canonical physical disk,
read-only, without following symlinks. Device identity and ioctl provider/geometry
must agree before and after bounded reads. GEOM descendants must be idle apart
from the observer's own physical-disk reader. Repeated topology, raw metadata,
slot and kernel-environment observations must remain consistent.

All 31 selection/GPT/FAT/native-refusal groups pass on Linux and native FreeBSD
ARM64. A retained x86 kernel with a minimal diagnostic RAM root and native Python
runs the observer automatically without keyboard input or networking. It selects
vtbd0p2, validates all 233 map entries and correlates the actual v4 record. Only
809 bytes in the loader ready/pre-exit banks change; userspace adds no writes.
The returned FAT passes both Linux and native FreeBSD read-only checks.

A second attached image with duplicate partition identities causes an explicit
observer refusal; the diagnostic boot still synchronizes and powers off normally.
The initial Python dependency-closure failure and an overlong-QMP-path launch
failure remain retained separately from these successful runtime controls.

This qualifies read-only device observation on the retained x86 fixture. It does
not qualify writable-device admission, cross-checking the installation identity
file, full retained logs, init/installer persistence hooks, final CURRENT media,
physical devices or release acceptance. Future default hooks must treat missing
or refused capture as best effort and continue ordinary boot/installation.

## Native bounded userspace checkpoint writes

The [userspace checkpoint evidence](../../verification/native-userspace-checkpoints-20261110.json)
adds a v4 bank encoder and a native one-bank commit path. It cross-checks the
installation identity file against the loader record, uses aligned raw reads,
holds the selected partition writable alongside a read-only physical-disk
descriptor, and verifies the exact GEOM access counts. FreeBSD ignores O_EXCL
for these character devices; the implementation does not claim that flag
provides an exclusive lock. Device/path/provider identities and GPT/FAT/map
observations are checked around the operation.

A bank is written only while empty, then fsynced, device-cache-flushed and
independently decoded from readback. Existing evidence is never replaced.
Identical retries avoid a replacement write but still flush and read back.
Partial writes remain inspectable and refuse automatic replacement; completed
loader banks remain readable. Forty test groups pass on Linux and native
FreeBSD ARM64 without skips, including partial-write, flush-failure, stale-session,
readback-corruption and existing-evidence controls.

The first native attempt exposed two real constraints and is retained: an
unaligned identity-file read failed, and a whole-disk write open spoiled its
partition views. The corrected x86 diagnostic fixture automatically records
a 2 KiB kernel-console snapshot with explicit truncation, plus a sanitized
18-byte installer-start event fixture. A later installer event is refused
because that bank already contains evidence. This is not a real installation.

The actual returned medium is booted again. Slot 1 remains byte-identical;
slot 2 records all four banks with a fresh nonce. Each boot changes only
4,695 bytes in its own normal slot. Both returned FAT filesystems pass Linux
and native FreeBSD read-only checks. The original image remains unchanged.

This is bounded checkpoint persistence on the retained kernel/minimal-root
fixture. The 2 KiB payload and single installer event do not establish complete
log retention or installer progress capture. Default live/installer integration,
full bounded logs, ARM and BIOS capture, final CURRENT media, actual interrupted
device writes/reset/power loss, physical hardware and release acceptance remain
open. Older records and published images retain their original scope.

## Full bounded per-session logs

The [session-log checkpoint](../../verification/bounded-session-logs-20261110.json)
extends new native trace filesystems with 64 preallocated USPACE files:
one kernel and one installer file for each of 32 sessions. Each file is 1 MiB,
split into two frames with a 4 KiB checksummed identity header and at most
520,192 payload bytes per frame. The firmware's existing 233-entry raw map is
unchanged. Native admission verifies every file's size, contiguous extent and
allocation ownership before exposing the selected session's log extents.

An update writes and flushes the inactive payload before committing and flushing
its header. The most recent complete frame remains readable if that update is
interrupted. A damaged inactive frame is retained rather than silently reused;
exhaustion is explicit. Foreign identities and ambiguous sequences refuse writes.
The standalone reader exports the latest valid payload through a correlated
normal-slot identity without modifying inputs. The small v4 banks remain first
checkpoints; installer progress appends to the full log while preserving them.
Media without USPACE retains the preceding bounded-bank behavior.

All 48 test groups pass on Linux and native FreeBSD ARM64. The actual retained
x86 fixture captures all 5,183 dmesg bytes without truncation, retains installer
start and completion fixtures in sequences 1 and 2, and retries the terminal
event without rewriting the log. Native and Linux extraction produce identical
payload bytes. The subsequent boot preserves the prior complete normal slot
and both full files byte-for-byte, then captures a fresh session. Each boot
changes only 11,441 bytes inside its own normal and log files. Both returned
FATs pass Linux and native FreeBSD read-only checks; the original image remains
unchanged. The initial host metadata-comparison and native probe-invocation
failures remain retained separately from these passing results.

The installer events are fixtures, not a real installation. Default boot and
installer hooks, actual phase/package/target/terminal evidence, ARM and BIOS,
final CURRENT images, real interrupted device writes/reset/power loss and
physical hardware acceptance remain required. Complete early-kernel or panic
persistence does not follow from an init-time dmesg snapshot.


## Default live-root service preparation

The [staging checkpoint](../../verification/live-trace-stage-20261110.json)
adds the bounded capture wrapper and a background FreeBSD rc service to both
RAM-root builders. The service follows filesystem, var, tmp and ldconfig
setup and precedes login. Missing capture identity or unavailable tracing does
not prevent ordinary boot. A retained lock inode serializes writers; the
operation has a 120-second timeout and five-second kill grace.

Nine staging groups pass on Linux and native FreeBSD ARM64 without skips.
They cover both ABI/ELF selections, exact helper bytes, repeat staging,
prerequisites, root metadata and unsafe paths. The initial repeat-stage failure
is retained; atomic replacement now handles read-only helpers. Four native
RAM-image admission groups also pass without skips. Linux passes the three
portable groups and explicitly skips native archive admission.

The complete retained x86 live root stages all eight helpers while preserving
its root UID 0, GID 1002 and mode 0755. Actual native rcorder confirms the
prerequisite/login ordering. A full image with an rc.local test observer is
being assembled for automatic service-start validation; native UFS authoring
and integrity checks have completed. This preparation does not yet prove
that the service runs at boot or that returned media contains its output.
Real installer hooks, final CURRENT media, ARM/BIOS runtime, failure/reset/
power-loss and physical acceptance remain open.


## Archive-preserving default composition

The [default composition checkpoint](../../verification/default-live-trace-integration-20261110.json)
wires the ordinary ISO build through the complete RAM-root assembler on both
architectures and includes staged helper hashes in each assembly manifest.
The canonical manifest name and existing raw/compressed size gates are retained.
The runtime auditor can open the outer ISO and packed UFS root read-only;
native ARM64 controls verify matching-worker refusal, unchanged image bytes and
cleanup of every MD device the auditor allocated. Full runtime execution of the
x86 payload on its matching worker passed the tool, import, GTK and desktop
wiring checks, then reached the one-hour limit in its retained ELF dependency
scan. That incomplete audit does not qualify full runtime execution.
The replacement batches `file(1)` classification while preserving every regular
pathname and every per-path `ldd` check. Native controls resolve four dynamic
ELF paths, including hardlink aliases and a newline filename, and refuse a
removed linked library. Its full-image execution remains pending.

The initial control used `cp -Rp`, breaking 2,077 original hardlink groups and
duplicating 3,128,137,688 bytes. Its automatic boot launch was stopped; the
preparation and output remain unqualified evidence. The corrected control uses
the retained original archive with explicit loader and test-observer updates.
Independent native checks now preserve all 2,077 unaffected hardlink groups and
root mode 0755, UID 0 and GID 1002. The image is 2,555,396,608 bytes. Actual native
manifest generation preserves its identity and records all eight staged helpers.
The corrected complete root now passes its normal rc trace service through
EFI/USB; its independently checked returned-media results are described below.
Neither this retained-world control
nor static default-call wiring closes final CURRENT or physical qualification.

The [amd64 CURRENT build continuation](../../verification/native-amd64-build-continuation-20261110.json)
retains a second confirmed five-hour world-build timeout and its objects/logs.
A fresh worker uses the exact same pinned source and plan with a twelve-hour
phase bound, fourteen-hour VM bound and unchanged four-CPU, memory and free-space
checks. Its restored source view is read-only; the third world attempt is live.
No world product or lifecycle receipt is inferred from that continuation.


## USB raw-request failure and bounded I/O

The [USB request checkpoint](../../verification/usb-bounded-device-io-20261110.json)
retains the completed full-root failure: normal rc startup reached its observer,
but the kernel repeatedly rejected a 522,240-byte USB CAM READ(10) request at
LBA 4,466,720. The observer timed out, and the guest shut down with only the
loader-ready/pre-exit banks recorded. Both userspace logs remain empty. The
video-primary console result and returned bytes are retained; an absent serial
observer message was not used as a success or failure verdict.

Shared device reads and writes now use at most 64 KiB per request, retaining
512-byte alignment, complete metadata validation and existing frame commit
ordering. Short reads refuse the extent; a partial write returns its short
total without retry, so the committer retains the interrupted inactive frame.
All 51 observation/checkpoint/log test groups pass on Linux and native FreeBSD
ARM64 without skips.

A smaller retained-kernel USB control places DATRACE and the FAT at the exact
failed physical LBAs, beyond 2 GiB. Actual FreeBSD 1600029 observation and
checkpoint calls complete without USB CCB errors, retaining all 5,951 sampled
dmesg bytes and 38 bytes of installer event fixtures. All four banks decode;
the full installer log reaches sequences 1/2, and a repeated terminal event
performs no log rewrite. Only 12,191 bytes in the current session change. Linux
and native FreeBSD read-only FAT checks both return zero. This is device-I/O
fixture evidence. A subsequent actual boot retains a fresh nonce in slot 2,
preserves the whole prior session byte-for-byte and repeats the same checks;
each boot changes only 12,191 bytes in its own session. Both subsequent FAT
checks also return zero.

The corrected full default-rc image (2,554,348,032 bytes) boots through ordinary
rc startup without network or keyboard input. The actual default service
records the init checkpoint and all 6,232 sampled kernel-log bytes, with no
full-log truncation. Its read-only observer visibly reports
`DEFAULT-TRACE-RC-PASS` and exits zero on the video-primary console. Independent
returned-media decoding confirms all three boot banks, an untouched installer
log and only 10,754 changed bytes confined to the current trace session. Linux
and FreeBSD read-only FAT checks both return zero; the input image is unchanged.
Native authoring preserves all 2,077 unaffected hardlink groups and root metadata.
This qualifies default rc capture on the retained complete root; real installation,
final CURRENT, ARM/BIOS, physical and interruption/power-loss gates remain open.

The preceding full-root image separately passes native xz integrity, exact
decompression and unchanged size limits: raw 2,555,396,608 bytes, compressed
1,882,527,364 bytes. Its runtime capture failure remains a failure; these
compression checks do not qualify its default trace service.


The [native ARM64 v4 EFI build](../../verification/normal-v4-arm64-build-20261110.json)
now produces an ARM64 EFI executable from the pinned source, using native
Clang/LLD 21.1.8, a read-only source view and separate unprivileged objects.
Native media, record-policy, FAT, block-map and Lua controls pass. The initial
metadata-query failure is retained separately. The repository's amd64-only
bootinfo fixture supplies no ARM handoff result. The subsequent actual ARM64
firmware and userspace controls below provide their own scoped evidence;
final-media acceptance remains open.


The corrected full default-rc image also passes native xz integrity, exact
decompression identity and the original size gates: raw 2,554,348,032 bytes;
xz 1,882,519,844 bytes, 264,963,804 bytes below the compressed limit. This result
binds the corrected image's own bytes, separately from the preceding failed
runtime control and its compression result.


The [ARM64 EFI/USB runtime checkpoint](../../verification/normal-v4-arm64-runtime-20261110.json)
now boots that exact loader with the native CURRENT base/kernel and Python
runtime through ordinary rc startup. The production background trace service
retains all 5,296 sampled kernel-log bytes on each of two actual boots. All
three boot banks decode; the installer log remains empty. Each boot changes
only 9,837 bytes confined to its own trace session. The second boot uses a
fresh nonce and preserves the complete first session byte-for-byte. Both
returned FATs pass Linux and native FreeBSD read-only checks. Both guests
synchronize and stop themselves without network or keyboard input.

The initial fixture outer archive omitted `/etc`; its failed assembly and
sealed, valid RAM root are retained. A fresh outer archive fixes the omission.
The observer's optional `uname` probe used the wrong path and failed; no guest
`uname` result is inferred. The base-only RAM root also lacks kernel linker
hints and reports that fixture limitation. These are CURRENT base-system
controls; complete packaged ARM installer media, real installation, desktop,
earlier kernel/panic persistence, unexpected reset/power loss and physical
platform acceptance remain open.


The replacement [matching-worker audit](../../verification/default-live-trace-integration-20261110.json)
now completes on the exact corrected amd64 retained-root image: all 8,006 regular
paths are classified and all 2,395 dynamic ELF paths resolve. Native cleanup
and an unchanged final image checksum pass, with an independent owned-mount/MD
check. This qualifies that retained image with its then-current eight helpers;
it does not qualify the later installer relay or final CURRENT media.

## 1.6 installer evidence relay

The [source integration checkpoint](../../verification/installer-evidence-integration-20261110.json)
adds real installer hooks for phases, observed archive hashes, selected disk
fingerprints and partition identities, actual package registrations and the
final installer status. The older performance trace closes before pool export,
so its `exit` row is excluded from the persistent outcome. The actual EXIT
handler supplies the terminal result, including ABI/configuration preflight
failures before the full cleanup handler is ready. Tests retain status 23 at
that entry boundary and status 37 after a simulated
export failure even when the performance trace had already closed with zero.

A background collector pins the private performance-file inode and projects
only defined fields and bounded values. It never copies raw rows, output,
answers, URLs or configuration. Package identities come from one actual
name/version registry snapshot at finish or failure, avoiding duplicated
download/extraction events that would consume the bounded log. Numeric-only
versions remain strings. A 1,500-package control fits the unchanged content
limit with terminal-event reserve. The new ninth staged helper uses the
existing serialized native writer, contiguous attempt/event sequences, retry
idempotency and unchanged two-frame commit ordering. Invalid input and full
logs preserve earlier evidence; diagnostic failure cannot replace the
installer's result. The final drain is bounded independently of device I/O.

All 81 control groups pass on native FreeBSD ARM64, without skips; Linux passes
79 with two explicit native kqueue groups skipped. The native unit collector
uses a test delivery callback. A subsequent actual EFI/USB fixture tests
the real relay and writer; neither these controls nor that controlled producer
constitute a complete real installation. Actual target mutation/export, real
installation and final-media acceptance remain open.


The native relay control persists ten structured events through the production
writer and retains the controlled exit status 37 while excluding the earlier
performance-trace zero and a fake secret marker. All four banks decode, all
5,296 sampled kernel bytes and 1,638 installer-event bytes are retained, and
only 14,753 current-session bytes change. Linux and native FreeBSD read-only
FAT checks pass. No actual target layout or export operation is performed.

That control first exposed a real init race: RAM-root rc can start while the
boot USB partition is absent from GEOM. The failed boot retains an empty init
bank and its recorded refusal; the later installer relay succeeded. Shared
init capture now waits read-only for a specifically absent provider within a
30-second bound. It still refuses ambiguous/malformed candidates immediately
and does not retry payload writes. The repaired native boot observes two
absent snapshots followed by the ready provider, then records the complete
kernel snapshot and the installer control. This is a shared readiness repair,
not a fixed boot delay or a board-specific workaround.

A second native EFI/USB relay control forces an actual first-batch commit
before the producer finishes. Both frame sequences decode; the final ten
events retain status 37, preserve the complete earlier batch as a prefix,
and leave the first installer bank unchanged. Only 15,514 bytes change, all
within the current session. This validates incremental delivery on the actual
medium; it remains a controlled producer rather than a complete installation.
