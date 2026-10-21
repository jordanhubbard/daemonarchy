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
inputs. The release authoring worker is also running an existing framework
qualification job; do not dispatch a competing bulk or image job into that run.

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
