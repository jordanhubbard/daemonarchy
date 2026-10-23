# Product architecture and acceptance traceability

[PROJECT.md](https://github.com/jordanhubbard/daemonarchy/blob/main/PROJECT.md) defines product intent. Components below describe
logical responsibilities across repositories; they are not claims of separately
buildable or generated artifacts. Existing source remains implementation authority.

| Goals | Component | Retained implementation | Acceptance boundary |
| --- | --- | --- | --- |
| G1, G7 | [Installer](https://github.com/jordanhubbard/daemonarchy/blob/main/components/installer/component.md) | Installer overlay, disk/layout/configuration helpers and target completion | Storage preservation, actual installation, integrity, root/devfs continuity and eventual measured visual progress |
| G2, G7 | [Desktop](https://github.com/jordanhubbard/daemonarchy/blob/main/components/desktop/component.md) | daemonarchy-desktop repository; theme, menu and graphics integration | Actual greeter, authenticated desktop, input and application rendering; future GUI interaction |
| G2 | [Compatibility](https://github.com/jordanhubbard/daemonarchy/blob/main/components/compatibility/component.md) | omarchy-freebsd repository, service/session shims and native panel backends | Native service and peripheral semantics; explicit missing-device and unsupported states |
| G3 | [Updates](https://github.com/jordanhubbard/daemonarchy/blob/main/components/updates/component.md) | Adoption/checkouts helpers and external desktop boot-environment tools | ABI refusal, preserved package/user choices, actual update/rollback/return |
| G4 | [Diagnostics](https://github.com/jordanhubbard/daemonarchy/blob/main/components/diagnostics/component.md) | Pairing/rescue tools, observers and controller receiver | Approval, revocation, bounds, identity, abrupt loss and owned cleanup |
| G5 | [Verified boot](https://github.com/jordanhubbard/daemonarchy/blob/main/components/verified-boot/component.md) | secureboot build/sign/bundle/maintenance tools and retained source patches | Exact trust closure, actual enforcement/rejection and maintenance/recovery |
| G6, G8, G9 | [Release](https://github.com/jordanhubbard/daemonarchy/blob/main/components/release/component.md) | ISO/feed/checkouts assembly, pinned-tree discovery and publication scripts; planned complete source/ports Component execution | Full-tree ownership, per-unit pkg provenance, variant-aware selected closures and measured build/packaging improvement; exact artifacts and native/VM/hardware evidence |
| G3, G7 | [Package engine](https://github.com/jordanhubbard/daemonarchy/blob/main/components/package-engine/component.md) | Pinned catalogue graph collector; current installer uses its existing package operations | Complete release DAG, native solver acceptance, coordinated parallel installation, failure/retry/recovery and measured performance |

## Source custody and repository boundaries

[The retained baseline](../../verification/retained-inputs.json) records every
tracked file at the adoption starting commit, one owning Component, its SHA-256
and executable bit. It demonstrates preservation during this authority change;
it is not a framework input-admission manifest or current test receipt. Shared
consumers use public contracts; the owner must review consumers when changing a
shared input. Future source changes require a deliberate baseline refresh.

Desktop and compatibility sources remain in their own repositories. Their local
contracts describe product integration without moving or regenerating upstream
source. The [release selection](../../verification/release-1.1.1.json) binds the
published installer, FreeBSD source/ports, desktop and feed selections. The
compatibility identity is also recorded from the qualified release selection;
none of these identities is inferred from an ambient checkout. Complete native
input admission, including toolchains and firmware, remains unfinished work.

FreeBSD source and ports implementations remain upstream-maintained retained
inputs with their normal synchronization and contribution procedures. Their
complete selected trees must be represented as canonical Components under G8
and [COMP-001](../roadmap/freebsd-components.md), including shared/support inputs
and unselected origins; opaque whole-tree wrappers are insufficient. Preserve
source authority and pin actual selections. Neither catalog registration nor
a moving branch is a qualified dependency or native acceptance result.

The owned [daemonarchy-src build workflow](../source-builds.md) prepares pinned
FreeBSD world/kernel/source packages and installer sets on the native build
worker. Its unsigned build records and controller tests do not qualify framework
execution, installation, VM boot, module compatibility, signing or hardware.
SRC-001 owns preparation; ADOPT-002 and RELEASE-001 retain their acceptance gates.
PERF-001 permits a replacement build system while preserving source/ABI and
dependency correctness. The pinned-tree discovery helper supplies diagnostic
inputs, with [producer/result identities](../../verification/native-tree-discovery.json);
it does not fabricate canonical contracts, package products or receipts.

## Cross-component invariants

- **Installation success:** selected storage + installed payload integrity +
  accounts/ownership/caches + durable completion. Desktop rendering is an
  additional acceptance result, not an inference from successful extraction.
- **Graphics readiness:** attached active driver plus device nodes. Actual user
  desktop/application acceptance remains separate from a working greeter.
- **Update safety:** compatible base/kernel/driver/package identities and a real
  recovery path. Boot-environment metadata alone is insufficient.
- **Diagnostic truth:** an SSH disconnect, a new listener and a reboot are distinct
  observations. Collection must retain bounds, cleanup and privacy guarantees.
- **Release evidence:** a test identifies its input image, target, mode, scope and
  outcome. Rebuilt-image claims require matching evidence or an explicit exception.
- **Parallel packages:** completed prerequisites do not by themselves make scripts,
  database operations or file-side effects safe to execute concurrently.

## Acceptance inventory and evidence scope

[The acceptance inventory](../../verification/acceptance-inventory.json) maps
existing test candidates and planned gaps to Components. Read each test before
running it: native FreeBSD, root, disposable storage, VM firmware and controller
requirements differ. HACKING.md remains the command/runbook authority. This
adoption executes metadata/preservation checks, not the expensive release matrix.

The [1.1.1 qualification record](../testing-1.1.1.md) remains historical evidence.
Its final-ISO boot/storage checks, preceding-image full installs and clone tests,
physical HP upgrade/rollback/login/application results and unrun/waived cases
retain their distinct scopes. MacBook GPU/Wi-Fi failures remain open.

Future current receipts need exact source and binary inputs, target/worker and
command identities, artifact hashes, positive/negative test results, explicit
skip/waiver policy and invalidation rules. Raw keys, credentials, host addresses
and private debug logs do not belong in committed authority.

## Adoption boundary

The automatic `litai onboard adopt` plan reports `blocked-no-driver` and proposes
quarantining the existing tree. It was inspected but not applied. This project
instead authors the supported project/Component contracts in place and explicitly
selects root repository authority through the reviewed `litai reparent none`
operation. No converted-stage or regenerated-source evidence is fabricated.

The stable installed CLI remains Literate AI 1.3.0 from the 1.1.1 system. A
separate `litai-dev` on the HP uses the exact reviewed framework wheel for the
source fork's Standard binding. It validates `/usr/src` authority and three
locks; no retained test receipt or native execution qualification exists.
Framework issue [#22](https://github.com/jordanhubbard/literate-ai/issues/22)
tracks the remaining executable capability and evidence gates. ADOPT-002 must
qualify native FreeBSD execution and mixed-input custody before release
enforcement changes. This adoption does not release a new product version. The reviewed public
`project adopt-original` operation now selects original source authority in place
on the product, preserving 272 tracked entries and adding only authority metadata
and its evidence/mutex. This is neither retained lifecycle admission nor
regenerative conversion authority. Explicit complete native manifests/profiles
remain required for executable work.


## Current tooling and gate interpretation

The committed Component locks resolve product contracts on the controller's
`host` target. They do not select a FreeBSD toolchain or prove native execution.
The native receipt policy anchors its candidate runner to the retained QEMU
harness bytes and requires build, acceptance, source/dependency and test evidence.
That harness does not yet produce a framework receipt; ADOPT-002 must qualify
its adapter and complete the inventory, not fabricate `verification/current.json`.
The configured receipt gate therefore fails closed while authority and contract
locks can pass. Historical 1.1.1 evidence remains separate.

Root Markdown entrypoints remain at their established paths. Links from declared
framework documentation to those root documents use the public repository URL
because the current documentation-root schema admits directories rather than
individual root files. The Component catalog is independently validated; its documentation links use
the public repository paths so mutable resolver mutexes are not documentation
assets. Source
indexing is disabled. Future framework updates must preserve these boundaries.

<!-- literate-ai:authority-reviewed sha256:2c8086f140b6ca25698ba32035ea1074abb0cc19042bf8b62bc0425decf8b42a -->


## Rechecking preservation

The adoption checked all 119 protected original non-Markdown files (excluding the
intentional ignore-policy edit), including scripts, binaries/assets, source patches
and public trust material. Their hashes and executable modes matched the baseline.
Use the per-file identities in `verification/retained-inputs.json` to repeat that
comparison. Documentation changes are intentional and separately reviewed. Refresh
the baseline only as part of a reviewed implementation change, never just to hide
a mismatch. `verification/adoption-checks.json` summarizes these checks and the
expected missing native receipt; it is not a signed or current lifecycle receipt.
