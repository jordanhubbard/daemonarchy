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
