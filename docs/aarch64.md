# aarch64: inventory and worker bring-up

[ARCH-001](roadmap/active-work.md#arch-001-add-aarch64-as-a-second-supported-architecture-for-140)
([issue #62](https://github.com/jordanhubbard/daemonarchy/issues/62)) adds
aarch64 alongside amd64 for 1.4.0. This page records the read-only inventory of
2026-10-26, the plan for the first native aarch64 worker, and that worker's
first native results:
- a kernel, world and poudriere jail at the selected source, and a passing
  `x11-wm/hyprland` testport;
- a native bulk build of the image package closure;
- an **unsigned development** package feed and UEFI installer ISO. The ISO
  boots to the installer menu under QEMU/EDK2
  ([record](#worker-record-native-bulk-unsigned-feed-and-uefi-iso-2026-10-27)).

## Status in 1.4.1: a community-validation image

The 1.4.1 release publishes `daemonarchy-1.4.1-aarch64.iso.xz`
([release notes](release-1.4.1.md#aarch64-image-community-validation)). The bar it
met is that it boots and installs in a QEMU virtual machine. Nothing beyond that is
claimed, and people with arm64 hardware are asked to fill the gaps.

**Verified** (records below and
[`aarch64-1.4.1-staging-20261030-development.json`](../verification/aarch64-1.4.1-staging-20261030-development.json)):
the signed aarch64 feeds; and two installs under QEMU 11.1.2 with HVF on an Apple
silicon Mac, on QA candidate images, each of which installed and booted under UEFI
with 23 checks passed and 2 failed. The failed checks are `sddm running` (no DRM/KMS
driver in the guest) and `updates from the signed Daemonarchy repository` (the
public feed URLs did not exist yet). The release image itself was then installed in the same QEMU setup from the public feeds: it took 36 minutes, booted under UEFI and passed 33 of 34 checks; the one failure is the known `sddm running` (no DRM device in the guest), and no package came from pkg.FreeBSD.org.

**Not verified:** any physical aarch64 machine; DRM/KMS and any hardware GPU
desktop (SDDM does not start in the VM, and no graphical desktop was seen on
aarch64); sound; Wi-Fi; upgrade, rollback, network debugging and the live desktop.
Apple silicon laptops cannot be install targets (see
[Running aarch64 on Apple silicon](#running-aarch64-on-apple-silicon)). Omitted from
the aarch64 desktop: `chromium`, `aether`, `mise` and `edk2@bhyve`
([why](#default-desktop-on-aarch64-decision-of-2026-10-30)); the default browser is
Epiphany.

**Reporting.** Open an issue at
<https://github.com/jordanhubbard/daemonarchy/issues> (there is no issue template):
the machine or VM, the image SHA-256, what you ran and the result. Success reports
help as much as failures.

The rest of this page is the working record that led here. It was written before
publication, so its "not published" statements describe the state of that day.

Earlier status, as of the worker records below: an
**unsigned development** package feed and UEFI installer ISO booted to the installer
menu under QEMU/EDK2 ([record](#worker-record-native-bulk-unsigned-feed-and-uefi-iso-2026-10-27)),
and one install under QEMU with HVF completed and booted
([record](#worker-record-aarch64-staging-at-the-post-14-base-2026-10-30)). Those
records have no upgrade, rollback, desktop, debugging or laptop result, and no amd64
result stands in for one.

## Inventory, blocking gaps first

The inventory was read-only. Package availability comes from the
`FreeBSD:16:aarch64/latest` and `FreeBSD:16:amd64/latest` `packagesite.yaml`
catalogues on pkg.FreeBSD.org (aarch64 catalogue built 2026-10-24). They were
downloaded on the controller and parsed without pkg's fingerprint verification,
so they are planning data only, not package provenance. The dependency closure
was computed from the published `packages-16-amd64-1.3.1` feed plus the official
amd64 catalogue, starting from:

- the installer's package set: `pkg bash sudo daemonarchy chromium octopkg wifi-firmware-kmod`;
- the GPU sets: `drm-612-kmod gpu-firmware-kmod mesa-dri vulkan-loader`, the
  navi14 firmware and the NVIDIA set;
- the live image set.

The closure has 1,222 packages. Port restrictions were read from the
Makefiles at ports `b785784` (fork `main`) and `f7d7ee8` (`native/workspace.json`),
and from upstream FreeBSD ports.

### Blocking gaps

1. **The default desktop does not resolve on aarch64.** These packages are absent
   from `FreeBSD:16:aarch64/latest`. Builder evidence was read on 2026-10-26 from
   pkg-status.freebsd.org build data and the pkg-fallout list:
   - **`x11-wm/hyprland`, the compositor** (needed by omarchy and omasnap). The
     port has no architecture restriction; it fails to build on the main-arm64
     builder.
     - pkg-fallout reported `hyprland-0.56.2_2` failing in the build phase on
       2026-10-23
       ([log](https://pkg-status.freebsd.org/ampere2/data/main-arm64-default/p3a3ea9a0eb1f_s1ca7f661853/logs/hyprland-0.56.2_2.log)).
       The same failure hit 0.54.2 in the March main-arm64 build.
     - Every translation unit compiled with the CMake precompiled header fails
       under `devel/llvm19` with `reference to '__builtin_va_list' is ambiguous`,
       raised from `libinput.h` through clang's `__stdarg_va_list.h`.
     - The port switches to `devel/llvm19` when the base clang reports
       `+assertions`, which -CURRENT's does.
     - The 15.1 aarch64 builder compiled the same 0.56.2_2 with the same PCH using
       base clang 19.1.7 and published it (build `ce97aa4dd1d9`, 2026-10-20).
     - Every Hyprland library dependency is published for `FreeBSD:16:aarch64`.
     - I found no upstream fix in FreeBSD ports.
     - [daemonarchy-ports#28](https://github.com/jordanhubbard/daemonarchy-ports/pull/28)
       builds without PCH on aarch64 only. A native aarch64 `poudriere testport`
       at ports `3e782916` confirmed it on 2026-10-26: 0.56.2_2 builds with
       `devel/llvm19` clang 19.1.7, passes stage-qa and check-plist, and
       installs and deinstalls cleanly
       ([record](#worker-record-native-kernel-jail-and-hyprland-2026-10-26)).
   - **`www/chromium`** is `ONLY_FOR_ARCHS= aarch64 amd64`, but has no aarch64
     package.
     - 15.1 aarch64: the build ran from 2026-10-20 08:24 to 2026-10-22 19:21 UTC.
       It was then killed by `Signal 15` at step 53168 of 55897 (95%). That is a
       builder time limit, not a compile error.
     - main-arm64: chromium is blacklisted (its last listed build, March 2026,
       records it as "Blacklisted").
     - `www/cef` also failed on 15.1 aarch64.
     - Daemonarchy already builds Chromium for its amd64 feed, because
       `FreeBSD:16:amd64/latest` has no Chromium package either. For aarch64, a
       native Chromium build needs a builder with no such time limit, or more
       capacity.
     - It was an unconditional `RUN_DEPENDS` of `x11-wm/daemonarchy`, so
       poudriere would queue it before the desktop package.
       [daemonarchy-ports#30](https://github.com/jordanhubbard/daemonarchy-ports/pull/30)
       makes it a dependency everywhere except aarch64. An aarch64 desktop
       therefore has no default browser.
   - **`x11-themes/aether`** fails in the native aarch64 build.
     - It builds its Vite frontend offline from an npm cache distfile that
       carries only the FreeBSD x64 rolldown, lightningcss and tailwind oxide
       bindings, and npm publishes no FreeBSD arm64 build of any of them.
     - Failing it skips `x11-wm/daemonarchy`, whose OMAAPPS option depends on
       it. ports#30 makes that dependency non-aarch64.
     - A real aarch64 aether needs a new distfile. Either:
       - a prebuilt, architecture-independent `frontend/dist`; or
       - an npm cache with WASI bindings and a lightningcss replacement.
   - **`sysutils/mise`** has `BROKEN_aarch64= unsupported freebsd architecture`
     (conda/rattler#2226), and the builders skip it as ignored. It was an
     unconditional `RUN_DEPENDS` of `x11-wm/omarchy`, and part of
     `x11-wm/daemonarchy`'s DEV option.
   - **`sysutils/edk2@bhyve`** is `ONLY_FOR_ARCHS=amd64`. It was an unconditional
     `RUN_DEPENDS` of `x11-wm/daemonarchy`.

   [daemonarchy-ports#28](https://github.com/jordanhubbard/daemonarchy-ports/pull/28)
   (against `daemonarchy`) changes the dependency metadata:
   - it makes `mise` a dependency everywhere except aarch64;
   - it makes `edk2@bhyve` an amd64-only dependency;
   - it leaves amd64 metadata unchanged, which a hosted metadata check verifies.

   omarchy's first-run user provisioning (`install/user/mise-work.sh` and
   `mise.sh`) still calls `mise` under `bash -eE`. The `omarchy-freebsd`
   compatibility layer must skip those steps when `mise` is absent before an
   aarch64 install can complete.

   Every Daemonarchy-only port (the `OMARCHY_ORIGINS`) is absent from the official
   set, as expected, and must be built natively. Their Makefiles carry no amd64
   restriction.
2. **No GPU KMS driver exists for aarch64.**
   - `graphics/drm-612-kmod` (fork-modified) and every other `drm-*-kmod` are
     `ONLY_FOR_ARCHS=amd64`. No DRM kernel module package exists for aarch64.
   - NVIDIA (`x11/nvidia-driver`, `nvidia-kmod`, `nvidia-drm-612-kmod`,
     `linux-nvidia-libs`) is amd64-only and uses x86_64 distfiles.
   - The only aarch64 KMS option is the standalone `graphics/virtio-gpu-qemu-kmod`,
     which serves a QEMU virtio-gpu device.
   - VMware's arm64 SVGA device has no FreeBSD driver, so a VMware aarch64 guest
     has only the EFI framebuffer and cannot start Hyprland.

   The desktop case therefore needs a virtio-gpu host (QEMU or UTM), a KMS port,
   or an explicit "not qualified in VMware" record.
3. **The source build tooling is amd64-only.** In `daemonarchy-src`:
   - `tools/daemonarchy/build.py` hard-codes `sys/amd64/conf`,
     `TARGET=amd64 TARGET_ARCH=amd64` and refuses non-amd64 workers.
   - `retained-source-stage.py` and the loader/netconsole test scripts
     (`tests/build-earlynet-loader.sh`, `run-efi-bootinfo.sh`,
     `run-efinet-console.sh`, `run-netconsole-receive.sh`) also assume amd64.
   - Only `sys/amd64/conf/DAEMONARCHY_DIAGNOSTIC` exists. An arm64 equivalent
     needs `NETGDB` (absent from `std.arm64`) and `DAEMONARCHY_NETCONSOLE`.
4. **The loader netconsole has no arm64 entropy fallback.** `nc_random()` in
   `stand/efi/loader/netconsole.c` falls back to RDRAND only on x86. Without
   `EFI_RNG_PROTOCOL` on the guest firmware, the authenticated loader console
   cannot start on arm64. It needs an RNDR fallback or a stated firmware
   requirement. Whether VMware's arm64 firmware provides the protocol is
   unverified.
5. **Source CI never builds Daemonarchy's aarch64 pieces.** The "Cross-build
   Kernel" workflow builds only `GENERIC` with `NO_MODULES` for aarch64; the
   latest main run, [40068278453](https://github.com/jordanhubbard/daemonarchy-src/actions/runs/40068278453)
   of 2026-10-24, passed. No aarch64 loader, world, diagnostic kernel or
   netconsole build has run in CI.
6. **poudriere cannot make an aarch64 ISO.** Its `iso` and `hybridiso` types
   embed x86 BIOS boot code (`cdboot`, `pmbr`, `isoboot`). This change adds a
   UEFI-only path (see below). A native build of it booted under QEMU/EDK2,
   both as a CD and as a disk, as development evidence
   ([record](#worker-record-native-bulk-unsigned-feed-and-uefi-iso-2026-10-27)).
   No VMware or hardware boot has qualified it.
7. **Product scripts still bound to amd64** (outside this change):
   - `scripts/build-checkout-packages.py:102` writes an amd64 ABI literal.
   - `scripts/adopt-candidate-packages.sh:33,85` requires amd64.
   - `secureboot/build.py` and `secureboot/module-inventory.py` are amd64-only;
     Secure Boot is not offered on aarch64, and `build-iso.sh` refuses Secure
     Boot artifacts there.
   - `test-qemu.sh` defaults to amd64.
   - `scripts/release-check-1.3.1.py` is historical.

### Dropped on aarch64 (amd64-only by design)

- NVIDIA drivers, Linux NVIDIA libraries and CUDA/Cudalab. CUDA is already
  refused for every architecture in this release.
- Legacy BIOS boot. aarch64 boots by UEFI only. The installer keeps the `p4`
  partition so indices match, and leaves it empty.
- The Apple T2 MacBook support: `net/if_brcmfmac-kmod` (BCM4364,
  `ONLY_FOR_ARCHS=amd64`), its firmware import and keyboard quirk, and the
  MacBook EFI timer loader. `stand/efi/libefi/time.c` is compiled only for
  amd64; arm64 already uses the monotonic `time_arm64.c`.
- Intel VAAPI and Intel GPU firmware. These are already guarded by architecture
  in the `daemonarchy` and `gpu-firmware-kmod` ports.

### Architecture-neutral

- Loader netconsole, efinet ownership/handoff, Lua menu, debugnet, NetGDB,
  iflib and the vtnet debugnet fixes (`bootp_client_arch` already handles
  aarch64).
- Debugnet-capable NICs in arm64 `GENERIC`: `vmx`, `vtnet`, `em`, `ix`, `re`,
  `bge` and `mlx5en`. These cover the VMware (`vmx`, `em`) and QEMU (`vtnet`)
  guests.
- The other Daemonarchy-only ports (Go, Rust, Qt, meson and `NO_ARCH`),
  `gpu-firmware-kmod`, `wifi-firmware-kmod`, `7-zip`, Mesa, Vulkan loader,
  Quickshell, SDDM, LibreOffice, VLC, node, Go, dotnet and `lib32.txz`. The
  arm64 16.0-CURRENT snapshot publishes `base`, `kernel` and `lib32`.

## Default desktop on aarch64 (decision of 2026-10-30)

The aarch64 desktop is the amd64 desktop minus what cannot be built or run there,
plus a default browser that exists for the architecture. Nothing is dropped
silently: each omission has a reason and a consequence.

| Not on aarch64 | Why | Consequence |
| --- | --- | --- |
| `chromium` | no aarch64 package: the 15.1 builder kills it at 95% and main-arm64 blacklists it | replaced by Epiphany, below |
| `aether` | its Vite frontend needs npm bindings that have no FreeBSD arm64 build | the theme editor is unavailable; switching themes still works |
| `mise` | `BROKEN_aarch64` (conda/rattler#2226) | developer toolchains come from `pkg` directly; omarchy's first-run skips the `mise` steps (ports#29) |
| `edk2@bhyve` | amd64-only | none on a guest |
| `amdgpu`, `radeon`, `i915`, NVIDIA | amd64-only | no hardware GPU desktop; see the VirtIO GPU record below |

**Default browser: Epiphany (GNOME Web).** `FreeBSD:16:aarch64/latest` has no
Chromium, Firefox or any Chromium-family browser (checked 2026-10-30). It does
carry Epiphany, Falkon, qutebrowser, Badwolf and NetSurf. Epiphany is the choice
because WebKitGTK is already in the closure: it adds 5 packages (`epiphany`,
`webkit2-gtk_60`, `libavif`, `libyuv`, `woff2`; 37 MiB), against 6 packages and
83 MiB for Falkon. The installer selects it on aarch64 where it selects
`chromium` on amd64. The five packages are not in the first closure shard, and published tags are
immutable, so they ship as a second, signed shard
(`packages-16-aarch64-1.4.1-upstream-2`, 9 files, 38 MB, published) that the
image lists beside the first.

Not solved: omarchy's web-app launchers run `chromium --app`; making the compat
layer's browser choice follow the installed browser (Epiphany has an application
mode) is a follow-up in `omarchy-freebsd`.

## What the product now does per architecture

`scripts/image-architecture.sh` selects every default from `ARCH` (`amd64`
default, or `aarch64`). The amd64 values are unchanged.

| | amd64 | aarch64 |
|---|---|---|
| Jail, ABI | `16amd64`, `FreeBSD:16:amd64` | `16aarch64`, `FreeBSD:16:aarch64` |
| Release sets | `snapshots/amd64/16.0-CURRENT`, cache `/var/cache/daemonarchy-iso` | `snapshots/arm64/aarch64/16.0-CURRENT`, cache `/var/cache/daemonarchy-iso-aarch64` |
| Package feed | `packages-16-amd64[-version]` | `packages-16-aarch64[-version]` |
| Image | `daemonarchy-VERSION-amd64.iso.xz`, poudriere `hybridiso` (BIOS + UEFI) | `daemonarchy-VERSION-aarch64.iso.xz`, poudriere `tar` + `scripts/make-efi-iso.sh` (UEFI only) |
| Removable-media loader | `EFI/BOOT/BOOTX64.EFI` | `EFI/BOOT/BOOTAA64.EFI` |
| Live kernel drivers | `if_brcmfmac-kmod` | none |
| ISO GPU payload | DRM 6.12, firmware, NVIDIA | `gpu-firmware-kmod` only; no KMS selected |

The changes by component:

- **`build-iso.sh`** refuses an `ABI` that disagrees with `ARCH`, and refuses
  Secure Boot artifacts outside amd64.
- **`scripts/make-efi-iso.sh`** follows FreeBSD's
  `release/arm64/mkisoimages.sh`. It writes an El Torito EFI image and a GPT in
  the ISO system area, so the same bytes boot from a virtual CD or a USB stick.
- **The installer** takes the architecture from the image `ABI`. It:
  - selects that architecture's feed family and refuses another's;
  - writes the matching fallback loader;
  - skips BIOS boot code and the BCM4364 path on aarch64;
  - selects no KMS driver on aarch64.
- **`pkg-repo.sh`** builds `packages-16-$ARCH`; its remote `publish` remains
  amd64-only.
- **`scripts/check-gpu-packages.sh`** takes the image ABI.
- **`origins.sh`** names the amd64-only ISO origins in `ISO_ORIGINS_AMD64_ONLY`.
- **`scripts/verify-release-assets.py`** accepts an optional `architectures`
  list in a release record. One image asset is expected per listed
  architecture, and a record without the list stays amd64-only. aarch64 is
  accepted from 1.4.0. The signed boot bundle remains the amd64 Secure Boot
  bundle.
- **The release input graph** gives every unit one architecture. See
  [Architecture variants](release-input-graph.md#architecture-variants) and
  [`native/release-graph/architectures.json`](../native/release-graph/architectures.json).

Portable checks: `bash tests/image-architecture.sh`, `sh tests/package-repository.sh`,
`python3 tests/release-asset-names.py` and, with the LitAI interpreter,
`tests/release-input-graph.py`.

## Worker bring-up: FreeBSD arm64 under VMware on Apple silicon

### Install media

FreeBSD publishes `dvd1` only for releases, not 16.0-CURRENT snapshots. Use the
newest arm64 release, currently 15.1:

- `FreeBSD-15.1-RELEASE-arm64-aarch64-dvd1.iso` from
  `https://download.freebsd.org/releases/arm64/aarch64/ISO-IMAGES/15.1/`;
- `CHECKSUM.SHA256-FreeBSD-15.1-RELEASE-arm64-aarch64` from the same directory.
  Check it against the PGP-signed 15.1-RELEASE announcement.

On the Mac, run `shasum -a 256 FreeBSD-15.1-RELEASE-arm64-aarch64-dvd1.iso` and
compare the result with the line in that checksum file. Record the ISO name and
SHA-256 before installing. A mismatch stops the bring-up.

Daemonarchy builds and installs FreeBSD 16. A poudriere jail cannot run a newer
major version than its host kernel, so after installation the guest must move
to the selected 16 source. Build and install world and kernel natively from the
exact `daemonarchy-src` revision in the release selection, or install the
matching 16.0-CURRENT snapshot sets. Record the resulting `uname -a` and
`freebsd-version -ku`.

### VMware guest: build worker

- **Firmware:** UEFI, the only arm64 option. Guest type: other/FreeBSD 64-bit Arm.
- **vCPU:** the Mac's performance cores minus two; 8 is the practical minimum.
  The 1.1.1 amd64 dependency rebuild used 20 CPUs.
- **RAM:**
  - 32 GiB on a Mac with 64 GiB or more; 16 GiB is the floor.
  - Hyprland, Chromium/CEF and LLVM must be built natively for aarch64 (gap 1),
    and linking them is memory-bound. Use one poudriere builder at 16 GiB and
    two at 32 GiB or more.
- **Disk:** one NVMe virtual disk of 400 GiB, the size of the 1.1.1 rebuild,
  under ZFS. It holds the poudriere jail, the ports tree, distfiles, the package
  cache, the release-set cache and the images. Keep at least
  `native/worker-template.json`'s free space after the jail is populated.
- **Network:** NAT (shared) networking is enough for outbound HTTPS to
  pkg.FreeBSD.org, download.freebsd.org and GitHub. Reach the guest over SSH by
  a VMware port forward or a private bridged LAN.
  - Use the `vmxnet3` virtual NIC (`vmx`, in arm64 `GENERIC`, debugnet-capable
    through iflib). An `e1000e` NIC (`em`) also works.
  - Keep worker addresses and keys out of committed records.
- **Display:** the EFI framebuffer console is enough for a build host.

### Making it a native build host

1. Install from `dvd1` with ZFS root, `sshd` and `ntpd`. Add the operator's SSH
   key and update to the selected 16 base as above.
2. Install the worker tools with `pkg install git python312 poudriere-devel
   gmake pkgconf`, and check them against `native/worker-template.json`. Then
   run `native/inspect-worker-allocation.py` from an operator-owned directory to
   record CPU, memory and disk. Only after those capacity and identity checks
   does the release graph admit the guest as the `aarch64` worker.
3. **Source:** clone `daemonarchy-src` at the selected revision. Port
   `tools/daemonarchy/build.py` and the loader test scripts to `TARGET=arm64
   TARGET_ARCH=aarch64` (gap 3) before claiming a native source build. Build
   world, kernel and the EFI loader natively.
4. **Release sets and jail:**

   ```sh
   SET_CACHE_DIR=/var/cache/daemonarchy-iso-aarch64 \
     SNAPSHOT_URL=https://download.freebsd.org/snapshots/arm64/aarch64/16.0-CURRENT \
     sh scripts/cache-release-sets.sh
   poudriere jail -c -j 16aarch64 -a arm64.aarch64 -v 16.0-CURRENT \
     -m tar=/var/cache/daemonarchy-iso-aarch64/base.txz
   tar -xpf /var/cache/daemonarchy-iso-aarch64/kernel.txz -C /usr/local/poudriere/jails/16aarch64
   tar -xpf /var/cache/daemonarchy-iso-aarch64/lib32.txz -C /usr/local/poudriere/jails/16aarch64
   ```

   Then follow `HACKING.md`'s jail, `@clean` snapshot and `/usr/src` steps for
   this jail.
5. **Ports:** register the selected `daemonarchy-ports` revision as in
   `HACKING.md`, after the fork makes `edk2@bhyve` and `mise` conditional
   (gap 1). Bulk-build `ISO_ORIGINS` minus `ISO_ORIGINS_AMD64_ONLY` with
   `-j 16aarch64 -b latest`. Expect to build Hyprland, Chromium/CEF and their
   dependencies natively, and retain every log, failures included.
6. **Feed and image:**
   - Build the feed with `ARCH=aarch64 TAG=packages-16-aarch64-VERSION sh
     pkg-repo.sh build` on the worker. Upload it as its own feed.
   - Build the image with `ARCH=aarch64 JAIL=16aarch64 PTREE=<tree> sh
     build-iso.sh`. It produces `daemonarchy-VERSION-aarch64.iso` and `.iso.xz`
     with their checksums.
   - Record exact artifact identities separately from amd64.

### Worker record: 15.1 to 16.0-CURRENT in a boot environment (2026-10-26)

The first worker was installed from the 15.1 `dvd1` ISO. On 2026-10-26 the
operator approved moving it to 16.0-CURRENT in a new boot environment, keeping
15.1 for rollback. The full record, with every hash, is
[`aarch64-worker-be16-bringup-20261026-development.json`](../verification/aarch64-worker-be16-bringup-20261026-development.json).
It covers host preparation only. The results after the reboot are in the
[next record](#worker-record-native-kernel-jail-and-hyprland-2026-10-26).

- **Preflight.**
  - The pool `zroot` (197G, one NVMe vdev) was ONLINE with no errors, and had
    one BE, `default`.
  - The ESP is p1, `gpt/efiboot0`. It held one 15.1 loader as both
    `efi/freebsd/loader.efi` and `efi/boot/bootaa64.efi` (`f7fce7a5…`).
  - The guest already had 8 vCPUs and about 16 GiB.
  - The base was **pkgbase**, not the assumed distribution sets: 316 FreeBSD-*
    15.1 packages from an enabled `FreeBSD-base` repository.
- **Sets.** The `snapshots/arm64/aarch64/16.0-CURRENT` snapshot is `BUILDDATE`
  20261019, `main` `041802b362aa` (`main-n290219`, 1600028). `kernel.txz`
  (`652609c5…`), `base.txz` (`5e9fa69c…`) and `lib32.txz` (`36c53511…`) were
  fetched over HTTPS and matched its `MANIFEST`.
- **BE.** `bectl create be16` cloned `default`. In the mounted be16:
  - `boot/kernel` became `kernel.15`, and `kernel.txz` was extracted.
  - `base.txz` and `lib32.txz` were extracted with
    `--clear-nochange-fflags`, excluding `etc`, `root` dotfiles,
    `boot/device.hints` and the contents of the shared datasets.
- **etcupdate.** The worker had no etcupdate database, and `etcupdate -t`
  takes a build tree rather than `base.txz`. Two distribution trees (`etc`,
  `root`, `boot/device.hints`) were cut from the verified 15.1-RELEASE and 16
  `base.txz`. The 15.1 tree seeded `etcupdate extract`; then
  `etcupdate -F -D /mnt/be16 -t` applied the 16 tree.
  - **No conflicts.**
  - `group` merged, gaining `audio` and `vmm`. 54 stock files were updated,
    three added, and `rc.d/apm` removed.
  - Users, `rc.conf`, `fstab`, `sysctl.conf`, ssh host keys, `loader.conf`
    and `sudoers` were verified unchanged.
  - `certctl rehash` followed.
- **ESP.** The 16 `loader.efi` (`7f2b89e4…`) replaced `efi/freebsd/loader.efi`
  and `efi/boot/bootaa64.efi`. The 15.1 copies stay beside them as
  `loader-15.1.efi` and `bootaa64-15.1.efi`. EFI variables are unchanged.
- **Packages.**
  - In be16, `FreeBSD-base` is disabled, so pkg cannot overwrite the
    verified sets.
  - `git`, `python312`, `poudriere-devel`, `gmake` and `pkgconf` came from
    `FreeBSD:16:aarch64` `latest`. Every ports package moved to the 16 ABI.
  - This needed `IGNORE_OSVERSION`: the packages are 1600029 and the snapshot
    userland is 1600028.
  - The 15.1 FreeBSD-* records remain in the database. Removing them, or moving
    base to pkgbase 16, is the operator's later choice.
- **Source.** `/usr/src`, the shared dataset, is a blobless clone of
  `daemonarchy-src` branch `daemonarchy` at `4bfe2344`. That head contains the
  selected `d63d77f4` (1600029) plus 33 commits.
- **Activation.** `bectl activate be16` was run: `bootfs` is
  `zroot/ROOT/be16`. `default` is kept. `/root/BE16-README.txt` gives the
  rollback, and `/root/be16-post-reboot.sh` in be16 holds the steps below.

**Rollback:** choose `default` from the loader's boot-environment menu, or run
`bectl activate default` and reboot. If the 16 loader ever fails, copy the
`-15.1.efi` files back over the active names.

The steps that needed the reboot (boot be16, build and install the
selected-source kernel, create the jail, admission) are done or resolved in the
next record.

### Worker record: native kernel, jail and Hyprland (2026-10-26)

The operator then put the worker entirely at the project's disposal. The record
is
[`aarch64-worker-native-build-20261026-development.json`](../verification/aarch64-worker-native-build-20261026-development.json).

- **Host.** be16 booted. The stale FreeBSD-* 15.1 pkg records were purged and
  `default` was destroyed, so be16 is the only BE. Address selection now prefers
  IPv4 (`ip6addrctl_policy=ipv4_prefer`): the guest gets an IPv6 address that
  passes no traffic, and every fetch stalled before falling back.
- **Kernel.** The first native aarch64 kernel, GENERIC at `d63d77f4` (1600029),
  was built in 20 minutes with its toolchain. It is installed and running as
  `n290215-d63d77f4eb3c` (`44e9a957…`); the snapshot kernel is
  `/boot/kernel.old`. No arm64 `DAEMONARCHY_DIAGNOSTIC` exists yet (gap 3).
- **World and jail.** buildworld took 40 minutes. `16aarch64` (16.0-CURRENT
  1600029, `arm64.aarch64`, `src=/usr/src`) was created from it. Its `@clean`
  snapshot holds the same kernel, `usr/lib32/libc.so.7` and the 1600029
  `param.h`. An earlier installworld without a buildworld failed and is kept.
- **Ports tree.** `daemonarchy` is a depth-1 clone of `daemonarchy-ports`
  branch `daemonarchy` at `3e782916`, which includes ports#28 and #29. It is
  registered with `-m null`. `daemonarchy-poudriere.conf` pins
  `PACKAGE_FETCH_URL` and sets `ALLOW_MAKE_JOBS=yes`.
- **Hyprland.** `poudriere testport -j 16aarch64 -p daemonarchy -b latest
  -o x11-wm/hyprland` **passed** on the third full run (3 h 1 min, one builder).
  - 238 dependencies came from `FreeBSD:16:aarch64` `latest`. 131 ports were
    built natively across the runs (115 in the first, 16 in the last), because
    the ports tree is ahead of the official set. They include `lang/rust`
    (53 min), `devel/llvm19` (57 min) and Mesa.
  - Hyprland built with `/usr/local/llvm19/bin/clang++` 19.1.7, the compiler
    that fails on the main-arm64 builder, and CMake reported "Not using
    precompiled headers".
  - stage-qa and check-plist passed, with only `LIB_DEPENDS` and
    `REINPLACE_CMD` hints. Install, the shared-library check and deinstall
    were clean.
  - This confirms a build, not a runtime: the VMware guest cannot start
    Hyprland (gap 2).
- **Failed runs, kept.**
  - One run had an unescaped `${ABI}`, so no package could be fetched.
  - One single-job run was stopped deliberately because LLVM would have
    outlasted the bound.
  - A three-builder run lost `llvm19` and `rust` to the out-of-memory killer:
    both built LLVM at 8 jobs on 16 GiB with 2 GiB swap. Use one builder for
    LLVM-class ports, or add memory.
- **Admission.**
  - `native/inspect-worker-allocation.py` does not apply: it relays to a
    `native/qemu-worker.py` QEMU guest's inspection socket, which a VMware
    guest does not have.
  - The `native/worker-template.json` checks pass: every command is present,
    Python is 3.12.14, and 177 GiB is free against a 10 GiB minimum.
  - The worker is **not admitted** to the release graph; that admission is
    still to be defined. The 200G disk is below the 400 GiB sizing.

### Worker record: native bulk, unsigned feed and UEFI ISO (2026-10-27)

The record, with every hash, is
[`aarch64-bulk-iso-20261027-development.json`](../verification/aarch64-bulk-iso-20261027-development.json).
Everything here is unsigned development evidence, outside LitAI custody. Nothing
was signed or published.

- **Package list.** 34 origins:
  - `ISO_ORIGINS` minus `ISO_ORIGINS_AMD64_ONLY`;
  - `build-iso.sh`'s live packages (`bash gum jq ttfx tzupdate pkg
    wifi-firmware-kmod 7-zip python312`);
  - the installer set (`sudo`, `octopkg`);
  - `mesa-dri` and `vulkan-loader`.

  Exclusions, each recorded with its reason:
  - DRM/KMS, NVIDIA and `if_brcmfmac-kmod` are amd64-only (gap 2).
  - `chromium` has no aarch64 build (gap 1).
  - `mise` and `edk2@bhyve` were already dropped by ports#28.
- **Ports.** The tree is `3e782916` plus
  [ports#30](https://github.com/jordanhubbard/daemonarchy-ports/pull/30) (open),
  which makes `chromium` and `aether` non-aarch64 dependencies of
  `x11-wm/daemonarchy`. Its metadata check passes on the worker.
- **poudriere settings.** HACKING.md's `PACKAGE_FETCH_BLACKLIST` was added, so
  kernel modules are built for the jail kernel.
- **Bulk.** `poudriere bulk -j 16aarch64 -p daemonarchy -b latest -J 2`, bounded
  by `timeout -k`. Memory-heavy ports were capped at 4 make jobs by a
  per-tree `make.conf`.
  - Runs 1-2 used ports#30's chromium commit. Run 3 added its aether commit, and
    built `daemonarchy-1.3.1,1`.
  - Of 1,044 queued packages:
    - 580 were built;
    - 463 were fetched from `FreeBSD:16:aarch64` `latest`;
    - 1 failed (`x11-themes/aether`, above);
    - none was ignored, and none is still skipped.
  - The longest builds were `llvm21` (2 h 11 min), LibreOffice (1 h 20 min),
    deno (1 h 8 min) and WebKitGTK (56 min).
- **Host incident.** Run 1 was killed after 1 h 27 min when the VMware *host*
  ran out of disk and rebooted the guest.
  - The pool was healthy afterwards, and the resumed run reused every completed
    package. No evidence was lost.
  - At the operator's direction:
    - the temporary 16 GiB swap zvol was removed;
    - a guard stopped the build if zroot passed 150G.
  - The pool peaked at 50.6 GiB allocated.
  - The guest's virtual NVMe reports **no Dataset Management (TRIM)**. A thin
    host disk therefore never shrinks when the guest frees space.
- **Release sets.** `make -C release packagesystem` from the native `d63d77f4`
  obj tree produced `base.txz`, `kernel.txz` and `lib32.txz`, held in their own
  set cache. The kernel set is the worker's own `44e9a957…` kernel.
- **Feed.** The unsigned development feed `packages-16-aarch64-dev20261027` was
  made with `pkg-repo.sh collect`, given the rebuilt-package list, then
  `pkg repo` with no key.
  - It has 360 payloads.
  - With `FreeBSD:16:aarch64` `latest`, it resolves the installer set without
    Chromium: 939 packages, 294 of them from this feed.
<!-- release-sync: history -->
- **ISO.** origin/main's `build-iso.sh` built `daemonarchy-1.3.1-aarch64-dev.iso`
  unchanged, with `ARCH=aarch64` and the d63d77f4 sets.
  - The `.iso` is 1,269,610,496 bytes (`6d6f1fe3…`). The `.iso.xz` is
    678,107,496 bytes (`59932128…`).
  - It used the 1.3.1-final checkout catalogue, whose source revision is
    `d63d77f4`, so the kernel identity check passed. That catalogue points at
    the amd64 checkout feed: no aarch64 checkout feed exists.
  - The worker needed `jq` and `bash` installed.
  - `tests/live-image-runtime.sh` passed.
<!-- /release-sync -->
- **Boot.** `qemu-system-aarch64` 11.1.2 with its EDK2 firmware (TCG,
  virtio-gpu) booted the image to the installer welcome screen, whose preview
  label reads "aarch64 development build, unsigned". With a USB keyboard,
  Return opened the installer menu. A first, packageless image of the same
  UEFI path booted from both CD and disk.
  - **Finding, fixed in
    [daemonarchy-src#37](https://github.com/jordanhubbard/daemonarchy-src/pull/37)
    (open):** bringing up `vtnet0` on arm64 logged about 50 WITNESS warnings
    and a lock order reversal, `VTNET Core Lock -> sysctl lock`. The boot and
    DHCP continued.
    - Cause: the control-command header tag asks for 2-byte alignment, so it
      could bounce. Its first `bus_dmamap_create()` comes from
      `vtnet_set_macaddr()` under the core mutex. When no bounce zone exists yet,
      that call creates one, which takes the sysctl lock, allocates with
      `M_WAITOK` and starts the busdma thread.
    - QEMU arm64 `virt` shows it because vtnet is the first driver there to need
      a bounce zone. amd64 has the same code path. It fires there only when no
      other driver has made a zone first, and was not tested.
    - Upstream main has the same code, so it is not fixed upstream either.
    - The fix creates the zone at attach with `BUS_DMA_ALLOCNOW`.
    - A QEMU A/B boot of this ISO, remastered with each kernel, gave 50 warnings
      and 1 LOR without the fix, and none with it. `vtnet0` got a DHCP lease in
      both runs.
    - This image's kernel still has the bug until it is rebuilt with the fix.
  - No install was run, because the `packages-16-aarch64` feed is not
    published. No upgrade, rollback, desktop or debugging case was run either.

### Worker record: aarch64 staging at the post-1.4 base (2026-10-30)

The first complete aarch64 chain: release sets at the 1.4.1 source base, signed
package feeds, an installer ISO, and an **end-to-end install that booted**, all
**staged and not published**. The exact commands are in
`scripts/aarch64-reroll/` (see its README.md); the artifact
identities are in
[`aarch64-1.4.1-staging-20261030-development.json`](../verification/aarch64-1.4.1-staging-20261030-development.json).
Nothing here is under LitAI custody, and nothing was uploaded.

| Stage | Result | Time |
| --- | --- | --- |
| Source, world, kernel, sets | `daemonarchy-src` `303b3646270f` (the post-1.4 upstream sync, which includes the vtnet WITNESS fix, [src#37](https://github.com/jordanhubbard/daemonarchy-src/pull/37)); incremental on the retained obj tree; kernel `FreeBSD 16.0-CURRENT #2 303b3646270f`; `base.txz` `f2e66bde…`, `kernel.txz` `492dc542…`, `lib32.txz` `42f4c9f7…` | 8 min (world 159 s) |
| Ports pin | `daemonarchy-ports` `0e8fb88350c7` (the merge of [ports#31](https://github.com/jordanhubbard/daemonarchy-ports/pull/31)) | |
| poudriere bulk | 13 queued: 12 built, 1 failed (`x11-themes/aether`, as before); `daemonarchy-1.3.1,1` built | 12 min |
| Application feed `packages-16-aarch64-1.4.1` | 496 payloads, 1.9 GiB, signed; `packagesite.pkg` `4c51894d…` | 30 s to collect |
| Checkout feed `checkouts-16-aarch64-1.4.1` | src `303b3646270f` (2 packages) and ports `0e8fb88350c7`; signed | 5 min |
| Closure shard `packages-16-aarch64-1.4.1-upstream` | 552 upstream packages, 3,261,881,077 bytes, 556 files; signed; verified | fetch 6 min |
| ISO `daemonarchy-1.4.1-aarch64.iso` | 2,628,749,312 bytes (`0f9af366…`); `.iso.xz` 957,743,052 bytes (`3f0675c3…`) | 22 min with xz |
| QEMU install | passed; see below | 39 min |

**Which ports.** The amd64 pin, `daemonarchy-ports` `main` at `b785784`, is 10
commits **behind** the `daemonarchy` branch and lacks the aarch64 fixes
(ports#28 to #30: `chromium`, `aether`, `mise` and `edk2@bhyve` made
conditional). An arm64 desktop cannot be built from it. Both architectures must
build from one ports revision that has those fixes; the aarch64 chain used the
`daemonarchy` branch at ports#31, which also carries the drifted-port updates.

**The jail-version trap.** A first bulk dry run said "newer version of jail,
cleaning all packages" and would have rebuilt 763 of 1,404 packages (LLVM alone
takes over two hours). The jail made from the new sets records its version as
`16.0-CURRENT`; the src-method jails that built the repository recorded
`16.0-CURRENT 1600029`. Same OSVERSION, different string. Setting the copied
repository's `.jailversion` to the new jail's string cut the dry run to the 13
ports that really changed: cliamp, herdr, omacalc, omacut, omarchy-nvim, omasnap,
omawrite, owe, owe-lockfeed, ttfx, usage, aether and `daemonarchy`.

**Signing.** The release key stays on the amd64 signing host. The unsigned
feeds were moved there, signed with `pkg repo`, and only the catalogue files
came back. A pkg client given the public key the image pins accepts the
application feed (496 packages processed); a client given another key refuses it
("Invalid signature, removing repository").

**Closure.** The installer's aarch64 roots (`pkg bash sudo daemonarchy octopkg
wifi-firmware-kmod vulkan-loader mesa-dri`) resolve to 989 packages, 4.57 GiB of
archives, nothing unsatisfied: 437 packages from our feed and the ISO's own
repository, and 552 from `pkg.FreeBSD.org`'s aarch64 `latest`, which the shard
carries so the image does not depend on a moving upstream.
`parallel-fetch` with 4 connections moved the shard's 3.26 GB in 6 minutes
(about 9 MB/s), against about 1 MB/s for the guest's single-connection fetch.

**QEMU install.** `qemu-system-aarch64` 11.1.2 with HVF on an Apple silicon
host (12 cores), `virt` machine, AArch64 edk2, 6 GiB, virtio-gpu, the harness
`test-qemu.sh ARCH=aarch64` unmodified except that it now builds CIDATA with
`mformat` when `mkfs.fat` is absent and passes the installer's iterative package
cache (`PACKAGE_CACHE_URL` and the three metadata pins) through, so an unpublished
signed feed can be tested from a local HTTP server. The ISO had no closure mirror.
- The installer resolved 1,157 packages, fetched them (914 archives, 4 GiB),
  installed them in about 3 minutes, passed the package integrity check and
  powered off; the installed system booted under UEFI. Total 39 minutes.
- **23 checks passed**, including: account and groups, SDDM's user, session and
  theme, `sshd`, `avahi`, DHCP, `daemonarchy` installed, packaged files keep their
  owners, GSettings schemas, `/bin/bash`, the selected signed application feed and
  the staged defaults.
- **Two checks failed, both expected.** `sddm running` fails because the guest has
  no DRM/KMS driver (the base `virtio_gpu` VT driver is console only, and
  `graphics/virtio-gpu-qemu-kmod` is not in the package set), so the Wayland
  greeter cannot start. `updates from the signed Daemonarchy repository` fails
  because the installed system points at the public
  `packages-16-aarch64-1.4.1` URL, which is not published.
- **Two defects found and fixed** ([#167](https://github.com/jordanhubbard/daemonarchy/pull/167),
  [#176](https://github.com/jordanhubbard/daemonarchy/pull/176)). The installer
  selected `chromium`, which has no aarch64 package, so every arm64 install failed
  at package resolution (the earlier QEMU attempt stopped there). `parallel-fetch`
  crashed with `No module named '_sqlite3'` because the live image's Python has no
  sqlite module; the install fell back to one serial fetch, which is why the
  download took 34 minutes. The amd64 live image does not add `py312-sqlite3`
  either and was exposed to the same failure.
- Evidence kept on the QEMU host: `install.log` `4e4a263b…` and `boot.log`
  `168746…`.

**VirtIO GPU on aarch64 (2026-10-30).** Gap 2 above is smaller than recorded, but
not closed. `graphics/drm-612-kmod` already contains a VirtIO GPU DRM driver
(freebsd/drm-kmod PR 499, carried by the Daemonarchy patch), and upstream
`drm-kmod` lists aarch64 as supported; only the port's `ONLY_FOR_ARCHS=amd64`
stood in the way. With the port changed to build `dmabuf ttm drm virtio` on
aarch64 ([ports draft](https://github.com/jordanhubbard/daemonarchy-ports/pull/36)),
all four modules link for aarch64 with no warnings and a native `poudriere
testport` (stage-qa, check-plist, install and deinstall) passes in 19 seconds.
The installer side is [a draft](https://github.com/jordanhubbard/daemonarchy/pull/179).
In a QEMU guest under HVF the installer selected and installed the driver and
the graphics service loaded it, but **no DRM device attached**, so there was no
`/dev/dri` and SDDM stayed off:
- `std.virt` compiles `device virtio_gpu` (`vtgpu(4)`) into the arm64 GENERIC
  kernel. It claims the device at boot and the DRM driver (probe priority
  `BUS_PROBE_VENDOR`, written to outrank the base driver) is never offered it.
  On amd64 `vtgpu` is a module that is not loaded at boot, which is why it works there.
- `hint.vtgpu.0.disabled=1` stops `vtgpu` but leaves the device childless; the
  DRM module then does not attach.
- Forcing the handover at runtime (`devctl detach vtgpu0`, then `devctl set
  driver -f vtgpu0 virtio_gpu_drm`) froze the guest during the DRM attach
  (console: `vtgpu0: detached`, then garbage). Reloading the module froze it too.

The next step is an arm64 kernel configuration with `nodevice virtio_gpu`, which
is a kernel decision, and then a retest of the DRM attach. Until then the aarch64
image has no graphical desktop in a VM, and `sddm running` is the one expected
failure of the QEMU checks.

**A second install, with parallel fetch (2026-10-30).** The same harness against
a QA ISO built from current `main` (which has #176) completed in **11 minutes**,
against 39: the parallel fetch took 915 archives in about 2 minutes where the
single connection took 34. The same 23 checks passed and the same two failed.
`install.log` `5b4ca642…`, `boot.log` `7a7b92b6…` on the QEMU host.

**What this is not.** The ISO is a QA candidate, not the release image: it was
built without the closure mirror gate, from a product commit before the final
mastering, and the feeds it names are not published. There is no upgrade,
rollback, desktop-in-VM, debugging or laptop case, and no graphics: arm64 has no
KMS driver in the package set. The aarch64 image ships without a default browser
(`chromium`), without `aether` and without `mise` (omarchy's first-run skips it).

**To publish.** The operator approves the publish plans
(`package-feed-stage.py publish-plan`, 557 commands for the shard); then publish
the three feeds, rebuild the ISO at the final product commit with
`PACKAGE_MIRROR_URLS` and `REQUIRE_PACKAGE_MIRROR=yes`, rerun the QEMU install
against the public URLs (the signed-repository and defaults checks then pass), and
add the `.iso.xz` and its `.sha256` to the release record with
`architectures: [amd64, aarch64]`.

### Separate VMware test guests

Installer and boot tests never run inside the build worker: a failed test must
not disturb build state. For each case:

- Create a fresh guest, or revert a clean snapshot, with UEFI firmware, 4 vCPUs,
  8 GiB RAM and a 64 GiB NVMe disk.
- Attach the raw `.iso` (verified against its `.sha256`) as the CD.
- Use a `vmxnet3` NIC on NAT, or on a private bridged LAN for the
  network-debugging case.

With each result, record:

- the Mac model and macOS version;
- the VMware Fusion version;
- the guest firmware and virtual devices;
- the exact image SHA-256.

Cover install (whole-disk and shared-disk), boot, upgrade, rollback, desktop
and network debugging. The desktop case is expected to fail under VMware (gap 2).
Record that failure, and qualify the desktop in a QEMU or UTM guest with
virtio-gpu, or after a KMS port. A virtual result qualifies only virtual
operation. Apple silicon laptops are enlisted only after the virtual matrix
passes, with each model's execution mode recorded.

## Running aarch64 on Apple silicon

What is verified, and what is not:

- **QEMU with HVF (verified).** `qemu-system-aarch64` 11.1.2 on an M-series Mac,
  `-machine virt,gic-version=max -accel hvf -cpu host`, AArch64 edk2 as `-bios`,
  4 CPUs and 6 GiB, a 40 GB disk, a virtio network device and a virtio GPU. A full
  install took 11 minutes on a 12-core host with about 9 MB/s to
  `pkg.FreeBSD.org`. UTM drives the same QEMU. The harness needs only Homebrew:
  `brew install qemu mtools`, then `ARCH=aarch64 sh test-qemu.sh daemonarchy.iso`
  (it makes CIDATA with `mformat` when `mkfs.fat` is absent; `PACKAGE_CACHE_URL`
  and the three `PACKAGE_CACHE_*_SHA256` pins test an unpublished signed feed from a
  local HTTP server at `http://10.0.2.2:PORT`, the guest's name for the host).
- **VMware Fusion guest (build worker, console only).** The arm64 builder is a
  Fusion guest. It installs and builds everything, but the guest GPU has no FreeBSD
  driver, so it has only the EFI framebuffer and cannot run the desktop. Run QEMU
  inside it only with software emulation (TCG): the first boot test took hours.
- **No graphical desktop in any VM yet** (see the VirtIO GPU record above).
- **Bare metal is not supported.** There is no FreeBSD boot or GPU path for Apple
  SoCs, so an M1 to M4 laptop is a host for virtual machines, never a target.

Both a VMware guest and QEMU/HVF can run on one Mac: Fusion held the arm64
builder while HVF ran the install tests on the same host.

## What the operator supplies

- The Apple silicon Mac and its model, macOS and VMware Fusion versions.
- The FreeBSD arm64 `dvd1` ISO and its verified SHA-256, recorded before
  installation.
- The worker guest at the sizing above, reachable by SSH, and its admission
  through the worker capacity and identity checks.
- Review of daemonarchy-ports#28 (conditional `mise` and `edk2@bhyve`, and the
  Hyprland aarch64 PCH workaround), and a decision on gap 2 (the desktop
  qualification host).
- Review of daemonarchy-ports#30 (no `chromium` or `aether` dependency on
  aarch64).
- Builder capacity for a native aarch64 Chromium build. The 15.1 package
  builder ran out of time after about 59 hours.
- An aarch64-capable aether frontend distfile, published as a release asset.
- The aarch64 package feed release (`packages-16-aarch64*`) and its signing,
  and an aarch64 checkout feed.
- Host disk capacity for the worker. Its virtual NVMe has no TRIM, so a
  thin-provisioned disk only grows.
