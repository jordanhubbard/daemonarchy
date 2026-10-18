# MacBookPro16,1 first-boot investigation

This is a dated investigation log. The October 17/18 follow-up at the end
describes the later 1.1 candidate installation; [1.1.1 qualification](testing-1.1.1.md)
is separate. Earlier driver results below remain historical evidence.

Collected on 2026-10-15 through console-approved SSH pairing, after manually
correcting the loader's `currdev`. This is an investigation of a partial
installation, not desktop acceptance. No reboot, package installation, GPU
reload or storage repair was performed during collection.

## Installed system

- MacBookPro16,1, Intel Core i9-9880H, 16 GiB memory; UEFI boot.
- FreeBSD 16.0-CURRENT, `main-n289844-a52c50b4b7c2`, kernel ABI `1600027`.
- OpenZFS module `2.4.99-1149-FreeBSD.g1f380a4f3`.
- The ZFS pool is ONLINE with zero read, write and checksum errors.
- There are 958 installed packages. `daemonarchy`, `omarchy`, `sddm` and
  `hyprland` are absent. There is no normal user account or home directory.
- Root still has the base image's empty password field. No password hashes
  were collected. The paired listener accepts only console-approved keys.
- The signed package-repository configuration, retained ISO repository,
  checkout catalogue and SDDM state have not been installed.
- The last package registration is `qt5-core`, after dependencies including
  `py312-numpy` and `opentimelineio`. Pool history has no final export event.

This places the incomplete installation in the package phase, before ownership
repair, cache rebuilding, user creation and final SSH configuration in that
installer version. The user subsequently confirmed that it rebooted itself
without reporting success or offering a reboot. The trigger for that unexpected
reboot is not established: its log and status were stored only in the live
ISO's `/tmp` and are absent after reboot.
The installer's configuration and early `rc.conf` writes alone do not prove
that the installation completed.

After evidence capture, a corrected EFI entry was added and verified first in
boot order, pointing at the full `POOL/ROOT/default` dataset. Existing boot
entries were retained. The machine has not yet rebooted through the new entry.

## Boot error triage

### ZFS rename replay diagnostics

The retained `dmesg` contains 62 messages of the form `got error -2 on name ...
on op 3`, with backtraces through `zfs_replay_rename` during root mounting.
FreeBSD defines `EJUSTRETURN` as `-2`; `zfs_rename` explicitly handles this
result for destination lookup. In a ZFS debug build, `zfs_lookup_internal`
prints a backtrace for any nonzero result, including this expected value.

These messages alone do not establish corruption or failed replay. A focused
diagnostic-noise improvement could exclude the expected rename result from
that debug print, but a corruption report is not supported by this evidence.
See [FreeBSD errno definitions](https://github.com/freebsd/freebsd-src/blob/main/sys/sys/errno.h)
and [FreeBSD's OpenZFS vnode operations](https://github.com/freebsd/freebsd-src/blob/main/sys/contrib/openzfs/module/os/freebsd/zfs/zfs_vnops_os.c).

### AMD GPU initialization failure: upstream report draft

Suggested title: **drm-66-kmod: Navi14 on MacBookPro16,1 fails PSP SDMA0 firmware initialization**

Hardware: AMD Navi14, PCI `1002:7340`, subsystem `106b:020f`, revision `0x40`,
4 GiB VRAM. BIOS string `113-D32206U1-019`.

Packages: `drm-66-kmod-6.6.25.1600027_11` and
`gpu-firmware-amd-kmod-navi14-20260519.1600027`. Both match the kernel ABI, and
`pkg check -s` reports no checksum mismatches for either package.

During boot, the driver successfully reads the Navi14 SOS, ASD, TA, SMC,
PFP, ME, CE, RLC, MEC, MEC2, VCN, SDMA and SDMA1 firmware images. It then
reports:

```text
[drm] failed to load ucode SDMA0(0x1)
[drm] psp gfx command LOAD_IP_FW(0x6) failed and response status is (0x0)
[drm ERROR :psp_v11_0_ring_destroy] Fail to stop psp ring
[drm ERROR :psp_hw_init] PSP firmware loading failed
[drm ERROR :amdgpu_device_fw_loading] hw_init of IP block <psp> failed -22
drmn0: amdgpu_device_ip_init failed
drmn0: Fatal error during GPU init
device_attach: drmn0 attach returned 22
```

Seventeen `amdgpu_irq_enabled` warnings follow the initialization failure.
This is a firmware initialization failure after file lookup succeeded, rather
than a missing firmware package. DRM device nodes remain present; their
presence does not prove successful GPU initialization.

Before filing: repeat on a completed installation and determine whether a
supported newer DRM branch reproduces it with matching kernel modules.
The initial search of the drm-kmod issue tracker did not identify an exact
duplicate. This is a draft; no upstream issue has been submitted.

### Other observations

- Apple SMC reports `key REV cmd error 0x84`, then enumerates 1164 keys.
  No failing sensor behavior was established, so this alone is insufficient
  for a separate functional bug report.
- Apple BCE initializes and the internal keyboard/trackpad enumerate.
- One additional USB Ethernet interface receives no DHCP offers; the primary
  interface obtains a working lease. This is not proof of a driver failure.
- Early timestamps are in January 1970, followed by an October clock
  correction. Do not infer wall-clock durations across that jump.

## Evidence retained locally

Raw data is in the workstation's private
`~/Library/Logs/Daemonarchy/2026-10-15-macbookpro/` directory: `dmesg.txt`,
`system.txt`, `accounts.txt` (authentication states only), `install-state.txt`,
`package-check.txt`, `gpu-check.txt`, `efi-repair.txt` and `logs.tar.gz`. The archive contains
available `/var/log` files, `/var/run/dmesg.boot`, the partition-table backup,
`rc.conf`, `fstab` and `loader.conf`. Its tar invocation returned nonzero for
explicitly requested files that were absent; the retained archive is readable.
The manifest records checksums and these collection limits. Raw files contain
machine identifiers and should be reviewed before attaching them upstream.

The installed-system debug listener was exercised successfully: a fresh host
key was verified at the console and the temporary client key was approved.
The normal SSH service and its password policy remain separate.

## Subsequent driver investigation

`drm-612-kmod-6.12.85.1600027_2` was built from the existing pinned ports tree
in the `16amd64` poudriere jail. Its package annotation is
`FreeBSD_version=1600027`, matching the MacBook's kernel ABI. Poudriere's
build, stage, install and deinstall checks passed. The build host runs
`1600026`, older than the jail; poudriere warned that this host/jail pairing
is unsupported. Build success does not qualify the driver on the GPU.

The new package, original `drm-66-kmod-6.6.25.1600027_11` rollback package,
build log and checksums are retained in the private evidence directory's
`drm-test/` subdirectory. Neither package has been changed on the MacBook.

The target stopped responding during a later hardware inventory command
containing `sysctl -a` with an output filter. A fresh SSH connection and a
bounded TCP/ping check also failed. The last returned output was the T2
USB-device descriptor. No driver unload, replacement or reboot was issued.
Whether the machine hung, panicked, suspended or lost networking is not
established; a console observation is required. Subsequent probes should use
named sysctl keys: filtering the output of `sysctl -a` does not prevent it
from invoking unrelated hardware handlers.

The console subsequently confirmed a general-protection fault in
`sysctl_handle_attr()`. That function is LinuxKPI's sysfs-to-sysctl bridge,
compiled inline into drivers including amdgpu. It dereferences the attribute's
owning kobject/type and calls the driver's `show` callback. A stale object or
attribute after the failed GPU attach is a leading hypothesis, not an
established cause. The function offset and full backtrace are still needed
to distinguish a fault in that bridge from an AMD callback fault.
The original amdgpu module's handler disassembly and the exact snapshot's
`linux/sysfs.h` are retained for comparison. Historical
[drm-kmod issue 68](https://github.com/freebsd/drm-kmod/issues/68) reported a
similar sysctl-enumeration panic, but involved older code and a different
failure; it is not yet an identified duplicate or proof that 6.12 fixes this.

Peripheral inventory before connection loss:

| Device | Observed state | Remaining native checks |
| --- | --- | --- |
| Wi-Fi | BCM4364 rev 4, PCI `14e4:4464`, subsystem `106b:07bf`; unattached, no `net.wlan.devices` | Working FullMAC driver and board firmware; not fixed by loading the older bwn driver |
| Bluetooth | No Bluetooth USB controller or `ubt` instance visible | Load/check the HCI transport and investigate radio enumeration before pairing tests |
| Trackpad | T2 virtual USB `05ac:0340`; `hms0` and an evdev mouse node present; no `hmt` instance | Finger/click event capture and native multitouch support; module presence alone is not proof |

The exact kernel snapshot's `usbdevs` names the trackpad device
`WELLSPRINGT2_J152F`, but its `bcm5974` device table has no corresponding
entry. The table and SMC/BCE source files from source revision
`a52c50b4b7c2652954ef1bd34710a4b1fc8ef391` are retained with the evidence.

The [experimental Apple Wi-Fi notes](https://github.com/seuros/ChaosBSD-src/wiki/Apple-Driver-WiFi)
describe out-of-tree `kwx/bcfm` work for BCM4364 and a requirement for
board-specific CLM firmware. These claims are development references, not
working-device evidence from this MacBook. The wiki was retrieved directly
at revision `620da33`; no matching `bcfm` module was found in that repository's
public unstable module tree. Its
[Bluetooth notes](https://github.com/seuros/ChaosBSD-src/wiki/Apple-Driver-Bluetooth)
also leave T2 radio validation open. No Wi-Fi connection, Bluetooth pairing,
trackpad movement or newer AMD driver success is claimed yet.

## Preview.10 driver payload

Preview.10 switches the image to `drm-612-kmod-6.12.85.1600027_2`,
including the matching `nvidia-drm-612-kmod` for NVIDIA 595.104.02. These
share the same DRM core; retaining the NVIDIA 6.6 package would pull in the
conflicting older core. The legacy Radeon selection table is regenerated
from the pinned 6.12 source. Physical AMD and NVIDIA acceptance is pending.


## 1.1 candidate recovery follow-up, 2026-10-17/18

A later installation reached the October 12 `3ceb5f150bc1` base, still
OSVERSION `1600027`. Its desktop transaction was incomplete, and the operator
reported repeated spontaneous restart or power-off while ordinary userland
packages were being installed. No desktop GPU startup had occurred during
those interrupted transactions, so these resets do not establish an AMD
initialization failure. The desktop remains unqualified.

A recovery boot environment and private logs were retained. Same-version cached
package repair corrected 104 damaged packages; later small checkpointed package
batches used durable pool barriers. Following another reset, the full installed
package-file checksum check passed, while approximately 42 packages were still
missing from the planned desktop. This distinguishes durable repaired files
from a completed installation; successful extraction of some packages is not
completion of the desktop transaction. This was an intermediate checkpoint;
the remaining repair completed later, as recorded below.

Crash capture was enabled before retries, but no saved panic dump or orderly
shutdown evidence was recovered. Samples showed temperatures of 59–71 C, no
armed FreeBSD watchdog and no observed ACPI power event. None of those negative
observations identifies the reset's cause. Named sysctls remain necessary;
the earlier `sysctl -a` panic above is a separate, confirmed observation.

The rescue menu could be hidden by late probe output and reappear after Return.
The 1.1.1 source now waits briefly for probe activity to settle and redraws the
menu automatically. Its Pair/Unpair option also clears stale remote-agent state
after a reset. These helpers were installed on the investigation target;
physical next-boot validation is separate from their passing native fixtures.
Bounded [continuous SSH diagnostics](remote-agent-debug.md#continuous-diagnostics)
were hot-deployed and retained live kernel, process, storage, sensor and passive
device-event output on the controller. They cannot capture an early panic
before networking or continue a live stream through a hard reset. New src-based
loader/early-kernel transport work remains deferred to 1.2.

### Completed package repair and controlled graphics test, October 18 UTC

The remaining desktop packages and missing `sudo` dependency were installed from
matching cached OS1600027 packages. All installed package files and dependencies
passed verification, a new recovery boot environment was retained, and desktop
postconfiguration completed. This machine was not upgraded to the new 1.1.1
kernel or its OS1600028 package feed.

SDDM had autostarted earlier in this boot without a working Xorg, greeter or
Hyprland session. It was explicitly stopped before the first controlled AMD
initialization. That test loaded Navi14 firmware and initialized SMU/Display Core,
then reported `KGQ enable failed`, `gfx_v10_0 hw_init failed -60`, fatal GPU
initialization failure and `drmn0` attachment error 60. The module-load operation
still returned success and left DRM card/render character nodes behind.

This exposed a graphics-service reporting bug fixed for 1.1.1: readiness now
requires an attached active device and DRM character nodes, rather than module
loading alone. The new guard rejected the actual failed MacBook state and removed
a seeded stale readiness marker. Before/after module lists and kernel logs were
identical, confirming this validation did not reload or reinitialize the GPU.
Graphics remains disabled and SDDM stopped. The AMD failure remains unresolved;
no desktop acceptance or explanation for the earlier package-phase resets is
claimed.
