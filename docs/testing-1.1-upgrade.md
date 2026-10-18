# Preliminary 1.0.1 upgrade and rollback checks

Historical 1.1 development/candidate evidence. Revisions, checksums and results
below apply to the named artifact and date; they do not qualify the new
[1.1.1 source/package set](testing-1.1.1.md). Follow that record for current
preparation and publication status.

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

## Enforced same-snapshot boot-maintenance checks, 2026-10-16

These checks used a separate private integration installation on the October
12 snapshot, not the older 1.0.1 base above. The installed firmware entry uses
the numeric pool selector. Its original policy kernel had a real desktop
process-inspection panic; the signed v8 bundle contains the fix described in
[the Secure Boot record](testing-1.1-secureboot.md).

| Actual native installed-guest check | Result |
| --- | --- |
| Stage authenticated v8 bundle into `qa-process-fixed-v8` | All present boot/module fingerprints validated; candidate unmounted; original selection retained |
| Validate/activate candidate and reboot | Candidate ZFS root and fixed kernel selected, actual firmware enforcement and locked policy confirmed |
| Automatic graphical startup after reboot | SDDM password login, Hyprland input, native Chromium rendering and OctoPkg UI passed |
| Stage correctly signed bundle with deliberately incorrect VirtIO module fingerprint | Failed with `Signed fingerprint mismatch: boot/modules/virtio_gpu_drm.ko`; failed candidate unmounted and retained, healthy bootfs unchanged |
| Activate previous `default` environment and reboot | Original kernel hash and rescue setting restored; locked policy remained active and SSH recovery worked |
| Re-activate v8 and reboot | Fixed environment, enforced policy and automatic greeter restored |
| Shared home sentinel through rollback and return | Retained unchanged |

The positive v8 bundle SHA-256 is
`c78c09a9eda0701eef28fe71e24a5130fbe159df1c1ee751acac5c43e82a1a64`.
It includes the authenticated maintenance helper as well as the managed boot
files. The negative bundle was intentionally signed with the development
authority, so rejection exercised installed driver validation rather than an
invalid outer signature. The failed candidate was never activated.

These results qualify the tested development-key same-snapshot transaction.
They do not qualify production enrollment, a base/ABI migration, the exact
final image, or the missing physical display/upgrade matrix.

## Final application-package upgrade and rollback, 2026-10-16

The retained original 1.0.1 environment was cloned to `qa-final-1.1-upgrade`.
The private repository used the production package-repository signature and the
final native-built packages, `daemonarchy-1.1.0,1` and `omarchy-4.0.4_22`.
`pkg upgrade -y` upgraded both packages from the original versions without
changing the stock kernel. After reboot, exact package versions, SDDM service,
`daemonarchy --help`, the kernel hash and a shared home sentinel were checked.

Activating `before-1.1-candidate` and rebooting restored
`daemonarchy-1.0.1,1` and `omarchy-4.0.4_9`. Re-activating the final candidate
and rebooting restored the exact final versions and running SDDM. Home data
remained unchanged through both transitions. No EFI entry was rewritten during
this sequence. The successful transaction is retained in the guest at
`/tmp/daemonarchy-final-upgrade-transaction.log`.

This qualifies the final application-package upgrade and ZFS rollback on the
retained 1.0.1 base. It does not qualify a FreeBSD base/kernel migration or usable
graphics on that older base. Production-authority signed boot maintenance is
recorded separately.

## Production-authority GELI/ZFS maintenance, 2026-10-16

The exact production candidate ISO from the
[final image record](testing-1.1-final-image.md) passed fresh enforced UEFI/GELI
installation and actual graphical checks. A separate QEMU copy-on-write disk
preserved that original test disk for the maintenance sequence.

A full native rebuild of the same pinned source and four policy/loader patches
used a later recorded build epoch, producing genuinely different kernel bytes.
The original production kernel SHA-256 was
`a2e3a6e1e73b09b22da646febb9949390d9ff9da56cf8c6980e462c67308a220`;
the maintenance kernel SHA-256 was
`287ca8d24cb5182adeecdaffb0799f9ab482a2ac48033a7f8d37abe9faea9f11`.
The maintenance bundle SHA-256 was
`1ee019115bc55f9439748a4a8de80c6b1f4d4f78ab6a4e8bd3e4773d5293a6c4`.
The protected production authority signed the new tree and maintenance bundle;
only public artifacts went to the guest.

| Actual installed production-key test | Result |
| --- | --- |
| Stage new signed bundle into `qa-production-update-v10` | Validated, unmounted, original boot selection unchanged |
| Stage a second valid candidate, then alter its inactive kernel | Activation rejected with `Managed boot file mismatch: boot/kernel.secure/kernel`; candidate retained and unmounted, original boot selection unchanged |
| Activate valid candidate and reboot through real GELI unlock | Updated ZFS environment and exact new kernel hash confirmed |
| Enforcement after update | Actual firmware Secure Boot enforced, verified kernel selected, all four locked policy states present |
| Graphical update check | Hyprland, keyboard/pointer, Chromium rendering and OctoPkg UI passed |
| Activate retained `default` and reboot through GELI unlock | Original kernel hash/environment restored; firmware and locked policy retained; graphical checks passed again |
| Return to updated environment and reboot through GELI unlock | New kernel hash/environment restored; enforcement and graphical checks passed again |
| Shared home sentinel throughout | Preserved unchanged |

This qualifies the tested production-key same-snapshot maintenance transaction,
failed activation and recovery on the candidate's encrypted ZFS layout. It does
not qualify a source/ABI transition, driver revision change, certificate
rotation, physical firmware enrollment or retained Windows boot. The rebuild
changes the kernel bytes/build epoch while retaining the already qualified
code and ABI; compatibility of a future code update still requires its own
native checks. The maintenance fixture is retained separately from the shipped
original boot bundle.
