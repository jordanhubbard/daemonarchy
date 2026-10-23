# MacBookPro16,1 signed firmware handoff candidate, 2026-10-23

This is build and installer-guard evidence for an isolated candidate, not a
physical Wi-Fi or enforced-boot qualification. No Apple firmware bytes or
release signing key are part of the repository or public image.

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
read path. An optional disposable-guest probe expects `EAUTH` for a tampered
registered firmware file. This negative probe has **not** run in an enforced
guest or on the MacBook.

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

## Remaining acceptance

The candidate has not produced a new signed ISO or run the installer on the
MacBook. The BCM4364 driver still needs stable association, DHCP, traffic and
reconnect after reboot. Enforced-boot guest and physical negative tests must
prove modified firmware is refused. The final build must use the protected
production authority and refreshed coherent source/package inputs. These
checks keep HW-003, physical Secure Boot and the release ledger open.
