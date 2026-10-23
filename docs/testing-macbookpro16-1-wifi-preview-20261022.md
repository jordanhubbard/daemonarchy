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
`bdcfeac3e1cb` kernel; the target kernel identity and module hash must be
checked before any live swap. No physical test of this module has occurred.

The controlled reboot first selected the existing ZFS installation instead
of the USB installer. A one-time EFI boot entry was created for the attached
USB, with the normal disk BootOrder restored; physical USB boot and renewed
remote debugging are pending. No complete fresh Wi-Fi installation, rebooted
wireless qualification, or release attestation follows from this session.
