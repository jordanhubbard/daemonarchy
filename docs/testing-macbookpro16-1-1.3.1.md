# MacBookPro16,1 physical acceptance for 1.3.1

Status: **pre-production checks passed by operator confirmation; additional
final-ISO physical rerun waived on 2026-10-24**. The operator confirmed that
all pre-production checks passed on the Intel 16-inch MacBook Pro. The final
public 1.3.1 ISO has not been run on that machine. This record preserves the
scope of the earlier observations and the decision to release without another
MacBook acceptance run. The machine and its pre-production validation must not
be described as untested. The exact decision is recorded in
[the release decision](../verification/macbook-release-decision-1.3.1.json).

Every unchecked physical item below means **not rerun against the final public
ISO**, not a failed pre-production check. No earlier result is rebound to final
ISO bytes. Production build, feed, signing, image-integrity and publication
checks remain mandatory and are recorded separately.

Retained pre-production records include the [installed-system MacBook
observations](testing-macbookpro16-1.md), [Wi-Fi preview and traffic
traces](testing-macbookpro16-1-wifi-preview-20261022.md), and [installer and
storage investigations](testing-macbookpro16-1-installer-20261022.md).
The [1.1.1 S3 trial](testing-macbookpro16-1-s3-20261024.md) keeps its historical
failure result. These records keep their own image and test scope; the later
October 24 aggregate pass is explicitly an operator confirmation, not a
retroactive rewrite of any individual run.

| Final input | Exact value and evidence |
| --- | --- |
| Product commit and release tag | ISO build pinned to `cdeb3434a2f7e5e205feb756c897b1e4a98d4c28`; final `daemonarchy-1.3.1` tag pending. No final-ISO MacBook run is required by the October 24 operator decision. |
| FreeBSD source and ports commits | `d63d77f4eb3cc29e16510f7bdec73602e27c2844` and `7e417dae24ffb95c4625601ae9d654eb2ca68f4d`; final native build pending |
| ISO SHA-256 and signed boot-bundle identity | Pending |
| Package and checkout feed tags, keys and signature checks | Public `checkouts-16-amd64-1.3.1` verified with 11 matching asset digests and a native FreeBSD `pkg` catalogue read; `packages-16-amd64-1.3.1` and installed signature checks pending. Selected package public key SHA-256: `67986b400f28a49e99df0f1f3368f60aca8064d5dc00094700ba1a17d8474ef7` (DER form). |
| BCM4364 module package and Apple board-file hashes | Module package and image hashes pending; installed-target hashes will not be collected in a final-ISO MacBook rerun. Pinned Apple recovery image SHA-256: `591f07a9a4a58d855a2e53b86a5f5da854a250000a66a9382adaf106c20f839b`; the four expected board-file hashes are in the [firmware importer](../scripts/import-apple-bcm4364-firmware.py). The private source stage passed its hash check, but that does not verify the public ISO contents. |

The `iso_installer_commit` identifies the source built into the ISO
(`cdeb3434...`). The release record separately identifies the final tagged
product commit, which can include later release notes and policy changes
without changing ISO bytes. The pre-production confirmation does not identify
a final-ISO SHA-256 or claim a physical boot of those bytes.

On 2026-10-24, an isolated FreeBSD `pkg` 2.8.4 client configured with the
selected public key updated the published checkout repository and processed
three packages. `pkg rquery` returned the ports checkout at
`20261023.g7e417dae24ff` and both source parts at
`20261023.gd63d77f4eb3c`. This checks the public catalogue and native client
trust path; installation from the public ISO is not claimed and its additional
MacBook rerun is waived.

## Fresh installer boot and storage

- [ ] Boot the exact image without pressing Enter. The EFI autoboot countdown
  advances and boots after its advertised three seconds; Space still pauses it.
  Rescue and retained remote-debug access remain available when selected.
- [ ] Verify the MacBook's EFI disk and NVMe controller before erasing. Record
  the selected disk identity, installation progress and any NVMe error status.
  The installer must finish package extraction, first boot and a later package
  upgrade without the earlier fatal NVMe event. Apple Diagnostics `ADP000`
  remains supporting evidence, not a substitute for this I/O run.
- [ ] Verify the installer preserves its EFI and recovery choices and reports
  an actionable error before writes if firmware, boot bundle or disk validation
  fails. Record the final partition layout and active boot environment.

## Wi-Fi from a wiped disk

- [ ] On the public image, prepare BCM4364 B3 firmware from the pinned Apple
  recovery source or operator-supplied local media. Verify its provenance and
  four board-file hashes before partition writes. The private preview's
  embedded firmware cannot qualify public-image acquisition. See the
  [firmware handoff record](testing-macbookpro16-1-firmware-handoff-20261023.md).
- [ ] Scan more than once and confirm the expected nearby network choices are
  visible. Join the selected AP with the password entered locally. Record WPA
  completion, `wlan0` IPv4 address, DHCP gateway, default-route interface and
  DNS/time setup without recording the password or SSID in public evidence.
- [ ] With Ethernet disconnected after debugger capture is safely staged,
  fetch installation packages and pass gateway, Internet and DNS traffic over
  Wi-Fi alone. Reconnect Ethernet for debugging as needed; then recheck that
  the installer can deliberately select the wireless route while both
  interfaces hold addresses. Exercise reconnect and another AP advertising
  the same network name.

## Installed desktop and recovery

- [ ] Reboot from the installed disk. Confirm normal GPU initialization, login,
  sustained keyboard input without repeated or batched key events, and usable
  trackpad movement/clicks. Verify the network panel lists and reconnects to
  Wi-Fi, and the remote-debugging menu shows the retained grant and listener.
- [ ] Reboot again and resume the approved debugger without another pairing
  confirmation. Confirm the saved Wi-Fi profile permits debugging over Wi-Fi
  and that Ethernet can independently recover the agent. Test explicit unpair
  only after the retained-grant checks.
- [ ] Check NVMe I/O and health counters after the install and package upgrade;
  preserve kernel and installer logs for any controller reset, media error,
  lock-order reversal or Broadcom firmware trap.
- [ ] Decide whether S3 is required for 1.3.1. The installed 1.1.1 system
  [failed its physical S3 trial](testing-macbookpro16-1-s3-20261024.md), with
  ACPI, input and Wi-Fi failures. If required, repeat suspend/resume on the
  exact final image and qualify display, input, storage, both network paths
  and debugger recovery across multiple cycles.

## Production boot attestation and release

- [ ] Bind the final kernel, external modules and four firmware files into a
  bundle signed by the protected production authority. Verify the bundle,
  module inventory, source/jail identities and image contents independently.
- [ ] Record the MacBook's actual T2 boot policy and test the signed installer,
  installed boot files, rejected untrusted component, signed update, failure
  rollback, and recovery. Apple's documented T2 Full and Medium policies do
  not provide the generic UEFI **db** enrollment route assumed in the
  [manual enrollment contract](secure-boot.md#apple-t2-macbook-limitation).
  If FreeBSD boots only under No Security, record that firmware enforcement is
  absent; project signature checks alone cannot close a hardware-rooted boot
  attestation requirement.
- [ ] Verify the versioned package and checkout feeds using only the new
  public key, then perform an installed package update and reboot. Retain
  exact package, boot and image digests with the signed release record.

The earlier 1.1.1 NVMe, network and S3 observations remain historical records
for their recorded images. They are not presented as current 1.3.1 publication
blockers or as results from the final ISO. Actual T2 firmware enforcement and
hardware-rooted attestation for the final ISO are not claimed.

The separate MSI hardware and network-aware early-boot acceptance belongs to
[1.3.2](roadmap/release-1.3.2.md). Do not treat MacBook acceptance as MSI
qualification.
No final-ISO checkbox here is closed by the operator's pre-production
confirmation, a development-kernel desktop login, or a successful installer
exit alone; those observations retain their own artifact scope.
