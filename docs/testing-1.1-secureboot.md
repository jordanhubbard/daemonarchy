# Secure Boot prototype evidence

Development checks on 2026-10-15; this is not an installer feature or a claim
that the release supports Secure Boot yet.

On 2026-10-16 the operator selected manual certificate enrollment for 1.1.
The production path must document adding the Daemonarchy certificate without
replacing existing OEM/Windows trust entries, plus revocation and recovery.
Booting under factory keys without enrollment is not the selected requirement.
This decision does not qualify the prototype as an installer feature.

A native FreeBSD loader was built from the selected October 12 source revision
`3ceb5f150bc121f5e6a3e0cc8b289279338405a1`. The Lua EFI loader enables BearSSL,
loader veriexec and EFI Secure Boot support. A disposable development certificate
is embedded as a manifest trust anchor and enrolled into a separate OVMF variable
store as PK, KEK and db. No physical machine's firmware variables were changed.

The signed loader boots a GPT image containing an EFI system partition and a
fresh UFS root extracted from the matching official base and kernel sets. A
signed `/boot/manifest` records SHA-256 fingerprints of the boot files, including
the Lua scripts, loader configuration and kernel. The kernel is the unmodified
snapshot GENERIC kernel.

| Actual QEMU/OVMF check | Result |
| --- | --- |
| Secure Boot enabled, enrolled certificate, signed loader and valid manifest | Reached FreeBSD userland and shut down; loader reported `SecureBoot: 1, SetupMode: 0`, and userland independently read the EFI SecureBoot variable as `1` |
| Loader verification of boot contents | Reported the manifest signer, verified the Lua boot scripts and `/boot/kernel/kernel` |
| Same image with unsigned EFI loader | Firmware rejected it with `Access Denied -- rejected probably by Secure Boot`; no FreeBSD loader or userland marker |
| Same image with one kernel byte changed, retaining the original signed manifest | Loader reported the kernel fingerprint mismatch and `panic: cannot continue`; no userland marker |
| Raw binary manifest signature, before correcting its encoding | Loader rejected the manifest and could not open `loader.lua`; no kernel boot |

The passing GPT image's SHA-256 is
`f95a30e7d49284d1a53393b8ec7d59e4862b9bc83aec79eaae37b67ee9351395`.
The signed EFI loader's SHA-256 is
`3041b47fc9aa27ca8834f0175e8269de0ce32aefbd0b680c3dba8e3270206bce`.
Serial logs and the enrolled variable-store listing are retained separately
from the repository. The development private key is excluded from those logs,
the repository and all published images.

## Reproduction details and remaining work

The native stand build used `WITH_BEARSSL=yes WITH_LOADER_VERIEXEC=yes
WITH_LOADER_EFI_SECUREBOOT=yes WITHOUT_LOADER_BIOS=yes`, an isolated object tree
and explicit `TRUST_ANCHORS` / `TA_PEM_LIST` pointing at the public development
certificate. Disabling self-tests required explicit `VE_HASH_KAT_STR_INPUT`
and `VE_HASH_KAT_STR` values because the trust-anchor generation recipe still
uses those variables. This development build does not qualify self-tests.

`uefisign` signed the PE image. The detached manifest signature was generated
with `openssl dgst -sha256 -sign`, then PEM-armored with a `SIGNATURE` label;
the raw binary output alone is not accepted by libsecureboot. The signer
certificate is supplied as `manifest.certs`. Manifest entries are
`relative/path sha256=<hex>`, relative to `/boot`.

OVMF used its Secure Boot code image, SMM, protected pflash and a private copy
of the enrolled variable store for each test. The tests use no network adapter.
Firmware rejection and the guest's EFI variable read are stronger evidence than
`uefisign -V`, which only checks for the presence of a signature.

The prototype is deliberately outside the installer. Production work still
requires a supported key-enrollment and revocation policy, a secure signing
workflow, verification of separately loaded modules, a signed update and recovery
path, and installation/reboot tests on the actual ZFS and encrypted layouts.
In particular, the stock GENERIC kernel does not ship `mac_veriexec.ko`; signing
the EFI loader and checking boot-time files does not enforce integrity of kernel
modules loaded later by userland. Embedding this development trust anchor is
also not a production enrollment policy. Keep the release gate open.
