# 1.5.1 plan: network upgrades and forkability

- **Status:** active
- **Owning queue item:** [NETUP-001](active-work.md#netup-001-upgrade-an-installed-systems-base-kernel-modules-and-boot-files-over-the-network)
- **Supporting queue items:** [NETUP-002](active-work.md#netup-002-update-trust-over-the-network-package-key-and-secure-boot-certificate-rotation), [NETUP-003](active-work.md#netup-003-qualify-upgrade-paths-on-exact-artifacts), [FORK-001](active-work.md#fork-001-let-another-developer-fork-the-repositories-and-publish-their-own-installer-packages-and-feeds)
- **Completion / archival evidence:** pending; nothing here is claimed done. Done means the evidence in each queue item, retained with exact inputs.

Opened 2026-11-01. It exists because of an assertion that was checked and found not to hold: that
Daemonarchy 1.5 would be the last release needing an ISO because full network upgrades from the GitHub
CDN are supported, and that another developer can fork the repositories and publish their own installer
and package collection. The investigation is recorded below. No document claims the assertion.

## Verdicts

| Half | Verdict | One line |
|---|---|---|
| A. Full network upgrade from the GitHub CDN | **PARTLY** for application packages, **FALSE** as asserted | Application packages upgrade over the network from signed feeds. Base, kernel, kernel modules, boot files and trust do not, and no upgrade of the 1.4 line was accepted. An ISO is still required across a snapshot change and for any release whose upgrade has not been qualified. |
| B. Another developer can fork and publish their own installer and feeds | **PARTLY** (possible with code edits), **FALSE** that it is easy | Several scripts take the repository and key as parameters and `pkg-repo.sh keygen` exists, but the installer pins `jordanhubbard/daemonarchy` URLs, a committed public key and our checkouts and extension feeds, and there is no fork guide. |

## A. The evidence

What works today:

- **Application packages.** `pkg upgrade` against the signed Daemonarchy feeds, which are GitHub release
  assets (`pkg-repo.sh`: "the repository is the assets of one GitHub release"). The 1.1 record shows an
  application-package upgrade and ZFS rollback on development artifacts
  ([testing-1.1-upgrade.md](../testing-1.1-upgrade.md)). `daemonarchy update` is described as saving a boot
  environment first ([getting-started.md](../getting-started.md#10-keep-it-up-to-date)); the implementation
  is in the separate omarchy-freebsd repository (`freebsd-bin/omarchy-snapshot` mentions `bectl`), which was
  not read for this plan.
- **Same-snapshot boot maintenance (development tool).** `daemonarchy-secureboot stage` and `activate`
  validate a signed bundle, stage it in a new boot environment and activate it for the next boot
  (`secureboot/maintenance.py`; [HACKING.md](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#secure-boot-development)). The 1.1 record
  has QEMU evidence, including a refused bad bundle and a rollback, with development authority
  ([testing-1.1-upgrade.md](../testing-1.1-upgrade.md#enforced-same-snapshot-boot-maintenance-checks-2026-10-16)).
  The file's own header says installer integration and native transaction qualification are required
  before it can be a supported update command.

What does not exist or is not qualified:

- **No base or kernel feed.** Nothing publishes a base, kernel or pkgbase feed for installed systems.
  [source-builds.md](../source-builds.md) and HACKING describe development pkgbase packages and installer
  sets, and say the snapshot-based procedure remains the release input path.
- **A newer feed on an older base is refused.** `scripts/adopt-candidate-packages.sh` compares the running
  kernel and userland `OSVERSION` with the catalogue and stops: "Upgrade the FreeBSD base and kernel
  together, with matching drivers, before selecting this feed." HACKING: "a newer feed requires a coordinated
  base, kernel and driver upgrade first."
- **Kernel modules are locked** to the signed inventory on verified installations; changing a driver needs the
  matching signed inventory and native package in the candidate environment
  ([getting-started.md](../getting-started.md#10-keep-it-up-to-date), [secure-boot.md](../secure-boot.md#update-and-recovery-contract)).
- **Boot files.** The loader, secure kernel, manifests and `daemonarchy-secureboot` itself arrive only by
  the maintenance bundle (`MANAGED` in `secureboot/maintenance.py`), which accepts only a whitelist of known
  source commits (`SOURCE_OSVERSIONS`). "Base/ABI transitions, certificate rotation and an EFI loader-protocol
  change need a separately qualified migration" (HACKING, secure-boot.md).
- **Trust.** The 1.3.1 rotation shipped a new image and kept the old feed for old systems
  ([package-repository-key-rotation-1.3.1.md](../package-repository-key-rotation-1.3.1.md)); getting-started
  says no in-place upgrade from 1.1.1 is qualified. There is no in-band key or certificate update.
- **No upgrade QA for the 1.4 line.** The 1.4.1 notes list "image-based upgrade and rollback" as not done
  ([release-1.4.1.md](../release-1.4.1.md#upgrading)); 1.4.1 "still requires a coordinated base, kernel and
  driver upgrade" from 1.4.0. The installed laptops were reinstalled from the image. The 1.4 coverage ledger
  carries upgrade and rollback as open rows ([A11](1.4-coverage-ledger.md)).

The 1.5.0 reality: 1.5.0 uses the same snapshot as 1.4.1 (daemonarchy-src `303b364`, OSVERSION `1600029`)
but ships a rebuilt `if_brcmfmac-kmod` and a re-signed boot bundle. In principle that is a same-snapshot
maintenance (stage the bundle, upgrade the locked module package in that environment, activate). It has not
been exercised on a 1.4.1 install and is not documented as supported, so a 1.4.1 system gets the Wi-Fi fix
reliably only by installing the 1.5.0 image. The `pkg upgrade` part of 1.5.0 (applications such as
Aquamarine, Windows programs, `daemonarchy-pkg`) does reach an installed system.

## B. The evidence

Parameterised already: `pkg-repo.sh` (`GH_REPO`, `KEY`, `TAG`, `BUILD_HOST`; `keygen` makes the key,
HACKING "The signing key is ... Make it once with `pkg-repo.sh keygen`"), `scripts/package-feed-stage.py`
and `scripts/package-feed-upload.py` (`--repo`), and `build-iso.sh` (`PACKAGE_REPOSITORY_PUBLIC_KEY`,
`PACKAGE_REPOSITORY_TAG`, `NAME`).

Hard-coded to `jordanhubbard/*` (checked with `git grep`):

- the installer: `overlay/usr/local/libexec/daemonarchy-installer/install` (feed URL, line 753; checkout URL
  pattern, line 773) and `package-repository` (lines 52 and 90) validate the feed URL against
  `https://github.com/jordanhubbard/daemonarchy/releases/download/...`; `build-iso.sh` lines 102 and 146;
  `test-qemu.sh` line 333;
- `overlay/usr/local/share/daemonarchy-installer/checkouts.json` (feed and the `daemonarchy-src` and
  `daemonarchy-ports` remotes) and `extensions.json` (the repository of the extension feed);
- `scripts/release-current.py`, `scripts/verify-release-assets.py` and `scripts/package-feed-*.py` defaults;
  `daemonarchy-cudalab`'s `repo_url`;
- the ports: `x11-wm/daemonarchy` fetches `jordanhubbard/daemonarchy-desktop` and `ports-mgmt/daemonarchy-pkg`
  fetches `jordanhubbard/daemonarchy` at pinned commits (daemonarchy-ports `main`);
- the Secure Boot chain: the project certificate and bundle signing are ours, and `maintenance.py` knows only
  our source commits.

Also: the pinned public key is a committed file shipped in the image; there is no fork guide (the only
`fork` text in the docs concerns the ports and source forks we own); the builder needs FreeBSD 16.0-CURRENT with
poudriere, snapshot jails and, for a release, build hosts for both architectures and a signing window.
Default build hosts and key paths in the scripts are our own. What breaks in a fork that changes only the
repository name: the installer refuses its own feed URL, the image points at our feeds and checkouts, and
`verify-release-assets.py` checks our repository.

## What 1.5.1 will change

NETUP-001 (base, kernel, modules and boot-file upgrade with boot-environment rollback), NETUP-002 (key and
certificate rotation over the network), NETUP-003 (upgrade QA on exact artifacts) and FORK-001
(one configuration, a fork guide and an example fork CI). Their acceptance texts are in the queue. Until they
have evidence, [the upgrade model](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#the-upgrade-model-today) is the statement of what works.
