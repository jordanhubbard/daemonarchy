# MacBookPro16,1 physical acceptance for 1.3.1

Status: **open**. This is the acceptance record for the final public 1.3.1
image, not a result from the installed 1.1.1 system or the private development
ISO. Fill in the exact revision and artifact identities before beginning the
physical run; retain console, debugger and package evidence outside Git when it
contains private network or credential details.

| Final input | Exact value and evidence |
| --- | --- |
| Product commit and release tag | Pending |
| FreeBSD source and ports commits | Pending; the private preview uses older source sets |
| ISO SHA-256 and signed boot-bundle identity | Pending |
| Package and checkout feed tags, keys and signature checks | Pending |
| BCM4364 module package and Apple board-file hashes | Pending |

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
- [ ] Enroll the matching public certificate in UEFI **db** while preserving
  existing PK, KEK, OEM/Microsoft db entries and dbx. Confirm firmware
  enforcement on the physical MacBook, boot the installed system, reject an
  untrusted boot component, and pass signed update, failure rollback and
  recovery tests. See the [manual enrollment contract](secure-boot.md).
- [ ] Verify the versioned package and checkout feeds using only the new
  public key, then perform an installed package update and reboot. Retain
  exact package, boot and image digests with the signed release record.

After the MacBook passes, run the separate MSI hardware and network-aware
early-boot acceptance before declaring the full 1.3.1 hardware matrix complete.
No row here is closed by a development-kernel desktop login or a successful
installer exit alone.
