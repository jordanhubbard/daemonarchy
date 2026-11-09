# ARM installer RAM root

`scripts/make-arm-ram-installer.sh` builds an experimental full installer whose
root is read through EFI before kernel device takeover. This allows native
kernel bring-up while USB or storage drivers are still incomplete. It does
not qualify installation, the native storage path or an Apple board.

Use the allocated FreeBSD worker and pinned inputs: a complete Poudriere live
installer archive, a complete native AArch64 `kernel.txz` set, and an Omarchy package for
`FreeBSD:16:aarch64`. The package's adjacent native dependency archive closure
must be present. The builder resolves immutable input paths, checks their
SHA-256 digests and rejects existing output/work paths. It runs as root only
for private archive ownership, devfs and filesystem assembly. No device writer,
partitioner, Apple provisioning or signing operation is invoked.

```sh
sudo sh scripts/make-arm-ram-installer.sh \
  /inputs/world.txz "$WORLD_SHA256" \
  /inputs/kernel.txz "$KERNEL_SET_SHA256" \
  /inputs/All/omarchy.pkg "$OMARCHY_SHA256" \
  /outputs/arm-ram-installer.iso /outputs/new-ram-work
```

The complete live kernel/module, DTB and matching kernel debug trees are replaced
by the selected kernel set. The installation archive receives the exact same set;
its MANIFEST digest is updated. A bare replacement kernel cannot carry the old
installer's modules into the new image. The set checker rejects missing UZIP,
foreign kernel/module architectures, duplicate members, unsafe links and members
outside those trees. FreeBSD's same-directory module aliases are checked against
their actual ELF targets. The selected set still needs native producer/source/toolchain and
runtime qualification; archive consistency does not establish those results.
Omarchy and its cached native dependencies
are installed only into the private root, with remote repositories disabled.
The local ISO package catalogue is refreshed, preserving configured signed
public dependency feeds. The package inventory is retained with the medium.

All installer files, release archives and the package repository remain in a
UFS2 filesystem. The builder requires the full filesystem check to complete
and rejects integrity diagnostics even if `fsck_ffs` returns zero. UFS1's
legacy cylinder-group inode-count field is too small for this desktop root.
GEOM UZIP compresses it into a read-only disk image loaded as
`md_image`; `geom_uzip.ko` exposes `/dev/md0.uzip`. Existing in-memory `/var` and
`/tmp` handling remains in use. The writable `/var` is seeded from the packaged
tree using `mdmfs -k`, preserving the installed package database after startup.
Unlike whole-filesystem gzip, UZIP supports an
expanded root larger than 4 GiB and reads compressed blocks on demand. The
compressed bootstrap input is bounded below 4 GiB. No CPU or RAM discovery
limit is added.

The outer UEFI hybrid ISO contains the matching loader, boot files and compressed
root. Its manifest records input/output digests, kernel-set identity, package
version/inventory and expanded/compressed root sizes. Assembly does not set
VM boot, physical boot, installation, desktop or recovery status true.

Before requesting a physical test, boot the exact image through its EFI loader
in a disposable ARM VM, verify the mounted RAM root, kernel/package identities
and full installer payload, and exercise the intended user interface. A VM
boot still does not prove Apple AIC, CPU startup, power, DMA, USB, storage or
framebuffer behavior. M2 Pro Mac mini tests also require an enrolled OS stub,
its correct OS-owned ESP and preserved macOS/Recovery ownership.

Run `python3 tests/arm-kernel-set.py -v` for portable archive refusal controls.
The native preflight suite runs as root on an allocated FreeBSD ARM64 worker:

```sh
sudo python3.12 tests/arm-ram-installer.py \
  --builder "$PWD/scripts/make-arm-ram-installer.sh" \
  --inputs /inputs/pinned-inputs.json --work /outputs/new-refusal-run
```

The inputs JSON has `world`, `kernel_set` and `package` objects, each with
absolute `path` and `sha256` fields matching the build command's inputs. The
suite preserves refusal logs and verifies that existing output/work sentinels
survive. Its seven cases passed on a disposable native FreeBSD ARM64 VM using
retained inputs ([checkpoint](../verification/arm-kernel-set-20261109.json)).
Those inputs include Omarchy 4.0.4_28, so the result covers preflight refusal;
current-Omarchy image assembly and runtime qualification remain open.
