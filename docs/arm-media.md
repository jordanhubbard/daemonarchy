# Platform-selected ARM installer media

`scripts/assemble-arm-media.py` stages a complete ARM installer ISO and the selected platform's boot container in a fresh directory. It accepts regular files and creates regular files. Use a pinned ISO from a native build or release record and an independently recorded checksum. It does not write a device or enroll an Apple OS.

The first profiles are the RTX Spark N1X laptop and the Mac mini with M2 Pro (J474s/T6020). This is ARM-005 implementation work. Native boot, installation, desktop and recovery qualification remain open; assembling an image or booting an ARM VM does not close them.

The controller needs Python 3.11 or later, libarchive `tar` with ISO9660 support, and mtools `mtype`. The FreeBSD kernel and EFI loader are built on their allocated native worker. This assembler does not compile or substitute either one.

The current assembler accepts the normal ISO layout, with installer payloads
directly visible in ISO9660. It refuses the experimental
[RAM-root layout](arm-ram-installer.md), whose installer is inside the UZIP root.
The native RAM/USB control now has boot and manual trace-persistence evidence,
but a verified packed-root handoff into this platform assembler remains open.
Do not bypass the normal ISO's payload checks to assemble that image.

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

The Apple input is an upstream ESP bootstrap ZIP, or its CI ZIP wrapper, containing `esp/m1n1/boot.bin`. The selected DTB must identify both `apple,j474s` and `apple,t6020`; another Mac's bootstrap is refused. The published v1.9.9/asahi-7.1.9-1 artifact contains that DTB. Keep its download identity, source/license records and producer limitations with the build inputs; a binary hash does not establish compiler provenance or FreeBSD driver compatibility.

The output includes the complete installer ISO plus the unchanged `owned-esp/m1n1/boot.bin`. Apple requires an enrolled OS stub and its matching OS-owned ESP before this payload can run. Initial provisioning and owner authorization in Recovery are separate host-local operations. Preserve macOS and Recovery. The assembler neither provisions those partitions nor chooses an ESP for the operator. See the upstream [open OS interoperability contract](https://asahilinux.org/docs/platform/open-os-interop/) for the boot layout.

Before assembly, the tool verifies the input hashes, installer filesystem and payloads, AArch64 ELF/PE identities, FreeBSD 16 kernel banner, GPT header/table checksums, and the removable-media EFI loader's equality with the installer's loader. It checks the complete FDT structure and root compatible property before enrolling the Apple board. The copied ISO is read back and the input is rechecked. The manifest records artifact hashes and keeps physical boot, installation, desktop and recovery status false.

An initial assembly check using the published 1.5.1 ARM installer proves the container path only. It is not the final current-Omarchy or native Apple candidate. APPLE-001 still needs a matched FreeBSD kernel, including the M2 controller/storage dependency closure, before requesting a physical boot. A matching upstream DTB is not a FreeBSD driver implementation.

Run `python3 tests/arm-media.py` for damaged-input and wrong-board refusal. Set `DAEMONARCHY_APPLE_BOOTSTRAP_ZIP` to the pinned published asset to include the real bootstrap/FDT control. Record full-image assembly and actual per-target boot/install results separately.
