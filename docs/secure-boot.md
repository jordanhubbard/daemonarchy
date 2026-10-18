# Manual certificate enrollment for 1.1 and 1.1.1

The 1.1 candidate includes the production manual-enrollment profile. Stable
1.0.1 requires Secure Boot to be disabled. Use only the production certificate
from the matching candidate/release; never enroll a disposable development key.
See [the exact image results](testing-1.1-final-image.md) and
[boot-chain test record](testing-1.1-secureboot.md). Physical firmware enrollment
and retained-operating-system checks remain unqualified.

The release provides its public signing certificate in DER form and its
SHA-256 fingerprint with the release. The private key stays on the protected
authoring host and is never part of a package, ISO or installed system.

The certificate belongs in UEFI's authorized signature database, **db**.
Existing platform keys (PK), key-exchange keys (KEK), OEM/Microsoft db entries
and the revocation database (dbx) must be preserved. UEFI authenticates boot
images using these signature databases; adding a Daemonarchy certificate does
not require replacing the platform owner. See the
[UEFI Secure Boot specification](https://uefi.org/specs/UEFI/2.11/32_Secure_Boot_and_Driver_Signing.html).

The 1.1.1 refresh retains the same production signing authority and certificate filenames; an already trusted matching certificate does not require a new enrollment merely because the release number changes. New OSVERSION `1600028` boot bundles and drivers must still match their own snapshot. See [the 1.1.1 record](testing-1.1.1.md).

The production `daemonarchy-1.1.der` SHA-256 is
`111539a7fb7178cea65f3e2fc50ea00839d045324a4272ce190e4733a9c118dd`.

## Enrollment contract

1. Obtain the certificate from the same verified release as the ISO. Compare
   its DER SHA-256 and X.509 fingerprint with the published values. On FreeBSD,
   `sha256 daemonarchy-1.1.der` and
   `openssl x509 -inform DER -in daemonarchy-1.1.der -noout -fingerprint -sha256`
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
snapshot and loader protocol, not a base/ABI migration. In particular, a 1.1.1 maintenance bundle does not replace an older system's base/kernel or make older driver bytes compatible. The application-feed adoption helper checks actual kernel and userland versions before identity changes; automatic `pkg install -y` alone does not reject newer-OS packages.

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
