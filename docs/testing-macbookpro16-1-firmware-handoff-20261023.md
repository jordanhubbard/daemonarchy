# MacBookPro16,1 signed firmware handoff candidate, 2026-10-23

This is build, installer-guard and disposable enforced-boot guest evidence for
an isolated candidate, not physical MacBook Wi-Fi qualification. No Apple
firmware bytes or release signing key are part of the repository or public
image.

## Candidate behavior

The installer offers a verified Apple recovery download or local
`BaseSystem.dmg` import before normal setup. The importer pins the recovery
image and the four BCM4364 B3 board-file hashes. A signed MacBook install
requires a private stage and verifies it against both signed inventories
before disk writes. It copies a fresh private snapshot into the target,
records provenance with root-only permissions, and verifies the installed
files before declaring completion. Other hardware may omit these optional
board files from shared media.

The FreeBSD binary `firmware_get` path uses an ordinary read. The candidate
adds the four firmware hashes to the verified runtime manifest and makes the
policy kernel reject a registered file whose fingerprint mismatches on that
read path. A disposable Secure Boot guest now confirms `EAUTH` for a tampered
registered firmware file. The physical MacBook has not run this probe.

## Native build and local checks

The native FreeBSD 16.0-CURRENT amd64 worker used a fresh worktree at source
revision `bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf`. The modified
`module-policy.patch` has SHA-256
`4c90255d273dcd162067b79eb271c267176cc8f3488e6d93b1f1b2b972384099`.
`secureboot/build.py` has SHA-256
`69e912e8291e4fca86858f2a2884aa3cf7d5f2e4ed44c07835ce5dd3b89eefcc`.
The build used disposable development certificates. Its retained receipt is
`/usr/daemonarchy/firmware-policy-native-build-20261023/build.json`, SHA-256
`03010b1f7f178a5bf919ceae5041443c296c4532fc5e02b216e3e496d4097e78`;
it records `native_boot_qualified: false`.

| Native output | SHA-256 | Result |
| --- | --- | --- |
| Policy kernel | `7c9f21ee680ddb5dcdbc2ddebef47ae830657f1a5b6c416ae55898ecad49010b` | ELF amd64; receipt hash matches |
| Verified EFI loader | `2f6ac1b7f285fd471d88413ad58e1cf838d515c28066a25753b22e377bf90c38` | PE32+ EFI; receipt hash matches |
| Normal EFI loader | `c9b74c66f971128a156cc912a8e97fb7145e52be39865b99b21379534611172f` | PE32+ EFI; receipt hash matches |

`git apply --check` passed on both the pinned source and the separately
retained FreeBSD-current source checkout. The native runtime probe compiled
with `-Wall -Wextra -Werror`. The Secure Boot Python suite passed 26 tests,
including a signed-manifest output check that confirms optional firmware
fingerprints enter both inventories while the image tree contains no firmware;
syntax checks and `git diff --check` passed. A disposable signed bundle built
from test credentials accepted the privately imported Apple files only when
both its boot and runtime manifests contained their exact hashes, and rejected
a signed runtime inventory with the wrong board-file name.

## Disposable enforced-boot guest

The native worker built the same pinned source and policy patch again, using
the public Debian OVMF snakeoil test certificate as its trust anchor. The
retained build receipt is
`/usr/daemonarchy/firmware-policy-snakeoil-build-20261023/build.json`, SHA-256
`037ffd7b85136ab4b54ebf5110bda17d24dd7717851560b06e235fa26db85373`;
its `native_boot_qualified` field remains false because it describes the build
step, before this guest run. The signed EFI loader's SHA-256 is
`83c51b6aabf096d7620b0003464c4a12822d91c678ee4e6edd1f5bc2fd695d1e`.
The signed runtime manifest has SHA-256
`5e29a6d015373cd22eccf23e3c21a138190d0f480838c1d0ea40f4fd4a4e3cfe`
and lists the four exact privately imported BCM4364 B3 hashes. None of those
firmware files or the test key entered the signed boot tree.

The guest used FreeBSD's official 16.0-CURRENT amd64 `base.txz` from
2026-10-19, verified against its adjacent `MANIFEST` at SHA-256
`7bf341029f19f10cff4298e619d261b13fb60c9ad4a1272bda5cb4340be8324b`.
The disk image built on the native worker has SHA-256
`182b82fddc9cebed3f82bebfb80a110939bf87999ef5c48485b976023bd1f899`
before boot. QEMU used OVMF Secure Boot with its pre-enrolled public test key;
the OVMF code image has SHA-256
`1286f2a3217d09b374d05951355d7a561c8bacecd74845c8a1fbb71a48c0de8d`.
The serial log remains outside the repository in the native worker's root-only
`/usr/daemonarchy/firmware-policy-guest-evidence-20261023/serial.log`, SHA-256
`0ac5d1af00d95949c13cc326851d61f151670003e9135e8e56b6ff985f7c7551`.

The serial log records `SecureBoot: 1, SetupMode: 0`, successful loader hash
and certificate self-tests, verified policy kernel and signed runtime manifest,
and `Security policy loaded: MAC/veriexec`. After boot, the native probe opened
a deliberately altered `/boot/firmware/brcmfmac4364b3-pcie.bin` whose SHA-256
was `2bdc9f6debfe561176043d8b1cf17880abb7ca7b2875e95111cef7468e42ebea`,
different from its registered fingerprint. It reported
`PASS registered-firmware-read: errno=80` (`EAUTH`). It also reported the
expected unsigned-module, protected-module-write, kernel-memory-write and
locked-policy-load denials, passed process-environment inspection, returned
zero, and shut down cleanly. The focused log checker passes with:

```
python3 secureboot/tests/check-runtime-log.py firmware-read \
  /path/to/retained/serial.log \
  --kernel-path kernel.secure/kernel
```

This uses a public disposable signing key and an emulated x86 guest. It proves
the patched FreeBSD read policy under enforcement; it does not qualify the
production signing authority, the physical MacBook or the Wi-Fi driver.

## Remaining acceptance

The candidate has not produced a new signed ISO or run the installer on the
MacBook. The BCM4364 driver still needs stable association, DHCP, traffic and
reconnect after reboot. The physical negative test must prove modified
firmware is refused. The final build must use the protected production
authority and refreshed coherent source/package inputs. These checks keep
HW-003, physical Secure Boot and the release ledger open.
