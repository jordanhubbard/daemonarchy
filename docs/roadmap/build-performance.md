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

## Performance baseline and candidate changes

The native GENERIC build at `92276fc76c65` uses 12 jobs and isolated staging. Its
controller records each completed phase's elapsed time and logs. Full world,
kernel, package, set and ISO measurements are still incomplete. Keep its checkout
and outputs frozen until that job is terminal; never restart because a status
observation times out.

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
Component/pkg binding, while finishing the live baseline measurements. Choose
and implement the optimized executor/caching/packaging path using those results.
