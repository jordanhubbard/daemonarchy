# Remote agent debug preview checks

Tested on 2026-10-13 in a bhyve guest on bare-metal AMD hardware. The guest
had 2 CPUs, 2 GiB wired RAM and the live ISO only: `kern.disks` reported
`cd0`, with no installation disk attached. The ISO root remained read-only.

| Check | Result |
| --- | --- |
| UEFI boot of the updated ISO | Passed |
| Welcome menu offers installation, remote debug, network setup and shell | Passed |
| Network menu returns to the main menu | Passed |
| Default SSH port 2222 | Passed |
| Editing the port to 2207 through the installer menu | Passed |
| New key waits for a console pairing decision | Passed |
| Rejecting a key denies login | Passed |
| Approving the displayed SHA-256 fingerprint permits a root shell | Passed |
| Approved key reconnects without another prompt in the same session | Passed |
| Stopping debug closes an active SSH connection and refuses new connections | Passed |
| Stopping removes temporary pairing state | Passed |
| Reboot requires fresh approval of a previously approved key | Passed |
| Stop returns to the installer menu | Passed |
| Bash syntax, helper ShellCheck and diff whitespace | Passed |

The first pairing/rejection/connection-cleanup checks ran on an initial image.
The final image adds a separate fingerprint display line and lets the
standalone network menu return without internet connectivity. Its menu,
custom-port pairing, reboot re-pairing and stop/return path were exercised
again. No target-disk installation was attempted by these debug-mode tests.
Preview.2's full installation result is recorded separately in
[the checkout test record](testing-1.1-live-checkouts.md).

## Artifact

The local test artifact is `daemonarchy-1.1.0-preview.3-amd64.iso`.

SHA-256:
`f572689f996d6787f5b196bca036d3d1387a5235b581d7dbd85c420c517c0717`.

It was repacked from preview.2 with the changed configurator, new remote-debug
helper and updated preview label. Base/kernel sets, packages and checkout
catalogue were retained. The image was assembled with FreeBSD's native
`makefs`, `etdump` and `mkimg` hybrid-ISO recipe, retaining the snapshot's
EFI loader and BIOS boot files. This is a development artifact, not a new
published release. BIOS boot of this repacked artifact remains untested.

The serial transcript is retained on the test host at
`/var/tmp/daemonarchy-debug-test/serial-fixed.log`. It contains both pairing
test runs. Temporary client keys were used only for these tests and are not
included in the image or repository.

## Preview.4: network prerequisite and adapter identification

An Intel MacBook hardware test exposed that selecting remote debug bypassed
network configuration. Preview.4 opens network setup before pairing and
withholds Continue until an active, non-loopback interface has an IPv4
address. The SSH helper checks the same prerequisite before starting.
The screen now labels USB and virtual interfaces, shows kernel descriptions,
and explains when FreeBSD has not detected a supported Wi-Fi adapter.

On 2026-10-13 the final preview.4 image was booted under UEFI bhyve on
`daemon.local`, with 2 CPUs, 2 GiB RAM and only the ISO attached:

- Selected Remote agent debug with no interface address: network setup opened,
  with DHCP/manual choices and no Continue option.
- The screen identified `vtnet0` as Virtual and displayed
  `VirtIO Networking Adapter`, plus the missing-Wi-Fi explanation.
- Selected DHCP: acquired `10.77.0.24` and Continue appeared.
- Proceeded to port 2222 and console-approved temporary-key pairing.
- SSH returned root identity and `kern.disks: cd0`.
- The guest had no default route and no DNS configuration; the test host had
  forwarding disabled. Local network access alone was sufficient.
- Shut down the guest and removed the temporary host networking.

The shell regression test also covers inactive/no-carrier/loopback addresses,
simulated DHCP and Wi-Fi menu transitions, cancellation, and adapter labels.
Physical Wi-Fi association, the MacBook's wireless driver support, and BIOS
boot remain unverified by this test.

The final artifact is `daemonarchy-1.1.0-preview.4-amd64.iso`, SHA-256:
`03aabb4d1bc94ccbd2a3420b696fd87d4f47a983f85121920c22ea53e153256f`.
It retains preview.2's base/kernel/packages and adds the installer changes.
The host serial log is
`/var/tmp/daemonarchy-debug-network-test/serial.log`; graphical console
captures used for the menu checks are retained locally as
`/tmp/daemonarchy-network-{menu,dhcp,debug,pair}.png`.
