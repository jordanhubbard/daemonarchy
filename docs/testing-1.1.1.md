# Daemonarchy 1.1.1 refresh

Preparation started October 16, 2026. This record is in progress; 1.1.1 has not
been built, qualified or published yet. Earlier release qualification does not
qualify the new kernel, package set or image.

## Release authorization

On October 17, the operator explicitly authorized publishing 1.1.1 without
additional physical-hardware evidence so the refreshed release can be used
for further debugging. Physical GPU/display/suspend, Apple T2, Bluetooth,
enterprise Wi-Fi and physical dual-boot qualification are not publication
gates for this release. Their documented failures and untested states remain
unchanged; this authorization does not establish hardware support or fixes.

Publication still requires completed release artifacts, matching kernel modules,
signed package and boot payloads, and artifact integrity checks. At the latest
native build inspection, 602 packages had built, 717 were fetched and 145
remained. The one failure was an HTTP/2 transport error fetching cliamp's Go
dependency `github.com/mewkiz/flac@v1.0.14`; it also skipped the dependent
desktop package. Retry that package after the active bulk run and complete the
final package pass with the selected 1.1.1 desktop port before image assembly.

## Selected inputs

The upstream tips were resolved once at the start of this refresh:

- FreeBSD source: `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf`,
  OSVERSION `1600028` (previous image: `1600027`).
- Upstream ports: `b1306594c4a601f98a3d28cbf6fc0569e218245f`.
- Release ports integration: `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`,
  branch `daemonarchy-1.1.1`; combines the refreshed submissions and retains
  the existing 6.12 VirtIO backport for the release. Package QA remains pending.
- Desktop source is tagged `v1.1.1` at the unchanged `ec2a00824ec95b342c0c095657ac725c56f0528b`; compatibility source remains
  `535e44bb6fa3e9b9f4fc3a870591688526279124` until a tested change requires
  advancing them. The requested release is named `1.1.1`. The original rc2
  preparation was renamed at the operator's request. The desktop port version
  update is integrated separately from the active dependency build; the final
  package pass will use this selected integration.

The requested source tip is newer than the October 12 binary snapshot. A fresh
world, GENERIC kernel, release sets, jail and kernel modules must be produced
from this exact revision. The OSVERSION increment changes the kernel packet-header layout, requiring
[external drivers to be rebuilt](https://github.com/freebsd/freebsd-src/commit/83f5b5c2eeba2a2d66d87d4367ca5406322386a4).
The previous release sets, ports integration, signing
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
  The isolated new-base boot checks below pass; final external-module,
  installer, recovery and maintenance validation are still required.
- All 21 new-port Makefiles parse against the selected current ports framework.
  Native `portlint -AC` reports zero fatal errors for all 21 ports; advisory
  warnings remain. The preflight fixture uses the exact refreshed port files
  and framework; all 21 ports also passed distfile checksum checks. This
  preflight does not replace full-tree dependency or testport checks.
- The image can now select a release-specific signed application feed through
  `PACKAGE_REPOSITORY_TAG`, and installed systems retain that selection.
  Stable fallback, versioned-feed selection and malformed/multiline metadata rejection
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
  The unsigned boot payload is assembled from the new release sets and policy
  outputs. Final signing awaits the matching external-module inventory; the
  isolated native boot checks below cover the new kernel and loaders. The build receipt explicitly retains
  `native_boot_qualified: false`.
- Source checkout admission now recognizes full, shallow and detached kernel
  revision labels while still requiring the selected commit and rejecting dirty
  trees. Parser tests pass on macOS and FreeBSD. ISO construction uses the same
  matcher: the actual new kernel archive accepts its exact source and rejects
  the previous snapshot revision. The previous stock kernel likewise accepts
  its own source and rejects the 1.1.1 revision.
- The new world and GENERIC kernel builds completed in 4,043 and 276 seconds.
  The base, kernel and lib32 release-set digests match their manifest. The
  builder booted this exact kernel and userland at OSVERSION `1600028` in a
  separate boot environment; the previous environment is retained. The fresh
  `16rc2` jail and its actual build clone contain the matching kernel, lib32 and
  source. A full combined package build with QA enabled is running against
  ports integration `84afb7141bd066711e0f45737b1705941380ee1a`. The earlier dry
  run queued 1,466 packages: 718 reusable official packages and 748 source builds.
  The fresh-jail run selected 717 reusable packages and 749 source builds,
  including the package manager itself.
- Both pinned checkout payloads passed actual native package installation and
  materialization: clean depth-1 trees owned by the selected user, expected
  remotes/tracking, self-contained Git objects and preserved working trees after
  seed package removal. Their repository is signed and staged with the existing
  production package key. Native signed catalogue queries, all three payload
  installs and part/archive hash checks pass; an unrelated key causes signature
  failure and rejects catalogue access and installation. The [pinned checkout feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-bdcfeac3e1cb-f7d7ee897405-v1)
  is public. All 11 GitHub asset sizes and SHA-256 digests match staging. A
  fresh native client fetched and installed all three packages from GitHub,
  verified every part and combined archive hash, and rejected an unrelated
  signing key. The embedded catalogue now selects this feed. Regenerate the
  feed if package QA advances the ports pin.
- The candidate dependency-feed fixture also passes on the new OSVERSION
  `1600028` base, including older official dependency adoption and preservation
  of private repository overrides. It additionally verifies newly required
  official-only dependencies, replacement of different same-version payloads,
  and preservation of an older private dependency during a mixed transaction.
- Rescue option 2 now toggles between pairing and unpairing a remote agent.
  Unpairing clears stale state after a reset and revokes active connections.
  Native SSH lifecycle tests pass on the new base, including unrelated PID
  preservation, mandatory fresh approval and protection of a replacement
  session from old cleanup. Portable menu tests preserve root authentication
  for both actions; native rescue installation remains idempotent.
- Pending: refreshed full-tree testport and combined package build; native module
  inventory and final signed boot payload; ISO size and
  runtime audit; fresh installation/desktop matrix and upgrade/recovery tests;
  stable GitHub release publication and asset-hash verification.

Loader and early-kernel network-debugging changes are deferred to 1.2. The
1.1.1 kernel retains the selected upstream GENERIC configuration, including
its existing NetGDB and network-dump support; no new source changes are made
for network debugging in this release.

Physical GPU/display/suspend, Bluetooth headset/HID, enterprise EAP and physical
Windows preservation limitations remain open until new evidence closes them.

## New-base boot checks, October 17

An isolated UFS test image uses the new base and stock kernel sets, the rebuilt
policy kernel and EFI loaders, and the existing production certificate. Its
kernel-only qualification bundle is separate from the final release bundle;
the latter still needs the completed external-module inventory. The runtime
probe was compiled on the new base. All successful userland boots independently
asserted OSVERSION `1600028` and printed the selected `bdcfeac3e1cb` identity.
The policy build's `-dirty` suffix identifies the existing downstream patches.

| Actual isolated QEMU check | Result |
| --- | --- |
| Enforced UEFI, production certificate enrolled | Passed loader self-tests, signed boot/runtime manifests, locked module policy, trusted module load/unload, unsigned-module rejection, protected-write rejection, process-environment reads and ordinary user execution |
| UEFI with Secure Boot disabled | Passed; selected the new stock kernel with no module policy |
| BIOS with the new base's boot blocks | Passed; selected the new stock kernel with no module policy |
| Unsigned verified EFI loader under enforced firmware | Rejected by firmware before the FreeBSD loader |
| One changed byte in the policy kernel, original signed manifest retained | Rejected by the loader with distinct actual/expected fingerprints before userland |

The valid image SHA-256 is
`61fd1e6297f28cb781156f2e44caa463b1f34eaf1f670aacdadb6be5e9311af7`.
Its kernel-only qualification bundle SHA-256 is
`8b4a663c8a6fe1e6d2028e7e0a72958fd9882a126495a045b05f882c63949488`.
Retained serial logs pass the repository's runtime and media-rejection checkers.
These checks qualify the new boot components in the isolated fixture; final
installer, external-module, ZFS/GELI and maintenance checks remain pending.
