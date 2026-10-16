# Daemonarchy roadmap

## 1.1.0

The next release is **1.1.0**. All work below is in scope; an unchecked item
is not a claim of working support. There is no release date yet.

Existing 1.0 installations must remain upgradeable through `pkg upgrade`.
New installation modes are optional and must preserve the existing whole-disk
installation path.

| Work | Implementation scope | Required acceptance evidence | Status |
| --- | --- | --- | --- |
| NVIDIA graphics | Detect supported GPUs, package kernel-matched drivers, configure modesetting and the desktop session, and explain unsupported models. | Install and reboot on NVIDIA hardware; SDDM login, Hyprland rendering, external displays, and suspend/resume; Intel/AMD regression checks. | In progress: NVIDIA 595 and DRM 6.12 packages built; selection tests pass; operator hardware matrix pending |
| Graphical VM desktops | Select a supported virtual graphics path and configure the compositor and login session for it. | Boot the installed image into a usable desktop in each advertised hypervisor; verify rendering, keyboard, pointer, resizing, and reboot. SSH-only checks do not qualify. | Planned |
| Bluetooth beyond input devices | Add audio device pairing, connection, output selection, reconnect, and removal to the FreeBSD backend and panel. Document the supported audio profiles. | Real headset/speaker playback, volume, disconnect/reconnect, and reboot persistence; existing keyboard/mouse pairing still works. | Planned |
| Enterprise Wi-Fi | Support certificate-validated 802.1X connections in the installer and desktop panel, including PEAP/MSCHAPv2 and EAP-TLS. Preserve credentials and certificate files securely across installation. | Join a test enterprise network with each supported EAP method, reject an untrusted server certificate, reconnect after reboot, and check that credentials stay out of logs. | In progress: profile helper, installer/panel integration, native parser and credential-transfer tests; real EAP exchanges and reboot qualification pending |
| Remote debug session feedback | Show when an approved agent actually connects, a short description of its current activity, and an explicit completion message telling the operator it is safe to stop the session. Keep the display readable without streaming every command or sensitive data. | Exercise pairing, successful connection, activity changes, reconnects and explicit completion on the local console. An SSH disconnect between commands must not be mistaken for completion; stopping access must still close connections and discard approvals. | Planned: operator reported that the current listener shows no connection, activity or completion feedback |
| Dual boot and partition selection | Show existing partitions; replace only an explicitly selected OS/data partition or create one in selected free space; preserve existing EFI loaders and entries. Never resize an existing filesystem implicitly. | Disposable disks containing another OS survive installation with partition/data checks and both operating systems booting; insufficient space and invalid selections fail before writes. | In progress: native preservation tests pass for both selection modes; physical Windows boot tests pending |
| Legacy BIOS boot | Add BIOS image boot and installed-system boot code, alongside the UEFI path. | Boot the ISO, install, and reboot in BIOS and UEFI VMs, including encrypted installations. | Implemented: BIOS and UEFI QEMU installation/reboot checks pass with and without GELI encryption; refreshed-snapshot qualification pending |
| Secure Boot | Establish a signed FreeBSD boot chain and a documented key-enrollment/update process. | Install and boot with Secure Boot enabled; reject an untrusted boot component and verify signed updates. | In progress: isolated signed-loader/manifest prototype boots with Secure Boot enabled and rejects an unsigned loader and tampered kernel; installer, runtime module protection and signed updates pending |
| Ports and source refresh | Refresh the Daemonarchy ports fork from upstream FreeBSD ports and re-sync system sources with FreeBSD CURRENT before selecting the release snapshot. Preserve Daemonarchy changes and reconcile ports with the selected package set. | Record pinned ports/source revisions; rebuild the snapshot jail, packages, and kernel modules together; clean `poudriere testport` and installation against the selected package set. | In progress: selected snapshot/source 3ceb5f150bc1 and package-compatible ports baseline 28d8f145fbec; matching build and package QA in progress |

Release ports come from [jordanhubbard/freebsd-ports, branch `omarchy`](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy).
System sources track [FreeBSD CURRENT (`freebsd-src`, branch `main`)](https://github.com/freebsd/freebsd-src/tree/main); pin the source revision that produced the selected image snapshot.
Desktop sources live in [daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop)
and [omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd).
Daemonarchy publishes its packages through its own [signed package repository](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64).

Upstream reviews: [supporting ports #630](https://github.com/freebsd/freebsd-ports/pull/630)
and [desktop ports #635](https://github.com/freebsd/freebsd-ports/pull/635).
Their merge timing depends on FreeBSD maintainers and does not block 1.1.0:
validated packages can ship from the fork while these reviews remain open.

### Delivery order

1. Deliver the partition-selection preview for existing-partition and free-space testing; establish hardware and VM coverage.
2. Implement graphics, networking, and Bluetooth in their owning repositories;
   update the ports and installer integration together.
3. Complete physical Windows preservation and boot checks; validate the remaining boot modes.
4. Refresh the ports fork from upstream and re-sync sources with FreeBSD CURRENT.
   Select and record the new snapshot/source revision and package-compatible ports
   baseline, then rebuild the jail, packages, and kernel modules together.
5. Build the release candidate, exercise upgrades from 1.0.1, and complete the
   acceptance matrix before publishing 1.1.0.

### Release gates

- [ ] Every feature above has implementation and retained native test evidence.
- [ ] Ports fork refreshed from upstream and system sources re-synced with FreeBSD CURRENT; exact release revisions recorded.
- [ ] Kernel modules match the image's exact FreeBSD snapshot.
- [ ] Changed ports pass `poudriere testport`.
- [ ] Unattended installation passes the existing QEMU and bhyve checks. BIOS and UEFI QEMU installation/reboot passed with and without encryption. Unencrypted UEFI bhyve passed with both shallow checkouts; encrypted bhyve and repetition against the refreshed snapshot remain pending.
- [ ] Graphical VM and physical-hardware checks pass.
- [ ] Existing installations upgrade successfully; failed updates remain recoverable.
- [ ] Documentation states supported GPUs, hypervisors, Bluetooth profiles,
      EAP methods, and boot/install combinations precisely.
- [ ] Package repository, ISO, checksum, and release notes are verified together.

Feature status and evidence belong here as work progresses. If a platform
dependency prevents a feature from shipping, record the blocker and agree on
any scope change before calling 1.1.0 complete.

### Implementation notes

- Remote agent debug: the live installer menu can open a temporary SSH
  listener (default port 2222, configurable), with console approval of the
  agent's key fingerprint. This provides the USB-to-agent handoff for physical
  test machines. Pairing, rejection, custom ports, reconnecting and stopping
  access passed native live-VM checks. See the [handoff guide](docs/remote-agent-debug.md)
  and [validation record](docs/testing-1.1-remote-debug.md).
  The listener currently has no reliable agent-activity or completion display;
  the session-feedback work above is required for 1.1. An agent must explicitly
  report that its work is complete rather than treating a closed SSH connection
  as permission to stop a session containing several commands.

- BIOS: the installer now adds a 512 KiB `freebsd-boot` partition in the gap
  before the EFI partition and writes the target snapshot's `pmbr` and
  `gptzfsboot`. Native disposable-disk tests passed with both 512-byte and
  4 KiB sectors. A QEMU SeaBIOS smoke test reached the snapshot's FreeBSD loader
  and loaded its kernel from ZFS; the development ISO also built successfully.
  The QEMU installation harness accepts `BOOT_MODE=bios` or `BOOT_MODE=uefi`.
  Full BIOS and UEFI QEMU installation/reboot checks now pass with and without
  GELI encryption. The harness detects the BIOS bootcode's early VGA password
  prompt as well as the UEFI loader's serial prompt. See the
  [development check record](docs/testing-1.1-bios.md).
- VM graphics: `graphics/virtio-gpu-qemu-kmod` in the current ports tree exposes
  a framebuffer for Xorg's `scfb` driver, not the DRM interface needed by
  Hyprland. Installing that port alone does not satisfy this feature.
- NVIDIA: the image explicitly packages `nvidia-drm-612-kmod` alongside
  `drm-612-kmod`, keeping the NVIDIA and AMD/Intel payloads on one DRM core. NVIDIA
  595.104.02 userland and kernel packages are built for the selected snapshot.
  An NVIDIA install also loads `linux.ko`, enables the Linuxulator, and
  installs `linux-nvidia-libs` at that same driver version. After the first
  boot, `daemonarchy-linux-cuda setup` installs the Rocky Linux CUDA 13.2
  toolkit inside `/compat/linux` without a Linux kernel driver. CUDA 13.3 and
  later need a newer driver branch than 595.104.02. `daemonarchy-linux-cuda cudalab`
  builds and runs [cudalab](https://github.com/jordanhubbard/cudalab.git) as a
  Linux program for development qualification. Installer selection and application
  menu entries remain disabled until version-specific native Linuxulator evidence
  is recorded. AMD firmware and Radeon/AMDGPU selection remain included.
  Supported AMD (`amdgpu`), Intel (`i915kms`), and NVIDIA installs also
  install `vulkan-loader` and `mesa-dri`. That is the common Vulkan layer:
  RADV, ANV, and NVIDIA's ICD from `nvidia-driver`. Legacy `radeonkms` does
  not get it. CUDA stays a NVIDIA-only extra and does not replace Vulkan.
  Native package admission and policy tests do not replace physical display,
  login, suspend, or cudalab qualification.
- Installer console: the live installer loads Terminus 16×32 (`terminus-b32`)
  when the console is wider than 200 columns. That is the face the Linux
  console selects on a HiDPI panel. The 16-inch MacBook's 3584×2240 EFI
  console is otherwise 448 columns of the default 8×16 font.
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
  repositories was addressed in 1.0.1. Both upstream PRs still await merge;
  upstream acceptance is tracked separately from release qualification of the fork.

### Optional development trees

Space planning for installer selections that populate `/usr/ports` and `/usr/src`
is recorded in [the sizing report](docs/optional-source-sizing.md). The live
packages now contain depth-1 shallow Git checkouts, superseding the original
source-only estimate. Separate installer selections and the runtime
`daemonarchy-checkouts` command are implemented; native package round-trip tests
pass. A complete unencrypted UEFI bhyve ISO installation and reboot with both
options selected also passed on bare metal, including post-boot checkout
verification; see the [test record](docs/testing-1.1-live-checkouts.md).
Other boot modes and runtime-only installation remain pending. Repeat sizing
after the ports refresh and FreeBSD CURRENT source sync.
