# Active work

[PROJECT.md](https://github.com/jordanhubbard/daemonarchy/blob/main/PROJECT.md) owns product goals and completeness.
Checkboxes below are execution status, not substitutes for test receipts.

## Open pull-request landing queue

[Draft PR #12](https://github.com/jordanhubbard/daemonarchy/pull/12) carries native
Component discovery, build-performance and operator-development work.
[Issue #11](https://github.com/jordanhubbard/daemonarchy/issues/11) tracks the broader
1.2.0 release. Existing release/test worktrees remain retained.

### [x] ADOPT-001 — Establish product-wide Literate AI authority

- **Priority:** P1
- **Owner:** project requirements and Component contracts
- **Direction:** Adopt Literate AI across the whole Daemonarchy product in stages while retaining source, native tests and release history.
- **Conclusion:** Author in-place project goals, logical Component contracts and acceptance mapping; automatic quarantine conversion is blocked-no-driver and is not applied.
- **Depends on:** none
- **Implementation:**
  - [x] Declare seven goals and eight Component contracts with public integration boundaries.
  - [x] Map every retained test file, external repository selections and published 1.1.1 assets.
  - [x] Reconcile root guidance, documentation reachability and the feature overview.
- **Evidence:**
  - [x] `litai project validate .` passes; eight `host` contract locks are current.
  - [x] Root and retained-boundaries skills pass static schema/security/license/quality evaluation.
  - [x] All 119 original non-Markdown files except the deliberately updated ignore policy retain their original bytes and executable modes.
  - [x] `litai verify` reports authority/locks passing and the expected missing native receipt; no acceptance is fabricated.
  - [x] [Adoption PR #10](https://github.com/jordanhubbard/daemonarchy/pull/10) security check passed on c517c4c; the final closure commit must pass again before merge.

Evidence: `verification/adoption-checks.json`. Native execution and release enforcement belong to ADOPT-002, not this completed-authority scope.

### [ ] ADOPT-002 — Qualify retained native execution and release enforcement

- **Priority:** P1
- **Owner:** native lifecycle integration and framework boundary
- **Direction:** Integrate existing FreeBSD build, test, signing and release procedures without transferring source authority.
- **Conclusion:** Do not enable framework execution or publication until exact mixed source/assets, worker/toolchain, privileged cleanup, artifact custody and current receipt paths are demonstrated; the installed candidate provides the retained handler, while the actual product profile and native acceptance remain unfinished.
- **Depends on:** ADOPT-001
- **Implementation:**
  - [x] Audit the retained execution handler on current framework main and reconcile [framework issue #22](https://github.com/jordanhubbard/literate-ai/issues/22): the issue was reopened because authorized execution still unconditionally refuses. Actual execution qualification remains open below.
  - [ ] Bind the actual FreeBSD target, action inventory, external inputs, privileged cleanup and protected signer.
  - [ ] Qualify current native receipts, artifact custody and release enforcement.

Next action: bind the actual source/ports compiler, sysroot and input closure to executable retained profiles and earn installed native admission. The product controller also retains a receipt policy without a lifecycle driver; the reviewed Standard first-binding command refuses that partial configuration with `standard_rebind.binding_required`. Qualify an explicit product-policy migration through the owning framework before product execution; do not remove existing policy to force initial binding.
- **Evidence:**
  - [ ] Actual installed CLI accepts retained native execution; source and binary invalidation works; native tests and artifact hashes are current; failed or omitted evidence blocks publication; existing release workflow is reproduced.

### [ ] UI-001 — Deliver measured retro installer visualizers

- **Priority:** P2
- **Owner:** installer and desktop Components
- **Direction:** Use colorful Winamp-inspired ANSI animation to show useful installation stage, disk, package and network activity.
- **Conclusion:** Drive animation from actual progress while retaining plain output, diagnostics, reduced motion and terminal compatibility.
- **Depends on:** none
- **Implementation:**
  - [ ] Prototype multiple styles from recorded events; implement stage-aware presentation; validate on physical console and SSH/serial.
- **Evidence:**
  - [ ] Useful readable metrics, genuine waiting/failure states, resize and reduced-motion behavior, bounded cost and native console demonstrations.

### [ ] PKG-001 — Implement the release package DAG and safe parallel transactions

- **Priority:** P1
- **Owner:** package-engine Component
- **Direction:** Plan the complete release package closure and pursue parallel download and leaf-package installation.
- **Conclusion:** Use exact catalogue identities and one coordinator; graph independence alone does not establish safe script, database or file-side-effect concurrency.
- **Depends on:** none
- **Implementation:**
  - [ ] Generate complete DAG for every selection; implement coordinated bounded scheduling; publish structured progress; exercise retry, failures and recovery.
- **Evidence:**
  - [ ] Native dependency closure and integrity pass; real parallel installation improves measured time; side-effect conflicts, interruption and rollback are handled.

### [ ] GUI-001 — Deliver a colorful fast graphical package manager

- **Priority:** P2
- **Owner:** desktop and package-engine Components
- **Direction:** Provide the same useful visual progress and parallel execution in graphical package management, contributing a port if a new application is needed.
- **Conclusion:** Evaluate the current manager; share the transaction engine and progress semantics rather than build a competing planner.
- **Depends on:** PKG-001
- **Implementation:**
  - [ ] Evaluate extension path; implement responsive install/update/remove plans and visuals; prepare upstream application port if needed.
- **Evidence:**
  - [ ] Actual native UI, input, shared plan identity, accurate progress, failure/retry and packaging tests pass.

### [ ] SRC-001 — Establish owned FreeBSD source builds and packages

- **Priority:** P1
- **Owner:** release and diagnostics Components; daemonarchy-src fork
- **Direction:** Build modified FreeBSD-CURRENT from the owned source fork, retaining upstream provenance and coherent kernel/world/source package selections.
- **Conclusion:** Introduce clean exact-commit native builds with isolated objects/staging, GENERIC and diagnostic profiles, pkgbase and installer-set outputs, bounded jobs and verifiable build records. Do not install on build workers or publish unsigned development outputs as releases.
- **Depends on:** ADOPT-002 for framework execution and release qualification
- **Implementation:**
  - [x] Author the native plan/build/verify controller in [source PR #4](https://github.com/jordanhubbard/daemonarchy-src/pull/4); 11 refusal/custody tests pass locally, in CI and on FreeBSD.
  - [x] Prepare optional filemon/meta-mode capture and immutable per-phase snapshots in source revision `a2f44e0b96c0`; seventeen controller checks pass locally and in controller CI. The declared worker bootstrap now enables owner-only filemon access and its unprivileged readiness inspection passes; all 26 current controller/bootstrap checks pass on FreeBSD. Full traced-build execution remains unqualified.
  - [ ] Complete native end-to-end build/package/verify qualification. The quiet traced run reached completed set generation but failed metadata capture on a 39 MB source-archive record. The bounded streaming correction passes 30 native checks and captures the actual record; an independent audit verifies 537 artifacts and all eight sets. [Outcome evidence](../../verification/native-traced-build-quiet-result.json) preserves the original failure; full lifecycle acceptance remains open.
  - [ ] Produce the first baseline world/kernel/package/set build and retain identities. The 12-job GENERIC build at `92276fc76c65` passed world, kernel and pkgbase, then failed its first set-staging attempt. An isolated replay of the exact 219-header install passed; the root cause remains unproven. An exact-plan resume retained the failure and completed sets; 533 artifacts byte-verify and all eight MANIFEST set hashes independently verify. The source archive audit found all 138 symlinks dereferenced and build-user ownership; an isolated corrected source archive now matches every Git file and symlink with root ownership. ISO and native acceptance remain open. Its [plan and scope](../source-builds.md) are retained.
  - [ ] Qualify VM boot, installer set admission, matching jail/external modules, signing and rollback before production selection.
- **Evidence:**
  - [ ] Exact source/config/toolchain/log/artifact identities and failure refusal checks; native package output; VM/hardware results remain separate.

### [ ] DEBUG-001 — Qualify earlier wired network debugging for 1.2

- **Priority:** P1
- **Owner:** diagnostics and verified-boot Components
- **Direction:** Investigate loader and early-kernel network debugging using a supported hard-wired NIC.
- **Conclusion:** Existing GENERIC networking facilities do not establish loader-to-early-kernel transport; design source-fork, trust and crash coverage before claiming support.
- **Depends on:** none
- **Implementation:**
  - [ ] Define transport and authorization boundaries; select supported NICs and matching symbols; implement and qualify the explicit debug profile.
- **Evidence:**
  - [ ] Actual early boot and crash traffic is retained on a controller with documented unsupported phases and protected private state.

### [ ] HW-001 — Close remaining physical hardware qualification gaps

- **Priority:** P1
- **Owner:** desktop, compatibility and diagnostics Components
- **Direction:** Keep unresolved GPU, radio, boot and restart behavior explicit while extending physical acceptance.
- **Conclusion:** HP desktop/application acceptance passed; MacBook GPU/Wi-Fi and earlier restart causes, other platform boot failures and radio/suspend checks remain open.
- **ASRock availability:** The operator reports the RTX system still hangs in firmware and cannot enter setup or the boot menu, even with other USB devices disconnected and the keyboard directly attached. Firmware recovery is pending; no current Daemonarchy boot or physical acceptance result can be obtained from it. Keep R12-11 open.
- **MSI video:** The October 18 recording ends readable output at `atrtc0: Warning: Couldn't map I/O.` before the display blanks, with no visible panic. The second video confirms the RTC-disable/panic flags and advances to `sc0 failed to probe on isa1` before blanking, without a visible panic. Repeated Intel SPMC constraint-format warnings motivated a `debug.acpi.disabled="spmc"` comparison, which the operator reports made no difference; the exact installer artifact remains unidentified. The [analysis](../testing-1.1-hardware-observations.md#msi-startup-video-reviewed-2026-10-18) records the movie identity, observed scope and source-backed diagnostic; no default quirk or fix is qualified.
- **Depends on:** none
- **Implementation:**
  - [ ] Retain exact hardware and artifact scope; investigate known failures without conflating transport loss and reboot; qualify actual rendering, wireless and recovery.
- **Evidence:**
  - [ ] Native/operator results identify exact hardware and build, with unresolved or unrun cases remaining open rather than waived into passing.

### [ ] RELEASE-001 — Deliver 1.2.0 through first-class FreeBSD Literate AI execution

- **GitHub issue:** [#11](https://github.com/jordanhubbard/daemonarchy/issues/11)

- **Priority:** P1
- **Owner:** whole product, release and acceptance
- **Direction:** Finish all existing Daemonarchy backlog work and publish a new release entirely through the qualified Literate AI method.
- **Conclusion:** The existence proof must include actual native build, complete declared testing, artifact custody and publication; authority-only adoption, waived backlog, or an external manual release is insufficient.
- **Depends on:** ADOPT-002,UI-001,PKG-001,GUI-001,DEBUG-001,HW-001,SRC-001,COMP-001
- **Implementation:**
  - [x] Inventory current roadmap and queue obligations in [the 1.2.0 completion ledger](release-1.2.0.md), including inherited Bluetooth, enterprise Wi-Fi, dual-boot, bhyve and physical trust/graphics gaps.
  - [ ] Contribute and qualify upstream FreeBSD platform and retained execution support; bind private native workers and VM supervision; complete backlog implementations and acceptance; run the exact final release through Literate AI and verify publication.
- **Evidence:**
  - [ ] Every inherited backlog obligation has direct completion evidence; native and virtual/physical acceptance match exact final artifacts; full LitAI verification and release gates pass; published new release and immutable assets are verified.

### [ ] COMP-001 — Model complete FreeBSD source and ports trees as Components

- **Framework issue:** [#74](https://github.com/jordanhubbard/literate-ai/issues/74)
- **Detailed plan:** [Complete source/ports Component coverage](freebsd-components.md)

- **Priority:** P1
- **Owner:** source and ports Component inventories; framework retained native lifecycle
- **Direction:** Represent all of /usr/src and all of /usr/ports as Literate AI Components, not opaque external trees.
- **Conclusion:** Require complete pinned tree ownership, native build-unit and port-origin contracts, target/options variants, dependency composition and honest per-component evidence while preserving upstream implementation authority.
- **Depends on:** SRC-001, ADOPT-002
- **Implementation:**
  - [x] Record complete-tree coverage, component granularity, variant and dependency requirements in G8 and the release Component contract; file framework issue #74.
  - [x] Retain pinned-tree diagnostic inventories and nine portable discovery checks; [producer/result identities](../../verification/native-tree-discovery.json) record candidate ownership separately from canonical admission.
  - [x] Observe the native `bin/ls` directory closure with explicit amd64/host contexts, shared Makefile inputs and cycle/failure refusal; [scope and identities](../../verification/native-dirdeps-observation.json) retain its diagnostic limits. The first full sweep exposed unqualified extra-directory/context parsing errors. The corrected collector preserves those paths and returned query output; eleven portable checks and a native two-seed probe pass their observation/refusal expectations. Re-observe full coverage and reconcile stale declarations with actual build actions before canonical binding. Full native catalog/action resolution remains open.
  - [x] Author and lock the first original header/parser/utility contracts in the source fork, apply reviewed in-place original authority and bind the installed Standard lifecycle. [Current checkpoint](../../verification/original-source-authority.json) keeps three registered/locked units separate from zero admitted units and zero qualified per-unit packages. Explicit FreeBSD/pkg Flavors resolve; the HP's isolated development CLI validates `/usr/src`. Compiler/runtime admission, complete ownership, execution and system framework renewal remain open.
  - [ ] Admit every source/build/support input and ports origin through canonical Component catalogs and locks; reject missing or ambiguous ownership.
  - [ ] Connect native actions and conditional dependencies to retained execution, receipts and the exact release closure.
  - [ ] Qualify the [first native source composition proof](freebsd-components.md#first-native-source-composition-proof): compile original application/library source with admitted compiler resources, headers and sysroot; run original tests and independent cases; produce per-unit pkg products; observe actual invalidation and relocated VM installation/recovery. Exported precompiled-helper and package-format fixtures retain their narrower custody/integration scope.
  - [ ] Acquire the [observed bootstrap compiler closure](freebsd-components.md#bootstrap-compiler-closure), including native linker-script references, with explicit seed provenance and input budgets; prove relocated sysroot resolution before treating it as an admitted compiler SDK. The retained read-only inventory is diagnostic evidence only.
- **Evidence:**
  - [ ] Full selected trees have zero unowned inputs, all origins are represented, and catalogued/admitted/built/accepted states remain distinct.
  - [ ] Changed source, options, dependencies, toolchain or artifact invalidates the applicable receipts; exact native release closure passes installed framework and runtime qualification.

### [ ] PERF-001 — Execute native Components and substantially accelerate ISO builds

- **Detailed plan:** [Native Component execution and build performance](build-performance.md)

- **Priority:** P1
- **Owner:** release build graph, native Component lifecycle and build-system Flavors
- **Direction:** After establishing the source/ports graph, use LitAI to execute literal Components and substantially improve FreeBSD ISO build and packaging time; replacing make with Bazel, Buck2 or another suitable system is authorized.
- **Conclusion:** Measure the current native baseline, establish complete package/provenance/dependency coverage, and choose execution, caching, incremental and packaging changes from evidence. Preserve exact output correctness and native acceptance; a wrapper or renamed executor is insufficient.
- **Depends on:** COMP-001
- **Implementation:**
  - [ ] Capture baseline phase, action, packaging and end-to-end timings with exact inputs and resource limits.
  - [ ] Admit source/ports graph units as canonical executable Components with versioned pkg products and full provenance/dependency information.
  - [ ] Compare and implement supported native or alternative build execution, caching, parallelism and packaging strategies.
  - [ ] Demonstrate materially faster clean, unchanged and changed-component ISO workflows without missing rebuilds or weakening acceptance.
- **Evidence:**
  - [ ] Same-target baseline/optimized measurements retain source, configuration, toolchain, cache/resource state, action counts, output hashes and test results.
  - [ ] Native Component invalidation, per-unit pkg provenance, complete dependency closure, packaging, ISO installation and rollback remain correct.

### [ ] DEV-001 — Provide an operator-ready native Component development system

- **Priority:** P1
- **Owner:** release Component, source and ports forks, native framework lifecycle
- **Direction:** Make the complete source and ports Component build, test, package, ISO creation and installation system available on the operator development workstation at /usr/src and /usr/ports, managed by Literate AI.
- **Conclusion:** Preserve the running desktop and existing data; deploy editable fork checkouts and the qualified framework, then prove unchanged and changed-input incremental builds, tests, package provenance, ISO creation and installation against exact native inputs. Checkout availability alone does not complete this work.
- **Depends on:** COMP-001, PERF-001
- **Parallel migration:** [Workspace and executor comparison](native-workspace.md).
  The operator prioritizes a common `litai-dev` interface and substantial elapsed
  time reduction over preserving old build interfaces. Establish an independent
  `/usr/daemonarchy` hierarchy and wrap selected native make targets first;
  choose Bazel or another executor using equivalent native measurements.
  **Next action in progress:** deploy the reviewed ports metadata from
  [ports PR #7](https://github.com/jordanhubbard/daemonarchy-ports/pull/7) through
  a new exact workspace selection, then connect source/ports retained build
  profiles to the installed common CLI;
  qualify real target execution before selecting the cut-over.
- **Source prototype:** [Five-owner retained profile](../../verification/native-source-profile.json)
  at source commit `0d7583758a2f9eadc83fd5077ec2957522cbc9ab` passes both source CI
  runs. Installed native execution has produced selected compiled products;
  terminal run evidence, original privileged tests, independent acceptance and
  per-unit packages remain open. Preserve the running build-worker overlay and
  the operator's preceding preview selection. Framework #84 owns the separately
  measured strict-SBOM overhead; its repair needs full and installed/native renewal.
- **Subsequent build-worker preview:** framework `ca604c00` passes the complete
  local regression (1,855 passed, 42 skipped) and seven installed native SBOM
  checks. The [preview record](../../verification/native-development-preview-ca604c00.json)
  binds its canonical wheel, reviewed source rebind and corrected native profile.
  All 62 source-controller checks pass on FreeBSD. The source lifecycle is
  finished with captured CLI exit 2 after 2,037.584 seconds. Compilation and
  documentation have empty stderr; original tests report 23 passes and one
  root-required skip. The lifecycle correctly refuses the unauthorized skip;
  independent acceptance, source/ports package admission and cut-over remain
  open. Framework #85 owns scoped secondary-test-user access.
- **Qualified controller renewal:** framework `d6070ba5` passes the full
  regression (1,865 passed, 42 skipped) and installed-wheel qualification. Its
  [renewal record](../../verification/native-development-preview-d6070ba5.json)
  binds the verified controller dependency wheelhouse and reviewed source
  rebind. Native dependency production completed with exit 0 in 991.19 seconds;
  the verified 37-distribution closure bootstraps on the native worker and the
  disposable guest. Installed native checks report 29 passes, one optional
  source-corpus skip and no failures. Three warm input verifications have a
  median of 9.227105 seconds versus 19.794351 seconds for the baseline; this
  is not a whole-build comparison. The guest also verifies installed module
  bytes and real Ed25519 signing. Seven isolated
  native ACL checks cover selected reads, denied unrelated/new-file access,
  denied writes, revocation and exact original ACL restoration. This backend
  probe does not implement framework grants or complete original acceptance.
- **Current framework evidence:** [69 native retained-project checks pass](../../verification/native-retained-acceptance.json) at local checkpoint `567e0f8a4092`; full framework regression, installed-wheel qualification and public runtime/receipt integration remain open. The installed-wheel smoke harness still uses Linux expectations on FreeBSD; production initialization already has a FreeBSD selector.
- **Implementation:**
  - [x] Prepare conventional editable source and ports checkouts, framework tooling and a documented operator entry point. [Native checkpoint](../../verification/operator-development.json): `/usr/src` is current at the reviewed source-fork commit, and isolated `litai-dev` validates it with the exact bound framework wheel. The stable CLI remains installed; complete lifecycle remains open.
  - [x] Deploy independent source/ports checkouts, control, objects, staging,
    packages, cache and evidence below `/usr/daemonarchy`. The
    [workspace checkpoint](../../verification/native-workspace.json) verifies the
    same exact selection on both native roles and separate ZFS storage outside
    boot environments; all eight workspace checks pass on each FreeBSD host.
  - [ ] Qualify regular upstream imports without wrapper edits throughout upstream
    source directories. The independent-Git fixture passes fetch/pin preservation;
    full native refresh and selection/cut-over acceptance remain open.
  - [x] Probe actual make targets for the original parser/utility and the LZ4 port
    in isolated outputs. The PIE library variant links correctly; default upstream
    port checks and native pkg creation pass. Preserve the first link failure.
    The original 24-case source ATF inventory now records 23 passes and one
    root-required skip; privileged and independent acceptance remain open.
    These direct-make diagnostics are not installed LitAI target qualification.
  - [x] Install the exact candidate wheel on both native roles and validate
    both reviewed projects and all five native locks in separate review checkouts.
    The [candidate checkpoint](../../verification/native-development-cli.json)
    records dependency/import smoke checks, preserved active selection and
    missing receipts. This qualifies metadata availability, not target execution.
  - [ ] Expose selected source and ports targets through the same installed
    `litai-dev` build/test/package interface; retain native make as the first
    execution bridge and compare candidate action executors honestly.
  - [ ] Designate and exercise cut-over with equivalent output/acceptance,
    clean/warm/change timings and rollback to the preceding workspace selection.
  - [ ] Admit native source and ports units, dependencies and versioned packages into the installed Literate AI lifecycle.
  - [ ] Run clean, unchanged and changed-input build/test/package/ISO workflows with isolated outputs and demonstrate installation and recovery.
- **Evidence:**
  - [x] Native checkout identities and cleanliness, installed CLI and discoverable commands are verified on the operator workstation.
  - [ ] Complete Component ownership and dependency closure, exact provenance, correct incremental invalidation, actual tests and package outputs pass.
  - [ ] Measured ISO creation and actual installation/recovery evidence match the exact source and ports selections.
