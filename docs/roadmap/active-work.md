# Active work

[PROJECT.md](https://github.com/jordanhubbard/daemonarchy/blob/main/PROJECT.md) owns product goals and completeness.
Checkboxes below are execution status, not substitutes for test receipts.

## Open pull-request landing queue

No open issues or reviews were found in the initial GitHub survey. Existing
release/test worktrees are retained; adoption does not authorize their deletion.

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
- **Conclusion:** Do not enable framework execution or publication until exact mixed source/assets, worker/toolchain, privileged cleanup, artifact custody and current receipt paths are demonstrated; the installed retained execution handler currently refuses qualification.
- **Depends on:** ADOPT-001
- **Implementation:**
  - [x] Audit the retained execution handler on current framework main and reconcile [framework issue #22](https://github.com/jordanhubbard/literate-ai/issues/22): the issue was reopened because authorized execution still unconditionally refuses. Actual execution qualification remains open below.
  - [ ] Bind the actual FreeBSD target, action inventory, external inputs, privileged cleanup and protected signer.
  - [ ] Qualify current native receipts, artifact custody and release enforcement.

Next action: demonstrate a supported installed retained-project execution path on a bounded mixed-source/binary fixture before connecting Daemonarchy production workers. Do not bypass `retained_project.execution_not_qualified`.
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
- **Depends on:** ADOPT-002,UI-001,PKG-001,GUI-001,DEBUG-001,HW-001
- **Implementation:**
  - [x] Inventory current roadmap and queue obligations in [the 1.2.0 completion ledger](release-1.2.0.md), including inherited Bluetooth, enterprise Wi-Fi, dual-boot, bhyve and physical trust/graphics gaps.
  - [ ] Contribute and qualify upstream FreeBSD platform and retained execution support; bind private native workers and VM supervision; complete backlog implementations and acceptance; run the exact final release through Literate AI and verify publication.
- **Evidence:**
  - [ ] Every inherited backlog obligation has direct completion evidence; native and virtual/physical acceptance match exact final artifacts; full LitAI verification and release gates pass; published new release and immutable assets are verified.
