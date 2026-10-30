# GPU report

`daemonarchy-gpu-report` says which GPU the desktop really renders on and whether that
is accelerated. It is read-only, opens no window and takes a few seconds.

```
daemonarchy-gpu-report            # a readable summary
daemonarchy-gpu-report --json     # the same, for scripts and bug reports
daemonarchy-gpu-report --from DIR # analyse saved outputs instead of running the commands
```

Run it from a terminal inside the desktop session, where `WAYLAND_DISPLAY` and `DISPLAY` are
set, so it can see what the session itself uses. From a console or over SSH it still
reports every GPU and EGL device but cannot name the session's renderer.

## What it reports

- The PCI display devices (`pciconf -lv`) and the GPU kernel modules loaded.
- Every EGL platform and device from `eglinfo -B`, each classified:
  **hardware** (a real GPU driver), **software** (`llvmpipe`, `softpipe`, `lavapipe`,
  `swrast`) or **virtual** (virgl, VMware SVGA: accelerated by the host).
- `nvidia-smi` name, driver and bus, where present.
- The renderer the session uses (Wayland first, then X11), its OpenGL version, and the
  PCI GPU it runs on. On a hybrid laptop this is the line that matters.

The exit status is 0 when the session renders on hardware or a virtual GPU, 2 when it
fell back to software, and 3 when nothing could be determined. A software renderer never
counts as acceleration, even when a real GPU is also present: on a machine that lists
`llvmpipe` as an EGL device, only the session's own renderer decides the verdict.

## Example: the MSI Raider 18 HX AI (Intel Arrow Lake-S plus NVIDIA RTX 5080)

Captured in the running desktop session on 2026-10-30, Mesa 26.2.2, NVIDIA 595.104.02:

```
GPU report
  PCI vgapci0@pci0:0:2:0 Intel   Arrow Lake-S [Intel Graphics]
  PCI vgapci1@pci0:1:0:0 NVIDIA  GB203M / GN22 [GeForce RTX 5080 Max-Q / Mobile]
  Kernel modules: drm, i915kms, nvidia, nvidia-drm, nvidia-modeset
  nvidia-smi: NVIDIA GeForce RTX 5080 Laptop GPU driver 595.104.02 bus 00000000:01:00.0
  EGL Device #0  hardware NVIDIA GeForce RTX 5080 Laptop GPU/PCIe/SSE2
  EGL Device #1  hardware Mesa Intel(R) Graphics (ARL)
  EGL Device #3  software llvmpipe (LLVM 19.1.7, 256 bits)
  Session renders with: Mesa Intel(R) Graphics (ARL)  [hardware, via wayland] on Arrow Lake-S [Intel Graphics] (vgapci0@pci0:0:2:0)
  API: 4.6 (Core Profile) Mesa 26.2.2
  Hybrid graphics: more than one GPU is present; only the one named above is used by the desktop.
  Verdict: accelerated
```

The desktop renders on the Intel GPU; the NVIDIA GPU is present for compute (CUDA) and for
applications that request it. The software device is listed but unused.

## Frame rates

The report does not measure frame rates. `glmark2` is packaged for FreeBSD (amd64 and
aarch64, 7 MiB) and can be installed with `pkg install glmark2`; it is not part of the
default image.
