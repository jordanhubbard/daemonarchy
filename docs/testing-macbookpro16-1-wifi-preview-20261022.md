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
