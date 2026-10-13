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
| Dual boot and partition selection | Install into explicitly selected available space without deleting other systems; preserve existing EFI loaders and entries. Never resize an existing filesystem implicitly. | Disposable disks containing another OS survive installation with partition/data checks and both operating systems booting; insufficient space and invalid selections fail before writes. | Planned |
| Legacy BIOS boot | Add BIOS image boot and installed-system boot code, alongside the UEFI path. | Boot the ISO, install, and reboot in BIOS and UEFI VMs, including encrypted installations. | In progress: disk layout and bootcode tests pass; full boot tests pending |
| Secure Boot | Establish a signed FreeBSD boot chain and a documented key-enrollment/update process. | Install and boot with Secure Boot enabled; reject an untrusted boot component and verify signed updates. | Planned |
| Upstream FreeBSD ports | Complete review and integration of the supporting ports and the Omarchy/Daemonarchy ports; reconcile the image's ports tree with upstream. | Upstream changes merged and packaged; clean `poudriere testport` and installation against the selected package set. | Under upstream review |

Upstream reviews: [supporting ports #630](https://github.com/freebsd/freebsd-ports/pull/630)
and [desktop ports #635](https://github.com/freebsd/freebsd-ports/pull/635).
Their merge timing depends on FreeBSD maintainers.

### Delivery order

1. Establish hardware and VM test coverage and resolve driver/profile feasibility.
2. Implement graphics, networking, and Bluetooth in their owning repositories;
   update the ports and installer integration together.
3. Implement and validate the new disk and boot modes on disposable disks.
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
