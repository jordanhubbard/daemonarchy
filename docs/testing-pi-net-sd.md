# Pi 4 and Pi 5 onboard Ethernet and SD acceptance

The operator requires onboard Ethernet and native SD controller support to
complete both Raspberry Pi targets for 1.6. RPI-001 and RPI-002 in the
[active queue](roadmap/active-work.md) own this work. Attaching a USB network
adapter or having firmware load files from SD does not meet these requirements.

| Physical profile | Onboard Ethernet path | Native SD path | Current evidence and remaining work |
| --- | --- | --- | --- |
| Pi 4 Model B, BCM2711, 8 GiB returned board | GENET v5 with its PHY; FDT and ACPI attachment must be distinguished | BCM2711 SD controller with its selected firmware description | November 20 source99 UEFI/ACPI image reached userland on four CPUs with the initial ~3 GiB cap and seven successful probes. Its BCM6E4E Ethernet and BCM2847/BRCME88C SD nodes remained unattached. The existing FDT runners exercise GENET transfers and SD in simulation; physical acceptance remains open. |
| Pi 5 Model B, BCM2712 D0 | RP1 Cadence GEM, reached through the real RP1 PCIe nexus, clocks, pinctrl, interrupts and DMA | BCM2712 SDHCI with its clock, pinctrl, voltage and card-detect providers | The source has the BCM2712 SD/provider implementation and host controls. Physical boot and native SD results remain pending. The source tree has no completed RP1 Ethernet attachment. The early-stage diagnostic image is a boot-boundary control. |

Pi 5 Ethernet differs from Pi 4 GENET. Raspberry Pi documents RP1's
[Cadence GEM Ethernet block](https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/RP-008370-DS-1-rp1-peripherals.pdf)
and [RP1's PCIe-connected peripheral architecture](https://www.raspberrypi.com/documentation/computers/io-controllers.html).
The existing FreeBSD Cadence driver cannot be claimed as RP1 support solely
because a compatible string or device-tree node exists.

## Development order

1. Preserve the returned diagnostic images and exact kernel/world/firmware
   identities. Keep the known-booting Pi 4 ACPI control available.
2. Exercise the existing Pi 4 FDT boot path on the actual board to test its
   existing GENET and SD drivers together. Compare driver attachment, resource
   windows, PHY configuration and DMA with the captured ACPI gaps. If ACPI is
   retained as a supported boot path, implement and qualify its missing
   frontends separately; simply adding device IDs is insufficient.
3. Use the Pi 5 D0 early-stage control to establish whether firmware reaches
   U-Boot, the EFI loader, the kernel and userland. Keep these boundaries visible.
4. Qualify the existing BCM2712 SD path with physical card detection, controller
   commands, interrupts and payload reads. Firmware reads alone do not qualify it.
5. Complete and qualify the RP1 nexus/interrupt/DMA, clock and pinctrl
   dependencies, then the Cadence Ethernet integration. Preserve working Pi 4
   and Pi 5 SD paths while adding RP1. A synthetic PCIe endpoint does not stand
   in for the RP1 device.

## Required physical evidence

For each board, retain exact image hash, source revision, firmware/EEPROM,
board/SoC stepping, RAM, boot description (ACPI/FDT), test-card identity and
actual driver tree. Bind every result to that selection.

Ethernet acceptance requires the onboard driver and PHY to attach, expected
MAC identity, carrier negotiation, DHCP/address/route acquisition, and
bidirectional transfers with independent payload hashes. Record packet counts,
errors/drops and link unplug/replug recovery. The interface's device ancestry
must identify GENET or RP1 GEM, rather than a USB adapter. Repeat cold and warm
boots and exercise network/storage DMA together under the selected memory cap
and the intended full-RAM profile.

SD acceptance requires native kernel discovery of the controller and card,
correct capacity, read-only reads of known card contents with independently
verified hashes, and scratch-write/readback on an explicitly approved disposable
partition. Preserve boot files, traces and unrelated media. The root transport
must be recorded: successful USB-root boot does not establish SD-root boot.
If SD boot is selected, demonstrate the native SD-backed root and reboot after
firmware handoff. Repeat cold/warm boot and card-detect/recovery where supported.

Capture `dmesg`, `devinfo -rv`, `sysctl kern.disks`, `ifconfig -a`, driver/PHY
status, native disk information, transfer outputs, hashes and bounded probe
exit statuses. A missing driver or failed probe remains an explicit failure.
Local compiler controls and simulator results support development; only actual
board results close these physical acceptance items. Hosted CI is bypassed by
the operator's direction while GitHub credits are exhausted.
