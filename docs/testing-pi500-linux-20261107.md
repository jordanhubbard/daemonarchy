# Pi 500 Linux reference, 2026-11-07

This is a physical Linux reference for RPI-002 and ARM-003, not FreeBSD
qualification or a Pi 4 result. Pi 4 remains the P0 SBC target ahead of the
P1 Pi 5 family. The supplied target identified itself as Pi 500, so no Pi 4
firmware or diagnostic image was written to it. Its boot files and EEPROM
were left unchanged. Raw captures and network addresses remain private.

## Observed baseline

| Item | Observation |
| --- | --- |
| Board | Raspberry Pi 500 Rev 1.0; board revision `d04190`; `raspberrypi,500`, `brcm,bcm2712` |
| CPU / RAM | Four online Cortex-A76 r4p1 CPUs; Linux MemTotal 8,142,664 KiB |
| OS / userspace | Raspbian GNU/Linux 12 (bookworm), **32-bit armhf**, glibc 2.36 |
| Kernel / pages | **64-bit** `6.12.115+rpt-rpi-v8`, 4096-byte pages, ARM32 compatibility enabled |
| Kernel source package | `linux`, `1:6.12.115-1+rpt1`; active v8 image package is `arm64` despite default userspace architecture `armhf` |
| Bootloader / firmware | EEPROM timestamp 2026-09-25 15:59:09 UTC; firmware version `1accd665` |
| PCIe / RP1 | BCM2712 bridge `14e4:2712`; RP1 southbridge `1de4:0001`, bound to Linux `rp1` |
| Native Ethernet | `eth0`, **Cadence GEM / Linux `macb`**, `raspberrypi,rp1-gem`, `cdns,macb` |
| Graphics observations | `vc4-kms-v3d` overlay; HDMI-A-1 connected; an Xorg process running. Interactive desktop/input acceptance was not performed. |
| Thermal observation | `throttled=0x0` at collection; no sustained thermal-load test |

The updated `tools/hwtrace/pi-reference.sh` ran natively with root-readable
diagnostics and every probe returned status zero. It retained kernel config,
firmware FDT, boot configuration/hashes, package versions/source identities,
devices and explicit kernel/userspace/page-size observations. The original
Linux installation image/checksum is not known; installed-input hashes below
do not establish its original media identity.

## Retained input identities

| Input | SHA-256 |
| --- | --- |
| `/boot/firmware/kernel8.img` | `02c2c04b09c5cf13c6f1378a5052ed3ccf62ea5b17ab9b511400cdf9673a4cd7` |
| `/boot/firmware/bcm2712-rpi-500.dtb` | `400b2da08abb8fd0ffd65085d1e0e1e6c6d01cadd27385403ea3a3fd5a1537f4` |
| Captured kernel configuration | `651d09a268cb211dde12f0ab9915c558af82a557b6b2b629c2f01ecab8da381c` |

The firmware-modified FDT is retained privately separately from the boot DTB;
firmware edits/overlays can change the handoff. Package source version identifies
the installed source lineage, not an independently resolved Git commit.

## Native Ethernet evidence and driver correction

A generated 4,194,304-byte file traveled to the Pi and back over SSH/SCP using
the route through built-in `eth0`. Controller, target and returned bytes matched
SHA-256 `957f3e5c3683eb9e7ab7eb18e3fd4ba0a3912763e3fd5788a3660a65a9335f4f`.
This is a Linux transfer-integrity result, not a throughput benchmark, packet-loss
stress result or FreeBSD network result.

This corrects the first roadmap's RP1/GENET conflation. Pi 4 BCM2711 uses GENET;
Pi 5-family RP1 Ethernet is Cadence GEM. The
[Raspberry Pi Linux reference](https://github.com/raspberrypi/linux/blob/2569533d6c33c15231fbc21704c87fcebc67173c/drivers/net/ethernet/cadence/macb_main.c)
selects `raspberrypi_rp1_config` for `raspberrypi,rp1-gem`, with RP1 capabilities,
clock handling, a DMA burst length of 16 and jumbo/PTP support. The corresponding
[RP1 device tree](https://github.com/raspberrypi/linux/blob/2569533d6c33c15231fbc21704c87fcebc67173c/arch/arm64/boot/dts/broadcom/rp1.dtsi)
describes the Ethernet interrupt, four clocks and AXI transaction properties.
This is a pinned comparison reference, not a claim that its Git revision equals
the installed kernel package.

The owned FreeBSD source at `f408bd065cb` has `sys/dev/cadence/if_cgem.c`, but
its compatibility table does not include either RP1 binding. Its existing
clock, PHY and DMA code is a predecessor to audit, not a working RP1 port.
First resolve the RP1 PCIe nexus, interrupt mapping, clocks/reset and DMA address
translation; then audit CGEM capabilities, descriptors, cache/DMA coherency,
queue/interrupt behavior and PHY setup before adding any RP1 match. A compatible
string alone is insufficient. Keep Pi 4's separate GENET path.

## Remaining hardware work

- Identify and capture the actual Pi 4 before its FreeBSD bring-up; the Pi 500
  reference does not close RPI-001 discovery or change its priority.
- Resolve the Linux installation-image identity and a maintained boot/firmware
  profile for this Pi 500 before its eventual FreeBSD tests.
- Qualify full RAM/DMA, storage, native Ethernet, real graphics/input, install,
  installed boot, updates and recovery on the exact FreeBSD distribution.
- Do not infer a 64-bit desktop package closure from `uname -m` alone, or infer
  a Pi 5 16 KiB requirement from its optimized Linux configuration.
