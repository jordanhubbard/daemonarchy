# Daemonarchy 1.1.0

Historical proposed stable-release notes. The public artifacts remain
`daemonarchy-1.1.0-rc.1`; the `daemonarchy-1.1.0` stable promotion is still a
GitHub draft at the 1.1.1 preparation checkpoint. Publication was explicitly
approved with the hardware and hypervisor limitations below, but approval is
not evidence of publication. The next requested release is [1.1.1](testing-1.1.1.md).
Outstanding qualification remains outstanding: publication does not turn an
untested or failing configuration into supported hardware.

Daemonarchy 1.1 adds native FreeBSD desktop defaults, optional installation into
selected GPT partitions/free space, BIOS boot, a QEMU/VirGL Hyprland path, and
manual-enrollment Secure Boot. The installed system uses FreeBSD packages;
Chromium and the OctoPkg package manager are included. The command presented to
users is `daemonarchy`. Linux/Arch-only launchers, including Docker setup, are
removed from the menu. Unsupported Linux applications are not offered without
Linuxulator qualification.

The installer uses the October 12 FreeBSD CURRENT snapshot, source revision
`3ceb5f150bc121f5e6a3e0cc8b289279338405a1` (`1600027`). Kernel modules are built
against that snapshot. Optional depth-1 source and ports checkouts are downloaded
when selected instead of being carried on the ISO. Authors retain verified
release-set, package and distfile caches between builds.

Remote debugging now reports authenticated connection, activity and explicit
completion on the console. A disconnected SSH command does not mark the session
complete. Recovery/debug tools are also installed on disk.

Secure Boot requires manual enrollment of the published project certificate.
Firmware with only factory Microsoft/OEM keys will reject the project loader.
The production certificate asset is `daemonarchy-1.1.der`; its SHA-256 is
`111539a7fb7178cea65f3e2fc50ea00839d045324a4272ce190e4733a9c118dd`.
Enrollment must append the certificate to db while preserving existing trust
entries. The installer does not enroll keys. The signed profile admits matching
kernel modules and protects its enforcement controls; ordinary application
packages remain installable. Signed boot updates use a retained boot environment
and explicit validation/activation. See [the enrollment guide](secure-boot.md).

The exact candidate application packages passed an isolated 1.0.1 `pkg upgrade`
and rollback test. The signed application packages are available through the versioned
`packages-16-amd64-1.1.0-candidate` feed. That result does not establish that
the unversioned stable feed was promoted. An application-package
transaction does not upgrade the FreeBSD base/kernel, replace its drivers,
or convert an existing installation to verified boot. Kernel modules must match
the running snapshot. The verified maintenance path currently covers the pinned
snapshot and loader protocol; a base/ABI migration needs separate qualification.

## Hardware limitations and open qualification

- The ASRock X570 Taichi/RTX 4090 test system became unable to visibly boot any
  OS or open usable firmware setup after installation recovery. The cause is
  unknown; display maintenance/output selection are hypotheses. The operator
  requested continued release work and community investigation. Live native and
  Linux NVIDIA diagnostics and a shim-assisted CUDA kernel passed before this
  failure; installed Hyprland, suspend and physical Windows preservation did not
  receive a passing result. See [the retained observations](testing-1.1-hardware-observations.md).
- The MSI Raider 18 HX AI A2XWIG (Ultra 9 285HX, RTX 5080, BIOS E1824IMS.312)
  resets early in kernel probing with both 1.0.1 and preview.11. No validated
  early-boot workaround or automatic quirk is available.
- The tested Apple T2 MacBook Pro encountered an `apple_bce` panic and unusable
  internal keyboard during recovery. It is not qualified for installation.
- Enterprise Wi-Fi profile validation has native test coverage, but real
  enterprise authentication/reboot remains untested: no test network is available.
- Refreshed bhyve and encrypted bhyve qualification remain pending; the tested
  graphical VM path is QEMU with VirtIO/VirGL. No alternate desktop is used.
- Bluetooth audio is limited to the implemented A2DP/SBC path. Real headset
  playback, reconnect/reboot and HID regression qualification remain pending.
- CUDA toolkit installation and menu entries remain disabled. The successful
  RTX 4090 driver-API probe required the UVM shim and does not qualify Unified
  Memory, the complete toolkit, or every CUDA application.

The release ISO is 2,098,395,136 bytes (under 2 GiB), SHA-256
`891fc6e6ee537bf92aecf035d4e855b8d526aeaf9c27be80166d689289c3acd9`.
Exact final application-package upgrade, reboot, rollback and return from 1.0.1
passed. Image inputs and fresh-install results are recorded in
[the final image record](testing-1.1-final-image.md).

All four fresh configurations passed installation, reboot, installed desktop
and application-policy checks: production-key enforced UEFI and BIOS, each
with plain ZFS and GELI/ZFS. The UEFI plain case also downloaded both optional
checkouts and verified their revisions, cleanliness and ownership. Production-key signed maintenance also
passed update, altered inactive-candidate rejection, rollback and return, with
actual graphical checks at each boot. [The roadmap](../ROADMAP.md) retains the remaining
qualification work; an untested configuration is not a support claim.
