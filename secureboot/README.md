# Secure Boot development

This directory contains work toward the 1.1 manual-enrollment boot path. It is
not an installer option yet. No release signing key or firmware-enrollment
operation belongs in this directory. See
[the evidence record](../docs/testing-1.1-secureboot.md) for qualification limits.

`patches/module-policy.patch` applies to FreeBSD source revision
`3ceb5f150bc121f5e6a3e0cc8b289279338405a1`. It adds the opt-in kernel option
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

Production enrollment, signed installation/update transactions, recovery and
ZFS/GELI qualification remain required before exposing this path to users.

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
fails instead of selecting another pool. The existing installer still uses
the snapshot loader; this option must not be emitted until the matching loader
is integrated.

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
from an already signed boot tree. The archive contains only managed boot files;
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

These tools are not installed or exposed to users yet. Native signed update,
injected failure and rollback tests remain required. This format covers
maintenance of the pinned snapshot and loader protocol; a base/ABI transition,
EFI protocol change or certificate rotation requires a separately qualified
migration. Do not replace pkg-owned drivers behind pkg's back to force a match.
