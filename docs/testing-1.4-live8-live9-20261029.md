# 1.4 live8 and live9 acceptance candidates (unsigned images) (2026-10-29)

This is a development record. It does not qualify a release. The images are
unsigned, nothing was published, and the evidence is on `daemon.local` under
`/usr/daemonarchy/live8-20261029` and `/usr/daemonarchy/sb14`. It follows
[live7](testing-1.4-live7-20261029.md).

## What changed since live7

- **live8** adds daemonarchy-src#47 (`vmd: Treat bus offset setting 3 like 2`).
  On an MSI Raider 18 HX with Intel VMD enabled, `vmd(4)` rejected the
  controller (`pcib12: Unknown bus offset`; `VMD_CONFIG` read `0x2f01`, offset
  field 3), so the NVMe drives behind it never appeared and the installer saw
  no internal disk. Linux maps value 3 like 2 (start bus 224); live8 does the
  same. Linux's interrupt-ordering workaround for this device (ARL004) is not
  ported.
- **live9** is live8 plus a signed Secure Boot bundle. On a MacBookPro16,1 the
  installer stages the BCM4364 Wi-Fi firmware and then requires a signed boot
  profile; live4 to live8 had none, so the install stopped with
  `MacBook firmware installation requires a signed boot profile; this image has
  none.` The 1.3.1 bundle cannot be reused: its policy kernel is `d63d77f4`,
  which predates the T2 NVMe fix.

Both images use the product tree at `origin/main` `95a4760c6cdf` and
daemonarchy-src `f6f30e8e1713` (`da95f20bcceb` plus #47). Their kernel is
`FreeBSD 16.0-CURRENT #1 f6f30e8e1713`. live8 and live9 reuse live7's package
repository, which is byte-identical to live6's.

## Artifacts

| File | SHA-256 |
|---|---|
| `daemonarchy-1.4.0-live8-amd64.iso` | `09aa374960d33ffddcc8b7464425118f3316c2c0d7d3e4dc0c96448d2984e03e` |
| `daemonarchy-1.4.0-live8-amd64.iso.xz` | `13dbb994e1beb20f09c6b7e673a26bec03e074c0531a8f28a62b82258a8164da` |
| `daemonarchy-1.4.0-live9-amd64.iso` | `920a011c18a27e99a821b085e6f91ff394cbddb914ce4e22dc9d458d19407577` |
| `daemonarchy-1.4.0-live9-amd64.iso.xz` | `d00850fcbe41b72a9b6e053ad498ec5afebf4a559bcdb201664494e78a195e09` |
| Secure Boot bundle `daemonarchy-1.4.0-boot.txz` | `64ff86ed39e021047a786407946ef49a96b2e8cd3078330dc048515e8bfcce77` |
| bundle signature `.sig` | `737c4dfe8922fd7718eb651a0aded6a40cebcbc1466356cdce7ff2af0ef65fda` |
| policy-kernel build receipt `build.json` | `3be289246274841d7892b8881cbc34ee4b016604aa5afd8440b28e6ad589b7ea` |
| policy kernel | `4da75dfc4791d82a1e7f1f8680fe5231e00d7292b523fb634ced734f16c0f3d7` |

## Secure Boot bundle

Built with the 1.3.1 recipe at the live8 revision, signed with the 1.3.1
Secure Boot authority ("Daemonarchy Secure Boot 1.3.1 candidate", valid to
2036), so the certificate is unchanged. All four patches in
`secureboot/patches` apply in sequence to the live8 source. The policy kernel
builds in 4 minutes. `maintenance.py verify` passes ("signed bundle and
installed boot files match"). The public bundle has 14 entries and contains no
private key or firmware. The runtime manifest names the BCM4364 firmware files.

The build, signing and maintenance tools pin each accepted source revision in
four hard-coded maps (`bundle.py`, `module-inventory.py`, `sign-boot-tree.py`,
`maintenance.py`). The live8 revision was added by hand in a scratch copy. A
real release must commit the pin for its exact revision.

## Results

- **Native suite** (FreeBSD 16.0-CURRENT, on the live7 product tree, which is
  the same product commit): 20 of 20 pass.
- **Full install and boot of live8** (QEMU/KVM on a Linux host, with the host's
  GPU as the VirGL render node, `tests/test-qemu.sh` with
  `EXPECTED_PACKAGE_REPOSITORY_TAG=packages-16-amd64-1.3.1` and
  `tests/qemu-desktop.py`): installed in 46 minutes and every check passed,
  including `sddm running`, the selected signed application feed, and
  `PASS: graphical login, input, native browser and package manager`.
  A run of live7 without a GPU failed `sddm running` because the SDDM greeter
  (`Hyprland`) aborts without a DRM device, and failed the feed check because
  the expected tag was not set. Neither was a product fault.
- **Package feed `packages-16-amd64-1.4.0`** is staged and signed with the
  1.3.1 package key (public-key DER SHA-256 `67986b40…74ef7`), 208 files, and
  is not published. It differs from the published 1.3.1 feed only in the 11
  packages updated by ports#31. The `daemonarchy` package keeps the published
  1.3.1 bytes. Over HTTP with fresh pkg databases, the right key loads all 204
  entries and a wrong key loads none. A byte flipped in the catalogue was not
  rejected, so that case is not claimed.
- **arm64:** an unsigned development ISO for `da95f20bcceb` was built natively
  on the arm64 worker (`daemonarchy-1.4.0-live7-aarch64.iso.xz`, SHA-256
  `b9c306faf357eb473a256b1d547205ecf4c7ae247a952125d848e076219c2e63`). It has
  not been booted.

## Hardware

- **MacBookPro16,1 with live8:** the internal NVMe drive is visible, so the T2
  NVMe fix works. The install stopped at the signed-boot-profile check above.
  The firmware stage verified (four BCM4364 B3 files). Built-in sound does not
  work: the T2 audio function (`106b:1803`) has no driver and the default
  output is HDMI. See [the application note](application-note-macbookpro16-1.md#sound).
- **MSI Raider 18 HX with live7:** the installer saw only the USB stick. With
  VMD enabled the NVMe controller is hidden (see live8 above).
- **Not yet run:** live8 on the MSI and live9 on the MacBook.

## Scope

Per operator decision on 2026-10-29, the exact-image installer network matrix
(ledger A14) and upgrade or rollback through the installation image (part of
A11) move to [1.4.1](roadmap/release-1.4.1.md).

## Open

- The MSI result with live8 and the MacBook result with live9.
- Merging daemonarchy-src#47, then rebuilding the kernel, the Secure Boot
  bundle and the ISO at the merged revision, with the pin committed.
- Publishing the feed and the images, and verifying the tag and assets.
