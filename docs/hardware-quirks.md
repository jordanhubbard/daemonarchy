# Hardware quirks

Entries describe observed behavior on specific hardware and firmware. A pending
diagnostic is not a validated workaround or an automatically applied setting.

## MSI Raider 18 HX AI A2XWIG: early installer reset

Status: **boot blocked; cause unresolved**. Reported 2026-10-15.

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
kernel startup/probing, returning to Windows. No panic backtrace or final probe
line has been captured. The behavior predates preview.11. Desktop and NVIDIA
driver qualification have not been reached.

The operator is using this same laptop for the current test conversation;
rebooting it into a USB test interrupts that session. Diagnostic instructions
should be available before leaving Windows. Windows machine/account identifiers
are unnecessary for identifying this quirk.

### Pending diagnostic comparisons

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


## Apple T2 MacBook Pro: incomplete installation and resets

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
