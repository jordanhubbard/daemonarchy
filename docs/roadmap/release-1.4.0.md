# 1.4.0: Literate AI across the Daemonarchy release graph

- **Status:** active
- **Release scope:** 1.4.0; no 1.4 build or release qualification is claimed.
- **Completion / archival evidence:** pending cross-repository locks, native worker receipts, equivalent timing comparisons, exact ISO/feed qualification, and published release verification.
- **Tracking:** [product issue #39](https://github.com/jordanhubbard/daemonarchy/issues/39), [1.4.0 milestone](https://github.com/jordanhubbard/daemonarchy/milestone/3).
- **Owning queue item:** [PERF-002](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140).
- **Existing foundations:** [retained native execution](active-work.md#adopt-002-qualify-retained-native-execution-and-release-enforcement), [complete source and ports ownership](freebsd-components.md), [native workspace](native-workspace.md), and [build-performance work](build-performance.md).
- **Release boundary:** this is 1.4 work. The pinned 1.3.1 package, ISO and signing path remains the current release path; the operator confirmed MacBook pre-production checks and waived an additional final-ISO physical rerun. [1.3.2 early-kernel MSI debugging](release-1.3.2.md) has its own acceptance.

## Intended operating model

Literate AI owns one exact, cross-repository release plan and schedules its
dependency-ready actions on parallel native workers. Keep source authority in
each owned fork and preserve the FreeBSD package, installer and signing
contracts. Select the
executor by measured correctness and elapsed time: Bazel, remote build caches,
remote execution, other incremental tools, `make` and Poudriere are candidates.
`make` and Poudriere are not required architecture. Every action's inputs,
outputs, variants, dependencies and side effects must be visible to the LitAI
plan. Calling a full legacy build or release script as one opaque action is a
migration bridge; it cannot provide per-unit invalidation or worker scheduling.

The selected release workspace includes `daemonarchy`, `daemonarchy-src`,
`daemonarchy-ports`, `daemonarchy-desktop`, and `omarchy-freebsd`. Admit the owned
`omarchy` fork and any later release input only when the exact release selection
uses it. Record each commit, upstream ancestry, tree identity and integration
contract without collapsing independently maintained repositories into one
checkout. Preserve reviewable upstream refreshes and pin one selection for each
qualification run.

Both FreeBSD source and ports are now owned forks. The 1.4.0 implementation
may change any part of those forks needed to make source units, ports,
packages, base ABI contracts and release inputs accurately incremental and
distributable. Put dependency declarations, package metadata, build hooks and
cache integration in the fork that owns them where that yields an authoritative
graph. Preserve FreeBSD's functional ABI, package format and installation
contracts, native qualification and reviewable FreeBSD CURRENT refreshes; the
existing make/Poudriere execution model is not a constraint. Land the resulting
source and ports changes through their own reviewed main branches before the
1.4 release selection is locked.

## Cross-release artifact reuse and distributed execution

Before scheduling any release build, produce an exhaustive package inventory
against the last published release. Include every old and selected package,
including added and removed origins, build dependencies and package-only
changes. For each row, record exact source and port-tree identities, package
version, options, flavors, generated inputs, toolchain and base ABI, build and
runtime dependency identities, old artifact digest, selected artifact digest
when present, and the proposed reuse or rebuild reason. Fail the release plan
if any package lacks a decision or if an unchanged artifact is rebuilt without
a recorded invalidation or failed native qualification. Publish aggregate
counts, cache bytes and time saved, plus the per-package decision ledger with
the release evidence. The [1.1.1-to-1.3.1 application-feed inventory](../evidence/release-1.3.1-package-reuse-inventory.md)
is the baseline: it covers 510 old packages, including 320 with unchanged port
and dependency metadata and 162 requiring runtime ABI review. Its LibreOffice
row changed version and port inputs, so that package required a new build.

Always reuse a verified build output, binary, package or release input across
versions when its complete action identity is unchanged. A release number or
an unrelated repository commit must not force recompilation. Cache keys must
cover the exact source subdirectory and transitive shared inputs; port
Makefiles, distinfo, patches, plist, options, flavors and metadata; generated
inputs; compiler, toolchain and sysroot; the relevant FreeBSD base ABI;
build-time dependency contents and generated interfaces; runtime dependency
ABI contracts and version constraints; command, environment and output format.
Record the exact base OSVERSION and dependency versions as provenance. Recheck
retained bytes, provenance and signatures where applicable before a cache hit.
Re-sign or repackage only a changed envelope when the underlying payload
remains valid.

If the graph lacks an input or dependency edge needed for a sound key, repair
that graph gap before allowing reuse. Until it is repaired, rebuild the
affected unit and retain the reason. The 1.1.1 and 1.3.1 Chromium and CEF port
subtrees are identical, while their selected base OSVERSION and seven package
dependency versions differ. This is a regression case for separating actual
build inputs from runtime-only dependencies, rather than either rebuilding on
every version change or admitting a cache hit based on port-tree equality alone.
For a changed base or runtime package, allow reuse of a userland payload only
after proving the selected base and dependency ABI contracts, package version
constraints, installation scripts, native execution and relevant application
behavior still hold. Record the new qualification against the retained payload
digest and repackage metadata if required. Rebuild kernel modules, changed
headers or generated interfaces, static links, incompatible ABIs, and any
case without sufficient evidence. A changed OSVERSION by itself must trigger
requalification, not automatically a full userland rebuild.

The release pipeline must decide reuse before scheduling compilation, fetch
retained payloads from the shared cache, and record either the native
requalification receipt or a specific failed condition. A compatible base or
runtime-library version change must not queue Chromium or CEF for compilation
solely because that version changed. If compatibility tests fail, rebuild and
retain the failure. Duplicate full builds on other machines do not count as a
distributed speedup.

Treat ports and packages as graph artifacts. Evaluate Bazel incremental builds,
shared remote cache servers and other proven incremental or remote-execution
systems against equivalent native output and end-to-end time. Dispatch ready
build, test and package actions across multiple physical machines using their
CPU, memory, disk, network and target capabilities. Share verified immutable
artifacts, coalesce duplicate work for one action key, and recover from worker
loss without racing package databases or protected signing state.

Use a cache on the release engineer's network for pre-release build and
installer iterations. The iterative bhyve harness and installer test
configuration should accept an explicit package and asset cache source, with
each entry bound to the selected signed catalogue, package name, version, ABI
and SHA-256 digest. Reject mismatches, fetch verified misses, and record hits,
misses, bytes saved and elapsed time. Exercise a corrupt cache entry in a
fail-closed test. Final release-candidate QA must disable the local cache
override and fetch the actual public binary, package and feed URLs, then
verify their signatures and payloads during a fresh install and installed
boot. Cache savings from earlier iterations cannot stand in for that public
distribution check.

## Build, test, package and release graph

1. **Admit inputs and dependencies.** Assign source build units, ports origins,
   desktop and compatibility outputs, shared Makefiles, public headers,
   generated inputs, bootstrap tools, compiler/sysroot, target/options/flavors,
   firmware and package catalogues to canonical owners. Resolve conditional
   source and package edges. Reject missing or ambiguous ownership, incomplete
   closures and changed inputs instead of treating them as cache hits.
2. **Dispatch native work.** Use LitAI's worker model to run ready actions across
   multiple isolated physical machines, with explicit CPU, memory, disk and network
   budgets. Keep a stable action identity over command, toolchain, environment,
   selected inputs and expected outputs. Parallelize independent compilation,
   tests, downloads, package preparation and image inputs. Use shared verified
   caches and avoid duplicate work for the same action key. Serialize shared
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
- [ ] Before queueing builds, compare every package in the prior public feed and
  selected release closure, including additions and removals. Produce the
  per-package reuse/rebuild ledger and account for every build, cache hit,
  invalidation, failed qualification, package byte and elapsed time. Reject an
  unexplained rebuild of an unchanged package. Include the 1.3.1 Chromium,
  CEF, OBS and changed LibreOffice cases in the regression fixture.
- [ ] Qualify retained native profiles and full dependency closures for every
  selected repository. Demonstrate that changed implementation, header,
  generated input, port option/flavor, compiler, sysroot and upstream commit
  invalidate the correct dependent actions; unchanged cross-release actions
  reuse their verified binary, package and release-input outputs without
  recompilation. Missing graph edges refuse cache admission until repaired.
- [ ] Implement required build, ports, package and ABI metadata changes in the
  owned FreeBSD source and ports forks, with native tests and reviewed merges
  to each fork's main. Demonstrate that the graph is authoritative at its
  actual producers rather than inferred only by an outer release wrapper.
- [ ] Split build-time inputs from runtime-only ABI/version constraints. Prove
  unchanged userland payload reuse across compatible OSVERSION and runtime
  dependency changes using native installation, package scripts, executable
  and application tests, exact payload digests and fresh provenance. Rebuild
  for changed headers, static dependencies, incompatible ABIs or failed tests.
  Use the 1.1.1-to-1.3.1 Chromium/CEF case as a positive or negative regression
  test determined by evidence, not an assumed hit.
- [ ] Run independent ready actions concurrently on at least two physical
  machines with a shared verified cache, bounded resources, retained
  partial-failure evidence and reproducible retry. Coalesce duplicate keys
  and show that package database and signing actions cannot race.
- [ ] Demonstrate verified local-cache hits in pre-release installer and build
  iterations, measured time and network savings, verified miss fallback, and
  rejection of a corrupt entry. Run final ISO QA with the cache override off
  against the public signed feeds and public package assets.
- [ ] Build and test the same selected source/ports/desktop/compatibility
  products with native tools under LitAI custody, then produce versioned pkg
  feeds and an installer ISO whose contents and signatures pass native checks.
- [ ] Measure equivalent clean, unchanged, changed-input, package-only and
  ISO-only runs against the baseline. Include single-machine and distributed
  runs, remote cache hit rates, prevented rebuilds, and action-level invalidation
  reasons. Set numeric speed targets from that baseline before implementation
  and demonstrate material end-to-end savings without skipping required
  products, tests or acceptance.
- [ ] Demonstrate the 1.3.1 regression is eliminated: an unchanged release
  rerun compiles no packages; a compatible base/runtime dependency update
  requalifies and reuses the retained Chromium/CEF payloads without compiling
  either browser; a changed browser build input or incompatible ABI rebuilds
  only the affected closure. Report wall-clock time, cache bytes reused and
  every admission or rebuild reason. A 1.4 release fails this item if it still
  repeats the 1.3.1 browser rebuild for a compatible version-only change.
  Measure the full build/package/sign/ISO critical path with the same required
  gates and worker pool: the compatible-update run must finish at least four
  times faster than an equivalent clean rebuild, and the unchanged rerun at
  least ten times faster. Record 1.1.1 and 1.3.1 observed timings separately
  from these normalized comparisons so earlier retries or hardware waivers
  cannot inflate a claimed speedup.
- [ ] Install the exact image in a fresh VM, exercise upgrade and rollback,
  complete the release's physical hardware matrix, publish through the
  LitAI-controlled release plan and independently verify the tag and assets.

Completion requires working cross-release reuse, a distributed multi-repository
flow and retained receipts, not a renamed wrapper around the current serial
build. Keep `make` or Poudriere only where they meet the same native correctness
and elapsed-time targets as the selected incremental executor.
