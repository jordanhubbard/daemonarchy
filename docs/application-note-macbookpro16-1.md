# Application note: MacBook Pro 16-inch (2019)

Updated October 24, 2026. Model: **MacBookPro16,1**, Apple T2, Intel Core
i9-9880H. This note describes the observed 1.1 candidate installation on
OSVERSION `1600027`; the released 1.1.1 uses `1600028`. It does not qualify a
fresh 1.1.1 installation or claim that the newer base fixes these failures.
The [October 22 investigation](testing-macbookpro16-1-installer-20261022.md)
records later development fixes on a repaired 1600028 installation.

## Radeon Pro 5500M graphics

The operator identifies the GPU as a Radeon Pro 5500M. Its detected identity is
AMD Navi14, PCI `1002:7340`, Apple subsystem `106b:020f`, with 4 GiB VRAM.
Apple lists this GPU in the [2019 model specifications](https://support.apple.com/en-us/111932).
The [FreeBSD 6.12 AMD driver](https://github.com/freebsd/drm-kmod/blob/6.12-lts/drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c)
explicitly recognizes this PCI ID as Navi14. GPU age alone does not establish
that the hardware is unsupported; recognition also does not guarantee a working
MacBook display or desktop.

The installed matching driver and firmware packages passed integrity checks.
An earlier 6.6 driver attempt failed during PSP/SDMA firmware initialization.
The later controlled 6.12 attempt read Navi14 firmware and initialized SMU and
Display Core, then reported `KGQ enable failed`, `gfx_v10_0 hw_init failed -60`
and device-attachment error 60. Surviving DRM device nodes did not represent
successful initialization. The 1.1.1 graphics guard rejects that false-ready
state; it does not repair the underlying GPU failure.

A later FreeBSD DRM reservation fix for the offset EFI framebuffer passed three
clean physical boots, then a refreshed ports package reached SDDM's Wayland
greeter. With the T2 keyboard test kernel, the operator entered a password and
reached a visible Hyprland desktop on that package. Hardware radeonsi/Navi14
rendering was observed. The corrected package is under review in
[ports PR #19](https://github.com/jordanhubbard/daemonarchy-ports/pull/19);
the released 1.1.1 image does not contain this fix.

The built-in T2 keyboard previously stalled the desktop in synchronous HID LED
output. The device-specific correction in
[source PR #19](https://github.com/jordanhubbard/daemonarchy-src/pull/19)
passed a native GENERIC build and a physical LED probe with the global LED
bypass disabled. The operator used the keyboard to log in. The built-in
trackpad pointer was initially very laggy, then worked; reliable clicking,
sustained input and normal-boot integration still need testing.

## Built-in Wi-Fi is unavailable in the observed installation

The detected wireless controller is **Broadcom BCM4364 revision 4**, PCI
`14e4:4464`, Apple subsystem `106b:07bf`. The recorded inventory found it
unattached, with no `net.wlan.devices` entry. A subsequent live recheck on
October 18 confirmed the same state, with only loopback and USB Ethernet
interfaces available. The operator also reports no Wi-Fi.
Without an attached wireless device, the desktop cannot scan for or join networks;
entering credentials or changing panel settings cannot supply the missing driver.

This controller needs suitable FullMAC driver support and board-specific firmware.
FreeBSD's existing [bwn driver](https://man.freebsd.org/cgi/man.cgi?query=bwn&sektion=4)
is a SoftMAC driver; its firmware package is not a demonstrated fix for this
BCM4364 device. Experimental external driver work mentioned in the investigation
has not been validated on this MacBook or shipped as a working solution in 1.1.1.

The earlier development installation exposed only loopback and USB Ethernet.
A later private native FreeBSD driver and `bali` B3 firmware preview attached
PCI `14e4:4464`, scanned nearby networks and joined an access point. A
subsequent isolated test passed gateway and Internet traffic over Wi-Fi, and
the desktop displayed the connected network. The live installer previously
associated without an IP address; a revised scan, WPA wait, DHCP and route
path is awaiting a fresh install from the next image. Reassociation across
access points, suspend and rebooted traffic remain unqualified for release.
The [release investigation](roadmap/release-1.2.0.md) tracks these results.
The [experimental native brcmfmac driver](https://github.com/narqo/freebsd-brcmfmac)
targets BCM4350/BCM43455, so its present device support does not close this gap.
Linux's [brcmfmac PCIe mapping](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c)
and this machine's working Linux behavior are references for the hardware
protocol, without importing Linux driver code.

The installer must acquire required laptop firmware when it is absent from its
image. For a wiped MacBook, the [T2 Linux firmware guide](https://wiki.t2linux.org/guides/wifi-bluetooth/)
documents extraction from an Apple recovery image without an installed macOS.
An Apple-signed Sonoma recovery image was downloaded and verified on the
controller; its BCM4364 B3 `bali` firmware hashes match all four files used in
the private MacBook radio tests. The exact hashes and verification steps are in
the [installer investigation](testing-macbookpro16-1-installer-20261022.md#2026-10-23-apple-recovery-firmware-provenance-check).
This is a verified source candidate, not a qualified FreeBSD installer flow.
The installer also needs a local-media path when network access is unavailable,
model/board matching, provenance and integrity checks, transfer into the target
system, and a reboot test that the driver loads the selected files. It must
report a clear unresolved dependency rather than claim wireless readiness if
firmware acquisition or driver attachment fails. This applies to other laptops
with required external firmware as well as the BCM4364.

Keep wired USB Ethernet available for installation and remote debugging while
the new Wi-Fi installer path is tested. Do not treat unrelated USB Wi-Fi adapters
as qualified without testing their exact chipset and driver.

## Other limits and investigation

The later installer retry reproduced a fatal NVMe status during package
installation; recovery under four I/O trackers does not resolve its cause.
Bluetooth, sustained trackpad behavior and restart causes remain unqualified.
An [October 24 S3 test](testing-macbookpro16-1-s3-20261024.md) on the installed
1.1.1 system exposed ACPI, input and networking failures after resume; suspend
acceptance remains open.

See the [dated investigation](testing-macbookpro16-1.md),
[hardware observations](testing-1.1-hardware-observations.md), and
[1.1.1 qualification record](testing-1.1.1.md) for the exact configurations,
repaired package state and test boundaries.
