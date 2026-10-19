# Release assembly and qualification acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [tests/live-image-runtime.sh](../../tests/live-image-runtime.sh)
- [tests/live-image-budget.sh](../../tests/live-image-budget.sh)
- [tests/checkout-kernel-identity.sh](../../tests/checkout-kernel-identity.sh)
- [test-qemu.sh](../../test-qemu.sh)
- [test-bhyve.sh](../../test-bhyve.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

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
