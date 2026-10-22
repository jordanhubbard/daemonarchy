# MacBookPro16,1 interrupted installation, October 22, 2026

HW-002 extends HW-001 with a current physical reproduction. This is diagnostic
and recovery evidence, not completed installation, desktop acceptance or final
release hardware attestation. The MSI RTX 5080 laptop remains a separate next
hardware investigation.

## Current qualification state

| Check | Result |
| --- | --- |
| Recovered package installation | Full dependency/file verification passed, including after forced power-off |
| NVMe under four trackers | Package recovery completed; earlier fatal-status cause remains open |
| Physical EFI countdown | Boots through to the operating system without Enter |
| Retained debugging grant | Same approval/host identity and unattended resumption verified over multiple reboots |
| Navi14 graphics attachment | Reproducibly fails enabling graphics queues; desktop acceptance blocked |
| Independent hardware diagnostics | Pending; health counters alone do not exclude a fault |

## Inputs and observed discrepancy

The operator reports that the installer claimed success. The installed target
instead retains `status=in-progress`, `phase=install`, no exit code/update marker
and no final package-integrity record. The installer log ends during OpenJDK
extraction, package 1026/1188; the package database contains 1040 registrations,
including eleven later registrations whose log lines were not retained. The
success-screen report has not yet been independently reproduced or explained.

The attached USB identifies itself as `1.1.1 (1.2 loader-debug test 1; 1.1.1 base)`.
Its installer, launcher and dashboard match the retained controller implementation.
Its installer helper SHA256 values are:

| Helper | SHA256 |
| --- | --- |
| install | 62604c6c465ecae20c4efa2aca6dbcb06c355028f565ca3bf4fd59c7d69500e0 |
| launch | 42a106a7afa26ac50e0d13ac8a85dd453952d4a755cf08a23fc0c943d9a051c0 |
| dashboard | fbd702ace484a086bcb46378880d3333ba71888c6f97f2ec166e06367bb33c1a |
| install-integrity | 5f7756747fb99edb875d4fd69850d2a1dcff5c4a329989144ca6f87337c31bd7 |
| install-diagnostics | 20b376225b1e920820fadd80112dd1893cbcada245f386e108ec29f0f000f4ba |

This does not independently verify every byte of the USB against the
[test ISO artifact](testing-1.2-test-iso.md). The running stock kernel identifies
source `bdcfeac3e1cb`, OSVERSION 1600028. Installed DRM is
`drm-612-kmod-6.12.110.1600028_5`; no AMD GPU module was loaded during these tests.

## Integrity and bounded recovery

Native dependency verification passed, but full installed-file verification
failed with **1158 checksum mismatches across twelve packages**. Damaged files
included zero-length Ghostscript payloads. Samples differed from the corresponding
files read directly from cached archives. All affected package registrations fell
in the final two seconds of the retained original transaction. Package database
consistency therefore did not establish payload integrity.

The pool was ONLINE with zero read/write/checksum errors. NVMe SMART reported
zero media errors and 96 lifetime unsafe shutdowns. Neither observation explains
the interruption or excludes a controller/driver failure. Crash dumping was
disabled, and all phase-boundary kernel logs were identical. They contain no
later package-phase failure record.

A pre-repair boot environment was retained. Each damaged package was reinstalled
from its exact cached version, individually verified and followed by `zpool sync`.
All twelve passed. A second boot environment retained that repaired state.

A private offline repository combined the existing cache and attached ISO. The
native resolver planned 151 additional packages, without upgrades or removals.
Every planned archive's name/version and native `FreeBSD_version` were checked
against OS1600028 before installation; architecture-independent packages could
omit that annotation. Installation followed dependency order, with individual
file verification, pool synchronization and an on-target checkpoint per package.

## Reproduced fatal NVMe event

At **19:12:05 UTC**, while installing `qt6-networkauth`, the independent controller
receiver retained the kernel's fatal-timeout/reset message, then a controller
start event and repeated reset-wait messages. The receiver retained heartbeats
through **19:12:18 UTC**, then recorded SSH exit 255 at **19:12:33 UTC**. Subsequent
SSH and independent native-worker ping probes failed. At that point a new boot had not been
confirmed; transport loss alone was not counted as a reboot.

Twenty-nine additional packages reached verified durable checkpoints. The last
was `qt6-imageformats`, leaving 122 planned packages. `qt6-networkauth` extraction
printed completion, but it did not reach its verification/barrier checkpoint.
Its integrity required checking after recovery rather than assuming success.

A separate bounded DTrace session watched ACPI button/sleep paths, shutdown
requests, reboot syscalls and signals to init. A harmless `kill(1, 0)` verified
caller/stack capture. It retained no real shutdown/reboot event before loss of
access. Its scope does not exclude T2 firmware reset, panic or an event after
trace/network delivery ceased.

The SMC shutdown-cause value was `-20`, undecoded by the selected source. The
thermal-status `prochot` field means enabled in that driver, not proof of current
overheating. Sampled CPU/GPU temperatures were 57/58 C shortly before failure.

[FreeBSD bug 298197](https://lists.freebsd.org/archives/freebsd-bugs/2026-September/036371.html)
reports the same fatal/reset/waiting sequence under internal-SSD load on a T2
Mac mini. This is a related upstream report, not proof of identical root cause.
Native source tracing locates the message in `nvme_qpair_timeout` after the
controller fatal-status bit is read, followed by reset-task scheduling. The
underlying trigger and failed recovery stage remain unresolved.

## Next controlled checks

1. Retain the physical console state and establish whether the target hung,
   powered off or rebooted. Recover access before another package transaction.
2. Check the durable checkpoint, active boot identity, newest kernel evidence and
   affected package files; preserve both recovery environments.
3. Trace entry/return through available NVMe reset-task, queue-disable and
   controller-disable probes during a bounded retry. The prepared 600-second
   trace compiles on the native worker using its actual probe inventory; inlined
   functions and tail calls have no separate entry/return probes. Compare the exact snapshot's
   Apple ANS2 implementation with the selected next-release source.
4. A separate boot test can reduce the existing `hw.nvme.io_trackers` tunable to
   four to isolate outstanding-I/O pressure. Record it as a diagnostic setting,
   not a validated fix or release default. Keep other storage variables fixed.
5. Complete installer postconfiguration, full integrity and dependency checks,
   then qualify real GPU attachment, authenticated desktop/application rendering,
   input, peripherals and reboot/recovery on the eventual exact release image.

Raw controller captures, package plans, trace output and private recovery scripts
remain outside Git. No signing keys, private worker addresses or credentials are
part of this record. No hardware gate is closed by this investigation.

## Recovery and bring-up fixes

After the operator booted the target again, its new boot identity confirmed a
reboot. Full file verification found 61 damaged files in the interrupted
`qt6-networkauth` package and no damage in the earlier verified package
checkpoints. Package repair/completion remains pending the storage diagnostic.

The operator additionally reported that the installed loader remained at its
three-second autoboot prompt until Enter. Native inspection found that amd64 EFI
timeouts use the firmware wall clock. A candidate uses a periodic EFI timer,
seeded once from the wall clock, to advance deadlines even if GetTime fails or
stops advancing. The actual production C file reproduces the old failure under a
frozen-clock control and passes six native controls after correction. A fresh
stand build passes. Actual OVMF execution counts down without input and returns
to firmware without a timer callback into unloaded loader code. The first VM
probe exposed that missing exit cleanup; the corrected candidate and failed
evidence are both retained. Physical countdown observation remains separate.

DEBUG-002 changes installed-system pairing into a durable, explicitly approved
hardware-debugging grant. A root-only store retains the approved client key,
server identity and evidence; recovery refreshes runtime ownership and refuses
unknown keys without console approval. Native real-SSH fixtures cover legacy
listener adoption, preservation across shutdown, stable host pinning, unrelated
reused PIDs, old-generation teardown, repeated resume and explicit revocation.
Initial storage-parent creation and boot-console resumption are also checked.

The first physical upgrade/reboot exposed an adoption defect: copying the old
generation lets an old running shell's cleanup revoke the adopted grant. The
corrected migration gives the grant new ownership before retiring the old
collector; a native regression verifies that old cleanup cannot revoke it and
that explicit Unpair cannot reimport the retired grant. Physical automatic
reconnection must be verified after deploying this correction.


## Controlled retry with four outstanding requests

The corrected pairing helper was deployed and a controlled reboot completed.
The operator reported reaching the rescue selection menu without intervening at
the loader countdown, then selected Resume. SSH admitted the previously approved
agent with the identical retained host-key digest. This verifies approval and
server-identity persistence and manual resumption; it does not verify unattended
listener startup. The boot clock initially returned to 1970 before NTP corrected
it; boot identity was distinguished by its changed value and short uptime,
without assuming wall-clock values must increase.

The first resumption attempt can precede DHCP readiness. A correction retries
for up to 60 seconds in the background without blocking the recovery menu. A
native FreeBSD console test covers delayed readiness and absence of a grant;
a subsequent physical reboot reconnects without console selection about fifteen
seconds into the new boot, with the same approved client and server identity.
The unattended listener has no console-approval marker. The diagnostic GPU
service remains suppressed during that resumption test.

The running NVMe queue reported four trackers. The interrupted
`qt6-networkauth` payload was reinstalled from its exact cached archive and
verified. The other 121 pending archives passed version/ABI/dependency preflight,
then installed individually with file verification and two pool barriers per
checkpoint. All reached durable checkpoints. A bounded native DTrace session
watched controller reset, disable and failure paths, with an independent
controller-side observation stream; no reset event was captured during this
package run. Installer postconfiguration was then restored from the on-media helpers, including
ordered GPU configuration, kernel-module locks, ownership/caches, signed package
feeds and ISO fallback, checkout catalogue, user shell/sudoers, and SDDM state.
The requested ordinary SSH service received fresh host keys; the debugging
listener retained its existing separate host identity. Full installed dependency
and file verification passed, followed by a pool barrier and healthy ZFS status.
The original incomplete installer state was preserved before recording recovered
completion, and a pre-GPU recovery boot environment was retained. This recovery
does not explain the originally reported success screen.

The current SSD health report gives no critical warnings, 100 percent spare,
2 percent estimated wear and zero reported media errors. The generic error-log
page is rejected as unsupported, and Identify reports no NVMe device self-test
support. These limits are recorded rather than counted as successful hardware
tests. The cause of the earlier fatal controller status remains unresolved;
completion under this diagnostic tunable does not establish a release fix or
exclude intermittent hardware failure.


## Separate Navi14 graphics initialization failure

After package integrity and recovery were verified, a separately captured
manual graphics start loaded the exact DRM 6.12.110 module and Navi14 firmware.
Firmware loading and SMU initialization succeeded, but
`amdgpu_gfx_enable_kgq` reported `KGQ enable failed` and `gfx_v10_0` initialization
returned -60. Device attachment failed. The ordered graphics service correctly
refused its readiness marker, despite the module remaining loaded. SSH remained
available and the bounded NVMe trace recorded no reset during this attempt.
Desktop acceptance therefore remains blocked. The selected upstream source
exposes a default-enabled asynchronous graphics-ring path and a supported
`compat.linuxkpi.amdgpu_async_gfx_ring=0` alternative; a fresh-boot single-variable
comparison is the next diagnostic, rather than treating module load as success.


The fresh-boot comparison confirmed the alternative graphics-ring parameter was
zero, with the NVMe tracker setting unchanged. Graphics initialization still
returned -60. Cleanup then repeatedly timed out writing GPU registers. The
independent receiver recorded last GPU register messages through 21:59:18 UTC
and SSH timeout at 21:59:37 UTC; independent ICMP probes also failed. No NVMe
reset event was captured by its separate trace. No reboot was requested during
this graphics attempt. Physical console state and a new boot must establish
whether the system hung, panicked or reset. Automatic graphics loading remains
suppressed for the next recovery boot. The failed alternative is not a workaround.

A diagnostic build passed against the exact stock kernel source
`bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` and the selected
`drm_v6.12.110_1` archive (SHA256
`9c99c05c3269271ca6ea19ccdca53b27517b1d6b679065fc5c3dfc2682ddfaef`).
Its additional ring-test diagnostics are investigative only. The separate module
remains staged outside the installed package; target execution is pending recovery
and is not implied by native build success. This does not qualify a release.


## First instrumented ring test

After the operator power-cycled the unresponsive target, rescue boot retained
approval and suppressed graphics loading. The original packaged GPU module
remained byte-identical, and full installed-file and dependency checks passed
after that forced power-off. The failed alternate queue parameter was removed
from persistent configuration and the original value of one restored before
loading the separately staged diagnostic module.

Diagnostic module SHA256
`8ab4005e1d61922c4d739977e0d0e65b94249cf51b2aa670e8c92a329e5c4781`
reproduced the initialization failure. Its ring-test log identifies
`kiq_0.2.1.0`, index 9, type 10, with doorbells enabled and a 100000-microsecond
timeout. Scratch register `0xc040` remained `0xcafedead` rather than the expected
GPU-written `0xdeadbeef`; the failing stage was asynchronous graphics-queue
initialization. This identifies a failed command-ring progress test, not its
underlying hardware or driver cause.

The module-load syscall returned successfully even though device attachment failed;
`devinfo` still showed no attached DRM device and no graphics readiness marker
was created. SSH remained available and bounded NVMe/shutdown tracing retained
no such event during the test. A second diagnostic adds read/write-pointer and
successful-test logging to distinguish the preceding compute-queue test from
the failing graphics-queue mapping. Its native build passes; fresh-boot execution
is recorded separately. Neither diagnostic replaces the packaged driver.


The second diagnostic module (SHA256
`b1b114e1ed8d2fa6e23fc1cdaddb44847afd48c13897057728700b5193566288`)
ran from a fresh rescue boot. The KIQ test following compute-queue mapping
passed with scratch `0xdeadbeef` and a write pointer of `0x200`. The test after
graphics-queue mapping failed with scratch `0xcafedead` and a write pointer of
`0x400`. The software-visible read pointer was zero in both cases, including the
successful test, so that value alone is not treated as proof of a stalled hardware
read pointer. The failure boundary is reproducible; its underlying cause remains
open. Both instrumented attempts returned with SSH available and no NVMe reset
or shutdown request observed before the next explicitly controlled reboot.


A further fresh-boot comparison used the same diagnostic module and original
asynchronous queue setting, with only `compat.linuxkpi.amdgpu_dpm=0` changed.
The driver confirmed both parameter values but failed earlier, reporting SMU
firmware loading failure before the instrumented ring tests. This is not a
successful workaround and does not isolate the original queue failure. The
runtime-only power-management setting was cleared and a clean rescue reboot
requested. The packaged driver remains unchanged; diagnostic modules remain
separate and automatic GPU loading remains suppressed.
