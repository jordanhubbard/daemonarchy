# 1.1 BIOS development checks

Recorded on 2026-10-12. These checks cover the first BIOS implementation;
they are not release acceptance for 1.1.0.

| Check | Result |
| --- | --- |
| Bash/POSIX shell syntax for changed scripts | Passed |
| ShellCheck warnings | Passed with SC2154 excluded for install's sourced configuration variables |
| Native FreeBSD disk layout, 512-byte sectors | Passed: EFI p1, swap p2, ZFS p3, BIOS p4 |
| Native FreeBSD disk layout, 4 KiB sectors | Passed with the same partition indices |
| Native BIOS bootcode write and byte comparison | Passed on both sector sizes |
| QEMU SeaBIOS boot of a disposable ZFS disk | Passed: snapshot's FreeBSD loader reached `OK` after loading the kernel |
| Development ISO build | Passed using the existing 1.0.1 desktop packages and 2026-10-05 snapshot |
| Complete ISO installation and reboot, BIOS/UEFI | Not run |
| Encrypted BIOS boot | Not run |
| Physical hardware | Not run |

The smoke disk was created with `tests/bios-boot-image.sh`, using the image
build jail's boot files. QEMU used SeaBIOS, `-machine pc -accel tcg -cpu Westmere`,
512 MiB RAM, and an IDE disk with `snapshot=on`. Its serial console identified
the FreeBSD/x86 bootstrap loader built on October 5, 2026 and reached the
interactive loader prompt. Missing `/etc/hostid` and `/boot/entropy` messages
are expected on this boot-files-only test disk.

Development image: `daemonarchy-1.1.0-dev-bios-amd64.iso`

SHA-256: `728e1e7bf49da1c8f53afd5428fd6b15079fb63ea9186d5217900665faadb6f1`

The development filename does not change the desktop package version or
constitute a published 1.1.0 release. The [roadmap](../ROADMAP.md) retains the
full installation, hardware, upgrade, and publication gates.


## Complete QEMU checks, 2026-10-15

Preview.11 passed unattended installation and installed-system reboot checks
under both SeaBIOS and OVMF UEFI, using QEMU 10.2.1 with KVM, q35, four virtual
CPUs, 4 GiB RAM and a disposable 40 GiB virtio disk. BIOS selected neither
checkout; UEFI selected `/usr/src` and verified its clean, user-owned, depth-one
Git checkout at `a52c50b4b7c2652954ef1bd34710a4b1fc8ef391`, matching the kernel.

Both runs verified the firmware boot method, BIOS partition, account/groups,
sudo, SDDM configuration and running service, networking, mDNS, packaged file
ownership, GSettings schemas, signed package repository access and staged
desktop defaults. Both ended with `All checks passed` and guest shutdown.
The UEFI installer shutdown logged a WITNESS lock-order warning involving
ISO/tmpfs unmounts; it did not prevent the installed system from booting.

Image SHA-256: `7a52f5c2e463fcd82ff224c4c4e5350ee4e5c98377344ffcba2d3f63b9f50653`.
Serial install/boot logs and check outputs are retained in the local
`2026-10-15-preview11/qemu-bios` and `qemu-uefi` evidence directories.
The corrected harness uses ATAPI CD media for xorriso CIDATA, bounds each VM
phase, preserves existing disks/logs, and stops its own VM on timeout or failure.
Its timeout cleanup was exercised with an actual one-second KVM run.

These are unencrypted, console/SSH checks of preview.11. They do not qualify
graphical VM rendering, hardware, later desktop package changes or encrypted
boot; those gates remain open.
