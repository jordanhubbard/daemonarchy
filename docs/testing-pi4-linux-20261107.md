# Pi 4 Linux baseline and first FreeBSD media, 2026-11-07

RPI-001 remains the first SBC implementation target. A physical Pi 4 has now
been identified and inventoried independently of the Pi 500 reference. This
records Linux behavior and staged diagnostic media, not a FreeBSD boot result.
Raw evidence and network addresses remain private.

## Observed Linux baseline

| Item | Observation |
| --- | --- |
| Board | Raspberry Pi 4 Model B Rev 1.5; revision `d03115`; `raspberrypi,4-model-b`, `brcm,bcm2711` |
| CPU / RAM | Four online Cortex-A72 r0p3 CPUs; 8 GB model, Linux MemTotal 7,996,852 KiB |
| OS / ABI | Debian GNU/Linux 12 bookworm; arm64 userspace and kernel, glibc 2.36, 4096-byte pages |
| Kernel | `6.12.25+rpt-rpi-v8`; installed arm64 kernel package and source version `1:6.12.25-1+rpt1` |
| Firmware | `5560078dcc8591a00f57b9068d13e5544aeef3aa`, 2025-04-30 |
| EEPROM / USB controller | Bootloader 2023-01-11 17:40:52 UTC; VL805 firmware `000138c0` |
| Native Ethernet | Linux `bcmgenet`, `fd580000.ethernet`; interface is down with no carrier, so no native Ethernet traffic result |
| Current control connection | SSH route uses `wlan0`; this is not an Ethernet result |
| Boot/storage | Initial inventory: one approximately 64 GB SD card containing the running root and boot filesystem. Separate USB diagnostic media was subsequently attached and written as recorded below. |
| Thermal observation | `throttled=0x0` at collection; no sustained thermal test |

The collector retained kernel configuration, firmware-modified FDT, boot config,
package/source identities, devices and firmware observations. The EEPROM query
returned status 1 and reported an available update in the installed package;
that output was preserved, and no update was applied. The remaining initial
probes succeeded. PiAware was running; no service, boot-file or EEPROM changes
were made. The original Debian installation image/checksum remains unknown.

| Retained installed input | SHA-256 |
| --- | --- |
| `/boot/firmware/kernel8.img` | `c6eb11fa5530b52d9ad7182e6ee7f085de50fc07b480e91ec0f301c6fc5d6f47` |
| `/boot/firmware/bcm2711-rpi-4-b.dtb` | `4bc9dd6182025add23a750b18ff748e46d4e939434530e8057c6bfa1ce6f1c16` |
| Captured kernel configuration | `e48631ff16cb4de147f8292647277ae305d3f455fa623b1a6e67f1710d62dbcf` |

## Boot path and staged diagnostic candidate

Both EEPROM configuration readers omit `BOOT_ORDER`. The
[documented empty-value default](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#BOOT_ORDER)
is SD first, then USB mass storage, repeated. This is interpretation of the
documented default, not an observed USB boot. The official
[EEPROM release notes](https://github.com/raspberrypi/rpi-eeprom/blob/master/firmware-2711/release-notes.md)
record GPT/FAT16 EFI partition support in October 2021, before this board's
installed bootloader. The candidate uses a conventional LBA-2 GPT table and
512-byte sectors. Start with the existing EEPROM as the control; native media
recognition and cold/warm boot still need physical evidence.

The Pi 4B UEFI diagnostic image is built and staged as a compressed file in the
target user's private cache, separate from its active boot filesystem. Its
decompressed SHA-256 was verified on the target:

`d6e28c32a439e8708978f3527835377bbd64d648022d83946d4abdaeba0af2a0`

It contains the matching existing 1.5.1 FreeBSD kernel/world, the newly tested
ARM EFI loader, a single four-CPU control, durable allowlisted init collection,
and pftf Pi 4 UEFI v1.53. The firmware ZIP is pinned to SHA-256
`ca9973e2a7a546b3df871cfb7382e656829114b6dfa424f40dc67cc90a217d88`;
every copied firmware file was read back. Its fixed 211-file map is valid.
The firmware's default 3 GiB cap stays enabled for the initial control. This
does not test all 8 GB, final-distribution installation or desktop usability.

## Next physical run

The separate 8 GB USB has now been written and its first 389,056,000 bytes
verified by direct readback against the candidate SHA-256 above. Device
identity, capacity, exclusive access and the running SD root were checked
before writing. The 64 GB SD card, boot configuration and running service were
preserved. This is media preparation, not a USB boot result.

Both physical boards are now unattended. Do not shut them down, reboot them
or change boot configuration while physical intervention is unavailable.
The [Pi 4 simulator checkpoint](testing-pi4-simulator-20261107.md) records the
independent work that can proceed in the meantime.

1. When physical intervention is available, recheck the prepared USB identity
   and image readback before the handoff.
2. At the hardware handoff, shut down Linux cleanly and retain its original SD
   card. For USB testing, remove that card while powered off so SD-first boot
   does not select the existing system. Boot the prepared USB without changing
   the EEPROM boot order.
3. Retain the UEFI/loader screen and ACPI snapshot. On a successful kernel boot,
   allow init to collect, reboot and stop, then preserve the returned media.
   A failure is useful evidence; do not infer boot progress from missing files.
4. Compare the UEFI/ACPI control with a separately selected FDT boot profile.
   Existing FreeBSD GENET attaches through FDT; Linux GENET attachment and an
   ACPI loader boot do not qualify FreeBSD's built-in Ethernet path.
5. Qualify full 8 GB RAM and USB/storage/network DMA before removing the memory
   cap for an accepted profile, then complete native display/input, installation,
   installed boot, update and recovery gates.

Until an attended physical boot is available, RPI-001 discovery and
implementation remain open. Pi 400/CM4 and Pi 5/Pi 500 have separate records.
