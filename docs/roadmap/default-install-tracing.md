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
capture. It also exceeds the existing raw release-image budget, so it is not
the final default-media solution. The amd64
BIOS/hybrid builder still needs integration; this helper deliberately refuses
layouts with partitions other than a single ESP. Automatic loader, kernel and
installer capture, interrupted writes and physical reset/power-loss acceptance
remain open. Neither a successful builder nor the independent write control
closes those gates.
