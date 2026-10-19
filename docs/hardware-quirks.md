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

Read the [MacBook application note](application-note-macbookpro16-1.md) for the
Radeon Pro 5500M initialization failure and unavailable BCM4364 Wi-Fi. The AMD
driver recognizes the GPU; age alone does not explain its failure. The wireless
controller was detected without an attached driver or wireless interface; use
the verified wired USB Ethernet connection.

The MacBookPro16,1 investigation includes earlier BCE/GPU failures and a later
1.1 candidate that repeatedly restarted or powered off during ordinary package
installation, before desktop graphics startup. A missing desktop after that
reset is not proof that installation finished. The retained state and package
integrity must be inspected before retrying; do not repeat partitioning over
the existing installation merely to resume packages. No reset cause or
successful 1.1.1 desktop result is established.

Use named sysctl keys on this machine: broad `sysctl -a` enumeration previously
triggered a confirmed LinuxKPI `sysctl_handle_attr()` general-protection fault.
The [dated investigation](testing-macbookpro16-1.md) records what was repaired
and what remains unqualified. The [rescue guide](rescue-console.md) covers stale
pairing cleanup, and the [continuous diagnostics guide](remote-agent-debug.md#continuous-diagnostics)
explains what can be retained while approved SSH access is available.
