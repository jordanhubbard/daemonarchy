# Testing the 1.1 partition installer

This is a development preview, not the completed 1.1 release. The partition
installer supports **UEFI boot with a healthy GPT disk and an existing EFI
system partition**. Secure Boot still needs to be off.

The preview carries the existing 1.0.1 desktop package with the new installer
and updated Omarchy package. Its welcome screen adds `1.1 partition preview`
to that package version; it does not claim to be the final 1.1.0 release.

## Choose where to install

The disk screen shows existing partitions, their device names, types and sizes,
including free space. It then offers:

- **Use an existing OS/data partition**: replace only the selected partition
  with Daemonarchy. Its contents are erased. Type its exact device name to
  confirm. Other partitions are preserved.
- **Create a partition in free space**: select a free extent, then enter the
  new partition's size in MiB. The minimum is 20480 MiB (20 GiB). Existing
  partitions are preserved, and no filesystem is resized.
- **Erase the entire disk**: the original whole-disk installation, with an
  explicit warning that every partition will be destroyed.

For either shared-disk choice, select the existing EFI partition to share.
The installer checks it read-only before changing the OS partition. It never
formats that EFI partition, replaces its existing loaders, or writes BIOS
bootcode to a shared disk. EFI, reserved and recovery partitions are protected
from selection as the OS target. Shared-disk installs do not allocate swap.

The new loader goes in a unique `EFI/Daemonarchy-<pool>/loader.efi` directory.
The installer adds a Daemonarchy firmware boot entry and selects its ZFS pool
explicitly. Existing boot entries remain available in the firmware boot menu;
the new Daemonarchy entry becomes first in the boot order. If firmware refuses
that entry, installation reports failure rather than overwriting a fallback
loader. This preview does not add a Windows chooser to FreeBSD's boot menu.

## The two physical test scenarios

Keep a backup and Windows recovery media before testing a development installer.
Prepare either at least 20 GiB of unallocated space, or an OS/data partition
whose contents can be replaced. Resize Windows from Windows beforehand if
needed; the installer does not perform that operation.

1. Boot the preview USB in UEFI mode. Check the partition table against the
   expected disk layout before choosing a target.
2. For the free-space scenario, choose **Create a partition in free space**.
   Verify the selected extent and requested size on the confirmation screen.
3. For the replacement scenario, choose **Use an existing OS/data partition**.
   Verify the device name and the explicit erase warning for that partition.
4. Complete installation, boot Daemonarchy, and confirm the desktop works.
5. Use the firmware boot menu to boot Windows. Confirm its files and recovery
   partition remain accessible and record any BitLocker recovery prompt.
6. Confirm the existing Windows EFI loader and partition boundaries/UUIDs
   remain unchanged. Record the ISO checksum, scenario, disk sector size,
   encryption choice, result, and `/tmp/daemonarchy-install.log` from the live
   installer if a step fails.

## Automated evidence

`sudo bash tests/shared-disk.sh` runs on a headless FreeBSD worker and modifies
only the memory disk it allocates. It tests both selection modes with 512-byte
and 4 KiB sectors, with and without GELI encryption (eight cases), creates an
actual ZFS pool on the selected target, and checks
that unselected partition geometry and UUIDs, Windows/recovery fixture data,
and existing Microsoft, fallback and FreeBSD EFI files remain unchanged.
It also checks rejection of stale layouts, disks in use (including an open
partition through a GPT label), BIOS shared-disk installs, protected/undersized
partitions, invalid free extents, and sizes that do not fit.

Those checks passed on 2026-10-12. These are synthetic Windows-style fixtures,
not proof that a real Windows installation boots afterward. Physical Windows
boot tests, complete preview installation, and encrypted shared-disk boot
remain acceptance gates.

Do not run the automated fixture test in a desktop session with an automounter:
it can mount the temporary EFI partition and make the test correctly refuse
further writes. The tests do not stop the desktop's automounter.
