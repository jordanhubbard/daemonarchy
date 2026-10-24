# Release assembly and qualification acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Test-image assembly isolation

`tests/iso-stage.py` exercises concurrent private staging, preserved prior/failed
artifacts and invalid-parent refusal. Each test ISO also needs exact inputs and
actual native assembly/boot evidence; physical results follow artifact readiness.

## Existing candidate checks

- [scripts/verify-release-assets.py](../../scripts/verify-release-assets.py) binds
  staged public asset hashes to the release record and validates the signed boot
  bundle. Its `--published` mode also checks the exact GitHub latest release,
  tag target and uploaded digests. Its result covers artifact identity only.
- [tests/live-image-runtime.sh](../../tests/live-image-runtime.sh)
- [tests/live-image-budget.sh](../../tests/live-image-budget.sh)
- [tests/checkout-kernel-identity.sh](../../tests/checkout-kernel-identity.sh)
- [test-qemu.sh](../../test-qemu.sh)
- [test-bhyve.sh](../../test-bhyve.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **Loader-only test media:** bind exact EFI/Lua identities and source revision;
  reject tampering and conflicting signed payloads before assembly. Keep debug
  keys/activation explicit, installer sets unchanged and installed loader coverage
  separate. Inspect and boot the final ISO before requesting hardware acceptance.

- **Unified development and cut-over:** execute real source and ports closures
  through the same installed Literate AI entrypoint in the parallel hierarchy.
  Refresh upstream inputs without changing wrapper files in upstream directories;
  retain exact selection, invalidation and build/test/pkg evidence. Compare
  equivalent clean/warm/change workloads before executor selection, then exercise
  the designated cut-over and rollback. Checkouts or validation-only commands do
  not satisfy actual build execution.

- **Per-unit packages and measured build improvement:** every unit has a real
  versioned pkg product and bound source/build/dependency provenance. Compare
  native baseline and optimized clean, unchanged and changed-unit ISO workflows
  with pinned inputs, toolchains, resources and cache state. Retain actual timings,
  action counts, artifact identities and independent installation/rollback tests;
  executor replacement alone is not a performance result.
- **Complete source and ports Component coverage:** retain complete pinned-tree
  enumeration and canonical contracts for all native build units and ports
  origins; demonstrate zero unowned inputs and explicit shared relationships.
  Select target/options-specific dependency closures and reject missing owners,
  unresolved edges and stale locks. Unselected catalog entries remain visible;
  aggregate build success cannot replace per-component acceptance evidence.
- **Coherent immutable inputs:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Artifact-bound evidence:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Publication consistency:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Honest release decisions:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
