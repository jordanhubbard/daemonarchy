# 1.6 upstream synchronization and PMC review, November 24

- **Status:** active
- **Owning queue item:** [SYNC-001](active-work.md#sync-001-synchronize-current-upstream-omarchy-450-and-freebsd-current-source-and-ports-for-16)
- **Completion / archival evidence:** [Revision and validation record](../../verification/upstream-sync-pmc-review-20261124.json); native and release acceptance remain open

This refresh imports the upstream tips observed on November 24, 2026, preserving
the owned changes and both sides of each history. It follows the
[November 23 review](pmc-1.6-review-20261123.md), whose source identities and native
evidence remain historical records. All six owned main/release branch pairs are
synchronized. The 36 open PRs represent 28 distinct feature heads; their current
main ancestry is recorded separately from their original build/test evidence.

## Repository inputs

| Repository | Owned main after import | Upstream selection |
| --- | --- | --- |
| daemonarchy-src | `ebd6178257dc` | FreeBSD source `a82c04293ecc` |
| daemonarchy-ports | `d32c635423e1` | FreeBSD ports `e9ccafded492` |
| omarchy | `41fd84ddabc2` | Upstream quattro `7427fab86f67` |
| omarchy-freebsd | `029e0eba6ff6` | Owned FreeBSD adaptation |
| daemonarchy-desktop | `4b2525533600` | Owned desktop layer |
| daemonarchy | `4f351f605f6f` before this documentation | Owned product repository |

Source imports 13 commits, ports 37 and Omarchy 19. All three merges preflighted
and completed without conflicts. The overlapping source ACPI change moves
machine initialization after sysctl setup and frees that context on failure.
Omarchy keeps the owned backup, preference and session routes and BSD architecture
normalization while importing the upstream CLI parsing and hardware scan fixes.
The source/ports `daemonarchy` aliases and Omarchy `quattro` also select their
respective synchronized mains.

One review-branch merge conflicts in the vulnerability catalogue. Its resolution
retains the new mod_perl, nginx and OpenEXR advisories, the owned setuptools VCS
advisory and the owned setuptools containment ranges. All other upstream advisory
blocks are compared byte for byte; XML syntax and unique advisory IDs are checked.
No review history is rebased or force-pushed. Synchronizing a candidate does not
merge that candidate into main or admit its native results at a new revision.

## Validation and limits

The source controller suites run 84 cases with two original skips and no
failures. The ports controller suites run 39 cases without failures. Of 33
selected Omarchy test files, 31 complete with exit zero; the keyboard-layout and
pacman-template files stop on missing host tools, `xkbcli` and `pacman-conf`.
Four completed suites report skips: unavailable hibernation, structural translation
mode, missing `inotifywait`, and missing icon-rendering tools. These are selected
host-side checks, not full FreeBSD desktop or graphical acceptance.

The ports whitespace check reports warnings inside original upstream patch
files. Those files match the selected upstream blobs; they are retained exactly.
Source and ports authority validation passes, while lifecycle verification still
fails for the missing configured test receipt. Omarchy has no Literate AI project
manifest. Product documentation and receipt gates retain their actual results in
the revision record; no human attestation or execution receipt is synthesized.

Existing native packages and full OS builds retain their exact earlier source
identities. They do not qualify these new imports. The packaged Omarchy port
still selects the earlier desktop snapshot; adapting and packaging the newest
repository selection remains required.

## Requested PMC work

All 19 supplied review pages and original diffs were retrieved again. Their diff
bytes match the previous review. The complete selected PMC kernel, library,
utility and test surface matches current upstream and is unchanged by today's
13 source commits. Consequently, the eleven already-landed changes remain
included:

| Area | Included revisions |
| --- | --- |
| PerfMonV2 global control | [D58256](https://reviews.freebsd.org/D58256) |
| RAPL and PERF/IRPERF | [D58028](https://reviews.freebsd.org/D58028), [D59554](https://reviews.freebsd.org/D59554) |
| IBS fixes and Zen 6 filters | [D60004](https://reviews.freebsd.org/D60004), [D56914](https://reviews.freebsd.org/D56914) |
| Shared core/IBS NMI service | [D61451](https://reviews.freebsd.org/D61451) |
| Data Fabric and UMC fixes | [D60769](https://reviews.freebsd.org/D60769), [D60771](https://reviews.freebsd.org/D60771) |
| Generic and AMD PMC tests | [D59549](https://reviews.freebsd.org/D59549), [D61062](https://reviews.freebsd.org/D61062), [D61063](https://reviews.freebsd.org/D61063) |

The test inventory remains 35 tracked files and 126 literal ATF registration
calls. This is neither runtime discovery nor a hardware pass count. The earlier
commit ancestry evidence remains applicable because the new import contains the
previous upstream tip and the selected PMC surface is identical.

The eight pending revisions were checked again against the new source main,
without editing or fuzzing their diffs:

| Candidate | Recommendation for 1.6 |
| --- | --- |
| [D61365](https://reviews.freebsd.org/D61365), accepted, applies | First isolated candidate: qualify stalled-IBS recovery, exhausted buffers, simultaneous fetch/op/core sampling, stop/start and stray NMIs. Preserve D61451. Upstream hardware reports remain supporting evidence. |
| [D61053](https://reviews.freebsd.org/D61053), accepted, conflicts | Rebase before selection. Qualify even/odd row reservation across process/system modes, overflow/reload and complete stop/deconfigure/release cleanup. |
| [D61371](https://reviews.freebsd.org/D61371), needs review, conflicts | Resolve the PMC test Makefile conflict and review the complete minimum-period/rate-limit/drop-record stack. Qualify per-CPU limits, tick restart and buffer recovery. |
| [D57630](https://reviews.freebsd.org/D57630) and [D57633](https://reviews.freebsd.org/D57633), need review, apply | Keep the complete grouping/multiplexing stack separate. The pair lacks referenced PMU/assignment prerequisites, complete rotation/userland support and acceptance tests. |
| [D58698](https://reviews.freebsd.org/D58698), needs review, applies | Hold for the invalid `pmd_branch` access through `struct pmc_multipart *`, dereference before its null check, ABI transition and flag collision with grouping. |
| [D60570](https://reviews.freebsd.org/D60570), needs review, conflicts | Hold for the complete LBR prerequisites, including D60569 and missing headers/test source. Require context-switch/exec isolation and actual LBR v2 hardware. |
| [D60548](https://reviews.freebsd.org/D60548), needs revision, applies | Keep separate until counter privilege, match-register exclusion, ownership, row limits and teardown are reviewed and tested on IOMMU hardware. |

No unmerged PMC diff is imported into main or release. Textual applicability does
not establish compilation, ABI compatibility or safe hardware behavior. The
[prior detailed findings](pmc-1.6-review-20261123.md#work-still-in-review) remain
applicable to the identical diff bytes.

## Remaining release work

Repository synchronization leaves SYNC-001 active. Matching world/kernel/modules,
source-built package closures, actual PMC ATF runs, desktop adaptation, installer,
update/rollback and recovery, Pi 4 before Pi 5 device acceptance, fleet updates,
canonical Component/SDK/TCB admission and signing remain release requirements.
