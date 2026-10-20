# Owned FreeBSD source builds

Daemonarchy's FreeBSD-CURRENT fork is
[jordanhubbard/daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src).
Its `main` tracks the selected upstream baseline. Changes and build tooling live
on review branches; generally useful kernel fixes should also be contributed to
FreeBSD. The local development checkout is `~/Src/daemonarchy-src`.

## Operator development preview on the HP

The HP at `daemon.local` has the reviewed source fork at `/usr/src` (commit
`978fed917ba2b391c3eace661c21a7a65549cb23`) and the owned ports fork at
`/usr/ports`. Its isolated `/home/jkh/bin/litai-dev` uses the wheel from
framework revision `cffef3238ba48f2c0876270aa4a1aeacce4c86e1`. The
source project's reviewed Standard binding pins that wheel's installed
distribution identity. The normal `/usr/local/bin/litai` remains the stable
1.1.1 installation.

From an HP shell, run `cd /usr/src && litai-dev project validate .` to inspect
the current project. `litai-dev verify .` currently reports passing authority
and three current locks, then exits unsuccessfully because
`verification/current.json` has not been earned. That failure is expected; it
must not be replaced with an invented receipt. The current three contracts are
metadata and target locks. Use the [native composition plan](roadmap/freebsd-components.md)
to admit the compiler/test closure and executable profile before authorizing a
retained build. The isolated CLI dependencies were copied from the stable
installation, so their independent native package qualification also remains
open.

The initial [versioned build runbook](https://github.com/jordanhubbard/daemonarchy-src/blob/92276fc76c65f3ca31552d2e1833a6063361ff64/tools/daemonarchy/README.md)
owns the native commands and resource requirements. Its controller plans and
executes an exact clean source commit with isolated object, staging, repository
and log directories. GENERIC and diagnostic kernel profiles have distinct package
versions and build directories. The diagnostic profile adds optional SYSINIT
tracing; targeted device-probe instrumentation is separate work.

The build produces both pkgbase packages (world, kernel and source) and the
`base.txz`, `kernel.txz`, `lib32.txz`, `src.txz` installer sets. A JSON plan binds
the source/tree, upstream base, configuration hashes and commands; the result
records worker tools, phase outcomes, logs and artifact checksums. Verification
checks the retained bytes. These unsigned development records are not Literate
AI receipts, signatures, native runtime acceptance or reproducible-build proof.

Use the dedicated native build worker's existing single slot. The workflow runs
unprivileged and never installs onto the worker, changes its package feed,
reboots, accesses signing keys or publishes a release. Keep the protected signer
and physical acceptance targets separate. Each long phase has a deadline and
retains failure logs; resume requires the same frozen source and build plan.

The installer still consumes the currently selected verified snapshot sets.
Before replacing them, qualify the owned build's VM boot and installation,
matching poudriere jail and external modules, update/rollback, boot and feed
signatures, physical hardware, and exact artifact admission. MSI or MacBook
compilation is not evidence that either machine boots successfully.

SRC-001 tracks this setup in the [active queue](roadmap/active-work.md).
ADOPT-002 and RELEASE-001 retain framework execution and release enforcement;
running this native controller directly does not close those gates.
COMP-001 additionally requires [complete source and ports Component coverage](roadmap/freebsd-components.md).
The aggregate world/kernel build does not account for every native unit or
ports origin as a canonical Component.

Initial controller implementation: [source PR #4](https://github.com/jordanhubbard/daemonarchy-src/pull/4),
commit `92276fc76c65f3ca31552d2e1833a6063361ff64`, based on upstream
`bdaddb76ef1b9d5537f4a76cff01cdb4795804a4`. Eleven controller tests passed locally
and in [GitHub CI](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/39206065364).
The same eleven tests passed on the native FreeBSD worker in 14.000 seconds.
The first 12-job GENERIC baseline build started at this exact source commit,
with plan identity
`2e783baa18b29ca2e62ce122a1ef4f94748a124bc3af797561d5120529622b95`.
World (4,195.318 s), kernel (210.840 s) and pkgbase (597.429 s) completed.
The first installer-set staging attempt failed during Clang header installation;
an isolated replay of the captured 219-header command passed. An exact-plan
resume retained that failure and completed sets in 1,344.623 s. The frozen
controller verified 533 recorded artifacts (1,503,160,792 bytes), and an independent
audit verified all eight MANIFEST-listed set hashes. This recovered workflow is
not a clean successful performance baseline. No ISO, VM boot, install/update or
rollback acceptance is implied.

The source archive audit compared every file against the pinned Git tree:
114,642 expected paths were present, with no extra files, but all 138 Git
symlinks had been dereferenced and all members retained build-user ownership.
That archive is not a faithful retained-source input. A separate source-fork
[fix](https://github.com/jordanhubbard/daemonarchy-src/commit/50594349f547f650bbcf0e2e945676c91c20be4b)
preserves internal symlinks and assigns root ownership. An isolated full source
archive using that release Makefile matches all 114,642 Git files in content
and mode, preserves all 138 symlinks and gives every member root ownership.
Both source and ports archive targets pass the native symlink/external-link and
ownership fixture. The original build and negative audit remain unchanged.
The controller now binds every MANIFEST-listed optional debug/test set into
its artifact inventory; all 21 checks pass on FreeBSD (30.097 s), with one native
archive check skipped on macOS. [Compact build/audit evidence](../verification/native-development-build.json)
retains phase failures, identities and qualification limits.

## Optional actual-action observations

Source revision `a2f44e0b96c06e3ee69a9f153e6854d73436a99c` adds
[`--trace-mode filemon`](https://github.com/jordanhubbard/daemonarchy-src/blob/a2f44e0b96c06e3ee69a9f153e6854d73436a99c/tools/daemonarchy/README.md#observe-native-actions).
It binds make metadata and filemon settings to the plan, disables source
Makefile.depend updates, uses a distinct development package version and retains
immutable metadata blobs after successful phases. Resume and byte verification
check those retained snapshots; missing filemon compilation records refuse.
Tracing/capture cost is included in phase timing. Require 100 GiB free.

The initial seventeen controller checks pass locally and in source-controller
CI. Source revision `76a523613db4` adds an explicit, separate worker-feature
bootstrap; all 26 current checks pass on FreeBSD (26.107 s), with one native
archive check skipped on macOS. The [exact-revision controller CI](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/39225164970)
also passes; its archive check requires FreeBSD. Standard worker alignment passes with a 100 GiB
free-space requirement. The declared bootstrap loaded the installed filemon
module on the dedicated worker and granted device access only to its build
account (mode 0600). A subsequent unprivileged inspection reports ready. Boot
configuration is unchanged. The build controller itself never loads modules or
changes permissions. Full traced-build qualification remains pending. The
completed development build remains frozen at `92276fc76c65`, without tracing.

A [native compile probe](../verification/native-filemon-compile-probe.json)
records the actual header read, reuses the unchanged object, rebuilds after a
header edit and verifies both immutable trace snapshots. This is one C
translation unit, not a full world/kernel traced build or Component receipt.

A separate 12-job GENERIC traced build has started from source
`76a523613db4d25d3c1702f32b21d1f07d11ee1e` with plan
`b564633fec495be21cc2ce6b550689560a25450c601888398ab0a252fdc37b34`.
The [start record](../verification/native-traced-build-start.json) binds its exact
source tree, configuration and development package version. It uses a clean
separate checkout/output; the prior build remains frozen. A started build and
live metadata are not successful immutable phase snapshots or acceptance.

That [first traced attempt failed](../verification/native-traced-build-failure.json)
after 4,218.257 seconds in `buildworld`: meta-mode's `verbose` output contaminated
crunchgen's structured `OBJS=` query. The first error was rescue generation; later
directory stops were cancellation cascades. Source revision `7d93dff0e80a` removes
that verbosity. All 27 controller/bootstrap checks pass on FreeBSD, including a
query regression with a verbose control; macOS skips the two native cases.
A [new isolated quiet-mode attempt](../verification/native-traced-build-quiet-start.json)
has started from `7d93dff0e80a`. The failed checkout, plan, log and
outputs remain unchanged; no successful full tracing result is implied.



The [pkgbase catalog audit](../verification/native-pkgbase-catalog-audit.json)
binds all 524 catalog packages to recorded artifact sizes and resolves their
1,082 runtime dependency edges to exact names, origins and versions without
cycles. All packages target `FreeBSD:16:amd64`. Their native annotations contain
FreeBSD version/set data; complete per-unit source/build provenance and a
compilation dependency graph remain unqualified. Runtime package closure is a
separate observation from the complete source/ports Component model.

Actual observations will inform [canonical Component and build-performance
work](roadmap/build-performance.md). They do not automatically produce canonical
Component contracts, package provenance, acceptance or an ISO speedup.

## Complete source input custody checkpoint

Framework revision `545c4ae6` adds explicit internal POSIX symlink custody while
preserving default refusal, legacy identities and the public execution guard.
Its [actual source corpus probe](../verification/native-source-input-custody.json)
validates 114,644 files, 9,856 directories and all 138 Git link targets at source
`76a523613db4`. All 83 focused checks and the full 1,696-test local framework
suite pass (37 skips). The probe runs on macOS and checks input discovery and
validation; small fixtures check snapshot copying. A complete native source
snapshot, canonical unit/action registration, per-unit packages and native
lifecycle execution remain unqualified. Exact framework CI and installed/native
renewal retain their own gates.

## Operator development workstation

DEV-001 extends this program to an editable native workstation. The conventional
`/usr/src` checkout selects the `daemonarchy-src` development branch; `/usr/ports`
selects the owned `daemonarchy-ports` fork, initially based on the published
`daemonarchy-1.1.1` ports selection. Both have explicit upstream remotes.
The ports fork was renamed from `freebsd-ports`, retaining its branches and history.
The development ports branch is `feat/litai-native-components`.

Product authority lives at `~/src/daemonarchy`; framework development lives at
`~/src/literate-ai`. Native object, staging, package, trace and ISO outputs belong
outside both source trees. Record exact revisions, options, toolchains and artifact
identities for every result. The installed 1.1.1 base, kernel, drivers and package
feed remain the running system until a separately verified installation is chosen.

Provisioning these checkouts does not implement the complete Component lifecycle.
DEV-001 remains open until the installed Literate AI entry points actually manage
source and ports build/test/package/ISO creation and installation, including
unchanged and changed-input invalidation and recoverable installation evidence.
Do not present direct aggregate make invocations as completed Component execution.

The first [native provisioning checkpoint](../verification/operator-development.json)
records clean source/ports selections, a verified offline framework dependency
closure, successful installed CLI/project validation and 27 passing native
controller tests. Use the development CLI from a normal shell:

```sh
cd ~/src/daemonarchy
litai --version
litai project validate .
litai verify
```

`litai verify` currently reports the missing native lifecycle receipt. This is an
open implementation gate, not a qualified build or a reason to fabricate a receipt.
The native aggregate controller can create a pinned plan from `/usr/src`, but its
8 GiB available-memory minimum exceeds this workstation's currently available
memory. Keep expensive full-world qualification on the dedicated worker.
The framework checkout is editable; the installed CLI is a separately pinned
non-editable development wheel. Changes there require a new verified installation.
`litai doctor` also reports an unauthenticated coding CLI and missing Git LFS; no
agent credentials were copied during this provisioning.

## Quiet traced-build outcome and streaming correction

The quiet attempt at `7d93dff0e80a` passed world, kernel, pkgbase and release-object
phases and reached the end of release-set generation. Its evidence capture then
refused the 39,097,413-byte `src.txz.meta` record under the old 16 MiB limit, so
the overall controller result remains failed. The original result and phase logs
remain unchanged. An independent byte audit verifies 537 artifacts totaling
1,833,076,586 bytes and all eight MANIFEST-listed sets. This does not convert the
failed run into successful native lifecycle evidence.

Source revision `f5e2473a68db` streams trace records with bounded in-memory
spooling, a 64 MiB per-file limit and unchanged 16 GiB/500,000-entry aggregate
bounds. Thirty controller/bootstrap checks pass on the native workstation,
including a record exceeding the old limit, split filemon markers and changing-file
refusal. A separate native probe preserves and hash-verifies the complete actual
archive trace in immutable custody. The workstation's `/usr/src` now contains
that fix. [Compact evidence](../verification/native-traced-build-quiet-result.json)
retains exact revisions, failure, hashes and qualification limits.

## Retained executable acceptance checkpoint

Framework checkpoint `567e0f8a4092` adds an opt-in withheld verifier policy for
sealed retained build exports. All 69 selected retained-project checks pass on
actual FreeBSD, including executable cases with exact binary input/output and
exit-status comparison, stale-policy/lock rejection, native dependency drift
and failed-result custody. Fourteen focused controller checks also pass.
[The checkpoint](../verification/native-retained-acceptance.json) records the
revision and log hashes. Its complete framework regression remains running
before publication of this local commit. The installed CLI remains at `545c4ae6`.

This does not enable public retained execution: SDK/source and resolved BOM
admission, retained-origin receipts, package/release consumers and installed
qualification are still required. Preflight also found that the installed-wheel
smoke harness expects a Linux Flavor on FreeBSD even though production
initialization has an explicit FreeBSD selector. Correct that harness under
framework issue #67 and qualify actual wheel bytes; a source test pass cannot
substitute for that installation gate.
