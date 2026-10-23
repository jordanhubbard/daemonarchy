# 1.2.0 completion obligations

- **Status:** active
- **Owning queue item:** [RELEASE-001](active-work.md#release-001-deliver-120-through-first-class-freebsd-literate-ai-execution)
- **Completion / archival evidence:** Pending exact final LitAI release receipts,
  native/VM/physical acceptance and independently verified GitHub publication.

[RELEASE-001](active-work.md) carries the operator's goal: finish the existing
backlog and publish a new Daemonarchy release entirely through qualified
Literate AI execution. This ledger expands the queue and the remaining
[ROADMAP.md](https://github.com/jordanhubbard/daemonarchy/blob/main/ROADMAP.md) obligations. Every row is open for the new release;
prior evidence remains useful only within its original artifact/hardware scope.
There is no inherited waiver, current receipt or claim of release readiness here.

## Worker and evidence model

Daemonarchy is FreeBSD-only. No other OS Flavor or product runtime matrix is a
release requirement. Parent-framework portability CI remains upstream work;
it does not delay implementation of the release-blocking loader debugger.

The controller may run on any qualified Literate AI host OS. Native FreeBSD build
and test actions run in FreeBSD; a VM's host OS never supplies its guest identity.
Use a dedicated native build worker for source/packages/images and reusable
caches; disposable guests for clean install, upgrade, rollback and boot checks;
and physical machines for graphics, radios, firmware and suspend acceptance.
QEMU guests and existing physical workers use private worker configuration.
Explicit provisioning owns VM sizing, exact guest inputs, supervision and bounded
cleanup; static registration does not imply automatic VM creation.

Signing remains on the protected signer. Public evidence carries source, wheel,
toolchain, guest/target and artifact identities, never private endpoints or keys.
The final release must use the exact admitted inputs through the LitAI lifecycle
and publication gates. Historical manual build logs and development-source probe
results cannot substitute for current installed-wheel receipts.

## Obligation ledger

| ID | Queue owner | Required completion and direct evidence |
| --- | --- | --- |
| R12-01 | ADOPT-002 | Qualified upstream FreeBSD contracts, FreeBSD OS Flavor, registration, alignment, native toolchain realization, paths, health, isolated execution and exact installed-wheel regression evidence. |
| R12-02 | ADOPT-002 | Retained mixed source/binary admission, invalidation, current native receipts, artifact custody and release enforcement; changed input, failed test, missing evidence and unauthorized publication are rejected. |
| R12-03 | UI-001 | Multiple creative ANSI visualizer styles use actual disk, package, transfer and stage events; console, SSH/serial, small terminals, 16/256 colors, resize, reduced motion and plain logs pass; waits/failures never animate as success. |
| R12-04 | PKG-001 | Retain complete exact release package DAGs for every selection, including transitive/official/GPU/optional packages, provenance, hashes, sizes, edges and space estimates; reject stale or conflicting catalogues. |
| R12-05 | PKG-001 | One coordinator performs bounded parallel downloads and actual safe parallel installation of ready independent packages; package DB, files, scripts, triggers and services remain coherent. Competing pkg processes are insufficient. |
| R12-06 | PKG-001 | Native serial/parallel comparison reports download, staging, install/commit, total time and peak resources separately; shared dependencies, file/script conflicts, low disk, interruption, retries, integrity and BE recovery pass. |
| R12-07 | GUI-001 | Native colorful responsive install/update/remove UI shares planner, transaction identity and events; real input, accurate progress, reduced motion and failure/retry work; contribute required engine changes and application port upstream. |
| R12-08 | DEBUG-001 | Explicit wired loader/early-kernel debug profile, source ownership, NIC support, trust/session boundaries and exact symbols; retain actual early-boot and crash transport evidence and document genuinely unsupported phases. |
| R12-09 | HW-001 | NVIDIA installation, SDDM login and actual Hyprland rendering, external displays and suspend/resume pass on supported hardware; retain Intel/AMD regression evidence. CUDA/nvidia-smi alone is insufficient. |
| R12-10 | HW-001 | Integrate the MacBook graphics and T2 keyboard fixes into exact normal-boot/release images; qualify sustained display/input, missing wireless and unexplained restarts with physical evidence. A successful development-kernel login alone does not close this row. |
| R12-11 | HW-001 | Resolve and qualify the recorded ASRock/RTX system's boot/firmware failure; network reachability or unrelated hardware success cannot close its physical acceptance. |
| R12-12 | HW-001 | Actual Bluetooth audio playback, output selection, volume, disconnect/reconnect/removal and reboot persistence pass; real keyboard/mouse pairing still works. Null transport is insufficient. |
| R12-13 | HW-001 | Actual certificate-validated PEAP/MSCHAPv2 and EAP-TLS exchanges, untrusted server rejection and reboot reconnect pass in installer/desktop paths; transferred credentials/certificates remain private. A controlled test network may provide this evidence. |
| R12-14 | HW-001 | Both selected-partition and selected-free-space installs preserve another OS/data/EFI entries; real Windows dual boot passes; invalid/insufficient-space selections fail before writes and no implicit resize occurs. |
| R12-15 | HW-001 | Physical Secure Boot enrollment preserves OEM/Windows trust; enforced boot, rejected untrusted components, signed maintenance and recovery pass with exact protected production authority. VM-only evidence cannot close physical enrollment. |
| R12-16 | RELEASE-001 | Final ISO QEMU BIOS/UEFI and plain/GELI unattended installation, actual Hyprland/login/rendering, keyboard/pointer, resizing and reboot pass; enforced UEFI uses the intended trust chain. |
| R12-17 | RELEASE-001 | Refreshed bhyve installation and graphical Hyprland acceptance, input, resizing and reboot pass, including the outstanding encrypted configuration and optional source/ports checkout selections. SSH-only acceptance is insufficient. |
| R12-18 | RELEASE-001 | Refresh/reconcile source and ports plus owned desktop/compatibility inputs; pin coherent snapshot/jail/packages/modules, retain native changed-port testport and clean bulk results, and submit upstream contributions. |
| R12-19 | RELEASE-001 | Existing-release upgrade, signed maintenance, injected failure, rejection, reboot, ZFS rollback and return pass on exact final inputs; retain physical desktop/application acceptance and recovery evidence. |
| R12-20 | RELEASE-001 | Final image/feed/checkouts checks bind kernel/driver/package identities, signatures, hashes, sizes, selected optional sources and artifact budgets; no preliminary-image result is relabeled as a final-image result. |
| R12-21 | RELEASE-001 | Review all documentation and release-by-release CHANGELOG, support tables, install/update/debug instructions and upstream links against final behavior and direct evidence. |
| R12-22 | RELEASE-001 | Full declared LitAI verification and release gates pass for exact final revision; publish the new GitHub release through the qualified method, verify immutable tag/assets independently and close each ledger row with its retained receipt. |
| R12-23 | COMP-001 | Represent the complete pinned `/usr/src` and `/usr/ports` trees through canonical Component catalogs with zero unowned inputs, explicit shared relationships and target/options variants; admit and qualify the exact selected native dependency closure without relabeling catalog membership as build/acceptance. |
| R12-24 | PERF-001 | Execute graph units as literal LitAI Components with versioned pkg products, full provenance and typed dependencies; demonstrate substantially faster equivalent native build, packaging and ISO workflows with correct invalidation and independent runtime acceptance. |
| R12-25 | HW-003 | For laptops needing external firmware, the installer identifies required device/board files, obtains them from a verified online source or operator-supplied local media, records provenance and hashes, installs them into the target, and verifies driver attachment after reboot. On this wiped MacBook, qualify an Apple recovery-image acquisition path for BCM4364 without requiring macOS; refuse a wireless-ready claim when firmware or driver support is missing. |

The R12-18 native ports checkpoint on October 23 used a disposable FreeBSD
16.0-CURRENT poudriere jail and the Omarchy debugger-panel changes from
[ports PR #21](https://github.com/jordanhubbard/daemonarchy-ports/pull/21).
The PR's older ports tree planned 292 source builds against the current binary
feed. A separate test worktree put its 21 new product ports on the official
package-feed commit `792be2623dc0ef1ac471fb80d4bb242b10b1bdde` while
retaining that feed's Quickshell 0.3.2. At temporary test revision
`ef1b27fdf1f9174bcd61124d419b146f07888807`, the matched dry run planned
only `ports-mgmt/pkg` and `x11-wm/omarchy`; the subsequent native
`poudriere testport` built both and completed Omarchy package installation and
removal with exit 0. Its retained worker log is under
`16test20261019-omarchybaseline20261023/2026-10-23_04h11m50s`.
The temporary transplant is not the release ports revision. A proper two-parent
merge of the product head and official package snapshot is now proposed in
[ports PR #22](https://github.com/jordanhubbard/daemonarchy-ports/pull/22) at
`d7cff107c2e1c80190012ec7db576707a58f19ab`. Its tree
`92124692db49cf872a1e3a6de4468b60f93b4a51` exactly matches the tested
transplant while retaining both histories. A native 21-origin poudriere dry run
at this exact merge revision fetched 1,180 packages and planned 23 builds:
the 21 product ports plus `ports-mgmt/pkg` and `devel/cmake-core`. Its log is under
`16test20261019-omarchyrefresh20261023/2026-10-23_04h40m52s` on the worker.
The subsequent full native bulk at that same ports head exited 0: 1,203 queued,
23 built, 1,180 fetched, zero failed, skipped or ignored, in 02:37:23. The
`daemonarchy-1.0.1,1.pkg` output is present. Its retained log is under
`16test20261019-omarchyrefresh20261023/2026-10-23_05h20m09s` on the worker.
This was a disposable October 19 CURRENT jail, not the production release jail.
Physical desktop acceptance, coherent source/package/module pinning, signed feed
and final artifact identity are still required before R12-18 can close.

The completed PR #22 bulk built `daemonarchy-1.0.1,1`: that branch diverges from
the published `daemonarchy-1.1.1` ports branch and lacks 31 release-branch
commits, including its desktop version and VirtIO DRM backport. It is therefore
dependency evidence, not the next ISO's package baseline. A disposable
two-parent merge with the 1.1.1 branch, followed by ports Component PR #7,
Fastfetch PR #8 and a provenance-preserving cherry-pick of the physically
tested Radeon PR #19, is retained at `13270547f4689b83a37969439abf1548928990f3`.
It yields `daemonarchy-1.1.1,1`, `omarchy-4.0.4_24` and
`drm-612-kmod-6.12.110.1600028_6`. Native patch stages pass for Omarchy and
DRM; the patched Omarchy QML contains FreeBSD Wi-Fi and debugger status, and
the Radeon sizing-helper regression passes against the patched source.
Project authority and native locks pass, while the lifecycle receipt is still
missing. The exact 30-origin native `poudriere bulk -n -b latest` at this head
finished with exit 0 on the October 19 CURRENT jail: 1,469 queued, 1,207
official packages fetched, 262 local builds planned, and zero failed, skipped
or ignored. Of the 262 builds, 234 are GPU or Wi-Fi firmware flavors and 28 are
other ports, including Daemonarchy, Omarchy, DRM and NVIDIA. Its retained log
is under `16test20261019-omarchymacbookpreflight20261023/2026-10-23_09h26m22s`
on the native worker. The corresponding full bulk and final source/kernel/jail
coherence remain open; no 1.2 desktop tag or final image exists.

A second disposable ports worktree refreshed PR #22 against FreeBSD ports
`99fc0413c18d18fc6c9750f2265ae9e33811b918`, 592 commits beyond the
official package-feed baseline. Its merge revision
`71d93183e1b58b76352db825e788f63cf5517797` retains the product ports;
conflicting Makefiles were resolved to the newer upstream definitions only in
that test worktree. The exact 21-origin native `poudriere bulk -n -b latest`
finished with exit 0 and planned 1,193 packages: 965 fetched and 228 source
builds, including Chromium, CEF, Rust and Qt. Its retained log is under
`16test20261019-omarchycurrentpreflight20261023/2026-10-23_08h11m44s`.
This is a reviewed upstream freshness comparison, not a completed build of the
newer tree. PR #22 remains the exact revision with a completed native bulk;
any later ports refresh requires its own full build and acceptance.

An isolated native source preflight at `02984cfbe95c063f130ae20d7ea6ed520df88a8f`
merges the EFI timer PR #13 and T2 keyboard PR #19 onto the fork's
`daemonarchy` branch, then merges FreeBSD-current through
`bea44a83631704110de8bbd7693b683c81d4fe55`. Both fixes and that upstream
head are ancestors of the clean preflight tree. The six EFI timer controls,
`-Werror` builds of `hidquirk.ko` and `hkbd.ko`, and the native `stand` build
pass on this tree. The resulting Lua EFI loader hashes to
`00e7ea32efc7288daae1526bbaf631a724d9c83bcc6b07da8e5b4e14ccfaa909`.
The full native GENERIC kernel and modules build then completed in 1,849 seconds
with `-j2`; its kernel SHA-256 is
`fa04e893df37a6c2d98200450855ce2483e8dfd71c5131d4d420116ec18cacdd`,
and its embedded build identity names the exact preflight revision. All four
existing verified-boot source patches pass `git apply --check` against this
tree. These are build and merge checks; they are neither final signed boot
artifacts nor a MacBook reboot or sustained-input qualification.
The operator also saw `Autoboot i 3 seconds` on the physical EFI menu. The
current Lua source spells `Autoboot in` correctly, so the missing character
remains a display-path observation to reproduce and fix on the final loader;
the passing timer controls do not resolve that separate visual defect.

The MacBook's repeated `vap_transmit: state=5 etype=0x800` messages come from
the preview `if_brcmfmac` module before it checks whether a firmware flow ring
exists. State 5 is net80211 RUN; the messages therefore establish an IPv4
transmit attempt, not firmware submission or delivery to the AP. A diagnostic
module built with `-Werror` against the preview kernel's exact FreeBSD source
`bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` hashes to
`58163ef0d117d9da81710ce153d7d2beb777beae9a3891d27cd6c6cca67d3bb6`.
It removes the per-packet console print and exposes read-only counts for VAP
attempts, dead firmware, missing or full flow rings, submitted packets and TX
completions. It changes no transmit or link policy and has not been deployed.
The next physical check must compare those counters with firmware link events,
ARP/DHCP and RX counts over a wired debugger before classifying the failure.

The FreeBSD-native driver is being prepared as
[ports PR #23](https://github.com/jordanhubbard/daemonarchy-ports/pull/23):
`net/if_brcmfmac-kmod` pins the ISC-licensed upstream source and applies the
retained preview changes. On the native FreeBSD amd64 worker, `poudriere
testport` passed package staging, QA, plist and install/deinstall checks in
`16test20261019` with the isolated `brcmfmacport20261023` tree. After patching,
all 14 C and header files byte-match the physically tested preview source.
This package check uses the candidate jail, not the final integrated kernel,
and does not establish working MacBook traffic. The ISO recipe and installer
still need to select the package and acquire/install verified Apple board
firmware before R12-10, R12-18 or R12-25 can close.

[Product PR #31](https://github.com/jordanhubbard/daemonarchy/pull/31)
prepares that ISO path: the module is selected from the candidate ports tree,
installed and locked on a MacBook target, while the installer offers a pinned
Apple recovery download or a local recovery image before network selection.
The importer checks the full image and four files, retains provenance privately,
and stages those files for the live radio and installed system before disk
changes. The backend and syntax checks pass, and the native FreeBSD tmpfs mount
form was exercised on the worker. No ISO from this branch has booted a MacBook;
the live download/media screens, kernel attach, signed inventory, DHCP/traffic,
reboot persistence and physical attestation remain open.

The same worker now retains a separately verified candidate set cache at
`/usr/daemonarchy/cache/iso-snapshot-20261019-041802b362aa`. The official
snapshot's `REVISION` remained `041802b362aa` before and after acquisition;
`base.txz`, `kernel.txz` and `lib32.txz` matched its MANIFEST SHA-256 values.
The kernel identity inside `kernel.txz` matches the actual poudriere jail kernel,
and both base and jail headers report OSVERSION `1600028`. This establishes
candidate set/jail coherence, not a built ISO or source-checkout selection.
The current committed checkout catalogue still names the older source revision
`bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf`; its required kernel identity
check will refuse these new sets until a matching signed catalogue is selected.

The October 23 disposable source integration check merged the then-current
[signed-firmware PR #29](https://github.com/jordanhubbard/daemonarchy/pull/29)
head `2cb0b460f003e986ca806015d55a388f9b0409d8` and
[debug-status PR #30](https://github.com/jordanhubbard/daemonarchy/pull/30)
head `326f95e5fee8fcc6df5583afb2100b38dd27449e` on `main`. The only
conflict was the generated authority-review marker; recording the combined
review produced identity `sha256:ab398cbd684b96dfebd1f6b3b3d8f9a1b366f7ebfbfb1d544c03c269034fb452`.
The combined tree passed `litai project validate`, all 26 secure-boot unit
tests and shell syntax checks. `litai verify` passed authority and locks but
failed its missing committed test-receipt gate. This disposable preflight is
merge preparation, not a native or physical release qualification.

## Closure rule

A row closes only when its implementation and required native/VM/physical
acceptance exist and are bound to the applicable final source/artifact identities.
An upstream submission requires the submitted contribution, without inventing
maintainer acceptance. A platform limitation, unavailable physical device, stale
receipt or deferred implementation stays open. Any proposed scope change must be
an explicit operator decision; this ledger does not make one implicitly.

R12-08 is the immediate implementation priority and a release blocker. R12-01/R12-02
remain final lifecycle admission requirements; they do not prevent original-source
loader development or native qualification. Framework work is tracked by
[issue 67](https://github.com/jordanhubbard/literate-ai/issues/67) and
[merged PR 68](https://github.com/jordanhubbard/literate-ai/pull/68). The retained
Standard execution route remains unqualified under reopened
[issue 22](https://github.com/jordanhubbard/literate-ai/issues/22); receiver and
wheel-bootstrap success cannot close R12-02.

The exact framework wheel at `89278c96` has passed wheel qualification and offline
native installation with 37 verified distributions. A native sample completed
public Standard rebind, documentation review and exact retained-source planning,
but authorized execution stopped before compilation because it demanded an unused
coding agent. The provider-neutral correction is tracked in
[issue 70](https://github.com/jordanhubbard/literate-ai/issues/70). This sample is
only a framework platform check; it cannot qualify Daemonarchy's complete retained
project or close either prerequisite row. The new native `pkg` host-install
realization was contributed in that merged framework PR, with native and
installed-lifecycle qualification still required.

The subsequent qualified framework wheel at `d96f6b8b` also installed offline
with 37 verified distributions. Its native sample completed reviewed Standard
rebind, documentation review and fresh retained-source review without a coding
agent. Authorized execution now reaches Python toolchain admission, where it
refuses because the shared builder searches only unversioned aliases and the
aligned native interpreter is `python3.12`. The framework contribution is adding
versioned interpreter discovery and preserving structured CLI refusals. No
compilation, passing receipt, Daemonarchy lifecycle qualification or release
readiness is claimed from this attempt; the complete native positive and
changed-input/failed-test checks remain required.

The current combined framework checkpoint at `e90cbadb` passes the full controller
regression (2,035 passes, 70 skips, no failures), exact installed wheel checks,
18 installed FreeBSD binding cases and real controller/FreeBSD binding plus
metadata-only original-adoption probes. The product now has the reviewed Standard
rebind and in-place original authority, with its existing receipt contract and
source layout preserved. [The checkpoint](../../verification/native-first-binding-integration-development.json)
keeps these preparation results separate from native execution. Authority and all
eight host contract locks pass; the native receipt and ISO remain missing.
R12-01/R12-02 still require complete native profiles, input/toolchain admission,
actual lifecycle execution and rejection/receipt/publication evidence. No ledger
row closes from metadata-only adoption.
