# Daemonarchy 1.3.1 release notes

Daemonarchy 1.3.1 is the next production release after 1.1.1. Version 1.2.0
was not published, so the 1.3.1 changelog and public announcement cover the
entire interval since 1.1.1. The [GitHub release](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.3.1)
is the authority for the final ISO, asset hashes and publication state.

**Preparation checkpoint, October 24: unpublished candidate.** This page
records the intended release and evidence needed before publication. The
[initial signed 1.3.1 checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-amd64-1.3.1)
is public with 11 matching asset digests. The selected ports revision requires
a [replacement signed checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-amd64-1.3.1-r2).
All 11 replacement assets match their published digests, and a native FreeBSD
`pkg` client accepted its public catalogue and listed all three packages.
At that checkpoint, no public 1.3.1 ISO, application package feed, or boot bundle was available. The private
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

Other work since 1.1.1 includes measured installer-progress displays,
bounded package-acquisition and dependency-graph tooling, authenticated
catalogue and native package-plan checks, owned QEMU workers, early wired
network-debugging development, and Literate AI contracts for the retained
FreeBSD implementation. The root CHANGELOG.md keeps the detailed
record. These development paths retain their recorded qualification limits;
their presence in the repository does not make them public-ISO features or
claim a complete LitAI-managed release, safe parallel package installation,
or physical early-kernel debugger acceptance.

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
`daemon.local` and the madmax FreeBSD guest. At the October 24 preparation
checkpoint, the madmax ports bulk was still running; its failed earlier
attempts were retained, and a passing retry was required. `daemon.local` was
reserved for independent final-ISO bhyve testing. The package build and ISO
have separate qualification records in the public release.

The operator confirmed on 2026-10-24 that **all pre-production checks passed
on the Intel 16-inch MacBook Pro** and waived an additional physical acceptance
run against the final public 1.3.1 ISO. Existing test records keep their
original image and development-input scope; the confirmation does not supply
a final-ISO hardware run or artifact hash. See the
[MacBook release decision](../verification/macbook-release-decision-1.3.1.json)
and [acceptance record](testing-macbookpro16-1-1.3.1.md).

## October 24 production gates

These gates were open at the preparation checkpoint. The public GitHub release
notes and exact asset record report their final results; this section preserves
the decision and required checks without treating an earlier attempt as passed.

- Finish the native production ports build and verify the versioned signed
  application feed with a native FreeBSD client. The replacement checkout
  feed's public digests and signed catalogue had passed at the selected source
  and ports revisions. Final-ISO installation had not run at this checkpoint.
- Assemble the public ISO without private firmware or development signing
  credentials, then verify its exact inputs, SHA-256, signed boot bundle,
  production certificate, installed package and module inventory, and the
  native build evidence bound to the release record. LitAI's broader project
  receipt remains open under its staged adoption work.

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

The public GitHub release linked above carries the exact ISO digest, signed
feed tags and final native verification. The root `CHANGELOG.md` retains the
detailed candidate history and limitations.
