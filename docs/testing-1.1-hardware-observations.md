# Physical hardware observations

These are operator-reported development results, not a completed acceptance
matrix. Record the exact image and last visible boot message when available.

| Platform | Image / test | Observation | Qualification |
| --- | --- | --- | --- |
| MSI Raider 18 HX, RTX 5080 | preview.11 and 1.0.1 USB boot, reported 2026-10-15 | Both images reset very early during kernel startup/probing and return to Windows; exact last message not yet captured | Failure predates preview.11; installer boot failed and NVIDIA driver/session tests were not reached |
| T2 MacBook Pro | Development USB / installed-system investigation, 2026-10-15 | Black screen; internal keyboard unavailable in single-user mode; explicitly preloading `apple_bce` produced a queue-registration panic | Unqualified; original black-screen cause and exact panic backtrace unresolved |

For the MSI comparison, the preview.10 and preview.11 ISO payloads were mounted
read-only on FreeBSD and the following files compared byte for byte by SHA-256:

| Payload | Same hash in both images |
| --- | --- |
| `/boot/kernel/kernel` | `8139ad6eb5fa91b91bb8860c27abb6bd2599fc7b0d0bfb2bc2c842fde93aadcb` |
| `/boot/loader.efi` | `f1a9e84cbe83e382ce824738628168900c57e5b00d3bef68400cb2ef00293e46` |
| `/usr/freebsd-dist/kernel.txz` | `5d712017d1b35ce6fb487fc3e448177c4be88f4ad7a801d9379b2ed4c2a5bc74` |

Both use the October 5 snapshot kernel. Their live userspace differs, so this
comparison alone does not exclude an image regression. Testing another ISO on
the same machine and recording the failure point are still necessary. The
desktop NVIDIA driver is not installed or initialized by the live installer.

A subsequent recursive comparison of the complete `/boot` directories on the
same read-only mounts reported no differences, including loader configuration,
Lua scripts and kernel modules. Both temporary mounts and their memory-disk
devices were released after comparison. This narrows the comparison to changes
outside `/boot`; it does not substitute for booting both images on the MSI.

For an ordinary kernel panic, these loader commands enable verbose probing and
hold the panic output rather than automatically rebooting:

```text
set kern.panic_reboot_wait_time=-1
set debug.trace_on_panic=1
boot -v
```

The snapshot's `kern_shutdown.c` exposes both settings as loader tunables.
A firmware reset or a fault before panic handling may still reboot immediately;
these commands are diagnostic settings, not a fix. Do not combine speculative
device-disabling settings before identifying the last visible probe.

For comparison, the official October 12 FreeBSD mini-memstick image was
downloaded and checked against the project's SHA-256 list:

`FreeBSD-16.0-CURRENT-amd64-20261012-3ceb5f150bc1-290063-mini-memstick.img`

SHA-256: `9127c94970ca11e6e44c582a7cab928851f73fd2476e94471ee1456d63990e14`.
The compressed download also matched its published checksum. This image is
available for an operator boot comparison; no MSI result with it is recorded.

## MSI comparison reports

The operator subsequently reproduced the early reset with Daemonarchy 1.0.1.
The observed failure therefore predates preview.11. A stock FreeBSD boot result
and a final probe line remain missing.

Windows System Information supplied by the operator identifies:

- Model: Raider 18 HX AI A2XWIG, SKU 1824.3.
- CPU: Intel Core Ultra 9 285HX, 24 cores / 24 logical processors.
- Board: MS-1824, REV:1.0; RAM: 32 GiB.
- UEFI BIOS: American Megatrends E1824IMS.312, dated 2025-08-28.
- Secure Boot: off.

Windows reports virtualization-based security running. This is a Windows-side
observation; it does not establish a cause for a separately booted USB failure.
Machine/account identifiers and unrelated Windows configuration were omitted.

A closely matching first-person hardware report was found on 2026-10-15:
[Slackware installer resets on MSI Raider 18 HX AI](https://www.linuxquestions.org/questions/slackware-installation-40/slackware-current-usb-boot-grub-hangs-msi-raider-18-hx-ai-4175764459/).
The May 22–27, 2026 thread identifies an A2XWIG, Core Ultra 9 285HX, RTX 5080
and BIOS E1824IMS.316. Its installer hard-resets after about 15 seconds. The
reporter says Debian, Manjaro and Void installer media boot, and disabling ACPI
changes the reset into a hang. No working Slackware fix is recorded in those
posts. The model, CPU and motherboard match the operator's machine, while the
reporter's BIOS is newer (.316 versus .312). This is Linux evidence, not a
confirmed FreeBSD duplicate or a diagnosis of this operator's machine. The
reset on .316 also means a newer BIOS is not by itself evidence of a fix.

FreeBSD [bug 287342's initial report](https://lists.freebsd.org/archives/freebsd-bugs/2025-June/028114.html)
concerns Arrow Lake desktop I/O instability after boot on different hardware.
It does not establish an explanation for this early installer reset. No exact
FreeBSD Raider/285HX reset duplicate was identified in the searches so far.

## ASRock X570 Taichi: preview.13 live boot and Wi-Fi

Observed 2026-10-15/16 through the console-approved remote debug listener.

- AMD Ryzen 9 3950X, 32 GiB RAM.
- NVIDIA GeForce RTX 4090, PCI `10de:2684` (ASUS subsystem `1043:88ef`).
- Intel Wi-Fi 6 AX200, PCI `8086:2723`, using `iwlwifi`.
- The USB root identifies itself as preview.13; the running kernel is the
  selected October 12 snapshot, `3ceb5f150bc1`.

The image boots to its live installer and permits a root SSH session over Wi-Fi.
WPA2 authentication completed and DHCP assigned an address and default route.
The primary DHCP-provided resolver timed out on direct queries; the secondary
resolver and gateway resolver answered. Reordering the existing DNS servers to
put the responsive secondary first made bounded hostname lookup and package
repository HTTPS probes pass. This was a live-session change; long-term Wi-Fi
stability and persistence across an installed-system reboot are not qualified.

The kernel log also contains an `iwlwifi0_com_lo -> ifnet_sx` lock-order warning,
Bluetooth HCI timeouts and USB re-enumeration failures. These are recorded
observations, not demonstrated causes of the DNS failures. The diagnostic image
had verbose boot enabled. Capturing `dmesg`, then setting `debug.bootverbose=0`
and `kern.consmute=1`, quieted console output while retaining the kernel log.

NVIDIA modules were not loaded during this inventory. PCI detection and a live
CLI boot do not qualify the NVIDIA driver, Hyprland, displays or suspend/resume.
All internal disks were allocated; no disk or partition was selected for writing.

The source installer now puts an eight-second outer timeout around its package
probe, including DNS resolution. Portable error/recovery tests and a native
FreeBSD test with a deliberately stalled fetch process passed. This fix is
newer than the already-built preview.13 image and needs a subsequent image.

### RTX 4090 driver and CUDA follow-up, 2026-10-16

The operator's subsequent preview.13 installation stopped at
`linux_base-rl9-9.8` with `kernel missing 64-bit Linux support`. The live kernel
had neither Linux ABI module loaded. Loading `linux` and `linux64` exposed
`kern.features.linux64: 1`; resuming only the package/configuration stages
completed the installation. Partitioning and base extraction were not repeated.
The installed recovery commands and Bash were already present before recovery.
Linux post-install caches were rebuilt inside the target, and its pool was
cleanly exported after testing.

The installed target has driver `595.104.02`, matching Linux NVIDIA libraries,
NVIDIA DRM `595.104.02.1600027_2`, core `omarchy-4.0.4_16` and desktop
`daemonarchy-1.0.1_2,1`. This is the recovered preview, not final 1.1 evidence.
Testing loaded its matching `nvidia.ko` into the still-running stock live
kernel; it did not reboot into the installed desktop.

- Native `nvidia-smi` reported NVIDIA GeForce RTX 4090, PCI bus `0e:00.0`,
  24,564 MiB VRAM, 49 C and driver 595.104.02. Its CUDA-version field was N/A.
- The Linux `nvidia-smi` ran through the Linuxulator and reported the same GPU
  and driver, with CUDA-version capability 13.2. That field alone does not
  qualify a CUDA workload or mean the toolkit is installed.
- The Linux executable built from `tests/cuda-probe.c` failed `cuInit` with
  error 304 without interposition. With the repository's UVM shim preloaded,
  it initialized CUDA, created a context, JIT-loaded an Ada PTX kernel,
  allocated GPU memory, copied input to it, launched and synchronized the
  kernel, and copied the correct result (42) back to the CPU. Cleanup passed.
- Linux proc/sys mounts and the target devfs were unmounted after testing.
  The target pool was exported again; the operator retains control of reboot.

The optional toolkit was not selected (`install_cuda=false`). This qualifies
the tested driver API/compute path with the shim, not toolkit installation,
cudalab rendering, every CUDA library, Unified Memory, or installed-system
Hyprland/display/suspend behavior. NVIDIA WITNESS lock-order warnings remain
in the kernel diagnostics; the test did not panic.
