# Daemonarchy 1.1.1 refresh

Preparation started October 16, 2026. Publication is held while a confirmed
boot-environment mounting defect is corrected and the ISO rebuilt. The selected
world, kernels, release sets and source packages have built and passed package QA.
Signed application and checkout feeds are public and verified. The final image passed its native payload audit and asset integrity checks;
final installation/desktop qualification remains in progress. Earlier release qualification does not qualify
the new kernel, package set or image.

## Release authorization

On October 17, the operator explicitly authorized publishing 1.1.1 without
additional physical-hardware evidence so the refreshed release can be used
for further debugging. Physical GPU/display/suspend, Apple T2, Bluetooth,
enterprise Wi-Fi and physical dual-boot qualification are not publication
gates for this release. Their documented failures and untested states remain
unchanged; this authorization does not establish hardware support or fixes.

Publication still requires completed release artifacts, matching kernel modules,
signed package and boot payloads, and artifact integrity checks. All 749 source
package builds completed, including the 1.1.1 desktop package. One transient
HTTP/2 error fetching cliamp's Go dependency
`github.com/mewkiz/flac@v1.0.14` succeeded on a targeted retry; the completed
retry had no failed or skipped ports. All 24 isolated native testport checks
then passed, followed by the final combined repository pass and actual external
module inventory generation. The qualification exit status is zero and its
recorded ports revision matches `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`.
The signed application feed is published and independently verified from GitHub;
final image installation/desktop qualification remains outstanding. The operator
subsequently authorized production publication without waiting for that matrix.

## Recovery and diagnostics changes

- Rescue option 2 pairs or unpairs an agent, including stale state left after
  a reset. The menu waits briefly for late boot messages and redraws without
  requiring an unexplained Return keypress.
- Installer completion requires dependency and all-file package checksum
  verification, a target-pool flush before the completion marker, and another
  flush afterwards. Portable checks and a native real-package fixture passed:
  truncating an installed payload prevents completion.
- Candidate adoption compares the signed feed's package OS requirements with
  both the actual kernel and userland before changing package identities.
  Native signed-feed tests and an actual OS1600027 VM rejected the OS1600028
  payload with automatic yes, `IGNORE_OSVERSION` and spoofed `UNAME_*` values.
  Architecture-independent packages retain their supported metadata exception.
- Continuous debug observation and a controller-side receiver are included in
  this refresh. See [the operating guide](remote-agent-debug.md#continuous-diagnostics).
  Native tests passed actual snapshots, bounded samples and rotation,
  generation-based collector exit, automatic collection after SSH approval,
  collector restart, snapshot dispatch, SFTP, live-access revocation and
  stale-PID safety. Controller tests passed retention of the last remote output
  after abrupt transport death, private file permissions, finite duration and
  transport cleanup when the receiver receives SIGTERM. These checks do not
  establish the cause of the MacBook's repeated resets or qualify its desktop.
  A private native broadcast-socket fixture also passed event delivery,
  reconnection after a devd-like disconnect, file permissions and generation
  exit. On October 18 UTC the helpers were hot-deployed on the existing OS1600027
  MacBook without restarting its approved listener; the off-target receiver
  retained actual kernel/process/storage/sensor output, heartbeats and a passive
  `devd-connected` record. Unsupported `vt` text capture and thermal sensors were
  reported explicitly. That live evidence does not qualify the new OS1600028
  image or establish the cause of any reset.
- After repairing and verifying the MacBook's installed package files and
  dependencies on its existing OS1600027 base, controlled AMD initialization
  reported `KGQ enable failed`, `gfx_v10_0 hw_init failed -60` and failed device
  attachment. Module loading nevertheless returned success and left DRM nodes,
  exposing a false graphics-ready result. The refreshed service requires an
  attached active driver and DRM card/render character devices. Regression tests
  cover failed attachment with surviving nodes; the actual MacBook now rejects
  that state and clears a stale marker without reloading its driver. This fixes
  startup reporting and SDDM gating, not the underlying GPU failure. The MacBook
  remains on its old base with graphics disabled and its desktop unqualified.
  Source inspection confirms NVIDIA 595.104.02 and the selected VirtIO driver
  advertise `DRIVER_RENDER`; their shared DRM core allocates and registers both
  render and primary minors. Requiring card/render nodes therefore matches
  those drivers' successful registration paths. This is a compatibility check,
  not a new physical NVIDIA desktop result.

## Selected inputs

The upstream tips were resolved once at the start of this refresh:

- FreeBSD source: `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf`,
  OSVERSION `1600028` (previous image: `1600027`).
- Upstream ports: `b1306594c4a601f98a3d28cbf6fc0569e218245f`.
- Release ports integration: `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`,
  branch `daemonarchy-1.1.1`; combines the refreshed submissions and retains
  the existing 6.12 VirtIO backport for the release. Package QA passed.
- Desktop source is tagged `v1.1.1` at the unchanged `ec2a00824ec95b342c0c095657ac725c56f0528b`; compatibility source remains
  `535e44bb6fa3e9b9f4fc3a870591688526279124` until a tested change requires
  advancing them. The requested release is named `1.1.1`. The original rc2
  preparation was renamed at the operator's request. The final combined package
  pass includes the desktop version update at this selected integration.

The requested source tip is newer than the October 12 binary snapshot. A fresh
world, GENERIC kernel, release sets, jail and kernel modules were produced
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

All three submissions are ready for review. The 19 supporting ports and both
desktop ports passed refreshed native testport checks with port files identical
to the release integration. The separate header-only #642 head
`c3acbaca77647f4661b5b0177c861880aeb7b2f2` passed its own isolated DRM and
NVIDIA DRM testports, including stage, plist, install/deinstall and package QA.
It excludes the release's VirtIO patch. None of these submissions is claimed merged.

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
  outputs. Final signing completed with the matching inventory of 186 packages
  and 997 external modules. The isolated native boot checks below cover the new kernel and loaders. The build receipt explicitly retains
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
  source. The full combined package build with QA enabled completed against
  final ports integration `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`. The earlier dry
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
- The [versioned application feed](https://github.com/jordanhubbard/daemonarchy/releases/tag/packages-16-amd64-1.1.1)
  contains 510 application/dependency packages and five metadata assets. All 515
  GitHub asset names, sizes and SHA-256 digests match staging. Native clients
  verified the signed catalogue, fetched all 22 selected root archives from
  GitHub, and rejected an unrelated signing key. The old stable feed is unchanged.
- Outstanding: final installation/desktop matrix and complete upgrade/recovery evidence.
  The operator authorized publication without waiting for these results; they are
  not counted as passing checks.
- Published: stable installer release with all six asset sizes and SHA-256 digests
  checked against the audited payloads.

## Superseded image and continuing tests, October 18 UTC

The image below is superseded before publication by the boot-environment fix
described next. Its ongoing VM results qualify these particular components and
image, not the forthcoming corrected installer ISO.

The corrected image was built from installer commit
`250db6f2b586c74e80d3c3ebf27e4b28793ce731`, including the graphics attachment
guard. Its native public-image audit passed: required tools and installation
payloads, versioned signed-feed selection, Python runtime imports, no private
rescue authorization, and dependency resolution for every retained dynamically
linked executable. The ISO is 1,912,215,552 bytes, below the 2 GiB asset limit:

```text
daemonarchy-1.1.1-amd64.iso
79e90ec36cfff3f4875dc6bc2bc710265e1e04710ec2527909aa623935f179dc
```

The signed boot bundle SHA-256 is
`c02a72244bf676869c0ca73afbe70507fb328bcb4331ef4343dce393e9a1ae4d`.
The four fresh BIOS/enforced-UEFI, plain/encrypted installation and desktop
runs use this exact ISO. The earlier `ee422ce` image and partial runs were
superseded before publication when the MacBook exposed false graphics readiness;
they are retained as partial evidence and do not qualify this final image.

Loader and early-kernel network-debugging changes are deferred to 1.2. The
1.1.1 kernel retains the selected upstream GENERIC configuration, including
its existing NetGDB and network-dump support; no new source changes are made
for network debugging in this release.

Physical GPU/display/suspend, Bluetooth headset/HID, enterprise EAP and physical
Windows preservation limitations remain open until new evidence closes them.

## Boot-environment mounting correction, October 18 UTC

The HP trial exposed a root-mounting defect in the earlier installer. Its
original `ROOT/default` had `canmount=on`, while the trial clone had
`canmount=noauto`. The retained shared log shows userspace services starting
during the failed attempt; the clone's runtime files were never updated.
This is stronger evidence than the console's apparent kernel-load hang, but
does not alone prove which root or kernel ran during that attempt.

A native OS1600028 isolated test demonstrated the mechanism: mounting only an
owned sibling root with overlay enabled replaced the selected root's marker
and hid its already mounted devfs. Unmounting the sibling restored both. FreeBSD's
ZFS startup mounts eligible datasets automatically, and OpenZFS enables overlay
mounts by default. The installer now creates its original root with
`canmount=noauto` and explicitly mounts it before installation. The native
memory-pool regression executes those actual installer commands, checks that
the first root is mounted, and switches to a clone while verifying the original
stays inactive and devfs remains visible. All disposable datasets and devices
were cleaned; no global mount-all command or unrelated pool was modified.

The HP recovered its original OS1600026 default after the operator power-cycled
it. Its candidate remains intact. Correcting the original root's mount policy
and obtaining actual new-system boot evidence are separate from the offline
package/signature checks already passed. No EFI-loader replacement is justified
by the current evidence.

## Known dependency advisories

An actual `pkg audit` on the staged physical upgrade reports three advisories
in two selected dependencies: `python312-3.12.15` has
[CVE-2025-15366](https://www.vuxml.org/freebsd/0be929a5-2e0f-11f1-88c7-00a098b42aeb.html)
and [CVE-2025-15367](https://www.vuxml.org/freebsd/6d3488ae-2e0f-11f1-88c7-00a098b42aeb.html),
and `py312-setuptools-63.1.0_3` has
[CVE-2025-47273](https://www.vuxml.org/freebsd/690144e9-4f88-11f1-982e-00a098b42aeb.html).
The Python issues concern application-controlled IMAP/POP commands containing
newlines. The setuptools issue concerns path traversal through `PackageIndex`
downloads; upstream fixes it in 78.1.1. The current VuXML entries still list
Python 3.12 as affected. A repository search found no direct use of `imaplib`,
`poplib` or `PackageIndex` in the installer scripts; this does not establish that
all installed applications avoid those paths. This release does not remediate
these dependency advisories and is not a zero-advisory package set. Avoid passing
untrusted commands to the affected mail APIs or using the vulnerable setuptools
download path with untrusted sources. Package QA and signatures establish build
and integrity results, not absence of vulnerabilities.

## New-base boot checks, October 17

An isolated UFS test image uses the new base and stock kernel sets, the rebuilt
policy kernel and EFI loaders, and the existing production certificate. Its
kernel-only qualification bundle is separate from the final release bundle,
which was subsequently signed with the completed external-module inventory. The runtime
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
