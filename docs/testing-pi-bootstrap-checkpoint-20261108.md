# Pi 4 and Pi 500 software bootstrap checkpoint, 2026-11-08

Pi 4 remains the first SBC porting target. The current software controls cover
Pi 4 storage/network boot and selected BCM2712 PCIe2 prerequisites. They do not
establish a physical Pi 4/Pi 500 FreeBSD boot, a complete RP1 port, or final
installer, desktop and update/rollback acceptance.

This checkpoint supplements the dated [Pi 4 Linux reference](testing-pi4-linux-20261107.md),
[Pi 500 Linux reference](testing-pi500-linux-20261107.md) and earlier simulator
records. Their original observations and failed controls remain historical
evidence. Both physical boards are unattended; their running installations,
boot files, EEPROM and physical media were unchanged during these controls.
Raw captures, image files, keys and worker identities remain private.

## Exact software inputs

| Input | Identity / state |
|---|---|
| Owned FreeBSD source | `4cf77572fd2f9577c1928357171fd28e3cc4acdf`, tree `4ce20419f1a338ca2ab51953abdfa568849cb0b0` |
| Native-built GENERIC kernel | SHA-256 `d520d7621d438c14c587d8684a4cc0321dc4773c20d687925ce87275bf2e846c` |
| Local qualified QEMU | SHA-256 `318f7ff3c7502aad1b5b49e4d682239a74a44351aaefba1b8e8379588966aeee` |
| uConsole integration | PRs 3–7 merged; `master` `9332306f6ba81eceb782059af58a5e15bed0108e` |
| Source integration | [Direct-map lookup PR75](https://github.com/jordanhubbard/daemonarchy-src/pull/75) and [PL011 receive PR76](https://github.com/jordanhubbard/daemonarchy-src/pull/76) remain draft, with successful controller/native-loader CI and scoped native guest qualification |

The source build and its headers, tools and runtime inputs are bound in retained
native records. A source build, green host CI or a framework authority check alone
does not establish any of the guest results below.

## Passed software controls

### Pi 4 defaults

All five controls use the D520 kernel and fresh private images/overlays. They
execute the FreeBSD EFI loader and kernel, report four active CPUs, mount the
native storage root, complete seven bounded probes and retain offline files
after natural guest reset. The 8 GiB profiles exercise full usable modeled RAM.

| Boot profile | Guards passed | Durable diagnostic files |
|---|---:|---:|
| U-Boot/FDT, SD root, 2 GiB | 26 | 15 |
| U-Boot/FDT, SD root, 8 GiB | 27 | 15 |
| U-Boot/FDT, USB-only loader and root, 2 GiB | 34 | 18 |
| U-Boot/FDT, USB-only loader and root, 8 GiB | 35 | 18 |
| UEFI/ACPI, USB root, 8 GiB | 20 | 10 |

The FDT network profiles use native GENET, DHCP, a verified VM SSH host key and
bidirectional 1 MiB payloads with checksum-verified round trips. USB-only controls
bind the actual EFI LoadDevice and kernel GEOM root to USB, excluding SD fallback.
The UEFI full-memory control is separate from the initial 3 GiB firmware-cap
experiment. The model's 4 GiB checks do not replace a separate physical 4 GiB
board result.

See the [USB-only FDT/GENET record](testing-pi4-fdt-usb-network-20261108.md),
[GENET record](testing-pi4-genet-network-20261108.md),
[memory record](testing-pi4-fullram-20261108.md) and
[UEFI USB record](testing-pi4-uefi-usb-20261108.md) for their earlier controls.
The retained five-control receipt has SHA-256
`ee1193df7502432d7d56bd09715c527c9ca82fcb48d6ba2067b76367fde3f396`.

### Selected PCIe2, DMA, interrupts and console recovery

The explicit synthetic PCIe2 profile reuses the BCM2711 CPU, SD, PL011 and RAM
boot substrate. It copies selected enrolled BCM2712 provider/frontend cells and
uses real QEMU PCI/xHCI engines. It has a standard QEMU endpoint, not an RP1
identity or peripheral model. It does not model the complete Pi 500 boot chain.

The native D520 kernel passes both interrupt modes:

| Mode | Observed MSI message | SPI / GIC INTID | Handler count increase | Stray increase |
|---|---:|---|---:|---:|
| MSI-X | 0 | 128 / 160 | 444 | 0 |
| MSI | 0 | 128 / 160 | 443 | 0 |

Each run verifies two 1 MiB USB nonces, guest and offline scratch data, untouched
bytes outside the test area, FAT diagnostics and kernel identity. All seven
native probes return status zero, the guest requests reset naturally and QEMU
exits zero. Capability state and the observed message route are checked; an
increasing unrelated INTx counter cannot satisfy the MIP guard.

A finite PL011 overflow test sends 515 wire bytes, observes 381 padding echoes,
then verifies interrupt quiescence, a fresh prompt and an exact recovery nonce.
Loss is intentional in this test: it proves forward progress after a finite
software-ring overflow, not complete byte delivery, arbitrary-flood latency,
physical UART timing or RTS/CTS behavior. Ordinary commands use separate bounded
frames. The kernel also includes the direct-map lookup repair tested by complete
production-function controls and a bounded real ARM EL1/MMU experiment.

The retained dual-mode independent audit has SHA-256
`2c648f6840df15a7f9ecfefa202a898b1b2fda7ff7549b69c49001610512ee2c`.
The aggregate source-build, guest, five-default and independent-audit record has
SHA-256 `1019a744cbc0a284341afb63ea4a22cade1339fb4e3dc32984daefa44af90bdc`.
It expressly excludes physical BCM2712/RP1, electrical and install qualification.

### Emulator packaging after merge

The [exact-master validation](https://github.com/jordanhubbard/uConsole/actions/runs/42502597355)
and [push host checks](https://github.com/jordanhubbard/uConsole/actions/runs/42502499049)
pass on uConsole `9332306f`. Linux x86_64, Linux ARM64 and macOS ARM64 archives
were downloaded and checked against committed source, fixture and documentation
hashes, native binary architecture, managed builder fingerprint, official QEMU
source archive and licenses. GUI qualification and all 14 model suites pass
against both rebuilt and bundled binaries on every platform, with 10 composer
guards per phase. Linux/macOS host and GUI checks and Windows portability checks
also pass. The validation dispatch creates no tag or release publication.

These host-package results qualify the emulator tools, not physical Pi hardware.

## Prepared candidate family and physical gates

New D520 candidates have been assembled as regular files, with native base/UFS,
root configuration, ESP, GPT and fixed-map readback. Each is 389,056,000 bytes.
They were not written to physical media or booted on either board.

| Candidate / lane | Image SHA-256 | Profile |
|---|---|---|
| Pi 4B USB-only v3 | `ac2dd3b3b44809a272d4687d2b760ba7037049fb8f629745b2d568cc08931e74` | Existing firmware-FDT USB-only recipe, D520 kernel |
| Pi 500 SD control | `e0185d652758787749f1fbca77a82b3b0fe918c5645ec7bfd112fe609b68f213` | 3 GiB cap; PCIe2 explicitly disabled in a derived diagnostic DTB |
| Pi 500 PCIe experiment | `080431f585a136b6da565527805845a52021f829004daa4b953cb825faa5492d` | 3 GiB cap; original enabled PCIe2 node |
| Pi 500 uncapped PCIe experiment | `f4de850b6e05a702f0c885a1dd2d2521f62e3e924e3ca5cadfc820ce7b64248b` | No configured kernel cap; PCIe2 enabled; full-RAM runtime unverified |

The Pi 4 v3 candidate retains the v2 U-Boot, physical DTB, firmware, marker and
no-fallback recipe. Native read-only UFS/configuration/ownership checks pass.
Its exact diagnostic queue also passes isolated 2/8 GiB controls with 28/29
guards, seven status-zero probes, ten offline files and natural reset. Those
controls use a documented Pi 4B-derived simulator profile and bypass
VideoCore/EEPROM; they do not qualify physical hardware or network payloads.
The retained candidate acceptance receipt has SHA-256
`3009f7abc69d942ce9f2835892363ad40fe3398ec3f52f837b30dd76f4b81b8e`.

The Pi 500 lanes bind the same D520 kernel/source to explicit memory and PCIe
profiles. Native base readback, unchanged root partition during ESP assembly,
FAT/queue readback and the 211-entry fixed map pass. The family receipt has
SHA-256 `cb8901171857d64abcbf576d4a945169305a7f5060c671738ecdeb50b2e7f9b1`.
Physical boot, MMC0 ordering, runtime memory size, real SD DMA and RP1 behavior
remain unverified on every lane.

The [profile-bound staging change, PR318](https://github.com/jordanhubbard/daemonarchy/pull/318)
is a separate draft, not an already published tool interface. It binds the
selected memory profile and exact queue, and distinguishes its bundle checks
from a native external base-image audit. The pre-profile
[staging tool](../tools/hwtrace/pi5-bootstrap.py), retained at product baseline
`398ed9eb`, stages a 3 GiB control.
A requested cap must agree with the actual root configuration and queue;
removing it in only one location is insufficient.

The SD control is deliberately separate because a D520 kernel can auto-attach
the new frontend to an enabled BCM2712 PCIe2 node. A 3 GiB cap does not prevent
new reset/MDIO/PCIe operations. The PCIe-disabled diagnostic comparison is not
the final port solution: the enabled 3 GiB lane isolates host initialization,
and the uncapped lane changes memory separately. The firmware-fixed handoff
FDT, not just the filesystem DTB, remains part of physical validation.

Earlier regular-file controls remain unchanged: Pi 4 v2 SHA-256
`829ae1a8eb8179332f920fd147d5ca86dc09601877b4daa6844e7713c1f7ba80`
and Pi 500 SD/MIP SHA-256
`386621b77461787d74cdaed1266b70232dcb985c533bf252e9e318253b0765cb`
contain the older kernel `7a76572b`. They are retained controls, not D520 results.
The historical Pi 4 physical-media write checkpoint is separately recorded in
its dated Linux/media record; these later regular-file hashes do not update it.

The following remain open under [RPI-001](roadmap/arm-implementation.md#rpi-001-port-raspberry-pi-4-before-raspberry-pi-5)
and [RPI-002](roadmap/arm-implementation.md#rpi-002-port-raspberry-pi-5-and-resolve-rp1-and-firmware-quirks):

- Physical VideoCore/EEPROM/firmware handoff, cold/warm and power-cycle behavior,
  actual SD/USB selection, full-RAM device DMA, pad/clock/PHY and cache behavior.
- Actual RP1 nexus and built-in USB, GEM Ethernet, interrupts, clocks/resets,
  input, PWM/cooling, display and NVMe behavior. Pi 4 GENET or a standard xHCI
  endpoint does not establish RP1 support.
- Separate model/revision/RAM records for Pi 5 C1/D0, Pi 400, CM4/CM5 and other
  admitted variants; a CM4 simulator DTB is not physical carrier acceptance.
- Board-specific final media, real installer and installed boot, renderer/input
  and default applications, network recovery and signed matched boot-set
  update/rollback. The generic aarch64 VM distribution result is separate.

The original roadmap requirements and issue checkboxes remain open. The next
work is review of the candidate/profile evidence and an explicit physical
handoff plan. Physical testing waits for an attended hardware window and
verification of the current medium identity; both boards are unattended and no
hardware action is queued. This checkpoint changes no running board, boot order,
EEPROM or physical media.
