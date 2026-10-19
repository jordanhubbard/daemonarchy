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

Initial controller implementation: [source PR #4](https://github.com/jordanhubbard/daemonarchy-src/pull/4),
commit `92276fc76c65f3ca31552d2e1833a6063361ff64`, based on upstream
`bdaddb76ef1b9d5537f4a76cff01cdb4795804a4`. Eleven controller tests passed locally
and in [GitHub CI](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/39206065364).
The same eleven tests passed on the native FreeBSD worker in 14.000 seconds.
The first 12-job GENERIC baseline build started at this exact source commit,
with plan identity
`2e783baa18b29ca2e62ce122a1ef4f94748a124bc3af797561d5120529622b95`.
Compilation, packages, installer sets and VM/hardware acceptance remain pending;
starting `buildworld` does not qualify those results.
