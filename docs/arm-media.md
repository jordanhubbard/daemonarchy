# Platform-selected ARM installer media

`scripts/assemble-arm-media.py` stages a complete ARM installer ISO and the selected platform's boot container in a fresh directory. It accepts regular files and creates regular files. Use a pinned ISO from a native build or release record and an independently recorded checksum. It does not write a device or enroll an Apple OS.

The first profiles are the RTX Spark N1X laptop and the Mac mini with M2 Pro (J474s/T6020). This is ARM-005 implementation work. Native boot, installation, desktop and recovery qualification remain open; assembling an image or booting an ARM VM does not close them.

The controller needs Python 3.11 or later, libarchive `tar` with ISO9660 support, and mtools `mtype`. The FreeBSD kernel and EFI loader are built on their allocated native worker. This assembler does not compile or substitute either one.

The assembler accepts both the normal ISO layout and the experimental
[RAM-root layout](arm-ram-installer.md). Packed UFS2 roots additionally require
Sleuth Kit's `ifind`, `istat` and `icat` (override with `--ifind`, `--istat` and
`--icat`). Inspection expands the actual zlib/LZMA UZIP payload in private
scratch space without mounting it. Allow room for the compressed payload,
cluster-rounded expanded root and the largest inspected file. The controller's
64 GiB expanded-root and 1 MiB cluster processing budgets do not cap target RAM
or CPU discovery.

For a packed root, the tool checks loader configuration, allocated regular
installer files, the FreeBSD 16 AArch64 ABI, matching inner/outer kernel and EFI
loader, the complete installation kernel set, and both installation archives'
MANIFEST hashes. The output binds their actual bytes; it does not trust a
producer sidecar as proof. Unknown codecs, corrupt clusters, absent payloads and
mismatched boot sets are refused. The [handoff checkpoint](../verification/arm-ram-handoff-20261109.json)
records successful RTX Spark and M2 Pro assembly from the boot-tested RAM image.
It does not establish physical boot or installation. The tested repack fits the raw-media budget but fails the compressed release-asset limit.

```sh
python3 scripts/assemble-arm-media.py \
  --platform rtx-spark-n1x \
  --installer /inputs/daemonarchy-aarch64.iso \
  --installer-sha256 "$INSTALLER_SHA256" \
  --output /outputs/rtx-spark-candidate
```

RTX Spark uses the laptop's UEFI firmware. This profile is separate from DGX Spark/GB10 desktops. It does not impose a CPU or RAM cap, substitute a diagnostic root, or establish graphics-driver support. The existing secondary-CPU bring-up and physical desktop gates remain in SPARK-001.

```sh
python3 scripts/assemble-arm-media.py \
  --platform apple-m2-pro-mini \
  --installer /inputs/daemonarchy-aarch64.iso \
  --installer-sha256 "$INSTALLER_SHA256" \
  --bootstrap-zip /inputs/pinned-uefi-bootstrap.zip \
  --bootstrap-sha256 "$BOOTSTRAP_SHA256" \
  --output /outputs/m2-pro-mini-candidate
```

The Apple input is an upstream ESP bootstrap ZIP, or its CI ZIP wrapper, containing `esp/m1n1/boot.bin`. The selected DTB must identify both `apple,j474s` and `apple,t6020`; another Mac's bootstrap is refused. The [published v1.9.9 release](https://github.com/AsahiLinux/m1n1/releases/tag/v1.9.9)
asset `ci-uefi-only-v1.9.9-asahi-7.1.9-1.zip` contains that DTB. Its publisher
SHA-256 is `e7ca644649bc4989abef005250cd606937111c4da7701d90a85d885a36cf5cd9`;
the checkpoint independently checks the downloaded bytes against it. Keep its download identity, source/license records and producer limitations with the build inputs; a binary hash does not establish compiler provenance or FreeBSD driver compatibility.

The output includes the complete installer ISO plus the unchanged `owned-esp/m1n1/boot.bin`. Apple requires an enrolled OS stub and its matching OS-owned ESP before this payload can run. Initial provisioning and owner authorization in Recovery are separate host-local operations. Preserve macOS and Recovery. The assembler neither provisions those partitions nor chooses an ESP for the operator. See the upstream [open OS interoperability contract](https://asahilinux.org/docs/platform/open-os-interop/) for the boot layout.

Before assembly, the tool verifies the input hashes, installer filesystem and payloads, AArch64 ELF/PE identities, FreeBSD 16 kernel banner, GPT header/table checksums, and the removable-media EFI loader's equality with the installer's loader. It checks the complete FDT structure and root compatible property before enrolling the Apple board. The copied ISO is read back and the input is rechecked. The manifest records artifact hashes and keeps physical boot, installation, desktop and recovery status false.

An initial assembly check using the published 1.5.1 ARM installer proves the container path only. It is not the final current-Omarchy or native Apple candidate. APPLE-001 still needs a matched FreeBSD kernel, including the M2 controller/storage dependency closure, before requesting a physical boot. A matching upstream DTB is not a FreeBSD driver implementation.

Run `python3 tests/arm-media.py` for damaged-input and wrong-board refusal. Set `DAEMONARCHY_APPLE_BOOTSTRAP_ZIP` to the pinned published asset to include the real bootstrap/FDT control. Record full-image assembly and actual per-target boot/install results separately.

Run `python3 tests/arm-ram-inspect.py -v` with Sleuth Kit available for packed-root decoder and real UFS2 refusal controls. These tiny synthetic filesystem fixtures are parser inputs, not bootable OS products.

For candidates that fit the raw-media budget but exceed the single compressed
asset limit, the [development split transport](split-media.md) preserves the
complete raw-image identity in bounded XZ parts. Publication integration and
final artifact acceptance remain separate required work.
