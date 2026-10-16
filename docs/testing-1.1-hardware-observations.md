# Physical hardware observations

These are operator-reported development results, not a completed acceptance
matrix. Record the exact image and last visible boot message when available.

| Platform | Image / test | Observation | Qualification |
| --- | --- | --- | --- |
| MSI Raider 18 HX, RTX 5080 | preview.11 and 1.0.1 USB boot, reported 2026-10-15 | Both images reset very early during kernel startup/probing and return to Windows; exact last message not yet captured | Failure predates preview.11; installer boot failed and NVIDIA driver/session tests were not reached |
| T2 MacBook Pro | Development USB / installed-system investigation, 2026-10-15 | Black screen; internal keyboard unavailable in single-user mode; explicitly preloading `apple_bce` produced a queue-registration panic | Unqualified; original black-screen cause and exact panic backtrace unresolved |

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

## MSI comparison reports

The operator subsequently reproduced the early reset with Daemonarchy 1.0.1.
The observed failure therefore predates preview.11. A stock FreeBSD boot result,
exact machine/CPU and BIOS revision, and a final probe line remain missing.

A closely matching first-person hardware report was found on 2026-10-15:
[Slackware installer resets on MSI Raider 18 HX AI](https://www.linuxquestions.org/questions/slackware-installation-40/slackware-current-usb-boot-grub-hangs-msi-raider-18-hx-ai-4175764459/).
The May 22–27, 2026 thread identifies an A2XWIG, Core Ultra 9 285HX, RTX 5080
and BIOS E1824IMS.316. Its installer hard-resets after about 15 seconds. The
reporter says Debian, Manjaro and Void installer media boot, and disabling ACPI
changes the reset into a hang. No working Slackware fix is recorded in those
posts. This is Linux evidence, not a confirmed FreeBSD duplicate or a diagnosis
of this operator's machine; its exact model and BIOS are not yet confirmed.

FreeBSD [bug 287342's initial report](https://lists.freebsd.org/archives/freebsd-bugs/2025-June/028114.html)
concerns Arrow Lake desktop I/O instability after boot on different hardware.
It does not establish an explanation for this early installer reset. No exact
FreeBSD Raider/285HX reset duplicate was identified in the searches so far.
