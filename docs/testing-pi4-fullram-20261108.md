# Pi 4 memory variants and USB DMA, 2026-11-08

The Pi 4B hardware reference has 8 GB RAM. A 2 GB simulator boot cannot
establish that the same kernel can use that memory while respecting the USB
interconnect's DMA aperture. uConsole now provides explicit `raspi4b-4g` and
`raspi4b-8g` models alongside the unchanged 2 GB `raspi4b` default. These are
BCM2711 models; they do not emulate BCM2712 or RP1.

## Reproduce memory assertions

Both [`pi4-simulator.py`](../tools/hwtrace/pi4-simulator.py) and
[`pi4-uefi-simulator.py`](../tools/hwtrace/pi4-uefi-simulator.py) accept
`--machine`, `--memory-min-bytes` and `--memory-max-bytes`. Bounds apply to the
single `hw.physmem` value in durable guest diagnostics. Missing or duplicate
values fail acceptance. These options assert observed memory; they do not
configure firmware or cap the kernel. The UEFI runner independently queries
QEMU's configured RAM. Default runs retain their prior model and checks.

For a full-memory UEFI USB bootstrap, add the following options to the
[hash-bound UEFI runner](testing-pi4-uefi-usb-20261108.md):

```sh
--machine raspi4b-8g --memory-min-bytes 7516192768 --memory-max-bytes 8589934592
```

Supply a kernel containing the standard ACPI `_DMA` repair, a fresh diagnostic
image with no `hw.physmem` or `hw.usb.xhci.dma32` override, and a separately
configured firmware copy with `RamLimitTo3GB=0`. The source image and firmware
remain regular files; every run uses a fresh image copy and overlay. A small
guest cannot pass merely because its emulator was configured with 8 GB RAM.

## Cause and bounded repair

With the original kernel, the uncapped 8 GB model places xHCI rings above
4 GB and USB commands time out. Firmware programs a 4 GB inbound PCIe window,
but its standard ACPI `SCB0._DMA` resource is narrower: an identity range
from zero through `0xbfffffff` (3 GiB). A disposable old-kernel control with
`hw.usb.xhci.dma32=1` boots successfully, supporting the reachability diagnosis;
that quirk alone cannot enforce the narrower 3 GiB resource.

The source repair reads the nearest ancestor's `_DMA` resource and supplies
an owned bus-DMA parent tag to the generic ACPI xHCI driver. The selected
fixed identity aperture constrains rings, contexts and USB transfer buffers
while retaining full system RAM. It rejects unsupported translated, disjoint
or malformed resources. Its cleanup retains owners when teardown cannot
finish. See the [source implementation and fault controls](https://github.com/jordanhubbard/daemonarchy-src/blob/work/pi5-bcmstb-gpio/docs/pi4-acpi-xhci-dma.md).

## Measured controls

The public UEFI runner passes all 20 checks with an 8 GB model and the firmware
3 GiB limit enabled: configured RAM is 8,589,934,592 bytes and durable guest
`hw.physmem` is 3,117,445,120 bytes. All seven probes, clean USB storage,
four active CPUs, ten diagnostic files and synchronized reset pass. The original
input image remains unchanged. Its kernel is the historical `79ebe4bf…`
baseline; this control validates the memory assertions and enabled limit.

The combined source was exported at `91204d3c8f22504eb4a346e5304d682618aea0d6`
and built from an empty object directory on native FreeBSD 16 ARM64 with
Clang 21.1.8. The first build failed on an OFW header prerequisite; its evidence
is retained. A fresh second export/build passes actual driver compilation,
kernel link and strip. Independently read-back kernel SHA-256 is
`8ec36736678f4de5308164fe6dfe990119b6ff042bf6eec6887ddd3ee84c60c9`.
Later documentation and dependency-gate changes do not alter implementation.
The final build dependency gates independently produce an equivalent native
GENERIC Makefile and all 193 option headers; six option-removal controls pass.

The same exact new kernel passes the 2 GB SD/FDT control (15 checks) and
UEFI/PCIe/USB control (19 checks). The public uncapped 8 GB control passes all
20 checks with guest `hw.physmem` 8,419,028,992 bytes and no `hw.physmem` or
`hw.usb.xhci.dma32` override. Dmesg reports `ACPI _DMA identity aperture ends at
0xbfffffff`. All seven probes, ten durable files, four active CPUs, clean
USB/UFS reads and synchronized reset pass. Source images remain unchanged.
The fresh ACPI/USB source image is 389,056,000 bytes, SHA-256
`70c5d89ca48ea314a6cbb17e106de06bbbdf681052e38d9b5c7960814fffc3e5`.
It contains the exact new kernel above and loader
`efff8d8aea278198f600f3d3d2e8b9638147f47517765f8a16dd9dff46697d66`.
Native UFS readback verifies those files, configuration and root ownership.
The simulator binary SHA-256 is
`430f85ef0819672ce21b2012476fea3abac39cd7d9598b31dff89df589883f34`.

A second fresh 20-check run adds only read-only QMP physical-memory reads; it
also passes without stopping the guest or changing guest memory/registers.
Seventy-six complete post-kernel-handoff samples show command ring
`0x315d5f00`, device-context array `0x395d7000`, event-ring segment table
`0x315d5000`, and event dequeue pointers through `0x315d5d20`, all below
`0xc0000000`. The controller is running (`USBCMD=0xd`, status zero), and
firmware BAR2 remains `0x11` with high word zero. This demonstrates actual
controller DMA reachability during the full-memory bootstrap; it is not a
sustained whole-RAM or peripheral stress qualification.


These are bootstrap controls. Physical Pi 4/Pi 500 boards remain unattended
and unchanged. Full-memory USB stress, physical cold/warm boot, Ethernet,
display/input, installation and recovery remain separate requirements.

### Reproduce the firmware profiles

Extract `RPI_EFI.fd` from the [pftf RPi4 v1.53 release](https://github.com/pftf/RPi4/releases/tag/v1.53).
The following standard-library Python recipe refuses another firmware
revision or an existing output directory. It creates two independent FD
copies; it changes only one 92-byte variable record in previously erased
NVRAM, leaving the original file and all executable firmware bytes unchanged.

```sh
python3 - firmware-original/RPI_EFI.fd firmware-profiles <<'PYCODE'
import hashlib, struct, sys, uuid
from pathlib import Path

source, output = Path(sys.argv[1]), Path(sys.argv[2])
original = source.read_bytes()
assert hashlib.sha256(original).hexdigest() == (
    "8334d9d3c3fe5341fb9876f2ddf653eca7b260ee2cda669c5446a0dd7f0104c5")
store = 0x3b0048
signature, size, formatted, healthy, _, _ = struct.unpack_from(
    "<16sIBBHI", original, store)
assert signature == uuid.UUID("aaf32c78-947b-439a-a180-2e144ec37792").bytes_le
assert (size, formatted, healthy) == (0xdfb8, 0x5a, 0xfe)
start = store + 28  # Four-byte-aligned end of VARIABLE_STORE_HEADER.
name = "RamLimitTo3GB\0".encode("utf-16-le")
guid = uuid.UUID("cd7cc258-31db-22e6-9f22-63b0b8eed6b5").bytes_le
expected = {
    0: "d1dbf70cf13c62e398f515c47a43bfd72e10f9fad2cf4044ee3a1d100951239f",
    1: "3381b1d8e02f3db939fb30df1fbacc75ddc3fd3329d21076408d70cb55efec7f",
}
output.mkdir(mode=0o700)
for limit in (0, 1):
    # AUTHENTICATED_VARIABLE_HEADER, VAR_ADDED; NV|BS|RT, UINT32 data.
    header = struct.pack("<HBBIQ16sIII16s", 0x55aa, 0x3f, 0, 7,
                         0, bytes(16), 0, len(name), 4, guid)
    record = header + name + struct.pack("<I", limit)
    assert len(record) == 92 and original[start:start + 92] == b"\xff" * 92
    configured = original[:start] + record + original[start + 92:]
    assert configured[:start] == original[:start]
    assert configured[start + 92:] == original[start + 92:]
    digest = hashlib.sha256(configured).hexdigest()
    assert digest == expected[limit]
    target = output / f"RPI_EFI-limit{limit}.fd"
    with target.open("xb") as stream:
        stream.write(configured)
    print(digest, target)
PYCODE
```

The name/GUID and 32-bit data are defined by the pinned
[ConfigDxe initialization](https://github.com/tianocore/edk2-platforms/blob/08566230c98729eb9760211e3111c7b4c391ccbf/Platform/RaspberryPi/Drivers/ConfigDxe/ConfigDxe.c)
and [form-set GUID](https://github.com/tianocore/edk2-platforms/blob/08566230c98729eb9760211e3111c7b4c391ccbf/Platform/RaspberryPi/Drivers/ConfigDxe/ConfigDxeFormSetGuid.h).
The record uses EDK2's
[authenticated variable-store format](https://github.com/tianocore/edk2/blob/master/MdeModulePkg/Include/Guid/VariableFormat.h).
This is an NVRAM configuration change, not a firmware executable patch.
A generic QEMU `loader` device loads the FD into RAM; it does not make the
input FD writable persistent flash. The separate configured files avoid
assuming that a UI or shell variable change survives a simulator restart.

Select `raspi4b-8g` and pass the chosen FD and its printed SHA-256 to the
UEFI/USB runner. For an independent runtime check, interrupt the Daemonarchy
queued-experiment countdown, then press Escape to reach the EFI loader
prompt. Run these actual FreeBSD-loader commands before the kernel boots:

```text
set LINES=1000
efi-show -g cd7cc258-31db-22e6-9f22-63b0b8eed6b5 -v RamLimitTo3GB
memmap
```

`efi-show` must report `NV,BS,RS` and the four bytes `01 00 00 00` for the
limit-on FD, or `00 00 00 00` for limit-off. With the limit on, ordinary EFI
RAM ends at `c0000000`. With it off, `memmap` additionally exposes
`[c0000000, fc000000)` and `[100000000, 200000000)`. Both retain the peripheral
hole and VideoCore reservation. This readback proves the firmware setting
independently of kernel memory limits. On the diagnostic image, resume the
normal queued boot with `include /boot/lua/loader.lua`.

