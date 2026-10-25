# 1.3.1 early-kernel diagnostics

- **Status:** partial
- **Scope transfer:** unfinished transport work is superseded by the
  [1.3.2 implementation plan](release-1.3.2.md) and
  [issue #33](https://github.com/jordanhubbard/daemonarchy/issues/33).
  The original assignment and artifact evidence below are historical.
  Product #27 closed after prerequisites merged; the complete feature remains
  open under DEBUG-003 for 1.3.2. The new explicit plain mode supersedes the
  authentication requirement below for this boot debugging workflow.
- **Tracking:** [Issue #27](https://github.com/jordanhubbard/daemonarchy/issues/27), [1.3.1 milestone](https://github.com/jordanhubbard/daemonarchy/milestone/1).
- **Owning queue item:** [DEBUG-003](active-work.md#debug-003-deliver-bidirectional-loader-mountroot-and-panic-network-debugging-for-14)
- **Completion / archival evidence:** Pending exact native loader/kernel builds,
  pre-driver VM packet captures, separate image qualification and physical MSI
  built-in-NIC evidence. No current connection or passing receipt is claimed.
- **Operator scope, October 23:** the 1.3 release is already in progress.
  Early-kernel network connection work belongs to **1.3.1**. Keep the 1.3
  branch, selected artifacts and release process undisturbed.

## Required result

On the MSI Raider 18 HX AI A2XWIG/RTX 5080, retain an explicitly approved wired
debugging connection from the UEFI loader into the kernel initialization that
currently resets without a visible panic. Bring-up uses the **built-in NIC**;
USB adapters and Wi-Fi are outside this acceptance target. Generalize the
selection and status interface for other built-in Ethernet devices without
claiming unsupported hardware works.

The operator has already tried the ACPI-on/SMP-disabled and panic-retention
settings without changing the reset. Do not request that comparison again.
ACPI-off reports `APIC: Could not find any APICs`; this different failure does
not explain the original reset. The currently booted medium is described as
the latest pre-1.3 ISO; its exact filename/hash remains unrecorded.

## Completion checks

- [ ] Provide a discoverable boot-menu setup flow and matching controller;
  retain local recovery, explicit approval and revocation.
- [ ] Identify the selected built-in NIC by firmware path, MAC and PCI identity;
  bind it and the exact kernel/image to one boot identity.
- [ ] Establish actual packet exchange after `ExitBootServices` and before
  normal PCI/NIC attachment. Loader-only output, a retained identity variable,
  post-boot SSH and initialized-driver NetGDB do not close this requirement.
- [ ] Retain early startup and driver-probe boundaries on the controller, with
  explicit output loss and last-observed-stage reporting. Silence alone never
  proves a reset or identifies the failed callback.
- [ ] Preserve session authentication across the transition without exporting
  keys through inspectable environment variables or captures. Reject forged,
  replayed, wrong-boot and malformed control messages.
- [ ] Bound absent-peer, link-loss, cancellation and reconnect paths; keep the
  local console usable. Hand network ownership to the native driver safely.
- [ ] Build exact FreeBSD loader/kernel products and retain independent VM
  captures for a deliberate pre-driver panic and hard-reset case, successful
  continued boot and transport-failure controls.
- [ ] Assemble a separate 1.3.1 diagnostic image with exact inputs and hashes;
  qualify its boot/trust closure without changing the in-progress 1.3 image.
- [ ] Capture the real MSI initialization over its built-in Ethernet port.
  VM e1000 acceptance does not qualify the MSI firmware or NIC.

## Current boundary and implementation direction

The source fork has an authenticated SNP-based loader console and a guided
activation candidate in [source PR #20](https://github.com/jordanhubbard/daemonarchy-src/pull/20).
[Source PR #22](https://github.com/jordanhubbard/daemonarchy-src/pull/22) adds
read-only PCI/UNDI runtime-capability inspection, authenticated kernel-phase
identity controls and an isolated native loader build. These are prerequisites,
not the kernel transport. It also has scoped native NetGDB/Netdump development
evidence once the native
driver is initialized. Neither implements the required early connection.

SNP is a boot-services protocol and cannot simply be called after firmware
handoff. Investigate runtime UNDI capability on the selected built-in device
and a kernel-owned polling backend; admit an actual runtime implementation,
memory mapping, callbacks and DMA ownership before calling it from the kernel.
The [UEFI UNDI definition](https://uefi.org/specs/UEFI/2.11/Apx_E_Universal_Network_Driver_Interfaces.html)
and [runtime-driver guidance](https://tianocore-docs.github.io/edk2-UefiDriverWritersGuide/draft/25_network_driver_design_guidelines/252_nii_protocol_and_undi_implementations/)
describe that route. Presence of an NII/UNDI descriptor alone is not proof of
working post-handoff networking. If the actual firmware lacks that capability,
an explicitly supported early native backend is required for the built-in NIC.

Historical 1.2 development records retain their original scope. This operator
decision assigns the continuous early-kernel transport and MSI capture to
1.3.1; it does not silently waive unrelated acceptance or publish a release.

## Firmware preflight checkpoint

The [development record](../../verification/earlynet-131-inventory-development.json)
binds source `51924656dcb3`, its native FreeBSD build and a separately booted
16,811,520-byte GPT/FAT inventory image. Native descriptor/protocol/setup
controls and controller regression pass. Actual UEFI QEMU boots with e1000 and
with no NIC reach the automatic inventory and loader prompt; both VMs stop
cleanly and leave the image bytes unchanged. The earlier invalid-FAT and
missing-loader-root attempts remain failures, not successful boot evidence.

The image automatically prints `PCI Ethernet`, the firmware NIC MAC/location
when available, and `UNDI` status. It contains no kernel, installer or private
keys and does not start the NIC or modify internal disks. Use the
[exact CI artifact](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/39924040948/artifacts/12487884623),
which includes `daemonarchy-1.3.1-firmware-inventory-amd64.img`. Write the image
to a spare USB medium and boot it as UEFI with Secure Boot disabled for this
unsigned development loader. Retain the MSI's PCI and UNDI lines. No kernel
boot is needed to collect them.

This is the required hardware/backend preflight, **not** the completed early
kernel connection. The actual kernel producer, runtime mapping/callbacks,
pre-driver packets and MSI acceptance remain open under DEBUG-003.

## USB report checkpoint

The [USB persistence development record](../../verification/earlynet-usb-report-development.json)
binds source `3db23a770643`, its successful native FreeBSD build and the revised
probe. Use [this revised CI artifact](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/39963296120/artifacts/12505319001)
for automatic saving; the earlier image above only displays inventory.
The revised `daemonarchy-1.3.1-firmware-inventory-amd64.img` has SHA256
`6693284dead657517349cc67c4b8acb68fe8c60d919287eb6d35898356559db9`.

Write the revised image to a spare USB and boot it as UEFI with Secure Boot
disabled for this unsigned loader. It automatically saves selected model/BIOS
fields and PCI/MAC/UNDI inventory to `DAEMDBG/BOOT0001.TXT`; later boots use the
next unused number. Wait for **Saved and verified USB report**, then remove the
USB and bring back its `DAEMDBG` folder. No screen photographs are required.
This report contains firmware inventory, not kernel logs.

The writer requires the purpose-built marker on the exact loaded USB device,
flushes and verifies the saved bytes, preserves previous reports, and refuses
non-USB boot paths. Read-only/full media or I/O failures show **save FAILED**;
there is no fallback to another disk. Actual UEFI USB VM tests passed two boots
with both reports retained, read-only USB failure and non-USB refusal. All cases
left the attached writable internal disk unchanged. MSI physical acceptance and
the actual early-kernel connection remain open.
