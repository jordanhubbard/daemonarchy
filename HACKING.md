# Hacking on Daemonarchy

How to build a Daemonarchy image yourself, change the installer, the ports, or the artwork, and test and release the result. [README.md](README.md) says what Daemonarchy is; this is for working on it.

Current refresh: **1.1.1**, FreeBSD source `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf`
(OSVERSION `1600028`), ports `f7d7ee897405dcb8ce87e674588a4e1b3bfba00e`
on `daemonarchy-1.1.1`. Keep base, kernel, jail, drivers, optional source checkout
and signed manifests on that selection. The [qualification record](docs/testing-1.1.1.md)
tracks publication readiness. Older image examples below must use their own
retained inputs; a package update is not a base/ABI migration.

## Literate AI project authority

Read [PROJECT.md](PROJECT.md), [the active queue](docs/roadmap/active-work.md) and
[the architecture](docs/architecture/design-traceability.md) before changing
cross-component behavior. Literate AI 1.3.0 currently validates the in-place
contracts; original source and the native commands below retain implementation
and release authority. Automatic quarantine conversion was not applied.

Run `litai project validate .` for authority checks and `litai verify` for the
complete declared gate report. The latter must continue to report a missing
current native receipt until ADOPT-002 qualifies native execution and release custody.
No generated source, native qualification or publication permission follows from
a metadata check. Keep signing keys and private worker evidence outside Git.

Use `litai work record` for new stable work IDs. Update the owning requirements,
acceptance evidence and changelog together. A prospective implementation change
must explicitly refresh its retained source baseline; metadata-only adoption
checks must preserve original implementation bytes. Native commands and platform
requirements remain in this runbook. PERF-001 permits replacing the build
executor after equivalent correctness and measured performance are demonstrated;
generated wrapper commands alone do not establish that qualification.

## Where things live

Daemonarchy spans the installer, desktop, compatibility, source and ports repositories:

- **This one** builds the installer image:
  - `overlay/usr/local/libexec/daemonarchy-installer/`: the installer. `launch` runs from root's login on the live system; `configurator` asks the questions (it vendors Omarchy's own setup form); `install` partitions, installs, and configures; `dashboard` draws the install screen from the install log.
  - `overlay/usr/local/libexec/daemonarchy-installer/install-integrity`: checks installed package files and dependencies before the installer records success. A nonzero result retains a failed installation and its rescue evidence.
  - `overlay/usr/local/libexec/daemonarchy-installer/rebuild-caches`: rebuilds the caches the packages' pkg triggers maintain (GSettings schemas, GIO modules, icon and MIME caches), which `pkg -r` cannot (see Pitfalls).
  - `overlay/usr/local/libexec/daemonarchy-installer/fix-ownership`: restores the owners, groups and modes packages record, which `pkg -r` loses when installing into the target (see Pitfalls).
  - `overlay/usr/local/share/daemonarchy-installer/`: the installer's logo, the loader brand, the keymap table, and the package repository's public key (`daemonarchy.pub`).
  - `origins.sh`: the ports whose packages Daemonarchy publishes itself, rather than taking them from pkg.FreeBSD.org.
  - `build-iso.sh`: collects the package repository and builds the hybrid ISO with `poudriere image`.
  - `pkg-repo.sh`: publishes the signed online package repository that installed systems update from (see Releasing).
  - `live-post.sh`: turns the plain FreeBSD image into the live installer (console autologin, memory-backed `/var`, loader brand).
  - `test-bhyve.sh` and `test-qemu.sh`: unattended install tests.
  - `docs/getting-started.md`: the beginner's guide; its screenshots are in `docs/images/`.
- **[jordanhubbard/omarchy-freebsd](https://github.com/jordanhubbard/omarchy-freebsd)**: the FreeBSD layer that `x11-wm/omarchy` installs together with Omarchy:
  - `freebsdize.in`: the adaptation of Omarchy's sources, run by the port and by `daemonarchy dev link`.
  - `compat/`: stand-ins for the systemd and Linux tools Omarchy calls (`systemctl`, `uwsm`, `journalctl`, `timedatectl`, `brightnessctl`, ...).
  - `freebsd-bin/`: FreeBSD versions of commands built on pacman, `/sys`, NetworkManager or BlueZ, among them `omarchy-wifi` (wpa_supplicant) and `omarchy-bluetooth` (FreeBSD's Bluetooth stack), which feed the network and Bluetooth panels.
  - `systemd-user/`: the session's PipeWire and keyring units.
  - `seed-user`: copies Omarchy's defaults into a home on the first session (Arch does this from `/etc/skel`).
  - `polkit-omarchy.rules`: lets an active wheel session run `omarchy-wifi` and `omarchy-bluetooth` as root.
- **[jordanhubbard/daemonarchy-desktop](https://github.com/jordanhubbard/daemonarchy-desktop)**: Daemonarchy's own layer, installed by `x11-wm/daemonarchy`:
  - The artwork: `wallpaper.svg`, `wordmark.svg` (the login screen's logo), `mark.svg` (the horned "A"), `screensaver.txt`, `about.txt`.
  - The SDDM theme that reuses Omarchy's with the Daemonarchy wordmark.
  - The System > FreeBSD menu (`omarchy-menu.jsonc`) and the `daemonarchy-*` commands behind it.
  - Its tags set Daemonarchy's version (see Releasing).
- **[jordanhubbard/daemonarchy-src](https://github.com/jordanhubbard/daemonarchy-src)**: the owned FreeBSD source fork. [Owned source builds](docs/source-builds.md) describes exact-commit world/kernel/pkgbase and installer-set preparation; [the performance plan](docs/roadmap/build-performance.md) tracks complete Component execution and build-system evaluation. Development outputs do not change the published 1.1.1 selection.
- **[jordanhubbard/daemonarchy-ports](https://github.com/jordanhubbard/daemonarchy-ports/tree/daemonarchy-1.1.1)** is the release ports fork; 1.1.1 uses `daemonarchy-1.1.1`, while the older 1.1 candidate uses `daemonarchy-1.1-package-baseline`. Upstream review does not block releases from this fork. It carries the ports:
  - `x11-wm/omarchy`: Omarchy itself, with omarchy-freebsd as a second distfile. Its `files/` holds only patches to Omarchy's own files, among them the ones that add the `FreeBSDWifi.qml` and `FreeBSDBluetooth.qml` stand-ins to the panels.
  - `x11-wm/daemonarchy`: the full desktop's dependencies, plus daemonarchy-desktop. Defaults for new users go to `share/omarchy/skel.d/daemonarchy`, which `seed-user` copies in ahead of Omarchy's.
  - The applications and tools Omarchy uses, one port each (`x11-themes/aether`, `graphics/tensaku`, `misc/ttfx`, ...), resubmitted upstream in [freebsd/freebsd-ports#640](https://github.com/freebsd/freebsd-ports/pull/640); `x11-wm/omarchy` and `x11-wm/daemonarchy` are in [#641](https://github.com/freebsd/freebsd-ports/pull/641). The earlier #630/#635 submissions were closed unmerged. The LinuxKPI header fix is [#642](https://github.com/freebsd/freebsd-ports/pull/642); review status is independent of fork qualification.
  - `x11/quickshell` carries a fix for a use-after-free in its Hyprland IPC, which is now committed upstream ([#634](https://github.com/freebsd/freebsd-ports/pull/634)).

## Working on Daemonarchy from Daemonarchy

A Daemonarchy machine can be its own development machine, much as Omarchy's repo mode works on Arch.

`daemonarchy-dev-setup` (also System > FreeBSD > Hack on Daemonarchy) clones the trees into `~/src`: Omarchy at the installed version on a `daemonarchy-dev` branch, omarchy-freebsd, daemonarchy-desktop, this repository, and the ports tree with the Omarchy ports. It then offers to link the desktop to the Omarchy checkout.

### Omarchy from a checkout

`daemonarchy dev link ~/src/omarchy` runs the desktop from your checkout after a reboot. A checkout of Omarchy is Arch-flavored, so on FreeBSD it is not run directly: the omarchy port's `freebsdize` builds the same FreeBSD tree the port installs (applying the port's patches, adding the FreeBSD versions of commands, rewriting paths and interpreters) into `~/.local/share/omarchy-dev`, and `OMARCHY_PATH` points there. While an Omarchy session runs, `daemonarchy dev sync --watch` rebuilds that tree a moment after each save; `daemonarchy dev sync` does it by hand. `daemonarchy dev unlink` goes back to the installed Omarchy.

The link also points sudo at the tree's commands (a `secure_path` in `/usr/local/etc/sudoers.d/omarchy-dev-path` that keeps FreeBSD's `/sbin`, `/bin`, and `/usr/sbin`).

If one of the port's patches stops applying to your checkout (you moved past the version the port packages), `daemonarchy dev link` and `sync` say so; refresh the patch in `~/src/freebsd-ports/x11-wm/omarchy/files`.

### The FreeBSD layer and the desktop layer

The ports fetch omarchy-freebsd and daemonarchy-desktop as tagged releases. To try your own checkout instead, let the port extract its sources, lay the checkout over them, and let it carry on:

```
cd ~/src/freebsd-ports/x11-wm/omarchy        # or x11-wm/daemonarchy
make extract
rsync -a --exclude .git ~/src/omarchy-freebsd/ "$(make -V WRKSRC_freebsd)/"
#   for daemonarchy: rsync -a --exclude .git ~/src/daemonarchy-desktop/ "$(make -V WRKSRC)/"
sudo make reinstall clean
```

`daemonarchy dev link` takes the FreeBSD commands and `freebsdize` from the installed port, so reinstall the omarchy port this way before linking to try changes to them.

### Observe native source dependencies

After pinned-tree discovery, use the native collector from this repository with
Python 3.11 or later on an unprivileged amd64 FreeBSD worker. Keep the output
outside the source tree and use a new directory for every observation:

```sh
python3 /path/to/daemonarchy/scripts/resolve-freebsd-dirdeps.py \
  --repo /path/to/daemonarchy-src --revision <full-source-commit> \
  --output /path/to/new-observation --unit bin/ls --acknowledge-evaluation
```

This evaluates trusted Makefiles, including parse-time commands, while requesting
only variables; it is not a sandbox or a build/acceptance pass. It rejects dirty
or ignored source inputs, bounds each query and the total run, retains partial
records on failure and refuses existing output directories. Omit `--unit` to seed
all amd64 dependency declarations and follow supported host/common contexts.
Missing declarations, unsupported contexts and cycles cause a nonzero result.
Run `PYTHONDONTWRITEBYTECODE=1 python3 tests/native-dirdeps.py -v` for eleven portable
refusal/graph/process checks; native observation remains a separate result.

## Isolated test-image staging

Every `build-iso.sh` invocation allocates a new private directory beneath
`ISO_STAGE_PARENT` (default `/var/tmp`) and prints its path. The parent must
already exist and be an absolute, nonsymlink directory. Failed and completed
staging trees remain for inspection; a later invocation never deletes them.
Use separate output names, output directories and native build selections too:
private staging alone does not make concurrent mutation of a poudriere jail safe.

The [1.2 test-ISO preparation](docs/testing-1.2-test-iso.md) precedes physical
qualification and is separate from final release publication.

## Setting up a build host

The product controller now pins the exact combined framework wheel from source
`e90cbadb`, recorded in `verification/native-first-binding-integration-development.json`.
It combines reviewed Standard binding with metadata-only original-source adoption;
the preceding `73311c69` checkpoint remains historical migration evidence.
Select the matching isolated installation as `FRAMEWORK_CLI` in private operator
configuration and use `"$FRAMEWORK_CLI"` for lifecycle planning and verification.
The default installed CLI and active source/ports workspace are preserved. This
configuration binding does not qualify a retained native build or produce its
missing receipt. Original-source authority is now selected through the reviewed
metadata-only `project adopt-original` flow. Actual action/input profiles and
native admission remain required. Use the explicit retained manifest/profile
`build` or `test` interface for that work; legacy harness readmission expects
legacy conversion metadata and is not an original-project initializer.

For a loader-only hardware test medium, follow
[the 1.2 test-ISO checklist](docs/testing-1.2-test-iso.md). `TEST_LOADER_BUNDLE`
selects a hash-checked EFI/Lua bundle for the live medium only. It refuses a
Secure Boot bundle and does not provision debugging keys, enable the console,
change installer sets or select the installed-system loader. Run
`python3 tests/test-loader.py -v` for its selection/refusal controls; actual image
assembly, boot and native lifecycle admission remain separate requirements.

For builds from our owned FreeBSD-CURRENT fork, start with
[owned source builds](docs/source-builds.md) and the versioned daemonarchy-src
runbook. That workflow produces development pkgbase packages and installer sets
from an exact source commit. The snapshot-based procedure below remains the
current release input path until the owned outputs pass admission, signing,
matching jail/module and VM/hardware qualification.

During source and ports development, periodically refresh the upstream tracking
refs for FreeBSD-CURRENT and ports `main`. Check again before choosing a new
diagnostic baseline, submitting a fix or qualifying a release. Review relevant
upstream commits, including LinuxKPI, NVMe, EFI, DRM ports and firmware changes,
and record the fetched revisions and the disposition of related fixes. Refresh
our development branches in isolated worktrees, preserving local patches and
skipping fixes already upstream. Pin each resulting source/ports selection and
rebuild against its matching kernel headers before native and hardware tests.
Keep the previous qualified selection available for comparisons and rollback;
fetching upstream alone is not an integrated or qualified refresh.

For pinned Git-tree discovery, run `python3 scripts/inspect-freebsd-graph.py`
with `--kind source` or `--kind ports`, `--repo`, an exact `--revision`, and a new
`--output` path outside the inspected repository. A ports object store can be
cloned with `--filter=blob:none --no-checkout`; discovery needs its tree objects,
not Makefile evaluation. Run `PYTHONDONTWRITEBYTECODE=1 python3 tests/native-tree-discovery.py -v`
for the portable refusal tests. Discovery outputs are not canonical catalogs,
complete dependency graphs, pkg provenance or framework receipts. See the
[Component/performance plan](docs/roadmap/build-performance.md).

You need a FreeBSD 16.0-CURRENT machine (bare metal or a VM with capacity for the selected build) with poudriere, git, and the ports tree, as root.

The 1.1.1 dependency rebuild used an isolated 20-CPU, 80-GiB VM with a 400-GiB
disk and two package builders. Smaller hosts may work with lower concurrency;
the full Chromium/CEF/LLVM dependency stack needs substantially more time and
space than a cached installer-only rebuild. Check resources before dispatching.

1. **A jail from the snapshot the image installs.** Before the next release, re-sync system sources with [FreeBSD CURRENT (`main`)](https://github.com/freebsd/freebsd-src/tree/main), select the image snapshot, and record its exact source revision. `/usr/src` offered by the installer must match that snapshot; do not fetch a moving branch at install time. Recreate/update the build jail and rebuild the selected kernel modules when moving snapshots. Cache the verified release sets first, then use those same files for the jail and ISO:

   ```
   sh scripts/cache-release-sets.sh
   poudriere jail -c -j 16amd64 -a amd64 -v 16.0-CURRENT -m tar=/var/cache/daemonarchy-iso/base.txz
   tar -xpf /var/cache/daemonarchy-iso/kernel.txz -C /usr/local/poudriere/jails/16amd64
   tar -xpf /var/cache/daemonarchy-iso/lib32.txz -C /usr/local/poudriere/jails/16amd64
   ```

   Populate the jail's `/usr/src` from that same source revision before building
   kernel modules. Include `lib32` before the first bulk run: dependencies such
   as LLVM need its 32-bit libraries, and adding it later changes GCC's default
   multilib option and invalidates cached compiler/dependency packages.

   On ZFS, Poudriere clones the jail's `@clean` snapshot, which jail creation
   recorded before those additions. Retain that initial snapshot under another
   name and recreate `@clean` from the completed jail before starting a build.
   Verify that the snapshot itself contains `/boot/kernel/kernel`,
   `/usr/lib32/libc.so.7` and the selected `/usr/src/sys/sys/param.h`; checking
   only the live jail directory does not establish what its build clones use.

2. **A ports tree pinned to the official package set.** Before the next release, refresh [the fork's `omarchy` branch](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy) from [upstream FreeBSD ports](https://github.com/freebsd/freebsd-ports), preserving and testing the Daemonarchy changes. The earlier 1.1 candidate uses `daemonarchy-1.1-package-baseline`; the refreshed 1.1.1 uses `daemonarchy-1.1.1` and the exact revision in [its qualification record](docs/testing-1.1.1.md). The 1.1.1 upstream tip is newer than the official binary baseline, so mismatched dependencies must also be rebuilt and published in its versioned candidate feed. Keep the selected integration fixed during qualification. Matching pkg.FreeBSD.org's `latest` baseline avoids rebuilding large dependency stacks; moving beyond it requires the versioned rebuilt-dependency publication procedure below. The official baseline is the newest `ports_top_git_hash` annotation across the set's packages. Builds are incremental, so one package's annotation can be older than the set:

   ```
   mkdir -p /tmp/pq/db /tmp/pq/repos
   printf 'FreeBSD: { url: "pkg+https://pkg.FreeBSD.org/FreeBSD:16:amd64/latest", mirror_type: "srv", signature_type: "fingerprints", fingerprints: "/usr/share/keys/pkg", enabled: yes }\n' >/tmp/pq/repos/FreeBSD.conf
   P="pkg -o PKG_DBDIR=/tmp/pq/db -o REPOS_DIR=/tmp/pq/repos -o ABI=FreeBSD:16:amd64 -o OSVERSION=1600026"
   $P update -q
   $P rquery -a '%At=%Av' | sed -n 's/^ports_top_git_hash=//p' | sort -u
   ```

   Check out the newest of those commits and apply the Daemonarchy-specific commits from `origin/omarchy` in order, skipping changes already upstream. Review that list after each sync; it must not include upstream merge commits. Register the resulting tree with poudriere:

   ```
   git clone --branch omarchy https://github.com/jordanhubbard/freebsd-ports.git /usr/local/poudriere/ports/omarchyiso
   cd /usr/local/poudriere/ports/omarchyiso
   git remote add upstream https://github.com/freebsd/freebsd-ports.git
   git fetch upstream main
   git checkout -b omarchy-iso <commit>
   git cherry-pick <daemonarchy-commit-1> <daemonarchy-commit-2> # reviewed list, in order
   poudriere ports -c -p omarchyiso -m null -M /usr/local/poudriere/ports/omarchyiso
   ```

3. **poudriere settings** (`/usr/local/etc/poudriere.d/omarchyiso-poudriere.conf`): build the kernel modules for the jail's kernel instead of fetching the package builders' copies, which target a different kernel:

   ```
   PACKAGE_FETCH_BLACKLIST="drm-*-kmod gpu-firmware-* wifi-firmware-* nvidia-* linux-nvidia-libs"
   PACKAGE_FETCH_URL="http://pkg.FreeBSD.org/\${ABI}"
   DISTFILES_CACHE=/usr/ports/distfiles
   ```

4. **Build the packages.** List the origins in `ISO_ORIGINS` in `origins.sh` in a file, and bulk-build with `-b latest`. Poudriere fetches eligible official dependencies and builds incompatible or missing ones against the selected jail:

   ```
   poudriere bulk -j 16amd64 -p omarchyiso -b latest -t -f omarchyiso-ports.list
   ```

   A refresh ahead of the official binary baseline can require hundreds of builds, including compilers and browsers. Preserve caches and logs; elapsed time alone is not evidence that a build stalled. An installer-only rebuild can reuse the qualified package set.

5. **Build the image:**

   ```
   ./build-iso.sh
   ```

   The image is named after the version of the `daemonarchy` package it carries: `daemonarchy-<version>-<arch>.iso`, for example `daemonarchy-1.0.0-amd64.iso`. Set `NAME` to override.

   The image and its `.sha256` land in `/usr/local/poudriere/data/images`.

   The live installer omits the base development toolchain, C/C++ headers,
   static libraries and compiler resources using `scripts/live-image-excludes`.
   Its shells, networking, storage and rescue tools remain available. These
   exclusions apply only to the live root: `base.txz` and `kernel.txz` remain
   intact, so the installed system retains its compiler, headers and libraries.
   Optional ports/source checkout packages are fetched separately; only their
   small catalogue is on the ISO. The build rejects a final ISO at or above
   GitHub's 2 GiB per-asset limit before generating its checksum. Run
   `bash tests/live-image-budget.sh` to check the exclusions and size boundary.
   On FreeBSD, `sudo sh tests/live-image-runtime.sh <iso>` mounts the image
   read-only, checks required live commands and payloads, and resolves the
   dynamic dependencies of every retained ELF program and library. It uses
   and detaches its own temporary memory-disk device. Follow this with a VM
   boot check; the dependency audit does not qualify installation or hardware.

   For development images, set `NAME` to a distinct preview filename and
   `PREVIEW_LABEL` to a short description. The installer welcome screen shows
   that label alongside the actual desktop package version.

### Persistent authoring caches

Keep the following directories on persistent storage on the ISO build host.
They are reused by anyone following this build workflow, including authors
running it inside a VM; retain its disk or mount persistent cache storage when
replacing the VM.

| Build input | Persistent location | Reuse |
| --- | --- | --- |
| Port source archives | `DISTFILES_CACHE`, above `/usr/ports/distfiles` | Ports reuse downloaded distfiles and verify them against `distinfo`. |
| Official dependency packages | `/usr/local/poudriere/data/packages/$JAIL-$PTREE/.pkg-cache` and the package repository | With `-b latest`, poudriere fetches eligible packages into its cache and links them into the repository. |
| Built packages | `/usr/local/poudriere/data/packages/$JAIL-$PTREE` | Poudriere checks existing packages and builds only missing or invalidated ones. |
| FreeBSD release sets | `SET_CACHE_DIR`, default `/var/cache/daemonarchy-iso` | `cache-release-sets.sh` and `build-iso.sh` share `MANIFEST`, `base.txz`, `kernel.txz`, and `lib32.txz`. |

Repeat the bulk and image commands with the same jail, ports-tree name and cache
paths. An installer-only change normally needs just `build-iso.sh`; it reuses
the package repository and release sets. Poudriere invalidates packages when
versions, options or dependencies change. Kernel-bound packages must be rebuilt
for a new snapshot even when a cached package has a compatible-looking ABI.

The release-set helper hashes each cached archive against the retained
`MANIFEST`. A valid archive is reused without contacting the snapshot server.
A missing or damaged archive is downloaded to a temporary file and replaces
the cache entry only after its checksum passes. A failed or partial download
does not replace the previous file. The image build also checks the jail's
FreeBSD version and the catalogue's source revision against the kernel set.

To put sets on another volume or retain separate snapshots, use the same
override for cache preparation and image construction:

```sh
export SET_CACHE_DIR=/build-cache/daemonarchy/sets/<selected-source-revision>
export SNAPSHOT_URL=https://download.freebsd.org/snapshots/amd64/16.0-CURRENT
sh scripts/cache-release-sets.sh
# Create the jail from "$SET_CACHE_DIR/base.txz" and extract its kernel/lib32.
JAIL=16amd64 PTREE=omarchyiso sh build-iso.sh
```

For source-built sets such as 1.1.1, populate this directory from the exact qualified build, including its MANIFEST, rather than fetching a newer daily snapshot. The moving snapshot URL is consulted only for missing inputs. Select a new
cache directory for a new snapshot so an older retained `MANIFEST` cannot be
mistaken for the new selection. Preserve poudriere's repository structure,
including `.latest` and any `.building` directory left by an interrupted bulk
run; poudriere can resume using its completed packages. Its cache management
may prune obsolete entries, so these directories are caches rather than release
archives. Retain final ISOs, checksums and published checkout payloads separately.

Fresh installer test VMs currently have independent package caches. The
authoring caches above speed package and ISO construction; sharing downloads
between those fresh test installations is a separate harness improvement.
Run `sh tests/release-set-cache.sh` on FreeBSD to exercise initial fetching,
offline reuse, damaged-entry repair and rejection of a corrupt replacement.

## Changing things

### The installer

The installer flow lives in `overlay/`, primarily as Bash helpers. An installer-only change needs a new image (`./build-iso.sh`) and runtime validation; it can reuse the already qualified package set.

- **The install screen** can be tried without an install: `dashboard` draws from a log file, so feed it one. Run it in a 160x50 terminal (the console's size) with `ISO_SHARE` pointing at a directory holding `logo.txt`, and append `@@phase <name>` lines, `Number of packages to be fetched: N`, `Fetching <pkg>: ... done`, and `[ n/N] Installing <pkg>...` lines to the log; it exits with the number written to the status file.
- **`install`** reads its answers from `$DAEMONARCHY_INSTALL_CONF`; the keys are what `configurator`'s `write_install_conf` writes. An unattended install takes the same file from a FAT drive labelled `CIDATA`, which is how both test scripts run.
- **`configurator`** sources Omarchy's setup form from the `omarchy` package at build time (`build-iso.sh` extracts it), so the account, hostname, and timezone questions follow Omarchy's.

### The ports

Work on a review branch based on the exact integration commit in [ROADMAP.md](ROADMAP.md). For 1.1.1 this is `daemonarchy-1.1.1`, pinned in [its qualification record](docs/testing-1.1.1.md); verify that poudriere uses the matching tree and snapshot jail before rebuilding.

- `poudriere testport -j 16amd64 -p <tree> -o <origin>` checks a port in a clean jail: stage-qa, the plist, install, and deinstall. Use it rather than `make stage-qa` as root on the host, which installs the port's dependencies onto the host.
- To try a change on a running Daemonarchy desktop, `make reinstall` the port there; `seed-user --force` re-copies the defaults into the home (it never overwrites a file you have).
- Pin each reviewed omarchy-freebsd or daemonarchy-desktop source change to an immutable tag or full commit in its port (`GH_TUPLE` in `x11-wm/omarchy`, `DISTVERSION` in `x11-wm/daemonarchy`), and run `make makesum`.
- Bump `PORTREVISION` whenever a package's contents change: poudriere rebuilds on version changes, not on file changes, so an unbumped port keeps its old package.
- Review and merge against the selected integration branch, pin its merged commit, then run native `poudriere testport` and rebuild the combined packages (step 4 above). Keep the matching official-package baseline; do not merge a moving ports tip into the qualified tree.

### The artwork

The wallpaper, wordmark, and mark are SVG in daemonarchy-desktop; the `x11-wm/daemonarchy` port renders the wallpaper to a 3840x2160 JPEG and the wordmark to the login screen's PNG with `rsvg-convert` at build time. Preview an edit with `rsvg-convert -w 1920 wallpaper.svg -o preview.png`. `about.txt` (the About screen's art) was made from `mark.svg` with Omarchy's own `omarchy-transcode-ascii`, and `screensaver.txt` is the same wordmark the installer shows.

Daemonarchy's artwork is original: keep the FreeBSD and Arch Linux logos out of it, and keep Daemonarchy's identity in daemonarchy-desktop rather than in Omarchy's files or omarchy-freebsd.

## Testing

The unattended harnesses check the installed system: the account and its
`wheel`, `operator`, `video`, and `audio` groups, SDDM's user, session, and theme,
sshd, Avahi, mDNS lookups, DHCP, and the Daemonarchy defaults. These SSH checks
do not qualify a graphical desktop. Hyprland requires a working DRM renderer;
the new VirtIO DRM/VirGL candidate and its separate graphical checks are
described in [the VM graphics record](docs/testing-1.1-vm-graphics.md). Preview.13
does not contain that driver integration.

- **`test-bhyve.sh <iso>`** on a FreeBSD host with VT-x or AMD-V, as root, with `edk2-bhyve` installed. It reads the installed disk directly after the install. `NET=nat` (the default, with pf and dnsmasq) or `NET=bridge` (onto the host's network, using the LAN's DHCP); `test-bhyve.sh --cleanup` undoes either. The guest's memory is wired (`MEM`, default 3G) so a busy host cannot swap it out: leave the host at least that much free, or lower `MEM`.
- **`test-qemu.sh <iso>`** anywhere QEMU runs, without root: it logs in over SSH and checks from inside. On a non-x86 host the guest is emulated, and an install takes two to three hours.

For the 1.1 BIOS work, run `BOOT_MODE=bios ./test-qemu.sh <iso>` and
`BOOT_MODE=uefi OVMF=/path/to/OVMF.fd ./test-qemu.sh <iso>` with separate
`WORK` directories. UEFI remains the default. Both runs check the firmware
mode reported by the installed kernel. `sudo bash tests/disk-layout.sh` on
FreeBSD checks the partition layout and actual BIOS bootcode on temporary
memory disks with 512-byte and 4 KiB sectors; it does not prove bootability.
The added BIOS partition is p4, in the alignment gap before the EFI partition,
so the existing EFI, swap, and ZFS partition numbers remain unchanged.

### Boot-environment mount policy

Boot-environment roots, including the original `ROOT/default`, must use
`canmount=noauto`. The installer explicitly mounts that first root before
writing into it. An inactive sibling with automatic mounting enabled can cover
the selected boot environment at `/`, including its mounted `/dev`. A cloned
environment's own `noauto` property does not protect it from that sibling.
For an older installation, inspect `zfs list -o name,canmount,mounted,mountpoint`
for the pool's boot environments before migration and correct each boot root
with mountpoint `/` to `canmount=noauto`; preserve unrelated datasets. Changing
that property does not unmount an already mounted root.

Run `sudo bash tests/boot-environment-mounts.sh` on FreeBSD. It executes the
actual installer root-creation commands in its own temporary memory-disk pool,
checks the initial explicit mount, and switches to a cloned root while keeping
the original inactive and devfs visible. It never runs global `zfs mount -a`
or changes another pool.

### BIOS and shared-disk fixtures

For a faster BIOS boot-chain check, run
`sudo bash tests/bios-boot-image.sh /new/test-directory /usr/local/poudriere/jails/16amd64`
on FreeBSD. It creates a disposable ZFS disk containing that snapshot's boot
files. Boot `disk.img` in QEMU with SeaBIOS and `-serial stdio`; reaching the
FreeBSD loader prompt checks the BIOS-to-ZFS-loader chain. This deliberately
does not install packages or qualify the complete installed desktop.

Shared-disk development is covered by `sudo bash tests/shared-disk.sh` on a
headless FreeBSD worker. It allocates its own disposable memory disks and tests
partition/EFI preservation and pre-write rejection. See the
[partition preview guide](docs/testing-1.1-partitions.md) for scope and physical
acceptance. A shared-disk unattended config must explicitly set
`install_mode=partition` with `partition_index`, or `install_mode=free_space`
with `free_start` (sector offset) and `install_size_mib`; both also require
`efi_index` and a current `disk_snapshot` from `disk_fingerprint`. The interactive
configurator writes these values. Omitting the mode retains the original
whole-disk unattended behavior; never omit it when preserving another OS.

Both send the installer's log to the guest's serial port, so a stalled install leaves a trail.

Set `INSTALL_PORTS=true INSTALL_SRC=true` on either harness to exercise both
optional live checkouts. After reboot, the checks run as the installed user and
verify ownership, clean Git status, exact catalogue revisions, tracking branches
and depth-1 history. The source revision must match the installed kernel.
Leave either option unset to check its default-off behavior. Use separate
`WORK` directories for each run. The bhyve harness now verifies SSH login after
reboot and shuts down the guest after checking it; bridge mode requires
`GUEST_IP`. Its NAT mode discovers the address from its own DHCP lease file.
Run `test-bhyve.sh --cleanup` with the same `WORK`, `VM`, `TAP` and `BRIDGE`
settings afterwards to remove the test network.

On real hardware, the install log is `/tmp/daemonarchy-install.log` on the live system.
Development installs also stream it to the target's
`/var/log/daemonarchy-install.log`, retain installation state and kernel
snapshots under `/var/db/daemonarchy/install`, and install recovery before
the desktop package transaction. See the [rescue console guide](docs/rescue-console.md)
for the password gate, boot monitor, interrupted-install behavior and tests.

NVIDIA installation enables both `linux` and `linux64` in the live kernel
before disk writes. The `linux_base` pre-install script checks
`kern.features.linux64` on that running kernel, including when using `pkg -r`.
Deferring Linux compatibility until the installed system boots is too late.
The cache repair step also repeats Linux ldconfig/GIO setup inside the target.
On an older installer, `kldload linux64` from its root shell enables the missing
ABI; do not rerun the whole installer over an existing target merely to retry
the package transaction.

CUDA/toolkit and cudalab installation are withheld in the current release.
`cuda_options_prepare` rejects `install_cuda=true` before disk writes, including
unattended installation. Their development scripts and portable tests remain
in the tree, but the earlier RTX 4090 driver-API result does not qualify the
complete toolkit, Unified Memory or cudalab. See the [application policy](docs/freebsd-application-policy.md)
and [retained hardware results](docs/testing-1.1-hardware-observations.md).
Desktop NVIDIA driver installation remains separate from this disabled option.

## Remote debugging on a test machine

The development installer provides a root debug shell and a separately enabled,
console-approved SSH listener. Opening either does not start installation or
choose a target disk. See the [remote debug guide](docs/remote-agent-debug.md)
for the full operator handoff and the [rescue console guide](docs/rescue-console.md)
for recovery after an interrupted installation or failed graphical startup.

### Open the shell and establish networking

At the USB welcome screen, choose **Remote agent debug**. The network screen
also offers **Open debug shell**. Both open a local shell even without a working
network. `help` or `remote-debug help` prints the available commands; `exit`
returns to the screen that opened it.

Start by identifying the hardware and network interfaces:

```sh
kenv smbios.system.product
pciconf -lv
usbconfig
ifconfig -a
sysctl net.wlan.devices
route -n get default
```

Use Ethernet initially when available. `dhclient ue0` requests an address on
that interface; substitute the name actually shown by `ifconfig`. Wi-Fi can be
configured through the installer's network form or with FreeBSD's
`wpa_supplicant` and `dhclient`. An associated wireless interface, a DHCP address,
a default route and working DNS are separate checks. `wpa_cli -i wlan0 status`
shows authentication state without printing the configured password. Do not
print or attach the supplicant configuration, which contains credentials.

Check package-server access with a bounded probe:

```sh
timeout 8 fetch -T 5 -o /dev/null https://pkg.FreeBSD.org/
```

The outer timeout also bounds DNS resolution. A usable LAN address allows
remote debugging even when internet access, DNS or HTTPS is failing. Inspect
`/etc/resolv.conf`, the DHCP lease and the system date before changing network
settings. If the debug connection itself uses Wi-Fi, restarting that interface
interrupts access; arrange a local operator or an alternate connection first.

### Enable access and pair the agent

At the physical console, run `remote-debug listen` for port 2222, or
`remote-debug listen 2207` for another port. Confirm the enable prompt. The
screen shows usable IPv4 addresses and a freshly generated server fingerprint.
The listener requires FreeBSD, an unlocked root account and a usable address.
The shell alone does not enable it.

On the agent's machine, create a temporary session key and show its fingerprint
to the operator:

```sh
pair_dir=$(mktemp -d)
ssh-keygen -q -t ed25519 -N '' -f "$pair_dir/operator"
ssh-keygen -l -f "$pair_dir/operator.pub"
ssh -i "$pair_dir/operator" -o IdentitiesOnly=yes \
  -o UserKnownHostsFile="$pair_dir/known_hosts" \
  -p 2222 root@MACHINE_IP
```

Replace `MACHINE_IP` and the port with the displayed values. Compare the server
fingerprint before accepting its host key. The operator then compares the
agent-key fingerprint on the local console and types `y` only for that key.
Authentication can wait up to two minutes for this approval. A rejected key
stays rejected until the listener is stopped and restarted. Reuse the approved
key for subsequent SSH and SCP commands in this session (`scp` uses uppercase
`-P` for the port).

The approved connection is a root shell. Start with read-only hardware, network
and disk inventory. Installation remains a separate action requiring an agreed
target disk or partition. To operate the installer forms remotely, use
`ssh -t` and `/usr/local/libexec/daemonarchy-installer/launch`.

### Collect evidence and keep the console readable

Capture `dmesg -a` before changing verbosity. A diagnostic preview can enable
verbose boot for filming early probes; kernel and driver messages can then
overwrite an interactive screen. For the current boot, use:

```sh
dmesg -a > /tmp/daemonarchy-debug-kernel.log
sysctl debug.bootverbose=0
sysctl kern.consmute=1
```

Kernel messages remain available through `dmesg`. Restore console output with
`sysctl kern.consmute=0` before trying to capture a panic on screen. These are
runtime settings; they do not change the installed system's loader settings.
Some driver warnings are independent of verbose boot, so reducing
`debug.bootverbose` alone may not stop them.

Installation output is `/tmp/daemonarchy-install.log` on the live system when
an installation has started. Development installations also retain
`/var/log/daemonarchy-install.log` and `/var/db/daemonarchy/install` on the
target. The active debug server's log is
`/var/db/daemonarchy/remote-debug/sshd.log`; retrieve it before stopping the
listener. Keep passwords, private keys and wireless credential files out of
shared reports.

### Finish or reconnect

The console announces the first authenticated connection. During the task, the
agent should send brief, non-sensitive activity updates from its SSH connection:

```sh
daemonarchy-debug activity 'Checking Wi-Fi connectivity'
daemonarchy-debug done
```

The first command updates the local console without streaming commands or their
output. The second explicitly says that debugging is complete and it is OK to
stop the session. A short SSH command closing its connection does not mean the
overall task has finished. Completion itself leaves remote access enabled until
the operator stops the listener. Older images, including preview.13, lack this
feedback and require the agent to communicate these states directly.

Once the agent reports completion, press **Enter** or **Ctrl-C** in the local
listener console. This closes its listener and SSH connections, deletes session
host keys and approvals, and returns to the debug shell. In current development
helpers, reboot preserves an installed-system grant and its host fingerprint.
The recovery console resumes that approved listener without fresh confirmation;
its background mode accepts only previously approved keys. A stale listener can
be resumed directly without Unpair. Explicit `daemonarchy-debug unpair` revokes
both active and stale grants. Older 1.1.1 helpers used volatile approvals and
required a new pairing after reboot. Stopping access does not undo agent changes.

Run `bash tests/remote-debug-progress.sh` for portable state/command checks and
`sudo bash tests/remote-debug-session.sh` on FreeBSD for real SSH rejection,
approval, console feedback, reconnect, SFTP and stop/cleanup checks. The native
test uses an isolated temporary server on port 23451 (`DEBUG_TEST_PORT` overrides
it) and does not change the normal SSH configuration.

New installed systems expose the same commands through `daemonarchy-debug`
(`daemonarchy-debug shell`, `listen`, `resume`, or `help`). No listener starts
without prior console opt-in. A retained debugging grant resumes across reboots;
normal SSH configuration and live-USB-to-target key isolation remain separate.
`sudo bash tests/remote-debug-reboot.sh` exercises retained approval, stable host
pinning, legacy listener adoption, reused PIDs, repeated resumption and revocation
on an isolated server (default port 23452).

### Continuous diagnostics

The 1.1.1 diagnostics path provides bounded read-only `daemonarchy-debug snapshot`
and `observe` output, with private, size-limited target logs. An approved
controller can retain the stream off-target using `scripts/capture-remote-debug.py`
and its existing host-key-pinned SSH wrapper. See the [continuous diagnostics
contract](docs/remote-agent-debug.md#continuous-diagnostics) for exact commands,
retention and privacy limits. It reports when console-buffer access is unavailable;
SSH diagnostics cannot reconstruct probes from before networking or survive a
hard reset as a live connection. Loader/early-kernel network debugging remains
1.2 work; no new src debugging patches are part of 1.1.1.

### When the screen or keyboard is unusable

Use the guide's [private headless rescue procedure](docs/remote-agent-debug.md#keyboard-free-rescue-image)
to build a separate USB image with one preauthorized operator public key.
That mode uses Ethernet DHCP and a dedicated SSH server on port 2222, blocks
T2 BCE and desktop GPU autoloading, and ignores unattended installation media.
Keep the overlay and image private: they contain a rescue server private key.
The operator's private key stays on the agent's machine. This mode provides
access for diagnosis; it does not qualify blocked drivers or the desktop.

On an installed system, the loader setting `set daemonarchy_rescue=YES` followed
by `boot` skips the desktop GPU service and SDDM. Configured networking and SSH
can start first. This does not enable normal SSH if it was declined at install
time, or prevent unrelated device-driver panics.

Portable prompt/address tests are `bash tests/remote-debug-cli.sh` and
`bash tests/remote-debug-network.sh`. Native connection, approval, rejection,
custom-port, reconnect and shutdown evidence belongs in the
[remote debug validation record](docs/testing-1.1-remote-debug.md).

## Releasing

### Maintaining the release history

Update [CHANGELOG.md](CHANGELOG.md) with every release change. Keep the current
release under an explicit unreleased heading until publication; backfill missed
changes from the actual commit/tag and GitHub release history. Record concrete
behavior, source/ports or ABI migrations, validation and material limitations.
Distinguish published releases, prereleases, drafts and supporting feeds; an
approval or release commit does not establish publication. Use UTC publication
dates and link the corresponding qualification record so both humans and agents
can follow the evidence. Final publication updates the changelog, download links
and current-status documentation together.

### Packages

A compatible application fix can reach existing installations through their online repository without a new image. The unversioned publication command below is only for packages compatible with that feed's retained base. For 1.1.1 use the versioned rebuilt-dependency procedure below and leave the unversioned feed unchanged. After rebuilding the compatible packages (step 4 of the build host setup), run this from a workstation with `gh`:

```
./pkg-repo.sh publish
```

It copies `origins.sh` and itself to the build host (`BUILD_HOST`, default `freebsd.local`), and collects and signs the `OMARCHY_ORIGINS` packages there. It then replaces the assets of the `packages-16-amd64` release, uploading the packages first and the catalogue last. That release is never marked latest, so the latest release stays the ISO.

The signing key is `/usr/local/etc/daemonarchy/pkg-repo.key` on the build host. Make it once with `pkg-repo.sh keygen`, and commit the public key it prints as `overlay/usr/local/share/daemonarchy-installer/daemonarchy.pub`. Keep a copy of the private key somewhere safe. If it is lost, a new key has to be put on every installed system by hand.

### Images

Daemonarchy releases use [semantic versioning](https://semver.org), numbered on their own rather than after Omarchy's or FreeBSD's releases (the notes say which of each a release carries). The number is the daemonarchy-desktop tag that `x11-wm/daemonarchy` fetches (its `DISTVERSION`):

- **Patch** (1.0.1): fixes only.
- **Minor** (1.1.0): new features that leave existing installs working as they were.
- **Major** (2.0.0): changes an existing install cannot simply upgrade into, such as a new FreeBSD branch or a disk layout the installer no longer makes.

Package-only fixes between images bump `PORTREVISION` instead and ship through the package repository.

For a candidate, publish the signed application repository under a versioned
tag (for example, `packages-16-amd64-1.1.0-candidate`) and verify it with a native
client. Keep the default stable package feed unchanged until stable qualification
is complete. Publish the installer as a prerelease with `--latest=false`, and
retain the open hardware gates in its notes.

Build a candidate image with `PACKAGE_REPOSITORY_TAG` set to its versioned
application-feed tag (for example, `packages-16-amd64-1.1.1`). The image
records that selection and installed systems retain it as their signed
Daemonarchy feed. Omitting the variable selects the stable feed. Set
`EXPECTED_PACKAGE_REPOSITORY_TAG` to the same tag when running `test-qemu.sh`;
the installed-system check asserts the exact feed URL.

When the selected ports tip is ahead of the official binary collection, the
candidate feed must include rebuilt ordinary dependencies as well as the
Daemonarchy ports. Collect a union of the successful `.poudriere.ports.built`
records from this candidate's build/test attempts into `BUILT_PACKAGES_FILE`.
Use `pkg-repo.sh collect` on the builder with `BUILT_PACKAGES_FILE` and the
versioned `TAG` to stage public payloads without a signing key. Transfer those
payloads into an `All` directory on the protected signing host. There, use
`PACKAGES_DIR` for the staged repository, `BUILT_PACKAGES_FILE` for that list,
and the same versioned `TAG` when running `pkg-repo.sh build`. Kernel-bound packages remain on the matching ISO.
The installer uses the signed candidate feed to resolve these dependencies,
then records them under the normal Daemonarchy repository for later upgrades.
The rebuilt-dependency option refuses the unversioned stable feed.

`sudo bash tests/pkg-repo-dependencies.sh` exercises real signed repositories,
dependency resolution and subsequent upgrades in disposable pkg roots.

For an existing test installation, select the versioned candidate URL in
`/usr/local/etc/pkg/repos/Daemonarchy.conf`, then run
`sudo bash scripts/adopt-candidate-packages.sh` from this checkout. This
reinstalls already-installed feed packages from Daemonarchy, including rebuilt
dependencies that `pkg` can otherwise retain from their previous repository.
Before changing any package identities, the helper compares the actual kernel
and userland OSVERSION values with the candidate catalogue's
`FreeBSD_version` requirements. Missing or malformed requirements on native
packages are refused; architecture-independent packages may omit them. A newer
feed requires a coordinated base, kernel and driver upgrade first. This check
also applies when pkg's automatic yes or OS-version overrides are enabled:
`pkg install -y` alone accepts newer-OS packages and does not provide this guard.
After that check it assigns those public packages to Daemonarchy, then uses normal
dependency resolution so newly required official packages remain available.
Unrelated build dependencies and private-repository overrides are preserved.
The feed choice takes effect before installation; after a failed transaction,
resolve the package error and rerun the helper. Normal `pkg upgrade` follows
that one-time transition; changing the FreeBSD base/kernel remains a separate
coordinated operation.


1. Tag daemonarchy-desktop `v<version>`, set `DISTVERSION` in `x11-wm/daemonarchy` to it and run `make makesum`, then build the packages and the image as above, publish the packages, and run a test.

2. Finish required review/checks, merge and synchronize the installer source,
   then tag the exact reviewed commit. Publish a normal stable GitHub release
   `daemonarchy-<version>`, marked latest. Standard public assets are the ISO,
   its `.sha256`, `daemonarchy-<version>-boot.txz`, its detached `.sig`, and
   `daemonarchy-1.1.pem` / `.der`. Certificate filenames identify the retained
   signing authority and do not change to 1.1.1. For example:

   ```
   gh release create daemonarchy-<version> --target <exact-reviewed-commit> --latest --title "Daemonarchy <version>" --notes-file notes.md daemonarchy-<version>-amd64.iso daemonarchy-<version>-amd64.iso.sha256 daemonarchy-<version>-boot.txz daemonarchy-<version>-boot.txz.sig daemonarchy-1.1.pem daemonarchy-1.1.der
   ```

   Verify the exact uploaded asset names, sizes and SHA-256 digests. Keep
   release-specific application and checkout feeds non-latest. Operator-approved
   physical qualification deferrals must remain explicit limitations in the
   release notes; they never become passing results. For 1.1.1 retain the existing
   1.1.0 draft and leave the unversioned stable application feed unchanged.

3. Point the Download section at the top of README.md to the new release: release name, ISO and checksum links, SHA-256, and the `dd` example.
4. If the release replaces one with a serious bug, say so at the top of the old release's notes.

## Pitfalls met so far

- **Swapped-out guests panic.** A bhyve guest paged out by a host short of memory stalls long enough for its kernel's deadlock detector to panic mid-install. Wire the guest's memory, and don't overcommit the host.
- **QEMU's AVX2 emulation faults in ZFS.** With `-cpu max` under emulation, ZFS's AVX2 SHA-256 code page-faulted; use a CPU model without AVX (`-cpu Westmere`).
- **SDDM matches sessions by full path.** Omarchy's login theme has no user list; it signs in as SDDM's last user and session from `/var/lib/sddm/state.conf`. FreeBSD's SDDM needs the session as `/usr/local/share/wayland-sessions/omarchy.desktop`; a bare name falls back to plain Hyprland.
- **Sound needs the `audio` group** on FreeBSD 16.
- **pkg pads its install counter** (`[ 119/1184]`); anything parsing it must allow the space.
- **Boot code goes stale after ZFS upgrades.** A pool that gains new features (after `zpool upgrade`) needs current boot code, or the machine stops at `boot:` with "unsupported feature". Inspect `gpart show` before updating matching boot files: the 1.1 whole-disk layout uses **p4** for BIOS `freebsd-boot`, while **p1 is the EFI filesystem**. Update only the verified boot partition or project EFI loader; shared-disk installs preserve other operating-system loaders. Do not apply an old p1 BIOS recipe to this layout.
- **The snapshot directory moves.** `download.freebsd.org/snapshots/.../16.0-CURRENT` always holds the newest snapshot, but the image's sets must be the ones the jail was made from, or the kernel modules on the image will not match its kernel. The authoring cache retains those verified inputs. Select a separate `SET_CACHE_DIR` when moving snapshots, then create the matching jail and rebuild its modules. The image build refuses a different jail version or a source catalogue that does not match its kernel.
- **pkg -r resolves accounts on the running system.** Installing into `$TARGET` from the live system gave every file owned by an account a package creates (`messagebus`, `polkitd`, `cups`, `colord`) to `root:wheel`, which broke D-Bus service activation and with it polkit prompts. `fix-ownership` re-applies each package's recorded owners, groups and modes inside the target after the install.
- **pkg -r runs triggers on the running system.** The packages' triggers (`/usr/local/share/pkg/triggers`) call tools such as `glib-compile-schemas` by absolute path, which the live installer does not have, so an install was left without compiled GSettings schemas and GTK applications such as Files aborted at start. `rebuild-caches` runs them inside the target.
- **The session's PATH is GNU first.** Omarchy's commands put GNU coreutils (`libexec/omarchy/gnubin`) ahead of FreeBSD's, so a FreeBSD-only flag such as `tail -r` fails when the command runs from the desktop even though it works in a plain shell. Test Daemonarchy's commands from a desktop terminal, or avoid the flags.
- **The package mirrors disagree.** poudriere's default `pkg+http://pkg.FreeBSD.org` hands each run a random mirror, and a mirror partway through a sync gives it a partial catalogue: one run fetched 56 packages where the next fetched 1,178, and built the rest from source. Pin `PACKAGE_FETCH_URL` to `http://pkg.FreeBSD.org/${ABI}` (step 3). The mirrors can also be slow from a given host (100 to 400 KB/s here); a faster machine can download the packages and copy them into the repository's `.pkg-cache`.
- **The official set's dependency versions lag.** pkg.FreeBSD.org builds incrementally, so some of its packages record older versions of their dependencies than the set now holds (chromium recorded `dbus-glib-0.114` while the set had 0.116). poudriere then refuses or deletes them and builds them, chromium and LibreOffice included, which takes most of a day. At a matching official baseline those dependencies can be fetched. A newer integration such as 1.1.1 instead needs the incompatible dependencies rebuilt and retained in its separate versioned feed; don't silently substitute older packages or overwrite the stable feed.
- **Quoting through ssh.** Don't pass code containing apostrophes inside `ssh host '...'`: a stray quote ends the remote command early and runs the rest locally. Write the file locally and copy it with scp instead.

## Optional installed ports and source trees

See [the sizing report](docs/optional-source-sizing.md) for `/usr/ports` and
`/usr/src` archive locations, measured sizes, and installation-space allowances.
These development installer options require archives pinned to the release
ports integration and the installed FreeBSD snapshot.

### Secure Boot development

Secure Boot development is documented separately in
[`secureboot/README.md`](secureboot/README.md), with the
[manual-enrollment contract](docs/secure-boot.md) and
[native development evidence](docs/testing-1.1-secureboot.md). Stable 1.0.1 and preview.1 do not implement that production path; the 1.1
candidate integrates it using public signed artifacts. Its private signing key must stay
off build payloads and public images.

The integration build accepts **public artifacts only**:

```sh
sudo env SECUREBOOT_BUNDLE=/path/to/signed-boot.txz \
  SECUREBOOT_SIGNATURE=/path/to/signed-boot.txz.sig \
  SECUREBOOT_CERTIFICATE=/path/to/public-certificate.pem \
  ./build-iso.sh
```

Prepare and sign those artifacts using the separate boot-tree workflow in
`secureboot/README.md`. The signing key is not an input to `build-iso.sh` and
must stay on its protected signing host. Keep disposable development keys and
images private; only the production public certificate belongs in a release.
The post-build hook validates the archive, stock kernel and actual live boot
files before ISO creation. The installer repeats validation before partition
writes, installs the profile after the base/rescue setup, and checks the target
again after package installation. It preserves other EFI loaders and never
changes firmware PK, KEK, db or dbx.

With the payload present, firmware-enforced UEFI selects the verified kernel;
UEFI with enforcement off and BIOS use the stock kernel. The signed EFI loader
also follows the installed pool's active boot environment through its numeric
GUID. Builds without this payload retain the older loader/explicit dataset
selection and cannot qualify Secure Boot. Packages owning boot modules are
locked to the signed inventory; ordinary applications remain upgradeable.

For an installed verified profile, same-snapshot maintenance is explicit:

```sh
sudo daemonarchy-secureboot stage update.txz --signature update.txz.sig \
  --certificate /usr/local/share/daemonarchy-secureboot/certificate.pem \
  --environment update-1.1-test
sudo daemonarchy-secureboot activate update.txz --signature update.txz.sig \
  --certificate /usr/local/share/daemonarchy-secureboot/certificate.pem \
  --environment update-1.1-test
```

Staging never activates or reboots. Activation rechecks the candidate, then
selects it for the next manual reboot; the previous environment is retained.
A failed stage stays unactivated and is retained for diagnosis. Changing a
driver needs the matching signed inventory and native package in that candidate;
do not overwrite pkg-owned driver files or unlock them in the running profile.
Base/ABI transitions, certificate rotation and an EFI loader-protocol change
need a separately qualified migration. The [1.1 record](docs/testing-1.1-upgrade.md)
contains native same-snapshot maintenance evidence; the [1.1.1 record](docs/testing-1.1.1.md)
tracks the new snapshot separately. Preview.13 lacks these integration commands.

For enforced QEMU installation tests, use separate fresh work directories and
persistent variables cloned from an already enrolled disposable template:

```sh
BOOT_MODE=uefi UEFI_SECUREBOOT=true \
  UEFI_CODE=/path/to/OVMF_CODE_4M.secboot.fd \
  UEFI_VARS_TEMPLATE=/path/to/enrolled-test-vars.fd \
  WORK=/path/to/fresh-test SSH_PORT=22461 sh test-qemu.sh private-test.iso
```

The harness keeps one private variable store across installation and reboot,
then checks real firmware state, verified kernel selection and locked policy.
Add `ENCRYPT_INSTALLATION=true` for GELI. For actual graphical checks, set
`VIRGL_RENDER_NODE=/dev/dri/renderD128`, an unused loopback `VNC_LISTEN`, and
`POST_INSTALL_CHECK="$PWD/tests/qemu-desktop.py"` on a qualified Linux/VirGL
worker; the callback performs password login (or encrypted-install autologin),
keyboard and pointer input, retaining screenshots and a JSON receipt. Services
running over SSH alone do not qualify graphics. `MEM=8G` can give that guest
more memory. Native firmware/graphics test results must still be recorded.

### Building live checkout packages

The optional trees are **depth-1 shallow Git checkouts**, not full repository
history. They include `.git`, the release revision and a configured HTTPS remote.
Users can fetch changes, deepen history and commit. Package files own only seed
archives in `/usr/local/share/daemonarchy/checkouts`; the working trees in
`/usr/ports` and `/usr/src` are independent, so package removal cannot delete work.

On the FreeBSD build worker, run `scripts/build-checkout-packages.py` for each
release input. Use the image's integrated ports revision and the source revision
printed in the selected kernel's build identity:

```sh
python3 scripts/build-checkout-packages.py --kind ports \
  --repo /usr/local/poudriere/ports/omarchyiso --revision <ports-commit> \
  --branch daemonarchy-1.1.1 --remote https://github.com/jordanhubbard/freebsd-ports.git \
  --out /path/to/checkout-repo
python3 scripts/build-checkout-packages.py --kind src \
  --repo /usr/src --revision <kernel-source-commit> \
  --branch main --remote https://github.com/freebsd/freebsd-src.git \
  --out /path/to/checkout-repo
python3 scripts/make-checkout-catalog.py /path/to/checkout-repo \
  --url https://github.com/jordanhubbard/daemonarchy/releases/download/<checkout-tag> \
  --ports-tracking-branch daemonarchy-1.1.1 \
  > /path/to/checkout-repo/checkouts.json
sudo pkg repo /path/to/checkout-repo /usr/local/etc/daemonarchy/pkg-repo.key
```

`--depth` defaults to 1. The 1.1.1 package integration is on the fork's
`daemonarchy-1.1.1` branch; older 1.1 images retain their pinned
`daemonarchy-1.1-package-baseline` catalogue and feed. Default fetches are restricted to one branch. Payloads are split into 512 MiB parts before packaging,
keeping each asset below 2 GiB. Publish the signed repository at a dedicated,
release-specific tag, packages first and catalogues last. Retain that tag for
older installations. Pass `CHECKOUT_CATALOG=/path/to/checkout-repo/checkouts.json`
to `build-iso.sh`; it rejects sources that do not match the selected kernel.
The checkout packages are downloaded when selected and do not enlarge the ISO.

The installer offers each tree separately. Unattended installs default both off;
set `install_ports=true` and/or `install_src=true` to enable them. Selections
increase the required disk/partition size by the measured peak-space allowance.
The checkout is owned by the new user. Later, install either tree with:

```sh
sudo daemonarchy-checkouts ports "$USER"
sudo daemonarchy-checkouts src "$USER"
```

The command refuses nonempty destinations and verifies payload checksums. It
also refuses to install source from a catalogue for a different kernel snapshot.
Seed packages and pkg's download cache can be removed after successful creation;
the command lists the seed package names. Build dependencies, distfiles and
compiler outputs still need additional disk space.

Run `sudo bash tests/checkout-packages.sh` on FreeBSD for the native package
round trip, shallow/deepen/commit checks, edit preservation and corruption
rejection. `bash tests/checkout-options.sh` checks selection and capacity policy.
