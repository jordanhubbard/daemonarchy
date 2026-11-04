# 1.5.0 plan: the 1.4.2 scope, re-scoped on 2026-11-03 to what is evidenced

- **Status:** partial
- **Owning queue item:** [RELEASE-001](active-work.md#release-001-deliver-a-qualified-literate-ai-release-workflow-in-14)
- **Supporting queue items:** [ADOPT-002](active-work.md#adopt-002-qualify-retained-native-execution-and-release-enforcement), [SRC-001](active-work.md#src-001-establish-owned-freebsd-source-builds-and-packages), [GUI-001](active-work.md#gui-001-deliver-a-colorful-fast-graphical-package-manager), [DEBUG-003](active-work.md#debug-003-deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14), [HW-004](active-work.md#hw-004-t2-touch-id-login-through-fprintd), [EXT-002](active-work.md#ext-002-sandboxed-lua-extensions-for-content-we-did-not-write), [DESKTOP-001](active-work.md#desktop-001-ship-the-desktop-launchers-and-menu-entries-in-the-daemonarchy-desktop-package), [SIGN-001](active-work.md#sign-001-one-signing-session-per-release-stop-the-key-window-churn)
- **Completion / archival evidence:** pending; nothing here is claimed done. Done means the evidence listed under Acceptance below, retained with exact inputs.

The 1.5.0 image was published November 4, 2026. Unfinished acceptance is
carried to [1.5.1](release-1.5.1.md#unfinished-150-acceptance); this plan's
remaining boxes are historical evidence of the original target.

Opened 2026-10-31 as the 1.4.2 scope plus a build-speed program (BUILD-001). **Re-scoped 2026-11-03 by
operator decision** to the work that is real, with the framework-executed goals deferred to
[1.5.1](release-1.5.1.md). The roadmap stays honest: no box is ticked without evidence, and a deferred
item keeps its evidence state, unchanged, in the 1.5.1 plan.

**Gating (replaces the 2026-11-01 gating).** The earlier text held 1.5.0 until ADOPT-002, RELEASE-001,
COMP-001, PERF-002, DEV-001, SRC-001 and BUILD-001 were all done and gated it on Literate AI 1.4.0. That
gate is withdrawn: the latest Literate AI release is v1.3.1, 1.4.0 does not exist, and COMP-001, PERF-002,
DEV-001, BUILD-001 and the native halves of ADOPT-002, SRC-001 and RELEASE-001 cannot be done on 1.3.x.
1.5.0 is **not** gated on Literate AI 1.4.0 and does not wait for those goals. It is published when each
goal in [release-goals.json](release-goals.json) for 1.5.0 has the evidence its own queue acceptance
demands. The runtime in use stays Literate AI 1.3.1; the 1.4 upgrade of the repositories moves to 1.5.1.

**What moved to 1.5.1** (exact list; each keeps its queue entry, acceptance text and evidence state):
PERF-002, COMP-001, DEV-001, BUILD-001, PERF-001, and the halves of three items that need the framework to
execute native components: ADOPT-003 (from ADOPT-002), SRC-002 (from SRC-001) and RELEASE-002 (from
RELEASE-001). The Literate AI 1.4 upgrade, the baselines, the targets and the framework-issue table moved
with them, verbatim, into the [1.5.1 plan](release-1.5.1.md#build-speed-and-framework-executed-goals-deferred-from-150).

## What shipped in 1.5.0

Status: shipping. This plan becomes `completed` when the release is published and [`release/current.json`](../../release/current.json) records it.

Shipped: ADOPT-002, SRC-001 and RELEASE-001 (delivered parts only), GUI-001 (the `daemonarchy-pkg` window and its
package, no real-desktop evidence), EXT-002 (sandboxed Lua extensions), DEBUG-003 (foundations), HW-004 (Touch ID stays
out of the image), DESKTOP-001 and SIGN-001 (option A: one signing session per release), plus Windows programs and
Steam on amd64, the faster Raider login and the MacBookPro16,1 Wi-Fi link-down fix. The release carries four images:
the installer ISO and the hardware trace image for each of amd64 and arm64. Not shipped: the RTX Spark laptop
(tested, not yet working, deferred) and everything moved to [1.5.1](release-1.5.1.md). The evidence for each
claim is in the [release notes](../release-1.5.0.md); the roadmap boxes stay unticked where the evidence is not there.

**What stays in 1.5.0:** ADOPT-002 (only the delivered handler audit and binding records), SRC-001 (only the
delivered controller and capture work), RELEASE-001 (the delivered 1.4.x release gate and the
prepare/fill tooling), GUI-001, DEBUG-003, HW-004, EXT-002, DESKTOP-001 and SIGN-001 (option A). The RTX
Spark laptop is deferred (see the [application note](../application-note-rtx-spark.md)).

## History: 1.4.2 was renamed 1.5.0 and never released

Opened as 1.4.2; renamed 1.5.0 on 2026-10-31 (user-visible features make it a minor release; no 1.4.2 tag,
feed or image exists). Its goals moved here without deferral and kept their queue entries; the 1.4.1 plan
and the [1.4.1 audit](release-1.4.1-audit.md) describe the same items under the 1.4.2 name.


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
  Re-scoped 2026-11-03: only the delivered handler audit and binding records stay; native execution moved to ADOPT-003 in 1.5.1.
- **GUI-001** ([queue](active-work.md#gui-001-deliver-a-colorful-fast-graphical-package-manager)).
  Not started.
- **SRC-001** ([queue](active-work.md#src-001-establish-owned-freebsd-source-builds-and-packages)).
  Re-scoped 2026-11-03: the delivered controller and capture work stay; native qualification moved to SRC-002 in 1.5.1.
- **RELEASE-001** ([queue](active-work.md#release-001-deliver-a-qualified-literate-ai-release-workflow-in-14)).
  Re-scoped 2026-11-03: the 1.4.x release gate and the prepare/fill tooling stay; the framework-executed release moved to RELEASE-002 in 1.5.1.
- **COMP-001** ([queue](active-work.md#comp-001-model-complete-freebsd-source-and-ports-trees-as-components)).
  Deferred to 1.5.1 (blocked on the framework).
- **PERF-002** ([queue](active-work.md#perf-002-coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140)).
  Deferred to 1.5.1 (blocked on the framework).
- **DEV-001** ([queue](active-work.md#dev-001-provide-an-operator-ready-native-component-development-system)).
  Deferred to 1.5.1 (blocked on the framework).
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

## SIGN-001: one signing session per release

New for 1.5.0 (operator decision, 2026-11-01; the operator's words: "this is too much security").
**Operator decision, 2026-11-03: option A for 1.5.0.** Nothing here is claimed done. Related item: BUILD-001
(the 10x release-cycle target, deferred to 1.5.1).

**The problem, as recorded by the release coordinator (the operator's counts; I did not re-measure them).** In 1.4.1 the signing key
lived on daemon.local and the workers signed without an operator step. For 1.5.0 the operator ran **six key windows by hand**:

| # | Window | Avoidable? |
|---|---|---|
| 1 | Boot bundle relabel 1.4.2 to 1.5.0 after the mid-release rename | Avoidable: the rename was a decision made after signing had started |
| 2 | amd64 feeds | Needed once |
| 3 | arm64 feeds | Needed once |
| 4 | Extension feeds (the installer derives the extension feed name from the image version) | Avoidable: scheduling; the name is known once the release label is frozen |
| 5 | Boot bundle full re-sign after the loader menu fix landed late | Avoidable: a late change to a signed input |
| 6 | arm64 checkout feed re-sign after QA found the wrong package ABI label | A genuine QA finding, but it would have cost nothing extra if signing had followed QA |

Why each window needed the operator: (a) the key was moved off the builders on purpose (daemon.local retired, the key on the key host,
and the rule that it is never on a build machine or sparky and never printed); (b) the agent permission system refuses to let agents
move key material even with a relayed operator approval, so every signing step needs the operator to type a command; (c) artifacts
were signed as soon as they were ready, instead of freezing the signed inputs, finishing QA and signing once.

**Goal (measurable).** At most **one** operator signing action per release; **zero** key material handled by agents; the signing
wall-clock time and operator-command count recorded in the release record for the next release.

**Options, with trade-offs (the operator picks):**

| Option | What it is | Trade-off |
|---|---|---|
| A. Process rule | Freeze all signed inputs (boot tree files, feeds, extension feeds, release label), finish QA, then one signing session. No code. | Costs nothing and keeps every safeguard; still needs the operator to run each window command once in that session. |
| B. One manifest-driven window script | One script signs every pending item in one sitting, with the existing safeguards (tmpfs, locks, hash checks, trap cleanup). | Some code on top of `scripts/key-windows/`; one operator command; the safeguards are kept. |
| C. A signing service on the key host | Signs only allowlisted artifact types after verifying their hashes against an operator-approved release manifest; agents request, never hold the key; one approval per release. | More to build and secure (the service is a new attack surface); zero operator commands per window, one approval per release. |
| D. Simplify the security policy | A dedicated release-signing VM holding the key, with operator approval once per release. | **Explicitly lowers the current safeguards.** The operator decides the threat model. The operator considers the current process excessive. |

**Decision (2026-11-03): option A, a process rule.** Freeze every signed input (boot tree files, feeds,
extension feeds, release label), finish QA, then sign once. The release record states the number of operator
signing commands and the signing wall-clock time. Options B, C and D are not part of 1.5.0; they stay recorded
above for a later release and need their own operator decision (D explicitly lowers safeguards). The acceptance
and evidence are in the [queue item](active-work.md#sign-001-one-signing-session-per-release-stop-the-key-window-churn).

## Acceptance

Nothing is claimed done until each of these has retained evidence with exact inputs. 1.5.0 is not gated on
Literate AI 1.4.0 and does not wait for the goals listed under "What moved to 1.5.1".

- Every goal listed for 1.5.0 in [release-goals.json](release-goals.json) is done by its own queue
  acceptance text: ADOPT-002, SRC-001 and RELEASE-001 as re-scoped, GUI-001, DEBUG-003, HW-004, EXT-002,
  DESKTOP-001 and SIGN-001. An item whose hardware or physical evidence is missing is moved to 1.5.1 by an
  operator decision, not ticked.
- SIGN-001 (option A): one signing session (each window command run once, after inputs are frozen and QA is done), no agent handling key material, and the release
  record states the operator command count and the signing wall-clock time.
- The release passes `scripts/release-check-1.4.py` and the release-media sync checks, and is published
  through the existing, documented hand pipeline ([mastering notes](../mastering-1.5.0.md)). It makes no
  build-efficiency or Literate AI 1.4 claim.
