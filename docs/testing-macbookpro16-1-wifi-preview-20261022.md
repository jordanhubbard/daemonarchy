# Private MacBook Wi-Fi preview image, October 22, 2026

This is a hardware test image, not a release candidate or public download.
It keeps the 1.1.1 kernel, base sets and package repository, updates the live
installer and rescue scripts from the integration branch, and stages the
private BCM4364 module and four board-specific firmware files. The installed
target copies those files and enables the module after its root is mounted.

| Artifact | SHA256 |
| --- | --- |
| Baseline `daemonarchy-1.1.1-amd64.iso` | `c1bc6e3a0d30e6806a324aa3abd76eb70f1593f9f22e7aab6d222491fc1eb956` |
| Private `daemonarchy-macbook-wifi-preview-20261022-amd64.iso` | `d5233835fc562b23a25a82189053ce2d9149bcf2fec2b03e9f0a46bf4f04b82d` |
| ISO and MacBook kernel | `94e4ace9d6b6083f682d1a0d325162d10d0db852aa82400f7b59655e4df507b2` |
| Native-built `if_brcmfmac.ko` | `4019af87238b839a9708c68b12f7c506678cf9433b2186ce98618f1f8d62b46a` |

The baseline's hidden BIOS and EFI El Torito images were extracted and used
when rebuilding the preview. The original volume label was retained because
the EFI loader uses it for the live root. Files were extracted with root
ownership and identical hard-linked content was deduplicated before image
authoring. The resulting 1.8 GiB image has protective MBR, GPT and both boot
entries. An OVMF/QEMU boot reached the installer welcome screen with the
preview label. A full VM install and physical fresh install are still pending.

The staged B3 binary, `bali-HRPN-u` board data, CLM and TxCap blobs came from a
source package declaring its license `unknown`. They are absent from Git and
must not be published without verified redistribution rights or replaced by
a supported acquisition path. The diagnostic driver is not yet integrated as
a maintained port, and the baseline image retains its older desktop/GPU
packages. MacBook Wi-Fi joined WPA2, obtained DHCP and reached the gateway
before this image was built; the physical preview image has not yet been
booted. The machine later stopped answering on its wired debugging address,
so the duration and cause of that outage require physical/log inspection.
Reboot stability and the earlier NVMe interruption remain release
gates. The MSI laptop or desktop has not been qualified by this preview.
