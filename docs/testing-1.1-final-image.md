# Final 1.1 image qualification

The production-signed candidate built on 2026-10-16 is
`daemonarchy-1.1.0-amd64.iso`, 2,098,395,136 bytes. Its SHA-256 is
`891fc6e6ee537bf92aecf035d4e855b8d526aeaf9c27be80166d689289c3acd9`.
The native image and transferred authoring/test copies matched. It is
49,088,512 bytes below the 2 GiB image/release-asset limit.

## Inputs

- Installer source: `f00fa952f36b7125bf50666470085029461c4bd8`, with the explicit
  final checkout catalogue later committed in `5dbb19d`.
- FreeBSD snapshot/source: `3ceb5f150bc121f5e6a3e0cc8b289279338405a1`,
  October 12, 2026, OSVERSION `1600027`.
- Ports: `08a6370a019a35ae791c549fa1da9a3ce9bd5b33`, branch
  `daemonarchy-1.1-package-baseline`.
- Desktop: `daemonarchy-1.1.0,1`, source tag `v1.1.0` at
  `ec2a00824ec95b342c0c095657ac725c56f0528b`.
- Compatibility: `omarchy-4.0.4_22`, source
  `535e44bb6fa3e9b9f4fc3a870591688526279124`.
- Production policy kernel SHA-256:
  `a2e3a6e1e73b09b22da646febb9949390d9ff9da56cf8c6980e462c67308a220`.
- Production certificate DER SHA-256:
  `111539a7fb7178cea65f3e2fc50ea00839d045324a4272ce190e4733a9c118dd`.
- Published optional checkout feed:
  `checkouts-16-3ceb5f150bc1-08a6370a019a-v1`.

The published optional checkout repository also passed native signature
verification and actual download/installation of all three payload packages.

The ISO uses public signed artifacts only. Signing keys remained on the
protected authoring host. Post-build live-file, signature, stock-kernel and
image-size audits passed. Both changed desktop ports passed native
`poudriere testport`; the final combined bulk built both without failures or
skips. The exact final application packages also passed installed native
menu/command-policy checks and the 1.0.1 upgrade/rollback/return sequence.

## Fresh installation matrix

The four tests use separate disposable QEMU disks. UEFI tests use enforced
OVMF with the production certificate appended to db, preserving existing trust.
The graphical checks use VirtIO/VirGL and real SDDM password input, Hyprland,
keyboard/pointer, native Chromium rendering and OctoPkg UI. GELI cases enter
the real loader passphrase. A launched test is not a passing result.

| Firmware | Root | Optional checkouts | Result |
| --- | --- | --- | --- |
| Enforced UEFI | ZFS | Ports and source | Running |
| Enforced UEFI | GELI/ZFS | Neither | Passed: installed boot, enforcement, native desktop policy and GUI |
| BIOS | ZFS | Neither | Passed: installed boot, native desktop policy and GUI |
| BIOS | GELI/ZFS | Neither | Passed: loader unlock, installed boot, native desktop policy and GUI |

Production-key installed GELI/ZFS maintenance passed: distinct rebuilt kernel,
altered inactive-candidate rejection, update, rollback and return, with
enforcement, shared home data and actual GUI checks at each boot. See the
[boot-chain evidence](testing-1.1-secureboot.md),
[upgrade evidence](testing-1.1-upgrade.md), and
[physical limitations](testing-1.1-hardware-observations.md).
This record does not claim physical firmware enrollment, real Bluetooth
playback, enterprise EAP exchanges or refreshed bhyve qualification.
