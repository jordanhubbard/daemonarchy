# RC1 upstream selection, recorded 2026-11-27

- **Status:** active
- **Owning queue item:** [SYNC-001](active-work.md#sync-001)
- **Completion / archival evidence:** [Exact branch observation](../../verification/active-release-branches-20261127-development.json) and the native port observation linked below; matched-world, desktop, hardware and canonical release acceptance remain pending.

This record updates the selected inputs of the [1.6 plan](release-1.6.0.md).
The operator selected the specific Omarchy release candidate rather than a
moving development branch. The prior stable 4.5.0 planning records remain
historical evidence. All outstanding 1.6 acceptance requirements remain open
unless their exact artifacts have separate qualifying evidence.

## Exact inputs and merged history

| Repository | Selected upstream | Owned integration |
| --- | --- | --- |
| Omarchy | [v4.6.0-rc1](https://github.com/omacom/omarchy/releases/tag/v4.6.0-rc1), peeled commit `745271ccd293fc2e7a233b269004a9926a5c6cb4` | Import `1fae8ac7713369857246d13515e1ee3467b37301`; [PR #7](https://github.com/jordanhubbard/omarchy/pull/7); owned `main` and `quattro` at `19abafa0b12560a7946b1e37444d3e6b2fc9f755` |
| FreeBSD src | Main snapshot `a972d2692bb789f9c79da4ee27dd3c32d3e3f349` | [PR #143](https://github.com/jordanhubbard/daemonarchy-src/pull/143); owned `main` and `daemonarchy` at `5fad2676be7d0c1bc75f3f673165daa697c41b91` |
| FreeBSD ports | Main snapshot `1ba4ddd7286037a7598b7a8da7c8b79bda192c76` | RC1 [PR #128](https://github.com/jordanhubbard/daemonarchy-ports/pull/128), final import [PR #129](https://github.com/jordanhubbard/daemonarchy-ports/pull/129); owned `main` at `b6a7ad4c532be23758bd9348ff510ac6bbb73ac6` |

The annotated Omarchy tag object is
`309b74a28363fca9328ebd050fcca9dee6a71849`; the peeled commit above is the
source revision. The FreeBSD compatibility source remains separately pinned at
`1923ffefc9fb5328e7d2054a01433e7cb77551eb`.

These are bounded observed snapshots, not a promise that moving upstream main
references remain unchanged. Complete Git-tree audits preserve upstream bytes,
modes and deletions outside owned changes, and preserve fork changes outside
the upstream delta. The shared Pi framebuffer path retains both the upstream
pixel-order update and the owned VideoCore support guard. Each fork retains
`verification/freebsd-main-sync-20261127-snapshot-development.json`.

## Active release branches

At the recorded observation, all six owned `main` / `release/1.6` pairs select
the same commit in each repository. The src, ports and Omarchy release refs
were plain fast-forwards from their prior ancestor commits; product,
compatibility and desktop pairs already agreed. No branch history, published
tag or artifact was rewritten. The
[exact branch observation](../../verification/active-release-branches-20261127-development.json)
retains before/after identities and the ancestry checks. Pending feature and
review heads still need their own integration and qualification.

Later on November 27, the qualified GDBM close-on-exec repair
([ports PR #126](https://github.com/jordanhubbard/daemonarchy-ports/pull/126))
and Nose Python 3.12 repair
([ports PR #123](https://github.com/jordanhubbard/daemonarchy-ports/pull/123))
landed with their original source and scoped native observations preserved.
Ports `main` and `release/1.6` then advanced together to
`7db3a135d48590e9cf8a5c327c3d7766194701af`; the selected upstream snapshot
above remains an ancestor. All ten Nose port inputs and the GDBM implementation
and control inputs match their qualified native source. These integrations
retain the original optional-profile, canonical receipt and release acceptance
gaps. The ARM worker's storage recovery is still in progress; historical
package results do not establish that the recovered SDK or source tree is
currently intact. Independent content readback is required before more native
package qualification.

## November 28 refresh and pkg upgrade regression

The November 28 imports select FreeBSD src main
`2496a1c6b14e7d2dc01b8e55412f54aca73a31a4`, integrated at owned
`9720a99c26cbe281d84b86e9a88a82e8c34d091d`, and ports main
`104508db6c34399e8e25685ca866c765fb564a8d`, imported at
`4ec2ca87e198b3e5f08b785be8612ebf5845ce3d`. The source recipe also retains
the accepted upstream Pi5 DTB/D0 overlay inclusion. Exact input preparation
and a source build plan do not establish a completed build of this selection.

[Ports PR116](https://github.com/jordanhubbard/daemonarchy-ports/pull/116)
then landed the local-archive upgrade repair at
`131cd72239551711cef66391fabe26ff1cf54b97`; its tree is identical to the
tested candidate. The [development comparison](../../verification/pkg294-local-archive-upgrade-development-20261128.json)
records fresh native builds of pkg 2.9.4_1 and pkg 2.9.4_2 on the existing
amd64 tester. Both pass the eight original port construction targets and
independent verification of 77 payloads and the declared directory. Using
identical original 34-case upgrade-file tests, the baseline has 33 passes
and one retained failure: an archive replacement is reported as a new install.
The candidate passes all 34 with no skips using the packaged static binary.
Normal registry, accounts, loader hints, mounts and source are preserved.

These observations use the older cb38 kernel and existing userland, with ELF FreeBSD version
1600029. They do not qualify the selected CURRENT world, the entire upstream
pkg suite, another architecture at this version, canonical SDK/TCB/lifecycle,
or final installation, update, rollback, signing or publication. The November 27
branch observations and earlier native results below retain their original pins.

## Native package and test evidence

The port selects `DISTVERSION=4.6.0-rc1` and the exact owned Omarchy import.
Its native package name is `omarchy-4.6.0.r1.pkg`, 13,212,716 bytes, SHA256
`017d1e792e8fff8f709732799d83bd5d1ac6f0b30be03f55f16b98048ece652a`.
This is a retained development package; this record does not select it for a
signed feed or claim installed desktop acceptance.

Original native checksum, extract, patch, configure, build, stage, check-plist
and package targets passed on the existing FreeBSD 16 amd64 tester running
kernel/world revision `cb38d6498a24`. Twelve independent native BSD zero-fuzz
patch controls passed. The static plist's 138 additions and 101 removals each
map to an actual RC1 source addition or removal. Native package identity and
3,924 archive members were checked; installed patch backups are absent and an
independent second copy matches the package hash. The final ports import
preserves all 17 port inputs and the tested Mk framework unchanged.

Original compatibility tests total 40 passes and two explicit root-only skips
across preserved runs. Incorrect already-adapted inputs were replaced with the
pristine pinned sources; the final power fixture used the native GNU-userland
PATH entry needed to preserve interception by its original fake command. Only
affected tests were rerun, with their original assertions and deadlines.
Twelve JavaScript VM controls exercise the actual patched backend-dispatch
functions; they do not constitute running Qt/QML or network acceptance.

The prepared portable CLI suite passes and 246 of 260 non-compositor shell test
files pass. All 14 remaining failures reproduce on the unchanged owned base
with the same complete tracked inputs and source-specific private font setup.
All initial failures and input corrections remain retained. No compositor or
visual acceptance is inferred.

The ports fork's
[`verification/omarchy-460rc1-native-development-20261126.json`](https://github.com/jordanhubbard/daemonarchy-ports/blob/b6a7ad4c532be23758bd9348ff510ac6bbb73ac6/verification/omarchy-460rc1-native-development-20261126.json)
records the scoped observations. The reviews reported no hosted checks; absence
of checks is not a passing hosted CI run. Authority and locks passed in the
source/ports synchronization worktrees, while canonical receipts were missing.

## Remaining acceptance

- Synchronize remaining feature and review work with the newly selected main
  histories, preserving work in progress and prior evidence. The six active
  main/release pairs are synchronized at the observation above.
- Rebuild and qualify changed dependency closures and matched latest-source
  kernel, world, modules, seeds, packages and installer images on both amd64 and
  aarch64. The older tester world above does not meet this gate.
- Complete installed login/desktop, applications, service, native network,
  visual, install, update and rollback acceptance for exact release artifacts.
- Retain the full ARM register and physical qualification obligations, including
  Pi 4 before Pi 5 and Ethernet plus native SD operation. A simulated boot or
  source import cannot satisfy those requirements.
- Complete canonical per-unit ownership, provenance, Component lifecycle,
  SDK/TCB, release freeze, signing and publication gates. No authority marker,
  lifecycle receipt or native admission is manufactured by this record.
