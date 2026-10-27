# Manual Secure Boot certificate enrollment

The current release, [1.3.1](release-1.3.1.md), ships the production
manual-enrollment profile with a new public certificate,
`daemonarchy-1.3.1.der` (and `daemonarchy-1.3.1.pem`), published with the
[GitHub release](https://github.com/jordanhubbard/daemonarchy/releases/tag/daemonarchy-1.3.1).
Use only the production certificate from the matching release; never enroll a
disposable development key. The signed boot bundle and exact ISO were verified,
but firmware enforcement of the published ISO, physical firmware enrollment and
retained-operating-system checks remain unqualified. The
[boot-chain test record](testing-1.1-secureboot.md) holds the earlier development
evidence. Earlier releases: 1.0.1 requires Secure Boot to be disabled; 1.1 and
1.1.1 use the 1.1 certificate described below.

The release provides its public signing certificate in DER form and its
SHA-256 fingerprint with the release. The private key stays on the protected
authoring host and is never part of a package, ISO or installed system.

The certificate belongs in UEFI's authorized signature database, **db**.
Existing platform keys (PK), key-exchange keys (KEK), OEM/Microsoft db entries
and the revocation database (dbx) must be preserved. UEFI authenticates boot
images using these signature databases; adding a Daemonarchy certificate does
not require replacing the platform owner. See the
[UEFI Secure Boot specification](https://uefi.org/specs/UEFI/2.11/32_Secure_Boot_and_Driver_Signing.html).

## 1.3.1 certificate

The 1.1 signing private key has not been found on the release build host, so
1.3.1 introduced a replacement key and public certificate, prepared on the
protected native signer. The private key is not an ISO or repository input. The
published `daemonarchy-1.3.1.der` SHA-256 and X.509 SHA-256 fingerprint are
`ee140e7a68d566d37a96ea49ac68238d2e039c1172eb896ab69bff189d70b733`; the
`daemonarchy-1.3.1.pem` file SHA-256 is
`26009db078d352318c06f1ea5cf7b5650dfd32137518f3a6fecd20802de2fb79`. Enrolling
the 1.1 certificate does not authorize 1.3.1 boot files; enroll this certificate
as well. On firmware with generic UEFI db enrollment, add it
while retaining the 1.1 and platform certificates, then run the physical
enforcement, recovery and negative tests below before claiming that profile.

### Apple T2 MacBook limitation

The generic UEFI db enrollment contract below has **not** been shown to work on
MacBookPro16,1. Apple describes the T2 Mac boot policy as Full Security for
Apple-verified operating systems, Medium Security for Apple- or
Microsoft-signed operating systems, and No Security for other boot images.
Apple's [August 2026 boot-process guide](https://support.apple.com/guide/security/boot-process-sec5d0fab7c6/1/web/1)
lists Microsoft UEFI CA 2023 among certificates used to authenticate Microsoft
bootloaders. That certificate listing does not establish that this MacBook's
firmware accepts a partner-signed shim for FreeBSD under Full or Medium
Security. The [T2 Linux installation guide](https://wiki.t2linux.org/guides/preinstall/)
still reports that even shim-signed GRUB cannot boot a third-party system while
T2 Secure Boot is enabled. The MacBook's actual firmware inventory, boot
policy and enforcement need a physical test; a custom Daemonarchy certificate
has not been enrolled in its firmware. See also [Apple's T2 boot-policy documentation](https://support.apple.com/guide/security/secc7b34e5b5/web).

Until a supported and physically tested T2 trust path exists, a Daemonarchy
signature and signed boot manifest can verify the project's own boot files,
but they do not prove firmware-enforced Secure Boot on this MacBook. Record the
actual T2 policy for each hardware test. Do not claim firmware enforcement from
an OVMF test, a successful signed-bundle check, or a FreeBSD boot under
No Security. The db enrollment contract remains applicable only to firmware
that exposes a compatible enrollment mechanism.

<!-- release-sync: history -->
## Earlier 1.1 certificate

The 1.1.1 refresh retained the 1.1 production signing authority and certificate
filenames; an already trusted matching certificate did not require a new
enrollment for 1.1.1. Its OSVERSION `1600028` boot bundles and drivers matched
their own snapshot. See [the 1.1.1 record](testing-1.1.1.md) and
[the 1.1 image results](testing-1.1-final-image.md).

The production `daemonarchy-1.1.der` SHA-256 is
`111539a7fb7178cea65f3e2fc50ea00839d045324a4272ce190e4733a9c118dd`.
<!-- /release-sync -->

## Enrollment contract

1. Obtain the certificate from the same verified release as the ISO. Compare
   its DER SHA-256 and X.509 fingerprint with the published values. On FreeBSD,
   `sha256 <matching-certificate.der>` and
   `openssl x509 -inform DER -in <matching-certificate.der> -noout -fingerprint -sha256`
   should report the same digest, apart from fingerprint punctuation.
   If firmware selects certificate files from removable storage, copy the DER
   file onto FAT32 media that it can browse. The installer ISO is read-only;
   use separate certificate media rather than reformatting the installer or an
   operating-system disk to add a file.
2. Export or record the existing firmware trust databases using the machine's
   firmware interface. Retain the other operating system's recovery material
   if it uses disk encryption tied to firmware state.
3. In the firmware's certificate-management interface, **add/append** the public
   certificate to db. Menu names vary by manufacturer. An operation that clears
   all keys or replaces PK, KEK or the whole db does not meet this contract.
4. Return to enforced Secure Boot with an existing platform key installed.
   A setup-mode boot is not acceptance evidence. Boot the signed installer,
   install and reboot, then verify the installed enforcement state.
5. Boot each retained operating system too. Compare the retained database
   entries before and after enrollment and record the result in the hardware
   matrix. Enrollment must preserve the existing Windows/OEM trust path.

The installer does not change firmware trust databases automatically. It also
does not enroll a project certificate as PK or KEK. A per-binary hash enrollment
or a shim/MOK workflow is a separate configuration, not the chosen release path.

## Update and recovery contract

Verified boot uses a signed EFI loader, signed boot-file and module manifests,
and a kernel policy that requires the verified manifest handoff before userland.
Local boot configuration may change root-device or GELI settings; it must not
allow an unsigned kernel/module or a fabricated manifest handoff.

Ordinary user programs remain installable from the configured FreeBSD package
repositories. The policy is not a userland executable allowlist. The profile
checks kernel-module admission and specific protected interfaces; it does not
qualify complete host lockdown or every privileged way of modifying a kernel.

An update affecting protected boot files/modules must be prepared in another
ZFS boot environment, validated against its signed manifests, and activated
only after every check succeeds. The running environment and a previously
verified recovery environment must remain bootable. A failed update must leave
the original boot selection usable. The installed `daemonarchy-secureboot` helper supports explicit staging and
activation; [HACKING.md](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md#secure-boot-development) shows the commands.
The [upgrade record](testing-1.1-upgrade.md) distinguishes development and
production-authority tests. These tools cover maintenance of the pinned
snapshot and loader protocol, not a base/ABI migration. In particular, a maintenance bundle, such as one for the OSVERSION `1600029` 1.3.1 snapshot, does not replace an older system's base/kernel or make older driver bytes compatible. The application-feed adoption helper checks actual kernel and userland versions before identity changes; automatic `pkg install -y` alone does not reject newer-OS packages.

Certificate rotation must add the replacement certificate before switching to
artifacts signed with it. Keep the previous certificate until the replacement
boot and recovery paths have been tested. To revoke trust in an old or
compromised Daemonarchy certificate, remove only that db entry, identified by
its published fingerprint, and verify that an artifact signed only by it is
rejected. Preserve OEM/Microsoft entries and dbx. No automatic firmware-key
replacement or revocation is planned for the installer.

Final qualification requires production-certificate enrollment without loss of
existing trust, signed installation/reboot on ZFS and GELI, rejection of an
untrusted boot component, a successful signed update, a failed-update rollback
and recovery media that boot under the retained trust policy.
