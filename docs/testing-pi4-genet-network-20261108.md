# Pi 4 GENET network simulator control

`tools/hwtrace/pi4-network-simulator.py` tests the actual FreeBSD FDT GENET
driver through DHCP, authenticated SSH and bidirectional SCP. It reuses the
U-Boot/FDT boot, storage and offline diagnostic checks. It does not substitute
a PCI/USB NIC or provide an ACPI GENET frontend.

The emulator must implement the opt-in real GENET profile. The default
controller-only profile remains a separate control. The runner selects:

```text
-nic none
-netdev user,id=genet0,restrict=on,hostfwd=tcp:127.0.0.1:PORT-:2222
-global bcm2838-peripherals.genet-network=on
-global bcm2838-genet.netdev=genet0
-global bcm2838-genet.mac=52:54:00:12:34:56
```

Only loopback forwarding is opened. Every run generates a VM-only client
identity and server host key in a fresh private output directory. Their
public keys and the server key are added only to the copied diagnostic
image. The controller prepopulates `known_hosts` with that server key and
requires `StrictHostKeyChecking=yes`; it does not learn identity from an
unverified scan or use the operator's SSH agent. No source image, physical
board or removable device is modified. The output image contains test SSH
keys and stays private; do not publish it as installation media.

## Run the control

Use the normal diagnostic FDT image containing `genet`, `miibus`, the native
PHY drivers and the existing network hand-over payload. The retained kernel
`8ec36736678f4de5308164fe6dfe990119b6ff042bf6eec6887ddd3ee84c60c9`
has both `brgphy` and `ukphy`; its rescue world includes DHCP, SSH/SFTP/SCP,
`ifconfig`, `netstat` and the rescue `md5`/`dd` applets. A new world build is
not needed for this control.

The controller needs OpenSSH client tools, `mtools`, `fdtget`/`fdtput` and
`toolscheme` on PATH, alongside Python and the selected QEMU build. All inputs
must be regular files and the source DUMPS directory must be empty:

```sh
python3 tools/hwtrace/pi4-network-simulator.py \
  --image "$IMAGE" --image-sha256 "$IMAGE_SHA256" \
  --uboot "$UBOOT" --uboot-sha256 "$UBOOT_SHA256" \
  --dtb "$DTB" --dtb-sha256 "$DTB_SHA256" \
  --qemu "$QEMU" --qemu-sha256 "$QEMU_SHA256" \
  --qemu-img "$QEMU_IMG" --output "$FRESH_PRIVATE_OUTPUT"
```

For full-memory coverage add `--machine raspi4b-8g
--memory-min-bytes 7516192768 --memory-max-bytes 8589934592`. These bounds
check the guest's actual `hw.physmem`; they do not change firmware or kernel
memory limits. The default remains the 2 GiB model.

The runner keeps the source image unchanged, configures only the copied FDT's
console and virtual MAC, and verifies `SLOTS.MAP` after adding keys and the
fresh queue. The queue enables a 30-second DHCP attempt and a 120-second
hand-over. Observable banner waits use bounded `toolscheme` conditions;
a helper timeout is a wait result, not a guest reset or successful hand-over.
The total controller deadline remains bounded.

## Required evidence

A successful result requires all of the following:

- The original four-CPU FDT/SD-root boot, seven completed probes, clean storage
  diagnostics, synchronized guest reset and natural emulator exit.
- Native `genet0`, the configured virtual MAC, active link and DHCP IPv4 address.
  An additional Ethernet interface or a replacement NIC cannot satisfy the check.
- Root SSH authentication with the preprovisioned VM host key. Each remote
  command returns a fresh complete nonce frame; exit status zero alone is insufficient.
- A random 1 MiB upload to guest `/var/tmp`, its download round trip with equal
  SHA-256, and a separate guest-generated 1 MiB download with the expected SHA-256.
  Guest rescue MD5 observations corroborate the files; controller acceptance
  uses their exact sizes and SHA-256 values.
- Native GENET counters covering at least 1 MiB in each direction, plus durable
  `network.txt`, `network-ifconfig.txt`, `network-netstat.txt` and a fresh run
  token in offline DUMPS. The queued label must match the collected `kenv`.
- A normal `hwtrace-continue` request followed by the normal reset path and an
  unchanged source-image hash.

Controller tests reject a replacement NIC, wrong MAC/IP, no carrier, false or
partial SSH output, missing/partial/wrong-hash SCP files, stale queue evidence,
ambiguous address records and incomplete diagnostics. The existing boot/storage
guards remain required.

## Measured checkpoint

The first actual FreeBSD run identified the PHY as `BCM54213PE` through
`brgphy`, at PHY address 1, but reported link down. The emulated Broadcom
family identifier was retained. Implementing the backend-derived vendor
AUXSTS register resolved the native driver's link check; forcing a generic
PHY driver was not used.

QEMU SHA-256
`9af365a27bfdbae57792666ce1d0d7cd136379ed6a8eabd1a0ab90009c6dbfe6`
then passes the 2 GiB control's 26 checks. GENET reports 1,225,528 input bytes
and 2,246,233 output bytes with zero input/output errors in that run. Both
payload directions and the uploaded file's round trip match their expected
SHA-256 values. Host-key verification, all seven probes, offline diagnostics,
normal continue/reset and original-image integrity pass.

The same frozen emulator, kernel and controller also pass the 8 GiB profile's
27 checks. The guest reports `hw.physmem=8430014464` bytes; the additional
check requires at least 7 GiB without a kernel memory override. Native GENET
link, DHCP, authenticated SCP in both directions, the upload round trip,
all probes, storage diagnostics, offline evidence and the natural reset
pass again with the source image unchanged.

The final model also preserves a partially assembled TX frame across separate
producer doorbells and migration. Its QEMU SHA-256 is
`bb79102f8cdebdd0da7f0678507a9281f496934f1089d8b1ab4b7f8f20f85ca6`.
A fresh native kernel
`77b90b794de95ec3908f4c182dae972fa81265f0dfeec527de23a8ce69aee328`
then repeats the complete public control with unchanged runner/helper bytes:

| Profile | Checks | Guest `hw.physmem` | GENET input/output bytes | Errors/drops |
| --- | --- | --- | --- | --- |
| 2 GiB | 26/26 | 2,054,680,576 | 1,225,228 / 2,245,839 | 0 |
| 8 GiB | 27/27 | 8,430,018,560 | 1,225,552 / 2,246,369 | 0 |

Both final runs preserve 15 offline diagnostic files, all seven probe statuses
are zero, SSH verifies the provisioned host key, and the bidirectional payloads
and upload round trip match their expected hashes. Native SD root, clean
storage, natural continue/reset and original-image integrity pass again.

These are actual guest-stack packets through the modeled MAC/DMA/interrupt
path and QEMU user networking. They do not qualify a physical PHY, cable,
Ethernet performance, an ACPI GENET frontend, or Pi 5/RP1.
