# Application note: MacBook Pro 16-inch (2019)

Updated October 28, 2026. Model: **MacBookPro16,1**, Apple T2, Intel Core
i9-9880H.

**Current release:** 1.3.1 (OSVERSION `1600029`) carries the graphics, T2
keyboard and BCM4364 Wi-Fi work described below, including the framebuffer and
keyboard fixes and verified Apple firmware acquisition in the installer. The
operator confirmed that all pre-production checks passed on this MacBook; an
additional physical run of the final public ISO was waived. Suspend, the NVMe
fault and firmware-enforced Secure Boot remain open. See the
[1.3.1 release notes](release-1.3.1.md) and
[MacBook acceptance record](testing-macbookpro16-1-1.3.1.md).

The investigation below began with the 1.1 candidate installation on
OSVERSION `1600027`; the earlier 1.1.1 release used `1600028`. The
[October 22 investigation](testing-macbookpro16-1-installer-20261022.md)
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
successful initialization. The graphics guard (since 1.1.1) rejects that false-ready
state; it does not repair the underlying GPU failure.

A later FreeBSD DRM reservation fix for the offset EFI framebuffer passed three
clean physical boots, then a refreshed ports package reached SDDM's Wayland
greeter. With the T2 keyboard test kernel, the operator entered a password and
reached a visible Hyprland desktop on that package. Hardware radeonsi/Navi14
rendering was observed. The corrected package was merged in
[ports PR #19](https://github.com/jordanhubbard/daemonarchy-ports/pull/19)
and ships in 1.3.1; the earlier 1.1.1 image does not contain it.

The built-in T2 keyboard previously stalled the desktop in synchronous HID LED
output. The device-specific correction in
[source PR #19](https://github.com/jordanhubbard/daemonarchy-src/pull/19),
which ships in 1.3.1, passed a native GENERIC build and a physical LED probe with the global LED
bypass disabled. The operator used the keyboard to log in. The built-in
trackpad pointer was initially very laggy, then worked; reliable clicking,
sustained input and normal-boot integration still need testing.

## Built-in Wi-Fi in the observed installation

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
had not been validated on this MacBook or shipped as a working solution in the earlier 1.1.1.

The earlier development installation exposed only loopback and USB Ethernet.
A later private native FreeBSD driver and `bali` B3 firmware preview attached
PCI `14e4:4464`, scanned nearby networks and joined an access point. A
subsequent isolated test passed gateway and Internet traffic over Wi-Fi, and
the desktop displayed the connected network. The live installer previously
associated without an IP address; a revised scan, WPA wait, DHCP and route
path ships in 1.3.1, whose MacBook pre-production checks passed by operator
confirmation. Reassociation across access points, suspend and rebooted traffic
remain unqualified. The earlier [release investigation](roadmap/release-1.2.0.md)
retains these results.
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

The public ISO does not include Apple's board files. Generic FreeBSD
`wifi-firmware-kmod` firmware remains on the media. The MacBook firmware step
offers two sources that need no Ethernet, ahead of the Apple download:

- **This Mac's internal disk.** The importer opens each APFS partition
  (`fstyp` reports `apfs`) as a device through 7-Zip. It never mounts or writes
  that disk.
  - It prefers a Recovery `BaseSystem.dmg`, copied with a 2 GiB bound.
  - It falls back to the system volume's `usr/share/firmware/wifi/C-4364__s-B3`
    files.
  - An image from another macOS build is accepted only when all four extracted
    files match the pinned sizes and SHA-256 values. Its observed hash is
    recorded as `source_image_sha256` with `source_image_pinned: false`.
- **A second USB stick.** The configurator mounts unmounted FAT or UFS volumes
  read-only, then unmounts them. It skips the live media and any disk holding
  APFS. It imports either a `BaseSystem.dmg`, which must match the pinned
  image, or a directory holding the four `brcmfmac4364b3-pcie.*` files, which
  must match their pinned sizes and hashes. exFAT is not supported on the
  live system.

Every source produces the same private stage and
`daemonarchy/apple-recovery-firmware@1` provenance. That provenance adds a
`source_kind` field. The signed boot and runtime inventories still bind the
four file hashes.

These paths have controller fixtures only. Physical MacBook proof is still
required for two things: that 7-Zip reads APFS from a FreeBSD disk device
(which needs sector-aligned reads), and that the stick search works on real
hardware.

The installer also needs a local-media path when network access is unavailable,
model/board matching, provenance and integrity checks, transfer into the target
system, and a reboot test that the driver loads the selected files. It must
report a clear unresolved dependency rather than claim wireless readiness if
firmware acquisition or driver attachment fails. This applies to other laptops
with required external firmware as well as the BCM4364.

Keep wired USB Ethernet available for installation and remote debugging while
the new Wi-Fi installer path is tested. Do not treat unrelated USB Wi-Fi adapters
as qualified without testing their exact chipset and driver.

## System clock

Every power-on starts the clock in January 1970. Measured on October 27 on the
installed 1.3.1 system (signed 1.3.1 plus the [T2 NVMe fix](testing-macbookpro16-1-nvme-20261026.md)
kernel):

- At boot `efirtc0` provides the initial time and reads `1970-01-17 01:46:11`;
  with `hint.efirtc.0.disabled="1"`, `atrtc0` reads the same clock
  (`1970-01-17 01:49:03` three minutes later). The value advances with real
  time between boots.
- While the system runs, writes to both clocks work: EFI `SetTime` returns
  success and `GetTime` reads the new value back, and the CMOS registers hold
  the time FreeBSD wrote after `ntpd` stepped the clock.
- At the next power-on both read the 1970-based value again. The firmware
  reloads the time-of-day clock from the T2 and ignores what the operating
  system wrote, so no FreeBSD clock driver change can make it persist.

`ntpd_sync_on_start` corrects the clock within seconds when the network is
reachable. Installations from 1.4 also add `daemonarchy_clock`, which records
the time at shutdown and every 15 minutes and, at boot, moves a clock that is
behind the record forward to it, so an offline boot starts no earlier than
the last time the system was up. `daemonarchy_clock_enable="NO"` turns it off.

On the same October 27 boot, built-in Wi-Fi associated to a 5 GHz WPA network
and obtained its address by DHCP on `wlan0`, and SDDM started Hyprland on the
Radeon Pro 5500M (`amdgpu`, 3072×1920).

That installed 1.3.1 system also showed `ue0` with a link but no address. It
is not USB Ethernet: see [the T2 internal link](#the-t2-internal-link-and-touch-id)
below. From FreeBSD's sources, a port with a link and no DHCP server makes
devd(8) hold a foreground dhclient for up to 60 seconds, which delays the Wi-Fi
client, while boot waits up to 30 seconds for a default route. This has not
been timed on this machine. Installations from 1.4 run DHCP clients in the
background, let `daemonarchy-netselect` choose the first usable connection
([NET-002](roadmap/active-work.md)), and never run DHCP on the T2 link; only
stubbed tests and the hand check below cover that so far.

## The T2 internal link and Touch ID

`ue0` on this machine is the Apple T2 controller's internal USB link to
bridgeOS: `cdce0: <Apple Inc. Apple T2 Controller>` on `usbus3` (the T2 BCE
virtual host controller), USB vendor `0x05ac`, product `0x8233`, with the fixed
MAC address `ac:de:48:00:11:22`. It always has a link and never a DHCP server.
The T2 answers on IPv6 link-local at `fe80::aede:48ff:fe33:4455` (MAC
`ac:de:48:33:44:55`); its RemoteXPC service listens on TCP 59602 and
advertises BiometricKit, the Touch ID sensor's service. The USB Ethernet
adapter is `axe0`/`ue1` here, but the numbers follow attach order, so
Daemonarchy identifies the T2 link by its USB ids and uses the MAC only as a
cross-check.

From 1.4 (NET-001, NET-002) the installer leaves the T2 link out of network
discovery, DHCP, route and DNS choice, and every installed system gets
`daemonarchy-t2link`: a devd rule on the cdce attach for `05ac:8233` and an
`rc.conf.d/network` fragment that give the link `inet6 -ifdisabled
auto_linklocal`, no IPv4 and no dhclient, whatever its number.
`daemonarchy-netselect status` lists it as never a route or DNS candidate.

Checked by hand on October 28 on the installed 1.3.1 system, without a reboot
and without touching `ue1` or `wlan0`: the files were installed, FreeBSD's own
`network.subr` reported no DHCP for `ue0` (and DHCP still for `ue1` and
`wlan0`), devd's `service dhclient quietstart ue0` refused to start a client,
the boot-time dhclient on `ue0` was stopped and `ue0` came up with
`fe80::aede:48ff:fe00:1122`, and the T2 answered ping and its RemoteXPC port.
One slip: a `SIGHUP` meant to make devd reread its rules stopped devd (devd
treats `SIGHUP` as a request to exit) for about ten seconds until
`service devd start` restarted it with the new rule; the SSH session over
`ue1` was not affected. The devd rule has not yet fired on a real attach, and
no boot has run with these files.

### Touch ID (HW-004)

KaiT2en's `t2-touchid` bridges the sensor to stock fprintd through libfprint's
virtual storage device, and Daemonarchy's ports tree packages it as
`security/t2-touchid` ([ports PR #33](https://github.com/jordanhubbard/daemonarchy-ports/pull/33);
disabled by default; see [HW-004](roadmap/active-work.md)).
The fingers must be enrolled under macOS: the bridge never enrolls, it only
binds a macOS-enrolled identity to a FreeBSD account. The Secure Enclave also
reports a locked, empty inventory until the macOS account password has
unlocked its biometric keybag once since the T2 last powered on (the
before-first-unlock gate); rebooting FreeBSD does not power-cycle the T2, but
a real power loss does.

This MacBook has no macOS (the whole disk is Daemonarchy), so only the
transport was tested, on October 28 with the package installed and the daemon
started by hand. Discovery found `ue0` from its USB ids and the T2 from the
neighbour table; RemoteXPC advertised `com.apple.eos.BiometricKit` on port
49166 within 0.4 s; the BiometricKit session (sensor reset, readiness and the
FDR calibration load) opened in 4 to 8 seconds. In two of three runs the
first attempt timed out instead (`EAGAIN` from the 8-second read timeout,
after about 9 seconds); the daemon retries, and its second attempt succeeded. The Secure Enclave's answers, for macOS user ids
501, 502 and 503 alike:

| Query | Status | Data |
| --- | --- | --- |
| `SKS_LOCK_STATE` | 0 | `0x15` |
| `PROVISIONING_STATE` | 0 | `5` |
| `USER_IDENTITIES` | 0 | empty (no enrolled finger) |
| `GET_FREE_IDENTITY_COUNT` | 0 | `0` |
| `REQUEST_MAX_IDENTITY_COUNT` | 0 | `5` |
| `GET_ENABLED_FOR_UNLOCK` | 0 | `0` |
| `GET_SENSOR_INFO` | 0 | `01000000 0c000000 03000000` |
| `GET_IDENTITY_RECORDS` | 0 | empty |

The daemon then searched macOS user ids 501 to 520, found no enrolled finger
and reported that the Secure Enclave is locked or empty. It was stopped
afterwards and is not enabled; PAM, SDDM and the lock screen were not changed.
A login by finger needs macOS installed beside Daemonarchy, fingers enrolled
there, and a macOS login after each T2 power loss.

### Enabling Touch ID (not yet tested end to end)

This is the intended procedure. No part of it after the transport check above
has run on hardware.

1. Install the bridge and fprintd; libfprint must be built with its virtual
   devices (the `VIRTUAL` option, on by default in Daemonarchy's ports tree):
   `pkg install t2-touchid`.
2. In macOS, enroll the fingers and log in once.
3. In `/etc/rc.conf`, enable the bridge and bind the macOS-enrolled fingers
   to your account (or run `fprintd-enroll -f <finger> <user>` and touch the
   sensor once instead):

   ```sh
   t2_touchid_enable="YES"
   t2_touchid_bind_user="<user>"
   ```

   Then `service t2_touchid start` and check `fprintd-list <user>` and
   `fprintd-verify <user>`. The rc script runs fprintd itself with
   `FP_VIRTUAL_DEVICE_STORAGE` set, because D-Bus activation starts it with a
   clean environment; stopping the bridge stops that fprintd, and PAM then
   falls through to the password.
4. Add pam_fprintd before the password module of each service that should
   accept a finger. Keep a root shell open while testing, so that a broken PAM
   file cannot lock you out:
   - sudo, in `/usr/local/etc/pam.d/sudo`, and console login, in
     `/etc/pam.d/login`, before `auth include system`:

     ```text
     auth		sufficient	/usr/local/lib/security/pam_fprintd.so
     ```

   - SDDM, at the top of the `auth` section of `/usr/local/etc/pam.d/sddm`
     (the same line). The greeter may then wait for the finger, or the
     match window, before it accepts the password.
   - hyprlock: either the same line at the top of `/usr/local/etc/pam.d/hyprlock`,
     or hyprlock's own fprintd support in `hyprlock.conf`
     (`auth { fingerprint { enabled = true } }`), which leaves PAM unchanged.

There is no Escape key to cancel a scan on FreeBSD (upstream reads it
through libinput on Linux); a prompt ends when the finger matches or after
the 10-second match window, and an unreachable T2 falls back to the password
after 15 seconds. Suspend and resume are not handled specially: without
logind, the bridge notices a dead session by its timeout.

## Other limits and investigation

The later installer retry reproduced a fatal NVMe status during package
installation. The [root cause and a driver fix](testing-macbookpro16-1-nvme-20261026.md)
are recorded; the fix is not in the 1.3.1 kernel, and four I/O trackers only
reduce the failures.
Bluetooth, sustained trackpad behavior and restart causes remain unqualified.
An [October 24 S3 test](testing-macbookpro16-1-s3-20261024.md) on the earlier
installed 1.1.1 system exposed ACPI, input and networking failures after resume; suspend
acceptance remains open.

See the [dated investigation](testing-macbookpro16-1.md),
[hardware observations](testing-1.1-hardware-observations.md), and
[1.1.1 qualification record](testing-1.1.1.md) for the exact configurations,
repaired package state and test boundaries.
