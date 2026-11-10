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
- [scripts/release-check-1.3.1.py](../../scripts/release-check-1.3.1.py) binds
  the private native source, Poudriere, signing and ISO result files to the same
  release record and ISO hash. It requires current LitAI authority and locks;
  the unqualified full LitAI lifecycle receipt retains its separate status.
  For 1.3.1 it also binds the [October 24 MacBook operator
  decision](../../verification/macbook-release-decision-1.3.1.json): all
  pre-production checks passed by operator confirmation, and only the
  additional final-ISO physical rerun is waived. This does not waive native,
  signature, feed, image-integrity or publication verification and does not
  claim hardware-rooted attestation for the final ISO.
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

## Development split media transport

`tests/split-media.py` must prove that bounded independent XZ parts reconstruct
exactly the selected raw-image identity, with a trusted manifest pin, canonical
part order, complete geometry and individual compressed/raw hashes. Refuse
missing/extra parts, unsafe names, duplicate/unknown fields, corrupt/truncated or
concatenated streams, oversized expansion, nonregular inputs and output races.
Retain failed outputs privately and never overwrite earlier media. Keep the
existing raw-image and strictly less than 2 GiB public-asset limits unchanged.

Run the transport against actual complete retained media as well as refusal
fixtures. Source/world/ABI, signing, platform boot/install/desktop/recovery and
lifecycle admission remain artifact-specific requirements. Require explicit
`xz-parts@1` release descriptors, trusted manifest pins, complete approved physical
asset maps and full raw-image verification. `tests/release-split-media.py` must
exercise the existing signed-boot/certificate and closure gates;
`tests/release-split-flow.py` must cover draft authoring, published-current metadata,
refusal before writes and download-document consistency. Preserve historical
single-image semantics. `tests/master-split-media.py` must exercise complete
reconstruction, both architecture selections, transfer tampering, private evidence
retention, pin-bound resume, all-device preflight and write/readback refusal.
Keep fixture boundaries explicit. Complete packed RAM-root content/runtime
integration and actual publication/target/device checks before release admission;
controller controls alone do not establish it.
