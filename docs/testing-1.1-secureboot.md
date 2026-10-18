# Secure Boot development and production evidence

Historical 1.1 development/candidate evidence. Revisions, checksums and results
below apply to the named artifact and date; they do not qualify the new
[1.1.1 source/package set](testing-1.1.1.md). Follow that record for current
preparation and publication status.

The October 16 production-candidate outcomes and exact ISO inputs are summarized in
[the final image record](testing-1.1-final-image.md). The sections below retain
chronological development failures and successes; an older pending-status
statement describes that iteration, not a later candidate.

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

## Runtime verification development checks, 2026-10-16

A GENERIC-derived kernel now includes `MAC_VERIEXEC`, `MAC_VERIEXEC_SHA256`
and the built-in `mac_veriexec_parser` device. A second native loader build
enabled `WITH_LOADER_VERIEXEC_PASS_MANIFEST` and the hash/certificate self-tests.
The certificate self-test uses a separate short-lived leaf signed by the
development CA; its private key stays on the isolated builder too.

The signed boot manifest covers the signed runtime manifest and its public
certificate. `load -t pass_manifest /boot/runtime.manifest` verifies it and
passes its digest to the kernel. Absolute paths in that manifest avoid a Lua
module-loader argument-order problem with the command's `-p` option. Setting
the three handoff environment variables manually is not a replacement: the
verified loader overwrites or clears them immediately before kernel entry.

The upstream policy reached userland with state `loaded active enforce locked`,
loaded the trusted test module, rejected an unregistered copy after unloading
the original, blocked writes to the registered module and rejected an
unregistered executable. That last restriction prevents ordinary desktop
package installation without further policy work.

The development [module policy](https://github.com/jordanhubbard/daemonarchy/blob/main/secureboot/README.md) adds an opt-in kernel
option, leaving upstream defaults unchanged. It allows unregistered user
executables and runtime-linker library opens, retains independent strict module
checks, denies live policy/memory-write overrides, and requires a verified
manifest handoff before userland. Its runtime manifest registers kernel files
only. This is downstream security policy work, not a production support claim.

| Actual isolated QEMU/OVMF check | Result |
| --- | --- |
| Enabled firmware Secure Boot; enabled loader SHA-256, SHA-384 and certificate self-tests | Passed |
| Verified handoff and locked kernel policy | Passed; all four state flags present |
| Trusted `geom_nop.ko` load and unload | Passed |
| Byte-for-byte unregistered copy of that unloaded module | Rejected; explicit policy diagnostic, linker syscall returned `ENOEXEC` |
| Open registered module for writing | Rejected with `EPERM` |
| Root open of `/dev/kmem` for writing | Rejected with `EPERM` |
| Root attempt to add a fingerprint to the locked policy | Rejected with `EPERM` |
| Copied user program absent from the runtime manifest | Executed successfully, including its normal dynamic linker/library path |
| Signed boot configuration omits the handoff but supplies plausible manifest path/hash variables | Specific `verified manifest handoff is required` kernel panic; no userland marker |

The passing runtime image SHA-256 is
`864097ad7c109d8a9cae87a65742ad55f9f52da90e80b1a8262c52f0cf44a832`.
The missing-handoff image SHA-256 is
`a7bcf92f3c719f967cb14ae7a7cf42d64a5182009085079f68aaf0b0d43db819`.
The retained serial logs pass `secureboot/tests/check-runtime-log.py` in their
respective modes. The checker also rejects the retained failed run.

Earlier iterations are retained as failures: a missing handoff left the first
upstream policy inactive; the initial copied-module test only hit a duplicate
module error; the first module-only policy blocked runtime-linker opens; and
the memory-write probe exposed an unlocked-vnode assertion in upstream trusted
process lookup. The final module-only profile denies those privilege overrides
directly rather than invoking that lookup. None of those failed iterations
qualifies the boot chain.

These checks used a development certificate and UFS test root, not the
installer, production certificate enrollment, ZFS/GELI, a signed package
update, or recovery. No production signing key has been created, no physical
firmware variables changed, and no private key is in any image. Those release
requirements remain open.

The reusable `secureboot/sign-boot-tree.py` authoring utility was subsequently
run against the disposable UFS tree. Its signed PE loader and boot/module
manifests booted with enabled firmware Secure Boot and passed every `valid`
serial-log check, including normal dynamic execution and all module/policy
probes. That image SHA-256 is
`154066e95089296d7f1799d2b96a0dc271c099d653788a9c1e02107e14f28c42`.
Ten authoring guard tests also passed on macOS and native FreeBSD: running-root
and symlink-root refusal, key location/permissions, private material in a
certificate input, key/certificate mismatch, file/directory symlink escapes,
verification-control files and exclusion of another OS's ESP contents. These
are authoring and development-image checks; the production release gates above
remain open.

## Reusable build, mode selection and enrollment checks

Further native checks on 2026-10-16 used `secureboot/build.py` against the same
pinned source and the current three downstream patches. The recipe built the
policy kernel and verified/normal EFI loaders, retaining build receipts and
logs. Verification testing mode was disabled; SHA-256, SHA-384 and certificate
self-tests and the verified manifest handoff were enabled. Vector-context
verification was disabled so raw boot-file loads use the strict verification
path too. A prepared source retry was checked against exactly the pinned base
plus all patches using a separate Git index before compiling.

The external module inventory hashed 997 native relocatable modules from 186
packages in the validated candidate repository. Optional absent modules are
skipped at manifest registration; present files remain subject to their signed
fingerprints. Symlink aliases use their canonical inode's runtime entry.

For enrollment, a disposable OVMF store first contained existing PK, KEK, db,
dbx and Microsoft trust entries. The development Daemonarchy certificate was
then appended only to db. JSON exports proved every other variable unchanged
and all prior db bytes retained, with the expected DER certificate appended.
`tests/check-enrollment.py` passed that evidence and rejected a deliberately
changed PK variable. This is an isolated firmware-store test, not physical
firmware enrollment or a Windows boot test. No private key was transferred.

The same signed image passed three actual boots:

| Firmware mode | Result |
| --- | --- |
| Enforced UEFI using the appended certificate and preserved trust store | `SecureBoot: 1, SetupMode: 0`; untrusted stock kernel and raw module rejected; trusted policy kernel automatically selected; all handoff, module-admission, protected-interface and ordinary-user-program probes passed |
| UEFI with Secure Boot disabled | Stock kernel booted; module policy absent |
| Legacy BIOS | Stock kernel booted; module policy absent |

The GPT image SHA-256 was
`a93570ee69bfd6b2b8969e75e6d1331f1d4e5ce8688d89720aea5173a84bbab7`;
its gzip SHA-256 was
`fda69c30abec2aa5731b4682306326f28f0b0cf718e0f3a32a0df308c791cc19`.
The policy kernel SHA-256 was
`c9cb347915c7797b35c427937da7e95280826d2c981f3350f038897d3fe742e7`.
Retained serial logs passed the `preload-rejection`, `uefi-off` and
`bios-normal` checks. An earlier mode-selection build is retained as a failure:
enforcement correctly rejected the untrusted stock kernel, but the EFI state
hook had been compiled out. The corrected state hook lives in the EFI
initializer and does not introduce EFI references into the other loaders.

Separately, `prepare-boot-tree.sh` prepared a clean boot-only tree from verified
cached sets, with no disposable test probes. Its signed maintenance bundle was
approximately 10 MiB and passed the native bundle/tree validator. Twenty-three
authoring/archive/offline-tree tests passed on both macOS and native FreeBSD.
The [upgrade record](testing-1.1-upgrade.md) describes the native rejected-stage
check against a mismatched older snapshot.

These are still development-key and disposable UFS/VM checks. Production
signing, installer integration, enforced ZFS/GELI installation and signed
update/recovery qualification remain open.

## Installed ZFS profile and desktop regression, 2026-10-16

A private development-key integration ISO reached installed ZFS roots with
enforcement enabled, both unencrypted and GELI-encrypted. The latter required
the real unlock prompt. These first runs failed the desktop check: ordered
graphics startup omitted VirtIO from its allowlist. After correcting that
service in a disposable copy, SDDM exposed a kernel panic in the upstream
userland-label process-debug hook when a desktop helper read another process
environment. These failures are retained; neither installation run is a fully
passing final-image test.

The module-only profile now leaves ordinary process inspection to FreeBSD's
base permissions instead of invoking that unrelated userland-label hook.
Kernel/module verification and the explicit protected-memory/policy-control
checks remain enforced. The full upstream policy is unchanged. A native
child-process environment-read regression was added to `runtime-probe.c`.

The v8 policy kernel SHA-256 is
`2c8af43f2663e4e434e4eae605002868e1c8cc24a60dd0f21c79e98a283f21cb`.
Its signed UFS test image SHA-256 is
`a21bd14bd4d366fbec2345041bec401488679629082fb0d685033a0c36402cdc`.
Actual enforced UEFI, disabled UEFI and BIOS boots passed again, including
the process-environment regression and all earlier enforcement probes.

The signed v8 maintenance bundle was staged, validated and activated in the
disposable installed plain-ZFS guest. Reboot selected the new environment and
kernel with firmware enforcement and `loaded active enforce locked` policy.
Trusted module load/unload and all five runtime probes passed there too.
With the service correction retained in that candidate, a subsequent reboot
automatically started SDDM. QEMU keyboard input authenticated the tester user;
the callback verified Hyprland's 1280x800 monitor, no nonempty configuration
errors, desktop panel, a terminal opened by keyboard, absolute pointer input,
Chromium rendering the requested data page, and the OctoPkg graphical UI.
Screenshots were captured inside the actual Wayland compositor because QMP
has no CPU screenshot surface for this EGL/GL scanout.

The signed-CD path also needed a loader filesystem fix: ISO dot records without
Rock Ridge alternate names must resolve `.` and `..`, and stat fields must be
initialized. Otherwise verified Lua cannot locate the adjacent manifest. A
private diagnostic ISO with the corrected EFI loader booted the installations
above. Its untrusted-loader and altered-kernel negative tests both rejected
the affected component before userland. This diagnostic ISO mixed test builds;
a coherent fresh integration image remains required.

The update, injected-driver-failure and rollback observations are recorded in
[the upgrade record](testing-1.1-upgrade.md). Production-authority signing,
fresh complete image tests and physical enrollment remain separate gates.

## Production authority: isolated firmware/runtime checks

The production authority was created on the protected signing host. Its
owner-readable private key never went to the authoring worker; only the public
certificate, public self-test fixture and signed artifacts were exported.
The self-test fixture's temporary private key was removed after issuance.
Public material and the DER fingerprint are in
[`secureboot/certificates`](https://github.com/jordanhubbard/daemonarchy/blob/main/secureboot/certificates/README.md).

Appending this certificate only to db in the isolated OVMF store preserved all
previous entries and every other firmware variable. The authenticated db
timestamp advanced, which is permitted; identity and attributes stayed intact.
The checker also rejected a backwards timestamp, extra db entry and changed PK.

The pinned source and same four patches were rebuilt against that public
authority. The policy kernel SHA-256 is
`a2e3a6e1e73b09b22da646febb9949390d9ff9da56cf8c6980e462c67308a220`.
Signing occurred on the protected host. The returned bundle passed independent
native signature, stock-kernel and boot-tree validation on the authoring worker.

| Actual production-certificate UFS test | Result |
| --- | --- |
| Enrolled OVMF, SecureBoot 1 / SetupMode 0 | Verified loader/kernel/manifest, all four policy states, trusted module load/unload and all five runtime probes passed |
| Same image, firmware enforcement disabled | Stock kernel booted, module policy absent |
| Original OEM/Microsoft store without the project certificate | Firmware rejected the signed loader with Access Denied before FreeBSD started |
| One kernel byte changed, original signed manifest retained | Verified loader reported unequal SHA-256 digests and refused the kernel before userland |

The valid test image SHA-256 is
`140a48782ef0d8ec97ec5440e21b31473aa376706472cd009c0b6eadf41b25c5`;
the deliberately altered image SHA-256 is
`d57f41f1f2ea512ef6cb0f48943f9b97bd1491363c85e3ea8ade3446d43f1b61`.
These actual firmware/runtime checks do not substitute for production-certificate
installer, installed ZFS/GELI, desktop, update and recovery qualification or
physical firmware/retained-OS checks. Those release gates remain open.
