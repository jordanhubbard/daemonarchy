# Owned FreeBSD source builds

Daemonarchy's FreeBSD-CURRENT fork is
[jordanhubbard/daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src).
Its `main` tracks the selected upstream baseline. Changes and build tooling live
on review branches; generally useful kernel fixes should also be contributed to
FreeBSD. The local development checkout is `~/Src/daemonarchy-src`.

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
archive check skipped on macOS. Standard worker alignment passes with a 100 GiB
free-space requirement. The declared bootstrap loaded the installed filemon
module on the dedicated worker and granted device access only to its build
account (mode 0600). A subsequent unprivileged inspection reports ready. Boot
configuration is unchanged. The build controller itself never loads modules or
changes permissions. Full traced-build qualification remains pending. The
completed development build remains frozen at `92276fc76c65`, without tracing.

Actual observations will inform [canonical Component and build-performance
work](roadmap/build-performance.md). They do not automatically produce canonical
Component contracts, package provenance, acceptance or an ISO speedup.
