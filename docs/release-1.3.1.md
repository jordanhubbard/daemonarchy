# Daemonarchy 1.3.1 release notes

**Status: unpublished candidate.** This page records the intended release and
the evidence still needed before a stable GitHub release. No public 1.3.1 ISO,
package feed, checkout feed, or boot bundle is available yet. The private
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
at `d63d77f4`. Ports `main` is `7e417dae`, with the same release file tree as
`efb8f848` and the reviewed official package snapshot lineage. A trial merge
of upstream ports `7b2b5742` changed 3,140 files and had eight conflicts,
and would require a
new package baseline and full dependency rebuild. The selected `www/chromium`
port and official binary catalogue contain Chromium `154.0.8037.57_2`;
upstream ports main has `156.0.8078.47_1`. Chromium remains in Daemonarchy,
but this candidate does not claim the newer browser version.

These are candidate changes. The desktop observation was on an installed 1.1.1
system with live development updates. It does not qualify a fresh installation
from the final 1.3.1 ISO.

## Qualification still required

- Finish the native production source and ports builds. Publish and verify the
  versioned signed application and checkout feeds with a real FreeBSD client.
- Assemble the public ISO without private firmware or development signing
  credentials. Verify its exact inputs, SHA-256, signed boot bundle, production
  certificate, and installed package and module inventory.
- Run the [MacBook acceptance plan](testing-macbookpro16-1-1.3.1.md) from an
  erased disk using Wi-Fi for installation. Confirm unattended autoboot,
  storage integrity, desktop input, Wi-Fi traffic and reboot, debugger recovery,
  and production Secure Boot enrollment and enforcement. The earlier installer
  reported a fatal NVMe event; Apple Diagnostics returned `ADP000`, but this
  does not explain or clear that event.
- The installed 1.1.1 MacBook failed its [S3 trial](testing-macbookpro16-1-s3-20261024.md):
  ACPI PCIe methods timed out, USB devices detached, and the Broadcom firmware
  reported a trap. Suspend and resume remain unqualified for 1.3.1.
- The MSI Raider 18 HX with RTX 5080 still resets during early kernel startup.
  Loader networking works in isolation; continuous authenticated early-kernel
  capture and a physical boot result remain open. This page makes no MSI
  installation or attestation claim.

The exact ISO digest, source and ports release heads, signed feed tags, final
hardware results, and GitHub release URL will be added only after those
artifacts and observations exist. The root `CHANGELOG.md` retains the detailed
candidate history and limitations.
