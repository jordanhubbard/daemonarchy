# Package repository key rotation for 1.3.1

The private key for the existing package feed is not present on the current
native build host. The MacBook's installed `/usr/local/etc/pkg/keys/daemonarchy.pub`
matches the public key shipped in the 1.1.1 installer. Preserve the existing
`packages-16-amd64` feed and its public key for systems that still trust it.
Do not replace that feed's catalogues with signatures from the new key.

On 2026-10-24, a separate 4096-bit RSA key was generated on `daemon.local` at
`/usr/local/etc/daemonarchy/pkg-repo-next.key` with root-only read permission.
Its public half is [pkg-repo-1.3.1.pub](../keys/pkg-repo-1.3.1.pub).
An OpenSSL sign/verify challenge passed on the native host. SHA-256 of the
public keys in DER form:

| Trust anchor | SHA-256 |
| --- | --- |
| Existing 1.1.1 key | `2e0e0cab66c8f60579d992359d93e66a0ad5cb49996279fae68ffde3988df38a` |
| New 1.3.1 candidate key | `67986b400f28a49e99df0f1f3368f60aca8064d5dc00094700ba1a17d8474ef7` |

An encrypted recovery copy is now held separately from its decryption key on
another machine. A streamed restore on 2026-10-24 reproduced the new public
key's DER SHA-256 above without saving a plaintext signing-key copy outside
the native signer. Backup coordinates and ciphertext digest are retained in
private custody records, outside this repository. This closes the package-key
backup requirement; feed signing, installation and upgrade acceptance remain
open.

An isolated native preflight on 2026-10-24 signed a one-package test catalogue
with the new key. `pkg` authenticated it with only the matching public key and
queried the package. With an unrelated public key, it reported an invalid
signature and left no queryable catalogue, although `pkg update -f` returned
success. The worker still runs OSVERSION `1600028` while the test package was
built for `1600029`, so this signature-only preflight used
`IGNORE_OSVERSION=yes`. It does not qualify the candidate feed or a package
installation. The final feed must be checked on a matching native system with
no OSVERSION override; `pkg update` exit status alone is insufficient.

## Candidate publication

1. Complete the exact FreeBSD source and ports bulk, including kernel modules,
   and retain its successful package list and build receipts.
2. Build a new signed application feed under a **versioned** tag such as
   `packages-16-amd64-1.3.1-r1`. Pass
   `KEY=/usr/local/etc/daemonarchy/pkg-repo-next.key` to `pkg-repo.sh build`.
   Sign the separate checkout repository with the same key. Check both
   catalogues and every package payload with the
   [signed snapshot checker](signed-package-snapshot.md) using only the new
   public key on a matching OSVERSION before publishing. Confirm the authenticated
   catalogue can be queried; upload payloads before catalogues.
3. Build the 1.3.1 ISO with that exact `PACKAGE_REPOSITORY_TAG`, its matching
   `CHECKOUT_CATALOG`, and
   `PACKAGE_REPOSITORY_PUBLIC_KEY=keys/pkg-repo-1.3.1.pub`. The build script
   stages this public key as the installer's `daemonarchy.pub`; the installed
   package and checkout repository configurations then point to the new key.
   The unversioned stable tag rejects an alternate public key.
4. Boot and install from that exact ISO on the MacBook, verify both signed
   repository refreshes and a package upgrade, then retain the image digest and
   physical receipt. Publish the release only after its other hardware and
   attestation gates pass.

## Existing installations

An installation holding only the old public key cannot authenticate the new
feed. The old private key is unavailable, so a signed old-key update cannot
deliver the new trust anchor. Existing installations need an explicit manual
enrollment: obtain the new public key through a trusted release channel, verify
its DER SHA-256 above, install it alongside the old key, and add a separate
versioned repository configuration pointing at the new tag and new key. Refresh
that repository and verify its signature before preferring it for upgrades.
Retain the old configuration until this succeeds, including the ISO fallback.
Document the exact published tag and commands in the release instructions once
the candidate feed exists. Do not silently replace an installed public key.

Key enrollment does not upgrade the FreeBSD base. The tested 1.1.1 native
installation reports `kern.osreldate=1600028`; the 1.3.1 package build and
installer jail select `1600029`. Check the target with
`sysctl -n kern.osreldate` before enabling the new feed or installing its
packages. An existing installation on the older base needs the qualified
1.3.1 ISO or a separately tested base, kernel and module upgrade first. Do not
use `IGNORE_OSVERSION` to force the new packages onto the older system. Retain
the old feed and key until the updated base boots and its new repository
signature, package dependencies and rollback path have been checked.

This key signs `pkg` repositories. It does not replace the separate Secure Boot
and hardware-attestation signing certificate; production boot attestation still
needs its own qualification and release signer.
