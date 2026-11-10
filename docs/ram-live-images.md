# RAM-root installer image authoring

The shared `scripts/make-ram-iso.sh` helper authors a complete, already-admitted
Poudriere live-root archive as a compressed UFS2 memory disk. It supports ARM64
EFI and amd64 BIOS/EFI media through the existing shared ISO/trace assembler.
Run it as root on an allocated FreeBSD worker so archive ownership, modes and
hardlinks survive extraction and filesystem creation. Authoring uses native
filesystem utilities and does not execute target binaries; the authoring host
and target architecture must be recorded separately.

Prepare and qualify the selected full world, kernel/modules, installer sets,
package inventory and offline repository first. This helper preserves that
input; file-presence/ELF checks are not package-closure, signature or lifecycle
admission. Record the input archive hash and retain the original bytes.

Use fresh output and work paths:

```sh
sh scripts/make-ram-iso.sh /build/live/amd64.txz DAEMAMD64 \
    /build/output/amd64.iso /build/work/amd64-ram BOOTX64.EFI bios
sh scripts/make-ram-iso.sh /build/live/arm64.txz DAEMARM64 \
    /build/output/arm64.iso /build/work/arm64-ram BOOTAA64.EFI
```

The helper requires the declared FreeBSD ABI to match the EFI selection, checks
actual kernel, shell and UZIP-module ELF machines, requires the owned brand and
profile Lua hooks, retains the complete live
root, and seeds its packaged `/var` before rc.d/var mounts writable memory.
It changes the private root's fstab and appends the seed configuration; the
outer loader configuration selects `/dev/md0.uzip`. The original archive is
unchanged. Existing work, images and RAM manifests are refused and preserved.

Native UFS2 construction and read-only fsck precede LZMA UZIP packing. The
existing 4 GiB compressed-bootstrap profile and media size limits remain in
force. The shared ISO helper retains BIOS/EFI optical and USB entries on amd64,
creates a fresh declared boot identity, and appends the standard trace volume.
The `.ram.json` sibling records actual source, root, packed-root and final-image
hashes and explicitly leaves VM/install/desktop/recovery/physical/signing gates false.

Retain failed work and logs. Independently inspect the actual ISO's nested
packed filesystem, compare the complete payload and metadata, and boot the exact
result. Verify its live package inventory after the `/var` mount, read back any
same-medium diagnostic write after shutdown, and run the unchanged raw and
compressed size checks. Earlier fixtures and source images cannot qualify a
new final artifact. TCG, native hardware, manual writes and automatic diagnostic
capture retain separate evidence scopes.

The default live-root archive producer and ARM-specific kernel/package refresh
helper retain their existing roles. Final default media selection and complete
CURRENT installer qualification remain tracked in the
[1.6 release plan](roadmap/release-1.6.0.md) and
[normal tracing plan](roadmap/default-install-tracing.md).

The [retained amd64 full-root control](../verification/full-ram-live-control-20261110.json)
passes native assembly and complete nested-filesystem readback, EFI USB boot,
269 live-package identities, SQLite import and same-medium trace writes. Both
owned Lua hooks survive unchanged. Linux and FreeBSD FAT checks pass after
shutdown; the raw image and compressed round trip pass the existing budgets.
This uses retained 1.5.1 world/kernel inputs with the new EFI, not final CURRENT
media. BIOS, ARM use of this shared helper, installation, desktop, signing and
physical qualification remain open. Failed incomplete inputs and host emulator
aborts remain recorded.
