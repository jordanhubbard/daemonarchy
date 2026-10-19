# Native Component execution and build performance

- **Status:** active
- **Owning queue item:** [PERF-001](active-work.md#perf-001-execute-native-components-and-substantially-accelerate-iso-builds)
- **Completion / archival evidence:** pending complete graph, literal Component/pkg execution and measured ISO improvement

The current operator goal is to establish the source/ports component graph,
execute its units as literal Literate AI Components, and substantially improve
FreeBSD installer build and packaging time. Replacing make with Bazel, Buck2 or
another suitable system is authorized. A change of executor, graph inventory or
whole-system wrapper alone does not achieve this goal.

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
on FreeBSD; exact-revision CI remains pending. Full native traced-build
qualification remains pending. Do not silently fall back to command-only traces. Reconcile observed compilation/linking/generated inputs
with canonical Component ownership, variants and selected action/package locks.

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
