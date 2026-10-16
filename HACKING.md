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
- **[jordanhubbard/freebsd-ports](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy)**, the `omarchy` branch, is the release ports fork. Upstream review does not block releases from this fork. It carries the ports:
  - `x11-wm/omarchy`: Omarchy itself, with omarchy-freebsd as a second distfile. Its `files/` holds only patches to Omarchy's own files, among them the ones that add the `FreeBSDWifi.qml` and `FreeBSDBluetooth.qml` stand-ins to the panels.
  - `x11-wm/daemonarchy`: the full desktop's dependencies, plus daemonarchy-desktop. Defaults for new users go to `share/omarchy/skel.d/daemonarchy`, which `seed-user` copies in ahead of Omarchy's.
  - The applications and tools Omarchy uses, one port each (`x11-themes/aether`, `graphics/tensaku`, `misc/ttfx`, ...), submitted upstream in [freebsd/freebsd-ports#630](https://github.com/freebsd/freebsd-ports/pull/630); `x11-wm/omarchy` and `x11-wm/daemonarchy` are in [#635](https://github.com/freebsd/freebsd-ports/pull/635).
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

## Setting up a build host

You need a FreeBSD 16.0-CURRENT machine (bare metal or a VM with about 8 GB of memory and 100 GB of disk) with poudriere, git, and the ports tree, as root.

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

2. **A ports tree pinned to the official package set.** Before the next release, refresh [the fork's `omarchy` branch](https://github.com/jordanhubbard/freebsd-ports/tree/omarchy) from [upstream FreeBSD ports](https://github.com/freebsd/freebsd-ports), preserving and testing the Daemonarchy changes. For the 1.1 integration, use `daemonarchy-1.1-package-baseline` and the exact revision recorded in [ROADMAP.md](ROADMAP.md). Its upstream baseline matches the published binaries; merging the moving `omarchy` or upstream HEAD into it can invalidate that match. The installer takes most packages from pkg.FreeBSD.org's `latest` set, so the Omarchy ports must be built against the same ports commit. That commit is the newest `ports_top_git_hash` annotation across the set's packages. Builds are incremental, so one package's annotation can be older than the set:

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
export SET_CACHE_DIR=/build-cache/daemonarchy/sets/3ceb5f150bc1
export SNAPSHOT_URL=https://download.freebsd.org/snapshots/amd64/16.0-CURRENT
sh scripts/cache-release-sets.sh
# Create the jail from "$SET_CACHE_DIR/base.txz" and extract its kernel/lib32.
JAIL=16amd64 PTREE=omarchyiso sh build-iso.sh
```

The moving snapshot URL is consulted only for missing inputs. Select a new
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

The installer offers CUDA and cudalab only when the detected display GPU is
supported by the image's NVIDIA driver table (including mixed-GPU machines).
The option defaults to Skip; unattended installs must set `install_cuda=true`
to select it. Unsupported hardware and invalid values are rejected before disk
writes. Desktop driver installation does not depend on this option.

Selecting it reserves an additional 16 GiB in the disk-space checks, downloads
the CUDA toolkit into the target's Linuxulator, and clones/builds cudalab for
the new user without opening a graphical session. The launcher and menu entry
are included only when selected. Linuxulator mounts are released before the
target pool is exported, including on failure. The allowance is a budget, not
a measured download size; the toolkit and build dependencies need internet.

`bash tests/cuda-options.sh` covers hardware gating, opt-in/default behavior,
space allowance, launcher/menu inclusion, and mount cleanup. Run
`bash tests/linux-cuda.sh` for toolkit policy and the headless build script.
These portable tests do not replace an installation and desktop launch on
supported NVIDIA hardware.

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
`/var/run/daemonarchy-remote-debug/sshd.log`; retrieve it before stopping the
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
host keys and approvals, and returns to the debug shell. Rebooting also clears
them. A new listener session requires pairing again. Stopping access does not
undo changes already made by the agent.

Run `bash tests/remote-debug-progress.sh` for portable state/command checks and
`sudo bash tests/remote-debug-session.sh` on FreeBSD for real SSH rejection,
approval, console feedback, reconnect, SFTP and stop/cleanup checks. The native
test uses an isolated temporary server on port 23451 (`DEBUG_TEST_PORT` overrides
it) and does not change the normal SSH configuration.

New installed systems expose the same commands through `daemonarchy-debug`
(`daemonarchy-debug shell`, `listen`, or `help`). No debug listener starts
automatically, and temporary pairing does not enable the normal SSH service or
copy approved keys into the installed system.

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
- **The snapshot directory moves.** `download.freebsd.org/snapshots/.../16.0-CURRENT` always holds the newest snapshot, but the image's sets must be the ones the jail was made from, or the kernel modules on the image will not match its kernel. The authoring cache retains those verified inputs. Select a separate `SET_CACHE_DIR` when moving snapshots, then create the matching jail and rebuild its modules. The image build refuses a different jail version or a source catalogue that does not match its kernel.
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

### Secure Boot development

Secure Boot development is documented separately in
[`secureboot/README.md`](secureboot/README.md), with the
[manual-enrollment contract](docs/secure-boot.md) and
[native development evidence](docs/testing-1.1-secureboot.md). Current published
images do not implement that production path. Its private signing key must stay
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
need a separately qualified migration. These integration commands are still
under native installation/update qualification; they are not in preview.13.

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
  --branch daemonarchy-1.1-package-baseline --remote https://github.com/jordanhubbard/freebsd-ports.git \
  --out /path/to/checkout-repo
python3 scripts/build-checkout-packages.py --kind src \
  --repo /usr/src --revision <kernel-source-commit> \
  --branch main --remote https://github.com/freebsd/freebsd-src.git \
  --out /path/to/checkout-repo
python3 scripts/make-checkout-catalog.py /path/to/checkout-repo \
  --url https://github.com/jordanhubbard/daemonarchy/releases/download/<checkout-tag> \
  --ports-tracking-branch daemonarchy-1.1-package-baseline \
  > /path/to/checkout-repo/checkouts.json
sudo pkg repo /path/to/checkout-repo /usr/local/etc/daemonarchy/pkg-repo.key
```

`--depth` defaults to 1. The current candidate package integration is on the fork's
`daemonarchy-1.1-package-baseline` branch; the checkout tracks that integration
branch. Default fetches are restricted to one branch. Payloads are split into 512 MiB parts before packaging,
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
