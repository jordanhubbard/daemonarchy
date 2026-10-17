# Daemonarchy 1.1-rc2 refresh

Preparation started October 16, 2026. This record is in progress; rc2 has not
been built, qualified or published yet. Earlier release qualification does not
qualify the new kernel, package set or image.

## Selected inputs

The upstream tips were resolved once at the start of this refresh:

- FreeBSD source: `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf`,
  OSVERSION `1600028` (previous image: `1600027`).
- Upstream ports: `b1306594c4a601f98a3d28cbf6fc0569e218245f`.
- Release ports integration: `84afb7141bd066711e0f45737b1705941380ee1a`,
  branch `daemonarchy-1.1-rc2`; combines the refreshed submissions and retains
  the existing 6.12 VirtIO backport for the release. Package QA remains pending.
- Desktop source remains `v1.1.0`; compatibility source remains
  `535e44bb6fa3e9b9f4fc3a870591688526279124` until a tested change requires
  advancing them. The installer candidate is named `1.1-rc2`.

The requested source tip is newer than the October 12 binary snapshot. A fresh
world, GENERIC kernel, release sets, jail and kernel modules must be produced
from this exact revision. The previous release sets, ports integration, signing
outputs and test evidence are retained separately. The stable package feed is
not a candidate publication target.

## Upstream submissions

All three branches start at the selected current upstream ports revision;
previous fork merge history is excluded.

- [PR #640](https://github.com/freebsd/freebsd-ports/pull/640): 19 supporting
  ports, one commit per port, replacing closed #630.
- [PR #641](https://github.com/freebsd/freebsd-ports/pull/641): current Omarchy
  and Daemonarchy ports, replacing closed #635. Scripts and desktop content
  are fetched from their source repositories as requested in the earlier review.
- [PR #642](https://github.com/freebsd/freebsd-ports/pull/642): separate DRM
  and NVIDIA DRM LinuxKPI configuration-header fixes. The downstream VirtIO
  backport is excluded; upstream driver review remains
  [drm-kmod #517](https://github.com/freebsd/drm-kmod/pull/517).

These submissions start as drafts pending refreshed native validation. Historical
native testport results are identified as results from the earlier package
baseline in each description. They are not current-baseline passing results.

## Checks and remaining work

- All four Secure Boot source patches apply cleanly to the selected source tip.
- The 23 signing/maintenance tests pass on macOS and on the native FreeBSD
  builder after updating the exact source and OSVERSION guards. The previous
  OSVERSION is explicitly rejected by the module-inventory regression test.
  Native signing, enforcement, recovery and boot validation on the new base
  are still required.
- All 21 new-port Makefiles parse against the selected current ports framework.
  Native `portlint -AC` reports zero fatal errors for all 21 ports; advisory
  warnings remain. The preflight fixture uses the exact refreshed port files
  and framework; all 21 ports also passed distfile checksum checks. This
  preflight does not replace full-tree dependency or testport checks.
- The image can now select a release-specific signed application feed through
  `PACKAGE_REPOSITORY_TAG`, and installed systems retain that selection.
  Stable fallback, rc2 selection and malformed/multiline metadata rejection
  pass on macOS and FreeBSD. Native image/install checks remain pending.
- Current ports requires Python 3.12.15 while the selected official package
  collection provides 3.12.14. The candidate publisher can include rebuilt
  ordinary dependencies, excluding kernel-bound and unrelated fetched packages.
  The installer resolves dependencies from this signed feed and retains their
  normal Daemonarchy update identity. A real native signed-pkg fixture passed
  dependency resolution, repository migration, a subsequent version upgrade,
  kernel/fetched-package exclusion and protection of the unversioned stable feed.
  The explicit candidate adoption step also upgrades an older official
  dependency without installing unrelated feed packages or replacing private
  repository overrides.
- The policy kernel and both EFI loaders built successfully from the selected
  source using the production public certificates. The build receipt records
  policy-kernel SHA-256
  `5022ac4bbf1b1cef9f590bc4384fea554197f1d85bf35d690840780fbeebbe13`.
  Signing and native firmware/kernel qualification remain pending; the build
  receipt explicitly retains `native_boot_qualified: false`.
- Source checkout admission now recognizes full, shallow and detached kernel
  revision labels while still requiring the selected commit and rejecting dirty
  trees. Parser tests pass on macOS and FreeBSD; the actual current stock kernel
  also matches its own source and rejects the rc2 revision.
- The new world build completed in 4,043 seconds; the matching GENERIC kernel
  is compiling. The completed dependency dry run queued 1,466 packages: 718
  reusable official packages and 748 source builds. The builder will use a
  separate boot environment and a matching fresh jail.
- Pending: world/kernel and release-set build; matching builder/jail; refreshed
  port parsing, checksums, testport and combined package build; native module
  inventory; newly signed boot payload and checkout repositories; ISO size and
  runtime audit; fresh installation/desktop matrix and upgrade/recovery tests;
  public prerelease publication and asset-hash verification.

Physical GPU/display/suspend, Bluetooth headset/HID, enterprise EAP and physical
Windows preservation limitations remain open until new evidence closes them.
