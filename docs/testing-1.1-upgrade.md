# Preliminary 1.0.1 upgrade and rollback checks

Native checks on 2026-10-16 used an installation made from the published
`daemonarchy-1.0.1-amd64.iso`, whose published SHA-256 was verified before boot.
The digest was
`937b0fc007824dad47f271ebeb8b5d41323afbc6d17b225e12735588de6f9d4d`.
The original installation disk was retained; all upgrade writes used a separate
QEMU copy-on-write disk. The installation/reboot harness passed its 20 checks.
Those checks include services and configuration, not usable desktop rendering.

The baseline is FreeBSD CURRENT `main-n289844-a52c50b4b7c2`, with packages
`daemonarchy-1.0.1,1` and `omarchy-4.0.4_9`. Before upgrading, the test created
a recursive ZFS boot environment named `before-1.1-candidate` and a sentinel
file in the user's home directory.

A private candidate repository was signed with the existing package-repository
key on its protected authoring host. Only public repository files were
transferred to the test server. Its configuration retained the installed
`Daemonarchy` repository name, public key and priority, changing only the URL
to the private test endpoint. This matters because pkg's conservative upgrade
policy normally retains a package's recorded repository; adding a differently
named test repository did not select the candidate versions.

`pkg upgrade -y` successfully upgraded the desktop to
`daemonarchy-1.0.1_2,1` and the core to `omarchy-4.0.4_19`, adding OctoPkg,
qt-sudo and the native Bluetooth output dependency. The transaction downloaded
approximately 114 MiB. These packages include current 1.1 development changes,
but are **not final 1.1 packages**. No kernel or kernel module was upgraded in
this transaction.

| Native check | Result |
| --- | --- |
| Reboot into upgraded packages | Passed; package versions confirmed, SDDM running and `daemonarchy --help` available |
| Activate the previous environment and reboot | Passed; original desktop/core versions restored |
| Home-directory data after rollback | Sentinel retained unchanged |
| Development EFI loader with `daemonarchy_rootpool=<pool GUID>` | Booted the previous environment through the new firmware entry |
| Activate the candidate environment and reboot through the same entry | Passed; `BootCurrent` unchanged and candidate versions restored |

The new EFI selection check used an independently built normal loader from
the pinned October 12 source with the downstream pool-selector patch. It
resolves the selected pool's active boot environment rather than hard-coding
`ROOT/default`. That loader is not yet integrated into the installer; these
checks do not imply that published 1.0.1 or preview images contain it.

Retained evidence includes the original installation and boot serial logs,
the successful pkg transaction, package versions before/after rollback,
firmware entry and active dataset observations. The sentinel lived in the
shared home dataset, so restoring a root boot environment did not restore an
older copy of user data.

The development signed boot-maintenance tool was also exercised against this
older installation. It created and mounted a recursive candidate boot
environment, verified the signed archive, then rejected the mismatched stock
kernel before installing boot files. The candidate was unmounted and retained
without activation; the original `zroot/ROOT/default` boot selection and home
sentinel remained unchanged. An earlier attempt exposed a mountpoint guard bug,
which was fixed and covered by a regression test before this retry. This is a
native transaction-failure check with Secure Boot off, not an enforced signed
update/recovery qualification.

Final acceptance still requires the exact final 1.1 packages and the Secure
Boot signed-update/recovery path, including an injected failure on that path.
This preliminary application-package transaction does not qualify a base/kernel
upgrade, physical hardware or graphics.
