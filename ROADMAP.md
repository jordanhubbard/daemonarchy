# Daemonarchy roadmap

## 1.1.0

The next release is **1.1.0**. All work below is in scope; an unchecked item
is not a claim of working support. There is no release date yet.

Existing 1.0 installations must remain upgradeable through `pkg upgrade`.
New installation modes are optional and must preserve the existing whole-disk
installation path.

| Work | Implementation scope | Required acceptance evidence | Status |
| --- | --- | --- | --- |
| NVIDIA graphics | Detect supported GPUs, package kernel-matched drivers, configure modesetting and the desktop session, and explain unsupported models. | Install and reboot on NVIDIA hardware; SDDM login, Hyprland rendering, external displays, and suspend/resume; Intel/AMD regression checks. | Planned |
| Graphical VM desktops | Select a supported virtual graphics path and configure the compositor and login session for it. | Boot the installed image into a usable desktop in each advertised hypervisor; verify rendering, keyboard, pointer, resizing, and reboot. SSH-only checks do not qualify. | Planned |
| Bluetooth beyond input devices | Add audio device pairing, connection, output selection, reconnect, and removal to the FreeBSD backend and panel. Document the supported audio profiles. | Real headset/speaker playback, volume, disconnect/reconnect, and reboot persistence; existing keyboard/mouse pairing still works. | Planned |
| Enterprise Wi-Fi | Support certificate-validated 802.1X connections in the installer and desktop panel, including PEAP/MSCHAPv2 and EAP-TLS. Preserve credentials and certificate files securely across installation. | Join a test enterprise network with each supported EAP method, reject an untrusted server certificate, reconnect after reboot, and check that credentials stay out of logs. | Planned |
| Dual boot and partition selection | Show existing partitions; replace only an explicitly selected OS/data partition or create one in selected free space; preserve existing EFI loaders and entries. Never resize an existing filesystem implicitly. | Disposable disks containing another OS survive installation with partition/data checks and both operating systems booting; insufficient space and invalid selections fail before writes. | In progress: native preservation tests pass for both selection modes; physical Windows boot tests pending |
| Legacy BIOS boot | Add BIOS image boot and installed-system boot code, alongside the UEFI path. | Boot the ISO, install, and reboot in BIOS and UEFI VMs, including encrypted installations. | In progress: disk layout and bootcode tests pass; full boot tests pending |
| Secure Boot | Establish a signed FreeBSD boot chain and a documented key-enrollment/update process. | Install and boot with Secure Boot enabled; reject an untrusted boot component and verify signed updates. | Planned |
| Upstream FreeBSD ports | Complete review and integration of the supporting ports and the Omarchy/Daemonarchy ports; reconcile the image's ports tree with upstream. | Upstream changes merged and packaged; clean `poudriere testport` and installation against the selected package set. | Under upstream review |

Upstream reviews: [supporting ports #630](https://github.com/freebsd/freebsd-ports/pull/630)
and [desktop ports #635](https://github.com/freebsd/freebsd-ports/pull/635).
Their merge timing depends on FreeBSD maintainers.

### Delivery order

1. Deliver the partition-selection preview for existing-partition and free-space testing; establish hardware and VM coverage.
2. Implement graphics, networking, and Bluetooth in their owning repositories;
   update the ports and installer integration together.
3. Complete physical Windows preservation and boot checks; validate the remaining boot modes.
4. Build the release candidate, exercise upgrades from 1.0.1, and complete the
   acceptance matrix before publishing 1.1.0.

### Release gates

- [ ] Every feature above has implementation and retained native test evidence.
- [ ] Kernel modules match the image's exact FreeBSD snapshot.
- [ ] Changed ports pass `poudriere testport`.
- [ ] Unattended installation passes the existing QEMU and bhyve checks.
- [ ] Graphical VM and physical-hardware checks pass.
- [ ] Existing installations upgrade successfully; failed updates remain recoverable.
- [ ] Documentation states supported GPUs, hypervisors, Bluetooth profiles,
      EAP methods, and boot/install combinations precisely.
- [ ] Package repository, ISO, checksum, and release notes are verified together.

Feature status and evidence belong here as work progresses. If a platform
dependency prevents a feature from shipping, record the blocker and agree on
any scope change before calling 1.1.0 complete.

### Implementation notes

- BIOS: the installer now adds a 512 KiB `freebsd-boot` partition in the gap
  before the EFI partition and writes the target snapshot's `pmbr` and
  `gptzfsboot`. Native disposable-disk tests passed with both 512-byte and
  4 KiB sectors. A QEMU SeaBIOS smoke test reached the snapshot's FreeBSD loader
  and loaded its kernel from ZFS; the development ISO also built successfully.
  The QEMU installation harness accepts `BOOT_MODE=bios` or `BOOT_MODE=uefi`.
  Full installation and encrypted-boot coverage remain open. See the
  [development check record](docs/testing-1.1-bios.md).
- VM graphics: `graphics/virtio-gpu-qemu-kmod` in the current ports tree exposes
  a framebuffer for Xorg's `scfb` driver, not the DRM interface needed by
  Hyprland. Installing that port alone does not satisfy this feature.
- NVIDIA: the current image uses `drm-66-kmod`; the default NVIDIA DRM
  metaport on the selected FreeBSD version chooses the 6.12 DRM family.
  Resolve that driver-family choice and GPU model support before integrating
  packages, and build every selected kernel module for the image's snapshot.
- An AMD desktop is assigned for non-NVIDIA testing. The user will prepare
  both a replaceable OS partition and free space for Windows-preservation
  testing. NVIDIA qualification still needs separate hardware. No physical
  Windows dual-boot acceptance result is recorded yet.
- Partition selection: see the [preview test guide](docs/testing-1.1-partitions.md).
  Shared-disk installs preserve the existing EFI filesystem and add a separate
  loader/firmware entry. They require UEFI/GPT and do not resize filesystems.
- Updates: Daemonarchy installations must identify themselves as Daemonarchy,
  link to Daemonarchy releases/support, and check its own package catalog.
  FreeBSD dependency repositories remain identified separately.
- The upstream ports review's request to move bundled files into source
  repositories was addressed in 1.0.1. Both upstream PRs still await merge.
