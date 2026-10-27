# LIVE-001 live desktop under QEMU/VirGL (2026-10-26/27)

This is a development record for [LIVE-001](roadmap/active-work.md#live-001-offer-a-live-desktop-from-the-installer-media-without-touching-the-disk).
It continues [the native build and bhyve record](testing-1.4-live-desktop-20261026.md).
It does not qualify a release, and nothing was published.

## Host and limits

- **Host and guest.** The madmax host (RTX 5090, NVIDIA 595.99.02) ran QEMU
  10.2.1/KVM with `virtio-vga-gl` and `egl-headless` on `/dev/dri/renderD128`.
  Each guest had 4 vCPUs, 8 GB, user-mode networking and a 40 GiB sparse
  virtio target disk. All files were in `~/live1-virgl-20261026` on madmax.
- **Firmware.** The formal cases used `OVMF_CODE_4M.secboot.fd` with
  unenrolled variables, which presents SecureBoot=0, like a PC with Secure
  Boot turned off. The first live1 boots used plain `OVMF.fd`.
- **Capturing the screen.** QMP `screendump` works for the loader and console.
  Once the GL scanout is active it reports "no surface", so screenshots were
  read back over VNC on 127.0.0.1 by `evidence/vmctl.py`. Input went through
  QMP `sendkey`/`input-send-event`. State was read with root logins on the
  guest serial console.
- **Render-node access.** QEMU ran as `jkh`, which needed a temporary ACL,
  `setfacl -m u:jkh:rw /dev/dri/renderD128`. A device ACL refresh on the host
  dropped it once, at 18:15:46 local time; it was re-applied for the
  installed-system boot. It was removed at the end, and `getfacl` then showed
  only `user::rw-`, `user:gdm-greeter:rw-`, `group::rw-` (render), `mask::rw-`
  and `other::---`.
- **Cleanup.** No existing madmax VM, disk or network was touched. Guests were
  torn down, and their disk images and ISOs were deleted. About 3.3 MB of
  evidence remains, listed with SHA-256 values in `SHA256SUMS` (whose own
  SHA-256 is `52d3221b…98ce3`).

## live1 (`4323a3b2…`): the desktop did not start

- **The live entry worked, but the desktop did not.** The loader menu offered
  the live entry, and T selected it (`vm/live/menu-after-t.png`). The
  in-memory file systems were ready. However, `live-gpu` could not extract the
  DRM modules: pkg stores absolute member names, and bsdtar exits nonzero for
  any `--include` pattern that matches nothing. The session therefore fell
  back to the text installer even with a working VirtIO GPU.
- **Disk digest.** The target was unchanged after the live boot:
  `2109856c…` before and after. That value is the digest of the empty 40 GiB
  image.
- **Network parity on live1.** Two paths reached identical decisions on QEMU
  user networking: `live-backend network-check`, run as the `live` account
  through sudo, and the text installer's own `network_bringup_ui`. Both chose
  dhcp, `vtnet0`, DNS `10.0.2.3,1.1.1.1,1.0.0.1` from DHCP, and a usable clock.
- **Diagnostic boot (not exact-image evidence).** With only `live-gpu` patched
  (`evidence/live-gpu.fixed`, `0b4c06b0…`), the guest loaded `virtio_gpu_drm`
  with VIRGL, ran Hyprland as `live`, and showed the GTK installer through its
  review page. Its trial install exposed two more defects:
  - A pipefail `| grep -q` SIGPIPE in `live-backend` rejected a valid timezone.
  - A silent exit 1 when the firmware lacks a SecureBoot variable.

All three defects are fixed in `358b16b`, with regression tests.

## live2 (`358b16b`)

Built on daemon.local from the same verified, isolated 1.3.1 inputs as live1:
the runtime audit passed, and the trim lines were unchanged
(`2746 MiB` before, `1640 MiB` after).

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `daemonarchy-1.4.0-live2-amd64.iso` | 3,504,906,240 | `1bd26fa5d6c501d1f242e543a60b87a8a341dfdda5e6febe187f07a48cdabf82` |
| `daemonarchy-1.4.0-live2-amd64.iso.xz` | 1,573,079,904 | `bb7ade9dec2f26a5c3b59d81d247e06722ac97e41256e141b0d65f64865b0221` |

The ISO hash was verified on madmax after copying. The build evidence is in
`/usr/daemonarchy/live2-20261026/evidence/SHA256SUMS` on daemon.local
(`b69c0b43…`).

### Case results

| Case | Result | Evidence (madmax `vm/…`) | Target digest |
| --- | --- | --- | --- |
| 1. Hyprland renders the live desktop | **Pass.** T booted the live entry. `virtio_gpu_drm` loaded with VIRGL, and `/dev/dri/card0` and `renderD128` appeared. Hyprland, seatd and the GTK installer ran as `live` on `v0`. A foot terminal tiled beside the installer. tmpfs copies on `/etc`, `/usr/local/etc`, `/root`, `/home` and `/live`. No unionfs, no swap, no pools. | `l2-live/02-desktop.png` `53b915c4…`, `03-terminal.png` `dd02215e…` | `2109856c…` before and after |
| Live-boot digest under VirGL | **Pass.** Powered off from the live session without installing. | `l2-live/target.before`, `target.after` | unchanged |
| 2. Compositor-failure fallback | **Pass.** At the loader prompt: `daemonarchy_live=YES` and `daemonarchy_live_test=compositor-failure`. The GPU step passed (`virtio_gpu_drm`, DRM nodes) and seatd started. The compositor (`false`) exited 1; the log reads "Live desktop ended: status 1". The console showed "The live desktop could not start: the compositor exited with status 1 … No disk has been changed.", then the text installer greeter. | `l2-compositor/02-after-boot-1.png` `fedc8d8a…`, `03-fallback.png` `b78daa5a…` | `2109856c…` before and after |
| 3. Network-page parity | **Pass.** Same decisions as live1 from both paths, now on the exact live2 image. The GTK network page showed each step's report (adapter, lease, primary, DNS, clock and firmware), the DNS-server entry and the adapter controls. | `l2-live/04-network-page.png` `a7f66a60…`; serial log | n/a |
| 4. Graphical whole-disk install | **Pass.** The GUI went welcome → keyboard → account → network → options → disk (`vtbd0`) → review. Install is refused until the confirmation is ticked. The install started at 01:06:36Z, with 931 packages to fetch and one retried download, and reported "Daemonarchy is installed." at about 02:10Z, status 0. The GUI's Power off then shut the guest down. The installed system booted from the disk alone to the SDDM greeter (hostname `daemonarchy`), and the account's password logged in to the full Daemonarchy desktop. | `l2-install/06-review.png` `10ca7981…`, `12-result.png` `27456a08…`, `20-installed-boot.png` `0a6f87f5…`, `21-installed-desktop.png` `fe0a17be…`, `install-log-summary.txt` `4bb67ff7…` (guest log `36dde40e…`, 8,327 lines) | `2109856c…` before and at confirmation; `6baeaacf…` after install |

## Observations

- **No fetch meter in either front-end.** During package fetch, pkg writes
  `Fetching x: .......... done` when its output is not a terminal. The shared
  dashboard parser counts only `Fetching x: 100%` lines, so the fetch stage
  shows "No measured total" in both the graphical and text installers. The
  disk and base-archive meters worked. This predates LIVE-001.
- **Open question for the operator: firmware without a SecureBoot variable.**
  `secureboot_detect_enforcement` in `secureboot-options` decides this:
  unless the loader kenv `daemonarchy_secureboot` is set, it reads the EFI
  `SecureBoot` variable and refuses to install when the variable cannot be
  read.
  - Plain `OVMF.fd` has no such variable. Older PCs and some Mac EFI may not
    expose it either.
  - The verified loader in the signed boot bundle exports that kenv from
    firmware state (`secureboot/README.md`), so this
    path is mainly reached by images built without it.
  - This PR only adds an explicit message; the policy is unchanged.
  - The operator should decide whether a missing variable means "Secure Boot
    off".
  - **Resolved after this record:** the operator ruled that a missing
    variable means Secure Boot off. The installer now proceeds with an
    explanatory note; a variable with an unknown value is still refused.
