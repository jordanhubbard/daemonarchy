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
The archive must declare its root directory explicitly. The helper applies that
entry's exact owner/group/mode because extraction can retain the staging mode.
The root inode must be owned by root and have mode 0555 or 0755; an omitted
archive root entry must not turn a private staging mode into the live root mode.
It changes the private root's fstab and appends the seed configuration; the
outer loader configuration selects `/dev/md0.uzip`. The original archive is
unchanged. Existing work, images and RAM manifests are refused and preserved.

Native UFS2 construction and read-only fsck precede LZMA UZIP packing. The
existing 4 GiB compressed-bootstrap profile and media size limits remain in
force. The shared ISO helper retains BIOS/EFI optical and USB entries on amd64,
creates a fresh declared boot identity, and appends the standard trace volume.
The `.ram.json` sibling records actual source, root, packed-root and final-image
hashes, root-directory mode/owner/group and explicitly leaves VM/install/desktop/recovery/physical/signing gates false.

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

A later BIOS run exposed a root-inode defect in that retained preparation: ISO
archive extraction omitted the root entry, leaving the private staging mode
0700. The earlier per-entry inventory excluded the root inode. Root-only package
checks passed, but non-root service execution failed. The helper now refuses
that input before filesystem authoring. Independent readback must include the
root inode, and runtime acceptance must execute as a non-root account. Retain
the original failed preparation and obtain replacement metadata from the actual
source filesystem; do not normalize ownership or permissions by assumption.

The [large BIOS handoff control](../verification/bios-large-ram-handoff-20261110.json)
reaches the kernel and native init after replacing the repeated first-GiB
bootstrap mapping with a two-GiB window. Its 269-package inventory, SQLite import
and returned manual trace files pass. The input still has the bad root inode,
and its final shutdown console oracle is missing, so full runtime qualification
remains open. The corrected native loader fits the unchanged 505,000-byte bound;
preload data outside its two-GiB kernel window is refused at handoff.
