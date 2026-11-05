# 1.5.1 plan: network upgrades, forkability and the framework-executed goals deferred from 1.5.0

- **Status:** active
- **Owning queue item:** [NETUP-001](active-work.md#netup-001-upgrade-an-installed-systems-base-kernel-modules-and-boot-files-over-the-network)
- **Supporting queue items:** [NETUP-002](active-work.md#netup-002-update-trust-over-the-network-package-key-and-secure-boot-certificate-rotation), [NETUP-003](active-work.md#netup-003-qualify-upgrade-paths-on-exact-artifacts), [FORK-001](active-work.md#fork-001-let-another-developer-fork-the-repositories-and-publish-their-own-installer-packages-and-feeds), [BUILD-001](active-work.md#build-001-cut-freebsd-source-ports-iso-and-release-cycle-time-10x-with-literate-ai), [COMP-001](active-work.md#comp-001-model-complete-freebsd-source-and-ports-trees-as-components), [PERF-001](active-work.md#perf-001-execute-native-components-and-substantially-accelerate-iso-builds), [PERF-002](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140), [DEV-001](active-work.md#dev-001-provide-an-operator-ready-native-component-development-system), [ADOPT-003](active-work.md#adopt-003-qualify-retained-native-execution-and-release-enforcement-deferred-half-of-adopt-002), [SRC-002](active-work.md#src-002-qualify-native-freebsd-source-builds-and-packages-deferred-half-of-src-001), [RELEASE-002](active-work.md#release-002-run-a-release-entirely-through-qualified-literate-ai-execution-deferred-rest-of-release-001), [TREE-001](active-work.md#tree-001-browse-usrsrc-and-usrports-on-the-system-as-nested-html-cards), [MON-001](active-work.md#mon-001-worker-activity-monitor-and-graphical-package-browser-on-the-installer-visual-sdk), [LITAI-PKG-001](active-work.md#litai-pkg-001-ship-literate-ai-as-a-port-and-package-so-users-run-srcports-operations-with-litai)
- **Completion / archival evidence:** pending; nothing here is claimed done. Done means the evidence in each queue item, retained with exact inputs.
- **Published 1.5.0 gate carry-over:** [GUI-001](active-work.md#gui-001-deliver-a-colorful-fast-graphical-package-manager), [DEBUG-003](active-work.md#debug-003-deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14), [HW-004](active-work.md#hw-004-t2-touch-id-login-through-fprintd), [EXT-002](active-work.md#ext-002-sandboxed-lua-extensions-for-content-we-did-not-write), [DESKTOP-001](active-work.md#desktop-001-ship-the-desktop-launchers-and-menu-entries-in-the-daemonarchy-desktop-package), and [SIGN-001](active-work.md#sign-001-one-signing-session-per-release-stop-the-key-window-churn). Their delivered 1.5.0 portions remain published; the unticked acceptance moves here.

Opened 2026-11-01. It exists because of an assertion that was checked and found not to hold: that
Daemonarchy 1.5 would be the last release needing an ISO because full network upgrades from the GitHub
CDN are supported, and that another developer can fork the repositories and publish their own installer
and package collection. The investigation is recorded below. No document claims the assertion.

## Verdicts

| Half | Verdict | One line |
|---|---|---|
| A. Full network upgrade from the GitHub CDN | **PARTLY** for application packages, **FALSE** as asserted | Application packages upgrade over the network from signed feeds. Base, kernel, kernel modules, boot files and trust do not, and no upgrade of the 1.4 line was accepted. An ISO is still required across a snapshot change and for any release whose upgrade has not been qualified. |
| B. Another developer can fork and publish their own installer and feeds | **PARTLY** (possible with code edits), **FALSE** that it is easy | Several scripts take the repository and key as parameters and `pkg-repo.sh keygen` exists, but the installer pins `jordanhubbard/daemonarchy` URLs, a committed public key and our checkouts and extension feeds, and there is no fork guide. |

## A. The evidence

What works today:

- **Application packages.** `pkg upgrade` against the signed Daemonarchy feeds, which are GitHub release
  assets (`pkg-repo.sh`: "the repository is the assets of one GitHub release"). The 1.1 record shows an
  application-package upgrade and ZFS rollback on development artifacts
  ([testing-1.1-upgrade.md](../testing-1.1-upgrade.md)). `daemonarchy update` is described as saving a boot
  environment first ([getting-started.md](../getting-started.md#10-keep-it-up-to-date)); the implementation
  is in the separate omarchy-freebsd repository (`freebsd-bin/omarchy-snapshot` mentions `bectl`), which was
  not read for this plan.
- **Same-snapshot boot maintenance (development tool).** `daemonarchy-secureboot stage` and `activate`
  validate a signed bundle, stage it in a new boot environment and activate it for the next boot
  (`secureboot/maintenance.py`; [HACKING.md](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#secure-boot-development)). The 1.1 record
  has QEMU evidence, including a refused bad bundle and a rollback, with development authority
  ([testing-1.1-upgrade.md](../testing-1.1-upgrade.md#enforced-same-snapshot-boot-maintenance-checks-2026-10-16)).
  The file's own header says installer integration and native transaction qualification are required
  before it can be a supported update command.

What does not exist or is not qualified:

- **No base or kernel feed.** Nothing publishes a base, kernel or pkgbase feed for installed systems.
  [source-builds.md](../source-builds.md) and HACKING describe development pkgbase packages and installer
  sets, and say the snapshot-based procedure remains the release input path.
- **A newer feed on an older base is refused.** `scripts/adopt-candidate-packages.sh` compares the running
  kernel and userland `OSVERSION` with the catalogue and stops: "Upgrade the FreeBSD base and kernel
  together, with matching drivers, before selecting this feed." HACKING: "a newer feed requires a coordinated
  base, kernel and driver upgrade first."
- **Kernel modules are locked** to the signed inventory on verified installations; changing a driver needs the
  matching signed inventory and native package in the candidate environment
  ([getting-started.md](../getting-started.md#10-keep-it-up-to-date), [secure-boot.md](../secure-boot.md#update-and-recovery-contract)).
- **Boot files.** The loader, secure kernel, manifests and `daemonarchy-secureboot` itself arrive only by
  the maintenance bundle (`MANAGED` in `secureboot/maintenance.py`), which accepts only a whitelist of known
  source commits (`SOURCE_OSVERSIONS`). "Base/ABI transitions, certificate rotation and an EFI loader-protocol
  change need a separately qualified migration" (HACKING, secure-boot.md).
- **Trust.** The 1.3.1 rotation shipped a new image and kept the old feed for old systems
  ([package-repository-key-rotation-1.3.1.md](../package-repository-key-rotation-1.3.1.md)); getting-started
  says no in-place upgrade from 1.1.1 is qualified. There is no in-band key or certificate update.
- **No upgrade QA for the 1.4 line.** The 1.4.1 notes list "image-based upgrade and rollback" as not done
  ([release-1.4.1.md](../release-1.4.1.md#upgrading)); 1.4.1 "still requires a coordinated base, kernel and
  driver upgrade" from 1.4.0. The installed laptops were reinstalled from the image. The 1.4 coverage ledger
  carries upgrade and rollback as open rows ([A11](1.4-coverage-ledger.md)).

The 1.5.0 reality: 1.5.0 uses the same snapshot as 1.4.1 (daemonarchy-src `303b364`, OSVERSION `1600029`)
but ships a rebuilt `if_brcmfmac-kmod` and a re-signed boot bundle. In principle that is a same-snapshot
maintenance (stage the bundle, upgrade the locked module package in that environment, activate). It has not
been exercised on a 1.4.1 install and is not documented as supported, so a 1.4.1 system gets the Wi-Fi fix
reliably only by installing the 1.5.0 image. The `pkg upgrade` part of 1.5.0 (applications such as
Aquamarine, Windows programs, `daemonarchy-pkg`) does reach an installed system.

## B. The evidence

Parameterised already: `pkg-repo.sh` (`GH_REPO`, `KEY`, `TAG`, `BUILD_HOST`; `keygen` makes the key,
HACKING "The signing key is ... Make it once with `pkg-repo.sh keygen`"), `scripts/package-feed-stage.py`
and `scripts/package-feed-upload.py` (`--repo`), and `build-iso.sh` (`PACKAGE_REPOSITORY_PUBLIC_KEY`,
`PACKAGE_REPOSITORY_TAG`, `NAME`).

Hard-coded to `jordanhubbard/*` (checked with `git grep`):

- the installer: `overlay/usr/local/libexec/daemonarchy-installer/install` (feed URL, line 753; checkout URL
  pattern, line 773) and `package-repository` (lines 52 and 90) validate the feed URL against
  `https://github.com/jordanhubbard/daemonarchy/releases/download/...`; `build-iso.sh` lines 102 and 146;
  `test-qemu.sh` line 333;
- `overlay/usr/local/share/daemonarchy-installer/checkouts.json` (feed and the `daemonarchy-src` and
  `daemonarchy-ports` remotes) and `extensions.json` (the repository of the extension feed);
- `scripts/release-current.py`, `scripts/verify-release-assets.py` and `scripts/package-feed-*.py` defaults;
  `daemonarchy-cudalab`'s `repo_url`;
- the ports: `x11-wm/daemonarchy` fetches `jordanhubbard/daemonarchy-desktop` and `ports-mgmt/daemonarchy-pkg`
  fetches `jordanhubbard/daemonarchy` at pinned commits (daemonarchy-ports `main`);
- the Secure Boot chain: the project certificate and bundle signing are ours, and `maintenance.py` knows only
  our source commits.

Also: the pinned public key is a committed file shipped in the image; there is no fork guide (the only
`fork` text in the docs concerns the ports and source forks we own); the builder needs FreeBSD 16.0-CURRENT with
poudriere, snapshot jails and, for a release, build hosts for both architectures and a signing window.
Default build hosts and key paths in the scripts are our own. What breaks in a fork that changes only the
repository name: the installer refuses its own feed URL, the image points at our feeds and checkouts, and
`verify-release-assets.py` checks our repository.

## What 1.5.1 will change

NETUP-001 (base, kernel, modules and boot-file upgrade with boot-environment rollback), NETUP-002 (key and
certificate rotation over the network), NETUP-003 (upgrade QA on exact artifacts) and FORK-001
(one configuration, a fork guide and an example fork CI), plus the goals deferred from 1.5.0 below. Their acceptance texts are in the queue. Until they
have evidence, [the upgrade model](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#the-upgrade-model-today) is the statement of what works.

## Unfinished 1.5.0 acceptance

The [published 1.5.0 notes](../release-1.5.0.md#what-is-not-done-and-why)
identify these concrete gaps. Their original 1.5.0 target is historical; the
active queue and release-goal ledger now assign remaining acceptance to 1.5.1.

| Queue item | What 1.5.0 delivered | What 1.5.1 must prove |
| --- | --- | --- |
| GUI-001 | Packaged first GTK manager; OctoPkg remains the menu choice. | Real installed desktop install, update and remove; plan identity, progress, retry and failure behavior. |
| DEBUG-003 | Trace and VM foundations. | Loader, forced `mountroot>` and panic control with exact native/physical evidence, including the MSI NIC and reset capture. |
| HW-004 | T2 transport and package development. | An enrolled-finger Mac test through fprintd, login, sudo, SDDM and hyprlock, plus resume and T2 power loss. |
| EXT-002 | Lua runtime and fish-tank source. | Exact-image sandbox refusal tests, published feed, authoring guide and play on the actual console. |
| DESKTOP-001 | Launchers still came from the installer overlay. | Package ownership, matching menu entries, fresh-install behavior and delivery of a launcher change through `pkg upgrade`. |
| SIGN-001 | The process rule was documented. | Freeze inputs, sign once and retain the operator command count and wall-clock time in the 1.5.1 release record. The 1.5.0 record lacks those measurements, so its one-session acceptance cannot be inferred from the notes. |

The native halves of ADOPT-002, SRC-001 and RELEASE-001 already have the
ADOPT-003, SRC-002 and RELEASE-002 queue items below. Those items must also
resolve the unticked 1.5.0 source-controller evidence and release-gate checks
with exact records; publication alone did not turn those boxes into passes.
The other limits in the 1.5.0 notes retain their existing owners: [HW-001](active-work.md#hw-001-close-remaining-physical-hardware-qualification-gaps)
for the RTX Spark boot failure, final-image MSI/MacBook runs and Wi-Fi retest;
[NET-001](active-work.md#net-001-make-the-installer-network-bring-up-proactive-and-robust)
for the exact-image network matrix; and [NETUP-003](active-work.md#netup-003-qualify-upgrade-paths-on-exact-artifacts)
for image-based upgrade and rollback. Windows/Steam real-desktop and Aquamarine
hotplug/resume checks remain physical acceptance under HW-001. The channel-1
MacBook Wi-Fi handshake remains a distinct unresolved case under HW-001.

## Installer fix: a failed installation explains itself (issue #257)

A failed installation no longer drops to a bare shell after `[exited]`. The
installer's own exit status decides the outcome, so a progress warning is
reported beside a successful result instead of turning it into a failure. The
failure card waits for a key, and `install-failed` then shows the end of the
install log, the last recorded stage, the log locations and a menu (view the
log, shell, reboot, power off). Unattended CIDATA installs keep their
behavior and never wait. See [When the installation fails](../installer-progress.md#when-the-installation-fails).
Evidence: `tests/install-failed.sh` and `tests/installer-progress.py` on Linux
with tmux. Exact-image and hardware runs are pending.

## Deferred from 1.5.0 (operator decision, 2026-11-03)

1.5.0 was re-scoped to what is real ([plan](release-1.5.0.md)). Every goal below needs the Literate AI
framework to execute native components, and the latest framework release is v1.3.1 (1.4.0 does not exist),
so none can be done on the released runtime. Each moved with its acceptance text and evidence unchanged;
nothing was ticked in the move. Evidence is counted as ticked boxes over all implementation and evidence
boxes of the queue item as of the move.

| Item | Evidence state | Notes |
|---|---|---|
| [BUILD-001](active-work.md#build-001-cut-freebsd-source-ports-iso-and-release-cycle-time-10x-with-literate-ai) | 0 of 5 | Baselines, the Literate AI 1.4 upgrade of three repositories, per-stage mechanisms, the 10x end-to-end measurement. |
| [COMP-001](active-work.md#comp-001-model-complete-freebsd-source-and-ports-trees-as-components) | 4 of 11 | Diagnostic inventories and first original-source authority only; zero admitted units. Blocked on framework #74, #93, #234, #235. |
| [PERF-001](active-work.md#perf-001-execute-native-components-and-substantially-accelerate-iso-builds) | 0 of 6 | A retained 1.4.1 hand-pipeline baseline exists under `verification/build-baselines/`; no box is ticked. Was carried from 1.4.1 with no release target. |
| [PERF-002](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140) | 0 of 11 | Not started. Blocked on framework #4, #5, #235, #236, #67. |
| [DEV-001](active-work.md#dev-001-provide-an-operator-ready-native-component-development-system) | 5 of 12 | Disposable QEMU worker and installed-CLI checkpoints; operator-ready system not delivered. |
| [ADOPT-003](active-work.md#adopt-003-qualify-retained-native-execution-and-release-enforcement-deferred-half-of-adopt-002) | 0 of 3 | The native half of ADOPT-002 (bind the real target, qualify receipts). The audit box of ADOPT-002 stays ticked in 1.5.0. |
| [SRC-002](active-work.md#src-002-qualify-native-freebsd-source-builds-and-packages-deferred-half-of-src-001) | 0 of 4 | The native half of SRC-001: end-to-end qualification, first baseline build, VM boot and signing. The two controller boxes stay ticked in 1.5.0. |
| [RELEASE-002](active-work.md#release-002-run-a-release-entirely-through-qualified-literate-ai-execution-deferred-rest-of-release-001) | 0 of 2 | Upstream FreeBSD platform support, a release run entirely through Literate AI, and the full inherited backlog. |

The RTX Spark laptop is also deferred (not a queue item; see the
[application note](../application-note-rtx-spark.md)).

Three new queue items follow in the queue with no 1.5.x commitment (target after 1.5, proposed 1.6.0, not
scheduled): [TREE-001](active-work.md#tree-001-browse-usrsrc-and-usrports-on-the-system-as-nested-html-cards),
[MON-001](active-work.md#mon-001-worker-activity-monitor-and-graphical-package-browser-on-the-installer-visual-sdk)
and [LITAI-PKG-001](active-work.md#litai-pkg-001-ship-literate-ai-as-a-port-and-package-so-users-run-srcports-operations-with-litai).

## Build speed and framework-executed goals deferred from 1.5.0

The sections below were the build-efficiency half of the 1.5.0 plan and are moved here verbatim (a "1.5.0"
in them means the release these goals were originally gated to). They are the open acceptance of BUILD-001
and the items above, not new claims.

### Build efficiency: not delivered under the 1.4.2 name

The 1.4.2 (now 1.5.0) queue items ADOPT-002, RELEASE-001, COMP-001, PERF-002, DEV-001 and SRC-001 were kept
open by operator decision and were not run natively under Literate AI. 1.4.2 therefore made no
build-efficiency claim: its builds used the hand pipeline of 1.4.1. The 1.4.2 work that touched
this area was preparatory only (documentation authority gate, release policy and gate for 1.4.x,
a registered FreeBSD worker, and written native adoption steps), and the retained native receipt
(`verification/current.json`) still does not exist.

### Baselines (recorded first, with where measured)

No target below is meaningful until its baseline is retained in `verification/build-baselines/`
with host, revision, vCPU, memory, clean or incremental, run count and the command. What exists
today, and what does not:

| Stage | Measured today | Where and how | Gap |
|---|---|---|---|
| `buildworld` | 7,931 s (clean, `-j4`) | Owned KVM FreeBSD guest, 8 vCPU, 16 GiB; see the DEV-001 source SDK baseline in [active-work.md](active-work.md#dev-001-provide-an-operator-ready-native-component-development-system) | One run; 874 to 878 s incremental on 8 cores (retained object tree) in the 1.4.1 record |
| `buildkernel` | 600 s (clean, same guest); 622 s incremental | same, and [the 1.4.1 pipeline record](../../verification/build-baselines/rev2-1.4.1-pipeline-20261030.json) | One run each |
| Full native producer (world, kernel, packages, sets) | 9,357 to 9,358 s, 537 artifacts | same 8 vCPU/16 GiB KVM guest | One run |
| 1.4.1 hand pipeline (incremental) | 3,518 s total (world 878, kernel 622, sets 601, jail 154, Secure Boot 314 + 442 + 62, checkouts 387) | daemon.local (retired), 8 cores, `-j8`, retained object tree | One run; not clean; host retired |
| ISO mastering (`build-iso.sh`), amd64 | 1,583 s and 1,601 s (two builds) | same pipeline record, `separate_phases` | Two builds; no per-arch repeat |
| ISO mastering, aarch64 | Not extracted | An aarch64 bulk and ISO record exists ([verification](../../verification/aarch64-bulk-iso-20261027-development.json)) | Needs a repeatable per-arch measurement on barmy |
| Full ports bulk for our origin set | No repeatable clean wall-clock retained | Earlier bulk attempts are described in the queue; the 1.4.1 and 1.4.2 package sets were built by hand pipelines | Measure a clean and an unchanged-input bulk per arch |
| End-to-end release cycle, "main frozen" to "published and verified" | Partial: 1.4.1 tag created 2026-10-31 04:03 UTC and published (non-draft) 06:08 UTC, about 2 h 5 min; 1.4.0 published 2026-10-29 20:28 UTC, so 1.4.0 to 1.4.1 publication is about 33 h 40 min including the re-roll | GitHub release timestamps | The freeze instant is not recorded for 1.4.1; 1.4.2 is not published at the time of writing |

Task 1 of the plan retains the missing rows, and a release rehearsal records the freeze time,
every stage's start and end (the existing `scripts/build-timing-record.py` format) and the
publication verification time. A stage with no measurement keeps the words "not measured".

### Targets and mechanisms

The headline target is the end-to-end cycle, "main frozen" to "published and verified", at least
10x shorter than the baseline measured for 1.4.2 or the later rehearsal, on equivalent gates:
the same tests, signatures, ISO boot and install checks, feed verification and byte re-download.
Per-stage targets are set when the baselines exist, and each names the mechanism and the item
that owns it:

| Stage | Mechanism | Owning item |
|---|---|---|
| World, kernel, sets | Literate AI native Components with an exact-input verified cache: unchanged inputs compile nothing; a changed input rebuilds only its closure. Incremental native builds on workers with bounded jobs | SRC-001, COMP-001 (framework [#74](https://github.com/jordanhubbard/literate-ai/issues/74), [#93](https://github.com/jordanhubbard/literate-ai/issues/93)) |
| Ports and packages | Package builds keyed by source subtree, port metadata, toolchain and ABI; compatible base version changes requalify and reuse unchanged payloads | PERF-002, COMP-001 |
| ISO mastering | Cached sets and package closure inputs, parallel per-arch builds on separate workers, scripted rather than manual mastering | PERF-001, PERF-002 |
| Distribution across machines | Literate AI workers on more than one physical machine sharing a verified immutable cache; duplicate-key and failure controls | PERF-002 |
| Development loop | Operator workstation `litai-dev` interface over the same Components | DEV-001 |
| Signing and key windows | Scripted key windows with the same custody rules; the key is never copied to workers or artifacts | RELEASE-001 |
| QA | Parallel amd64 and aarch64 install, boot and feed checks from one plan, instead of sequential manual runs | RELEASE-001, PERF-002 |
| Release state and gates | `litai release` plan, check and publish driven by the 1.4.x gate (this repository's release gate, not the 1.4 framework), replacing hand steps | RELEASE-001 |

These mechanisms are the open acceptance of the listed items, not new claims. A 10x figure is not
credible if it comes from skipping a test, a package or a signature; the evidence says so.

### Literate AI upgrade to 1.4 in all Daemonarchy repositories (prepared, not applied)

Today the runtime in use is litai 1.3.1 (tag `v1.3.1`), with framework main (1.4.0 development) built
side by side at `~/daemonarchy-framework-main-runtime` for read-only plans. "1.4 (top of tree)" means the
framework 1.4.0 revision recorded when the upgrade is applied. Nothing is applied before 1.4.0.
The Daemonarchy repositories and their state on 2026-10-31 (three carry `literate.project.json`):

| Repository | `literate.project.json` | Project version | Notes |
|---|---|---|---|
| daemonarchy | yes | 1.4.1 | Standard binding to framework distribution 8b9c09fd; release policy and 1.4.x gate in place |
| daemonarchy-src | yes | 1.2.0 | Standard lifecycle binding present; older project version |
| daemonarchy-ports | yes | 1.2.0 | Standard lifecycle binding present; older project version |
| daemonarchy-desktop | yes (added 2026-11-01, scaffolded with framework main) | 1.4.1 | In scope, not subsumed: see below |

### daemonarchy-desktop: in scope, not subsumed

Checked on 2026-10-31. The repository is still applicable and is not folded into daemonarchy-ports or daemonarchy-src:

- The port `x11-wm/daemonarchy` in daemonarchy-ports builds from it (`USE_GITHUB`, `GH_ACCOUNT=jordanhubbard`, `GH_PROJECT=daemonarchy-desktop`, `GH_TAGNAME` pinned to commit `ec2a00824ec9`) and installs its wallpaper, SDDM theme, menu (`omarchy-menu.jsonc`), icons and the `daemonarchy-*` FreeBSD tools. The ports tree holds only the packaging, not these sources.
- It is active (a commit on `main` on 2026-10-31, and open PR 1, which makes the Packages menu open daemonarchy-pkg) and not archived. Its last tag is v1.1.1, so tags and the port's pin are not aligned today.

So it gets a project binding: a `literate.project.json` with the Standard lifecycle, a release policy suited to a small source repository (version and tag convention to be decided with the operator, including whether the port pin follows a tag), and the same `litai verify` qualification as the other three. It would be excluded only if a later change moved its sources into daemonarchy-ports or daemonarchy-src; this item records that this has not happened.

### Out of scope

Scope is exactly daemonarchy, daemonarchy-src, daemonarchy-ports and daemonarchy-desktop. The other repositories under the owner that carry a `literate.project.json` (Aviation, ElixirSSI, project-tracker, bookscan, freebsd-sentiment, LeRTX, and the Literate AI framework with its labs) are unrelated to Daemonarchy and are out of scope. Nothing in this plan changes them.

For each repository, the upgrade is: review the Standard rebind plan
(`litai project lifecycle rebind-standard`, plan only until 1.4.0), apply it only with the reviewed plan and
explicit authorization, add the release-goal manifest that framework 1.4 requires
(`contributions.roadmap_goal_manifest`, with a `Release target:` line on each queue heading and every
included goal checked off), then run `litai verify` and the repository's own tests. The rebind changes
lifecycle and receipt-policy authority, so each is an operator-approved change, and native receipts made on 1.3.x
are not carried over (see [the upgrade sequence](../native-adoption-steps.md#the-literate-ai-14-move-prepared-not-applied)).
daemonarchy's `authority-reviewed` marker is recorded by a human after review.

### Framework issues for the 1.4.0 gaps

The gaps found while preparing ADOPT-002, COMP-001, PERF-002, DEV-001 and SRC-001 are framework work, done in the
framework project and not in this repository. Opened or already open, as of 2026-11-01 (milestones as the framework
labels them):

| Issue | Gap | Milestone | Items it blocks |
|---|---|---|---|
| [#74](https://github.com/jordanhubbard/literate-ai/issues/74) | Complete retained native trees as canonical Component catalogs | 1.4.0 | COMP-001 |
| [#93](https://github.com/jordanhubbard/literate-ai/issues/93) | Internal aliases through native SDK product admission | 1.4.0 | COMP-001 |
| [#234](https://github.com/jordanhubbard/literate-ai/issues/234) | Catalog and pinned-input ceilings at src and ports scale (about 1,000 units) | 1.4 | COMP-001 |
| [#235](https://github.com/jordanhubbard/literate-ai/issues/235) | Per-unit link-aware native packages and tree-aware worker transport | 1.4 | COMP-001, DEV-001, PERF-002 |
| [#236](https://github.com/jordanhubbard/literate-ai/issues/236) | Cache keying for FreeBSD native units across two physical FreeBSD workers | 1.4 | PERF-002 |
| [#4](https://github.com/jordanhubbard/literate-ai/issues/4) | Production action DAG dispatch and shared LAN caches | 1.4.0 | PERF-002 |
| [#5](https://github.com/jordanhubbard/literate-ai/issues/5) | Native package construction and verification on compatible remote workers | 1.4.0 | PERF-002, SRC-001 |
| [#67](https://github.com/jordanhubbard/literate-ai/issues/67) | First-class FreeBSD worker, target and native lifecycle support | 1.4.0 | ADOPT-002, DEV-001 |

The framework has two milestones, `1.4` (4 open issues) and `1.4.0` (53 open issues); the first three-issue batch (#234 to
#236) carries `1.4` while the older issues carry `1.4.0`. Which of the two the framework treats as the 1.4.0 release scope is the
framework project's call; this plan follows whichever it names. The "Items it blocks" column is this repository's reading of each issue,
not the framework's statement.

