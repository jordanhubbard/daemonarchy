# Hyprland in QEMU: VirtIO DRM development checks

Tested 2026-10-16. This records an isolated driver experiment, not a released
image or qualification of every hypervisor.

The guest was the retained preview.13 UEFI installation, booted with QEMU's
temporary disk snapshot option so its original disk remained unchanged. It
used four virtual CPUs, 8 GiB RAM, UEFI, `virtio-vga-gl`, and an EGL headless
display backed by the host render node. No PCI device was passed through.

Guest kernel/source: `3ceb5f150bc121f5e6a3e0cc8b289279338405a1` (`1600027`).
Hyprland: 0.56.2; Aquamarine: 0.15.1; Mesa: 26.2.2.

## Driver provenance

The current `virtio-gpu-qemu-kmod` port only provides an scfb framebuffer.
It cannot supply the DRM interface required here. The experimental module is
instead based on [upstream DRM review #499](https://github.com/freebsd/drm-kmod/pull/499)
at `ae8fc4c421eb4c0d6d9e0821ea6b070e8aec8199`, adapted to the selected
`drm_v6.12.110_1` sources and matching CURRENT headers. The adaptations remove
obsolete DMA/memory shims now provided by base, update fbdev deferred-I/O
guards, and generate/include the LinuxKPI configuration as the release's other
modules already do. Imported licenses are retained.

Upstream superseded that review with [#517](https://github.com/freebsd/drm-kmod/pull/517)
on DRM 6.13. The release integration keeps 6.12 to share its existing core
with the NVIDIA DRM companion. The [Daemonarchy ports change](https://github.com/jordanhubbard/freebsd-ports/pull/2)
records the complete patch and provenance.

## Observed results

- The matching `dmabuf`, `drm`, and `virtio_gpu_drm` modules built and loaded.
  The kernel negotiated VIRGL and EDID and created `/dev/dri/card0` and
  `/dev/dri/renderD128`.
- SDDM's Hyprland greeter rendered. A temporary SDDM autologin configuration
  then launched the actual tester account's Omarchy/Daemonarchy Hyprland
  session. Interactive login itself was not exercised by this check.
- `grim` captured the desktop wallpaper, panel and application windows from
  the guest's real Wayland session. Hyprland reported backend `drm` and
  connector `Virtual-1` at 1280x800.
- Keyboard events sent through QEMU reached a Foot terminal: a shell read
  `daemonarchy` and wrote that exact line to the retained test result.
- Relative pointer events moved Hyprland's reported cursor position.
- `hyprctl eval` with `hl.monitor` changed the output to 1920x1080; both the
  monitor report and a new guest screenshot confirmed it. This was guest-side
  mode selection, not automatic adaptation to a resized viewer window.
- Installing the three matching modules into the disposable guest's
  `/boot/modules` and adding `virtio_gpu_drm` to `kld_list` survived reboot:
  the modules autoloaded and the Hyprland desktop rendered again. The default
  1280x800 mode returned because the temporary resolution change was not saved.
- Native `poudriere testport` for the integrated `drm-612-kmod` revision 5
  passed build, stage QA, plist checks, install/deinstall, and package
  install/deinstall against the matching jail.
- The subsequent native bulk build produced `drm-612-kmod-6.12.110.1600027_5`.
  Installing that actual package in the disposable guest, restoring its package
  lock and rebooting again produced a working Hyprland desktop and screenshot.
  The new image preflight accepted the complete GPU repository with this
  package and rejected the previous package because it lacks the VirtIO module.

The screenshots, keyboard result, source patch, build logs and reboot report
are retained separately from the repository. No signing keys or operator SSH
keys are part of the patch or screenshots.

## Remaining qualification

Test the packaged driver in a fresh installer image, including ordered GPU
startup after SSH, an interactive SDDM login and reboot. Repeat physical
Intel/AMD/NVIDIA regression checks because the shared DRM package changed.
Final ISO integration remains separate from the successful package checks.

The supported candidate configuration requires a VirGL-enabled QEMU display.
The 2D-only device does not provide a qualified Hyprland rendering path.
UTM, bhyve and other hypervisors are not qualified by this experiment. Neither
Venus/Vulkan, multi-head nor module unloading has been qualified. The kernel
also prints a duplicate `hw.dri.debug` sysctl warning; retain it in diagnostics
rather than claiming a warning-free run.
