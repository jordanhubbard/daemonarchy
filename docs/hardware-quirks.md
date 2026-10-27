# Hardware quirks

Entries describe observed behavior on specific hardware and firmware. A pending
diagnostic is not a validated workaround or an automatically applied setting.

## MSI Raider 18 HX AI A2XWIG: early installer reset

Status: **boot blocked; cause unresolved**. Reported 2026-10-15; boot video
reviewed 2026-10-18.

| Identification | Tested configuration |
| --- | --- |
| Model / SKU | Raider 18 HX AI A2XWIG / 1824.3 |
| Motherboard | MS-1824, REV:1.0 |
| CPU | Intel Core Ultra 9 285HX, 24 cores |
| GPU | NVIDIA GeForce RTX 5080 Laptop GPU |
| RAM | 32 GiB |
| Firmware | UEFI, American Megatrends E1824IMS.312, 2025-08-28 |
| Secure Boot | Off |
| Images reproducing the failure | Daemonarchy 1.0.1 and 1.1.0-preview.11 |

Both installer images start booting from USB and then reset very early during
kernel startup/probing, returning to Windows. The behavior predates preview.11.
The subsequently supplied video ends its readable output with
`atrtc0: Warning: Couldn't map I/O.` and then shows a blank display, without a
visible panic or backtrace. The exact image and loader settings for that video
still need identification. Desktop and NVIDIA driver qualification have not been
reached.

The operator is using this same laptop for the current test conversation;
rebooting it into a USB test interrupts that session. Diagnostic instructions
should be available before leaving Windows. Windows machine/account identifiers
are unnecessary for identifying this quirk.

### RTC comparison prompted by the video

The final visible device is the legacy AT real-time clock. In the inspected
[FreeBSD driver](https://github.com/freebsd/freebsd-src/blob/df615735960370255d3acc4ac2a6f4fd297b7461/sys/x86/isa/atrtc.c#L474),
the failed resource allocation prints this warning and continues into CMOS
register access. The warning itself is not a panic or proof of the reset cause.
The driver also exposes `hw.atrtc.enabled`; setting it to zero rejects its probe.

On one boot of the same image, enter these commands at the loader prompt:

```text
set hw.atrtc.enabled=0
set kern.panic_reboot_wait_time=-1
set debug.trace_on_panic=1
boot -v
```

This is a temporary diagnostic, not an automatic hardware quirk or a validated
fix. Record whether it reaches later device probes or the installer, hangs, or
resets again; preserve any new final line. Keep the image and other settings the
same so the comparison tests RTC attachment. See the
[dated video analysis](testing-1.1-hardware-observations.md#msi-startup-video-reviewed-2026-10-18).

### RTC-disabled result and next comparison

The follow-up `IMG_2157.MOV` visibly uses the RTC-disable and panic settings
above. It advances to non-PnP ISA probing, ending at `sc0 failed to probe on isa1`
before the display blanks; no panic or backtrace is visible. RTC exclusion
changes progress but does not fix boot. Repeated Intel SPMC power-state constraint
format warnings supply another investigation lead; deferred ACPI task messages
and the final unmatched syscons probe do not establish fatal errors.

For a separate boot of that same artifact, retain the three settings above and
add this single subsystem exclusion before `boot -v`:

```text
set debug.acpi.disabled="spmc"
```

This bypasses the System Power Management Controller driver, leaving other ACPI
subsystems enabled. The operator reports no difference with this exclusion; no
new video/log independently verifies the exact stopping point. It is not a
default or demonstrated fix. A separate pending single-CPU comparison removes
`debug.acpi.disabled`, retains RTC exclusion and the panic flags, and sets
`kern.smp.disabled=1`. See the [follow-up analysis](testing-1.1-hardware-observations.md#msi-rtc-disabled-follow-up-video-2026-10-18).

### Other pending diagnostic comparisons

1. Boot the checksum-verified stock October 12 FreeBSD mini-memstick image;
   record the outcome separately from Daemonarchy.
2. Capture verbose boot with a phone video if the reset prevents reading the
   final message. To retain ordinary panic output, enter at the loader prompt:

   ```text
   set kern.panic_reboot_wait_time=-1
   set debug.trace_on_panic=1
   boot -v
   ```

3. On a separate boot, compare with ACPI disabled:

   ```text
   set hint.acpi.0.disabled=1
   set kern.panic_reboot_wait_time=-1
   boot -v
   ```

   Record whether it resets, hangs, or reaches a later stage. ACPI disabling is
   a temporary diagnostic, not a supported operating configuration or a confirmed
   workaround. These loader settings apply to that boot; they are not written
   into the installed configuration. A reset outside ordinary panic handling may
   still occur. See [FreeBSD acpi(4)](https://man.freebsd.org/cgi/man.cgi?query=acpi&sektion=4).

### Reset-surviving trace stick

Filming the screen cannot show what runs after the last message. The
[hardware trace stick](boottrace.md) records every startup step in a UEFI
variable before it runs, files each boot's trace on the stick and boots the
next queued experiment; with the stick first in the boot order the loop is
unattended. Its first queue starts from the `/boot/d/1` legacy-ISA-off
preset that produced `sc0 failed to probe on isa1` as the last visible line.

### Related report

A [May 2026 Slackware report](https://www.linuxquestions.org/questions/slackware-installation-40/slackware-current-usb-boot-grub-hangs-msi-raider-18-hx-ai-4175764459/)
identifies the same model, CPU, board and GPU, with newer BIOS E1824IMS.316.
Its installer hard-resets after approximately 15 seconds; ACPI disabling changes
the reset into a hang. Other Linux installers boot there. That report supplies
a useful comparison, but does not establish a shared cause or a FreeBSD fix.

See the [hardware investigation record](testing-1.1-hardware-observations.md)
for image comparisons and source-image checksums. Append new firmware/image
results rather than replacing the configuration that reproduced this failure.


## Apple T2 MacBook Pro: graphics, Wi-Fi and resets

**Current release:** 1.3.1 carries the MacBookPro16,1 work below: Navi14
graphics, the built-in T2 keyboard and trackpad, and BCM4364 Wi-Fi with
firmware acquired from Apple recovery media or local media before the disk is
changed. The operator confirmed that all pre-production checks passed on this
MacBook; an additional physical run of the final public ISO was waived, so the
final ISO bytes have not been installed on it. Firmware-enforced Secure Boot,
suspend and the NVMe fix below are not part of that claim. See the
[1.3.1 release notes](release-1.3.1.md) and
[MacBook acceptance record](testing-macbookpro16-1-1.3.1.md).

Read the [MacBook application note](application-note-macbookpro16-1.md) and
[installer investigation](testing-macbookpro16-1-installer-20261022.md) for the
Radeon Pro 5500M and BCM4364 Wi-Fi evidence. The EFI framebuffer overlap fix
passed three clean GPU boots. The refreshed graphics package reached SDDM's
Wayland greeter, and the operator subsequently logged into its desktop on the
T2 keyboard test kernel. The BCM4364 is PCI `14e4:4464`, Apple
subdevice `106b:07bf`. It was initially unbound; a private driver and
board-firmware preview later attached it and passed isolated gateway and
Internet traffic tests. The 1.3.1 installer adds verified firmware acquisition.
Wired USB Ethernet is verified.

The built-in T2 keyboard's synchronous LED-output reports blocked the desktop
input path. A targeted quirk passed native GENERIC build and a one-boot MacBook
probe with the global LED bypass off. The operator entered a password and
reached the desktop; the pointer was initially very laggy but then worked.
Sustained input and reliable clicking still need qualification.

A physical S3 test on the installed 1.1.1 system did not resume cleanly.
The screen initially stayed black; later ACPI PCIe power-method timeouts,
temporary input loss, Broadcom firmware failure, and a stale wireless default
route were observed. The wired gateway responded once wireless was down and
the wired route was selected. This test does not qualify suspend on the new
image; see the [S3 trial](testing-macbookpro16-1-s3-20261024.md).

The MacBookPro16,1 investigation includes earlier BCE/GPU failures and a later
1.1 candidate that repeatedly restarted or powered off during ordinary package
installation, before desktop graphics startup. A missing desktop after that
reset is not proof that installation finished. The retained state and package
integrity must be inspected before retrying; do not repeat partitioning over
the existing installation merely to resume packages. No reset cause or
fully qualified 1.1.1 installer result is established despite the later desktop
login on the repaired installation.

The internal T2 SSD (ANS2, `106b:2005`) raised a fatal controller status
under concurrent writes on both the 1.1.1 and 1.3.1 kernels. That fault
interrupted package installation. The cause is the order in which the driver
acknowledged completions, and a driver fix is under review; the published
1.3.1 kernel does not include it. See the
[October 26 NVMe record](testing-macbookpro16-1-nvme-20261026.md). Kernels
without the fix can avoid most failures with `hw.nvme.io_trackers=4`, but
this is only a workaround: queue depths of 4 and 8 still faulted in raw-write
tests.

Use named sysctl keys on this machine: broad `sysctl -a` enumeration previously
triggered a confirmed LinuxKPI `sysctl_handle_attr()` general-protection fault.
The [dated investigation](testing-macbookpro16-1.md) records what was repaired
and what remains unqualified. The [rescue guide](rescue-console.md) covers stale
pairing cleanup, and the [continuous diagnostics guide](remote-agent-debug.md#continuous-diagnostics)
explains what can be retained while approved SSH access is available.
