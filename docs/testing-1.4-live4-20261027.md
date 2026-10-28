# 1.4 live4 development candidate and hwtrace dev3 (2026-10-27)

This is a development record. It does not qualify a release. Nothing was
signed or published, and nothing ran under LitAI custody. The images and
evidence are kept on `daemon.local` under `/usr/daemonarchy/live4-20261027`.
The SHA-256 of every evidence file, set, catalogue and image is in
`evidence/SHA256SUMS` there (`3ed6ac7d…`). The machine-readable summary is
[`verification/live4-candidate-20261027-development.json`](../verification/live4-candidate-20261027-development.json).

live4 is the first 1.4 image with a kernel and loader built from our own
sources. live1 to live3 reused the 1.3.1 sets.

## Inputs

- **Product:** `origin/main` at `17123ca1d692` (#95 boot-trace tools and
  `build-hwtrace-image.sh`, #96 release sync, #97 installer charm and
  sound, #98 aarch64 record). The build used it unchanged.
- **Kernel, loader and world:** daemonarchy-src `74f81f1949d5`. That is
  the `daemonarchy` head `f4d86dc786eb` (src#34 T2 NVMe completion fix,
  #35 boottrace, #36 loader splash, #37 vtnet bounce zone) plus one header
  fix, on branch `fix/boottrace-header-types`, which is not merged:
  - `buildworld` at `f4d86dc786eb` stopped in `tools/build/test-includes`
    with `sys/daemonarchy_boottrace.h:68: unknown type name 'uint16_t'`.
    The new header is not self-contained. The kernel-only builds in #35
    could not show this.
  - The fix adds `#include <sys/types.h>`. Attempt 2 reused attempt 1's
    objdir with `-DNO_CLEAN`. Attempt 1's log is kept in
    `evidence/attempt1/`.
- **Build method:** The same recipe that reproduced the 1.3.1 sets byte for
  byte (`/usr/daemonarchy/build-source-d63d77f4-20261024.sh`), at `-j8`:
  `buildworld`, `buildkernel` GENERIC, then `release ftp NOPORTS=1 NOSRC=1`.
  - Wall times: world 2 h 34 min, kernel 20 min, sets 9 min.
  - `__FreeBSD_version` is 1600029, the same as 1.3.1.
- **Sets** (`MANIFEST` verified):
  - `base.txz` `24341ec5…`
  - `kernel.txz` `4c18fb83…`
  - `lib32.txz` `391904eb…`
- **Jail:** `16live4f4d86`, created in an isolated Poudriere configuration
  from those sets, with `/usr/src` from the same tree. The name predates
  the header fix. The kernel identity is
  `FreeBSD 16.0-CURRENT #0 74f81f1949d5`.
- **Packages:** The same isolated 1.3.1 repository that live1 to live3 used
  (the 1.3.1 selection plus sudo, ports `b785784`, tree `macbookefb8` with
  the `brcmfmac131fix` overlay).
  - It was copied from live1 and is identical: 1,470 files,
    `packagesite.pkg` `0756ee09…`.
  - No bulk was run. ports#30 (`ea7ff722`) changes only aarch64 metadata.
  - The kernel-bound packages (DRM, GPU firmware, Wi-Fi and BCM4364 modules)
    were built against the `d63d77f4` kernel. The kernel changes since then
    touch no KBI those modules use: they are private nvme and debugnet
    fields and an `efi_ops` member appended at the end. This candidate did
    not exercise those modules.
- **Checkout catalogue:** A development catalogue (`8f37f65a…`).
  - The ports tree is the 1.3.1 entry, unchanged.
  - The src tree is a receipt that `scripts/build-checkout-packages.py`
    made for `74f81f1949d5`, so `build-iso.sh`'s kernel-identity check
    passes.
  - The two src checkout packages are unsigned and unpublished, and the
    catalogue still names the 1.3.1 checkout feed. **Selecting the optional
    `/usr/src` download on live4 will fail.** The ports download is
    unaffected.

## Images

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `daemonarchy-1.4.0-live4-amd64.iso` | 3,505,987,584 (budget 3,758,096,384) | `56684b8d877a51b34a3027252abd2c55c63598112ea0416479e5a0654f0ea31e` |
| `daemonarchy-1.4.0-live4-amd64.iso.xz` | 1,572,748,628 (limit 2,147,483,648) | `e8dbd825557b00830f97475803c2537f75f6bd2531beea9c5c5c71de5f32fda0` |
| `daemonarchy-hwtrace-1.4.0-dev3-amd64.img` | 391,153,152 | `f4aec0e6a2e205cf0ca268bb9a2aa3eb12ec0db0af1e1ac5e2fce9e83f3ef99a` |

- **ISO build:** `build-iso.sh` took 33 minutes, `NAME=daemonarchy-1.4.0-live4-amd64` and
  `PREVIEW_LABEL="1.4 preview live4"`. The ISO repository has 263 packages and
  the live root 267; the trim took `/usr/local` from 2747 to 1640 MiB.
- **hwtrace image:** main's `build-hwtrace-image.sh` built it from the live4
  ISO, that ISO's GENERIC kernel, the `loader_lua.efi` built with it and
  `stand/lua` from the same tree, with `-V 1.4.0-dev3`. A `-S` (serial)
  copy, `97f402cc…`, was built for the VM check and is not delivered.

## What is in the image

`evidence/iso-content-checks.txt` and `evidence/kernel-checks.py`:

- **Same kernel and loader everywhere.** The live `/boot/kernel/kernel`
  (`88f70f8d…`) is the built kernel and is identical to the one in the
  ISO's `kernel.txz`. The live `/boot/loader.efi` (`d2762e86…`) is identical
  to the one in `base.txz`. The ISO's `MANIFEST` is the build's.
- **T2 NVMe quirk:** in the `nvme_pci.c` table, the entry for `0x2005106b`
  ("Apple ANS2 NVMe Controller (T2)") has quirks `0x24f0`, so
  `QUIRK_APPLE_ACK_EACH_CPL` (`0x2000`) is set. In the 1.3.1 kernel it was
  `0x04f0`.
- **vtnet fix:** `vtnet_attach` creates the header tag (2-byte alignment)
  with flags `0x6`, which is `BUS_DMA_COHERENT | BUS_DMA_ALLOCNOW`. In the
  1.3.1 kernel the flags were `0x4`.
- **boottrace:** `dbt_start`, `dbt_sysinit`, `dbt_device`, `dbt_hook`,
  `dbt_complete`, `dbt_panic` and the `debug.boottrace` tunable are
  present. All are absent from 1.3.1.
- **Loader:** It reports Revision 3.1, built on the day of this record.
  `boot/lua/splash.lua` and the splash call in `loader.lua` are present,
  `loader_brand="daemonarchy"` is set, and the menu has the new
  "Boot Trace" entry.

## Tests

- **Runtime audit:** `tests/live-image-runtime.sh` on FreeBSD passed. That
  covers live tools and payloads, the desktop wiring, GTK 3.24, tmux 3.8
  and every retained ELF dependency.
- **Native FreeBSD 16, as root on `daemon.local`, from the exact product
  tree:** all of the following pass.
  - `installer-progress.py` with the real pkg fetch, `live-installer.py`,
    `vt-console-colors.py` and `boottrace-tools.py`
  - `secureboot-options`, `installer-charm`, `installer-clock` and
    `live-desktop`
  - remote-debug background, session, reboot, observe and cli
  - `live-image-budget` and `release-set-cache`
  - the memory-disk tests `disk-layout`, `shared-disk`,
    `boot-environment-mounts`, `rescue-setup` and `checkout-packages`
  - `efi-boot-image` and `rescue-boot-image`, built from the live4 jail's
    `/boot`
- **Not run:** `pkg-repo-dependencies.sh`, because it signs a fixture
  repository and this candidate signs nothing.
- **Linux:** every portable test passes. The FreeBSD-only tests refuse to
  run there.
- **EFI boot-chain fixture:** `efi-boot-image.sh` made a ZFS disk image from
  live4's `/boot`. Under QEMU/OVMF with `console=comconsole`, the live4
  loader ran its Lua, loaded `/boot/kernel/kernel` and stopped at the
  prompt, as the fixture expects. No splash appeared.

## VM boots

Every guest was torn down afterwards, and no memory disks remain.

### bhyve on `daemon.local` (UEFI, 2 vCPUs, 4 GB, 16 GiB target)

The cases use live3's serial driver, extended for live4. The target disk's
SHA-256 was `07d217eb…` before and after every case.

| Case | Result |
| --- | --- |
| TUI default (Enter) | **Pass.** `launch` and `configurator` ran on `ttyv0`. The kernel was `#0 74f81f1949d5`. The tmux install screen's dry run drew every stage, the ticker and the meters, then exited 0. On `ttyu0`, `sound ensure` started no player and `sound status` printed `mode=off reason='serial console'`. |
| Live desktop, entry **2** | **Pass.** `daemonarchy_live=YES`, the tmpfs layers and `ready` were present, there was no unionfs, the GPU fallback went to the TUI, and storage was untouched. This matches live1 to live3. |
| Live desktop, key **T** | **Defect.** `T` booted the new Boot Trace entry (`debug.boottrace.status: 2`, 3406 steps, 8 NVRAM writes) and not the live desktop, so the disk stayed untouched. Kept as `vm/live-key-t`. |

### QEMU 8.2 / OVMF (TCG) on the Linux host

The case had an Intel HDA codec with a null audio backend, a serial
console and a VGA console, and used `qemu-live4-case.py`. It passed, and the
target was unchanged.

- **Welcome screen:** "Omarchy's desktop spliced onto FreeBSD's daemon ·
  1.3.1 (1.4 preview live4)" appeared about 80 s after the serial login
  prompt (`welcome-2.png`).
- **Sound:**
  - `pcm0` attached. The vt installer's player ran (`sound.py serve`,
    status `mode=on`).
  - From the root login on `ttyu0`, `sound ensure` with its own runtime
    directory started no second player. `sound status` printed
    `mode=off reason='serial console'`.
  - The audio backend was null, so nothing was heard.
- **Splash on serial:** The serial log has no splash wordmark, mascot or
  tagline before the menu. That holds on bhyve too.

### hwtrace dev3 under QEMU/OVMF

The `-S` copy was attached as SATA, with a fresh `OVMF_VARS_4M.fd`, and
driven by `tools/boottrace/qemu-stick-test.py --silence 150`.

| Experiment | Queue | Filed trace |
| --- | --- | --- |
| 0001 `hang-configure` | `read-conf /boot/d/1`, `debug.boottrace.test_hang=configure_first` | Silent, reset after 150 s. `0001.TXT` INCOMPLETE, last step `#1680 sysinit: configure_first`. |
| 0002 `normal` | — | Complete: `#3800 boot complete: root mounted, executing init`. `DUMPS/0002/` holds dmesg, kenv, sysctl, kldstat, pciconf, devinfo and acpidump output. |

- **Next boot:** the loader showed `HARDWARE TRACE: STOPPED`, "Experiment
  0002 reached init".
- **DATRACE:** `fsck.fat -n` found it clean.

## Defects found

1. **The loader splash never draws.** The loader's Lua is built without
   `ltablib.c` and `lmathlib.c` (`stand/liblua/Makefile`), and
   `splash.lua` calls `math.max` and `table.concat`.
   - `splash.run()` contains the error, so the boot continues, but nothing
     is drawn on any console.
   - On a video-only QEMU console (no serial port), frames dumped about
     every 0.1 s showed the loader output and then the menu, with no
     splash frame between them. At the prompt, `loader_brand=daemonarchy`
     and `console=efi`, and `daemonarchy_splash` was unset, so the splash
     should have drawn.
   - `stand/lua/tests/splash-test.lua` ran under full Lua 5.4.
   - Fix: daemonarchy-src branch `fix/splash-loader-libs` (`4b8b1324`,
     not merged). It joins lists by hand, and its test hides `table` and
     `math`. That test fails on the merged `splash.lua` and passes with the
     fix.
   - `stand/lua/netdebug.lua` uses `table.insert` and `table.unpack` the
     same way. Its menu path was not exercised here.
2. **`T` is taken twice in the loader menu.** src#35's "Boot Trace" entry
   aliases `t`/`T`, and so does the product's "Try Daemonarchy (live
   desktop)" entry in `brand-daemonarchy.lua`. Both letters are
   highlighted. The menu runs the Boot Trace entry, so on live4 the live
   desktop is reachable only as entry 2. One of the two aliases needs to
   change.
3. **`buildworld` failed at the merged `daemonarchy` head** (above). The
   fix is on `fix/boottrace-header-types`.

The permission check refused to open a daemonarchy-src pull request for
the header fix, so no pull request was attempted for the splash fix. Both
branches are pushed and ready to open.

## Not covered

- An installation.
- Desktop rendering (no DRM GPU in these VMs).
- Real audio.
- The kernel-bound GPU and Wi-Fi modules.
- Physical MacBookPro16,1 NVMe and MSI runs.
- Secure Boot.
- The optional `/usr/src` checkout.
- `hwtrace` dev3 on physical USB.
