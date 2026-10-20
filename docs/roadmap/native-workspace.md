# Parallel native workspace and executor selection

- **Status:** partial
- **Owning queue item:** [DEV-001](active-work.md#dev-001-provide-an-operator-ready-native-component-development-system)
- **Completion / archival evidence:** pending deployed source/ports execution, measured executor selection and cut-over

The operator requires a unified `litai-dev` build interface for source and ports,
substantially shorter elapsed builds, regular upstream imports, and a parallel
hierarchy before a designated cut-over. Unification takes priority over keeping
old build interfaces. Bazel was proposed as an implementation; its value must be
tested rather than inferred from its name or a wrapper around an opaque build.

## Parallel layout

Use `/usr/daemonarchy` on a native developer or build host. The deployment tool
also accepts another absolute root for isolated tests and worker installations.
Keep each checkout independent of the legacy `/usr/src` and `/usr/ports` Git
object stores so legacy garbage collection or branch movement cannot invalidate
the new workspace.

| Path below workspace root | Purpose |
| --- | --- |
| `control` | Reviewed Daemonarchy build definitions and portable workspace selection |
| `src` | Owned original-source fork, initially at an exact reviewed commit |
| `ports` | Owned ports fork, initially at an exact reviewed commit |
| `obj` | Target/configuration-specific incremental objects |
| `stage` | Isolated staged installations and image roots |
| `packages` | Versioned source/build/runtime pkg products and repositories |
| `cache` | Explicitly selected compiler/action/download caches |
| `evidence` | Logs, plans, timings, input/output identities and actual test results |

The workspace selection records exact repository revisions. Each checkout has
the owned fork as `origin` and the original FreeBSD repository as `upstream`.
Import upstream changes on reviewed integration branches; never automatically
merge, reset a developer's work, or change a running build's input selection.
Build definitions stay in the control repository or canonical owned metadata,
without scattering wrapper files through upstream source directories. Initial
deployment is a source-selection operation, not execution admission.

`native/workspace.json` selects the source and ports revisions. The deployment
helper adds the exact control commit from its own checkout, defaults to a
read-only plan, and never reuses an occupied root. Run it from the reviewed
control checkout on the native host:

```sh
python3.12 scripts/native-workspace.py plan --root /usr/daemonarchy
```

Provision the new root once with the developer as its owner, then deploy as that
unprivileged developer. On ZFS, provision a dedicated dataset mounted there so
build objects and caches are outside operating-system boot environments:

```sh
sudo install -d -o "$(id -un)" -m 0755 /usr/daemonarchy
python3.12 scripts/native-workspace.py deploy --root /usr/daemonarchy
python3.12 scripts/native-workspace.py inspect --root /usr/daemonarchy
```

The deploy operation fetches only the selected commit ancestry, without shared
Git object stores, and records the exact selection in `workspace.json`. A failed
deployment retains its partial checkouts and evidence; choose a fresh root after
inspection rather than removing or resetting retained state. Inspection refuses
revision, remote, worktree or output-root drift. It does not fetch, build, install
packages or issue a lifecycle receipt. The native worker prerequisite template
is `native/worker-template.json`; worker endpoints remain in private user
configuration.

The [deployment and probe checkpoint](../../verification/native-workspace.json)
records identical selection `sha256:170a3bceebfe42746a3750c01b98caf599cf5f6703edde26e3e964a0a4da46df`
on the operator workstation and native build host, with control commit
`327ab93eae21f36ed569974c224f55042bbd9b79`. Both use separate ZFS storage and
pass all eight real-Git workspace checks. The operator's installed development
CLI validates the relocated source project and three locks. Its test receipt is
missing. [Ports PR #7](https://github.com/jordanhubbard/daemonarchy-ports/pull/7)
now authors two original-source contracts, reviewed adoption, both FreeBSD/pkg
locks and the complete installed Standard binding. Installed-wheel authority
and lock validation pass; the receipt remains missing. This review has not
changed the deployed ports selection, which still needs that metadata.

## Executor decision

Bazel's cache operates on explicitly declared action inputs, commands,
environments and outputs. A whole-world `make` action remains one large
invalidation boundary; a `bazel run` shell wrapper adds no compilation-action
cache. Incremental correctness also requires exact compiler, sysroot, generated
header and configuration inputs. The existing directory-dependency observations
have unresolved contexts and are not ready to become a qualified Bazel graph.

The initial comparison uses existing native make targets, FreeBSD meta/filemon
observations, explicit compiler caching, and ports package reuse under one
Literate AI target and evidence model. Bazel remains a candidate for granular
actions once their closures are real. Buck2 would require the same graph and
toolchain work and has no demonstrated advantage here yet. Do not develop a
second private receipt format or label a raw executor result a passing LitAI
lifecycle.

The earlier recovered baseline spent 4,195.318 seconds in world and 1,344.623
seconds in successful set staging. It is diagnostic timing, not an equivalent
clean performance baseline. Measure staging, compression and ISO assembly
separately; an executor change cannot eliminate those costs by skipping them.
The current retained command owner also revalidates complete input inventories
around commands, so full-tree scanning must not be multiplied by every leaf
compilation. Bound custody to the actual selected closures and preserve its
invalidation guarantees.

The isolated native make probes now compile the original parser slice and
`truncate` against its private static PIE archive. The first probe selected the
ordinary static archive and failed PIE linking; that failure is retained rather
than disabling PIE. The corrected first parser/utility build took 2.090319
seconds and its unchanged repeat took 1.029382 seconds on the observed worker.
Source ATF suites, independent acceptance and per-unit source packages remain
pending. ELF inspection observes the parser symbols in the built program and
only libc as its dynamic dependency.

The `archivers/liblz4` probe verified the pinned distfile, built in 26.547052
seconds, ran the port's default upstream `check` target in 29.464662 seconds and
produced an ordinary native pkg in a further 1.432787 seconds. The upstream test
Makefile selects the newly built programs directory in its PATH. The unchanged
ports build phase took 0.177630 seconds, with no command output; completion-cookie
reuse is not a changed-input correctness proof. The same requirement therefore
applies to any make or Bazel bridge: source, patches, shared Mk files, options,
toolchain and build flags must invalidate stale work and test/package state.
These are bounded diagnostic timings, not a full release speedup, canonical
provenance receipt or completed executor comparison.

Sources: [Bazel remote action caching](https://bazel.build/remote/caching),
[Bazel hermeticity](https://bazel.build/basics/hermeticity),
[FreeBSD incremental build controls](https://github.com/freebsd/freebsd-src/blob/main/share/man/man7/build.7),
and [poudriere caching and parallelism](https://docs.freebsd.org/en/books/handbook/ports/#ports-poudriere).

## Migration and designated cut-over

1. Deploy independent pinned checkouts and immutable workspace selection. Keep
   the preceding selection and native outputs available.
2. Make one real source closure and one real port closure build, test and package
   through installed `litai-dev`, using native make as the first bridge. Retain
   actual bootstrap provenance, dependencies and limitations. A validation-only
   CLI does not satisfy this step.
3. Measure clean, unchanged, implementation-change, shared-header-change,
   options-change and toolchain-change runs. Compare artifact contents and actual
   test/acceptance outcomes. Record action/cache counts and total overhead.
4. Select and grow the measured executor to the required source/ports release
   closure. Retain the same canonical target and package authority during growth.
5. Designate cut-over `native-build-v1` for the first qualified 1.2 development
   release closure after all required build/test/package/ISO and disposable-VM
   install/update/rollback evidence passes. Record the exact control, source,
   ports, toolchain and executor selection and the measured improvement. Until
   those gates pass, the mode remains parallel development. No calendar date or
   release-publication claim follows from creating the directory hierarchy.
6. Exercise selection rollback before promoting the unified entrypoint. Retire
   old build entrypoints only through the recorded cut-over, with old published
   tags, outputs and recovery evidence preserved.
