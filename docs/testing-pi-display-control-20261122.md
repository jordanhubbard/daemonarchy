# Pi software display development checkpoint, 2026-11-22

This is a private hardware bring-up control in the 1.6 development program.
It does not qualify the installed Daemonarchy desktop or a release. Original
FreeBSD, DRM and userspace implementations and failed probes are retained.

The Pi 4 operator confirmed red/green/blue bars above a white lower half.
Native KMS controls also passed modeset, framebuffer damage, page flip with
completion event, and console restoration. A subsequent framebuffer capture
and independent compositor IPC show a software Wayland terminal on that Pi.
Physical keyboard acceptance remains pending. This supplies no V3D result.

The image builder now accepts additive root and firmware directories without
replacing its selected kernel, loader or generated recovery files. The
opt-in desktop starts in a separate RAM filesystem before network handover.
Five controller checks exercise added files, preserved kernel bytes, symlink
escape refusal, source symlink refusal and privileged-mode refusal. Existing
network and bounded capture controls pass. Native ARM64 compilation with
`-Wall -Wextra -Werror`, socket readiness/refusal/deadline controls and a fresh
interactive shell with the runtime terminal database pass.

The native GENERIC kernel candidate derives from FreeBSD source
`f4eb2cff7f8b5c511c448f0158f071105d19aaf5` with three BCM2711 mailbox/DMA
source changes. The complete kernel build passed, with all 115,681 original
source files, the candidate source selection, original bootstrap and selected
host files checked afterward. Its SHA-256 is
`bb3278a22dd15933d10b4c393004e9cfab922d7973532405d087d4282f110090`.
Its successful generic UEFI boot does not qualify the physical mailbox or WiFi.

The private image `daemonarchy-pi5-c1-desktop-r3-20261122.img.xz` has 37,790,352
bytes and SHA-256
`f74e77c939f9a51c9ac210232de46e2a1d45ded64b8eeecf3b801fc894b67b03`.
The raw image has 443,581,952 bytes and SHA-256
`9f5fc0420ea1f864fd76f7a9fb069eb3de886671621579483b5bda1dd60c649f`.
Full decompression matches those raw bytes. Native read-only image mounts
verified the kernel, loader, runtime, selected modules and firmware. Primary
and backup GPT CRCs, the FAT32 ESP and DATRACE block map pass. The runtime
archive's 2,564 nodes passed independent byte/mode/owner/path verification.

An exact-image generic ARM64 UEFI/QEMU boot starts Sway and foot automatically
before network handover. The actual 800×600 capture shows the graphical
terminal, and compositor IPC identifies its window. Emulated USB keyboard
input through that terminal created a previously absent file whose contents
were independently observed. Earlier missing-termcap, module-order and
observer-command failures remain separate retained evidence. An additional
exact-image boot without a network device renders the identical terminal
framebuffer and holds the desktop after network handover fails. The configured
compositor exit binding resumes the trace cycle; guest reboot and successful
VM exit were independently observed. The initial refused memory allocation
remains retained separately.

The subsequent [owned port candidate](https://github.com/jordanhubbard/daemonarchy-ports/pull/85)
packages the opt-in driver for ARM. Native build, layout tests, stage/plist QA
and package creation pass. Actual installation with its original scripts,
installed-file ownership and hashes, deletion/reinstallation and checksum
checks pass in a separate RAM root in a disposable ARM64 UEFI VM. Modules
loaded from that package pass the KMS controls and 1,440,000 captured pixels
with zero mismatches; a software terminal renders and accepts emulated USB
keyboard input. Those results remain separate from physical package acceptance.

The Pi 5 firmware input is upstream
[worproject v0.3](https://github.com/worproject/rpi5-uefi/releases/tag/v0.3).
Its [support notice](https://github.com/worproject/rpi5-uefi#end-of-support-notice)
limits upstream testing to early C1 boards and reports possible D0/new EEPROM
graphics failures. The original firmware archive is retained. The selected
configuration omits its optional forced turbo and USB-current overrides; no
EEPROM updater files are included. The discovery queue caps memory to 3 GiB.

Physical Pi 5 boot, native SD/network/RP1 peripherals, full RAM, input, thermal
behavior, GPU acceleration, WiFi, the installed product session and
update/rollback acceptance remain open. These upstream binary userspace
controls and observed native build tools do not establish owned source
qualification or SDK admission. Authority and eight contract locks pass;
canonical verification still reports the missing configured test receipt.
