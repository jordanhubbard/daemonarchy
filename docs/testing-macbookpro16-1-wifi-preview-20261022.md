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
| Private `daemonarchy-macbook-wifi-preview-20261022-amd64.iso` | `7db7756c0685ea6069246933db5494c008ffbf550797171064be306dfe81adc6` |
| ISO and MacBook kernel | `94e4ace9d6b6083f682d1a0d325162d10d0db852aa82400f7b59655e4df507b2` |
| Native-built `if_brcmfmac.ko` | `4019af87238b839a9708c68b12f7c506678cf9433b2186ce98618f1f8d62b46a` |
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
