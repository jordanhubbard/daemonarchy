# Daemonarchy 1.3.1 release notes

**Status: unpublished candidate.** This page records the intended release and
the evidence still needed before a stable GitHub release. The
[initial signed 1.3.1 checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-amd64-1.3.1)
is public with 11 matching asset digests. The selected ports revision requires
a [replacement signed checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-amd64-1.3.1-r2).
All 11 replacement assets match their published digests, and a native FreeBSD
`pkg` client accepted its public catalogue and listed all three packages.
No public 1.3.1 ISO, application package feed, or boot bundle is available yet. The private
MacBook preview embeds development-only inputs and is not a public artifact.

## What changes

- The MacBookPro16,1 development system reached a graphical desktop with Navi14
  graphics, built-in T2 keyboard and trackpad, and BCM4364 Wi-Fi. The desktop
  network menu joined a WPA2 network and obtained an address during the earlier
  hardware run. The revised installer waits for WPA and DHCP, verifies a usable
  wireless route, and can acquire required firmware from a checked Apple
  recovery image or local media before changing the target disk.
- Remote-debugging approval and the agent identity survive reboot for repeated
  hardware bring-up. The desktop menu reports listener state and permits
  explicit revocation. Installer and installed-system network setup retain the
  approved Wi-Fi profile for a later debugging session.
- The EFI loader countdown and target boot files are updated. Source, ports,
  kernel-bound modules, package catalogue, optional checkout packages, and boot
  policy are pinned to reviewed revisions for the final image.

Source `main` now merges FreeBSD CURRENT through `a3d1d4e8` (October 24)
at `d63d77f4`. Ports `main` is `b7857842`; it adds a Broadcom SDPCM event
BSSID fix to the earlier `7e417dae` release tree. Native FreeBSD Poudriere
testport passed for that fix. A trial merge
of upstream ports `7b2b5742` changed 3,140 files and had eight conflicts,
and would require a
new package baseline and full dependency rebuild. The selected `www/chromium`
port and official binary catalogue contain Chromium `154.0.8037.57_2`;
upstream ports main has `156.0.8078.47_1`. Chromium remains in Daemonarchy,
but this candidate does not claim the newer browser version.

All eight hosted source checks passed at the selected `d63d77f4` commit,
including the controller, native loader, and Linux/macOS architecture jobs.
Native FreeBSD world, kernel, and release sets passed independently on
`daemon.local` and the madmax FreeBSD guest. The madmax ports bulk is still
running; its failed earlier attempts remain recorded and require a passing
retry. `daemon.local` is reserved for independent final-ISO bhyve testing.
The package build and ISO remain separate qualification steps.

The operator confirmed on 2026-10-24 that **all pre-production checks passed
on the Intel 16-inch MacBook Pro** and waived an additional physical acceptance
run against the final public 1.3.1 ISO. Existing test records keep their
original image and development-input scope; the confirmation does not supply
a final-ISO hardware run or artifact hash. See the
[MacBook release decision](../verification/macbook-release-decision-1.3.1.json)
and [acceptance record](testing-macbookpro16-1-1.3.1.md).

## Qualification still required

- Finish the native production ports build. Publish and verify the
  versioned signed application feed with a real FreeBSD client. The checkout
  replacement checkout feed's public digests and native signed catalogue
  pass at the selected source and ports revisions. Installation from the final
  ISO remains open.
- Assemble the public ISO without private firmware or development signing
  credentials. Verify its exact inputs, SHA-256, signed boot bundle, production
  certificate, installed package and module inventory, and the retained native
  build evidence bound to the release record. LitAI's broader project receipt
  remains open under its staged adoption work.

## Hardware status and limits

- The additional [MacBook acceptance rerun](testing-macbookpro16-1-1.3.1.md)
  on the final ISO is waived by the operator. The MacBook passed all
  pre-production checks by operator confirmation; this release makes no claim
  that the final ISO bytes were installed or booted on it. The actual T2 boot
  policy and firmware enforcement of this ISO were not established, so
  hardware-rooted attestation is not claimed. [Apple's T2 firmware
  guide](https://support.apple.com/guide/security/boot-process-sec5d0fab7c6/1/web/1)
  remains the policy reference. The earlier fatal NVMe event and the
  [1.1.1 S3 failure](testing-macbookpro16-1-s3-20261024.md) are historical
  observations tied to their original images, not current release gates.
- The MSI Raider 18 HX with RTX 5080 still resets during early kernel startup.
  Loader networking works in isolation. The complete network bootloader debugger,
  pre-driver kernel capture, and physical MSI result are tracked for
  [1.3.2](roadmap/release-1.3.2.md). This release makes no MSI installation or
  attestation claim.

The exact ISO digest, signed feed tags and GitHub release URL will be added
after those artifacts exist. The root `CHANGELOG.md` retains the detailed
candidate history and limitations.
