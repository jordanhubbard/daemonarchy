# 1.4.2 plan: deferred from 1.4.1

- **Status:** active
- **Owning queue item:** [RELEASE-001](active-work.md#release-001-deliver-a-qualified-literate-ai-release-workflow-in-14)
- **Supporting queue items:** the rows under Scope below, and [EXT-002](active-work.md#ext-002-sandboxed-lua-extensions-for-content-we-did-not-write); each keeps its own queue entry
- **Completion / archival evidence:** pending; each scope row closes only on the evidence its own queue item demands (see the [1.4.1 audit](release-1.4.1-audit.md))

1.4.1 carried every open queue item. The items below cannot be finished by
repository work before 1.4.1 ships, so they move here. None of them is claimed
done by 1.4.1. The [1.4.1 audit](release-1.4.1-audit.md) holds the evidence
that exists for each.

## Scope

- **MacBookPro16,1 Wi-Fi: the dead associated state.** The BCM4364 driver
  (`if_brcmfmac-kmod`) can stall after association: the interface still reports
  `associated` and no traffic moves. Cause: `brcmf_link_event()` ignored every firmware
  `E_LINK` down while the VAP was in `RUN`, including a real link loss after the
  handshake, so net80211 and `wpa_supplicant` stayed associated while the firmware had
  dropped the association and tossed every frame (`tx_complete status=3`). The fix is
  merged ([daemonarchy-ports #37](https://github.com/jordanhubbard/daemonarchy-ports/pull/37),
  `e136408d`). Still open: it is a kernel-bound package on the ISO, so it needs the
  re-signed boot bundle (the rebuilt module changes the signed inventory; see
  [mastering-1.4.2.md](../mastering-1.4.2.md#rebuilding-a-kernel-bound-module-on-mudflap-the-wi-fi-driver-2026-10-31))
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

## Added for 1.4.2

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

## Build efficiency: not delivered in 1.4.2

ADOPT-002, RELEASE-001, COMP-001, PERF-002, DEV-001 and SRC-001 stay open and were not run natively
under Literate AI in 1.4.2, so 1.4.2 delivers no build-efficiency gain. The speed work is planned
in the [1.5.0 plan](release-1.5.0.md) (BUILD-001).

## Also carried

Known limitations written in the [1.4.1 release notes](../release-1.4.1.md) that
have no fix yet: the roughly 1.6 second display-driver sleeps at login and the
first-login delay (under investigation), and the aarch64 gaps (real hardware, GPU,
sound, Wi-Fi, a desktop in a VM).
