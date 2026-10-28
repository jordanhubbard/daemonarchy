# Active work

[PROJECT.md](https://github.com/jordanhubbard/daemonarchy/blob/main/PROJECT.md) owns product goals and completeness.
Checkboxes below are execution status, not substitutes for test receipts.

## 1.3.1 release execution, 2026-10-24

All previously open Daemonarchy product, source, and ports pull requests are
merged into their respective `main` branches. The [current GitHub branch audit](../../verification/branch-merge-audit-1.3.1-development.json)
finds all 76 non-main branch heads ancestral to `main` across those three
repositories and no open PRs in any of the five Daemonarchy repositories.
The [earlier landing inventory](../../verification/contribution-inventory-1.3.1-development.json)
retains review-head details; a formal release contribution sweep is still
required. Retained worktrees and development evidence remain available.

Source `main` at `d63d77f4` includes the MacBook and early-network work plus
FreeBSD CURRENT through `a3d1d4e8`. Its exact native world, kernel and release
set builds passed. Ports `main` at `b7857842` contains all fork branch
histories and adds a Broadcom SDPCM event BSSID fix verified by native
Poudriere testport to the earlier `7e417dae` tree. The selected official
package snapshot does not include the newest
upstream ports changes; [the refresh record](../../verification/freebsd-current-refresh-20261024-development.json)
explains the dependency and conflict review. The `1600029` jail bulk on madmax
is in progress, with failed earlier attempts retained for audit. Keep all
source, ports, checkout and package revisions pinned through the final image
run. Product `main` at `33ff0108`
contains merged release notes, policy and the hardware-record identity fix.
The ISO worker and public feed controllers use a separate clean product
checkout pinned to `cdeb3434`; the final tag can include the later release
documentation while the physical test record identifies the ISO source.

The [earlier checkout development record](../../verification/checkout-catalog-1.3.1-final-development.json)
binds signed source and ports seed packages to the then-selected `main` heads,
including ports `7e417dae`. An isolated native `pkg` client authenticated and
installed those three packages, rejected the old key, and materialized both
exact shallow Git trees. The
[initial versioned checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-amd64-1.3.1)
is public with 11 verified assets for the earlier ports pin. The
[replacement feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-amd64-1.3.1-r2)
selects `b7857842` with 11 matching public asset digests, and a native FreeBSD
`pkg` client authenticated its public catalogue. The
desktop source is pinned to `ec2a0082` until qualification permits a stable
`v1.3.1` tag.

The operator confirmed on October 24 that all pre-production checks passed on
the Intel 16-inch MacBook Pro and waived only an additional physical acceptance
rerun against the final public 1.3.1 ISO. The earlier 1.1.1 S3 and debugger
observations remain historical results for that image, not current release
blockers. No final-ISO physical boot or hardware-rooted T2 attestation is
claimed. See the [scoped decision](../../verification/macbook-release-decision-1.3.1.json)
and [acceptance record](../testing-macbookpro16-1-1.3.1.md). At this October 24
checkpoint, the new image had not yet been assembled. `daemon.local` was
selected as the independent final-ISO bhyve installation and boot test target.
The new package signing key has a separately
held encrypted recovery copy with a verified restore. The production boot signing
key and certificate are staged on the native worker with root-only access;
the final signed bundle was pending at this checkpoint. The signed application
feed, public ISO, retained native build evidence, artifact integrity and
publication checks are release gates whose final outcome belongs to the public
release record. The MSI early kernel boot remains unqualified and is not
claimed by the MacBook release notes.

`litai verify` currently fails its declared receipt gate because
`verification/current.json` is absent. The 1.3.1 release gate separately checks
current LitAI authority and locks, then requires a hashed native build record,
signed artifacts, image identity and the scoped MacBook release decision. That native
record binds actual source, ports, signing and ISO results without asserting a
passing LitAI lifecycle receipt. Issues #11 and #39 have explicit 1.3.1
deferrals and 1.4.0 milestones; the complete LitAI release graph remains open.
No historical log is a substitute for a current native result or LitAI receipt.
The dated development entries below retain the status observed at their own
artifact revisions. The October 24 operator confirmation supersedes their
then-open MacBook physical checks as a 1.3.1 publication gate; it does not
rewrite those observations as tests of the final ISO.

### [x] ADOPT-001 — Establish product-wide Literate AI authority

- **Priority:** P1
- **Owner:** project requirements and Component contracts
- **Direction:** Adopt Literate AI across the whole Daemonarchy product in stages while retaining source, native tests and release history.
- **Conclusion:** Author in-place project goals, logical Component contracts and acceptance mapping; automatic quarantine conversion is blocked-no-driver and is not applied.
- **Depends on:** none
- **Implementation:**
  - [x] Declare seven goals and eight Component contracts with public integration boundaries.
  - [x] Map every retained test file, external repository selections and published 1.1.1 assets.
  - [x] Reconcile root guidance, documentation reachability and the feature overview.
- **Evidence:**
  - [x] `litai project validate .` passes; eight `host` contract locks are current.
  - [x] Root and retained-boundaries skills pass static schema/security/license/quality evaluation.
  - [x] All 119 original non-Markdown files except the deliberately updated ignore policy retain their original bytes and executable modes.
  - [x] `litai verify` reports authority/locks passing and the expected missing native receipt; no acceptance is fabricated.
  - [x] [Adoption PR #10](https://github.com/jordanhubbard/daemonarchy/pull/10) security check passed on c517c4c; the final closure commit must pass again before merge.

Evidence: `verification/adoption-checks.json`. Native execution and release enforcement belong to ADOPT-002, not this completed-authority scope.

### [ ] ADOPT-002 — Qualify retained native execution and release enforcement

- **Priority:** P1
- **Owner:** native lifecycle integration and framework boundary
- **Direction:** Integrate existing FreeBSD build, test, signing and release procedures without transferring source authority.
- **Conclusion:** Do not enable framework execution or publication until exact mixed source/assets, worker/toolchain, privileged cleanup, artifact custody and current receipt paths are demonstrated; the installed candidate provides the retained handler, while the actual product profile and native acceptance remain unfinished.
- **Depends on:** ADOPT-001
- **Implementation:**
  - [x] Audit the retained execution handler on current framework main and reconcile [framework issue #22](https://github.com/jordanhubbard/literate-ai/issues/22): the issue was reopened because authorized execution still unconditionally refuses. Actual execution qualification remains open below.
  - [ ] Bind the actual FreeBSD target, action inventory, external inputs, privileged cleanup and protected signer.
  - [ ] Qualify current native receipts, artifact custody and release enforcement.

Next action: bind the actual source/ports compiler, sysroot, input closure and
native action inventory to executable retained profiles and earn installed native
admission. The [first-binding checkpoint](../../verification/standard-first-binding-development.json)
now records an exact reviewed Standard configuration apply on the controller using
qualified framework `73311c69`; all seven existing receipt requirements, 43 historical
evidence files, the default CLI and active workspace selection are preserved. The
same plan identity passed five real installed CLI operations on a disposable
FreeBSD product copy, and all 13 installed contract cases pass. At that
checkpoint, [framework PR #108](https://github.com/jordanhubbard/literate-ai/pull/108)
was a draft; it was subsequently consolidated into merged PR #110. Its isolated
CLI established lifecycle planning only. This binding is not native execution,
SDK/pkg/ISO admission or release
qualification. Current authority and all eight host contract locks pass after an explicit lock/audit refresh; the configured project receipt remains missing. A read-only retained-harness plan now reports
`retained_harness.not_adopted`; this first-binding wheel does not expose
`project adopt-original`. The next candidate combined this repair with
in-place native admission from [framework PR #87](https://github.com/jordanhubbard/literate-ai/pull/87),
then author/admit the actual product profiles. The combined `e90cbadb` candidate
now passes full controller regression (2,035 passes, 70 skips, no failures), clean
wheel qualification, 18 installed FreeBSD binding cases and real installed
controller/FreeBSD binding plus metadata-only original-adoption probes. The
[combined checkpoint](../../verification/native-first-binding-integration-development.json)
preserves the first probe's documentation-review refusal and its corrected result.
The reviewed Standard rebind is now applied: only the driver changes, with all
seven receipt requirements, 44 evidence files and the default CLI preserved.
Current authority and all eight host contract locks pass with the new binding;
full verification still reports the missing native receipt. No lock mutation was
needed. The public reviewed original-adoption plan is now applied at source
revision `dbd3420`: all 272 tracked source entries preserve their bytes/modes;
only original-adoption evidence, authority metadata and its runtime mutex are
added. The mutex is explicitly ignored afterward; authored authority JSON remains
tracked. [Framework PR #109](https://github.com/jordanhubbard/literate-ai/pull/109)
retained the combined candidate at that checkpoint; it was later consolidated
into PR #110.

Next author the real FreeBSD source/binary/toolchain action inventory as a complete
retained manifest/profile and use the public `build`/`test --retained-project`
route. The legacy `project retained-harness readmit` command now reports missing
`.literate/legacy-lift-shift.json`; it is not an original-project initializer and
no legacy conversion metadata will be synthesized. Metadata-only original
adoption does not grant execution or acceptance; the native lifecycle receipt
remains missing. A separate original-source loader test ISO now passes native
payload/runtime audits and disposable UEFI installation/reboot; see TESTISO-001.
Preserve original source placement and earn lifecycle admission.

The [SDK runtime candidate](../../verification/native-sdk-public-development.json)
now has a separate [framework contribution #110](https://github.com/jordanhubbard/literate-ai/pull/110).
That contribution merged on October 23 with its hosted matrix passing.
PRs #87, #108 and #109 were closed as superseded by it. On October 24 the
controller's clean framework checkout was fast-forwarded to `d17881fa0`, but
its installed `litai` still reports `90d5b6e9`. The Daemonarchy project still
selects its earlier framework distribution identity, and `litai verify` still
fails the configured native receipt gate. An exact installed candidate and real
FreeBSD retained profile must be qualified before changing that authority.
Exact code `f65e0c62` passes 2,046 controller tests with 70 skips and no failures,
clean wheel qualification and offline FreeBSD installation of 37 distributions.
Its source fixtures supply project discovery and local Git routing; installed
native fixture checks ended at their 1,800-second deadline after nine observed
passes; the 40-case batch is incomplete. A separate real SSH source acquisition and
capture check passes without routing mocks. A real canonical project now passes
installed FreeBSD CLI validation with its 16-kind default receipt policy preserved;
canonical build/test acceptance remains open. These preparation checks do not
admit the actual compiler/sysroot, product lifecycle or ISO. Next bind the complete
actual retained profiles and earn native admission; all 24 release rows remain open.

A subsequent real installed FreeBSD/KVM attempt now completes native library-SDK
production, project validation, reviewed original-source adoption and retained
planning with the default 16-kind receipt policy preserved. Separate checks refuse
missing host-execution acknowledgement and missing exact retained-plan
authorization. Earlier authored capability, ignored-output and unsorted-case
refusals remain retained; their corrections do not relax the framework guards.
The supervised preparation and execution attempt ended after 951.990 seconds with
`retained_project.execution_failed`: the SDK command scope rejects an import or
loader override. The retained runner projects `LD_LIBRARY_PATH` from its reviewed
captured runtime directory, while the SDK scope rejects that key unconditionally;
that installed candidate retained both behaviors.
[Framework issue #118](https://github.com/jordanhubbard/literate-ai/issues/118)
owns their fail-closed composition. The subsequent repair binds the complete
captured loader projection to live dependency and command owners, preserving
ambient-injection, shadowing, drift and revocation refusal. Exact code `4eab5e25`
passes all 2,198 controller cases (2,128 passes, 70 declared skips), its clean
wheel qualification and the complete 223-test framework host lifecycle with
independent acceptance and a current framework receipt. Published review head
`cb648dc9` has the same source/test trees; its exact CI remains pending. Offline
FreeBSD installation verifies all 37 distributions. Ten installed context cases
and a fresh canonical native CLI replay are now terminal. All ten installed
context cases pass with 469 production modules verified from the installed prefix.
The real public CLI replay passes native SDK production, original-source adoption,
retained planning and both separate authorization refusals, then times out during
authorized execution at its unchanged 3,600-second deadline. Partial compiled
products and three original test results do not establish a completed receipt or
independent admission. Framework issue #117 owns the performance repair.
The [renewal checkpoint](../../verification/native-sdk-runtime-context-development.json)
keeps that preparation separate from unearned consumer, compiler/sysroot, product
and release admission. All 24 release obligations remain open.

A separate successful read-only plan under cProfile took 68.762 seconds and
recorded 41,930 stat calls plus four installed-distribution observations. This is
diagnostic evidence with profiling overhead, not a release performance benchmark.
[Framework issue #117](https://github.com/jordanhubbard/literate-ai/issues/117)
owns bounded observation/revalidation work with tamper and revocation guards
preserved. No performance fix or lifecycle pass is claimed.

The [current-framework preparation record](../../verification/framework-c345e652-native-preparation.json)
binds clean framework source `c345e652`, an exact wheel and seven passing
Linux ARM64 captured-runtime cases. The wheel copy has the same SHA-256 on the
FreeBSD build host, but an isolated no-dependency install cannot start the CLI
because `referencing` is absent. It is neither a complete dependency install
nor a native product receipt. Install from an exact FreeBSD dependency closure,
then run the real public retained build and test path before updating product
lifecycle authority.

- **Evidence:**
  - [ ] Actual installed CLI accepts retained native execution; source and binary invalidation works; native tests and artifact hashes are current; failed or omitted evidence blocks publication; existing release workflow is reproduced.

### [ ] UI-001 — Deliver measured retro installer visualizers

- **Release:** 1.4.0 headline feature; [A15 in the 1.4 ledger](1.4-coverage-ledger.md#acceptance-rows).
- **Priority:** P1 (raised from P2 on 2026-10-26 by operator direction)
- **Owner:** installer and desktop Components
- **Direction:** Use colorful Winamp-inspired ANSI animation to show useful installation stage, disk, package and network activity.
- **Operator direction (2026-10-26, Jordan Hubbard, owner):** A real MacBookPro16,1 installation of 1.3.1 gave almost no visible progress: the screen said the installation was still running and then showed nothing until it ended. The retained log stops while pkg extracted package 976 of 1188. For 1.4 the install screen must give "dazzling and impressive visuals" and is a headline feature, while staying truthful: never invent a completion percentage. The screen must be continuously alive with real activity in every stage (disk throughput and IOPS, network, per-core CPU, memory, ZFS/GELI where cheap), show a stage timeline with elapsed time per stage, scroll the package names pkg reports with count/total, and draw a spectrum and scope from real I/O rates with 256-color gradients, the Daemonarchy logo and smooth animation at bounded CPU. Plain mode, reduced motion, small terminals, 16-color/VT100 fallback, serial/SSH output and resize must keep working; the FreeBSD vt(4) console is the primary target. The graphical installer (LIVE-001) must show the same stages and metrics from one producer.
- **Operator direction, laptops without function keys (2026-10-26):** The Touch Bar MacBookPro16,1 has no physical F-keys, so it cannot switch vt(4) consoles with Alt+F1–F8; this is common on laptops. Nothing a user needs may depend on F-keys or console switching: the log, diagnostics and a shell must be reachable from the install screen while the installation keeps running, console-approved remote debugging must keep running from the configurator through the installation (the operator had to leave the listener to start the install, which ended SSH observation), and instructions that rely on Alt+F2 or similar need a non-F-key path. The operator then chose tmux's model and default keys for this: windows and panes, a status line listing windows, the `Ctrl-b` prefix, `%` `"` `o` arrows `x` `z` `c` `n` `p` `0-9` `&` `w` `[` `?`, `d` that never detaches or kills, `C-b C-b` for a literal prefix, `exit` closing a shell pane; window 0 is the progress view and cannot be closed while installing; small terminals are zoom-only; plain/serial mode keeps line output.
- **Operator direction, charm and sound (2026-10-27, Jordan Hubbard, owner):** "We want a lot of pizazz — Daemonarchy 1.4 needs to be a lot more charming and interesting to watch through all phases of installation and also be willing to use sounds liberally", and "animations should make noise". Every phase gets charm while staying truthful: the loader splash, the configurator's screens, network bring-up, the firmware step, the disk confirmation, each install stage, completion, the first boot and the live desktop. Transitions, an animated banner and mascot, stage-change flourishes, a celebratory completion and attract-mode animation only where the wait is genuine; graceful fallbacks keep the 16-color, serial/plain and reduced-motion paths. Sounds are tied to real events (stage start and finish, package milestones with a ticker blip, network results, the disk-commit warning, errors, the completion fanfare, a boot chime), with an optional ambient/chiptune layer driven by the same measured rates as the spectrum. Sounds are generated procedurally (no third-party samples) and played through FreeBSD OSS without blocking; the image loads the sound drivers. Controls: an on-screen mute/volume indicator, `C-b m` and `C-b +`/`C-b -` (listed in `C-b ?`), a configurator option and a loader default (`daemonarchy.sound=on|off|quiet`). Silence is automatic on serial/headless consoles, in unattended CIDATA installs unless requested, and without an audio device; a sound failure never affects the install. The graphical installer plays the same sounds from the same event stream. UEFI has no reliable audio, so the loader gets visual charm only, in daemonarchy-src.
- **Conclusion:** Drive animation from actual progress while retaining plain output, diagnostics, reduced motion and terminal compatibility. Run the real tmux (already in the desktop package closure; about 4 MiB with libevent and utf8proc) as a locked-down session on the console and over SSH rather than reimplement a terminal multiplexer: it emulates shells correctly, maps colors to what the outer terminal declares (16 on vt(4)), and its copy mode and resize handling are mature. Serial-class terminals keep the direct screen without tmux.
- **Depends on:** none
- **Implementation:**
  - [ ] Prototype multiple styles from recorded events; implement stage-aware presentation; validate on physical console and SSH/serial.
  - **Implementation checkpoint:** [Draft PR #21](https://github.com/jordanhubbard/daemonarchy/pull/21) retains a dashboard that now reads bounded incremental observations and offers bars, spectrum and scope styles, pin/sequence-checked acquisition events, explicit waiting/failure, plain output, reduced motion and resize handling. Storage milestones and archive counts advance only after their native commands succeed; pkg download reports and processing positions remain distinct from verified transaction completion. Twelve controller and twelve native FreeBSD/PTY checks pass, including small terminals, 16/256 colors, signal cleanup and backlog drain. [Scoped evidence](../../verification/installer-progress-development.json) retains exact source hashes and limits; the intentional retained source baseline is refreshed.
  - **Recorded replay checkpoint:** A verbatim retained native pkg journal passes all three styles through real PTYs: 16 ordered events, eight archives and 29,831 verified bytes. Its input hash, journal hash and current retained imported database hash agree with the original signed acquisition result; replay produces no installer result. The expanded twelve-case controller and native suites pass, including rejection of backward package counts and changed totals. The existing controller workflow now triggers and runs these controls on renderer, installer hook and fixture changes. It does not perform a live fetch or installation.
  - **1.4 live install screen checkpoint:** `progress-model.py` is the one producer for the console screen and the graphical installer: stage timeline from `@@phase` and new `@@step NAME EPOCH` markers (partition, encrypt, pool now emit their own), `@@target` disk and pool, the pkg package ticker, and activity rates from kernel counters (`kern.cp_times`, `kern.devstat.all`, interface MIB, `vm.stats`, ARC, per-pool ZFS `nwritten`) without a subprocess per sample. The download stage, which had no measured meter in either installer on the LIVE-001 run (pkg prints only dots when not on a terminal; a 64-minute graphical install showed no fetch progress), now counts pkg's `Fetching NAME: ... done` lines against its package count and reports received bytes from pkg's event pipe (`pkg-events`, `@@fetch`). The screen draws a Winamp-style spectrum, a braille scope, exact activity lines, the measured counter and the logo, redraws only changed cells at up to 10 fps and backs off when drawing is slow. It runs as window 0 of a locked-down tmux session with tmux's default keys; splits and windows show the install log, diagnostics, remote debugging or a shell. Remote debugging can stay in the background from the configurator through the install, with console approval from the `C-b R` window or the installer menu. On vt(4) the screen uses its 16 colors and never 24-bit color, verified by feeding the real output (direct and through tmux) to sys/teken. A scrubbed real MacBook 1.3.1 log is the replay fixture. 36 controller cases (one native-only case skipped) pass on Linux and natively on FreeBSD 16 (Python 3.12, tmux 3.7c); as root the native real-pkg fetch case passes too, plus four native teken cases and the native background remote-debug and existing session tests. Recorded demos are in [docs/demos/installer-visuals](../demos/installer-visuals/README.md). [Development record](../../verification/installer-visuals-1.4-development.json).
  - **Charm and sound checkpoint (2026-10-27):** `progress-model.py` now derives an event stream from its observations (stage started and finished, packages reported with a milestone every 50, warning, acquisition failure, a genuine wait of 20 seconds without a report, the installer's result); the console screen and the graphical installer animate and sound only on those events. `sound.py` synthesizes 17 cues and an ambient chiptune layer (oscillators, noise and envelopes; no samples) and plays them through OSS from one per-user player process that front ends reach with non-blocking datagrams; it loads `snd_hda`/`snd_uaudio` with `kldload -n` when root, and the live image loads `snd_uaudio`. Modes are `on`, `quiet` (the moments that matter) and `off`; `daemonarchy.sound` in the loader environment, `DAEMONARCHY_SOUND`, a `sound=` answer in a CIDATA file and the configurator's new Sound option choose it; serial and headless consoles, unattended installs and missing devices are silent and the indicator says why. The install screen shows the state at the bottom right and in tmux's status line, takes `m`, `+`, `-` and `a` directly and `C-b m`, `C-b +`, `C-b -`, `C-b a` in tmux; it adds a curtain opening, stage cards, sparkles on finished stages, a milestone banner, a ticker note per package, a banner glint and logo drift whose speed is the measured activity, a mascot whose trident keeps time with it and who announces a genuine wait, and fireworks with a fanfare held four seconds (any key skips) only for a successful result. `charm.py` gives the configurator a boot chime with an idle logo and mascot animation on the welcome screen, typed-in screen titles with a whoosh, a sparkling mark and sound per network and firmware check (`nb_hook_result`), a pulsing disk-commit warning with a klaxon and a confirmation sound. The installed system gets `daemonarchy_greeting` (a boot chime, and on first boot an animated welcome; an 8 kHz raw fallback needs no Python) and `daemonarchy.sound` from the installer choice; the live desktop plays a greeting chime; the GTK installer plays the same cues through the same `Director`, adds mute and volume controls (muting, or a mode chosen in the session, becomes the installed `daemonarchy.sound` through the backend's `sound` answer) and CSS keyframe flashes for stage starts, the disk warning and the result. The loader splash is open [source PR #36](https://github.com/jordanhubbard/daemonarchy-src/pull/36) (`daemonarchy_splash=YES|static|NO`). 54 cases of `tests/installer-progress.py`, `tests/installer-charm.sh`, 21 of `tests/live-installer.py` and `tests/vt-console-colors.py` pass on Linux and natively on FreeBSD 16 (Python 3.12, tmux 3.7c); on FreeBSD 16 the player opened `/dev/dsp0` and sound(4) reported `userland -> feeder_root(s16le:1.0) -> feeder_rate(22050 -> 48000) -> feeder_matrix(1.0ch -> 2.0ch)` for it. Recorded demos with their audio tracks and previews of every sound are in [docs/demos/installer-visuals](../demos/installer-visuals/README.md) and [docs/demos/installer-sounds](../demos/installer-sounds/README.md). [Development record](../../verification/installer-charm-1.4-development.json). No image was built and nothing was heard on an exact image.
  - **live4 image checkpoint (2026-10-27, [record](../testing-1.4-live4-20261027.md)):** The first 1.4 image with our own kernel and loader (daemonarchy-src `74f81f1949d5`) and this charm code, unsigned. Under QEMU the vt installer started the player with an HDA device; from `ttyu0`, `sound status` was `off (serial console)` and no second player started. Nothing was heard, because the audio backend was null. **The loader splash never draws.** The loader's Lua has no `table` or `math` library, so `splash.lua` fails inside its `pcall`. The fix is on daemonarchy-src `fix/splash-loader-libs` and is not merged.
  - **Next action:** Build the 1.4 image with tmux in the live set, run a full installation on the physical vt(4) console (MacBookPro16,1 without F-keys, a 16:10 panel at terminus-b32) and in a bhyve VM with a serial console, record the screen and the timeline against the install log, and connect LIVE-001's GTK progress page to `InstallProgress`. On a machine with an audio device, record every phase's flourishes with their sound (and a serial, an unattended and a no-device run that stay silent), and review source PR #36 for the loader splash on a real loader console. UI-001 remains open.
- **Evidence:**
  - [ ] Useful readable metrics, genuine waiting/failure states, resize and reduced-motion behavior, bounded cost and native console demonstrations.
  - [ ] A full installation of the exact 1.4 image on the physical console, including the MacBookPro16,1 with no function keys, using only the tmux keys for the log, diagnostics, a shell and remote-debug approval.
  - [ ] The same stages and metrics in the graphical installer (LIVE-001) from `progress-model.py`.
  - [ ] Every phase's flourish and sound seen and heard on the exact 1.4 image with a real audio device (loader splash visual only), mute/volume/mode controls working, and serial, unattended and no-device runs silent with the install result unchanged ([A17](1.4-coverage-ledger.md#acceptance-rows)).

### [ ] PKG-001 — Implement the release package DAG and safe parallel transactions

- **Priority:** P1
- **Owner:** package-engine Component
- **Direction:** Plan the complete release package closure and pursue parallel download and leaf-package installation.
- **Conclusion:** Use exact catalogue identities and one coordinator; graph independence alone does not establish safe script, database or file-side-effect concurrency.
- **Depends on:** none
- **Implementation:**
  - [x] Implement pinned catalogue dependency-graph collection and controller refusal checks. Preserve exact package/archive/manifest identities, repository selection, ABI/OSVERSION constraints and per-selection transitive closure; retain unresolved native version/solver requirements explicitly. [Collector contract](../package-dag.md).
  - [x] Compare actual native pkg dry-run plans with captured development graphs in fresh private databases. All 952 desktop and 960 NVIDIA package identities and imported dependencies match; native version-drift and omitted-transitive-package controls refuse. Sixteen controller/native checks pass. [Native checkpoint](../../verification/native-package-plan-development.json). Signed final inputs, actual installation and lifecycle admission remain open.
  - [x] Authenticate frozen public-key catalogues and verify package payloads through native pkg. The immutable 1.1.1 regression feed passes all 510 archives and independent GitHub hash/size checks; final-code seed replay and real wrong-key/signature/payload corruption controls pass. Twelve controller/native snapshot checks pass. [Signed-input checkpoint](../../verification/signed-package-snapshot-development.json). This does not select final 1.2 inputs or qualify installation/lifecycle admission.
  - **Parallel acquisition checkpoint:** The explicit version-2 signed-snapshot mode authenticates before scheduling, isolates each fetch database/cache and publishes ordered verified-byte progress. All 112 controller cases and all 40 process/snapshot controls on FreeBSD pass. Exact corrected source passes real pkg 2.8.4 on an eight-package immutable 1.1.1 subset: peak four overlapping fetches, byte-identical serial/parallel inventories, corrupt-payload/wrong-key/altered-signature refusal, successful fresh retry and unchanged host package database. The initial source-template refusal and its strict correction remain retained. This subset does not qualify final release inputs, installation or performance. [Scoped checkpoint](../../verification/parallel-package-fetch-development.json).
  - [ ] Capture complete real release catalogues and every supported selection; qualify native solver results, signature/hash verification and graph invalidation.
  - [ ] Implement coordinated bounded scheduling; publish structured progress; exercise retry, failures and recovery.
  - **Next action:** Integrate the qualified acquisition event contract with the shared transaction planner and installer/GUI. Designate complete final release catalogues and supported selections, then qualify full-input fetch and recovery. Installation scheduling, script/database/file conflicts and measured parallel installation remain open.
- **Evidence:**
  - [ ] Native dependency closure and integrity pass; real parallel installation improves measured time; side-effect conflicts, interruption and rollback are handled.

### [ ] GUI-001 — Deliver a colorful fast graphical package manager

- **Priority:** P2
- **Owner:** desktop and package-engine Components
- **Direction:** Provide the same useful visual progress and parallel execution in graphical package management, contributing a port if a new application is needed.
- **Conclusion:** Evaluate the current manager; share the transaction engine and progress semantics rather than build a competing planner.
- **Depends on:** PKG-001
- **Implementation:**
  - [ ] Evaluate extension path; implement responsive install/update/remove plans and visuals; prepare upstream application port if needed.
- **Evidence:**
  - [ ] Actual native UI, input, shared plan identity, accurate progress, failure/retry and packaging tests pass.

### [ ] SRC-001 — Establish owned FreeBSD source builds and packages

- **Priority:** P1
- **Owner:** release and diagnostics Components; daemonarchy-src fork
- **Direction:** Build modified FreeBSD-CURRENT from the owned source fork, retaining upstream provenance and coherent kernel/world/source package selections.
- **Conclusion:** Introduce clean exact-commit native builds with isolated objects/staging, GENERIC and diagnostic profiles, pkgbase and installer-set outputs, bounded jobs and verifiable build records. Do not install on build workers or publish unsigned development outputs as releases.
- **Depends on:** ADOPT-002 for framework execution and release qualification
- **Implementation:**
  - [x] Author the native plan/build/verify controller in [source PR #4](https://github.com/jordanhubbard/daemonarchy-src/pull/4); 11 refusal/custody tests pass locally, in CI and on FreeBSD.
  - [x] Prepare optional filemon/meta-mode capture and immutable per-phase snapshots in source revision `a2f44e0b96c0`; seventeen controller checks pass locally and in controller CI. The declared worker bootstrap now enables owner-only filemon access and its unprivileged readiness inspection passes; all 26 current controller/bootstrap checks pass on FreeBSD. Full traced-build execution remains unqualified.
  - [ ] Complete native end-to-end build/package/verify qualification. The quiet traced run reached completed set generation but failed metadata capture on a 39 MB source-archive record. The bounded streaming correction passes 30 native checks and captures the actual record; an independent audit verifies 537 artifacts and all eight sets. [Outcome evidence](../../verification/native-traced-build-quiet-result.json) preserves the original failure; full lifecycle acceptance remains open.
  - [ ] Produce the first baseline world/kernel/package/set build and retain identities. The 12-job GENERIC build at `92276fc76c65` passed world, kernel and pkgbase, then failed its first set-staging attempt. An isolated replay of the exact 219-header install passed; the root cause remains unproven. An exact-plan resume retained the failure and completed sets; 533 artifacts byte-verify and all eight MANIFEST set hashes independently verify. The source archive audit found all 138 symlinks dereferenced and build-user ownership; an isolated corrected source archive now matches every Git file and symlink with root ownership. ISO and native acceptance remain open. Its [plan and scope](../source-builds.md) are retained.
  - [ ] Qualify VM boot, installer set admission, matching jail/external modules, signing and rollback before production selection.
- **Evidence:**
  - [ ] Exact source/config/toolchain/log/artifact identities and failure refusal checks; native package output; VM/hardware results remain separate.

### [ ] DEBUG-001 — Qualify earlier wired network debugging for 1.2

- **Current release scheduling:** The complete network bootloader, `mountroot>`, early-kernel and panic transport, and MSI built-in-NIC capture belong to DEBUG-003 as **1.4 P0**. Prior release artifacts and the development history below retain their original scope.

- **Priority:** P0 — next-release blocker
- **Owner:** diagnostics and verified-boot Components
- **Direction:** Implement and qualify loader and early-kernel network debugging using a supported hard-wired NIC. The product and its runtime qualification are FreeBSD-only; implementation proceeds while parent CI is pending.
- **Conclusion:** Existing GENERIC networking facilities do not establish loader-to-early-kernel transport; design source-fork, trust and crash coverage before claiming support.
- **Depends on:** none
- **Source implementation:** [daemonarchy-src issue #6](https://github.com/jordanhubbard/daemonarchy-src/issues/6), owned by SRC-DEBUG-001. The first phase provides an authenticated, bounded UEFI console and controller; ordinary loader input retains show/set/boot semantics. It must preserve local recovery and explicitly report the firmware-to-kernel coverage gap.
- **Current source evidence:** [source PR #7](https://github.com/jordanhubbard/daemonarchy-src/pull/7) now contains the integrated console/controller. Native FreeBSD build and initial OVMF VM checks pass: authenticated show/set/boot, reconnect and replay refusal, output retry/ACK reflection, shared-NIC TFTP kernel loading, bounded RX pressure, missing-NIC normal boot and missing-peer local keyboard boot. A separate login/SSH observation confirms the remote kernel boot. Physical firmware/NIC, shared-netboot and injected firmware faults remain unqualified; this is not release acceptance.
- **Fault hardening:** Native scripted SNP/boot-service callback checks pass timeouts, late/error completion, shutdown quarantine, receive/allocation errors and polling/ownership bounds under address/undefined-behavior sanitizers. They reproduced and fixed frame-size overflow. The native ELF boot path now refuses an active/quarantined NIC; actual failed-firmware handoff remains unqualified. The latest binary repeats UEFI network/recovery checks, and its loader boot ID and MAC match the kernel environment/native NIC. EFI bootinfo errors now propagate, with native production-code tests for map/allocation/exit/retry/success paths. A production-parser fixture and actual UEFI NFS transfer reproduce and fix fragment theft: 8192-byte reads now complete with debugging active, and NFS kernel boot independently reaches a FreeBSD login. The latest EFI repeats adversarial session, TFTP/queue-pressure and remote boot/SSH checks. Runtime-map failure recovery, alternate exec paths and physical firmware remain unqualified.
- **Handoff identity renewal:** Source `f45d86b21143` and its exact rebuilt EFI pass native sanitizer export-failure controls and actual two-e1000 UEFI/kernel identity checks. Independent SSH verifies that the boot ID, selected debug NIC and local/peer addresses survive handoff. Both owned guests shut down successfully with original disks preserved. The [identity checkpoint](../../verification/loader-network-identity-development.json) retains the separate failed transfer: a `net0` file request reused the cached `net1` connection. [Source issue #11](https://github.com/jordanhubbard/daemonarchy-src/issues/11) owns unit-specific selection and live debug lifetime; fixing the unit comparison alone would close the active console NIC. The subsequent ownership checkpoint below records that repair and its scoped renewals. Early-kernel transport and physical firmware remain open.
- **Network ownership repair:** The [ownership checkpoint](../../verification/loader-network-ownership-development.json) records stable physical owners, separate raw debug sockets, driver/unit-aware ordinary access, close accounting, explicit protocol restoration and interface-bound DHCP cache reuse. Three native owner/cache suites and three native parser/SNP/bootinfo suites pass under sanitizers; 62 controller cases pass with four declared skips. The exact new EFI passes cross-NIC and same-NIC TFTP, two revocation/restart cycles, adversarial sessions, 112 queue-pressure drops with working control, fragmented 8192-byte NFS reads and NFS kernel boot. Four independent SSH observations match boot IDs/MACs; all six final owned guests shut down successfully. The NFS debug address remains metadata rather than active kernel networking. The source work has merged; native SDK admission, physical firmware, early-kernel transport and release acceptance remain open.

- **Panic transport baseline and recovery repair:** The
  [baseline checkpoint](../../verification/netgdb-panic-baseline-development.json)
  binds the actual kernel and matching full/debug symbols to ELF build ID
  `8139e27d002dc81d7f3a342d74ecc346e2787bb3`. An isolated guest refuses non-panic
  NetGDB entry, resumes locally and connects over e1000 after a controlled panic.
  The first Linux GDB client lacks the FreeBSD ABI; no successful native debugger
  inspection is claimed. Peer closure reaches debugnet but leaves NetGDB polling.
  [Source issue #12](https://github.com/jordanhubbard/daemonarchy-src/issues/12)
  owns the missing finish callback and single teardown owner. Its source repair
  is in progress; a changed native kernel and successful inspection, detach and
  peer-close/local recovery remain required. The FreeBSD client is prepared.
  Both guests and owned tunnels are stopped, with original disks preserved.
  The protocol remains unauthenticated and panic-only; physical NIC, pre-driver
  and continuous early-kernel transport qualification remain open.

- **Native debugger baseline:** The [FreeBSD client checkpoint](../../verification/netgdb-native-baseline-development.json)
  now passes actual e1000 NetGDB register and panic-memory reads, a kernel
  backtrace, enumeration of 100 threads and orderly detach with matching ELF
  symbols. Independent serial control verifies return to DDB, local register
  inspection, pager recovery and reset. Both guests exit zero before their
  deadlines. Two debugger re-entry messages and the absent source-text paths
  are retained observations. This uses the unmodified retained `bdcfeac3e1cb`
  kernel baseline, not repair `791ac20a21ad`. Build and qualify that candidate's
  peer-close recovery next; native netdump, physical NIC and early-kernel
  activation remain open.

- **Implementation:**
  - [x] Inspect loader/kernel transport foundations: EFI Simple Network Protocol and standalone UDP exist; an interactive loader network stub does not. Current NetGDB explicitly requires a panic and an initialized supported NIC. Firmware networking stops at `ExitBootServices`; boot flags do not establish an early network debugger. This is source-backed scope discovery, not runtime qualification.
  - [ ] Qualify an explicitly selected loader command/console stub, including environment inspection/update and kernel boot over the reviewed wired transport.
  - [ ] Qualify existing NetGDB/netdump operation with the selected native NIC and exact symbols, preserving the panic-only limitation until separately resolved.
    The linked native Netdump baseline now passes for the private e1000 VM and
    exact kernel. Next: inspect driver-ready activation and the pre-driver coverage
    boundary; retain the separate physical NIC and authenticated transport gates.
  - [ ] Implement and qualify early-kernel driver/transport activation and debugger entry; retain the loader handoff identity and document the remaining pre-driver gap.
  - [ ] Define transport and authorization boundaries; select supported NICs and matching symbols; implement and qualify the explicit debug profile.
- **Evidence:**
  - [ ] Actual early boot and crash traffic is retained on a controller with documented unsupported phases and protected private state.

### [ ] HW-001 — Close remaining physical hardware qualification gaps

- **Priority:** P1
- **Owner:** desktop, compatibility and diagnostics Components
- **Direction:** Keep unresolved GPU, radio, boot and restart behavior explicit while extending physical acceptance.
- **Conclusion:** HP desktop/application acceptance passed. On the MacBook, a refreshed graphics package and T2 keyboard test kernel reached a visible desktop and accepted a password; the pointer worked after initial lag. A private BCM4364 driver and board firmware joined WPA2, obtained DHCP and reached the gateway, and the desktop Wi-Fi panel connected. The operator confirmed on October 24 that all Intel 16-inch MacBook Pro pre-production checks passed and waived a final-ISO physical rerun. Earlier preview gaps and failures remain historical observations on their original images, not current 1.3.1 publication blockers. The final public ISO has no claimed physical run or hardware-rooted T2 attestation. Other hardware platforms and future driver improvements remain tracked here. See [preview evidence](../testing-macbookpro16-1-wifi-preview-20261022.md) and the [release decision](../../verification/macbook-release-decision-1.3.1.json).
- **ASRock availability:** The operator reports the RTX system still hangs in firmware and cannot enter setup or the boot menu, even with other USB devices disconnected and the keyboard directly attached. Firmware recovery is pending; no current Daemonarchy boot or physical acceptance result can be obtained from it. Keep R12-11 open.
- **MSI video:** The October 18 recording ends readable output at `atrtc0: Warning: Couldn't map I/O.` before the display blanks, with no visible panic. The second video confirms the RTC-disable/panic flags and advances to `sc0 failed to probe on isa1` before blanking, without a visible panic. Repeated Intel SPMC constraint-format warnings motivated a `debug.acpi.disabled="spmc"` comparison, which the operator reports made no difference; the exact installer artifact remains unidentified. The [analysis](../testing-1.1-hardware-observations.md#msi-startup-video-reviewed-2026-10-18) records the movie identity, observed scope and source-backed diagnostic; no default quirk or fix is qualified.
- **MSI current report, October 23:** ACPI enabled still produces an early reset without a visible panic; disabling it produces a missing-APIC panic and debugger entry. The operator confirms the MSI Raider 18 HX/RTX 5080, latest pre-1.3 ISO and `APIC: Could not find any APICs`; exact artifact filename/hash and current BIOS remain unrecorded. [The source-backed diagnostic](../testing-1.1-hardware-observations.md#msi-acpi-on-reset-and-acpi-off-apic-panic-reported-2026-10-23) explains why ACPI-off can also remove MADT-based APIC discovery. The operator confirms the proposed ACPI-on/SMP-disabled and panic-retention settings were already tried without changing the reset; do not request that repeat. Loader networking is implemented only through firmware handoff; continuous early-kernel capture remains unfinished. No boot fix is claimed.
- **Depends on:** none
- **Implementation:**
  - [ ] Retain exact hardware and artifact scope; investigate known failures without conflating transport loss and reboot; qualify actual rendering, wireless and recovery.
- **Evidence:**
  - [ ] Native/operator results identify exact hardware and build, with unresolved or unrun cases remaining open rather than waived into passing.

### [ ] RELEASE-001 — Deliver a qualified Literate AI release workflow in 1.4

- **GitHub issue:** [#11](https://github.com/jordanhubbard/daemonarchy/issues/11)

- **Priority:** P1
- **Owner:** whole product, release and acceptance
- **Direction:** Finish the retained backlog and publish a future release entirely through qualified Literate AI execution across the owned repositories. The original 1.2.0 milestone was not published; 1.3.1 records the intervening development but uses its separately verified native release workflow.
- **Conclusion:** This remains a 1.4 goal. Its existence proof must include actual native build, complete declared testing, artifact custody and publication; authority-only adoption, waived backlog, or the 1.3.1 native release cannot close it.
- **Depends on:** ADOPT-002,UI-001,PKG-001,GUI-001,DEBUG-001,HW-001,SRC-001,COMP-001
- **Implementation:**
  - [x] Inventory current roadmap and queue obligations in [the 1.2.0 completion ledger](release-1.2.0.md), including inherited Bluetooth, enterprise Wi-Fi, dual-boot, bhyve and physical trust/graphics gaps.
  - [x] Keep release media and documentation in sync: [`release/current.json`](../../release/current.json) records the latest published release and all its image types and asset digests; `scripts/release-current.py` updates and checks it against GitHub; `tests/docs-release-sync.py` runs in the release-controls workflow and fails on a current-state document that names an older release as current, an older image name, checksum or size, or an unreleased version as available. HACKING.md's release step 3 is the checklist. The 1.4.0 publication must pass it ([ledger row A16](1.4-coverage-ledger.md)).
  - [ ] Contribute and qualify upstream FreeBSD platform and retained execution support; bind private native workers and VM supervision; complete backlog implementations and acceptance; run the exact final release through Literate AI and verify publication.
- **Evidence:**
  - [ ] Every inherited backlog obligation has direct completion evidence; native and virtual/physical acceptance match exact final artifacts; full LitAI verification and release gates pass; published new release and immutable assets are verified.

The [subsequent October 22 refresh](../../verification/upstream-refresh-2026-10-22-night.json)
confirms sources remain current at `775e421dc38f`; source PR #9 still has four
passing Linux cross-builds and two queued macOS cells. [Ports PR #18](https://github.com/jordanhubbard/daemonarchy-ports/pull/18)
is merged at `72c758ea367d`, importing 44 upstream commits through
`a7c9a97bae26` across 172 paths. All 64 downstream blobs/modes and the complete
downstream binary delta are preserved; the imported delta exactly matches
upstream. Its 141 whitespace diagnostics match the upstream patch files verbatim.
Native changed-port builds and clean bulk qualification remain unrun.

The [final October 22 refresh](../../verification/upstream-refresh-2026-10-22-final.json)
confirms the owned source mirror still matches upstream at `775e421dc38f`.
Source PR #9 retains four passing Linux cross-builds and two queued macOS cells;
its integration remains pending. [Ports PR #17](https://github.com/jordanhubbard/daemonarchy-ports/pull/17)
is merged at `702e0e3cc491`, importing two further upstream commits through
`e4abbf95f5b8`: the new optique port and octave-forge-drafting 0.2.4.
All seven changed paths match upstream exactly; all 64 downstream blobs/modes
and the complete downstream binary delta are preserved. Whitespace checks pass.
Native changed-port builds and clean bulk qualification remain unrun. Active
workspaces and published release pins retain their preceding selections.

The [latest October 22 refresh](../../verification/upstream-refresh-2026-10-22-late.json)
keeps sources current at `775e421dc38f`. Source PR #9's exact-head run now has
all four Linux cross-builds passing; both macOS cells remain queued, so source
integration is still pending. [Ports PR #16](https://github.com/jordanhubbard/daemonarchy-ports/pull/16)
is merged at `e132ac13a895`, importing another 27 upstream commits through
`4df6b05e0803` across 57 paths, including Keycloak security fixes and PowerDNS
Recursor updates. All 64 downstream blobs/modes and the complete downstream
binary delta are preserved; the imported delta exactly matches upstream.
Six whitespace warnings match the original upstream patch files. Native builds,
active workspace selections and published release inputs remain unchanged.

The [evening October 22 refresh](../../verification/upstream-refresh-2026-10-22-evening.json)
adds three source commits through `775e421dc38f` and 14 ports commits through
`ca96d11f77ad`. The owned source mirror matches upstream exactly. [Source PR #9](https://github.com/jordanhubbard/daemonarchy-src/pull/9)
now retains 98 upstream commits plus the existing mandoc/libz bootstrap repair
at `b051901b0ff1`. Fresh exact-head [cross-build run 39818544271](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/39818544271)
is pending; the preceding head's four passing Linux cells and two queued macOS
cells do not qualify this new head. [Ports PR #15](https://github.com/jordanhubbard/daemonarchy-ports/pull/15)
is merged at `17bebe849ef2`, updating 586 upstream paths, including Unbound
security fixes and Chromium. All 64 downstream blobs and modes, the complete
downstream binary delta and the exact upstream import are preserved. Ports has
211 whitespace warnings identical to upstream; patch bytes remain unchanged.
Source whitespace checks pass. Native world/kernel, changed-port and clean bulk
qualification remain open. Active development workspace selections and published
release inputs are unchanged.

The [preceding October 22 refresh](../../verification/upstream-refresh-2026-10-22-followup.json)
adds one source commit through `c7523e8cfbd0` and 15 ports commits through
`9517a531083e`. The source mirror is current; [source PR #9](https://github.com/jordanhubbard/daemonarchy-src/pull/9)
now retains 95 upstream commits and the existing mandoc bootstrap dependency
repair at `4b64fb49d22e`. Exact-head [cross-build run 39802806112](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/39802806112)
is pending, so source integration remains open. [Ports PR #14](https://github.com/jordanhubbard/daemonarchy-ports/pull/14)
is merged: 41 upstream paths changed, all 64 downstream blobs and modes and the
complete downstream delta are preserved. Both imports match their upstream
deltas exactly and pass whitespace checks. Ports has no hosted workflows;
native changed-port and clean bulk builds remain unrun. Active workspace and
published release selections are unchanged. The preceding checkpoint below
retains its historical revision and test scope.

The [October 22 upstream checkpoint](../../verification/upstream-refresh-2026-10-22.json)
records the latest conflict-free ports import: 21 further commits through
`38ef2e0cd3e6`, merged in [ports PR #13](https://github.com/jordanhubbard/daemonarchy-ports/pull/13)
at `bb2dac41b789`. All 64 downstream paths retain their blobs and modes, the
complete downstream delta is preserved, and the imported delta exactly matches
upstream. Fifteen whitespace warnings inside verbatim upstream patch files are
retained; no hosted workflows are configured for the ports repository. The
preceding six-commit import remains recorded separately. Source tracking is
current at `ad0f86694157`; [source PR #9](https://github.com/jordanhubbard/daemonarchy-src/pull/9)
retains 94 commits pending integration plus a scoped bootstrap repair at
`883295fb6aa`. The earlier exact-upstream run failed its ARM64 Ubuntu 24.04
`mandoc` link while zlib was still compiling. [Source issue #10](https://github.com/jordanhubbard/daemonarchy-src/issues/10)
records the missing graph edge. All four Linux cross-build cells now pass on the
repair in run `39776145660`; both macOS cells remain queued, so source integration
remains pending. Active workspace selections are unchanged. Native changed-port
tests, clean bulk builds, coherent final input admission and the remaining R12-18
requirements stay open.

The [ordinary network context checkpoint](../../verification/loader-network-context-development.json)
adds source `17872b0d6b4`: failed DHCP/RARP setup now refuses stale parameters
from another interface, and a new configuration without MTU removes the stale
published value. Both failures are reproduced before repair. The production
native sanitizer fixture passes, and a complete verified `983b4315ec01` source
baseline plus the pinned change builds the new EFI. Actual cross-NIC TFTP,
same-NIC revocation/restart and small/fragmented NFS with kernel loading pass.
Three independent kernel observations match boot IDs and NIC identities; the
NFS debug IP remains metadata only. All four owned guests shut down normally.
The controller passes 62 cases with four native-only skips; authority and all
five explicit FreeBSD locks pass. Source PR #7 is now merged; native SDK,
compiler admission, physical firmware, early-kernel transport and final release
qualification remain open.

The [native NetGDB recovery checkpoint](../../verification/netgdb-peer-close-development.json)
qualifies exact kernel `791ac20a21ad` from a clean native GENERIC build
(609.905 seconds; 610.475 supervised), with matching kernel/full/debug build IDs.
FreeBSD GDB 15.1 reads registers, actual panic memory, a panic backtrace and 104
threads. Two orderly detach sessions return to DDB, including a renewed complete
version-output check after retaining a harness truncation failure. A third client
exits without detach: captured FINISHED now reaches generic GDB termination,
restores mbuf zones and returns to DDB. Local registers and reset work after the
close; non-panic refusal and local continue also pass. Both owned VMs exit zero
before deadline and all disks are retained. [Source issue #12](https://github.com/jordanhubbard/daemonarchy-src/issues/12)
was implemented and natively qualified on PR #7, now merged into source `main`.
Physical NICs, Netdump, authenticated kernel sessions, continuous early-kernel
transport, compiler/SDK admission and release acceptance remain open.


The [native Netdump baseline](../../verification/netdump-native-baseline-development.json)
now passes on the same exact `791ac20a21ad` kernel with matching full symbols.
A pinned upstream `netdumpd` receiver builds natively in 0.93 seconds; the owned
VM's controlled panic sends a 165,371,904-byte minidump with valid header parity.
Native `kgdb` reads the full kernel version, panic pointer/string and backtrace,
and enumerates 100 threads. Independent reconstruction of all 116,076 data
messages from the packet capture reproduces the received core's SHA-256 exactly,
with no gaps or overlapping unique data. The receiver exits zero and both bounded
guests stop before deadline with all backing disks read-only. Initial CLI-option
and driver-text harness failures remain retained. This is a private-wire VM
baseline: physical NICs, authenticated kernel sessions, continuous early-kernel
activation, compiler/SDK admission and final release acceptance remain open.

The [debugnet pool-readiness repair](../../verification/debugnet-pool-readiness-development.json)
now reproduces an earlier-panic safety defect: the original allocator activation
replaces global mbuf pointers even when its reserved pools are absent. The candidate
returns `ENXIO` before changing ownership and propagates refusal without finishing
an inactive pool. All seven absent/partial combinations, retry and complete cycles
pass in sanitized controller and native FreeBSD function fixtures. The controller
suite passes 62 cases with four native-only skips; style checks and hosted controller
CI pass. [Source issue #14](https://github.com/jordanhubbard/daemonarchy-src/issues/14)
and [merged PR #15](https://github.com/jordanhubbard/daemonarchy-src/pull/15) retain this
repair. A fresh native checkout reached its 300-second bound; its remaining owned
Git child is stopped and all partial files/logs are retained. A clean, unused cold
canonical checkout then reaches exact `7a4b58c717bc` in 2.13 seconds after process,
cwd, mount/export and Git audits, preserving its old revision and index. Primary
refs/HEAD are unchanged. The full native kernel now builds in fresh objects with
four jobs and unchanged 2400-second supervision, within the 3 GiB write budget
and 40 GiB physical host reserve. Earlier bare-repository and checkout failures
remain retained. The [exact kernel and early guard checkpoint](../../verification/debugnet-early-kernel-development.json)
now passes its clean GENERIC build in 521.803 supervised seconds. All three
products share build ID `38821cf580ffed76cdffc9109ee84bd6f5f4d71a` and transfer
hashes reverify. A direct boot-time DDB call before driver initialization returns
`ENXIO` with ten inspected allocator/saved-state words unchanged; registers and
ordinary boot then pass, with independent UUID, kernel and NIC observations.
The guest shuts down normally before deadline. The same-guest completion of a
truncated serial continue request remains recorded. The [ready-kernel NetGDB renewal](../../verification/debugnet-ready-recovery-development.json)
passes two detach sessions and one abrupt peer closure, with three allocator
restorations and local DDB recovery. The [Netdump renewal](../../verification/debugnet-ready-netdump-development.json)
passes on the same exact kernel: native postmortem reads the panic and 100 threads,
and reconstruction of all 165,330,944 core bytes from the private-wire capture
matches the received dump hash. Both test pairs stop before their deadlines.
Continuous early-kernel networking, authentication, physical NIC and final
source/compiler/product admission remain open.

The [standalone NetGDB contribution patch](../contributions/netgdb-peer-close.md)
applies to current upstream and passes its style checker. It remains unsubmitted
pending human review and native qualification on that exact upstream base;
the downstream runtime also contains three guarded mbuf pullup calls absent
upstream. Preserve this distinction when contributing or refreshing source.

The [isolated native public SDK checkpoint](../../verification/native-sdk-isolated-cli-development.json)
now passes exact framework wheel `4ed7e5a1` in 575.845 supervised seconds, within
the unchanged 3,600-second authorized execution budget. The real public CLI
builds the original consumer, passes three tests, documentation and two withheld
acceptance cases, and admits a local-runtime receipt. All 28 retained records
reverify from current CAS bytes. The accepted app fails without the reviewed
loader context; both authorization refusals remain intact. The owned source
server exits zero, and six binding controls pass in this new prefix. All ten installed
context controls pass with zero skips; all 469 production modules resolve from
the installed prefix. This does not admit the source-built
compiler, actual FreeBSD source SDK, packages, product receipt, ISO or release.
The [Windows/descriptor composition](../../verification/composed-framework-qualification-development.json)
now passes the complete controller regression (2,206 selected, 2,135 passing,
71 declared skips) and exact installed Linux wheel qualification, including
changed-payload refusal. Its fresh FreeBSD prefix installs offline, initializes,
and passes six binding controls. Its [real public CLI renewal](../../verification/native-sdk-composed-cli-development.json)
now passes in 573.597 supervised seconds: three original tests and two independent
acceptance cases pass, the local-runtime receipt is admitted, all 28 retained
records reverify from current bytes, and the owned source server exits zero.
All ten installed context controls now pass in 625.485 supervised seconds,
with zero skips and 469 installed production modules verified. Native Windows passes preflight,
environment, compile, lint, OpenSpec and documentation checks, then its wheel
check refuses missing Git objects in the qualification partial clone before unit
testing. The failed run is retained. Fetching the complete Git object closure
reduces 4,142 missing objects to zero, and connectivity verification passes.
The renewed native gate then refuses newly reported critical/high DOMPurify
advisories before wheel or unit tests. [Framework issue #120](https://github.com/jordanhubbard/literate-ai/issues/120)
owns the compatible 3.4.17 transitive-lock update and native gate renewal; no audit
exception is added. Production Python source is unchanged.
The first complete host lifecycle refuses a generated frontend BigInt error
without a candidate receipt. Fresh complete regeneration with the same configured
model now passes 228 tests and independent acceptance in 1,595.584 seconds.
Supported promotion yields current parent receipt `0e2f897c8b6e`; the original
failure remains retained. The compatible DOMPurify 3.4.17 repair passes clean
controller audit and documentation checks without exceptions. The full native
Windows gate on patched composition `23d0b678` reached its unchanged
5400-second limit during wheel qualification. Its finite supervisor terminated
the process tree; the unit suite did not start. The failed workspace and wheel
remain retained for targeted profiling; no native Windows gate pass is claimed.
The [targeted import investigation](../../verification/framework-project-import-development.json)
now finds 39 optional URI parser constructions during ordinary project CLI startup.
The parent repair in [draft framework PR #122](https://github.com/jordanhubbard/literate-ai/pull/122)
defers MAC validation imports until its command is selected; strict schema rejection
still passes through the actual CLI. Two focused and seven CycloneDX cases pass;
repository lint, formatting, authority and declared framework verification pass.
A single unprofiled Windows baseline/deferred import pair takes 7.48/2.91 seconds
with installed bytes unchanged. Profile times include substantial overhead; neither
measurement proves complete wheel qualification. Exact candidate `8f1b7df6` is staged
for a fresh canonical Windows checkout with its original 5400-second gate bound;
Git hydration and connectivity now pass with zero missing objects, preflight passes,
and the live gate is creating its dedicated environment. The primary checkout and
failed preceding workspace remain preserved.
The [patched-wheel public CLI renewal](../../verification/native-sdk-postaudit-cli-development.json)
also passes on a fresh FreeBSD allocation with exact framework `23d0b678`:
536.095 supervised seconds, three original tests, two independent acceptance
cases and all 28 retained records reverified. Its 3600-second authorization limit
is unchanged. A separate tree-alias case now observes real hard-link inode equivalence and
exact symbolic-link text from its live producer. Its [public CLI tree lifecycle](../../verification/native-sdk-tree-public-cli-development.json)
now passes in 535.622 seconds: three original tests, two independent acceptance
cases, all 28 receipt records reverified and a clean owned-server exit. Its scope
is local-runtime; the completed run reports SDK admission false. All ten exact patched installed context controls also pass in 592.634 seconds,
with zero skips and 469 installed production modules verified. The separate
[real source-package C diagnostic](../../verification/source-compiler-relocation-development.json)
now preserves 28 symbolic aliases and nine hard links and compiles/runs after
retiring its initial compiler/sysroot path. Actual loader and linker-input
observations remain within the declared resources. Live source-producer/SDK
admission and complete per-unit package provenance remain open.

No compiler SDK, product receipt, ISO or release admission follows from these
partial checks.

The optional-import framework CI passes 2179 selected unit cases (2090 passes,
89 declared skips) and documentation checks, then correctly refuses the stale
lifecycle-driver pin. Reviewing the sole changed TCB import location through the
canonical command records `4ec3013bae99`; documentation authority passes and the
old receipt becomes stale. Exact framework `191887c0` then passes its complete
230-test configured host lifecycle with independent acceptance in 1664.006 seconds.
Its receipt is canonically promoted and committed in `bd76625f`; driver review and
framework verification pass. The final receipt commit has new
hosted CI is queued. The Windows gate remains bound to preceding `8f1b7df6`;
its result cannot qualify later project metadata.

The [native worker investigation](../../verification/native-sdk-worker-investigation-development.json)
now profiles the installed descriptor candidate for a deliberate 300-second
execution window. File closes consume 134.537 self seconds and stat calls
109.699 seconds. A bounded syscall trace sees some closes take up to 249 ms;
read-only kernel samples identify the vnode batch/mutex path. A root-owned
periodic security scan is concurrently traversing the worker filesystems; it is
left running and kernel settings are unchanged. The same 1,235 current wheel
members yield identical identities in fresh observations: 7.7–8.4 seconds on the
primary role and 0.18–0.20 seconds in a disposable aligned FreeBSD VM. The
kernels, filesystems and load differ; this is diagnostic evidence of a worker
bottleneck, not a controlled speedup attribution. The isolated offline install
and project initialization pass. Its unchanged-budget canonical SDK command
was live at that checkpoint and has now passed as recorded above. The ten installed
context controls have now passed as recorded above.
Windows/descriptor composition is isolated for fresh full regression and later
exact-wheel/lifecycle renewal. The missing product receipt and release gates
remain open.

The [descriptor-read checkpoint](../../verification/native-sdk-descriptor-read-development.json)
records framework code `4ed7e5a1`, published with qualification at `9b834cde`.
Its uninterrupted regression passes 2,132 cases with 70 declared skips; the exact
clean Linux wheel passes. Six binding controls pass from the installed FreeBSD
prefix, including open-boundary symlink refusal. The complete configured host
lifecycle passes 228 tests and independent acceptance; its receipt is promoted
through the supported command and verifies current. The real installed FreeBSD
SDK replay timed out at its unchanged 3,600-second command budget
(4,103.472 seconds supervised total). The owned source server exited zero;
no native SDK admission was earned. Profile the installed descriptor candidate
before another canonical replay.
This does not admit the actual compiler/sysroot or Daemonarchy lifecycle. A new
passing public replay, installed context controls and Windows composition are required before landing
the parent contribution. The preceding checkpoint retains its older artifact and
233-test receipt scope.

The [observer performance checkpoint](../../verification/native-sdk-observation-performance-development.json)
records the exact `760bfa09` wheel, 2,131 controller passes with 70 declared
skips, clean Linux wheel qualification and a complete 233-case configured host
lifecycle with a current framework receipt. The subsequent installed FreeBSD
canonical public SDK build still times out at the unchanged 3,600-second
execution budget (4,162.132 seconds total), despite passing its preparation and
authorization refusal controls. Its owned source server exits successfully.
Canonical native admission remains unearned; profile actual authorized execution
before claiming the observer optimization resolves that release blocker.

### [ ] COMP-001 — Model complete FreeBSD source and ports trees as Components

- **Framework issue:** [#74](https://github.com/jordanhubbard/literate-ai/issues/74)
- **Detailed plan:** [Complete source/ports Component coverage](freebsd-components.md)

- **Priority:** P1
- **Owner:** source and ports Component inventories; framework retained native lifecycle
- **Direction:** Represent all of /usr/src and all of /usr/ports as Literate AI Components, not opaque external trees.
- **Conclusion:** Require complete pinned tree ownership, native build-unit and port-origin contracts, target/options variants, dependency composition and honest per-component evidence while preserving upstream implementation authority.
- **Depends on:** SRC-001, ADOPT-002
- **Implementation:**
  - [x] Record complete-tree coverage, component granularity, variant and dependency requirements in G8 and the release Component contract; file framework issue #74.
  - [x] Retain pinned-tree diagnostic inventories and nine portable discovery checks; [producer/result identities](../../verification/native-tree-discovery.json) record candidate ownership separately from canonical admission.
  - [x] Observe the native `bin/ls` directory closure with explicit amd64/host contexts, shared Makefile inputs and cycle/failure refusal; [scope and identities](../../verification/native-dirdeps-observation.json) retain its diagnostic limits. The first full sweep exposed unqualified extra-directory/context parsing errors. The corrected collector preserves those paths and returned query output; eleven portable checks and a native two-seed probe pass their observation/refusal expectations. Re-observe full coverage and reconcile stale declarations with actual build actions before canonical binding. Full native catalog/action resolution remains open.
  - [x] Author and lock the first original header/parser/utility contracts in the source fork, apply reviewed in-place original authority and bind the installed Standard lifecycle. [Current checkpoint](../../verification/original-source-authority.json) keeps three registered/locked units separate from zero admitted units and zero qualified per-unit packages. Explicit FreeBSD/pkg Flavors resolve; the HP's isolated development CLI validates `/usr/src`. Compiler/runtime admission, complete ownership, execution and system framework renewal remain open.
  - [ ] Admit every source/build/support input and ports origin through canonical Component catalogs and locks; reject missing or ambiguous ownership.
  - [ ] Connect native actions and conditional dependencies to retained execution, receipts and the exact release closure.
  - [ ] Qualify the [first native source composition proof](freebsd-components.md#first-native-source-composition-proof): compile original application/library source with admitted compiler resources, headers and sysroot; run original tests and independent cases; produce per-unit pkg products; observe actual invalidation and relocated VM installation/recovery. Exported precompiled-helper and package-format fixtures retain their narrower custody/integration scope.
  - [ ] Acquire the [observed bootstrap compiler closure](freebsd-components.md#bootstrap-compiler-closure), including native linker-script references, with explicit seed provenance and input budgets; prove relocated sysroot resolution before treating it as an admitted compiler SDK. The retained read-only inventory is diagnostic evidence only.
  - [ ] Qualify internal alias provenance through the canonical native SDK producer, materialization and consumer owners; framework [issue #93](https://github.com/jordanhubbard/literate-ai/issues/93) tracks the current regular-file-only SDK boundary separately from retained input custody.
- **Evidence:**
  - [ ] Full selected trees have zero unowned inputs, all origins are represented, and catalogued/admitted/built/accepted states remain distinct.
  - [ ] Changed source, options, dependencies, toolchain or artifact invalidates the applicable receipts; exact native release closure passes installed framework and runtime qualification.

### [ ] PERF-001 — Execute native Components and substantially accelerate ISO builds

- **Detailed plan:** [Native Component execution and build performance](build-performance.md)

- **Priority:** P1
- **Owner:** release build graph, native Component lifecycle and build-system Flavors
- **Direction:** After establishing the source/ports graph, use LitAI to execute literal Components and substantially improve FreeBSD ISO build and packaging time; replacing make with Bazel, Buck2 or another suitable system is authorized.
- **Conclusion:** Measure the current native baseline, establish complete package/provenance/dependency coverage, and choose execution, caching, incremental and packaging changes from evidence. Preserve exact output correctness and native acceptance; a wrapper or renamed executor is insufficient.
- **Depends on:** COMP-001
- **Implementation:**
  - [ ] Capture baseline phase, action, packaging and end-to-end timings with exact inputs and resource limits.
  - [ ] Admit source/ports graph units as canonical executable Components with versioned pkg products and full provenance/dependency information.
  - [ ] Compare and implement supported native or alternative build execution, caching, parallelism and packaging strategies.
  - [ ] Demonstrate materially faster clean, unchanged and changed-component ISO workflows without missing rebuilds or weakening acceptance.
- **Evidence:**
  - [ ] Same-target baseline/optimized measurements retain source, configuration, toolchain, cache/resource state, action counts, output hashes and test results.
  - [ ] Native Component invalidation, per-unit pkg provenance, complete dependency closure, packaging, ISO installation and rollback remain correct.

### [ ] PERF-002 — Coordinate all Daemonarchy repositories through Literate AI workers in 1.4.0

- **GitHub issue:** [#39](https://github.com/jordanhubbard/daemonarchy/issues/39); [1.4.0 milestone](https://github.com/jordanhubbard/daemonarchy/milestone/3).
- **Detailed plan:** [1.4.0 cross-repository build and release graph](release-1.4.0.md).
- **Priority:** P1 for 1.4.0; outside the 1.3.1 release and 1.3.2 MSI acceptance paths.
- **Owner:** LitAI native lifecycle, owned source/ports/desktop/compatibility forks and product release integration.
- **Direction:** Select exact commits across all owned release-input repositories, resolve their complete native build/test/package/release dependency graph, and schedule ready actions across multiple physical machines with LitAI's parallel workers and a shared verified artifact cache. Treat ports and packages as build artifacts; evaluate Bazel incremental builds, remote cache/execution and other suitable tools. FreeBSD make and Poudriere are optional executors.
- **Fork authority:** The owned FreeBSD source and ports forks are in scope for any 1.4 build, ports, package, ABI or cache integration changes needed to deliver this flow. Keep their native contracts and reviewable FreeBSD CURRENT refreshes; land changes in each fork's main before the release selection is locked.
- **Conclusion:** LitAI must coordinate cross-release reuse of unchanged builds, binaries, packages and release inputs; fine-grained input custody and invalidation; resource-bounded distributed concurrency; test receipts, package provenance and exact release publication. A single opaque wrapper around the legacy build and distribution pipeline does not meet this item.
- **Depends on:** ADOPT-002, COMP-001, DEV-001, PERF-001.
- **Implementation:**
  - [ ] Bind product, source, ports, desktop and FreeBSD compatibility fork revisions, plus any selected owned Omarchy input, in one reviewed release plan with upstream ancestry and target/options/toolchain identities.
  - [ ] Implement authoritative dependency, package, ABI and cache metadata at the source and ports producers where needed; qualify and merge the fork changes, rather than inferring a complete graph from an outer wrapper alone.
  - [ ] Admit complete relevant Component/action ownership and conditional dependencies. Key cached outputs by source subtrees and shared inputs, port metadata, generated inputs, toolchain/sysroot, relevant target ABI, build-time dependency contents, runtime ABI/version constraints, command and environment; retain exact OSVERSION and package versions as provenance, and repair missing graph edges before admitting a cache hit.
  - [ ] Separate actual build-time inputs from runtime-only dependencies. For a changed OSVERSION or runtime package, qualify reuse of unchanged userland payloads against the selected ABI, version constraints, package scripts and native application behavior; retain the exact payload digest and new receipt. Rebuild changed headers, static inputs, kernel modules or incompatible/uncertain cases. Exercise the 1.1.1-to-1.3.1 Chromium/CEF case.
  - [ ] Execute and cache native source, tests, binaries, ports packages, feeds, boot products and ISO inputs through LitAI workers on multiple physical machines. Share verified immutable artifacts, avoid duplicate actions and race-free package database or protected signer access. Select Bazel, remote cache/execution or another incremental executor by equivalent native correctness and measured speed.
  - [ ] Compare clean, unchanged and changed-input single-machine and distributed workflows against the 1.3.1 baseline, qualify native/VM/physical results on exact assets, and publish a verified 1.4.0 release from the selected plan.
- **Evidence:**
  - [ ] Per-repository locks, zero unowned selected inputs, complete dependency and package closures, correct invalidation and verified cross-release reuse are retained. Unchanged action keys cause no recompilation; missing edges refuse reuse.
  - [ ] Compatible base/runtime-dependency version changes requalify and reuse unchanged userland payloads without recompilation; incompatible ABI, changed build inputs or failing native tests rebuild the correct closure.
  - [ ] The 1.3.1 Chromium/CEF regression is eliminated in an admitted 1.4 run: unchanged release inputs compile no packages, compatible base/runtime version changes requalify and reuse both browser payloads, and changed build inputs or incompatible ABI rebuild only the affected closure. On equivalent build/package/sign/ISO gates and worker pool, finish a compatible update at least 4x faster and an unchanged rerun at least 10x faster than a clean rebuild. Record wall-clock time, cache bytes and every decision; duplicate full builds on additional machines do not satisfy this item.
  - [ ] At least two physical machines run independent native actions concurrently from one plan and shared verified cache within recorded resource budgets; duplicate-key, failure, retry and serialization controls pass.
  - [ ] Measured full release creation and unchanged repeat are materially faster without omitted tests or packages, and the tagged ISO, signed feeds, receipts and scoped hardware evidence agree on exact bytes.

### [ ] DEV-001 — Provide an operator-ready native Component development system

- **Disposable worker implementation:** The versioned QEMU supervisor owns its
  child and finite lifetime and exposes only fresh, context-bound read-only
  inspections through a private socket. Its FreeBSD root relay keeps QMP on the
  controller. Twelve controller checks pass. The separate
  [native checkpoint](../../verification/native-qemu-worker-development.json)
  boots the actual FreeBSD guest, verifies three fresh root-relay inspections
  and refuses replay, wrong-plan and control-field requests. It uses an operator
  fixture context. A subsequent supervisor interruption cleanly powers off the
  guest, syncs buffers, records QEMU exit zero and removes the inspection socket;
  both owned processes are confirmed gone. Native automatic expiry and installed
  lifecycle qualification remain required. See the
  [worker runbook](../native-qemu-worker.md).

- **Preceding candidate renewal:** Framework `587ad3f1` passes a fresh Python 3.11 full
  regression and its exact committed installed-wheel gate. The isolated native
  FreeBSD installation verifies all 37 distributions, the 1,212-member framework
  identity, unchanged Standard policy, Ed25519, SQLite and the numeric secondary
  account. The [checkpoint](../../verification/native-development-cli-587ad3f1.json)
  preserves the refused manifest-less invocation and successful explicit-manifest
  retry. Hosted CI, installed original-source lifecycle, SDK admission and physical
  workspace cut-over remain open.

- **Source SDK baseline:** A separate owned KVM FreeBSD guest now runs the pinned
  native make build as an unprivileged account with four jobs, eight guest CPUs,
  16 GiB RAM and a 160 GiB disk. `buildworld` completes with exit 0 in 7,930.977
  seconds, with its retained log hash independently checked and the pinned source
  worktree still clean. Kernel compilation then passes in 600.195 seconds,
  package generation in 352.074 seconds and release object preparation in 0.471
  seconds. Installer-set staging then passes in 469.502 seconds. The complete
  producer exits zero in 9,357.606 seconds and records 537 artifacts; an independent
  unprivileged verification rechecks every artifact, phase log and installer
  manifest reference. A separate streaming archive audit matches all 114,710
  tracked members and 138 symlinks against exact Git blob identities, executable
  modes and root ownership, without extracting the archive. Package payload
  acceptance, SDK admission, ISO creation, boot testing and performance qualification remain
  open. The installed source lifecycle attempt separately exposed disabled
  UFS ACL support; the verified mount correction and retry retain the failed
  attempt. [Checkpoint](../../verification/native-sdk-build-development.json).

- **Priority:** P1
- **Owner:** release Component, source and ports forks, native framework lifecycle
- **Direction:** Make the complete source and ports Component build, test, package, ISO creation and installation system available on the operator development workstation at /usr/src and /usr/ports, managed by Literate AI.
- **Conclusion:** Preserve the running desktop and existing data; deploy editable fork checkouts and the qualified framework, then prove unchanged and changed-input incremental builds, tests, package provenance, ISO creation and installation against exact native inputs. Checkout availability alone does not complete this work.
- **Depends on:** COMP-001, PERF-001
- **Parallel migration:** [Workspace and executor comparison](native-workspace.md).
  The operator prioritizes a common `litai-dev` interface and substantial elapsed
  time reduction over preserving old build interfaces. Establish an independent
  `/usr/daemonarchy` hierarchy and wrap selected native make targets first;
  choose Bazel or another executor using equivalent native measurements.
  **Next action in progress:** deploy the reviewed ports metadata from
  [ports PR #7](https://github.com/jordanhubbard/daemonarchy-ports/pull/7) through
  a new exact workspace selection, then connect source/ports retained build
  profiles to the installed common CLI;
  qualify real target execution before selecting the cut-over.
- **Source prototype:** [Five-owner retained profile](../../verification/native-source-profile.json)
  at source commit `0d7583758a2f9eadc83fd5077ec2957522cbc9ab` passes both source CI
  runs. Installed native execution has produced selected compiled products;
  terminal run evidence, original privileged tests, independent acceptance and
  per-unit packages remain open. Preserve the running build-worker overlay and
  the operator's preceding preview selection. Framework #84 owns the separately
  measured strict-SBOM overhead; its repair needs full and installed/native renewal.
- **Subsequent build-worker preview:** framework `ca604c00` passes the complete
  local regression (1,855 passed, 42 skipped) and seven installed native SBOM
  checks. The [preview record](../../verification/native-development-preview-ca604c00.json)
  binds its canonical wheel, reviewed source rebind and corrected native profile.
  All 62 source-controller checks pass on FreeBSD. The source lifecycle is
  finished with captured CLI exit 2 after 2,037.584 seconds. Compilation and
  documentation have empty stderr; original tests report 23 passes and one
  root-required skip. The lifecycle correctly refuses the unauthorized skip;
  independent acceptance, source/ports package admission and cut-over remain
  open. Framework #85 owns scoped secondary-test-user access.
- **Qualified controller renewal:** framework `d6070ba5` passes the full
  regression (1,865 passed, 42 skipped) and installed-wheel qualification. Its
  [renewal record](../../verification/native-development-preview-d6070ba5.json)
  binds the verified controller dependency wheelhouse and reviewed source
  rebind. Native dependency production completed with exit 0 in 991.19 seconds;
  the verified 37-distribution closure bootstraps on the native worker and the
  disposable guest. Installed native checks report 29 passes, one optional
  source-corpus skip and no failures. Three warm input verifications have a
  median of 9.227105 seconds versus 19.794351 seconds for the baseline; this
  is not a whole-build comparison. The guest also verifies installed module
  bytes and real Ed25519 signing. Seven isolated
  native ACL checks cover selected reads, denied unrelated/new-file access,
  denied writes, revocation and exact original ACL restoration. This backend
  probe does not implement framework grants or complete original acceptance.
  A subsequent [original-suite guest probe](../../verification/original-native-suite-guest-probe.json)
  passes all 24 reviewed cases with no skips, including privileged deallocation
  and both unprivileged cases. It transfers the retained native products and
  uses guest base tools. The failed first probe exposed default-deny inheritance
  inside writable fixtures; the second scopes writable inheritance to that
  subtree and restores all pre-existing ACLs exactly. This remains a manual
  capability probe, not installed framework grants or lifecycle admission.
- **Installed candidate renewal:** Framework `6e370033` passes the complete
  controller regression (1,912 passes, 86 skips), exact clean-commit wheel gate
  and isolated native installation with 37 verified distributions. Native module
  bytes, Standard policy, signing and SQLite match. All 24 original source cases
  pass with no skips, including both previously denied launchers. All 11
  independent acceptance observations match their declared exits and exact stream
  hashes, including the expected invalid-input failure. Cleanup succeeds, the
  prefix ACL is root-only again and no nullfs mounts remain. The retained
  local-runtime receipt is admitted and all 34 records verify. This is not a
  canonical Standard lifecycle receipt, SDK, pkg or release qualification. The
  [checkpoint](../../verification/native-development-cli-6e370033.json) preserves
  that boundary. No physical workstation selection changes.
- **Installed prefix access gap:** The preceding `587ad3f1` framework run compiles
  the reviewed source and builds its documentation, then passes 22 of 24 original
  cases. Two unprivileged launchers fail before their test bodies because the
  allocation prefix remains private mode 0700. Mount cleanup succeeds; independent
  acceptance and admission are not reached. The scoped upstream repair passes
  16 native source-level checks, including integrated receipt handling with a
  protocol-peer allocation. The renewed installed candidate now reports all 24
  original cases and all 11 independent checks passed, with successful cleanup
  and retained local-runtime admission. Canonical SDK and package admission remain open.
  [Development evidence](../../verification/native-prefix-search-development.json)
  preserves the failed command identities and distinguishes the repair probe
  from actual installed qualification.
- **Secondary access development:** [Framework PR #87](https://github.com/jordanhubbard/literate-ai/pull/87)
  now contains the numeric identity and descriptor ACL backend; full local
  regression passes (1,879 passed, 51 skipped). A live allocation-bound source
  prototype passes all 24 original cases and restores permissions and account
  state. The captured SDK has 352 directories and 28 links, so a separate
  read-only-view capability probe now supplies the selected integration direction.
  Its kernel flags, rejected writes, alias reads and cleanup pass. With the
  complete byte-verified SDK mounted readonly, all 24 original cases also pass
  with no skips, using two permission resources and two readonly/nosuid mounts.
  Original compiled programs/body, accounts and cleanup remain verified. The
  launcher is probe-generated; reviewed root/unprivileged dependency observations,
  installed lifecycle integration and receipt/package admission remain open.
  [Development evidence](../../verification/native-secondary-access-development.json)
  separates published backend code from the private source probes.
  The later local framework checkpoint `d3b8c278` passes eleven native source-level
  checks without skips in 797.989 seconds, including local orchestration,
  secondary-account access, independent acceptance, cleanup-bound admission and
  payload use after run retirement. That lifecycle fixture uses a protocol-peer
  inspector. A separate allocation-owner probe now uses fresh process and QMP
  observations of the actual supervised guest, verifies two inspections of the
  same instance and refuses insufficient lifetime with permanent revocation.
  Neither result qualifies an installed distribution or reusable provisioner.
  Source checkpoint `dcac180c844` prepares the original suite for reviewed runtime
  and product views and explicit unprivileged-user selection; 62 controller checks
  pass with four native-only skips. Its selected native profile is not yet run.
- **Historical framework evidence:** [69 native retained-project checks pass](../../verification/native-retained-acceptance.json) at checkpoint `567e0f8a4092`. Its full regression, installed-wheel qualification and public runtime/receipt integration were pending at that checkpoint. The newer runtime and source-level results above retain their separate scopes; complete native wheel-smoke and product lifecycle qualification remain open.
- **Implementation:**
  - [x] Prepare conventional editable source and ports checkouts, framework tooling and a documented operator entry point. [Native checkpoint](../../verification/operator-development.json): `/usr/src` is current at the reviewed source-fork commit, and isolated `litai-dev` validates it with the exact bound framework wheel. The stable CLI remains installed; complete lifecycle remains open.
  - [x] Deploy independent source/ports checkouts, control, objects, staging,
    packages, cache and evidence below `/usr/daemonarchy`. The
    [workspace checkpoint](../../verification/native-workspace.json) verifies the
    same exact selection on both native roles and separate ZFS storage outside
    boot environments; all eight workspace checks pass on each FreeBSD host.
  - [ ] Qualify regular upstream imports without wrapper edits throughout upstream
    source directories. The independent-Git fixture passes fetch/pin preservation;
    full native refresh and selection/cut-over acceptance remain open.
  - [x] Probe actual make targets for the original parser/utility and the LZ4 port
    in isolated outputs. The PIE library variant links correctly; default upstream
    port checks and native pkg creation pass. Preserve the first link failure.
    The original 24-case source ATF inventory now records 23 passes and one
    root-required skip; privileged and independent acceptance remain open.
    These direct-make diagnostics are not installed LitAI target qualification.
  - [x] Install the exact candidate wheel on both native roles and validate
    both reviewed projects and all five native locks in separate review checkouts.
    The [candidate checkpoint](../../verification/native-development-cli.json)
    records dependency/import smoke checks, preserved active selection and
    missing receipts. This qualifies metadata availability, not target execution.
  - [ ] Expose selected source and ports targets through the same installed
    `litai-dev` build/test/package interface; retain native make as the first
    execution bridge and compare candidate action executors honestly.
  - [ ] Designate and exercise cut-over with equivalent output/acceptance,
    clean/warm/change timings and rollback to the preceding workspace selection.
  - [ ] Admit native source and ports units, dependencies and versioned packages into the installed Literate AI lifecycle.
  - [ ] Run clean, unchanged and changed-input build/test/package/ISO workflows with isolated outputs and demonstrate installation and recovery.
- **Evidence:**
  - [x] Native checkout identities and cleanliness, installed CLI and discoverable commands are verified on the operator workstation.
  - [ ] Complete Component ownership and dependency closure, exact provenance, correct incremental invalidation, actual tests and package outputs pass.
  - [ ] Measured ISO creation and actual installation/recovery evidence match the exact source and ports selections.

### [ ] TESTISO-001 — Prepare the 1.2 hardware test ISO before physical qualification

- **Priority:** P1
- **Owner:** release assembly and source/ports integration
- **Direction:** Produce an isolated exact-input test ISO carrying the reviewed fixes before asking the operator to run hardware qualification.
- **Conclusion:** Prepare and qualify assembly independently of final release publication; physical acceptance is downstream of the test artifact.
- **Depends on:** DEBUG-001
- **Loader selection:** [Exact live-only EFI/Lua selection](../../verification/test-loader-selection.json)
  is prepared and hash-checked against committed source and native development
  evidence. Eight controller/native staging and selection controls pass, including
  hardlinked jail preservation and signed-payload conflict refusal. Native exact
  bundle preparation passes. Native assembly now produced `daemonarchy-1.2-test1-amd64.iso`
  (SHA256 `146d0a7127472f1d2e8c05cedc2d54e6c91c1aa0988c5cc8506b03d12fbc7aaa`).
  Actual EFI boot payload, installer sets, live kernel, embedded packages and full
  live-runtime audit pass. Disposable UEFI install/reboot qualification passed,
  including exact installed ABI/kernel and all three stock loader copies. The
  live-shutdown WITNESS lock-order warning remains an explicit known observation.
  [Artifact record](../../verification/test-iso-1.2-test1.json) binds these results.
  This explicitly requested preview uses retained original-source assembly;
  canonical native lifecycle admission and final release qualification remain open.
- **Implementation:**
  - [x] Allocate a private per-run ISO staging directory; preserve preceding artifacts; bind exact loader, kernel/world sets, jail, ports, modules and checkout selections; coordinate native dispatch with active worker ownership.
- **Evidence:**
  - [x] Retain staging isolation/refusal controls, input identities, native assembly results and ISO hash; announce readiness only after a real test artifact exists. Keep hardware and final 1.2 release obligations open.

Patched composition `23d0b678` is undergoing exact Linux wheel renewal while its
native Windows gate continues. Completed SDK/PTY guest work is retired by normal
shutdown before the original deadline; QEMU exits zero and the original disks,
prefixes and raw evidence remain retained. Wheel and subsequent native guest
renewal are serialized to preserve the 40 GiB backing-volume reserve; no cache or
evidence deletion is performed. This is resource scheduling, not a gate waiver.

The [iflib debugnet ownership correction](../../verification/iflib-debugnet-ownership-development.json)
addresses another prerequisite found during the resumable-debugger audit.
Production START changes receive allocator pointers and batching, but END leaves
them changed; the multi-list loop also repeats list zero. The original callback
fails three sanitizer controls on macOS and FreeBSD. The candidate passes exact
pointer/batching restoration across repeated sessions and every receive list.
Exact kernel/recovery renewal, ring-buffer provenance and non-panic resume remain
open; no panic-only guard is removed. Source issue #16 owns this correction.
The exact `4f46a741fb2` candidate kernel passes its clean GENERIC build in
526.747 supervised seconds with four jobs and unchanged 2400-second supervision.
All three products share build ID `0a71d6f0677d45edf987fbd288d58febd07a949a`;
build evidence and transfers reverify by hash. A new bounded private-wire pair
has handed off through the loader. Before/during/after live allocator inspection
and ordinary recovery renewal remain required.

The optional-import Windows full gate on preceding `8f1b7df6` is now terminal:
it times out in wheel qualification after 5400.328 seconds, before unit tests.
Its supervisor terminates the owned process tree and preserves all temporary
evidence. Earlier compile, lint and documentation checks passed. This is a failed
qualification, not a later-metadata or release result; inspect retained wheel
stages before another complete attempt without widening the bound.

The [live iflib recovery check](../../verification/iflib-debugnet-live-recovery-development.json)
now passes three native sessions on the exact repaired kernel: two detachments
and one abrupt client exit. Before/during/after memory reads prove allocator
restoration, cleared saved/active state and the original batching setting;
registers and reset work after peer closure. Native GDB sees 104 threads. Both
owned VMs stop normally within their original bounds. Real-NIC coverage is one
2048-byte receive list; Netdump renewal and non-panic resume remain unqualified.

The [iflib-kernel Netdump renewal](../../verification/iflib-debugnet-netdump-development.json)
passes with native panic/version/backtrace and 104-thread inspection. Independent
reconstruction from 116,400 captured data messages covers all 165,834,752 bytes
without gaps or overlap and matches the received core hash. Both bounded VMs
stop cleanly. The new ESP omits unselected modules/firmware and shares immutable
product files by verified read-only inode; retained cases are preserved. This
completes the scoped VM recovery renewal, while buffer provenance, non-panic
resume, authentication, physical NIC and final lifecycle admission stay open.

The [preserved Windows fixture diagnostic](../../verification/framework-windows-validation-diagnostic.json)
separates an 11.172-second stale-review refusal from successful initialized-project
validation in 9.187 seconds (6.206 seconds inside the operation). Manifests and
installed module bytes stay unchanged. These single ordered observations do not
identify the full gate bottleneck or qualify its wheel. Next: retain per-operation
wheel-smoke timings and investigate the expensive native stages.

The [Windows wheel timing follow-up](../../verification/framework-windows-wheel-timing-development.json)
is implemented in [framework PR #124](https://github.com/jordanhubbard/literate-ai/pull/124):
each native gate attempt selects a unique report, and completed spans replace
atomically. Partial-write integrity fails against the original writer and passes
on macOS and real Windows. Eight focused tests and driver review pass. Exact
`46c14963` now runs complete configured host lifecycle renewal under its existing
3600-second bound. Its receipt is not promoted, and final full native qualification
remains open; report files do not establish a passing gate.

### [ ] HW-002 — Diagnose MacBook installer interruption and qualify storage recovery

- **Priority:** P1
- **Owner:** installer and diagnostics Components with native FreeBSD storage
- **Direction:** Resolve the reproduced Apple ANS2 fatal storage event before MacBook hardware acceptance for the next release.
- **Conclusion:** Package registration and progress do not establish completion; preserve the interrupted target and controller evidence, then qualify a storage correction and complete native installation and desktop acceptance.
- **Depends on:** none
- **Implementation:**
  - [x] Reproduce and isolate the ANS2 fatal I/O and implement a tested correction. The fault is the driver releasing command IDs before the CQ head doorbell acknowledges their completions; see daemonarchy-src PR 34 and docs/testing-macbookpro16-1-nvme-20261026.md.
  - [ ] Select the correction into the source integration branch, then repeat fresh-image installation, package integrity and hardware checks with a release kernel that contains it.
- **Evidence:**
  - [ ] 2026-10-22 physical reproduction, exact cached package recovery under four trackers, and full integrity after a forced power-off are recorded in docs/testing-macbookpro16-1-installer-20261022.md. Instrumented Navi14 tests isolate a graphics-queue initialization boundary. A 2026-10-23 FreeBSD-current review produced an isolated native-compiling NVMe candidate with upstream reset recovery, but it is not selected or hardware qualified. Storage cause, false-success explanation and complete hardware acceptance remain open.
  - [x] 2026-10-26: the ANS2 fatal status (CSTS.CFS) reproduces in seconds with raw random writes at queue depth 4 or more, on both the 1.1.1 and 1.3.1 kernels, so it is not a 1.3.1 regression. Acknowledging each completion through the CQ head doorbell before its command ID can be reused, and never repeating an unchanged doorbell write, passed 2.4M QD-8 and 4.8M QD-48 random writes, the original 3-round stress, and 5 rounds over all 1,906 cached packages, with no recovery events. The machine now boots that kernel by default. Recorded in docs/testing-macbookpro16-1-nvme-20261026.md; fresh-image installation and the false-success explanation remain open.

### [ ] HW-003 — Acquire and install required laptop firmware

- **Priority:** P1
- **Owner:** installer and compatibility Components with native FreeBSD driver integration
- **Direction:** Support laptops that need device-specific firmware during installation, including a MacBook whose macOS installation was wiped.
- **Conclusion:** Firmware acquisition is part of installer completion when a selected built-in device requires it; a network panel cannot compensate for an unattached driver or absent firmware.
- **Depends on:** HW-001
- **Implementation:**
  - [ ] Identify required firmware and board configuration from the actual PCI/device and driver identity; select an online source with verifiable provenance or operator-supplied local media, including an Apple recovery-image path for BCM4364 without installed macOS.
  - [ ] Verify integrity and model match before copying into the target, retain source and digest evidence without private data, and make acquisition retryable without repeating disk partitioning or package installation.
  - [ ] Install firmware in the driver's expected target path, enable its loading at boot, and check actual device attachment, scan, association, traffic and reconnect after reboot; report a clear incomplete-device result when the driver or firmware is unavailable.
- **Evidence:**
  - [ ] Fresh physical MacBook installation proves acquisition and rebooted BCM4364 operation; offline-media and failure/retry cases pass. A private diagnostic module attaches BCM4364/4 to net80211 and returns access points on repeated physical scans using B3 firmware, `bali-HRPN-u` board data, the Apple seed footer, CLM and TxCap blobs. Earlier physical WPA2 association, DHCP and gateway traffic passed on the installed system, but the 2026-10-23 installer session lost data traffic while the driver ignored a firmware link-down event and continued reporting association. An experimental link-loss change did not pass DHCP testing and was rolled back; see docs/testing-macbookpro16-1-wifi-preview-20261022.md. Fresh-image loading, stable reconnect after reboot, maintainable driver integration and installer firmware acquisition remain open. Manually staged files do not qualify redistribution.
  - [ ] Offline acquisition candidate, controller-tested only: the MacBook firmware step reads the internal APFS disk (never mounted or written) or a second FAT/UFS stick mounted read-only, ahead of the Ethernet download. Both use the same file pins and provenance, and Apple files stay off the public ISO. Physical proof of 7-Zip APFS reads from the FreeBSD disk device and of the stick search is still required; see docs/application-note-macbookpro16-1.md.
  - [ ] An isolated signed-handoff candidate now offers Apple recovery download or local-image import in the MacBook installer menu, verifies the private stage before disk writes, records provenance in the target, and binds the four board-file hashes to both signed boot and runtime inventories. FreeBSD's existing veriexec hook allows an ordinary read of a mismatched registered file; the candidate policy patch denies that read. The pinned native policy kernel and both EFI loaders built with disposable credentials. A separate OVMF Secure Boot guest booted the patched policy kernel and reported `EAUTH` for a tampered registered firmware file; identities and limits are in docs/testing-macbookpro16-1-firmware-handoff-20261023.md. Physical firmware acquisition, stable Wi-Fi traffic, rebooted driver attachment and physical enforcement are still required. This candidate is not release qualification.

  - [ ] On October 23, a kernel-matched diagnostic module on the installed MacBook completed WPA, DHCP, 60 gateway probes and 27 access-point entries; a Wi-Fi-only route returned eight Internet probes after releasing a stale wired address. Roaming briefly dropped carrier and recovered. The installer candidate now clears a disconnected wired lease before selecting the wireless gateway; its targeted test passes on Linux and native FreeBSD. A fresh installation, packaged-driver reboot and sustained traffic remain open.

### [ ] DEBUG-002 — Preserve approved hardware-debugging sessions across reboot

- **Priority:** P1
- **Owner:** diagnostics and installer Components
- **Direction:** Support repeated hardware bring-up cycles without deleting the previous grant or requiring fresh approval of the same agent.
- **Conclusion:** Retain private approval and host identity on installed storage; refresh runtime generation, refuse unknown keys on background resume and preserve explicit revocation.
- **Depends on:** none
- **Implementation:**
  - [ ] Implement and natively exercise durable resumption, legacy adoption, boot-console startup and explicit Unpair; verify on the physical MacBook.
  - [ ] Show the installed desktop's remote-debugging state in its menu bar while a grant or listener is active. Include whether the agent is connected, the listener address/port, and a clear path to revoke access; update promptly after reboot, disconnect and Unpair. The rescue menu is hidden once the desktop is up, so it cannot serve as the only local status display.
- **Evidence:**
  - [ ] Native real-SSH persistence, existing lifecycle and delayed-network console fixtures pass. Physical reboot retains the same agent approval and host identity; manual Resume works. One reboot resumed unattended SSH about fifteen seconds into boot, but a later boot reached the desktop with the listener inactive until manual Resume. The 60-second network retry limit is a plausible cause, not yet proven by boot timing. A retry-while-approved correction passes native console tests, including simulated readiness after 60 seconds. The watcher previously exited after its first successful listener start, leaving a later listener failure without recovery; a continuous-watch correction passes the console fixture on Linux and native FreeBSD, including simulated listener loss and explicit revocation. Neither correction has passed a fresh physical reboot yet. Desktop menu-bar status is physically visible; packaged-image integration remains pending.
  - [ ] A desktop status candidate publishes only grant, listener, connected-agent, address and port fields to a world-readable runtime file. The native real-SSH fixture passes approval, SFTP, disconnect, reboot suspension, resume and Unpair status transitions. On October 23, the updated helper and network panel were live-installed on the MacBook with the retained grant intact; the public status named both IP addresses and the listener, QML formatting passed, and the restarted desktop shell answered IPC. The operator confirmed that the visible menu shows the remote-debugging section, listener address and Unpair control. Control actions and reboot behavior still need physical checks. The installed desktop package remains 1.1.1 after its Wi-Fi setup failure.
  - [ ] The installed debugger now retains the active Wi-Fi profile and wireless parent with the root-only pairing grant. On the MacBook, a live update saved a mode-0600 profile matching the active configuration, then recreated `wlan0`, completed WPA and reacquired DHCP after a controlled wireless teardown while Ethernet and the approved listener stayed active. Public-status publication also saved the profile automatically. A full reboot over Wi-Fi awaits the packaged driver in the new ISO; the live USB still needs a durable medium for cross-reboot state.

### [ ] DEBUG-003 — Deliver bidirectional loader, mountroot and panic network debugging for 1.4

- **GitHub issue:** [#33](https://github.com/jordanhubbard/daemonarchy/issues/33), milestone **1.4.0**; source [#21](https://github.com/jordanhubbard/daemonarchy-src/issues/21), also in 1.4.0.
- **Release scope:** [Current 1.4 plan](release-1.4.0.md) supersedes the [earlier 1.3.2 plan](release-1.3.2.md). Preserve the published 1.3.1 ISO, tags, feeds, signing material, source and native evidence. Historical product #27 closed after prerequisites merged; complete-feature acceptance remains open here.
- **Priority:** P0
- **Owner:** diagnostics, owned FreeBSD source and release integration
- **Direction:** Provide explicitly enabled plain wired console control without SSH, a new key or pairing from boot blocks/loader through a forced `mountroot>` prompt, early startup and deliberate panic. Include kernel/module selection, variables and Lua, bounded polled bidirectional transport, retained last-stage output after reset and orderly native-NIC takeover.
- **Conclusion:** A preloaded NIC kernel module does not supply loader networking or establish the early transport. Loader-only output, inventory and initialized-driver NetGDB do not satisfy the MSI reset use case.
- **Depends on:** DEBUG-001 prerequisites; actual hardware reports for physical NIC/backend admission. Loader, VM mountroot and panic work proceed independently of the MSI report. Firmware SNP must never be called after `ExitBootServices`.
- **Preflight evidence:** Existing [inventory](../../verification/earlynet-131-inventory-development.json) and [USB report persistence](../../verification/earlynet-usb-report-development.json) retain their original scope and hashes. Neither captures kernel logs.
- **Native VM progress:** The [October 26 native run](1.4-coverage-ledger.md#october-26-native-debug-003-run) passed 8 of 10 bhyve cases on source `4bfe2344af74`. The [rerun on source `fd259a1787ab`](../testing-1.4-network-debug-20261026.md) (merged source PR #33) then passed the three open cases on their first attempt: `d1-loader-ops` with a TFTP `net0:/kernel` load, `d3-handoff-vtnet` with the rootconf marker, and the two-NIC `d3-early-em` with a pre-driver panic and DDB over the e1000 early transport. These are VM backends only. Physical NICs, the MSI built-in NIC, anything before `SI_SUB_KMEM`, downloaded module selection and release acceptance stay open, and the passing cases from the first run have not been repeated on the new build.
- **Implementation:**
  - [ ] Specify protocol/CLI and implement plain-mode activation, remote commands, variables and local Stop/recovery.
  - [ ] Implement bounded direct UDP staging, TFTP pulls, disk/staged kernel/module boot and downloaded Lua execution through standard loader APIs.
  - [ ] Identify the actual NIC/backend from retained reports, implement kernel-owned polled transport and loader handoff, and exercise remote input/output at a forced `mountroot>` prompt.
  - [ ] Qualify deliberate pre-driver/later panic, hard-reset retention, normal boot, transport faults and safe native-driver takeover; package the controller and separate 1.4 diagnostic image in isolated output roots.
- **Evidence:**
  - [ ] Complete the plan's native/UEFI loader, boot-block, forced-mountroot, panic, disk-boot, fault and recovery matrix with exact artifact identities and the earliest covered stage stated honestly.
  - [ ] Retain independent pre-driver panic/reset captures, successful normal boot and actual MSI built-in-NIC evidence.
- **Reset-surviving boot trace (MSI):** The MSI's RTL8125 has no early kernel backend, so a [hardware trace stick](../boottrace.md) records each SYSINIT, device probe/attach, config hook, mountroot and panic in the UEFI variable `DaemonarchyBootTrace` before the step runs (opt-in `debug.boottrace=1`; coarse by default within a `QueryVariableInfo` byte budget, `debug.boottrace.from=N` zooms in). The loader files each boot's trace on the stick's `DATRACE` partition and boots the next queued experiment unattended; `tools/windows/read-boottrace.ps1` is the Windows fallback. The loader change also accepts UNDI 3.1 ROMs reporting minor version 0x10 (the MSI's RTL8125). The [first MSI run](../testing-1.4-boottrace-20261027.md#first-physical-run-msi-raider-18-hx-ai-ami-e1824ims317) proved the loop on AMI E1824IMS.317 but found only 55 KiB of NVRAM free; 64-byte breadcrumbs and an 8–16 KiB reserve now fit about 250 steps from `SI_SUB_CONFIGURE` in that space (QEMU with a store filled to 52 KiB). The dedicated image is tracked as DEBUG-004. Preserve controller logs on loss; do not repeat exhausted ACPI/SMP/panic tunable comparisons or infer a reset cause from silence.

### [ ] ARCH-001 — Add aarch64 as a second supported architecture for 1.4.0

- **GitHub issue:** [#62](https://github.com/jordanhubbard/daemonarchy/issues/62), milestone **1.4.0**.
- **Priority:** P1
- **Owner:** release integration, owned FreeBSD source and ports, installer and desktop packaging
- **Direction:** Build, package, install and boot Daemonarchy for aarch64 alongside amd64 from the same selected source, ports, desktop and compatibility revisions. Use virtual machines as the qualifying test bed now; enlist Apple M1-M4 laptops as test machines only after the virtualized image passes its matrix.
- **Conclusion:** Each architecture keeps its own artifacts, feeds, timings and evidence; amd64 results never qualify aarch64. Virtualized acceptance qualifies only virtualized operation, and a laptop result is scoped to its exact model and execution mode (hosted VM or bare metal).
- **Depends on:** PERF-002, DEBUG-003
- **Implementation:**
  - [x] Inventory aarch64 build, ABI and package gaps in the selected source and ports closure, and add aarch64 as a typed variant in the release input graph. The read-only [aarch64 inventory](../aarch64.md) lists the blocking gaps: the desktop closure (Hyprland, Chromium, `mise`, `edk2@bhyve`), no aarch64 DRM KMS, amd64-only source build tooling and diagnostic kernel, and the loader entropy fallback. The release graph keys every unit on one [architecture variant](../release-input-graph.md#architecture-variants). The product build, installer and release asset check are architecture-aware without a native aarch64 run.
  - [ ] Build world, kernel, signed aarch64 package feeds and an aarch64 UEFI installer image under the same LitAI custody, cache and graph rules as amd64. Native progress, outside LitAI custody so far: world and the GENERIC kernel are built at `d63d77f4`, and `poudriere testport` of `x11-wm/hyprland` passed with ports#28 at ports `3e782916` ([record](../aarch64.md#worker-record-native-kernel-jail-and-hyprland-2026-10-26)). A native bulk of the image package closure then built 580 packages and fetched 463. One failed: `x11-themes/aether`, whose npm cache has no FreeBSD arm64 bindings. It used [ports#30](https://github.com/jordanhubbard/daemonarchy-ports/pull/30), which drops `chromium` and `aether` on aarch64 and is still open. From that bulk came an unsigned development feed (360 payloads) and an unsigned `daemonarchy-1.3.1-aarch64-dev.iso` (`6d6f1fe3…`), built by the unmodified `build-iso.sh` from `d63d77f4` release sets. The ISO boots under QEMU/EDK2 to the installer menu ([record](../aarch64.md#worker-record-native-bulk-unsigned-feed-and-uefi-iso-2026-10-27)). No signed or published feed or image exists, and nothing here is under LitAI custody.
  - [ ] Install the initial aarch64 worker: a FreeBSD arm64 VMware guest on an Apple silicon Mac from the operator-supplied, checksum-verified arm64 `dvd1` ISO; admit it as the native aarch64 build host and first test target. The [bring-up plan](../aarch64.md#worker-bring-up-freebsd-arm64-under-vmware-on-apple-silicon) gives sizing, the 15.1-RELEASE `dvd1` to selected-16 step and the separate test guests. The guest is installed from 15.1, and a verified 16.0-CURRENT snapshot (20261019, `041802b362aa`) is staged and activated in boot environment `be16`, with 15.1 kept for rollback ([record](../aarch64.md#worker-record-151-to-160-current-in-a-boot-environment-2026-10-26)). The guest now runs the native GENERIC kernel built at `d63d77f4`, from be16 alone; 15.1 is gone. Its `16aarch64` jail was built from the same source ([record](../aarch64.md#worker-record-native-kernel-jail-and-hyprland-2026-10-26)). It passes the `native/worker-template.json` checks. Release-graph admission is still to be defined: `native/inspect-worker-allocation.py` serves only QEMU-supervised workers. The 200G disk is below the 400 GiB sizing.
  - [ ] Run install, boot, upgrade, rollback, desktop and network-debug cases in separate aarch64 VMware guests.
  - [ ] After the virtualized matrix passes, enlist M1-M4 Mac laptops for the execution modes they can actually support, recording model, firmware and mode.
- **Evidence:**
  - [ ] Native aarch64 build, package, signature and ISO records with exact artifact identities, separate from amd64.
  - [ ] Retained aarch64 VM install/boot/upgrade/rollback/desktop/debug matrix results, failures included.
  - [ ] Scoped per-model Apple silicon laptop records, if and when enlisted, with any unsupported mode stated honestly.

### [ ] LIVE-001 — Offer a live desktop from the installer media without touching the disk

- **GitHub issue:** [#67](https://github.com/jordanhubbard/daemonarchy/issues/67), milestone **1.4.0**.
- **Priority:** P1
- **Owner:** installer, live image and desktop packaging
- **Direction:** Add a boot option that starts a minimal Daemonarchy desktop entirely from the ISO and RAM, matching what the FreeBSD installer media already offers. It must show whether the desktop boots on the target hardware and provide enough application surface to run the complete installation graphically instead of on the TUI.
- **Conclusion:** The live set is deliberately minimal: compositor, terminal and a graphical installer front-end over the existing install engine and configuration file, not the full application set. The read-only ISO root is made usable without unionfs: /etc, /usr/local/etc, /root and /home are copied into tmpfs at boot, and GPU payloads are added only on tmpfs layers mounted with -o union, which can add files but never replace ISO files. A unionfs probe over the ISO's /etc stopped a FreeBSD 16-CURRENT host during pw's password database rename (crash dump pending), so unionfs is not used. GPU modules come from the ISO repository, so no network is required. Nothing is written to any disk until the operator starts an installation, and a failed desktop start falls back to the TUI installer. The live account has passwordless sudo: the operator decided on 2026-10-26 that a live demo and installer controlled entirely by the person at the keyboard is not a server install, so no password prompt is needed.
- **Depends on:** PERF-002
- **Implementation:**
  - [ ] Install a minimal live desktop package set into the image at build time and move the 2 GiB budget from the raw ISO to the published .xz asset. The .xz budget is in place (#70); the live set, trim and package checks are in draft PR #74 and await a native image build.
  - [ ] Add a loader menu entry and live rc path: tmpfs copies of /etc, /usr/local/etc, /root and /home, GPU module selection from the ISO repository, an unprivileged live user and automatic desktop start with fallback to the TUI installer.
  - [ ] Provide a graphical installer front-end that writes the same install configuration and renders the installer's @@progress stream.
  - [ ] Keep pool import, disk swap and every disk write disabled on the live path until an installation is confirmed.
  - Controller implementation and stub tests for the remaining items are in draft PR #74; none is checked until exact-image native evidence exists.
  - First native preview ([record](../testing-1.4-live-desktop-20261026.md)): raw ISO 3,504,902,144 bytes, `.xz` 1,573,059,812 bytes; the runtime audit passed; under bhyve the live boot, the no-supported-GPU fallback and the TUI default left the target disk unchanged. Desktop rendering, the graphical installation and the compositor-failure branch need QEMU/VirGL.
  - QEMU/VirGL on madmax ([record](../testing-1.4-live-desktop-virgl-20261027.md)): live1 fell back because of a module-extraction defect. Rebuilt live2 (`358b16b`) rendered Hyprland and the graphical installer, passed the forced compositor-failure fallback and network-page parity, left the target unchanged in every live boot, and completed a graphical whole-disk install that boots to the installed desktop. Operator ruling: firmware without a SecureBoot variable counts as Secure Boot off; `secureboot_detect_enforcement` now says so instead of refusing, and an unknown value is still refused (`tests/secureboot-options.sh`).
  - live4 development candidate ([record](../testing-1.4-live4-20261027.md)): under bhyve the live boot by menu entry 2 and the TUI default left the target unchanged, as in live1 to live3. **`T` no longer selects the live desktop:** src#35's "Boot Trace" entry also aliases `t`/`T`, and the menu runs the Boot Trace entry. One of the two aliases must change.
- **Evidence:**
  - [ ] Exact-image VM runs reaching the live desktop and completing a graphical installation, with before/after disk digests proving the live path wrote nothing until install.
  - [ ] Fallback to the TUI installer when the compositor cannot start, and the TUI installer default unchanged.
  - [ ] Scoped physical live-desktop records per tested machine, including the MacBookPro16,1.

### [ ] NET-001 — Make the installer network bring-up proactive and robust

- **GitHub issue:** [#80](https://github.com/jordanhubbard/daemonarchy/issues/80), milestone **1.4.0**.
- **Priority:** P1
- **Owner:** installer, live image and unattended install
- **Direction:** Before any disk change, find every wired, USB-tethering and wireless adapter (including devices still waiting for firmware), probe all wired ports for DHCP concurrently with bounded timeouts, choose the primary connection, prove DNS with direct lookups (DHCP servers, then Cloudflare, Google and Quad9, then a user server that must answer), make the clock usable, load missing firmware, and bring up Wi-Fi; Wi-Fi first when no cable works.
- **Conclusion:** One shared pipeline (network-bringup) serves the text configurator, the live graphical installer and unattended CIDATA installs. DNS is proven by a record lookup sent to the server, never by ICMP. A usable clock is no earlier than the image build and inside the signing certificate validity; network time is tried before the manual clock. Every step is bounded, retryable, reported in plain language and logged; unattended installs honor net_* answers and fail with a clear message instead of prompting.
- **Depends on:** none
- **Implementation:**
  - [ ] Shared `network-bringup` library and step runner (discover, dhcp, dns, clock, firmware, wifi-prepare, Wi-Fi join), sourced by the configurator and run by `launch` for CIDATA installs; the configurator's network screen shows its findings and offers a primary override, a DNS server entry and a rerun. Verified DNS that replaced broken DHCP DNS is pinned on the installed system with `supersede domain-name-servers`. Code-level only: `tests/network-bringup.sh` exercises every step against shimmed FreeBSD commands in hosted CI.
  - [ ] The live desktop's graphical backend (LIVE-001) calls the same steps instead of its own DHCP and Wi-Fi commands.
- **Evidence:**
  - [ ] Exact-image VM matrix: several NICs with only one offering DHCP, DHCP DNS broken, public DNS blocked with a user resolver, ICMP blocked, a wrong clock fixed by NTP and then by hand, and an unattended CIDATA run, with the retained network-check logs.
  - [ ] The MacBookPro16,1 BCM4364 path on physical hardware: offline firmware first, Wi-Fi-first ordering with no cable, then DNS and clock over Wi-Fi.

### [ ] DEBUG-004 — Ship a hardware bring-up trace image for developers and agentic researchers

- **Priority:** P1
- **Owner:** diagnostics, owned FreeBSD source and release integration
- **Direction:** Master a separate hardware bring-up / trace image (daemonarchy-hwtrace-VERSION-amd64.img) beside the install/live ISO: boottrace kernel and modules, the boottrace loader with the unattended experiment cycle as its only behaviour, /boot/d presets, a rescue root that saves dmesg/sysctl/pciconf/devinfo/acpidump to DATRACE when a boot reaches init, and the DATRACE queue/trace partition.
- **Conclusion:** Unattended cycling cannot coexist with the install ISO's interactive menu, so the trace loop is its own image type; the standard ISO keeps at most the interactive single traced boot.
- **Depends on:** DEBUG-003
- **Implementation:**
  - [ ] build-hwtrace-image.sh on the FreeBSD builder; tools/boottrace/stick.py for queues and traces; release-asset handling when published
  - `daemonarchy-hwtrace-1.4.0-dev3-amd64.img` (`f4aec0e6…`, unsigned) was built by main's `build-hwtrace-image.sh` from the live4 ISO and that ISO's kernel and loader (daemonarchy-src `74f81f1949d5`). Its serial copy under QEMU/OVMF filed a `configure_first` hang as INCOMPLETE and a normal boot to init with DUMPS, then stopped ([record](../testing-1.4-live4-20261027.md)).
- **Evidence:**
  - [ ] QEMU/OVMF multi-boot checks with a crowded NVRAM store; physical MSI Raider iterations

### [ ] GPU-001 — Qualify cross-vendor GPU diagnostics and a Daemonarchy showcase

- **Priority:** P1
- **Owner:** desktop and physical hardware qualification
- **Direction:** Add glmark2 diagnostics and a visually impressive Daemonarchy showcase with exact renderer evidence on AMD, NVIDIA and the Intel MacBook under FreeBSD.
- **Conclusion:** Planned 1.4 work; software fallback is diagnostic only and physical GPU qualification remains pending.
- **Depends on:** LIVE-001
- **Release / tracking:** 1.4.0; [issue #101](https://github.com/jordanhubbard/daemonarchy/issues/101); acceptance row A18. DEBUG-003 remains P0.
- **Implementation:**
  - [ ] Select retained packages where possible; record renderer/vendor/driver/API and measured FPS/frame times; SuperTuxKart is an optional existing alternative.
  - [ ] Identify the actual selected GPU on hybrid hardware; retain exact-image/package identities and settings. Software fallback never qualifies acceleration.
- **Evidence:**
  - [ ] Pending exact-image AMD, NVIDIA and Intel MacBook physical FreeBSD checks, explicit software-fallback classification and retained logs/visual evidence.

### [ ] NET-002 — Boot with the first usable connected interface without waiting for disconnected Ethernet

- **Priority:** P1
- **Owner:** installed-system networking and compatibility integration
- **Direction:** Trace installed boot separately from installer NET-001; skip missing/no-carrier interfaces and race bounded candidate DHCP safely.
- **Conclusion:** Source-level diagnosis (FreeBSD 16 `libexec/rc`, `sbin/devd`, `sbin/dhclient`; not yet a timestamped trace from an installed machine): with the installed `ifconfig_DEFAULT="DHCP"`, rc.d/netif only brings ports up and devd(8) starts `dhclient` on each `LINK_UP`. devd runs actions one at a time, and a foreground dhclient on a port with a link but no DHCP server (the MacBookPro16,1 `ue0` case) keeps sending DISCOVERs for its 60-second `timeout` before it backgrounds, so later `LINK_UP` events, such as `wlan0` associating, wait behind it. Meanwhile rc.d/defaultroute waits up to `defaultroute_delay` (30 s) because a DHCP port has a carrier but no default route exists. A port with no carrier costs at most `defaultroute_carrier_delay` (5 s); an absent port costs nothing. Separately, each dhclient-script adds a default route if none exists and rewrites resolv.conf, so concurrent leases publish in arrival order with no ownership. `ntpd -g` (`ntpd_sync_on_start`) and `netwait` (disabled) do not block boot. Implemented at code level (installer + `daemonarchy-netselect`); exact-image and physical timing evidence is pending, and no speedup is claimed yet.
- **Depends on:** NET-001 (shared installer semantics; installed-boot diagnosis is a separate boundary).
- **Release / tracking:** 1.4.0; [issue #102](https://github.com/jordanhubbard/daemonarchy/issues/102), related to [#80](https://github.com/jordanhubbard/daemonarchy/issues/80); acceptance row A19. DEBUG-003 remains P0.
- **Implementation:**
  - [x] First usable connected interface wins; serialize route/DNS publication, bound offline boot and retain failed-candidate diagnostics. DHCP and Wi-Fi installs add `background_dhclient="YES"` (no dhclient holds devd or rc), and the dhclient enter/exit hooks hand every lease result to `/usr/local/libexec/daemonarchy-netselect`, the only publisher of the default route and `/etc/resolv.conf`. It checks each lease outside its lock (gateway by ARP after one ping, as NET-001; DNS by a direct `drill` from the lease address, where any rcode proves the server reachable, so no ICMP or public endpoint is required), then under `lockf` records it and elects: class 3 (gateway + DNS) > 2 (gateway) > 1 (lease only); the first interface at the best class keeps ownership, only a strictly better class replaces it, and a devd `LINK_DOWN` or an ended lease fails over at once. Losers keep their address and background dhclient for late-link recovery but never publish. Static installs are unchanged, and a default route DHCP does not manage is left alone. Timestamped events with seconds since boot, the first-usable time and failed candidates are logged to `/var/log/daemonarchy-net.log`; `daemonarchy-netselect status` shows the per-boot state. Code-level only: `tests/installed-boot-network.sh` runs in hosted CI against shimmed FreeBSD commands (with real `timeout` and `flock`) and, when `DHCLIENT_SCRIPT` names FreeBSD's dhclient-script, the hooks inside the real script.
  - [x] Declared budgets: a candidate check takes at most 3 s (ping 1 s, then concurrent DNS queries 2 s each, at most 3 servers); boot waits at most 10 s for the first owner (`defaultroute_delay="10"`) and 5 s when no DHCP port has a carrier (`defaultroute_carrier_delay="5"`), so a fully offline boot waits at most 10 s; a late lease or link is used after login without blocking boot. A lock wait is bounded at 15 s.
  - [ ] Retain timestamped installed rc/DHCP traces from the exact image and prove offline boot meets its budget.
- **Evidence:**
  - [ ] Pending exact-image multi-NIC, absent/no-carrier Ethernet, Wi-Fi-only, late link, competing DHCP and offline boot timing tests, with boot-to-usable times against the 1.3.1 baseline. No VM or physical run has exercised the change; the MacBookPro16,1 `ue0` + `wlan0` case needs a physical boot.
