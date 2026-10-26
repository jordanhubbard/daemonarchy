# aarch64: inventory and worker bring-up

[ARCH-001](roadmap/active-work.md#arch-001-add-aarch64-as-a-second-supported-architecture-for-140)
([issue #62](https://github.com/jordanhubbard/daemonarchy/issues/62)) adds
aarch64 alongside amd64 for 1.4.0. This page records the read-only inventory of
2026-10-26 and the plan for the first native aarch64 worker. **No aarch64 world,
kernel, package, image, VM or laptop result exists yet.** Nothing here
qualifies aarch64, and no amd64 result stands in for one.

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
       builds without PCH on aarch64 only. This is a candidate fix until a native
       aarch64 build confirms it.
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
   UEFI-only path (see below), which no native run has qualified yet.
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

## What the operator supplies

- The Apple silicon Mac and its model, macOS and VMware Fusion versions.
- The FreeBSD arm64 `dvd1` ISO and its verified SHA-256, recorded before
  installation.
- The worker guest at the sizing above, reachable by SSH, and its admission
  through the worker capacity and identity checks.
- Review of daemonarchy-ports#28 (conditional `mise` and `edk2@bhyve`, and the
  Hyprland aarch64 PCH workaround), and a decision on gap 2 (the desktop
  qualification host).
- Builder capacity for a native aarch64 Chromium build. The 15.1 package
  builder ran out of time after about 59 hours.
- The aarch64 package feed release (`packages-16-aarch64*`) and its signing.
