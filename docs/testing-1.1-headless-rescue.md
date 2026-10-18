# Private headless rescue checks, 2026-10-15

Historical 1.1 development/candidate evidence. Revisions, checksums and results
below apply to the named artifact and date; they do not qualify the new
[1.1.1 source/package set](testing-1.1.1.md). Follow that record for current
preparation and publication status.

A separately prepared rescue overlay was built into an unpublished development
ISO using installer revision `7399015575401c9d64cd2391db1c02517266b8f8` and
the same kernel/package set as preview.12. Its host key and operator public key
are private test inputs and are not included in the public image or repository.

The image passed the native live-runtime audit and the size gate at
1,922,768,896 bytes. Copies on the operator machine and QEMU worker matched
SHA-256 `05a51255501dbfe38a5eed06a9be1c56c550717052e17eee0b12fac00e7d53b6`.
The audit now takes an explicit `headless` role for private images. Its default
`public` role rejects rescue authorization or an automatic rescue SSH service.
Both role checks passed against the actual public preview.12 and private ISO;
the private authorization files are root-owned with mode 0600.

It then booted in a QEMU/KVM UEFI VM with a blank 40 GiB virtio disk and an
existing CIDATA CD containing an unattended installation configuration.

| Check | Result |
| --- | --- |
| Startup without console input | Dedicated SSH listener started on port 2222 |
| Server identity | Client pinned the overlay's generated host key |
| Operator authentication | Selected key accepted for root; private client key stayed on the operator machine |
| Other key | Rejected with `Permission denied (publickey)` |
| Effective SSH configuration | Public key required; password and keyboard-interactive authentication disabled; forwarding disabled |
| Driver autoload | BCE and desktop GPU modules absent; loader's devmatch block list present |
| Stale unattended media | CIDATA visible, console launcher reached, no installation configuration or log created |
| Target disk | No partitions or imported pool; QMP block statistics showed zero write operations and zero bytes written |
| Shutdown | Guest shut down over the authenticated rescue connection |

Logs, authentication results, disk statistics and the private image are retained
in the operator's `2026-10-15-headless-rescue` evidence directory. The disposable
VM was stopped after validation. No USB device was written.

This verifies the rescue mechanism on a native FreeBSD guest. It does not prove
Ethernet availability, BCE behavior, graphics or keyboard support on the T2
MacBook Pro, nor provide networking after a kernel panic. Physical rescue boot
and an exact panic backtrace remain outstanding.
