# 1.6 upstream synchronization and PMC review, November 23

- **Status:** active
- **Owning queue item:** [SYNC-001](active-work.md#sync-001-synchronize-current-upstream-omarchy-450-and-freebsd-current-source-and-ports-for-16)
- **Completion / archival evidence:** [Source and branch review record](../../verification/upstream-sync-pmc-review-20261123.json); native acceptance remains open

The repository synchronization is published. All six owned `main` branches and
their `release/1.6` branches select the same respective commits at this checkpoint;
Omarchy's primary `quattro` branch is synchronized too. The source and ports
`daemonarchy` integration aliases also contain their current owned main histories.
All 35 existing open PRs, representing 27 distinct feature heads, contain their
repository's synchronized main. These candidates remain in review; synchronization
does not admit their failing or incomplete native qualification.

The [revision and review record](../../verification/upstream-sync-pmc-review-20261123.json)
binds the public source identities, original diff hashes, branch ancestry and
validation boundaries. Observations were made on November 23 Pacific time
(November 24 UTC). The documentation commit itself follows this snapshot.

## Repository inputs

| Repository | Synchronized owned main | Upstream input |
| --- | --- | --- |
| daemonarchy | `89f94c28cc7a` before this documentation | Owned product repository |
| daemonarchy-src | `1d78373ea7b0` | FreeBSD `97fd69b0b884` |
| daemonarchy-ports | `e6b24255020e` | FreeBSD ports `d5f50f314664` |
| omarchy | `acdf15e738e7` | Upstream quattro `94a8c3c33211` |
| omarchy-freebsd | `029e0eba6ff6` | Owned FreeBSD adaptation |
| daemonarchy-desktop | `4b2525533600` | Owned desktop layer |

The FreeBSD source and ports imports merged cleanly. Omarchy's four conflicts
retain session cancellation, backup and preference menus, BSD architecture
checks and backup guidance, together with upstream translated notifications,
PCI probes and revised panel instructions. Translation labels removed by the
upstream agent-menu and password-menu changes were reconciled with those changes.

Review-branch conflict resolution preserves the RabbitMQ source build and its
source digests, both owned setuptools security records and every current upstream
advisory, and the newer packaged desktop snapshot rather than restoring the old
November 18 snapshot. Independent work and failed-evidence documentation remains
present. No histories were rebased or force-pushed.

Four source controller suites ran 84 cases with two explicit skips and no
failures. Three ports controller suites ran 39 cases without failures. Omarchy
CLI, menu, translation structure, power, hardware-platform and session checks
pass; complete translation coverage retains its structural-mode skip. These
checks do not establish a new native kernel, package, graphical session or image.
The product documentation lifecycle and release-sync suites pass. Authority and
lifecycle receipt gates still refuse the stale human documentation review; all
eight product Component locks remain current, and no attestation was synthesized.
Source and ports authority checks pass, as do their five and two respective
Component locks. Both still lack the required current lifecycle test receipt.

The packaged Omarchy port still selects `0640b8c1c761`, with adapter
`029e0eba6ff6`. Updating that package to the newly synchronized desktop requires
fresh adaptation, source/plist checks, native packaging and installed behavior
qualification. Existing package results retain their original input identities.

## Changes already included through FreeBSD main

All eleven closed revisions below are included through the current upstream
import. The complete compared PMC kernel, library, utility and test surface in
owned main matches that upstream source. Older RAPL and Zen 6 commit ancestry
was also checked against the authoritative GitHub graph because the local source
checkout has shallow history.

| Area | Included reviews |
| --- | --- |
| PerfMonV2 global control | [D58256](https://reviews.freebsd.org/D58256) |
| RAPL energy and PERF/IRPERF | [D58028](https://reviews.freebsd.org/D58028), [D59554](https://reviews.freebsd.org/D59554) |
| IBS shared fetch/op NMI handling and Zen 6 filters | [D60004](https://reviews.freebsd.org/D60004), [D56914](https://reviews.freebsd.org/D56914) |
| Core counters serviced alongside IBS | [D61451](https://reviews.freebsd.org/D61451) |
| Data Fabric encoding and UMC saturation | [D60769](https://reviews.freebsd.org/D60769), [D60771](https://reviews.freebsd.org/D60771) |
| Generic and AMD PMC tests | [D59549](https://reviews.freebsd.org/D59549), [D61062](https://reviews.freebsd.org/D61062), [D61063](https://reviews.freebsd.org/D61063) |

The current test directory contains 35 tracked source/support files and 126
literal ATF registration calls. This is a source inventory, not runtime test
discovery or a pass count. Native tests must exercise the selected kernel/module
and matching libpmc/tools on appropriate hardware, preserving feature-dependent
skips and negative cases. A VM without the relevant counters cannot qualify AMD
hardware behavior.

## Work still in review

No unmerged review patch was applied to main or the release branch. Applicability
below is an original `git apply --check` against synchronized source main, with no
source edits or fuzzy application. Review status describes the retained primary
snapshot, not an upstream landing promise.

| Reviews | Source review and recommendation for 1.6 |
| --- | --- |
| [D61365](https://reviews.freebsd.org/D61365), accepted | Highest-priority isolated candidate. It applies cleanly and addresses restarting stalled IBS units after sample-queue failure. Qualify buffer exhaustion, simultaneous fetch/op/core sampling, repeated start/stop and stray NMI handling, retaining the already-landed D61451. Its upstream hardware reports are supporting evidence, not our own acceptance. |
| [D61053](https://reviews.freebsd.org/D61053), accepted | Useful correctness candidate for large-increment events. The retained diff does not apply to current `hwpmc_amd.c`; rebase before selection. Verify even/odd counter reservation, process versus system ownership across CPUs, overflow/reload, rejected raw MergeEvent allocation and complete stop/deconfigure/release cleanup. |
| [D61371](https://reviews.freebsd.org/D61371), needs review | Rebase the PMC test Makefile conflict before qualification. Verify per-PMC/per-CPU limits, tick restart, buffer-full recovery, the disabled-limit path and preserved unrelated critical sections. Minimum-period and drop-record companion work is not established by the supplied pair alone; review that stack separately before claiming the whole high-rate feature set. |
| [D57630](https://reviews.freebsd.org/D57630), [D57633](https://reviews.freebsd.org/D57633), need review | Review as a complete grouping/multiplexing stack. Both diffs apply textually, but the pair alone does not provide the new PMU/assignment sources and header referenced by the glue, complete rotation/userland support or its acceptance tests. Require stable handles, constraint-aware row assignment, scaled enabled/running times and concurrent process-exit/release/unload coverage. ABI declarations alone do not deliver multiplexing. |
| [D58698](https://reviews.freebsd.org/D58698), needs review | Hold the retained diff. It accesses `pmd_branch` through `struct pmc_multipart *`, which has no such member, and dereferences that pointer before its null check. It also proposes flag `0x00000400`, already proposed for `PMC_F_GROUP_MUX` by D57630, and a conflicting major ABI transition. Resolve the interface and flag allocation together, then validate bounded multipart capacity, callback errors and old/new tools compatibility. A clean textual application does not imply a compiling or safe implementation. |
| [D60570](https://reviews.freebsd.org/D60570), needs review | Hold until the complete LBR prerequisite stack is selected and reviewed. It explicitly depends on D60569; its header/test prerequisites are absent from current main and the diff does not apply. Require context-switch/exec isolation, bounded branch payloads and actual LBR v2 hardware acceptance. |
| [D60548](https://reviews.freebsd.org/D60548), needs revision | Keep as a separate candidate. The diff applies, but review is still outstanding. Require the underlying IOMMU counter interfaces, privilege enforcement even when unprivileged system PMCs are enabled, locked match-register exclusion, row-budget limits, ownership and teardown tests, and device/DMA workload validation. |

## Remaining release qualification

Prioritize the isolated IBS stall fix for a separate native candidate, then
rebase and qualify the large-increment fix. Keep the larger ABI, multiplexing,
branch-history/LBR and IOMMU changes separately reviewable until their complete
dependencies and acceptance are demonstrated. Their exclusion from main at this
checkpoint does not remove them from the requested review queue.

The new source selections still require matched amd64/aarch64 world, kernel,
modules and package closures; actual PMC ATF outcomes; desktop and application
behavior; installation, update and rollback; ARM/Pi device acceptance; canonical
SDK/TCB/lifecycle admission; and the existing signing/release gates. Repository
synchronization does not close [SYNC-001](release-1.6.0.md#upstream-synchronization-goal-sync-001)
or the full 1.6 release objective.
