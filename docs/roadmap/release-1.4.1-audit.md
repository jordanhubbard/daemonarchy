# 1.4.1 roadmap audit

- **Status:** completed
- **Owning queue item:** [RELEASE-001](active-work.md#release-001-deliver-a-qualified-literate-ai-release-workflow-in-14)
- **Completion / archival evidence:** the [1.5.0 plan](release-1.5.0.md) records where each audited item moved; the per-item `audit` lines are in [active-work.md](active-work.md).

Audited 2026-10-30 against the repository, `verification/` records, the test suite
and the physical and QEMU runs of this cycle. Scope: the open queue items in
[active-work.md](active-work.md) that are not owned by a running workstream
(parallel fetch and the package closure, the visual SDK, games and extensions, the
arm64 image, the MSI Hyprland first launch, the MacBook Wi-Fi investigation, the
cudalab wrapper, and the amd64 packages and mastering runbook).

Status words are used strictly:

- **done with evidence** — every acceptance box has direct evidence;
- **partly** — real work and evidence exist, the rest is named;
- **not started** — no implementation;
- **blocked on hardware** — only the operator's physical machines can produce the evidence;
- **blocked on framework** — needs the external Literate AI framework, not this repository;
- **proposed: leave 1.4.1** — a recommendation for the operator to decide. Nothing was moved
  or closed without that decision; every audited item still carries `Release: 1.4.1`.

## Summary

| Item | Status | Needed for the 1.4.1 image? | Proposed disposition |
| --- | --- | --- | --- |
| [ADOPT-002](#adopt-002) | partly (1 of 4), blocked on framework | no | proposed: leave 1.4.1 |
| [UI-001](#ui-001) | partly; implemented, physical evidence incomplete | yes (stats header: another worker) | keep |
| [GUI-001](#gui-001) | not started | no | proposed: leave 1.4.1 |
| [SRC-001](#src-001) | partly (2 of 6) | no (hand pipeline builds the base) | proposed: leave 1.4.1 |
| [DEBUG-001](#debug-001) | partly (1 of 6), blocked on hardware | no | proposed: leave 1.4.1 |
| [HW-001](#hw-001) | partly; a standing evidence log | yes (fresh installs) | keep as the evidence log |
| [RELEASE-001](#release-001) | partly (2 of 4), blocked on framework | no | proposed: leave 1.4.1 |
| [COMP-001](#comp-001) | partly (4 of 11), blocked on framework | no | proposed: leave 1.4.1 |
| [PERF-001](#perf-001) | partly; first box now evidenced | no | split: baseline done here, rest leaves |
| [PERF-002](#perf-002) | not started, blocked on framework | no | proposed: leave 1.4.1 |
| [DEV-001](#dev-001) | partly (5 of 12), blocked on framework | no | proposed: leave 1.4.1 |
| [TESTISO-001](#testiso-001) | **done with evidence** | no | close |
| [HW-002](#hw-002) | partly; closes with the fresh MacBook install | yes (that install) | keep until the install |
| [HW-003](#hw-003) | partly, blocked on hardware | yes (firmware path) | keep |
| [DEBUG-002](#debug-002) | partly; physical resume unproven | helps testing | keep; logging added |
| [DEBUG-003](#debug-003) | not started beyond foundations, blocked on hardware | no | proposed: leave 1.4.1 |
| [LIVE-001](#live-001) | partly; shipped in 1.4.0, exact-image evidence open | yes (run at mastering) | keep |
| [NET-001](#net-001) | partly; implementation tested, matrix open | yes (fresh installs) | keep |
| [DEBUG-004](#debug-004) | partly | no | proposed: leave 1.4.1 |
| [GPU-001](#gpu-001) | partly; reporting tool added with MSI evidence | yes (hybrid GPU diagnostics) | keep |
| [NET-002](#net-002) | partly (4 of 6) | yes (boot evidence) | keep |
| [HW-004](#hw-004) | not in the image, blocked on hardware | no | proposed: leave 1.4.1 |
| [WORKER-001](#worker-001) | partly (3 of 9) | no | proposed: leave 1.4.1 |

Nine items (ADOPT-002, GUI-001, SRC-001, RELEASE-001, COMP-001, PERF-002, DEV-001,
DEBUG-003, HW-004) cannot be completed by repository work in this release: they need
the external Literate AI framework to execute native components, a research program in
the boot chain, or a Mac with enrolled fingers. Taking them "into 1.4.1" cannot make them
true by publication time; the honest options are to move them or to ship 1.4.1 with them
open. That is the operator's decision.

## What this sweep changed

- **GPU-001:** `daemonarchy-gpu-report` (new, in the image's `/usr/local/bin`) with tests on
  the MSI's real captures; run live on the MSI.
- **DEBUG-002:** the boot-time remote-debug resume now logs every step with a timestamp
  to `/var/log/daemonarchy-rescue.log` (it was empty on the MSI), with tests.
- **PERF-001:** `scripts/build-timing-record.py` and the first retained build-timing
  baseline, [`rev2-1.4.1-pipeline-20261030.json`](../../verification/build-baselines/rev2-1.4.1-pipeline-20261030.json).
- **Native FreeBSD re-verification** on daemon.local at current `main`, nice 15, `/tmp`
  scratch only: `remote-debug-session`, `remote-debug-background`, `remote-debug-observe`,
  `remote-debug-reboot`, `rescue-setup`, `rescue-console`, `shared-disk` and `disk-layout`
  pass. On Linux: `network-bringup`, `network-diagnostics`, `installed-boot-network`,
  `installer-wifi-timing`, `live-backend`, `live-desktop`, `live-image-budget`,
  `headless-rescue`, `gpu-config`, `apple-firmware-offline`, `secureboot-options` and
  `remote-worker` (130 checks) pass.
- This audit, and an `audit` line on each audited queue item.

## Items

### ADOPT-002
Qualify retained native execution and release enforcement. **Partly (1 of 4); blocked on
framework.** Evidence: the audit of the retained execution handler is recorded; the
framework's own issue #22 was reopened because authorized execution still refuses.
Remaining: bind the actual FreeBSD target, qualify receipts and custody, and have the
installed CLI accept native execution. All of it depends on framework work. Effort:
weeks, outside this repository. Not needed for the image. Proposed: leave 1.4.1.

### UI-001
Measured retro installer visualizers. **Partly.** Evidence: the dashboard, flourishes and
sound exist; it now draws through the SDK (PR #151) with tests (54 installer-progress,
SDK, audit); an operator ran a full physical install on the MSI (2026-10-30, real console,
tmux dashboard) and reported the screen's gaps, which a worker is fixing (statistics
header, totals, timeline). Remaining: the same stages in the graphical installer; sound on
a real device; a full MacBookPro16,1 install using only the tmux keys. **Needs the
operator:** run the fresh installs and report sound and key behavior on each laptop.
Needed for the image.

### GUI-001
Colorful fast graphical package manager. **Not started.** `octopkg` (Qt) is installed and
wired to the menu entries; no evaluation of an extension path, no parallel plan visuals.
Effort: large (a new application or a substantial extension), and it depends on PKG-001's
transaction planner. Not needed for the image. Proposed: leave 1.4.1.

### SRC-001
Owned FreeBSD source builds. **Partly (2 of 6).** Evidence: the controller and filemon
capture; and this cycle the 1.4.1 base (daemonarchy-src `303b364`, kernel `#3`) was built
from the owned fork by a hand-run pipeline in 3,518 s incremental
([record](../../verification/build-baselines/rev2-1.4.1-pipeline-20261030.json)),
installed on two physical machines. Remaining: the controller-driven end-to-end run, the
set-staging failure root cause, VM boot with signing and rollback. Effort: days to weeks.
Not needed for the image. Proposed: leave 1.4.1.

### DEBUG-001
Wired network debugging. **Partly (1 of 6); blocked on hardware.** Evidence: native
netdump and NetGDB baselines in `verification/`, [testing-1.4-network-debug-20261026.md](../testing-1.4-network-debug-20261026.md).
Remaining: a loader stub, early-kernel activation, retained early-boot traffic from the
MSI's built-in NIC. Not needed for the image. Proposed: leave 1.4.1.

### HW-001
Remaining hardware qualification gaps. **Partly; by design a standing log.** Evidence:
[testing-1.4.0.md](../testing-1.4.0.md) and [hardware-quirks.md](../hardware-quirks.md)
record exact hardware and what failed (MSI VMD, GuC, touchpad, CUDA-integrity, the
stick-removal panic, the Hyprland first launch, MacBook Wi-Fi DHCP). The acceptance says
unresolved cases stay open, so this closes only when every case is run on the final image.
**Needs the operator:** the fresh-install runs listed below.

### RELEASE-001
Release entirely through Literate AI. **Partly (2 of 4); blocked on framework.** Evidence:
`release/current.json`, `scripts/release-current.py` and the docs/release sync test run in
CI; 1.4.x was released by scripts and `verify-release-assets.py`, not through the framework.
Remaining: everything that needs ADOPT-002. Proposed: leave 1.4.1.

### COMP-001
Source and ports as Components. **Partly (4 of 11); blocked on framework** (issues #74 and
#93). Evidence: tree-discovery and dirdeps observations in `verification/`. Remaining:
catalogs and locks for every input, native actions, the first source composition proof.
Proposed: leave 1.4.1.

### PERF-001
Execute native components and accelerate ISO builds. **Partly; first box now evidenced.**
New: a retained baseline of the real 1.4.1 build — source 51 s, world 878 s (make: 874 s),
kernel 622 s, sets 601 s, jail 154 s, Secure Boot source 314 s, build 442 s, sign 62 s,
checkouts 387 s, 3,518 s total on one 8-core amd64 host with `-j8`; two ISO builds took
1,583 s and 1,601 s. It is **incremental** on a retained object tree and one run, so it
is a baseline, not a speed claim. Remaining: component admission, Bazel or another
executor, clean/unchanged/changed comparisons. Proposed: the baseline box closes here;
the rest leaves 1.4.1.

### PERF-002
Coordinate all repositories through Literate AI workers. **Not started; blocked on
framework.** This cycle used three builders manually (amd64 FreeBSD, arm64 FreeBSD, a
Linux QEMU host), not through the framework or a shared verified cache. Proposed: leave 1.4.1.

### DEV-001
Operator development system. **Partly (5 of 12); blocked on framework.** The workspace,
checkouts and candidate CLI checkpoints exist; the build/test/package interface through
`litai-dev` does not. Proposed: leave 1.4.1.

### TESTISO-001
Prepare the 1.2 hardware test ISO. **Done with evidence** (both boxes checked: isolated
staging with exact input identities, and retained identities and hash). The 1.2 milestone
was never published and its purpose is superseded by the 1.4.x images. **Closed by this
audit.**

### HW-002
MacBook installer interruption and storage recovery. **Partly.** Evidence: the ANS2 fix
(daemonarchy-src PR #34, merged 2026-10-27) is an ancestor of the 1.4.0 kernel and of the
1.4.1 base, and the 1.4.0 MacBook install completed on that kernel (operator-confirmed).
Remaining box: repeat a fresh-image installation with package integrity and hardware
checks on a release kernel that contains it. **The fresh 1.4.1 MacBook install is that
run**: its install trace and integrity log close the box. **Needs the operator:** the
install, then I record it.

### HW-003
Firmware for laptops. **Partly; blocked on hardware.** Evidence: the 1.4.0 MacBook install
passed the signed firmware stage (operator-confirmed); on 2026-10-30 `brcmfmac0` on the
installed MacBook attached, scanned and associated over WPA2, and DHCP completed after a
long delay (Wi-Fi investigation in progress). Remaining: rebooted operation as a recorded
acceptance, offline-media and failure/retry runs, physical proof of the APFS read path.
**Needs the operator:** the fresh MacBook install with and without a cable, and the offline
firmware path.

### DEBUG-002
Persist approved debugging sessions across reboot. **Partly; physical resume unproven.**
Evidence (native, re-run today on daemon.local at current `main`): real-SSH session
lifecycle, background listener, observer, reboot persistence and rescue setup all pass.
On the installed MSI the boot path is wired — first-console autologin runs
`daemonarchy-rescue monitor`, which was running — but its grant did not exist at first
boot (the operator started the listener by hand), so the MSI shows nothing. On the MacBook
the operator had to press Resume after a crash-reboot; that failure is not diagnosed.
**Changed:** every step of the boot resume now logs a timestamped line, so the next reboot
shows whether the grant, networking or the listener is what failed. **Needs the operator:**
after pairing a freshly installed laptop, reboot it once without touching it, then tell me
to read `/var/log/daemonarchy-rescue.log`.

### DEBUG-003
Bidirectional loader, mountroot and panic network debugging. **Not started beyond
foundations; blocked on hardware** (the MSI's NIC backend, forced mountroot and panic
captures). A research program in the boot chain. Proposed: leave 1.4.1.

### LIVE-001
Live desktop from the installer media. **Partly; shipped in 1.4.0.** Evidence: the live
desktop is in the 1.4.0 release notes; `live-desktop`, `live-backend` and
`live-image-budget` pass; VirGL and live-desktop test records exist
([live-desktop](../testing-1.4-live-desktop-20261026.md),
[virgl](../testing-1.4-live-desktop-virgl-20261027.md)). Remaining: an exact-image VM run
with before/after disk digests (`tests/live-image-runtime.sh IMAGE.iso`, FreeBSD, root),
the TUI-fallback case and scoped physical records. The runtime test and the digest run
belong at mastering, on the final ISO. **Needs the operator:** boot the live desktop on each
laptop and report whether it reaches the desktop.

### NET-001
Proactive, robust installer network bring-up. **Partly.** Evidence: `network-bringup`,
`network-diagnostics`, `installer-wifi-timing` and `live-backend` (the graphical backend
runs the same network steps) pass; the shared library, concurrent DHCP probes, direct DNS
with a user fallback, clock repair and Wi-Fi ordering are covered. Two MSI and MacBook
installs ran this code on wired and USB networks. Remaining: the exact-image VM matrix
(several NICs, broken DHCP DNS, blocked public DNS, wrong clock, CIDATA) and the MacBook
BCM4364 Wi-Fi-first path. The matrix was deferred to 1.4.1 (A14). **Needs the operator:** a
fresh MacBook install with no cable.

### DEBUG-004
Hardware bring-up trace image. **Partly.** A `daemonarchy-hwtrace-1.4.0-dev3-amd64.img`
was built and used on the MSI (testing records in `docs/`); tools are tested. Remaining:
QEMU/OVMF multi-boot checks with a crowded NVRAM store, more MSI iterations, release
handling. A developer tool, not part of the install image. Proposed: leave 1.4.1.

### GPU-001
Cross-vendor GPU diagnostics. **Partly; a reporting tool is new.** `daemonarchy-gpu-report`
lists the PCI GPUs and modules, every EGL device with a hardware/software/virtual
classification, and the renderer the desktop session really uses matched to its PCI GPU;
it exits 2 on software fallback. Live on the MSI (2026-10-30), in the desktop session:
the session renders on the **Intel Arrow Lake-S** GPU through Wayland (Mesa 26.2.2,
OpenGL 4.6, hardware); the **NVIDIA RTX 5080** (driver 595.104.02) is present for compute;
an `llvmpipe` software device exists and is not used; verdict accelerated. Remaining:
frame-time measurements (`glmark2` 2023.01 is packaged for amd64 and aarch64, 7 MiB, but is
not in the image's package roots; adding it changes the closure, a decision for the
operator and the closure worker), the AMD and MacBook runs, and a showcase. **Needs the
operator:** run `daemonarchy-gpu-report` on each laptop's desktop after the fresh install
and send the output; decide about `glmark2` in the image.

### NET-002
First usable connected interface at boot. **Partly (4 of 6).** Evidence: the code
(`netselect`, T2 link rule, boot budgets) and `installed-boot-network` pass. Remaining:
timestamped installed rc/DHCP traces from the exact image proving the offline-boot budget,
and the multi-NIC, no-carrier, Wi-Fi-only and late-link runs on hardware. The installer
trace (`docs/install-trace.md`) covers the install, not the boot. **Needs the operator:**
boot each freshly installed laptop once offline and once with the cable, and send the
boot-to-usable time.

### HW-004
T2 Touch ID through fprintd. **Not in the image; blocked on hardware.** The port exists on
the `daemonarchy-ports` `daemonarchy` branch (`security/t2-touchid`); nothing in the
installer or image uses it; the 2026-10-28 transport test is by hand. Needs a Mac with
macOS-enrolled fingers and an unlocked SEP. Proposed: leave 1.4.1.

### WORKER-001
Durable SSH-controlled remote workers. **Partly (3 of 9).** Evidence: the worker, rc.d
service and recipes `sample`, `sample-long`; 130 hosted checks pass today; real survival of
disconnects and reboots on the builders. Remaining: `src-world-kernel` has never run,
`hwtrace-image`, `release-sets`, `live-iso`, `poudriere-bulk` and `vm-qualify` recipes do
not exist, the worker is not on the media, and no candidate was built through it. This
cycle's builds ran as detached `daemon(8)` scripts. Proposed: leave 1.4.1.

## What I need from the operator

Run these after the fresh 1.4.1 installs, one line each in the reply:

1. **MSI and MacBook, fresh install:** did the install finish, and did the progress screen
   show the totals and statistics? (UI-001, HW-002, HW-003, NET-001)
2. **Both:** boot it once without touching it after pairing remote debugging, and tell me;
   I read the rescue log. (DEBUG-002)
3. **Both:** run `daemonarchy-gpu-report` in the desktop and send the output. (GPU-001)
4. **MacBook:** a Wi-Fi-only install (no cable), and the offline firmware path; a boot offline and
   with a cable, with the time to a usable network. (HW-003, NET-001, NET-002)
5. **Both:** boot the live desktop from the stick, say whether it reaches the desktop. (LIVE-001)
6. **Decisions:** move the nine framework- and hardware-blocked items out of 1.4.1, or ship
   with them open; and whether `glmark2` goes into the image.
