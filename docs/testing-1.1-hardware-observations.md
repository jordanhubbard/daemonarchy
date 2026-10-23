# Physical hardware observations

Historical 1.1 development/candidate evidence and a scoped 1.1.1 upgrade result.
Revisions, checksums and results below apply to the named artifact and date; earlier results do not qualify the new
[1.1.1 source/package set](testing-1.1.1.md). Follow that record for current
preparation and publication status.

These are operator-reported development results, not a completed acceptance
matrix. Record the exact image and last visible boot message when available.

| Platform | Image / test | Observation | Qualification |
| --- | --- | --- | --- |
| HP All-in-One 24-cb1xxx, AMD Barcelo | Coordinated 1.1.1 upgrade to `bdcfeac3e1cb` / OS1600028, 2026-10-18 UTC | Original-root mount policy corrected; actual old-system rollback and return passed; AMD-rendered Hyprland/SDDM greeter captured at 1920×1080 | Full base/apps upgrade, rollback/return and greeter/renderer passed; operator confirmed normal authenticated desktop login; suspend remains untested; this is not fresh-ISO acceptance |
| MSI Raider 18 HX, RTX 5080 | preview.11 and 1.0.1 USB boot, reported 2026-10-15 | Both images reset very early during kernel startup/probing and return to Windows; exact last message not yet captured | Failure predates preview.11; installer boot failed and NVIDIA driver/session tests were not reached |
| T2 MacBook Pro | Development USB / installed-system investigation, 2026-10-15 | Black screen; internal keyboard unavailable in single-user mode; explicitly preloading `apple_bce` produced a queue-registration panic | Unqualified; original black-screen cause and exact panic backtrace unresolved |

The later [MSI startup video](#msi-startup-video-reviewed-2026-10-18) supplies a
last visible probe line for a boot whose exact image is still unidentified. It
does not retroactively identify the final line of either October 15 test.

For the MSI comparison, the preview.10 and preview.11 ISO payloads were mounted
read-only on FreeBSD and the following files compared byte for byte by SHA-256:

| Payload | Same hash in both images |
| --- | --- |
| `/boot/kernel/kernel` | `8139ad6eb5fa91b91bb8860c27abb6bd2599fc7b0d0bfb2bc2c842fde93aadcb` |
| `/boot/loader.efi` | `f1a9e84cbe83e382ce824738628168900c57e5b00d3bef68400cb2ef00293e46` |
| `/usr/freebsd-dist/kernel.txz` | `5d712017d1b35ce6fb487fc3e448177c4be88f4ad7a801d9379b2ed4c2a5bc74` |

Both use the October 5 snapshot kernel. Their live userspace differs, so this
comparison alone does not exclude an image regression. Testing another ISO on
the same machine and recording the failure point are still necessary. The
desktop NVIDIA driver is not installed or initialized by the live installer.

A subsequent recursive comparison of the complete `/boot` directories on the
same read-only mounts reported no differences, including loader configuration,
Lua scripts and kernel modules. Both temporary mounts and their memory-disk
devices were released after comparison. This narrows the comparison to changes
outside `/boot`; it does not substitute for booting both images on the MSI.

For an ordinary kernel panic, these loader commands enable verbose probing and
hold the panic output rather than automatically rebooting:

```text
set kern.panic_reboot_wait_time=-1
set debug.trace_on_panic=1
boot -v
```

The snapshot's `kern_shutdown.c` exposes both settings as loader tunables.
A firmware reset or a fault before panic handling may still reboot immediately;
these commands are diagnostic settings, not a fix. Do not combine speculative
device-disabling settings before identifying the last visible probe.

For comparison, the official October 12 FreeBSD mini-memstick image was
downloaded and checked against the project's SHA-256 list:

`FreeBSD-16.0-CURRENT-amd64-20261012-3ceb5f150bc1-290063-mini-memstick.img`

SHA-256: `9127c94970ca11e6e44c582a7cab928851f73fd2476e94471ee1456d63990e14`.
The compressed download also matched its published checksum. This image is
available for an operator boot comparison; no MSI result with it is recorded.

## MSI startup video reviewed 2026-10-18

The operator supplied `IMG_2155.MOV`, a 12.2-second, 1920×1080 recording.
Its SHA-256 is
`ed681d0b4ff7f41a34f732d733423ce0dfc30c7b67c7f3035da5da62aacec8d0`.
The original movie and extracted frames remain private; no raw media is committed.
The image/version and any loader overrides used for this recording are pending
operator identification.

Readable output shows 24 CPUs, the AP launch list, EFI real-time clock
registration, and HPET counter/event-timer registration. The last visible lines
are:

```text
atrtc0: <AT realtime clock> port 0x70-0x77 irq 8 on acpi0
atrtc0: Warning: Couldn't map I/O.
```

Frame inspection around the transition shows the same warning followed by a
blank display at approximately 7.6 seconds. No panic, trap, backtrace, subsequent
probe, firmware logo or Windows boot is visible before the recording ends. This
establishes the last captured console output; the movie alone cannot distinguish
a reset, power loss or loss of video. Earlier operator reports of a reset remain
separate evidence.

The inspected upstream `atrtc.c` is byte-identical between current main and its
[last-changing commit df615735](https://github.com/freebsd/freebsd-src/blob/df615735960370255d3acc4ac2a6f4fd297b7461/sys/x86/isa/atrtc.c).
`atrtc_attach()` prints the warning when its I/O resource allocation fails, then
calls `atrtc_start()`, which writes RTC control registers through legacy I/O.
This makes RTC attachment a focused diagnostic candidate, not a confirmed cause.
`hw.atrtc.enabled=0` makes `atrtc_probe()` refuse attachment. The
[one-boot comparison](hardware-quirks.md#rtc-comparison-prompted-by-the-video)
uses that existing tunable without changing the kernel or installing a default
workaround. The follow-up below records the RTC-disabled comparison; it still fails to reach the installer.

## MSI RTC-disabled follow-up video, 2026-10-18

`IMG_2157.MOV` is a 14.5-second, 1920x1080 recording, 16,139,826 bytes,
SHA-256 `ccb9f6f3a04fd66af93da47feb13143f24352ec13c01b9a982de68c7eec1d275`.
The loader visibly sets `hw.atrtc.enabled=0`,
`kern.panic_reboot_wait_time=-1`, `debug.trace_on_panic=1`, then uses `boot -v`.
The exact installer artifact/version remains unidentified. Raw media and frames
remain private in the controller's temporary evidence directory.

This boot advances beyond the earlier RTC stopping point. It enumerates PCI and
ACPI devices, reports repeated `acpi_spmc0: Intel: Wrong package length` messages
for power-state constraint packages, enables ACPI GPEs and reaches non-PnP ISA
probing. The last readable lines are:

```text
isa_probe_children: probing non-PnP devices
sc0 failed to probe on isa1
```

The display subsequently blanks around 12.8 seconds, without a visible panic,
backtrace, firmware logo or Windows startup. The operator reports another boot
failure; the movie alone does not distinguish reset, power loss and video loss.
Disabling RTC attachment changes observed progress but does not qualify a fix or
establish RTC as the sole cause.

Source inspection at FreeBSD `bdaddb76ef1b9d5537f4a76cff01cdb4795804a4`
shows that `isa_probe_nomatch()` merely reports an unmatched device. The final
`sc0` line does not establish a syscons crash or identify the next child.
`AcpiOsExecute: task queue not started` is a verbose deferred-work message that
returns success. The Intel SPMC constraint parser skips packages whose element
count differs from its expected three; this is evidence of a firmware/driver
format mismatch, not proof that parsing caused the later failure.

The next targeted one-boot comparison retains the three visible settings above
and adds `set debug.acpi.disabled="spmc"` before `boot -v`. The driver explicitly
honors this subsystem exclusion. The operator subsequently reports no difference
with the exclusion. No follow-up movie or kernel log was supplied, so the exact
last line and effective driver exclusion are not independently verified. This
negative comparison weakens SPMC attachment as the immediate failure trigger; it
does not validate the rejected power-state constraints. It does not disable all
ACPI or qualify a permanent workaround. If failure persists, per-child probe
entry/exit instrumentation can identify the unreported operation after the final
ISA message. A separate pending comparison returns to the RTC-disabled baseline,
removes `debug.acpi.disabled`, and adds `kern.smp.disabled=1` to test the
multiprocessor configuration. A changed result would implicate CPU/interrupt or
concurrency-dependent behavior without identifying a particular driver; an
unchanged result would motivate probe entry/exit and SYSINIT instrumentation.
No single-CPU result or instrumented-kernel build is claimed. Relevant source: [ISA probes](https://github.com/freebsd/freebsd-src/blob/bdaddb76ef1b9d5537f4a76cff01cdb4795804a4/sys/isa/isa_common.c),
[ACPI deferred work](https://github.com/freebsd/freebsd-src/blob/bdaddb76ef1b9d5537f4a76cff01cdb4795804a4/sys/dev/acpica/Osd/OsdSchedule.c),
and [SPMC](https://github.com/freebsd/freebsd-src/blob/bdaddb76ef1b9d5537f4a76cff01cdb4795804a4/sys/dev/acpica/acpi_spmc.c).

## MSI comparison reports

The operator subsequently reproduced the early reset with Daemonarchy 1.0.1.
The observed failure therefore predates preview.11. At that checkpoint, a stock
FreeBSD boot result and a final probe line were missing; the later video above
adds console evidence for its separately scoped boot.

Windows System Information supplied by the operator identifies:

- Model: Raider 18 HX AI A2XWIG, SKU 1824.3.
- CPU: Intel Core Ultra 9 285HX, 24 cores / 24 logical processors.
- Board: MS-1824, REV:1.0; RAM: 32 GiB.
- UEFI BIOS: American Megatrends E1824IMS.312, dated 2025-08-28.
- Secure Boot: off.

Windows reports virtualization-based security running. This is a Windows-side
observation; it does not establish a cause for a separately booted USB failure.
Machine/account identifiers and unrelated Windows configuration were omitted.

A closely matching first-person hardware report was found on 2026-10-15:
[Slackware installer resets on MSI Raider 18 HX AI](https://www.linuxquestions.org/questions/slackware-installation-40/slackware-current-usb-boot-grub-hangs-msi-raider-18-hx-ai-4175764459/).
The May 22–27, 2026 thread identifies an A2XWIG, Core Ultra 9 285HX, RTX 5080
and BIOS E1824IMS.316. Its installer hard-resets after about 15 seconds. The
reporter says Debian, Manjaro and Void installer media boot, and disabling ACPI
changes the reset into a hang. No working Slackware fix is recorded in those
posts. The model, CPU and motherboard match the operator's machine, while the
reporter's BIOS is newer (.316 versus .312). This is Linux evidence, not a
confirmed FreeBSD duplicate or a diagnosis of this operator's machine. The
reset on .316 also means a newer BIOS is not by itself evidence of a fix.

FreeBSD [bug 287342's initial report](https://lists.freebsd.org/archives/freebsd-bugs/2025-June/028114.html)
concerns Arrow Lake desktop I/O instability after boot on different hardware.
It does not establish an explanation for this early installer reset. No exact
FreeBSD Raider/285HX reset duplicate was identified in the searches so far.

## ASRock X570 Taichi: preview.13 live boot and Wi-Fi

Observed 2026-10-15/16 through the console-approved remote debug listener.

- AMD Ryzen 9 3950X, 32 GiB RAM.
- NVIDIA GeForce RTX 4090, PCI `10de:2684` (ASUS subsystem `1043:88ef`).
- Intel Wi-Fi 6 AX200, PCI `8086:2723`, using `iwlwifi`.
- The USB root identifies itself as preview.13; the running kernel is the
  selected October 12 snapshot, `3ceb5f150bc1`.

The image boots to its live installer and permits a root SSH session over Wi-Fi.
WPA2 authentication completed and DHCP assigned an address and default route.
The primary DHCP-provided resolver timed out on direct queries; the secondary
resolver and gateway resolver answered. Reordering the existing DNS servers to
put the responsive secondary first made bounded hostname lookup and package
repository HTTPS probes pass. This was a live-session change; long-term Wi-Fi
stability and persistence across an installed-system reboot are not qualified.

The kernel log also contains an `iwlwifi0_com_lo -> ifnet_sx` lock-order warning,
Bluetooth HCI timeouts and USB re-enumeration failures. These are recorded
observations, not demonstrated causes of the DNS failures. The diagnostic image
had verbose boot enabled. Capturing `dmesg`, then setting `debug.bootverbose=0`
and `kern.consmute=1`, quieted console output while retaining the kernel log.

NVIDIA modules were not loaded during this inventory. PCI detection and a live
CLI boot do not qualify the NVIDIA driver, Hyprland, displays or suspend/resume.
All internal disks were allocated; no disk or partition was selected for writing.

The source installer now puts an eight-second outer timeout around its package
probe, including DNS resolution. Portable error/recovery tests and a native
FreeBSD test with a deliberately stalled fetch process passed. This fix is
newer than the already-built preview.13 image and needs a subsequent image.

### RTX 4090 driver and CUDA follow-up, 2026-10-16

The operator's subsequent preview.13 installation stopped at
`linux_base-rl9-9.8` with `kernel missing 64-bit Linux support`. The live kernel
had neither Linux ABI module loaded. Loading `linux` and `linux64` exposed
`kern.features.linux64: 1`; resuming only the package/configuration stages
completed the installation. Partitioning and base extraction were not repeated.
The installed recovery commands and Bash were already present before recovery.
Linux post-install caches were rebuilt inside the target, and its pool was
cleanly exported after testing.

The installed target has driver `595.104.02`, matching Linux NVIDIA libraries,
NVIDIA DRM `595.104.02.1600027_2`, core `omarchy-4.0.4_16` and desktop
`daemonarchy-1.0.1_2,1`. This is the recovered preview, not final 1.1 evidence.
Testing loaded its matching `nvidia.ko` into the still-running stock live
kernel; it did not reboot into the installed desktop.

- Native `nvidia-smi` reported NVIDIA GeForce RTX 4090, PCI bus `0e:00.0`,
  24,564 MiB VRAM, 49 C and driver 595.104.02. Its CUDA-version field was N/A.
- The Linux `nvidia-smi` ran through the Linuxulator and reported the same GPU
  and driver, with CUDA-version capability 13.2. That field alone does not
  qualify a CUDA workload or mean the toolkit is installed.
- The Linux executable built from `tests/cuda-probe.c` failed `cuInit` with
  error 304 without interposition. With the repository's UVM shim preloaded,
  it initialized CUDA, created a context, JIT-loaded an Ada PTX kernel,
  allocated GPU memory, copied input to it, launched and synchronized the
  kernel, and copied the correct result (42) back to the CPU. Cleanup passed.
- Linux proc/sys mounts and the target devfs were unmounted after testing.
  The target pool was exported again; the operator retains control of reboot.

The optional toolkit was not selected (`install_cuda=false`). This qualifies
the tested driver API/compute path with the shim, not toolkit installation,
cudalab rendering, every CUDA library, Unified Memory, or installed-system
Hyprland/display/suspend behavior. NVIDIA WITNESS lock-order warnings remain
in the kernel diagnostics; the test did not panic.

### ASRock post-recovery boot failure, 2026-10-16

After the recovered installation and live-session CUDA checks, the operator
reported that the ASRock system no longer visibly boots any operating system.
DEL, F2 and F11 did not bring up usable firmware setup or the boot menu. A brief
message said `Screen Optimization is not complete`. Its source has not been
established; display maintenance and GPU output selection are hypotheses, not
diagnoses. No post-failure disk or EFI inspection is available.

The recovery above resumed package/configuration work without repeating
partitioning, base extraction or EFI loader registration. No firmware flash or
Secure Boot key enrollment was performed on this machine. These facts do not
establish the cause of the subsequent failure or qualify other-OS preservation.

The operator requested that release work continue and community investigation
track this unresolved platform failure. Installed Hyprland, display behavior,
suspend/resume and physical Windows boot preservation remain unverified on this
system. Release notes must retain this limitation; successful live CUDA testing
must not be presented as successful installed-system boot qualification.

The operator also reports four DisplayPort connectors and one HDMI connector on
the GPU. Changed output selection/order is an additional hypothesis for the
missing display; it has not been demonstrated and does not explain the reported
firmware hang by itself. The operator explicitly requested that release work
continue while this platform is investigated by the community.


## Later 1.1 candidate / 1.1.1 preparation, 2026-10-17/18

The MacBook later reached a newer OSVERSION `1600027` installation but reset
repeatedly during userland package repair, before any desktop GPU startup.
No saved panic dump or confirmed reset cause is available. Repaired installed
files passed a full checksum check after a later reset. The package transaction
and postconfiguration subsequently completed and passed dependency/file checks.
A controlled AMD test then failed KGQ initialization and device attachment.
The 1.1.1 startup guard correctly rejects that state despite surviving DRM nodes;
the underlying GPU failure and desktop remain unresolved. See the detailed
[MacBook follow-up](testing-macbookpro16-1.md#11-candidate-recovery-follow-up-2026-10-1718).
This does not supersede the earlier BCE, GPU or sysctl failure evidence.

The requested HP All-in-One 24-cb1xxx upgrade began from OSVERSION `1600026`
with AMD Barcelo graphics. A separate rollback environment was preserved and
an inactive candidate received the matching 1.1.1 base/kernel/lib32 plus a
conflict-free configuration merge. Offline validation passed the signed boot
profile, all installed package checksums and dependencies, 376 selected
application identities/versions/automatic flags, account preservation and 184
kernel-module locks. Original EFI loaders and Windows firmware settings were
preserved. A one-shot candidate boot was selected while retaining the old
persistent default; the target did not return to the network and console
evidence was requested. At that stage, successful new-system boot and a
boot/rollback cause were not established. Native desktop and rollback tests were pending;
offline preparation is not a physical-upgrade pass.

After the operator power-cycled the apparent hang, the HP returned to its
original OS1600026 default. Inspection and a native isolated fixture exposed
the original root's automatic-mount policy, which can cover a selected clone
and its devfs. After setting that original root to `canmount=noauto`, an
instrumented second trial booted the actual OS1600028 kernel and userland in
the intended 1.1.1 environment. Before/after-ZFS and after-SSH checkpoints
confirmed root continuity and intact devfs; networking and SSH returned within
37 seconds. EFI loaders and firmware settings remained unchanged. Native
desktop finalization and AMD rendering then passed, including an actual branded
1920×1080 Wayland greeter and native AMD EGL renderer. A controlled old-OS1600026
rollback and new-OS1600028 return both passed; 1.1.1 is now persistently active
with the original environment retained. At 06:07 UTC on October 18 the operator
confirmed that normal authenticated `jkh` login opens the desktop and that its
applications work. Suspend and
fresh-ISO installation remain separate qualification work.

The operator permits release publication with physical qualification limitations
retained in the notes. That authorization does not mark these tests as passed.
