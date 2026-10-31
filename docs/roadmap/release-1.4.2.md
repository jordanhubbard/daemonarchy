# 1.4.2 plan: deferred from 1.4.1

- **Status:** proposed (opened 2026-10-30 by operator decision; nothing here is claimed done)
- **Owning queue items:** the ten rows below

1.4.1 carried every open queue item. The items below cannot be finished by
repository work before 1.4.1 ships, so they move here. None of them is claimed
done by 1.4.1. The [1.4.1 audit](release-1.4.1-audit.md) holds the evidence
that exists for each.

## Scope

- **MacBookPro16,1 Wi-Fi: the dead associated state.** The BCM4364 driver
  (`if_brcmfmac-kmod`) can stall after association: the interface still reports
  `associated` and no traffic moves. A fix is drafted in
  [daemonarchy-ports #37](https://github.com/jordanhubbard/daemonarchy-ports/pull/37)
  and is deferred: it is a kernel-bound package on the ISO, so it needs a rebuilt
  module, a regenerated Secure Boot module inventory, a re-signed boot bundle and
  a physical retest on the MacBook. 1.4.1 ships without it.
- **ADOPT-002** ([queue](active-work.md#adopt-002--qualify-retained-native-execution-and-release-enforcement)).
  Needs the external Literate AI framework to execute native components.
- **GUI-001** ([queue](active-work.md#gui-001--deliver-a-colorful-fast-graphical-package-manager)).
  Not started.
- **SRC-001** ([queue](active-work.md#src-001--establish-owned-freebsd-source-builds-and-packages)).
  Partly done; the hand pipeline builds the base.
- **RELEASE-001** ([queue](active-work.md#release-001--deliver-a-qualified-literate-ai-release-workflow-in-14)).
  Blocked on the framework.
- **COMP-001** ([queue](active-work.md#comp-001--model-complete-freebsd-source-and-ports-trees-as-components)).
  Blocked on the framework.
- **PERF-002** ([queue](active-work.md#perf-002--coordinate-all-daemonarchy-repositories-through-literate-ai-workers-in-140)).
  Blocked on the framework.
- **DEV-001** ([queue](active-work.md#dev-001--provide-an-operator-ready-native-component-development-system)).
  Blocked on the framework.
- **DEBUG-003** ([queue](active-work.md#debug-003--deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14)).
  Foundations only; needs boot-chain research and hardware.
- **HW-004** ([queue](active-work.md#hw-004--t2-touch-id-login-through-fprintd)).
  Not in the image; needs a Mac with enrolled fingers.

## Also carried

Known limitations written in the [1.4.1 release notes](../release-1.4.1.md) that
have no fix yet: the roughly 1.6 second display-driver sleeps at login and the
first-login delay (under investigation), and the aarch64 gaps (real hardware, GPU,
sound, Wi-Fi, a desktop in a VM).
