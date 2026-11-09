# Pi 4 USB-only FDT boot and GENET control

`tools/hwtrace/pi4-usb-network-simulator.py` combines native U-Boot USB EFI
loading, FreeBSD FDT USB/UFS root and the actual GENET DHCP/SSH/SCP control.
It reuses the [existing network control](testing-pi4-genet-network-20261108.md)
and its private image, VM-only SSH keys, pinned server identity, bidirectional
1 MiB transfers, fresh offline diagnostics and natural reset checks.

The input image is attached only as `usb-storage` on the modeled BCM2711 PCIe
xHCI controller. No SD backing image or alternate disk is attached. The USB
virtual capacity equals the input image size; SD power-of-two padding is not
used. U-Boot may probe empty MMC slots, which provides no fallback medium.

## Required evidence

Acceptance requires each distinct boot boundary:

- U-Boot initializes native PCIe xHCI, enumerates one storage device, and selects
  the `usb 0` EFI bootflow.
- The FreeBSD loader's unique console `Load Device` contains a USB device-path
  node and no SD/eMMC node. Opaque `VenHw` ancestors are permitted; a literal
  PCI text node is not required. USB enumeration after an SD EFI loader fails.
- The kernel attaches native BCM2838-compatible PCIe, PCI xHCI, USB mass storage
  and `da0`. `mount -p` records one read-only UFS root; native GEOM XML must
  resolve its provider through consumers to the actual `da0` DISK. A GPT label
  alone does not establish the root transport. `kern.disks` must include `da0`
  and no `mmcsd` provider.
- All four CPUs, seven successful probes, clean storage, optional full-memory
  bounds, GENET link/DHCP, trusted SSH, bidirectional payload hashes, offline
  collection, normal continue/reset and original input integrity pass.

The runner collects `usb-mounts.txt`, `usb-disks.txt` and `usb-geom.xml` through
an authenticated native GENET session and preserves them in offline DUMPS.
The GEOM parser accepts the trailing NUL produced by the native binary sysctl;
missing providers, duplicate identifiers, cycles and partial XML fail closed.
The complete command, exact input hashes and selected profile are recorded.

## Invocation

Use the same tools and immutable regular-file inputs as the network control,
with a pinned U-Boot build that includes the BCM2711 PCIe/xHCI boot drivers and
a matching emulator implementing the native PCIe/MDIO contract:

```sh
python3 tools/hwtrace/pi4-usb-network-simulator.py \
  --image "$IMAGE" --image-sha256 "$IMAGE_SHA256" \
  --uboot "$UBOOT" --uboot-sha256 "$UBOOT_SHA256" \
  --dtb "$DTB" --dtb-sha256 "$DTB_SHA256" \
  --qemu "$QEMU" --qemu-sha256 "$QEMU_SHA256" \
  --qemu-img "$QEMU_IMG" --output "$FRESH_PRIVATE_OUTPUT"
```

The default is 2 GiB. Add `--machine raspi4b-8g
--memory-min-bytes 7516192768 --memory-max-bytes 8589934592` for the full-memory
control. These options verify guest memory; they do not impose a kernel cap.

## Qualification boundary

The public runner passes on both selected memory profiles using the same
immutable inputs and fresh output directories:

| Profile | Checks | Guest `hw.physmem` | GENET input/output bytes | Packet errors/drops |
| --- | --- | --- | --- | --- |
| 2 GiB | 34/34 | 2,054,680,576 | 1,226,320 / 2,247,295 | 0 |
| 8 GiB | 35/35 | 8,430,018,560 | 1,225,918 / 2,246,853 | 0 |

Both runs retain 18 offline diagnostic files and seven probe statuses of zero.
The guest records `kern.disks: da0`; native GEOM resolves the mounted read-only
UFS root to that disk. Both payload directions and the upload round trip match
their expected hashes. The normal guest reset exits QEMU with status zero, and
the original image SHA-256 is unchanged. An earlier native reset-driver kernel
also passes both profiles; the table records the final GPIO-hogs kernel.

Final pinned input SHA-256 identities:

- QEMU: `08d5088766b2670847f0ec1c57cc7aeceb24f6c3fc98caff6ed2f6265718d834`.
- U-Boot: `0679280e659e284cfebb3fa568747c3fcab5bdcc4784f434e8f89003247757b4`.
- Original CM4 fixture DTB: `c9d70ba0e397c772fca8ce18e187fd1762bba082cad82445f314603c42bca7e7`.
- Diagnostic image: `da8a5df568b97fc77a9692f24d889557196befc2d8521d8be9df9a744f92d441`.
- Native kernel: `2bfb3f49d7972e59d3cc73d90fb15160e3f5c01d4b35b453a4dc3231a7c6e649`.

The copied DTB receives the established PL011 console and virtual GENET MAC
fixups; its hash and exact command are in each result. USB capacity is exactly
389,056,000 bytes. Neither an SD image nor a kernel physical-memory override is
used. Private outputs contain VM SSH identities and are not release images.

The FDT PCI host emits an unsupported optional ACPI-handle query under verbose
logging; this is not a failed USB transaction. The bridge also reports an
initial memory-window allocation warning before the successful xHCI/USB path.
This observed recovery does not establish general PCI resource-allocation
health. Unsupported EFI runtime tracing/clock and VideoCore audio remain
separate simulator limitations; no CAM or storage I/O errors occur in the
accepted runs.

QEMU injects U-Boot and the FDT. This does not exercise VideoCore, EEPROM boot,
a physical USB controller/cable or DRAM stress. Physical Pi 4, an ACPI GENET
frontend, installed desktop/recovery and Pi 5/RP1 acceptance remain separate.
