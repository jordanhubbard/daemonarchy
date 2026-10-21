# 1.2 hardware test ISO preparation

TESTISO-001 prepares a real test image before the operator starts physical
qualification. It does not waive the final 1.2 completion ledger or authorize
publication. Hardware evidence is downstream of this test artifact.

## Current candidate boundary

No 1.2 test ISO is ready yet. The current source/ports workspace selection still
pins source `978fed917ba2b391c3eace661c21a7a65549cb23` and ports
`f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`. The retained 1.1.1 authoring worker
has a matching 1600028 jail and existing package/set caches; a separate older
native worker has a 1600027 jail. These are distinct selections, not interchangeable
inputs. Inspect current worker allocation and host-volume headroom before dispatch;
do not overlap an existing framework qualification or bulk job.

The live-only loader selection is now pinned separately in
[`verification/test-loader-selection.json`](../verification/test-loader-selection.json).
It selects source `848c4bc16f3e757c6c3179f1fed5fcb6cd7503c0` and the exact
732,672-byte EFI already exercised by the retained UEFI TFTP/NFS checks. All nine
compiled source identities were rechecked against that committed revision;
later uncommitted source work is not part of this selection. This changes neither
the selected kernel/world nor the installed system's loader.

## Explicit live loader selection

Prepare a private bundle directory containing `selection.json` (the exact public
selection above), `loader.efi`, and `loader.lua`. Both files must match the recorded
sizes and SHA256 identities. Set `TEST_LOADER_BUNDLE` to that directory when running
the selected build. The builder validates and copies the bundle into a fresh
stage. The final image hook checks it again and replaces only the live root's
`/boot/loader.efi` and `/boot/lua/loader.lua`, before poudriere creates its EFI
boot image. Native final-ISO inspection and UEFI boot must still prove that ordering
on the actual authoring toolchain.

Combining this unsigned development loader with a Secure Boot bundle refuses;
neither an old signed payload nor an arbitrary overlay may silently replace the
selected loader. Debugging remains disabled: no key or activation configuration
is created. Provision an explicitly selected private wired profile separately
using the source fork's loader-console runbook. This path does not qualify
Secure Boot or change the untouched installer sets and installed-system loader.

Six selection/refusal controls pass on the controller and native FreeBSD:
exact live payload and unchanged installer sets; changed Lua bytes; signed-bundle
conflict; input/destination aliases; invalid source/scope/extra destinations;
and preservation of read-only hardlinked jail inputs. Replacement creates a new
inode and preserves boot-file modes, rather than writing through shared links.
The two existing staging controls also pass natively. See
[`verification/test-loader-controls.json`](../verification/test-loader-controls.json).
The exact retained EFI/Lua bundle also prepares successfully on FreeBSD, with
matching output hashes. Inspection of the installed poudriere scripts confirms
that the post hook precedes hybrid-image build/generation, whose EFI image uses
the live root's loader. The inspected script identities are retained with the
controls. These eight controls are not assembly, boot, hardware
or lifecycle acceptance.

The installed controller's read-only Standard rebind plan still refuses with
`standard_rebind.binding_required`: the product retains a receipt policy without
a Standard lifecycle driver. This reproduces ADOPT-002's product migration gate.
The policy was preserved, and no manual assembly was substituted for the required
admitted lifecycle. Qualify the product binding migration through the framework
before dispatching assembly. The portable upstream migration is tracked in
[framework issue #107](https://github.com/jordanhubbard/literate-ai/issues/107).

The loader-debugging owner must provide the exact reviewed loader artifact,
source revision, compatibility scope and native/VM result. A loader-only test
image may retain an explicitly verified base/package selection; a changed
kernel/world requires a matching jail, external modules and source checkout
catalogue. A moving upstream branch is not a selected candidate.

## Preparation and readiness checks

1. Record exact control, loader, source/ports, desktop/compatibility and package
   catalogue revisions; hash loader bytes and base/kernel/lib32 MANIFEST sets.
2. Bind the existing signed checkout catalogue to the selected kernel identity;
   retain the builder's GPU module ABI checks. Do not silently use old signed
   boot payloads to overwrite a new debugging loader.
3. Select an available native worker and fresh staging/output names. Allocate
   the stage privately; preserve existing runs and cached input artifacts.
4. Execute the selected assembly through its actual admitted lifecycle. If that
   lifecycle still refuses, retain the concrete refusal and prepare its inputs;
   do not synthesize a receipt or label a manual probe admitted execution.
5. Verify resulting image size and hash, boot it in a disposable UEFI guest and
   confirm the intended loader bytes/debug behavior. Preserve BIOS coverage and
   installed-system loader behavior as separate explicit tests when affected.
6. Notify the operator with the actual test-ISO location, SHA256, selected fixes
   and known limits. Only then ask for physical hardware observations. A prepared
   plan, a loader binary or an older image is not a ready test ISO.

## Staging qualification

`python3 tests/iso-stage.py` passes two controls on the controller (0.043 seconds)
and native FreeBSD (0.141 seconds). Two concurrent allocations receive distinct
0700 directories; a subsequent attempt preserves both an old fixed-stage sentinel
and failed-run contents. Relative, missing, file and symlink parents refuse
without creating output. Shell syntax checks pass. These are narrow native
staging controls, not ISO assembly, boot or performance qualification.

The deliberate [retained source refresh](../verification/iso-stage-source-change.json)
records replaced and candidate bytes while preserving the adoption-time inventory.
Full native lifecycle, final hardware and release gates remain open.

Project authority validation passes after the explicit documentation review.
Full `litai verify` still refuses stale contract locks and the missing native
receipt, matching the unchanged control revision's result under the installed
CLI. Those pre-existing gates remain open; no lock or receipt was fabricated.

## Reviewed first-binding checkpoint

[Framework PR #108](https://github.com/jordanhubbard/literate-ai/pull/108) repairs
the receipt-only migration path without deleting policy. Its exact qualified wheel
at `73311c69` installs offline on FreeBSD with 37 verified distributions. Five
real CLI checks pass on a disposable copy of product revision `aadfa33f`, preserving
all receipt requirements and 42 historical evidence files. Thirteen installed
contract tests also pass. The [checkpoint](../verification/standard-first-binding-development.json)
retains both earlier probe-harness failures and the successful scope. The actual
product binding, active workspace/default CLI, native lifecycle receipt and ISO
remain unchanged. Qualify and apply the reviewed binding with its actual retained
profiles before dispatching assembly; hosted framework CI remains pending.
