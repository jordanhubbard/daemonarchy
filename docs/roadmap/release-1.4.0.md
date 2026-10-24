# 1.4.0: Literate AI across the Daemonarchy release graph

- **Status:** active
- **Release scope:** 1.4.0; no 1.4 build or release qualification is claimed.
- **Completion / archival evidence:** pending cross-repository locks, native worker receipts, equivalent timing comparisons, exact ISO/feed qualification, and published release verification.
- **Tracking:** [product issue #39](https://github.com/jordanhubbard/daemonarchy/issues/39), [1.4.0 milestone](https://github.com/jordanhubbard/daemonarchy/milestone/3).
- **Owning queue item:** [PERF-002](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140).
- **Existing foundations:** [retained native execution](active-work.md#adopt-002-qualify-retained-native-execution-and-release-enforcement), [complete source and ports ownership](freebsd-components.md), [native workspace](native-workspace.md), and [build-performance work](build-performance.md).
- **Release boundary:** this is 1.4 work. The pinned 1.3.1 package, ISO, signing, and MacBook acceptance path remains the current release path; [1.3.2 early-kernel MSI debugging](release-1.3.2.md) has its own acceptance.

## Intended operating model

Literate AI owns one exact, cross-repository release plan and schedules its
dependency-ready actions on parallel native workers. Existing implementation
and tool authority stays with each owned fork and its native build system. FreeBSD
`make`, Poudriere, `pkg`, ISO assembly, signing tools, and a measured Bazel or
other executor can all run as action executors. Their inputs, outputs, variants,
dependencies and side effects must be visible to the LitAI plan. Calling a full
legacy build or release script as one opaque action is a migration bridge; it
cannot provide per-unit invalidation or worker scheduling.

The selected release workspace includes `daemonarchy`, `daemonarchy-src`,
`daemonarchy-ports`, `daemonarchy-desktop`, and `omarchy-freebsd`. Admit the owned
`omarchy` fork and any later release input only when the exact release selection
uses it. Record each commit, upstream ancestry, tree identity and integration
contract without collapsing independently maintained repositories into one
checkout. Preserve reviewable upstream refreshes and pin one selection for each
qualification run.

## Build, test, package and release graph

1. **Admit inputs and dependencies.** Assign source build units, ports origins,
   desktop and compatibility outputs, shared Makefiles, public headers,
   generated inputs, bootstrap tools, compiler/sysroot, target/options/flavors,
   firmware and package catalogues to canonical owners. Resolve conditional
   source and package edges. Reject missing or ambiguous ownership, incomplete
   closures and changed inputs instead of treating them as cache hits.
2. **Dispatch native work.** Use LitAI's worker model to run ready actions across
   isolated FreeBSD build workers, with explicit CPU, memory, disk and network
   budgets. Keep a stable action identity over command, toolchain, environment,
   selected inputs and expected outputs. Parallelize independent compilation,
   tests, downloads, package preparation and image inputs. Serialize shared
   package-database writes, protected signing operations and any other action
   whose side effects cannot safely overlap.
3. **Retain products and evidence.** Capture verified source/build/runtime pkg
   outputs, versioned repositories, source and dependency SBOMs, native test
   reports, independent acceptance, logs, resource use and failure/retry state.
   Package and feed metadata must retain ABI, origin, flavor, options, exact
   dependencies and archive identities. A successful command exit alone does
   not qualify the selected product or release.
4. **Assemble and qualify one release.** Derive the signed feeds, boot bundle,
   installer ISO, checksums, documentation and GitHub asset selection from the
   same locked plan. Bind native tests, fresh VM installation, upgrade/rollback
   and scoped physical hardware checks to those exact artifact bytes. Keep the
   existing signing keys and private worker details outside committed metadata.

## Delivery sequence and acceptance

- [ ] Inventory all selected fork revisions, tools, workers, actions and outputs;
  record complete-tree source/ports ownership and the 1.3.1 clean-build timing
  baseline, including world, kernel, package fetch/build, signing and ISO stages.
- [ ] Qualify retained native profiles and full dependency closures for every
  selected repository. Demonstrate that changed implementation, header,
  generated input, port option/flavor, compiler, sysroot and upstream commit
  invalidate the correct dependent actions; an unchanged run reuses only
  verified outputs.
- [ ] Run independent ready actions concurrently on at least two isolated
  admitted worker slots, with bounded resources, retained partial-failure
  evidence and reproducible retry. Show that package database and signing
  actions cannot race.
- [ ] Build and test the same selected source/ports/desktop/compatibility
  products with native tools under LitAI custody, then produce versioned pkg
  feeds and an installer ISO whose contents and signatures pass native checks.
- [ ] Measure equivalent clean, unchanged, changed-input, package-only and
  ISO-only runs against the baseline. Set numeric speed targets from that
  baseline before implementation and demonstrate material end-to-end savings
  without skipping required products, tests or acceptance.
- [ ] Install the exact image in a fresh VM, exercise upgrade and rollback,
  complete the release's physical hardware matrix, publish through the
  LitAI-controlled release plan and independently verify the tag and assets.

Completion requires the working multi-repository flow and its retained receipts,
not a renamed wrapper around the current serial build. The executor can remain
`make` where it performs well; changing to Bazel is justified by equivalent
native correctness and elapsed-time evidence.
