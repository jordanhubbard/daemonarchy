# MacBookPro16,1 interrupted installation, October 22, 2026

HW-002 extends HW-001 with a current physical reproduction. This is diagnostic
and recovery evidence, not completed installation, desktop acceptance or final
release hardware attestation. The MSI RTX 5080 laptop remains a separate next
hardware investigation.

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
SSH and independent native-worker ping probes failed. A new boot has not been
confirmed; transport loss alone is not counted as a reboot.

Twenty-nine additional packages reached verified durable checkpoints. The last
was `qt6-imageformats`, leaving 122 planned packages. `qt6-networkauth` extraction
printed completion, but it did not reach its verification/barrier checkpoint.
Its integrity must be checked after recovery rather than assumed.

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
