# Native Component execution and build performance

- **Status:** active
- **Owning queue item:** [PERF-001](active-work.md#perf-001-execute-native-components-and-substantially-accelerate-iso-builds)
- **Completion / archival evidence:** pending complete graph, literal Component/pkg execution and measured ISO improvement

The current operator goal is to establish the source/ports component graph,
execute its units as literal Literate AI Components, and substantially improve
FreeBSD installer build and packaging time. Replacing make with Bazel, Buck2 or
another suitable system is authorized. A change of executor, graph inventory or
whole-system wrapper alone does not achieve this goal.
The operator has explicitly asked that executor choices be challenged. Bazel is
a candidate, while the required result is a faster common `litai-dev` interface
for both trees. The [parallel workspace and cut-over plan](native-workspace.md)
keeps that interface and upstream import process independent of executor choice.

## Establish the graph before qualifying execution

`scripts/inspect-freebsd-graph.py` inspects exact Git commit objects without
checking out or executing Makefiles. It assigns every tracked input to a
candidate owner, discovers native build-directory and port-origin candidates,
and retains lexical directory-reference declarations and their conditions.
Source/build/support candidates are not canonical Components or reviewed owners.

The first retained discovery evidence is
[verification/native-tree-discovery.json](https://github.com/jordanhubbard/daemonarchy/blob/feat/native-release-program/verification/native-tree-discovery.json):

| Pinned tree | Tracked inputs | Discovery result |
| --- | --- | --- |
| Source `92276fc76c65` | 114,642 | 4,620 build/support candidates, 10,823 declared directory references, 1,504 unresolved tokens and 72 native control statements |
| Ports `e1b7bf55b857` | 176,131 | 35,204 origin candidates plus 68 shared-support candidates; every origin still needs native variant/dependency resolution |

The source candidates include 4,238 native build directories, 307 driver-source
groups, 71 vendor-input groups and four shared groups. Directory discovery can
both group multiple actual units and include unsupported units. A complete input
inventory does not prove complete logical unit boundaries. No canonical
registration, full dependency graph, package or receipt pass is recorded.

A native amd64 query of `bin/ls/Makefile.depend` resolved `lib/${CSU_DIR}` to
`lib/csu/amd64` and included implicit `lib/libgcc_eh` and `lib/libgcc_s` inputs.
The original declaration file alone did not establish that selected graph.
Native context, option controls, implicit rules and bootstrap relationships must
therefore be captured before canonical locks or an alternative build executor
can rely on these edges.

## Native directory closure observation

`scripts/resolve-freebsd-dirdeps.py` evaluates reviewed dependency Makefiles on an
unprivileged native amd64 worker. It requests variables without a build target,
isolates temporary/object paths outside the source, requires a clean exact pin,
rejects external or redirected Makefile inputs, and bounds time, output and node
counts. Makefile evaluation can run parse-time shell commands, so it requires
explicit acknowledgement and a trusted source selection. It is not a sandbox.

The first native `bin/ls` observation resolves 19 directory/context nodes and 52
non-self edges with a dependency-first order and no unresolved declarations in
that selected directory closure. It includes host `bin/sh`, `usr.bin/yacc` and
`lib/ncurses/tinfo`, plus amd64 headers, startup objects and libraries. Forty
consulted Makefiles are retained as shared dependency inputs. Compact identities
and scope are in [the observation evidence](../../verification/native-dirdeps-observation.json).

This is a real native metadata result, not a complete compilation/action graph
or a Component receipt. The helper preserves missing declarations, unsupported
contexts, query failures and cycles; it never converts them into a successful
DAG. The full tree, kernel composition, generated-file/toolchain admission,
ports variants and canonical Component/package binding remain open. The first full directory sweep completed after the baseline stopped. Its 1,790
query records include 154 parser refusals and 19 unresolved declaration records.
Inspection found a parser defect: unqualified extra-directory targets can be
mistaken for dotted context names, and rejection loses otherwise valid edges.
The collector now preserves unqualified targets without splitting dots inside
paths and retains returned stdout/stderr plus command arguments. Eleven portable
checks pass. A native two-seed probe observes 20 nodes and 59 edges, retaining the
unqualified `gnu/lib/csu` reference from `bin/timeout`; it correctly exits nonzero
rather than calling that closure resolved. [Refinement evidence](../../verification/native-dirdeps-refinement.json)
binds the current producer and preserved query bytes. The corrected full sweep
retains 1,799 records: 1,766 observed, six query refusals and 27 missing or
unsupported records. Its 12,542 directory edges include 336 unqualified targets;
closure remains incomplete. [Full-sweep evidence](../../verification/native-dirdeps-full-sweep.json)
binds these counts to the producer and report hashes. Reconcile stale declarations and unsupported
variants against actual build actions before canonical target binding. Actual
compiler `.depend.*` files include compilation inputs absent from this directory
metadata, which alone is insufficient for admission.

## Performance baseline and candidate changes

The native GENERIC build at `92276fc76c65` uses 12 jobs and isolated staging. Its
controller records each completed phase's elapsed time and logs. World (4,195.318 s), kernel (210.840 s) and pkgbase (597.429 s) completed.
The first set-staging attempt failed after 220.836 s while installing Clang
headers. The exact captured install tool/flags subsequently copied all 219
headers successfully in an isolated directory; three system-install copies also
matched source bytes. The failure is retained and its cause remains unproven.
The exact-plan resume completed sets in 1,344.623 s, retaining all previous
phase logs. The controller byte-verified 533 artifacts and an independent audit
verified all eight MANIFEST set hashes. This recovered workflow is not a clean
successful performance baseline. The source archive audit found all 138 Git
symlinks dereferenced and build-user ownership throughout; archive fidelity and
complete optional-set inventory were corrected separately in source revision
`50594349f547`. Its isolated full source archive matches all 114,642 Git files,
including the 138 symlinks, with root ownership throughout; all 21 controller
checks pass on FreeBSD. [Build/audit evidence](../../verification/native-development-build.json)
retains both outcomes and the exact identities. Keep the
original checkout, outputs and negative audit frozen. ISO assembly and native
boot/install/update/rollback measurements remain incomplete.

| Candidate | Required evaluation |
| --- | --- |
| Native make directory dependencies/meta-mode | Resolve actual target inputs, determine tracing requirements and validate changed-header/tool/configuration invalidation; do not trust stale directory declarations. |
| Content-addressed Component/action caches | Include toolchain, target, options, declared and observed inputs; validate producer evidence and current acceptance before reuse. Measure hits and rebuild scope. |
| Bazel | Qualify the FreeBSD toolchain, bootstrap/loader/kernel rules, package products and any remote execution. Bazel documents its FreeBSD package as community-supported; this is not native qualification. |
| Buck2 | Qualify the required native platform, toolchain/rules, action graph, caching and pkg outputs before selecting it as executor. |
| Packaging and assembly | Measure staging, compression, repository/catalog creation, copies and ISO assembly independently; bound concurrency and memory and preserve package/file ownership. |

Sources: [FreeBSD directory-dependency mechanism](https://github.com/freebsd/freebsd-src/blob/bdaddb76ef1b9d5537f4a76cff01cdb4795804a4/share/mk/dirdeps.mk),
[FreeBSD meta-mode](https://github.com/freebsd/freebsd-src/blob/bdaddb76ef1b9d5537f4a76cff01cdb4795804a4/share/mk/meta.sys.mk),
[Bazel installation support](https://bazel.build/install),
and [Buck2 documentation](https://buck2.build/docs/getting_started/).

## Actual action tracing preparation

The [owned source controller](../source-builds.md#optional-actual-action-observations)
now has an optional filemon/meta-mode plan with immutable per-phase metadata
snapshots. The original seventeen controller checks pass locally and in CI.
The dedicated worker now passes normal alignment and the separately declared
filemon feature bootstrap/inspection, with owner-only device access and no boot
configuration change. All 26 current source-controller/bootstrap checks pass
on FreeBSD and the exact-revision controller CI passes. Full native traced-build
qualification remains pending. Do not silently fall back to command-only traces. Reconcile observed compilation/linking/generated inputs
with canonical Component ownership, variants and selected action/package locks.
The [native single-unit probe](../../verification/native-filemon-compile-probe.json)
now verifies actual header reads, unchanged reuse, changed-header invalidation
and preserved snapshots. The [524-package catalog audit](../../verification/native-pkgbase-catalog-audit.json)
resolves 1,082 runtime edges without cycles and binds every catalog package to
recorded artifact sizes. Neither observation supplies the missing complete
canonical compilation graph or per-unit provenance/pkg products.
The [new full tracing attempt](../../verification/native-traced-build-start.json)
is isolated from the earlier build and retains its own exact plan. Its first
world phase [failed in crunchgen](../../verification/native-traced-build-failure.json)
because meta verbosity contaminated structured query output. The corrected
quiet mode passed all 27 native controller checks. The [separate corrected attempt](../../verification/native-traced-build-quiet-result.json)
completed world, kernel and package commands, then failed while capturing a
39 MB set trace above the old per-file limit. The bounded streaming repair
passes 30 native checks and captures that same trace; an independent audit
verifies 537 artifacts and all eight installer-set hashes. The original failed
result remains unchanged. This recovered workflow is not a clean successful
performance baseline or full lifecycle acceptance. Source changes
between those revisions affect only release archive handling and controller/worker
preparation; native compiler and OS source regions are unchanged. Component/action
keys should bind consumed inputs, toolchain, flags and generated inputs, while
retaining repository-origin provenance separately. Do not invalidate every native
unit solely because an unrelated controller file changed. Measure this reuse;
source similarity alone does not prove equivalent generated inputs or artifacts.

The current set phase invokes `packagesystem` serially. Before parallelizing its
world/kernel/source branches, separate archive publication: the base target's
`mv dist/*.txz` overlaps the kernel target's output names. Bind compression thread
budgets as well as make jobs; native defaults can choose compressor threads
automatically. Qualify both archive contents and phase/total timings.


## Granular lifecycle execution constraints

The current framework command workspace executes the reviewed action order
sequentially and verifies complete original/snapshot manifests around each
command (`RetainedProjectExecutionWorkspace.execute_next` and `_require_current`).
That is useful custody for the existing bounded fixtures, but assigning the full
source tree to every compilation would multiply full-tree scans. The real source
input probe already takes 226.888 seconds for discovery/validation on this host;
this is input-custody evidence, not a native build-performance comparison.

Per-unit execution must select exact source/shared/generated/SDK input closures,
retain their complete ownership and dependency edges, and qualify bounded shared
custody and independent output publication before introducing parallel scheduling.
Require dependency-ready action dispatch and independent output publication to
qualify parallel Component execution.
The installed candidate now exposes retained execution; the selected native
source profile has produced compiled products but no complete accepted receipt.
Canonical unit/action/package integration remains open in issues #22 and #74. Preserve
those gates while connecting the actual native observations to existing owners.

The real 5,266-member source inventory also exposed evidence-construction cost
before and after compilation. Framework [#84](https://github.com/jordanhubbard/literate-ai/issues/84)
owns quadratic strict-schema object uniqueness checks. A portable comparison in
the same Python environment takes 20.251011 seconds before and 1.417537 seconds
after the proposed repair, producing the exact same 4,661,185-byte source BOM.
This is a measured SBOM step; full regression and native installed renewal are
pending. It is not a whole-build speedup or evidence for selecting Bazel.

Framework [#86](https://github.com/jordanhubbard/literate-ai/issues/86) separately
bounds retained input ancestor traversal while retaining byte hashes and current
filesystem-name checks. A warm portable comparison of the same 5,310-member
manifest takes 7.281015 seconds before and 1.938397 seconds after the proposed
repair; profiled open calls fall from 711,962 to 7,108. Native profiling then
identified additional Python 3.12 lexical-path overhead. Three FreeBSD samples
per implementation have medians of 19.794351 seconds before and 7.926676 seconds
after the final source-level correction, using the same 5,270-member native
manifest. The [performance record](../../verification/native-input-verification-performance.json)
binds adapter bytes, exact inventories, raw sample hashes and the passing full
framework regression (1,865 passed, 42 skipped). Installed-wheel and native
renewal remain required; these measurements do not establish whole-build
improvement or select an executor.

## Compare equivalent workloads

Retain exact source/ports, Component/Flavor locks, native toolchain and worker
resources, cache state, action counts, peak resources, phase/total times and
artifact identities for baseline and optimized runs. Include:

1. Clean build through packages and the same installer ISO contents.
2. Unchanged repeat with explicitly identified warm state.
3. Changed implementation, public header, options and toolchain cases that must
   invalidate the correct dependent closure.
4. Packaging-only and ISO assembly work, including compression and staging cost.
5. Independent VM installation, module/ABI, update and rollback correctness for
   the selected products; preserve existing hardware acceptance boundaries.

Substantial improvement must be demonstrated in these actual workflows, not
inferred from a tool's advertised speed or achieved by omitting source, tests,
packages, signatures or other required work. Source/build pkg products must bind
every compositional unit's inputs and typed dependencies; runtime installation
can select the composed system packages. [COMP-001](freebsd-components.md) and
the release Component contract retain those invariants.

Next action: complete native dependency/variant admission and canonical
Component/pkg binding, while completing the native baseline and archive-fidelity measurements. Choose
and implement the optimized executor/caching/packaging path using those results.
