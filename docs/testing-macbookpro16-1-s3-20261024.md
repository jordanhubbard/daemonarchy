# MacBookPro16,1 S3 trial, 2026-10-24

This was a physical test of the installed Daemonarchy 1.1.1 desktop on
FreeBSD 16.0-CURRENT kernel `bdcfeac3e1cb`, with the private diagnostic
`if_brcmfmac-eapol-trace-20261023.ko` loaded. It does not qualify the new ISO,
which is still building from a different source revision.

`hw.acpi.supported_sleep_state` advertised S3. A pre-suspend kernel and
network snapshot was saved locally, then `acpiconf -s 3` was issued. The screen
went black and both debugger network paths stopped answering. Short power
presses did not visibly restore the system. After a longer power hold and a
normal press, the operator saw ACPI errors and then the desktop. The boot time
was unchanged, confirming this was resume rather than a cold boot. Keyboard
and trackpad initially did not respond; they later responded after an Ethernet
cable replug. The sequence does not by itself establish which action restored
the input devices.

The saved post-resume kernel log shows:

- The Navi14 graphics driver reported a successful SMU resume, but the
  Hyprland startup process exited on signal 6 once.
- ACPI methods for `PEG1.UPSB` and `PEG2.UPSB` timed out with
  `AE_AML_LOOP_TIMEOUT` while those PCIe paths were being set to D0.
- The T2 BCE virtual USB host controller and the USB Ethernet adapter
  detached and reattached. The Ethernet DHCP client reported its old interface
  invalid and exited.
- A later Broadcom scan returned error 55 and the BCM4364 firmware console
  reported `TRAP 4`. Wi-Fi did not pass traffic afterward.

Both wired and wireless interfaces retained addresses on the same subnet.
The default route remained bound to the failed wireless interface after it was
put down, so off-subnet traffic failed. With wireless down, the wired route
reached the gateway. Removing the stale wireless address, rebuilding the
default route, and restoring the address made wired internet and the debugger
reachable again. The original `route -ifp` command silently kept the prior
interface: FreeBSD's Netlink `route` path discarded that option. A patched
utility passed a physical switch to wireless and back to wired while both
addresses were present; the isolated source correction is
[daemonarchy-src PR 24](https://github.com/jordanhubbard/daemonarchy-src/pull/24).
It was merged into the MacBook source integration branch at `75a3f211e776`.
The current private ISO build remains pinned to the earlier `02984cfbe95c`
source sets and stages that tested utility only in its live environment.
Production sets and the installed utility must be rebuilt from the merged
source revision.

The pre- and post-resume raw logs remain private on the MacBook and controller.
During a later post-resume check, putting `wlan0` down made the route to the
gateway select the USB Ethernet interface, and the MacBook received gateway
replies. The controller, native build host and a second peer still received no
reply from the MacBook's previously observed wired address. A controller-side
packet capture showed its ICMP requests leaving on Ethernet without replies.
The MacBook's current wired address, debugger listener and return path still
need direct inspection; a successful gateway ping alone does not establish
inbound debugger recovery.

S3 acceptance is **open**. Repeat on the exact new image after qualifying ACPI
power restoration, T2 input, desktop restart, BCM firmware recovery, NVMe I/O,
and network route selection across multiple cycles.
