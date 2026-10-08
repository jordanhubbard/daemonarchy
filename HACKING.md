# Hacking on Daemonarchy

How to build a Daemonarchy image yourself, change the installer, the ports, or the artwork, and test and release the result. [README.md](README.md) says what Daemonarchy is; this is for working on it.

## Where things live

Daemonarchy is two repositories:

- **This one** builds the installer image:
  - `overlay/usr/local/libexec/daemonarchy-installer/`: the installer. `launch` runs from root's login on the live system; `configurator` asks the questions (it vendors Omarchy's own setup form); `install` partitions, installs, and configures; `dashboard` draws the install screen from the install log.
  - `overlay/usr/local/share/daemonarchy-installer/`: the installer's logo, the loader brand, and the keymap table.
  - `origins.sh`: the ports whose packages Daemonarchy publishes itself, rather than taking them from pkg.FreeBSD.org.
  - `build-iso.sh`: collects the package repository and builds the hybrid ISO with `poudriere image`.
  - `pkg-repo.sh`: publishes the signed online package repository that installed systems update from (see Releasing).
  - `live-post.sh`: turns the plain FreeBSD image into the live installer (console autologin, memory-backed `/var`, loader brand).
  - `test-bhyve.sh` and `test-qemu.sh`: unattended install tests.
- **[jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy)**, the `omarchy` branch, carries the ports:
  - `x11-wm/omarchy`: Omarchy itself, kept as Omarchy ships it apart from FreeBSD compatibility. `files/compat/` has stand-ins for the systemd and Linux tools Omarchy calls (`systemctl`, `uwsm`, `journalctl`, `timedatectl`, `brightnessctl`, ...); `files/freebsd-bin/` has FreeBSD versions of commands built on pacman, `/sys`, or NetworkManager; `files/seed-user` copies Omarchy's defaults into a home on the first session (Arch does this from `/etc/skel`).
  - `x11-wm/daemonarchy`: the full desktop's dependencies, plus Daemonarchy's own look: `files/wallpaper.svg`, `files/wordmark.svg` (the login screen's logo), `files/mark.svg` (the horned "A"), `files/screensaver.txt`, `files/about.txt`, and an SDDM theme that reuses Omarchy's with the Daemonarchy wordmark. Defaults for new users go to `share/omarchy/skel.d/daemonarchy`, which `seed-user` copies in ahead of Omarchy's.
  - The applications and tools Omarchy uses, one port each (`x11-themes/aether`, `graphics/tensaku`, `misc/ttfx`, ...), submitted upstream in [freebsd/freebsd-ports#630](https://github.com/freebsd/freebsd-ports/pull/630); `x11-wm/omarchy` and `x11-wm/daemonarchy` are in [#635](https://github.com/freebsd/freebsd-ports/pull/635).
  - `x11/quickshell`, carrying a fix for a use-after-free in its Hyprland IPC ([#634](https://github.com/freebsd/freebsd-ports/pull/634)).

## Working on Daemonarchy from Daemonarchy

A Daemonarchy machine can be its own development machine, much as Omarchy's repo mode works on Arch.

`daemonarchy-dev-setup` (also System > FreeBSD > Hack on Daemonarchy) clones the three trees into `~/src`: Omarchy at the installed version on a `daemonarchy-dev` branch, the ports tree with the Omarchy ports, and this repository. It then offers to link the desktop to the Omarchy checkout.

### Omarchy from a checkout

`omarchy dev link ~/src/omarchy` runs the desktop from your checkout after a reboot. A checkout of Omarchy is Arch-flavored, so on FreeBSD it is not run directly: the omarchy port's `freebsdize` builds the same FreeBSD tree the port installs (applying the port's patches, adding the FreeBSD versions of commands, rewriting paths and interpreters) into `~/.local/share/omarchy-dev`, and `OMARCHY_PATH` points there. While an Omarchy session runs, `omarchy dev sync --watch` rebuilds that tree a moment after each save; `omarchy dev sync` does it by hand. `omarchy dev unlink` goes back to the installed Omarchy.

The link also points sudo at the tree's commands (a `secure_path` in `/usr/local/etc/sudoers.d/omarchy-dev-path` that keeps FreeBSD's `/sbin`, `/bin`, and `/usr/sbin`).

If one of the port's patches stops applying to your checkout (you moved past the version the port packages), `omarchy dev link` and `sync` say so; refresh the patch in `~/src/freebsd-ports/x11-wm/omarchy/files`.

### Ports from the ports tree

Rebuild and install a port from `~/src/freebsd-ports` with `sudo make reinstall clean` in its directory: `x11-wm/omarchy` for Omarchy's FreeBSD layer (compat tools, FreeBSD commands, `freebsdize`), `x11-wm/daemonarchy` for Daemonarchy's own look and the System > FreeBSD tools.

## Setting up a build host

You need a FreeBSD 16.0-CURRENT machine (bare metal or a VM with about 8 GB of memory and 100 GB of disk) with poudriere, git, and the ports tree, as root.

1. **A jail from the snapshot the image installs.** poudriere's `url` method fetches no kernel, and the image needs one, so add it:

   ```
   poudriere jail -c -j 16amd64 -a amd64 -v 16.0-CURRENT -m url=https://download.freebsd.org/snapshots/amd64/16.0-CURRENT/
   fetch -o - https://download.freebsd.org/snapshots/amd64/16.0-CURRENT/kernel.txz | tar -xJf - -C /usr/local/poudriere/jails/16amd64
   ```

2. **A ports tree pinned to the official package set.** The installer takes most packages from pkg.FreeBSD.org's `latest` set, so the Omarchy ports must be built against the same ports commit. That commit is the newest `ports_top_git_hash` annotation across the set's packages. Builds are incremental, so one package's annotation can be older than the set:

   ```
   mkdir -p /tmp/pq/db /tmp/pq/repos
   printf 'FreeBSD: { url: "pkg+https://pkg.FreeBSD.org/FreeBSD:16:amd64/latest", mirror_type: "srv", signature_type: "fingerprints", fingerprints: "/usr/share/keys/pkg", enabled: yes }\n' >/tmp/pq/repos/FreeBSD.conf
   P="pkg -o PKG_DBDIR=/tmp/pq/db -o REPOS_DIR=/tmp/pq/repos -o ABI=FreeBSD:16:amd64 -o OSVERSION=1600026"
   $P update -q
   $P rquery -a '%At=%Av' | sed -n 's/^ports_top_git_hash=//p' | sort -u
   ```

   Check out the newest of those commits, cherry-pick the `omarchy` branch's commits onto it, and register it with poudriere:

   ```
   git clone https://github.com/freebsd/freebsd-ports.git /usr/local/poudriere/ports/omarchyiso
   cd /usr/local/poudriere/ports/omarchyiso
   git checkout -b omarchy-iso <commit>
   git fetch https://github.com/jordanhubbard/freebsd-ports.git omarchy
   git cherry-pick <first-omarchy-commit>^..FETCH_HEAD   # the omarchy branch's own commits
   poudriere ports -c -p omarchyiso -m null -M /usr/local/poudriere/ports/omarchyiso
   ```

3. **poudriere settings** (`/usr/local/etc/poudriere.d/omarchyiso-poudriere.conf`): build the kernel modules for the jail's kernel instead of fetching the package builders' copies, which target a different kernel:

   ```
   PACKAGE_FETCH_BLACKLIST="drm-*-kmod gpu-firmware-* wifi-firmware-*"
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
- Bump `PORTREVISION` whenever a package's contents change: poudriere rebuilds on version changes, not on file changes, so an unbumped port keeps its old package.
- Commit each change on the `omarchy` branch, cherry-pick it onto the ISO tree, and rebuild the packages (step 4 above).

### The artwork

The wallpaper, wordmark, and mark are SVG in `x11-wm/daemonarchy/files/`; the port renders the wallpaper to a 3840x2160 JPEG and the wordmark to the login screen's PNG with `rsvg-convert` at build time. Preview an edit with `rsvg-convert -w 1920 wallpaper.svg -o preview.png`. `about.txt` (the About screen's art) was made from `mark.svg` with Omarchy's own `omarchy-transcode-ascii`, and `screensaver.txt` is the same wordmark the installer shows.

Daemonarchy's artwork is original: keep the FreeBSD and Arch Linux logos out of it, and keep Daemonarchy's identity in the `daemonarchy` port rather than in Omarchy's files.

## Testing

A VM cannot run the desktop (Hyprland needs a DRM driver), so the tests install unattended and then check the installed system: the account and its `wheel`, `operator`, `video`, and `audio` groups, SDDM's user, session, and theme, sshd, Avahi, mDNS lookups, DHCP, and the Daemonarchy defaults.

- **`test-bhyve.sh <iso>`** on a FreeBSD host with VT-x or AMD-V, as root, with `edk2-bhyve` installed. It reads the installed disk directly after the install. `NET=nat` (the default, with pf and dnsmasq) or `NET=bridge` (onto the host's network, using the LAN's DHCP); `test-bhyve.sh --cleanup` undoes either. The guest's memory is wired (`MEM`, default 3G) so a busy host cannot swap it out: leave the host at least that much free, or lower `MEM`.
- **`test-qemu.sh <iso>`** anywhere QEMU runs, without root: it logs in over SSH and checks from inside. On a non-x86 host the guest is emulated, and an install takes two to three hours.

Both send the installer's log to the guest's serial port, so a stalled install leaves a trail.

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

Daemonarchy releases use [semantic versioning](https://semver.org), numbered on their own rather than after Omarchy's or FreeBSD's releases (the notes say which of each a release carries). The number is `PORTVERSION` in `x11-wm/daemonarchy`:

- **Patch** (1.0.1): fixes only.
- **Minor** (1.1.0): new features that leave existing installs working as they were.
- **Major** (2.0.0): changes an existing install cannot simply upgrade into, such as a new FreeBSD branch or a disk layout the installer no longer makes.

Package-only fixes between images bump `PORTREVISION` instead and ship through the package repository.

1. Set the version in `x11-wm/daemonarchy`, build the packages and the image as above, publish the packages, and run a test.
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
- **Quoting through ssh.** Don't pass code containing apostrophes inside `ssh host '...'`: a stray quote ends the remote command early and runs the rest locally. Write the file locally and copy it with scp instead.
