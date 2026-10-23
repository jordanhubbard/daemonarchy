# Secure Boot authoring

This directory implements the 1.1 manual-enrollment boot profile and its
authoring tools. The candidate integrates public signed artifacts into the
installer; private keys and firmware-enrollment operations do not belong in
this directory. See
[the retained 1.1 evidence](../docs/testing-1.1-secureboot.md) and
[current 1.1.1 qualification record](../docs/testing-1.1.1.md) for separate
snapshot results and limits.

`patches/module-policy.patch` applies to FreeBSD source revision
`bdcfeac3e1cb8ce3f05c32d8a7ad3597deb48bdf` for the **1.1.1** refresh
(OSVERSION `1600028`). The existing four Secure Boot patches are retained;
new loader/early-kernel network debugging is deferred to 1.2.
The module-policy patch adds the opt-in kernel option
`DAEMONARCHY_MODULE_POLICY`, used together with `MAC_VERIEXEC`,
`MAC_VERIEXEC_SHA256` and the `mac_veriexec_parser` device in a GENERIC-derived
kernel. Build this from a separate source worktree; do not change the builder's
running kernel or silently replace the selected snapshot sources.

The option permits execution and runtime-linker verification opens of user
programs/libraries absent from the runtime manifest, so normal desktop package
installation remains possible. It does not relax the
independent kernel-module load check or checks on registered files. Enforced,
locked veriexec denies kernel/process-memory write overrides and live policy
control, including for root. Updates must use another boot environment rather
than overriding the running policy.
The kernel also refuses to start userland without a verified manifest handoff.
Without this option, upstream behavior is retained.
Process inspection also retains base FreeBSD permissions: this profile has
kernel/module fingerprints, not user-program TRUSTED/NOTRACE labels. Its
regression probe reads a child process environment, matching the desktop path
that exposed an unlocked-vnode panic in the upstream userland-label hook.

The EFI loader must enable `WITH_LOADER_VERIEXEC_PASS_MANIFEST` and verify a
signed runtime manifest before passing its digest to the kernel. Lua's module
loader puts module flags after the file name, which does not work for the
`pass_manifest` command's options. Use absolute paths in the runtime manifest
and this configuration, with no `runtime_flags`:

```
runtime_load="YES"
runtime_type="pass_manifest"
runtime_name="/boot/runtime.manifest"
```

Do not set `veriexec.manifest_hash` by hand as a replacement for signature
verification. The verified loader's handoff exports the digest it checked.

`tests/runtime-probe.c` checks exact kernel errors in a disposable guest. It
must not run against an operator's installed system: it attempts a module load,
opens a protected file for writing, and probes policy-control permissions.
The caller must first load and unload the trusted original module, then make
an unregistered copy. A duplicate-module error is not verification evidence.
The linker dispatcher returns `ENOEXEC` for the rejected module, so the serial
log must also contain the policy's explicit rejection diagnostic. Run
`python3 secureboot/tests/check-runtime-log.py valid <serial.log>`; its checks
require positive firmware, loader, policy and ordinary-program results, and
reject a panic or failed assertion. `missing-handoff` checks the corresponding
negative boot case and requires the specific kernel panic before userland.

Qualification is specific to the signing authority, image and boot layout.
Development-key results do not substitute for production-certificate checks;
the evidence record distinguishes those tests and physical enrollment limits.

## Kernel and loader build

On the qualified FreeBSD amd64 worker with Python 3.11 or later:

```
sudo python3.12 secureboot/build.py --source /usr/src --out /path/to/fresh-build \
  --certificate /path/to/public-trust-anchor.pem \
  --selftest-certificate /path/to/public-selftest-leaf.pem --jobs 4
```

The recipe requires the pinned source revision, creates a separate Git worktree,
applies the policy and EFI patches and retains build logs. Write access to the
source repository's Git worktree metadata is required (hence `sudo` when
`/usr/src` is root-owned). It does not modify the checked-out `/usr/src` files
or install a running kernel. Its outputs are `kernel`, unsigned
`loader_lua.efi`, a normal `loader_normal.efi`, public certificates and a
`build.json` receipt containing the
input/output hashes, options and build epoch. A fixed `--epoch` can be recorded
for subsequent builds; it must fall within the certificates' validity periods.
The receipt is build evidence, not a native boot qualification.

For a retry, `--prepared-source /path/to/retained/worktree` avoids another
checkout. The recipe compares every tracked source file against a temporary
Git index containing exactly the pinned base plus the current patches, and
rejects untracked files. A fresh output directory and full rebuild are still
required; previous logs and objects remain intact.

The self-test leaf must validate under the public trust anchor. Its private key
must stay protected on the signing host or be destroyed after issuing that
public fixture: it is a signing-capable credential under the same authority.
The build worker needs only its public certificate. Loader verification testing
mode is explicitly disabled, while hash/certificate self-tests and the verified
manifest handoff are enabled.

Both EFI loaders support `daemonarchy_rootpool=<decimal ZFS pool GUID>` in
their firmware load options. They resolve that pool's active boot environment
using the standard ZFS loader path, so `bectl activate` and rollback are not
bypassed by a permanently pinned dataset. A configured but unavailable pool
fails instead of selecting another pool. The installer emits this selector only when its validated signed payload
supplies the matching loaders. Builds without that payload retain the snapshot
loader and its explicit dataset selection.

The verified loader exports `daemonarchy_secureboot` from firmware state.
The signed `boot/local.lua` hook selects `kernel.secure` and its required
manifest when enforcement is enabled. With firmware Secure Boot disabled,
verification is disabled and the stock kernel remains available for ordinary
debugging. An explicit `daemonarchy_verified_profile="YES"` selects the policy
kernel in that mode too, but does not create firmware-rooted trust.

## Boot-tree signing

`sign-boot-tree.py` is an authoring utility, kept off the installer and installed
desktop. On the protected FreeBSD signing host, prepare a separate staging root
with the matching policy kernel and boot modules, then run:

```
python3 sign-boot-tree.py /path/to/staging-root \
  --loader /path/to/verified-loader-build/loader_lua.efi \
  --build-receipt /path/to/verified-loader-build/build.json \
  --kernel-path kernel.secure/kernel \
  --module-inventory /path/to/release-modules.json \
  --certificate /protected/release-public.pem \
  --key /protected/release-private.key
```

For the MacBookPro16,1 BCM4364 B3 profile, first use
`scripts/import-apple-bcm4364-firmware.py` to import the pinned Apple recovery
image into a private directory. Pass that directory with `--firmware-stage`
when signing. The signer verifies its provenance and four file hashes, then
adds their fingerprints to the signed boot manifest. It does not copy Apple
firmware into the public image. The installer needs the same privately acquired
stage, supplied as `DAEMONARCHY_APPLE_FIRMWARE_STAGE`, before any partition
write. It verifies the stage against the signed bundle, copies the four files
to the target, and verifies the installed tree. A signed MacBook image without
that stage refuses installation before changing the disk. Driver attachment,
Wi-Fi traffic and reboot persistence still require physical qualification.

The private key stays outside the image, readable only by its owner. The tool
checks the certificate/key match, signs the PE loader, creates and signs the
module manifest, and then signs the boot manifest that covers it. Each detached
signature is also verified with the exported public key before installation in
the staging tree. Copy the resulting `/boot/loader.efi` to the image's EFI
system partition; firmware verification remains a required native test.

The runtime manifest includes the kernel and `.ko` files, not user packages.
The boot manifest leaves local loader configuration and generated linker hints
mutable. It still requires fingerprints for code, including Lua scripts, kernels
and modules. The policy kernel must require the verified manifest handoff even
when local configuration changes. Another OS's files in `/boot/efi` are excluded.
Verification-control files such as `loader.ve.off` cause signing to fail.

`module-inventory.py` inventories external modules from the native package
repository. It checks package ABI, exact snapshot annotation, ELF module type
and actual module bytes. The signer binds its source revision to the build
receipt. Optional modules absent from an installation are skipped by the
kernel parser; present modules must still match. Symlink aliases are covered
by their canonical inode's runtime fingerprint, because the upstream parser
refuses symlink opens. An alternate stock kernel is deliberately absent from
the verified manifest.

Run `python3 -m unittest discover -s secureboot/tests -p 'test_*.py'` for the
authoring guards. These checks do not qualify firmware boot or the kernel;
the separate native serial-log checks cover those cases.

## Maintenance bundle development

`bundle.py` creates an authoring-side archive and detached RSA/SHA-256 signature
from an already signed boot tree. The archive contains managed boot files and
the authenticated maintenance helper;
the stock kernel and pkg-owned drivers stay in their original payloads.
`prepare-boot-tree.sh SET_CACHE BUILD_DIRECTORY FRESH_STAGING_ROOT` prepares
that tree from MANIFEST-checked release sets, the matching build and the
production boot hook. It includes no disposable-test Lua probes or userland.
Run the boot-tree signer against it before creating the bundle.
`maintenance.py` verifies the archive against an independently supplied trusted
certificate before parsing it, validates its pinned stock kernel and every
present signed boot/module fingerprint, and rejects extra installed modules.

The development commands are `install` for an offline target, `verify`, `stage
--environment NAME` and `activate --environment NAME`. All take a bundle,
`--signature FILE` and `--certificate FILE`. Staging creates a recursive boot
environment, mounts it, installs and validates the files, then unmounts it.
It never changes the active environment. Activation revalidates the mounted
environment and requires the EFI pool selector before calling `bectl activate`.
Neither command reboots. Failed staging retains the candidate for diagnosis
and leaves the original boot selection unchanged.

`daemonarchy-secureboot status` takes no archive arguments. It reads the actual
firmware SecureBoot variable, selected kernel and policy state; enforced
firmware with an incomplete profile is an error. It requires root on FreeBSD.

The installed profile includes the maintenance helper when a validated signed
payload is supplied. Native update, failure and rollback results are recorded
with the exact candidate, rather than inferred from authoring tests. This format covers
maintenance of the pinned snapshot and loader protocol; a base/ABI transition,
EFI protocol change or certificate rotation requires a separately qualified
migration. Do not replace pkg-owned drivers behind pkg's back to force a match.
