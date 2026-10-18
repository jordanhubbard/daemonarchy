# Remote agent debug preview checks

Historical 1.1 development/candidate evidence. Revisions, checksums and results
below apply to the named artifact and date; they do not qualify the new
[1.1.1 source/package set](testing-1.1.1.md). Follow that record for current
preparation and publication status.

## Session feedback (2026-10-16)

The matching October 12 FreeBSD CURRENT builder passed a real, isolated SSH
server lifecycle test using the new helper. It rejected one key without
announcing a connection, approved a second key, announced authentication on
the listener console, displayed an explicit activity update, and preserved it
across subsequent SSH commands. Command output did not appear on that console.
SFTP continued to work through the authenticated session wrapper. Explicit
completion displayed the safe-to-stop message; stopping the listener then
closed a live connection, removed approvals/state and refused reconnection.

`tests/remote-debug-session.sh` retains this reproducible native check. Portable
progress tests also cover terminal-control sanitization, duplicate-message
suppression and rejection of updates after stopping. The native rescue-setup
idempotence check passed as well. These changes are newer than preview.13 and
still require final-image qualification.

## Earlier preview checks

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

## Preview.5: offline CLI access

The debug entry now opens an interactive root Bash shell immediately, without
network setup or an address prerequisite. Network setup also has an explicit
Open debug shell action. `remote-debug listen [port]` uses text prompts for
listener opt-in and key pairing; Enter/Ctrl-C stops it and returns to the shell.

On 2026-10-13, preview.5 booted under UEFI bhyve on daemon.local with no NIC and
no target disk attached. The main debug entry opened a working shell;
`ifconfig -l` returned only `lo0`. Attempting `remote-debug listen` and answering
y failed with the no-address explanation and returned to the same usable shell.
Exiting the shell returned to the installer menu. CLI regression tests cover
opt-in, default/custom ports, approval/rejection, and the real no-address guard.
ShellCheck, Bash syntax checks, and network regression tests passed.
Actual SSH pairing was exercised on preview.4; preview.5's text pairing prompts
were tested with a simulated listener. Physical Mac networking remains pending.

Artifact: `daemonarchy-1.1.0-preview.5-amd64.iso`.
SHA-256: `599e8e6a2730b094fe7f4aa8a040cc66fc97831e1e907f3b5362878f816f31f5`.
Console captures: `/tmp/daemonarchy-cli-shell.png`,
`/tmp/daemonarchy-cli-no-network.png`, and `/tmp/daemonarchy-cli-return.png`.
