# 1.5.0 plan: the 1.4.2 scope, build speed and release-cycle speed

- **Status:** active
- **Owning queue item:** [BUILD-001](active-work.md#build-001-cut-freebsd-source-ports-iso-and-release-cycle-time-10x-with-literate-ai-14)
- **Supporting queue items:** [ADOPT-002](active-work.md#adopt-002-qualify-retained-native-execution-and-release-enforcement), [COMP-001](active-work.md#comp-001-model-complete-freebsd-source-and-ports-trees-as-components), [SRC-001](active-work.md#src-001-establish-owned-freebsd-source-builds-and-packages), [PERF-001](active-work.md#perf-001-execute-native-components-and-substantially-accelerate-iso-builds), [PERF-002](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140), [DEV-001](active-work.md#dev-001-provide-an-operator-ready-native-component-development-system), [RELEASE-001](active-work.md#release-001-deliver-a-qualified-literate-ai-release-workflow-in-14), [DESKTOP-001](active-work.md#desktop-001-ship-the-desktop-launchers-and-menu-entries-in-the-daemonarchy-desktop-package)
- **Completion / archival evidence:** pending; nothing here is claimed done. Done means the evidence listed under Acceptance below, retained with exact inputs.

Opened 2026-10-31 by operator decision. The operator's words: decrease the time required to
compile all of FreeBSD src, FreeBSD ports and the ISO mastering process using all applicable
features of Literate AI, also upgrading Literate AI in all Daemonarchy repositories to version
1.4 (top of tree), and improve the entire release engineering cycle by 10x.

## 1.4.2 is superseded by 1.5.0 and was never released

This release was opened as 1.4.2. The operator and the release coordinator renamed it 1.5.0 on
2026-10-31: the work adds user-visible features (the graphical package manager, Windows programs
and Steam, the aarch64 VirtIO GPU path, the Wi-Fi fix) and the BUILD-001 program, which is a
minor release under semantic versioning, and Literate AI's patch rule admits only bounded fixes.
No 1.4.2 tag, feed or image was published. Every 1.4.2 goal moved here without deferral and
keeps its own queue entry and acceptance text; the scope and the honest status text of the old
plan follow, unchanged in substance. The 1.4.1 plan and the [1.4.1 audit](release-1.4.1-audit.md)
describe the same items under the 1.4.2 name.

## Scope carried from the 1.4.2 plan

- **MacBookPro16,1 Wi-Fi: the dead associated state.** The BCM4364 driver
  (`if_brcmfmac-kmod`) can stall after association: the interface still reports
  `associated` and no traffic moves. Cause: `brcmf_link_event()` ignored every firmware
  `E_LINK` down while the VAP was in `RUN`, including a real link loss after the
  handshake, so net80211 and `wpa_supplicant` stayed associated while the firmware had
  dropped the association and tossed every frame (`tx_complete status=3`). The fix is
  merged ([daemonarchy-ports #37](https://github.com/jordanhubbard/daemonarchy-ports/pull/37),
  `e136408d`). Still open: it is a kernel-bound package on the ISO, so it needs the
  re-signed boot bundle (the rebuilt module changes the signed inventory; see
  [mastering-1.5.0.md](../mastering-1.5.0.md#rebuilding-a-kernel-bound-module-on-mudflap-the-wi-fi-driver-2026-10-31))
  and a physical retest. Evidence so far is fault injection on the MacBook (a synthetic
  link-down after the PTK: 5 of 5 honoured and recovered, no scan stall, no flapping),
  not a reproduction of the firmware-side loss. 1.4.1 ships without it.
- **MacBookPro16,1 Wi-Fi: the 2.4 GHz channel-1 AP fails the 4-way handshake.** Candidate,
  not investigated. On the 1.4.0 MacBook the AP `70:a7:41:81:16:e0` (2.4 GHz, channel 1,
  chanspec `0x1001`) never completed a handshake: the join succeeds, then 3 to 4 s later
  the firmware reports `event 6` (deauth indication) with reason 15 (4-way handshake
  timeout) and `wpa_supplicant` logs `WRONG_KEY` and temp-disables the SSID for 10 s, then
  28 s to 38 s. The pre-shared key is right: the same SSID joined other APs in 1 to 2 s.
  Every logged attempt on that AP failed this way (at least seven, 2026-10-30 00:02 twice,
  00:28 and 08:51, and 2026-10-31 00:01 twice and 00:04), on both the 1.4.0 driver and the
  patched one. Reason 15 is not exclusive to it: it also hit the channel-6 AP (once after
  the key was installed) and, once, the strong channel-36 AP, but those APs usually joined.
  When `wpa_supplicant` picks this AP the join costs 10 to 45 s. Candidates, none tested: our
  message 4 (or message 2) is not reaching the AP on channel 1, an event-ordering problem
  around key installation, or the X0 regulatory country. A passive capture of the AP's
  EAPOL frames and `dev.brcmfmac.0.debug=2` during a join would separate them.
- **ADOPT-002** ([queue](active-work.md#adopt-002-qualify-retained-native-execution-and-release-enforcement)).
  Needs the external Literate AI framework to execute native components.
- **GUI-001** ([queue](active-work.md#gui-001-deliver-a-colorful-fast-graphical-package-manager)).
  Not started.
- **SRC-001** ([queue](active-work.md#src-001-establish-owned-freebsd-source-builds-and-packages)).
  Partly done; the hand pipeline builds the base.
- **RELEASE-001** ([queue](active-work.md#release-001-deliver-a-qualified-literate-ai-release-workflow-in-14)).
  Blocked on the framework.
- **COMP-001** ([queue](active-work.md#comp-001-model-complete-freebsd-source-and-ports-trees-as-components)).
  Blocked on the framework.
- **PERF-002** ([queue](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140)).
  Blocked on the framework.
- **DEV-001** ([queue](active-work.md#dev-001-provide-an-operator-ready-native-component-development-system)).
  Blocked on the framework.
- **DEBUG-003** ([queue](active-work.md#debug-003-deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14)).
  Foundations only; needs boot-chain research and hardware.
- **HW-004** ([queue](active-work.md#hw-004-t2-touch-id-login-through-fprintd)).
  Not in the image; needs a Mac with enrolled fingers.
- **EXT-002** ([queue](active-work.md#ext-002-sandboxed-lua-extensions-for-content-we-did-not-write)).
  New work, not deferred: sandboxed Lua extensions for content we did not write. The runtime (SDK API 1.5:
  `.lua` entries and `Audio.blip`) and the fish tank are implemented and tested on Linux; FreeBSD capability mode
  and checks on the exact image are open. Touches `daemonarchy_visual` (`lua.py`, `sandbox.lua`, `plugin.py`,
  `audio.py`), the installer's `sound.py` and `daemonarchy-extensions`; other 1.4.2 work in those files should
  rebase onto it. The four Python games and the feed's trust model are unchanged.

## Added after the 1.4.2 plan opened

- **Windows games: Wine and Steam in the Apps menu** (operator decision, 2026-10-30,
  moved from the [1.4.1 plan](release-1.4.1.md)). amd64 only. Delivered as virtual apps
  like Cudalab, not as default packages: `daemonarchy-steam` and `daemonarchy-wine`
  launchers, desktop entries, icons and System > FreeBSD menu entries that the installer
  places on amd64 only. The first launch installs `wine-devel`, `wine-mono-devel`,
  `wine-gecko-devel` and `winetricks` from the system's repositories and downloads Valve's
  `SteamSetup.exe` over HTTPS; nothing of Wine's or Valve's is shipped, so the package
  lists, feeds and ISO size do not change. Design, licences and the source offer are in
  [Windows programs and Steam](../windows-apps.md). The launcher state machine and the
  installer placement are tested against stand-ins. **Not verified:** a Windows game and
  Steam each launching from the Apps menu on a fresh install on the MSI (NVIDIA
  OpenGL/Vulkan, sound, Steam's updater and web view under Wine); that needs the
  operator's hardware, and the item is not claimed done until then. Linux Steam under the
  Linuxulator stays out (no receipt).

## Also carried (known limitations)

Known limitations written in the [1.4.1 release notes](../release-1.4.1.md) that
had no fix at 1.4.1. The roughly 1.6 second display-driver sleep at login now has a fix on the MSI Raider 18 HX
(daemonarchy-ports #44, Aquamarine; one machine, hotplug, resume, lid and VT switch untested), the
first-login delay is still under investigation, and the aarch64 gaps (real hardware, GPU,
sound, Wi-Fi, a desktop in a VM).

## DESKTOP-001: launchers and menu entries move to the desktop package

New for 1.5.0 (operator decision, 2026-10-31): [DESKTOP-001](active-work.md#desktop-001-ship-the-desktop-launchers-and-menu-entries-in-the-daemonarchy-desktop-package)
moves the Cudalab, Wine and Steam launchers, desktop files, icons and menu entries out of the
installer overlay into the daemonarchy-desktop package, so fixes arrive by `pkg upgrade` and not
only with a new image. Nothing is claimed done; its acceptance is in the queue entry.

## Build efficiency: not delivered under the 1.4.2 name

The 1.4.2 (now 1.5.0) queue items ADOPT-002, RELEASE-001, COMP-001, PERF-002, DEV-001 and SRC-001 were kept
open by operator decision and were not run natively under Literate AI. 1.4.2 therefore made no
build-efficiency claim: its builds used the hand pipeline of 1.4.1. The 1.4.2 work that touched
this area was preparatory only (documentation authority gate, release policy and gate for 1.4.x,
a registered FreeBSD worker, and written native adoption steps), and the retained native receipt
(`verification/current.json`) still does not exist.

## Baselines (recorded first, with where measured)

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

## Targets and mechanisms

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
| Release state and gates | `litai release` plan, check and publish driven by the 1.4.x gate and a goal manifest, replacing hand steps | RELEASE-001 |

These mechanisms are the open acceptance of the listed items, not new claims. A 10x figure is not
credible if it comes from skipping a test, a package or a signature; the evidence says so.

## Literate AI upgrade to 1.4 in all Daemonarchy repositories

Today the installed runtime is litai 1.3.0 (c345e652) and framework main reports 1.4.0 development.
"1.4 (top of tree)" means the framework revision chosen and recorded at the start of this work.
The Daemonarchy repositories and their state on 2026-10-31 (three carry `literate.project.json`):

| Repository | `literate.project.json` | Project version | Notes |
|---|---|---|---|
| daemonarchy | yes | 1.4.1 | Standard binding to framework distribution 8b9c09fd; release policy and 1.4.x gate in place |
| daemonarchy-src | yes | 1.2.0 | Standard lifecycle binding present; older project version |
| daemonarchy-ports | yes | 1.2.0 | Standard lifecycle binding present; older project version |
| daemonarchy-desktop | no (to be added) | n/a | In scope, not subsumed: see below. Needs a project binding like the other three |

### daemonarchy-desktop: in scope, not subsumed

Checked on 2026-10-31. The repository is still applicable and is not folded into daemonarchy-ports or daemonarchy-src:

- The port `x11-wm/daemonarchy` in daemonarchy-ports builds from it (`USE_GITHUB`, `GH_ACCOUNT=jordanhubbard`, `GH_PROJECT=daemonarchy-desktop`, `GH_TAGNAME` pinned to commit `ec2a00824ec9`) and installs its wallpaper, SDDM theme, menu (`omarchy-menu.jsonc`), icons and the `daemonarchy-*` FreeBSD tools. The ports tree holds only the packaging, not these sources.
- It is active (a commit on `main` on 2026-10-31, and open PR 1, which makes the Packages menu open daemonarchy-pkg) and not archived. Its last tag is v1.1.1, so tags and the port's pin are not aligned today.

So it gets a project binding: a `literate.project.json` with the Standard lifecycle, a release policy suited to a small source repository (version and tag convention to be decided with the operator, including whether the port pin follows a tag), and the same `litai verify` qualification as the other three. It would be excluded only if a later change moved its sources into daemonarchy-ports or daemonarchy-src; this item records that this has not happened.

### Out of scope

Scope is exactly daemonarchy, daemonarchy-src, daemonarchy-ports and daemonarchy-desktop. The other repositories under the owner that carry a `literate.project.json` (Aviation, ElixirSSI, project-tracker, bookscan, freebsd-sentiment, LeRTX, and the Literate AI framework with its labs) are unrelated to Daemonarchy and are out of scope. Nothing in this plan changes them.

For each repository, the upgrade is: review the Standard rebind plan
(`litai project lifecycle rebind-standard`, plan first), apply it only with the reviewed plan and
explicit authorization, add the release-goal manifest that framework main requires
(`contributions.roadmap_goal_manifest`, with a `Release target:` line on each queue heading and every
included goal checked off), then run `litai verify` and the repository's own tests. The rebind
changes lifecycle and receipt-policy authority, so each is an operator-approved change.
daemonarchy's `authority-reviewed` marker is recorded by a human after review.

## Acceptance

Nothing is claimed done until each of these has retained evidence with exact inputs:

- Baseline records for every row of the baseline table, including the missing ones, with
  where-measured details.
- Per-stage results against targets, each stage's gates unchanged from the baseline cycle.
- The end-to-end cycle at least 10x shorter on equivalent gates, on a rehearsal and on a real
  release, with every decision, cache hit and rebuild recorded.
- Literate AI at the recorded 1.4 revision in daemonarchy, daemonarchy-src, daemonarchy-ports and
  daemonarchy-desktop (with its new binding); each passes `litai verify` for its declared gates.
- ADOPT-002, COMP-001, SRC-001, DEV-001, PERF-001, PERF-002 and RELEASE-001 meet their own
  acceptance texts; framework issues #74 and #93 are resolved or the dependent scope stays open.
