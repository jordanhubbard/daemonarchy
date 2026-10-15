# Hacking on Daemonarchy

How to build a Daemonarchy image yourself, change the installer, the ports, or the artwork, and test and release the result. [README.md](README.md) says what Daemonarchy is; this is for working on it.

## Where things live

Daemonarchy is four repositories:

- **This one** builds the installer image:
  - `overlay/usr/local/libexec/daemonarchy-installer/`: the installer. `launch` runs from root's login on the live system; `configurator` asks the questions (it vendors Omarchy's own setup form); `install` partitions, installs, and configures; `dashboard` draws the install screen from the install log.
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
  - `freebsdize.in`: the adaptation of Omarchy's sources, run by the port and by `omarchy dev link`.
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
- **[jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy)**, the `omarchy` branch, is the release ports fork. Upstream review does not block releases from this fork. It carries the ports:
  - `x11-wm/omarchy`: Omarchy itself, with omarchy-freebsd as a second distfile. Its `files/` holds only patches to Omarchy's own files, among them the ones that add the `FreeBSDWifi.qml` and `FreeBSDBluetooth.qml` stand-ins to the panels.
  - `x11-wm/daemonarchy`: the full desktop's dependencies, plus daemonarchy-desktop. Defaults for new users go to `share/omarchy/skel.d/daemonarchy`, which `seed-user` copies in ahead of Omarchy's.
  - The applications and tools Omarchy uses, one port each (`x11-themes/aether`, `graphics/tensaku`, `misc/ttfx`, ...), submitted upstream in [freebsd/freebsd-ports#630](https://github.com/freebsd/freebsd-ports/pull/630); `x11-wm/omarchy` and `x11-wm/daemonarchy` are in [#635](https://github.com/freebsd/freebsd-ports/pull/635).
  - `x11/quickshell` carries a fix for a use-after-free in its Hyprland IPC, which is now committed upstream ([#634](https://github.com/freebsd/freebsd-ports/pull/634)).

## Working on Daemonarchy from Daemonarchy

A Daemonarchy machine can be its own development machine, much as Omarchy's repo mode works on Arch.

`daemonarchy-dev-setup` (also System > FreeBSD > Hack on Daemonarchy) clones the trees into `~/src`: Omarchy at the installed version on a `daemonarchy-dev` branch, omarchy-freebsd, daemonarchy-desktop, this repository, and the ports tree with the Omarchy ports. It then offers to link the desktop to the Omarchy checkout.

### Omarchy from a checkout

`omarchy dev link ~/src/omarchy` runs the desktop from your checkout after a reboot. A checkout of Omarchy is Arch-flavored, so on FreeBSD it is not run directly: the omarchy port's `freebsdize` builds the same FreeBSD tree the port installs (applying the port's patches, adding the FreeBSD versions of commands, rewriting paths and interpreters) into `~/.local/share/omarchy-dev`, and `OMARCHY_PATH` points there. While an Omarchy session runs, `omarchy dev sync --watch` rebuilds that tree a moment after each save; `omarchy dev sync` does it by hand. `omarchy dev unlink` goes back to the installed Omarchy.

The link also points sudo at the tree's commands (a `secure_path` in `/usr/local/etc/sudoers.d/omarchy-dev-path` that keeps FreeBSD's `/sbin`, `/bin`, and `/usr/sbin`).

If one of the port's patches stops applying to your checkout (you moved past the version the port packages), `omarchy dev link` and `sync` say so; refresh the patch in `~/src/freebsd-ports/x11-wm/omarchy/files`.

### The FreeBSD layer and the desktop layer

The ports fetch omarchy-freebsd and daemonarchy-desktop as tagged releases. To try your own checkout instead, let the port extract its sources, lay the checkout over them, and let it carry on:

```
cd ~/src/freebsd-ports/x11-wm/omarchy        # or x11-wm/daemonarchy
make extract
rsync -a --exclude .git ~/src/omarchy-freebsd/ "$(make -V WRKSRC_freebsd)/"
#   for daemonarchy: rsync -a --exclude .git ~/src/daemonarchy-desktop/ "$(make -V WRKSRC)/"
sudo make reinstall clean
```

`omarchy dev link` takes the FreeBSD commands and `freebsdize` from the installed port, so reinstall the omarchy port this way before linking to try changes to them.

## Setting up a build host

You need a FreeBSD 16.0-CURRENT machine (bare metal or a VM with about 8 GB of memory and 100 GB of disk) with poudriere, git, and the ports tree, as root.

1. **A jail from the snapshot the image installs.** Before the next release, re-sync system sources with [FreeBSD CURRENT (`main`)](https://github.com/freebsd/freebsd-src/tree/main), select the image snapshot, and record its exact source revision. `/usr/src` offered by the installer must match that snapshot; do not fetch a moving branch at install time. Recreate/update the build jail and rebuild the selected kernel modules when moving snapshots. Poudriere's `url` method fetches no kernel, and the image needs one, so add it:

   ```
   poudriere jail -c -j 16amd64 -a amd64 -v 16.0-CURRENT -m url=https://download.freebsd.org/snapshots/amd64/16.0-CURRENT/
   fetch -o - https://download.freebsd.org/snapshots/amd64/16.0-CURRENT/kernel.txz | tar -xJf - -C /usr/local/poudriere/jails/16amd64
   ```

2. **A ports tree pinned to the official package set.** Before the next release, refresh [the fork's `omarchy` branch](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy) from [upstream FreeBSD ports](https://github.com/freebsd/freebsd-ports), preserving and testing the Daemonarchy changes. The installer takes most packages from pkg.FreeBSD.org's `latest` set, so the Omarchy ports must be built against the same ports commit. That commit is the newest `ports_top_git_hash` annotation across the set's packages. Builds are incremental, so one package's annotation can be older than the set:

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
   ```

4. **Build the packages.** List the origins in `ISO_ORIGINS` at the top of `build-iso.sh` in a file, and bulk-build with `-b latest`, so every other dependency is fetched as the official binary:

   ```
   poudriere bulk -j 16amd64 -p omarchyiso -b latest -t -f omarchyiso-ports.list
   ```

   The first build takes a few hours, mostly the GPU modules and anything not in the official set. Rebuilds take minutes.

5. **Build the image:**

   ```
   ./build-iso.sh
   ```

   The image is named after the version of the `daemonarchy` package it carries: `daemonarchy-<version>-<arch>.iso`, for example `daemonarchy-1.0.0-amd64.iso`. Set `NAME` to override.

   The image and its `.sha256` land in `/usr/local/poudriere/data/images`.

   For development images, set `NAME` to a distinct preview filename and
   `PREVIEW_LABEL` to a short description. The installer welcome screen shows
   that label alongside the actual desktop package version.

## Changing things

### The installer

The installer is plain bash and lives entirely in `overlay/`, so changing it only needs a new image (`./build-iso.sh`, about 20 minutes); the packages stay as they are.

- **The install screen** can be tried without an install: `dashboard` draws from a log file, so feed it one. Run it in a 160x50 terminal (the console's size) with `ISO_SHARE` pointing at a directory holding `logo.txt`, and append `@@phase <name>` lines, `Number of packages to be fetched: N`, `Fetching <pkg>: ... done`, and `[ n/N] Installing <pkg>...` lines to the log; it exits with the number written to the status file.
- **`install`** reads its answers from `$DAEMONARCHY_INSTALL_CONF`; the keys are what `configurator`'s `write_install_conf` writes. An unattended install takes the same file from a FAT drive labelled `CIDATA`, which is how both test scripts run.
- **`configurator`** sources Omarchy's setup form from the `omarchy` package at build time (`build-iso.sh` extracts it), so the account, hostname, and timezone questions follow Omarchy's.

### The ports

Work in a checkout of the fork's `omarchy` branch (the build host's `/usr/ports` works well).

- `poudriere testport -j 16amd64 -p <tree> -o <origin>` checks a port in a clean jail: stage-qa, the plist, install, and deinstall. Use it rather than `make stage-qa` as root on the host, which installs the port's dependencies onto the host.
- To try a change on a running Daemonarchy desktop, `make reinstall` the port there; `seed-user --force` re-copies the defaults into the home (it never overwrites a file you have).
- A change to omarchy-freebsd or daemonarchy-desktop ships as a new tag there: tag it, set the tag in the port (`GH_TUPLE` in `x11-wm/omarchy`, `DISTVERSION` in `x11-wm/daemonarchy`), and run `make makesum`.
- Bump `PORTREVISION` whenever a package's contents change: poudriere rebuilds on version changes, not on file changes, so an unbumped port keeps its old package.
- Commit each change on the `omarchy` branch, cherry-pick it onto the ISO tree, and rebuild the packages (step 4 above).

### The artwork

The wallpaper, wordmark, and mark are SVG in daemonarchy-desktop; the `x11-wm/daemonarchy` port renders the wallpaper to a 3840x2160 JPEG and the wordmark to the login screen's PNG with `rsvg-convert` at build time. Preview an edit with `rsvg-convert -w 1920 wallpaper.svg -o preview.png`. `about.txt` (the About screen's art) was made from `mark.svg` with Omarchy's own `omarchy-transcode-ascii`, and `screensaver.txt` is the same wordmark the installer shows.

Daemonarchy's artwork is original: keep the FreeBSD and Arch Linux logos out of it, and keep Daemonarchy's identity in daemonarchy-desktop rather than in Omarchy's files or omarchy-freebsd.

## Testing

A VM cannot run the desktop (Hyprland needs a DRM driver), so the tests install unattended and then check the installed system: the account and its `wheel`, `operator`, `video`, and `audio` groups, SDDM's user, session, and theme, sshd, Avahi, mDNS lookups, DHCP, and the Daemonarchy defaults.

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

## Releasing

### Packages

A fix to a port reaches installed systems through the online repository; no new image is needed. After rebuilding the packages (step 4 of the build host setup), run this from a workstation with `gh`:

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

1. Tag daemonarchy-desktop `v<version>`, set `DISTVERSION` in `x11-wm/daemonarchy` to it and run `make makesum`, then build the packages and the image as above, publish the packages, and run a test.
2. Publish the image and its `.sha256` as a GitHub release tagged `daemonarchy-<version>`, marked as the latest:

   ```
   gh release create daemonarchy-<version> --latest --title "Daemonarchy <version>" --notes-file notes.md daemonarchy-<version>-amd64.iso daemonarchy-<version>-amd64.iso.sha256
   ```

3. Point the Download section at the top of README.md to the new release: release name, ISO and checksum links, SHA-256, and the `dd` example.
4. If the release replaces one with a serious bug, say so at the top of the old release's notes.

## Pitfalls met so far

- **Swapped-out guests panic.** A bhyve guest paged out by a host short of memory stalls long enough for its kernel's deadlock detector to panic mid-install. Wire the guest's memory, and don't overcommit the host.
- **QEMU's AVX2 emulation faults in ZFS.** With `-cpu max` under emulation, ZFS's AVX2 SHA-256 code page-faulted; use a CPU model without AVX (`-cpu Westmere`).
- **SDDM matches sessions by full path.** Omarchy's login theme has no user list; it signs in as SDDM's last user and session from `/var/lib/sddm/state.conf`. FreeBSD's SDDM needs the session as `/usr/local/share/wayland-sessions/omarchy.desktop`; a bare name falls back to plain Hyprland.
- **Sound needs the `audio` group** on FreeBSD 16.
- **pkg pads its install counter** (`[ 119/1184]`); anything parsing it must allow the space.
- **Boot code goes stale after ZFS upgrades.** A pool that gains new features (after `zpool upgrade`) needs current boot code, or the machine stops at `boot:` with "unsupported feature". Run `gpart bootcode -p /boot/gptzfsboot -i 1 <disk>` (or the EFI loader update) after upgrading a pool.
- **The snapshot directory moves.** `download.freebsd.org/snapshots/.../16.0-CURRENT` always holds the newest snapshot, but the image's sets must be the one the jail was made from, or the kernel modules on the image will not match its kernel. `build-iso.sh` keeps the sets it fetched in `/var/cache/daemonarchy-iso` and refuses sets whose `__FreeBSD_version` differs from the jail's. Empty that directory only after moving the jail to a new snapshot and rebuilding the packages.
- **pkg -r resolves accounts on the running system.** Installing into `$TARGET` from the live system gave every file owned by an account a package creates (`messagebus`, `polkitd`, `cups`, `colord`) to `root:wheel`, which broke D-Bus service activation and with it polkit prompts. `fix-ownership` re-applies each package's recorded owners, groups and modes inside the target after the install.
- **pkg -r runs triggers on the running system.** The packages' triggers (`/usr/local/share/pkg/triggers`) call tools such as `glib-compile-schemas` by absolute path, which the live installer does not have, so an install was left without compiled GSettings schemas and GTK applications such as Files aborted at start. `rebuild-caches` runs them inside the target.
- **The session's PATH is GNU first.** Omarchy's commands put GNU coreutils (`libexec/omarchy/gnubin`) ahead of FreeBSD's, so a FreeBSD-only flag such as `tail -r` fails when the command runs from the desktop even though it works in a plain shell. Test Daemonarchy's commands from a desktop terminal, or avoid the flags.
- **The package mirrors disagree.** poudriere's default `pkg+http://pkg.FreeBSD.org` hands each run a random mirror, and a mirror partway through a sync gives it a partial catalogue: one run fetched 56 packages where the next fetched 1,178, and built the rest from source. Pin `PACKAGE_FETCH_URL` to `http://pkg.FreeBSD.org/${ABI}` (step 3). The mirrors can also be slow from a given host (100 to 400 KB/s here); a faster machine can download the packages and copy them into the repository's `.pkg-cache`.
- **The official set's dependency versions lag.** pkg.FreeBSD.org builds incrementally, so some of its packages record older versions of their dependencies than the set now holds (chromium recorded `dbus-glib-0.114` while the set had 0.116). poudriere then refuses or deletes them and builds them, chromium and LibreOffice included, which takes most of a day. Only the ISO's own ports need building here; the others come from pkg.FreeBSD.org at install time.
- **Quoting through ssh.** Don't pass code containing apostrophes inside `ssh host '...'`: a stray quote ends the remote command early and runs the rest locally. Write the file locally and copy it with scp instead.

## Optional installed ports and source trees

See [the sizing report](docs/optional-source-sizing.md) for `/usr/ports` and
`/usr/src` archive locations, measured sizes, and installation-space allowances.
These development installer options require archives pinned to the release
ports integration and the installed FreeBSD snapshot.

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
  --branch omarchy --remote https://github.com/jordanhubbard/freebsd-ports.git \
  --out /path/to/checkout-repo
python3 scripts/build-checkout-packages.py --kind src \
  --repo /usr/src --revision <kernel-source-commit> \
  --branch main --remote https://github.com/freebsd/freebsd-src.git \
  --out /path/to/checkout-repo
python3 scripts/make-checkout-catalog.py /path/to/checkout-repo \
  --url https://github.com/jordanhubbard/daemonarchy/releases/download/<checkout-tag> \
  --ports-tracking-branch daemonarchy-1.1-iso \
  > /path/to/checkout-repo/checkouts.json
sudo pkg repo /path/to/checkout-repo /usr/local/etc/daemonarchy/pkg-repo.key
```

`--depth` defaults to 1. The current image integration is published on the fork's
`daemonarchy-1.1-iso` branch; the local ports branch is named `omarchy` and tracks
that integration branch. Default fetches are restricted to one branch. Payloads are split into 512 MiB parts before packaging,
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
