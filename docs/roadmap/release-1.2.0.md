# 1.2.0 completion obligations

- **Status:** active
- **Owning queue item:** [RELEASE-001](active-work.md#release-001-deliver-120-through-first-class-freebsd-literate-ai-execution)
- **Completion / archival evidence:** Pending exact final LitAI release receipts,
  native/VM/physical acceptance and independently verified GitHub publication.

[RELEASE-001](active-work.md) carries the operator's goal: finish the existing
backlog and publish a new Daemonarchy release entirely through qualified
Literate AI execution. This ledger expands the queue and the remaining
[ROADMAP.md](https://github.com/jordanhubbard/daemonarchy/blob/main/ROADMAP.md) obligations. Every row is open for the new release;
prior evidence remains useful only within its original artifact/hardware scope.
There is no inherited waiver, current receipt or claim of release readiness here.

## Worker and evidence model

The controller may run on any qualified Literate AI host OS. Native FreeBSD build
and test actions run in FreeBSD; a VM's host OS never supplies its guest identity.
Use a dedicated native build worker for source/packages/images and reusable
caches; disposable guests for clean install, upgrade, rollback and boot checks;
and physical machines for graphics, radios, firmware and suspend acceptance.
QEMU guests and existing physical workers use private worker configuration.
Explicit provisioning owns VM sizing, exact guest inputs, supervision and bounded
cleanup; static registration does not imply automatic VM creation.

Signing remains on the protected signer. Public evidence carries source, wheel,
toolchain, guest/target and artifact identities, never private endpoints or keys.
The final release must use the exact admitted inputs through the LitAI lifecycle
and publication gates. Historical manual build logs and development-source probe
results cannot substitute for current installed-wheel receipts.

## Obligation ledger

| ID | Queue owner | Required completion and direct evidence |
| --- | --- | --- |
| R12-01 | ADOPT-002 | Qualified upstream FreeBSD contracts, OS Flavor, registration, alignment, native toolchain realization, paths, health, isolated execution and exact installed-wheel regression evidence; existing OS behavior remains qualified. |
| R12-02 | ADOPT-002 | Retained mixed source/binary admission, invalidation, current native receipts, artifact custody and release enforcement; changed input, failed test, missing evidence and unauthorized publication are rejected. |
| R12-03 | UI-001 | Multiple creative ANSI visualizer styles use actual disk, package, transfer and stage events; console, SSH/serial, small terminals, 16/256 colors, resize, reduced motion and plain logs pass; waits/failures never animate as success. |
| R12-04 | PKG-001 | Retain complete exact release package DAGs for every selection, including transitive/official/GPU/optional packages, provenance, hashes, sizes, edges and space estimates; reject stale or conflicting catalogues. |
| R12-05 | PKG-001 | One coordinator performs bounded parallel downloads and actual safe parallel installation of ready independent packages; package DB, files, scripts, triggers and services remain coherent. Competing pkg processes are insufficient. |
| R12-06 | PKG-001 | Native serial/parallel comparison reports download, staging, install/commit, total time and peak resources separately; shared dependencies, file/script conflicts, low disk, interruption, retries, integrity and BE recovery pass. |
| R12-07 | GUI-001 | Native colorful responsive install/update/remove UI shares planner, transaction identity and events; real input, accurate progress, reduced motion and failure/retry work; contribute required engine changes and application port upstream. |
| R12-08 | DEBUG-001 | Explicit wired loader/early-kernel debug profile, source ownership, NIC support, trust/session boundaries and exact symbols; retain actual early-boot and crash transport evidence and document genuinely unsupported phases. |
| R12-09 | HW-001 | NVIDIA installation, SDDM login and actual Hyprland rendering, external displays and suspend/resume pass on supported hardware; retain Intel/AMD regression evidence. CUDA/nvidia-smi alone is insufficient. |
| R12-10 | HW-001 | Resolve the recorded MacBook graphics, missing wireless and unexplained restart failures with exact hardware/build evidence; distinguish transport disconnect from reboot and retain failure diagnostics. |
| R12-11 | HW-001 | Resolve and qualify the recorded ASRock/RTX system's boot/firmware failure; network reachability or unrelated hardware success cannot close its physical acceptance. |
| R12-12 | HW-001 | Actual Bluetooth audio playback, output selection, volume, disconnect/reconnect/removal and reboot persistence pass; real keyboard/mouse pairing still works. Null transport is insufficient. |
| R12-13 | HW-001 | Actual certificate-validated PEAP/MSCHAPv2 and EAP-TLS exchanges, untrusted server rejection and reboot reconnect pass in installer/desktop paths; transferred credentials/certificates remain private. A controlled test network may provide this evidence. |
| R12-14 | HW-001 | Both selected-partition and selected-free-space installs preserve another OS/data/EFI entries; real Windows dual boot passes; invalid/insufficient-space selections fail before writes and no implicit resize occurs. |
| R12-15 | HW-001 | Physical Secure Boot enrollment preserves OEM/Windows trust; enforced boot, rejected untrusted components, signed maintenance and recovery pass with exact protected production authority. VM-only evidence cannot close physical enrollment. |
| R12-16 | RELEASE-001 | Final ISO QEMU BIOS/UEFI and plain/GELI unattended installation, actual Hyprland/login/rendering, keyboard/pointer, resizing and reboot pass; enforced UEFI uses the intended trust chain. |
| R12-17 | RELEASE-001 | Refreshed bhyve installation and graphical Hyprland acceptance, input, resizing and reboot pass, including the outstanding encrypted configuration and optional source/ports checkout selections. SSH-only acceptance is insufficient. |
| R12-18 | RELEASE-001 | Refresh/reconcile source and ports plus owned desktop/compatibility inputs; pin coherent snapshot/jail/packages/modules, retain native changed-port testport and clean bulk results, and submit upstream contributions. |
| R12-19 | RELEASE-001 | Existing-release upgrade, signed maintenance, injected failure, rejection, reboot, ZFS rollback and return pass on exact final inputs; retain physical desktop/application acceptance and recovery evidence. |
| R12-20 | RELEASE-001 | Final image/feed/checkouts checks bind kernel/driver/package identities, signatures, hashes, sizes, selected optional sources and artifact budgets; no preliminary-image result is relabeled as a final-image result. |
| R12-21 | RELEASE-001 | Review all documentation and release-by-release CHANGELOG, support tables, install/update/debug instructions and upstream links against final behavior and direct evidence. |
| R12-22 | RELEASE-001 | Full declared LitAI verification and release gates pass for exact final revision; publish the new GitHub release through the qualified method, verify immutable tag/assets independently and close each ledger row with its retained receipt. |

## Closure rule

A row closes only when its implementation and required native/VM/physical
acceptance exist and are bound to the applicable final source/artifact identities.
An upstream submission requires the submitted contribution, without inventing
maintainer acceptance. A platform limitation, unavailable physical device, stale
receipt or deferred implementation stays open. Any proposed scope change must be
an explicit operator decision; this ledger does not make one implicitly.

The next execution dependency is R12-01/R12-02. Framework work is tracked by
[issue 67](https://github.com/jordanhubbard/literate-ai/issues/67) and
[draft PR 68](https://github.com/jordanhubbard/literate-ai/pull/68). The retained
Standard execution route remains unqualified under reopened
[issue 22](https://github.com/jordanhubbard/literate-ai/issues/22); receiver and
wheel-bootstrap success cannot close R12-02.

The exact framework wheel at `89278c96` has passed wheel qualification and offline
native installation with 37 verified distributions. A native sample completed
public Standard rebind, documentation review and exact retained-source planning,
but authorized execution stopped before compilation because it demanded an unused
coding agent. The provider-neutral correction is tracked in
[issue 70](https://github.com/jordanhubbard/literate-ai/issues/70). This sample is
only a framework platform check; it cannot qualify Daemonarchy's complete retained
project or close either prerequisite row. The new native `pkg` host-install
realization is contributed in the same draft framework PR, with native and
installed-lifecycle qualification still required.

The subsequent qualified framework wheel at `d96f6b8b` also installed offline
with 37 verified distributions. Its native sample completed reviewed Standard
rebind, documentation review and fresh retained-source review without a coding
agent. Authorized execution now reaches Python toolchain admission, where it
refuses because the shared builder searches only unversioned aliases and the
aligned native interpreter is `python3.12`. The framework contribution is adding
versioned interpreter discovery and preserving structured CLI refusals. No
compilation, passing receipt, Daemonarchy lifecycle qualification or release
readiness is claimed from this attempt; the complete native positive and
changed-input/failed-test checks remain required.
