# 1.4 live5 release candidate (unsigned) and hwtrace dev6 (2026-10-28)

This is a development record of an unsigned candidate for final hardware
checks. It does not qualify a release. Nothing was signed or published, and
nothing ran under LitAI custody. The images and evidence are kept on
`daemon.local` under `/usr/daemonarchy/live5-20261028`. The SHA-256 of every
evidence file, input, catalogue, image and VM log is in `evidence/SHA256SUMS`
there (`126bf8d1…`, 341 files; the installed 40 GiB VM disk is excluded). The
machine-readable summary is
[`verification/live5-candidate-20261028-development.json`](../verification/live5-candidate-20261028-development.json).

live5 was built the same way as [live4](testing-1.4-live4-20261027.md):
a full world, kernel and sets build from our own sources, a new jail, the
retained 1.3.1 packages and main's `build-iso.sh`. Unlike live4 and the
[lua4 repair](testing-1.4-live4-lua4-20261028.md), it needs no unmerged
source branch and no file replacement: every fix is merged.

## Inputs

- **Product:** `origin/main` at `2066e62ef899`, used unchanged (exported to
  `product/` with `.selected-commit`). Since live4 it adds:
  - #99 raw-block stick writes
  - #103 GPU and network roadmap
  - #104 MSI dev5 record
  - #105 lua4 record
  - #106 `daemonarchy_clock` clock floor
  - #107 no-driver console
- **Kernel, loader and world:** daemonarchy-src `daemonarchy` head
  `b582921ee928`, cloned fresh with `--depth 1` and built clean. It contains:
  - src#34 T2 NVMe fix
  - src#35 boottrace
  - src#36 splash
  - src#37 vtnet
  - src#38 raw-block boottrace writes, loader NVRAM self-report and
    breadcrumb ring
  - src#39 header fix
  - src#40 splash and netdebug without the table and math libraries,
    plus the stdlib guard
  - src#41 Boot Trace on `i`
- **Build method:** live4's recipe (`build-source-d63d77f4-20261024.sh`
  steps) at `-j8`: `buildworld`, `buildkernel` GENERIC, then
  `release ftp NOPORTS=1 NOSRC=1`.
  - Wall times: world 3 h 22 min, kernel 14 min, sets 9 min. All passed
    first time.
  - `__FreeBSD_version` is 1600029, as in live4.
  - The kernel identity is now `FreeBSD 16.0-CURRENT #0
    daemonarchy-b582921ee928`, because the source is now built from a
    branch checkout. `build-iso.sh`'s kernel-identity check accepts the
    `*-<revision>` form.
- **Sets** (`MANIFEST` `c301ca63…`, verified):
  - `base.txz` `ebf59269…`
  - `kernel.txz` `94850ef6…`
  - `lib32.txz` `56a39cab…`
- **Jail:** `16live5b5829`, created in an isolated Poudriere configuration
  from those sets, with `/usr/src` from the same tree, as `jail-live4.sh`
  did.
  - `jail-live5.sh` stopped with status 141 after the jail was complete. A
    `strings | grep -m1` under `pipefail` got SIGPIPE.
  - The remaining checks were run separately and pass
    (`jail-live5-finish.log`): `/usr/src` matches, and the jail kernel is
    the built kernel.
- **Packages:** The same isolated 1.3.1 repository as live1 to live4,
  copied from live1 and byte-identical to it and to live4's copy: 1,470
  files, `packagesite.pkg` `0756ee09…`.
  - No bulk was run, and nothing in main needed one: no package list or
    port changed. The new installer files (`daemonarchy_clock`, the
    `graphics-service` and rescue changes) are overlay shell scripts.
  - daemonarchy-ports amd64 is unchanged since live4.
  - The kernel-bound packages (DRM, GPU firmware, Wi-Fi and BCM4364
    modules) were built against the `d63d77f4` kernel, as for live4. The
    source changes since then do not touch a KBI those modules use. These
    candidates did not exercise them.
- **Checkout catalogue:** A development catalogue (`773adaac…`).
  - The ports tree is the 1.3.1 entry, unchanged.
  - The src tree is a receipt that `scripts/build-checkout-packages.py`
    made for `b582921ee928`: archive `29949ef0…`, 2 packages, tracking
    `daemonarchy`.
  - Those packages are unsigned and unpublished, and the catalogue still
    names the 1.3.1 checkout feed, as on live4. **Selecting the optional
    `/usr/src` download on live5 will fail.**

## Images

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `daemonarchy-1.4.0-live5-amd64.iso` | 3,506,483,200 (budget 3,758,096,384) | `c3c83983b4d40ea564913941cd5999220f2122466ce3d83cb39c5e75aa367e60` |
| `daemonarchy-1.4.0-live5-amd64.iso.xz` | 1,573,067,372 (limit 2,147,483,648) | `cab26478c38596d68f276694aedd091c816d4808cd4b04036232e8b25fde7707` |
| `daemonarchy-hwtrace-1.4.0-dev6-amd64.img` | 391,153,152 | `be39683ca8c0df40a9da272ce1fb86a7b3a2177f599d51d2cda08bafcfc61dc7` |

- **ISO build:** `build-iso.sh` took 26 minutes, with
  `NAME=daemonarchy-1.4.0-live5-amd64` and
  `PREVIEW_LABEL="1.4 preview live5"`.
  - The ISO repository has 263 packages and the live root 267, as on live4.
  - The trim took `/usr/local` from 2748 to 1641 MiB.
  - `build-iso.sh` checked that the `.xz` decompresses to the ISO.
- **hwtrace image:** main's `build-hwtrace-image.sh` built it from the
  live5 ISO, the GENERIC kernel, the `loader_lua.efi` built with it and
  `stand/lua` from the same tree, with `-V 1.4.0-dev6`.
  - dev5 was the last name used (MSI capture, #104).
  - The queue is empty: `next 0001 of 0`. `SLOTS.MAP` lists 201
    contiguous files.
  - A `-S` serial copy, `1185839b…`, was built for the VM check only and
    is not delivered.
- **Delivered:** `/home/jkh/daemonarchy-isos/` holds the three files and
  their digest files. The ISO's `.sha256` lists both the ISO and the
  `.xz`. All copies were verified after transfer.

## What is in the image

`evidence/iso-content-checks.txt`, `evidence/kernel-checks-user.txt`:

- **Same kernel and loader everywhere.**
  - The live `/boot/kernel/kernel` (`bbceb537…`) is the built kernel, and
    is identical to the one in `kernel.txz`.
  - The live `/boot/loader.efi` (`95f624f1…`) is identical to the
    `loader_lua.efi` built with it and to the one in `base.txz`.
  - The ISO's sets and `MANIFEST` are the build's.
- **T2 NVMe quirk:** the `0x2005106b` entry has quirks `0x24f0`, so
  `QUIRK_APPLE_ACK_EACH_CPL` is set.
- **vtnet:** the header tag (2-byte alignment) is created with flags `0x6`,
  which is `BUS_DMA_COHERENT | BUS_DMA_ALLOCNOW`.
  - Run under `sudo`, the check script picked GNU `objdump` from
    `/usr/local/bin` and printed no vtnet line.
  - Rerun with the base `objdump`, it reports `0x6`
    (`kernel-checks-user.txt`). The disassembly shows the same.
- **boottrace:** `dbt_start`, `dbt_sysinit`, `dbt_device`, `dbt_hook`,
  `dbt_complete`, `dbt_panic` and `debug.boottrace` are present.
- **Loader Lua:**
  - `splash.lua` is `3f905495…`, `netdebug.lua` `c9da2b5a…` and
    `menu.lua` `5d16efef…`. These are the digests the lua4 repair
    installed.
  - All 19 source-tree files are byte-identical to daemonarchy-src
    `b582921ee928`. The 20th file is the product's
    `brand-daemonarchy.lua`.
  - `menu.lua` gives Boot trace `{"i", "I"}`. `brand-daemonarchy.lua`
    gives the live desktop `{"t", "T"}`.
- **Installed-system Lua:** every `boot/lua` file in `base.txz` equals the
  live ISO's. The installed system therefore gets the fixed loader Lua,
  which the lua4 record left open. The installation below confirms it.
- **Stdlib guard on the image:**
  - `stand/lua/tests/stdlib-test.lua` from `b582921ee928` ran against the
    ISO's own 20 `/boot/lua` files and printed "PASS: 20 loader Lua files
    use no missing standard library".
  - `splash-test.lua` passed against the ISO's `splash.lua`.
- **Clock floor:** `/usr/local/share/daemonarchy-installer/clock/daemonarchy_clock`
  (`f547069d…`) equals the product file. The installer copies it to
  `rc.d` and writes the `cron.d` entry.
- **No-driver console:** `graphics-service` and `daemonarchy-rescue`
  equal the product files: the `nodriver` marker and the "No supported
  desktop graphics driver" reason.

## Tests

- **Runtime audit:** `tests/live-image-runtime.sh` on FreeBSD passed. It
  covers live tools and payloads, desktop wiring, GTK 3.24 and every
  retained ELF dependency.
- **Native FreeBSD 16, as root on `daemon.local`, from the exact product
  tree:** all of the following pass.
  - live4's 15 tests
  - the new `clock-floor`
  - `graphics-startup` and `rescue-console`
  - the memory-disk tests `disk-layout`, `shared-disk`,
    `boot-environment-mounts`, `rescue-setup` and `checkout-packages`
  - `efi-boot-image` and `rescue-boot-image`, built from the live5 jail
- **Not run:** `pkg-repo-dependencies.sh`, because it signs a fixture.
- **Linux:** the same sweep as live4 gives the same result for every test,
  plus `clock-floor.sh`, which passes.
  - The portable tests pass.
  - The FreeBSD-only tests refuse to run.
  - `qemu-desktop.py` and `qemu-unlock-geli.py` are harness modules.
  - `release-input-graph.py` and `release-qa-plan.py` need the
    `literate_ai` module.

## VM boots

Every guest was torn down afterwards, and no memory disks remain.

### bhyve on `daemon.local` (UEFI, 2 vCPUs, 4 GB, 16 GiB target)

The driver is live4's `live-vm-case.py`, revised as below. All three
revisions are kept. The target's SHA-256 was
`07d217ebccc55480b7afa191674ec5da87f2d14efbc04dbc7e40efe345f16776` before
and after every case.

| Case | Result |
| --- | --- |
| TUI default, attempt 1 (driver r1) | **Harness failure, kept** (`vm/tui-attempt1`). The serial copy of the loader output stopped after 5,166 bytes, inside the splash. A VNC capture showed the full menu, but with no autoboot countdown. The loader appeared stalled on the serial write. The driver timed out and destroyed the guest. |
| TUI default (r2) | **Pass.** This time the serial menu arrived after 9 s, and the default entry autobooted. Observed: <ul><li>Kernel `#0 daemonarchy-b582921ee928`. `debug.boottrace.steps` 0.</li><li>`launch` and `configurator` on `ttyv0`.</li><li>Root `0755`, and the live account works.</li><li>The guest's `/boot/lua` digests are the fixed ones.</li><li>The tmux install screen's dry run exited 0.</li><li>On `ttyu0`, `sound status` printed `mode=off reason='serial console'`.</li></ul> |
| Live desktop, key **T** (r3) | **Pass.** `t` was sent within the 3 s countdown, on serial and through the video console (VNC). Observed: <ul><li>`daemonarchy_live=YES`.</li><li>tmpfs over `/live`, `/etc`, `/usr/local/etc`, `/root` and `/home`, and the `ready` marker.</li><li>No unionfs.</li><li>`live-gpu` reported that no supported desktop GPU was found, and the boot fell back to the TUI.</li><li>Boottrace inactive (0 steps). On live4, `T` booted the traced entry.</li></ul> |

- **Driver revisions:**
  - r1: live4's driver with `T` for the live case, CLOCAL and no software
    flow control on the serial side.
  - r2: selects the entry through the video console with a small RFB
    client (`vnc-key.py`, `vnc-shot.py`).
  - r3: sends the key the moment the menu appears.
- **The splash on serial:** unlike QEMU, bhyve's firmware also copies the
  splash ("summoning the daemons…") to the serial port. This is the output
  that stalled once. It matches the lua4 record's note about its own
  serial harness.

### Full unattended install in bhyve (`test-bhyve.sh`)

`evidence/test-bhyve-live5.sh` is main's `test-bhyve.sh`. It added
clock-floor and no-driver checks, plus a VNC capture of `ttyv0` before
shutdown. It ran with 4 vCPUs, 3 GB and a 40 GB disk, from a CIDATA answer
file, using the public 1.3.1 package feed.

- **Install:** 2,846 s, then a clean power-off. Every existing disk check
  passed. These new checks also passed:
  - `/usr/local/etc/rc.d/daemonarchy_clock` (mode 0555, equal to the
    product file)
  - `/usr/local/etc/cron.d/daemonarchy-clock` (`*/15 … root …
    daemonarchy_clock save`)
  - `/var/db/daemonarchy/clock`
  - the installed `daemonarchy-graphics` has the no-driver path
- **Installed boot** (UEFI, bhyve framebuffer, which has no DRM driver),
  checked over SSH (`vm/install/installed-checks.txt`):
  - Installed kernel `#0 daemonarchy-b582921ee928`, booted by UEFI.
  - Installed `/boot/lua` is the fixed set, including Boot trace on `i`,
    with `loader_brand=daemonarchy`.
  - `daemonarchy_graphics_modules=""`.
  - `/var/run/daemonarchy-graphics.nodriver` is present, and `.ready` is
    absent.
  - `daemonarchy-graphics.log`: "No supported desktop graphics driver for
    this display; staying on the console."
  - `/etc/rc.conf.d/sddm` turned SDDM off. `service sddm status`: "sddm is
    not running". No Hyprland, and no DRM module loaded.
  - `/var/log/daemonarchy-rescue.log` records the reason ("No supported
    desktop graphics driver was found for this display, so the graphical
    desktop is off. …").
  - `service daemonarchy_clock rcvar` shows the service enabled, and
    `service daemonarchy_clock save` advanced the record.
  - The install-time checkout checks (ports and src not selected) and the
    UEFI and sshd checks passed. The guest powered off.
- **Clock:** the installed system's first syslog entry is at 10:37:56Z.
  - That is 4 s after the record that the installer wrote (10:37:52Z),
    although the boot happened about 47 min later.
  - By the time of the SSH checks, the clock read the correct 11:25:54Z.
  - This is consistent with the floor raising a bhyve RTC that the guest
    reads as local time, followed by ntpd's correction.
  - The console line that would prove it ("Clock was behind…") goes to the
    video console and was not captured.

### QEMU 8.2 / OVMF (TCG) on the Linux host

- **Welcome case** (`qemu-live5-case.py`, live4's driver renamed). It ran
  with an HDA codec on a null backend, a serial console and a VGA console.
  It passed, and the target was unchanged.
  - **Welcome screen:** "Omarchy's desktop spliced onto FreeBSD's daemon ·
    1.3.1 (1.4 preview live5)" appeared about 80 s after the login prompt
    (`welcome-2.png`).
  - **Sound:** `pcm0` attached, and the vt installer's player ran
    (`sound.py serve`, `mode=on`).
  - **Silent on serial:** from the root login on `ttyu0`, `sound ensure`
    started no second player. `sound status` printed
    `mode=off reason='serial console'`. Nothing was heard, because the
    backend was null.
- **Splash on a video console:**
  - **VGA only, no serial port** (`qemu-vga-splash.py`): of 1,478 frames,
    frames 56–72 show the wordmark drawing in, the animated mascot and
    the "summoning the daemons…" tagline (`f0057.png`, `f0062.png`,
    `f0070.png`). The branded menu follows (`f0084.png`, with
    `T` on "Try Daemonarchy" and `i` on "Boot trace"). There was no Lua
    error.
  - **With a serial port** (the welcome case): the splash also draws on
    VGA, but OVMF's text console prints the unhandled cursor-hide sequence
    as a literal `[?25l` above the wordmark (`loader-050.png`). This is
    cosmetic.
  - The menu box title still reads "Welcome to FreeBSD".

### hwtrace dev6 under QEMU/OVMF

The `-S` copy was attached as SATA, with fresh `OVMF_VARS_4M.fd`, and run
with `qemu-stick-test.py --silence 150`. The queue matched dev3's.

| Experiment | Queue | Filed trace |
| --- | --- | --- |
| 0001 `hang-configure` | `read-conf /boot/d/1`, `debug.boottrace.test_hang=configure_first` | Silent, then reset after 150 s. `0001.TXT` is INCOMPLETE, with last step `#1680 sysinit: configure_first`. |
| 0002 `normal` | — | Complete: `#3800 boot complete`. `DUMPS/0002/` holds 8 files, including dmesg, sysctl and acpidump output. |

- The loader wrote through raw blocks (`SLOTS.MAP`, 201 files, read back
  through the whole disk). It stopped with `HARDWARE TRACE: STOPPED`,
  "Experiment 0002 reached init".
- `fsck.fat -n` found DATRACE clean.

## Findings

1. **The rescue reason is on screen only briefly.** `daemonarchy-rescue`
   prints the no-driver reason. It then waits up to 15 s for boot messages,
   and `rescue_menu` clears `ttyv0` before it draws the menu.
   - The VNC capture of the installed system (`installed-ttyv0.png`) shows
     only the menu.
   - The reason survives in `/var/log/daemonarchy-rescue.log`. Menu entry
     3, "View installation and boot logs", does not show that file.
   - Keeping the reason above the menu would make #107's explanation
     visible. This is not fixed here.
2. **The bhyve serial copy of the splash can stall the loader.** It
   happened once in three bhyve boots. The video console showed the menu
   and no countdown.
   - QEMU does not copy the splash to serial.
   - A physical machine with a serial console redirected by its firmware
     could behave the same way. That is worth one look on hardware with
     console redirection.
3. **OVMF prints `[?25l`** above the splash when a serial port is present.
   This is cosmetic.

## Not covered

- Desktop rendering (no DRM GPU in these VMs) and the graphical installer.
- Real audio.
- The kernel-bound GPU and Wi-Fi modules on this kernel.
- Physical MacBookPro16,1 (T2 NVMe, clock floor on real T2 hardware) and
  MSI runs.
- Secure Boot.
- The optional `/usr/src` checkout (the catalogue feed limitation above).
- hwtrace dev6 on physical USB.
- Signing and publication, which are left to the operator.
