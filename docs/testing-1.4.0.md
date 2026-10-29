# 1.4.0 test record

Recorded October 29, 2026. This is a dated record of what was run against the
published 1.4.0 image and the development images before it. It does not widen
the claims in the [release notes](release-1.4.0.md).

## Final image, QEMU, public feeds

The image is `daemonarchy-1.4.0-amd64.iso.xz` (SHA-256
`fcaf5e1db17b57a37d01f3db5cefac5794a83b4fe38de2ee926953b9778c7cf6`), built from
installer commit `608506450844ceb08c2af499b1d8056496062674`, daemonarchy-src
`06e5befc`, kernel `#2 06e5befc6031`. `test-qemu.sh` ran on a Linux host with KVM
and a VirGL render node, against the public `packages-16-amd64-1.4.0` feed:

- A default install (no checkouts) took 33 minutes. All installed-system checks
  passed, including the signed feed selection, the SDDM and Omarchy session
  setup, the installed desktop commands, and `tests/qemu-desktop.py` (graphical
  login, input, native browser and package manager).
- The same harness with the ports and src checkouts selected, on the image one
  build earlier (it differs from the final image only in the installer's CUDA
  failure handling), installed both checkouts from the public
  `checkouts-16-amd64-1.4.0` feed: each a clean, owned, depth-1 checkout, ports at
  `b785784219af` and src at `06e5befc6031`, and the same desktop checks passed.

A virtual machine has no NVIDIA GPU, so the CUDA step was not run by the
installer in either run.

## Physical machines

These were operator and agent tests of the development images built in this
cycle, with changes applied live; **the final image was not rerun on either
machine before publication.**

MSI Raider 18 HX AI A2XWIG (see [hardware quirks](hardware-quirks.md#140-on-this-machine)):

- The installer saw no disk until `vmd(4)` accepted bus-offset setting 3
  (daemonarchy-src#47); the install then completed.
- The installed system showed a black screen: `i915kms` resolved `enable_guc` to 0,
  the GPU was declared wedged (`GT0: Enabling uc failed (-5)`), and Hyprland and
  the greeter aborted in `initEGL`. Setting `compat.linuxkpi.i915_enable_guc=3`
  loaded `mtl_guc_70.bin` and the desktop came up; the operator confirmed it.
- The touchpad did nothing. Loading `ig4` rebuilt with the ID of the Arrow
  Lake-S PCH I2C controller `8086:7f4c` attached the ELAN 04F3:31FD touchpad
  (`hms0`, `hmt0`, five contacts, polling mode); the operator confirmed it.
- `nvidia-smi` reported the RTX 5080 Laptop GPU at driver 595.104.02. Intel
  graphics rendered with Mesa 26.2.2 (OpenGL 4.6) on Wayland; an offscreen EGL
  test ran on the NVIDIA GPU. Windowed demos need Xwayland, which was absent
  until installed by hand.
- CUDA 13.2: `daemonarchy-linux-cuda setup` completed after fixes found by running it
  (bsdcpio and symlinked `/compat/linux` directories, a half-unpacked dnf,
  Rocky's CRB repository for `ninja-build`, file capabilities, X11 and Wayland
  development libraries, and SDL 3.4 against Rocky 9's libXi). `nvcc` reported
  13.2.86, cudalab built against SDL 3.2, and a CUDA kernel ran correctly on the GPU
  (compute capability 12.0) with the UVM shim. A `cudaMallocManaged` program
  crashed with a segmentation fault.

MacBookPro16,1:

- The image without a signed boot profile failed the firmware stage
  (`MacBook firmware installation requires a signed boot profile`); a bundle
  built at the same revision fixed it, and the operator confirmed that
  installation proceeded and the firmware passed its signature check.
- The same install later stopped at the `src` checkout step because the
  checkout feed had no package for that revision; the 1.4.0 checkout feed was
  rebuilt and the QEMU run above covers it.
- There is no sound: the T2 audio function has no driver.

## Not run

- Physical runs of the exact final image.
- The A14 installer network matrix and image-based upgrade and rollback, deferred
  to 1.4.1.
- aarch64: the arm64 image boots in QEMU (`test-qemu.sh` with `ARCH=aarch64`) and
  its unattended install fails at the package step because the arm64 feed has no
  `chromium` or `hyprland`.
