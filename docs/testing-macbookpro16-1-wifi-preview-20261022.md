# Private MacBook Wi-Fi preview image, October 22, 2026

This is a hardware test image, not a release candidate or public download.
It keeps the 1.1.1 kernel, base sets and package repository, updates the live
installer and rescue scripts from the integration branch, and stages the
private BCM4364 module and four board-specific firmware files. It refreshes
the offline Omarchy and Radeon packages to the versions tested on the MacBook.
The installed target copies the radio files and enables the module after its
root is mounted. On MacBookPro16,1 it also retains the working keyboard LED
tunable. The installer waits for WPA key exchange before requesting DHCP.

| Artifact | SHA256 |
| --- | --- |
| Baseline `daemonarchy-1.1.1-amd64.iso` | `c1bc6e3a0d30e6806a324aa3abd76eb70f1593f9f22e7aab6d222491fc1eb956` |
| First private `daemonarchy-macbook-wifi-preview-20261022-amd64.iso` | `7db7756c0685ea6069246933db5494c008ffbf550797171064be306dfe81adc6` |
| Revised `daemonarchy-macbook-wifi-efi-timer-preview-20261022-amd64.iso` | `bbb54332a191b414f50b1de6890faad8777095c7e2ce6bc39f44d7a60d242525` |
| ISO and MacBook kernel | `94e4ace9d6b6083f682d1a0d325162d10d0db852aa82400f7b59655e4df507b2` |
| Native-built `if_brcmfmac.ko` in revised image | `14b1eb7d1ab24c74ced568c14a17466321cf3b2733802b2a591bef2abc518590` |
| Native-built EFI timer loader | `402971436555f7b607de9b521ba3da826a8119cfa29ebe4c1ad2d8be9fd33ba1` |
| MacBook-tested `drm-612-kmod-6.12.110.1600028_6.pkg` | `f3e3cac349851fdf0fc2acdf2dec36971ebb8023c227977fd00c9e45f371c5ba` |
| Omarchy Wi-Fi-panel `omarchy-4.0.4_24.pkg` | `02d30212a5f2bc5ffa36f16cf44b36388a0b68c2bd578ba253c8bd3dc74611b9` |

The baseline's hidden BIOS and EFI El Torito images were extracted and used
when rebuilding the preview. The original volume label was retained because
the EFI loader uses it for the live root. Files were extracted with root
ownership and identical hard-linked content was deduplicated before image
authoring. The resulting 1.8 GiB image has protective MBR, GPT and both boot
entries. This exact refreshed image reached the installer welcome screen
under both OVMF and BIOS QEMU; the screen showed the private hardware-preview
label. The booted live system loaded `if_brcmfmac` without a VM radio present.
A full VM install and physical fresh install are still pending.

## Physical install attempt, October 23

The revised image booted the MacBook and joined Wi-Fi, but the first whole-disk
install attempt stopped before partition writes. The live installer reported
`Managed boot file mismatch: boot/loader.efi` while validating its signed boot
bundle. The live loader hash is the revised timer-loader hash above, while the
bundle still pins the original loader hash
`2058bc3b47a6a98b03c7f69c99416b272a31bdefa6415e16e9b171c5ba158e51`.
The target's existing GPT and importable ZFS pool were still present after the
failure. This preview must not be treated as an installable image until the
final loader and signed bundle are made consistent and verified together.

The live system's Wi-Fi profile and remote-debug grant are on volatile `/tmp`
and `/var` filesystems. A private, mode-0600 recovery copy was retained on the
debug controller, outside Git, but this ISO cannot automatically reconnect the
debugger over Wi-Fi after reboot. A future debug image needs a durable,
access-restricted profile and grant, plus boot-time Wi-Fi and listener startup;
the saved controller copy alone does not provide unattended recovery.

A second **private development image** was assembled for the next physical
retry: `daemonarchy-macbook-wifi-debug-recovery-20261023-amd64.iso`, SHA-256
`5f6b5e49a40f22edeb2da5c6889cb922c0ae91ceb2b258c46ce22d30c33b6688`.
It carries this one debugging session's Wi-Fi profile, approved SSH state and
host identity in root-readable ISO files, with a live-boot helper to bring up
Wi-Fi and resume the listener. The file must remain private and should be
destroyed when the session ends. The stale signed bundle was removed because
it cannot attest the timer-fixed loader; firmware Secure Boot was disabled on
the observed MacBook boot. This image is **not a signed or attested release**.
Its ISO tree, EFI/GPT boot records and timer-loader hash were checked, and an
OVMF VM mounted the live root and reached multi-user startup. Automatic Wi-Fi
reconnection and debugging resumption still require a physical reboot test on
the MacBook; the VM has no BCM4364 radio.

## EFI timer and installer Wi-Fi revision

The first preview reused the published 1.1.1 EFI boot image. Its
`EFI/BOOT/BOOTX64.EFI` was byte-identical to the old `/boot/loader.efi`
(`2058bc3b47a6a98b03c7f69c99416b272a31bdefa6415e16e9b171c5ba158e51`),
so the known MacBook countdown defect remained. The revised image replaces
both live EFI paths with the exact corrected loader previously staged on the
MacBook. A private selection file pins its SHA-256, and the installer copies
that loader into the MacBook target before writing the installed ESP; other
machines continue to use the loader from the release sets. The corrected
production source passed frozen-clock native controls and an OVMF countdown
probe. Physical boot of this revised image remains to be tested.

The operator's first installer Wi-Fi scan found only one of eight nearby
networks. The first join timed out after 60 seconds; the second attempt
reported success, but a later debug-shell check showed WPA complete with no
IPv4 address or default route. Background DHCP clients were already running
on both the wired and wireless interfaces. Killing only the wireless client
and retrying DHCP yielded an offer, ACK and lease. The first associated BSSID
had very weak signal and later lost most gateway packets. The kernel printed
a nonfatal Broadcom lock-order reversal; its role is unknown. The revised
installer marks `wlan0` `NOAUTO`, stops any old wireless DHCP client before
joining, collects results from four scans over at least nine seconds, permits
up to 120 seconds for WPA, and bounds DHCP at 60 seconds. It waits briefly
after DHCP and requires a remaining IPv4 address and default route via
`wlan0`. When Ethernet owns that route, it explains that the operator must
disconnect it and retry Wi-Fi for a Wi-Fi-only install. The network screen
shows both states and failures report their stage. Delayed-radio regression
tests pass; fresh physical installation with this image remains open.

The first live image also returned a malformed security information element:
`ifconfig -v wlan0 list scan` printed an enormous RSN record and segfaulted.
The native-built diagnostic module in the revised image validates RSN and WPA
cipher/AKM list bounds before publishing scan records. Its source change is
retained in [the driver patch](../patches/brcmfmac/bcm4364-security-ie-bounds.patch),
against a private diagnostic `src/scan.c` snapshot with SHA-256
`8f05c5f93f10e41cf715364c416b1d2a0725c9eef1cf453282fa4f1f1aa1dc59`.
After a live `kldunload`/`kldload` cycle, the new module returned ten BSSIDs
without an `ifconfig -v` crash. An active scan joined the stronger hidden AP;
Wi-Fi-only tests then returned 20/20 gateway pings and 10/10 Internet pings,
and downloaded a 22,060-byte HTTPS page with the default route on `wlan0`.
This is module-reload evidence, not a fresh boot qualification. A manually
terminated foreground DHCP diagnostic left an empty resolver file; DNS worked
after adding a nameserver. The revised installer uses normal DHCP rather than
that foreground diagnostic command.

The staged B3 binary, `bali-HRPN-u` board data, CLM and TxCap blobs came from a
source package declaring its license `unknown`. They are absent from Git and
must not be published without verified redistribution rights or replaced by
a supported acquisition path. The diagnostic driver is not yet integrated as
a maintained port. MacBook Wi-Fi joined WPA2, obtained DHCP and reached the gateway
before this image was built; the physical preview image has not yet been
booted. The machine later temporarily stopped answering on its wired debugging
address, then recovered with uninterrupted uptime, low load, and WPA2/DHCP
restored. The operator reports the desktop remained responsive. A later
source-bound gateway ping returned 8/8 replies. Repeated roaming/association
attempts appear in the retained log;
the cause of the network interruption remains open.
Reboot stability and the earlier NVMe interruption remain release
gates. The MSI laptop or desktop has not been qualified by this preview.

## 2026-10-23 link-loss follow-up

The live installer later retained `wpa_state=COMPLETED`, an IPv4 lease and a
default route while gateway pings failed with `Host is down`. The driver still
logged IPv4 frames entering `vap_transmit` in VAP state RUN. Its kernel log
also recorded a firmware `E_LINK` down event followed by `ignoring E_LINK down
in RUN`; the interface therefore continued to report association after the
firmware had signaled a lost link. Reassociation alone did not restore traffic.
After wired debugging was re-enabled, a later probe routed over `wlan0`
returned 3/3 gateway replies and transmit completions advanced. The exact
recovery trigger was not established.

A native-built experimental module narrowed the link-down exception to the
period before pairwise-key installation. A live module-swap test reached WPA2
`COMPLETED` on a weak AP, but DHCP did not obtain a lease. Subsequent attempts
on stronger APs flapped between link UP and DOWN without a lease. This was
insufficient to qualify the change; the original diagnostic module was
restored. Repeated live module reloads then left firmware scans reporting
BUSY, so a cold boot was selected for the next comparative test. A separate
diagnostic-only module that records firmware link event status, reason and
key-install timing builds natively, but has not been tested on the MacBook.

The retained physical `wifi-current-dmesg.gz` has SHA-256
`7ad37b99c8c64ad81a949b18f60357cb8d2480653cf2531a3f87325e50aba44e`.
Its first `E_LINK` down event occurs while the VAP reports state 5 (RUN), and
the driver explicitly ignores it. Before the following failed `SET_SSID`
event, `vap_transmit` logs another 56 IPv4 and 30 ARP frames, all still in
RUN. These are requests entering the driver, not evidence that the AP received
them. The experimental link-fix trace has SHA-256
`592589cf816e3368bf5364d0beb0d4a7cb6ead1a3a1c64d285a28425fa4b059f`;
its link flaps and failed DHCP remain a negative result.

The [upstream Linux brcmfmac connection handler](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/net/wireless/broadcom/brcm80211/brcmfmac/cfg80211.c)
recognizes an `E_LINK` down event, then checks the event BSSID against the
connected profile before disconnecting. This is a behavior reference, not an
untested FreeBSD patch or a claim about the exact Omarchy kernel revision. The
next physical trace must record event status, reason, BSSID, current BSSID and
pairwise-key state around a failed traffic window. The logging-only module
retained for this purpose has SHA-256
`f541d1ede54a7be281bba0699a9eff3811a22a12716f3509c216ddcf971bdf3c`.
At the 2026-10-23 recheck, the SSH listener was closed; this module had not
been loaded on the MacBook and the cause of the ignored event was unproven.

A fresh diagnostic-only copy of the FreeBSD driver was built cleanly on the
native FreeBSD worker at
`/usr/daemonarchy/brcmfmac-link-event-trace-20261023/if_brcmfmac.ko`.
Its SHA-256 is
`065eb4019d10aa2b11afcded429d1418be59bc3a1013053152571ad7b271a5c8`;
the retained source patch is
`/usr/daemonarchy/brcmfmac-link-event-trace-20261023/diagnostic.patch`
(SHA-256 `4c935d4cfd0dddccd2cb8fe217a27f612311e54fa22341f78257b272bc29db56`).
The patch logs firmware event status, reason, flags, event and selected BSSID,
VAP state, and whether a pairwise key was installed since the latest join. It
does not change link handling. The native worker built it against a
`bdcfeac3e1cb` kernel. The worker's `/boot/kernel/kernel` SHA-256 is
`94e4ace9d6b6083f682d1a0d325162d10d0db852aa82400f7b59655e4df507b2`,
matching the documented preview kernel above. The MacBook's currently booted
kernel and target module hash must still be checked before any live swap. No
physical test of this module has occurred.

The later packaged driver [ports PR #23](https://github.com/jordanhubbard/daemonarchy-ports/pull/23)
head `311ca12eba9c968d2f3f20bb383210c6934f8672` contains the same four
diagnostic source changes and no longer prints every VAP transmit attempt to
the console. Its `PORTREVISION=1` package has not completed a fresh native
`testport` or run on this MacBook. Once a matching module is installed, capture
these read-only counters before and after a failed DHCP or gateway probe over
the wired debugger:

```sh
sysctl dev.brcmfmac.0.diag_tx_vap_count dev.brcmfmac.0.diag_tx_fw_dead \
  dev.brcmfmac.0.diag_tx_no_flowring dev.brcmfmac.0.diag_tx_ring_full \
  dev.brcmfmac.0.tx_count dev.brcmfmac.0.tx_complete \
  dev.brcmfmac.0.rx_complete
```

Record the booted kernel and module hashes first. These counter deltas can
locate the transmit stall; they cannot by themselves prove AP delivery.

The controlled reboot first selected the existing ZFS installation instead
of the USB installer. A one-time EFI boot entry was created for the attached
USB, with the normal disk BootOrder restored. The installed system later
reappeared over a wired debugger, but it still ran the 1.1.1 desktop and had
no attached Wi-Fi interface on arrival: the last installer attempt had failed
in Wi-Fi setup.

### October 23 installed-system transmit check

The booted `MacBookPro16,1` kernel matched the native worker's
`bdcfeac3e1cb` kernel hash above. A diagnostic `if_brcmfmac.ko` built against
that exact kernel was copied to the MacBook and verified with SHA-256
`58163ef0d117d9da81710ce153d7d2beb777beae9a3891d27cd6c6cca67d3bb6`.
The four required private firmware and board files were already in
`/boot/firmware`. Loading the module attached BCM4364 revision 4; creating
`wlan0` and starting the existing local WPA profile reached
`wpa_state=COMPLETED`. DHCP then assigned a /23 address without exposing
the profile secret. The wired debugger stayed reachable.

The active route initially favored Ethernet, so a temporary host route sent
four gateway probes through `wlan0`; all four returned in 1.1–4.5 ms. Driver
transmit and completion counters both rose from 20 to 24. Firmware-dead,
missing-flow-ring and ring-full counters remained zero. The temporary route
was removed, restoring the wired route. This proves local Wi-Fi data traffic
in this manually repaired installed session. It does not prove that the
installer configures Wi-Fi reliably, that traffic survives a reboot, or that
the later packaged port has the same behavior. Those remain release gates.

A later scan while associated returned 27 access-point entries. A 60-packet
gateway probe using 1200-byte payloads through `wlan0` lost no packets; mean
round-trip time was 2.028 ms, transmit and completion counters both reached
92, and the three diagnostic drop counters stayed at zero. The existing WPA
association remained complete. This is a short installed-system check, not a
replacement for the installer and reboot tests.

The later scan also provoked roaming among APs advertising the same network.
The radio briefly reported no carrier and WPA moved through ASSOCIATING and
ASSOCIATED before returning to COMPLETED without manual intervention. The
logging-only driver recorded a matching link-down event, an authentication
event with reason 15, then a new pairwise key. The wired debugger remained
reachable because a temporary host route pinned its controller to the wired
interface; after wireless DHCP, the overlapping wired and wireless /23 routes
had otherwise selected the wireless interface for that controller. This short
recovery does not resolve the earlier persistent traffic stall. Multi-AP
roaming and stable debugger routing with both interfaces active need a fresh
physical check.

A controlled Wi-Fi-only route probe left the wired address configured while
temporarily bringing its link down. FreeBSD still selected that interface for
the default gateway even when the default route was recreated with the
wireless interface specified. Four of five Internet probes failed with
`Network is down`; the fifth succeeded only as the wired link returned.
An automatic recovery restored the wired link and default route, and WPA
returned to COMPLETED. A successful gateway probe on `wlan0` therefore does
not yet qualify package downloads over Wi-Fi with both interfaces configured.
With an active wired link, the installer reports this route conflict and asks
the operator to disconnect that link before installing over Wi-Fi.
With the wired DHCP client stopped and its address removed, the default route
selected `wlan0`; eight Internet probes returned with no loss and the debugger
remained reachable on its Wi-Fi address. The wired address was then restored.
This proves a bounded Wi-Fi-only route and traffic path, but the installed
system did not go through the new installer handoff or reboot on Wi-Fi.

The installer candidate now handles a disconnected Ethernet adapter that
retains a stale lease: after WPA and Wi-Fi DHCP complete, it checks the wired
carrier, releases only that adapter's DHCP client and address, and installs
the router from the wireless lease. It leaves an active wired debugger intact
and reports the route conflict. The real scan/join test passes on Linux and
the physical FreeBSD MacBook's shell; the automatic handoff still needs a
fresh installer run.

### October 23 reassociation ring trace

A second diagnostic module, built against the running MacBook kernel, logged
the selected BSSID and PCIe transmit-ring lifecycle without changing driver
behavior. After a clean association and wireless DHCP lease, a requested WPA
reassociation caused carrier loss and repeated AP selection. For an AP change,
the trace showed deletion of the prior flow ring and creation of a ring for
the new BSSID. The missing-ring and full-ring transmit counters remained zero,
and submitted packets completed. This rules out an unchanged flow-ring BSSID
as the simple cause of this reproduced stall.

Several subsequent associations ended in firmware authentication event reason
15 before WPA could remain complete; at least one occurred before a new
pairwise key was installed. Another transiently reached WPA COMPLETED, then
lost carrier. The APs in the last scan had weak signals, so the trace alone
does not distinguish a driver handshake or event-ordering defect from AP
selection and radio conditions. Keep the Wi-Fi installer path in draft until
a repeated physical install and reboot demonstrate stable association, DHCP,
default routing and package downloads. The temporary trace module is retained
only on the test machine and native builder, not in the release image.

An Ethernet-header-only EAPOL capture during one failed attempt saw four
retries of the AP's first key message. The capture did not show outbound key
frames even during a later successful exchange, so this capture point cannot
prove whether the station sent a reply. A later supplicant debug session on a
different, weak AP recorded receipt of message 1, sending
message 2, receipt of message 3 and sending message 4; WPA briefly reached
COMPLETED before carrier dropped again. This narrows the failure to an
intermittent association or handshake path, without proving that the driver
discarded any particular key frame. Supplicant logs are root-readable private
test artifacts because they contain handshake material; no payloads are
included in repository evidence.

On a later failed attempt, the supplicant again recorded receipt of message 1
and three attempts to send message 2. Over the bounded attempt, the VAP entry
counter rose while PCIe bus submission and completion counters did not. The
driver reported no firmware-dead, missing-ring or ring-full drops. The coarse
counter gap motivated an EAPOL-specific check; it did not identify a frame or
branch. A subsequent diagnostic module logs only EAPOL frame length, EtherType
and VAP state; a clean WPA exchange with the
module showed contiguous Ethernet headers and two bus submissions. A later
failed exchange also showed EAPOL frames arriving at the VAP in RUN state with
contiguous Ethernet headers, ruling out that VAP's early state and short-header
drop branches for the traced frames. The coarse counter gap can include other
traffic while the VAP is down; it does not prove EAPOL was dropped. The wired
debugger temporarily stopped answering during reassociation, then recovered
without a reboot. No stronger driver conclusion is recorded here.

During the same installed-system session, a completed supplicant scan returned
29 BSS entries representing eight distinct SSIDs across both 2.4 and 5 GHz.
An immediate second scan returned `FAIL-BUSY` while the first was pending.
This supports the installer's repeated, delayed scan UI; it does not establish
that the installer image discovers all eight networks or joins one reliably.

After restoring ordinary supplicant operation, WPA reached COMPLETED and
wireless DHCP assigned an address again. A one-minute, 120-packet gateway
probe with 1200-byte payloads used the `wlan0` route and received 117 replies
(2.5% loss; mean round-trip 6.391 ms). The selected AP changed during the
probe; WPA and the DHCP address were still present afterward. No missing-ring
or ring-full transmit drops were recorded. This establishes that the recovered
link carries traffic, while its packet loss and reassociation remain a release
blocker for a Wi-Fi-only installation claim.

The supplicant's private debug log labeled two failed four-way handshakes
`WRONG_KEY` after the AP repeated message 1. The same saved profile completed
the handshake on other BSSIDs advertising that SSID, and scan flags reported
WPA2-PSK/CCMP for both successful and failed BSSIDs. The label is a timeout
interpretation, not proof that the password entered by the operator was wrong:
the remaining possibilities include inconsistent AP credentials and loss or
rejection of the station's second key message. No AP-side capture is available.

### Installed debugger Wi-Fi recovery

The retained-grant helper was live-installed on the incomplete MacBook system.
With WPA complete and a wireless DHCP address present, it retained the active
supplicant profile and wireless parent in root-only state. The profile was mode
0600 and byte-identical to the active configuration. A controlled test stopped
only wireless DHCP and the supplicant, destroyed `wlan0`, and invoked
`daemonarchy-debug wifi-resume` while leaving Ethernet and the approved debug
listener intact. The helper recreated `wlan0`, started WPA from the retained
profile, reached COMPLETED and reacquired DHCP. The grant and listener remained
active. Automatic profile retention during public-status publication was also
verified. This does not prove reboot recovery on this incomplete installation:
the packaged BCM4364 module is still absent from its boot filesystem.

### Bounded single-AP traffic probe

On October 23, the installed system temporarily pinned its currently
successful BSSID in the supplicant, kept wired debugging enabled, and sent
300 gateway probes with 1200-byte payloads over `wlan0` at 0.2-second
intervals. All 300 replies arrived (0% loss; mean RTT 5.192 ms, maximum
116.589 ms), and WPA remained COMPLETED. After the temporary BSSID pin was
cleared, the supplicant returned to SCANNING, `wlan0` lost carrier and its
DHCP address disappeared. A separate wired SSH attempt timed out briefly,
then the debugger returned without a reboot. Re-pinning the last successful
AP restored WPA and DHCP; the runtime pin remains active for diagnostic work.
This bounded result shows steady traffic on one AP and a failure during
unrestricted reassociation. It does not establish the cause of the failed
handshake, reliable roaming or installer Wi-Fi.
