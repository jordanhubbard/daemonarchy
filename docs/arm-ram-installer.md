# ARM installer RAM root

`scripts/make-arm-ram-installer.sh` builds an experimental full installer whose
root is read through EFI before kernel device takeover. This allows native
kernel bring-up while USB or storage drivers are still incomplete. It does
not qualify installation, the native storage path or an Apple board.

Use the allocated FreeBSD worker and pinned inputs: a complete Poudriere live
installer archive, a complete native AArch64 `kernel.txz` set, and an Omarchy package for
`FreeBSD:16:aarch64`, plus a pinned complete package-closure manifest. The
builder resolves immutable input paths, checks their
SHA-256 digests and rejects existing output/work paths. It runs as root for
private archive ownership, chrooted package installation, mounts and filesystem
assembly. It never writes a physical device, provisions Apple storage or signs
outputs.

```sh
sudo sh scripts/make-arm-ram-installer.sh \
  /inputs/world.txz "$WORLD_SHA256" \
  /inputs/kernel.txz "$KERNEL_SET_SHA256" \
  /inputs/All/omarchy.pkg "$OMARCHY_SHA256" \
  /outputs/arm-ram-installer.iso /outputs/new-ram-work \
  /inputs/package-closure.json "$CLOSURE_SHA256"
```

The manifest uses `daemonarchy/arm-package-closure@1`, with `root: "omarchy"`
and a `packages` list. Each package records `name`, `version`, `abi`, absolute
regular-file `path`, `bytes`, `sha256` and its list of dependency names in
`dependencies`. Include every transitive dependency and no unrelated packages;
each name has one selected version. Native `pkg query -F` must agree with every
archive's declared identity and dependency edges. AArch64 and architecture-neutral
`FreeBSD:16:*` dependencies are admitted; Omarchy itself requires the AArch64 ABI.
Pin the manifest's own SHA-256 separately from the root package's digest.

The builder copies the verified closure into a fresh private directory, checks
the copied bytes, installs all selected archives in dependency order through
one native pkg writer,
and verifies every installed version/ABI and native dependency check. Its local
ISO repository receives the same closure, removing older versions of those
names. The image contains a path-free `ram-package-closure.json` inventory; its
manifest binds both that inventory and the original input manifest. Mutable
adjacent cache contents cannot silently become image inputs.

Installation uses `pkg -c` with a read-only package mount and an empty repository
directory inside the private root. `pkg -r` alone does not confine arbitrary
package scripts. Preserve the native `pkg-install.log` even on timeout, and
reject reported pre/post-install script failures even if pkg returns zero.

This is a development archive-identity contract, not signed-repository
authentication or Component lifecycle admission. Those release gates remain
separate, as do the native solver, full installer and rendered desktop checks.

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
`md_image`; the default codec is LZMA with 256 KiB clusters and two compression
workers. The manifest records actual codec, geometry and cluster-rounding
padding. `geom_uzip.ko` exposes `/dev/md0.uzip`. Existing in-memory `/var` and
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

The outer EFI builder also appends initialized 256 MiB DATRACE storage by
default, using native `makefs`, `mkimg` and Python 3. Keep its co-located
`scripts/make-install-trace.py` and `tools/boottrace/stick.py` with the builder.
This prepares storage; automatic early-boot and installer capture remains
[TRACE-001 work](roadmap/default-install-tracing.md). The normal ISO-root USB
control cannot mount its sibling trace partition for writing while using the
raw disk as its live root. The RAM-root controls below demonstrate same-medium writes after an orderly VM
shutdown; automatic capture and physical reset/power-loss acceptance remain open.

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

The inputs JSON has `world`, `kernel_set`, `package` and `closure` objects, each with
absolute `path` and `sha256` fields matching the build command's inputs. The
suite preserves refusal logs and verifies that existing output/work sentinels
survive. Its seven cases passed on a disposable native FreeBSD ARM64 VM using
retained inputs before the closure-input extension
([checkpoint](../verification/arm-kernel-set-20261109.json)). Those historical
inputs include Omarchy 4.0.4_28, so the result covers that preflight refusal;
final current-Omarchy distribution qualification remains open. The later
development RAM control below supplies assembly and VM evidence for its exact
retained-world inputs.

Run `python3 tests/arm-package-closure.py -v` for checksum, metadata, ABI,
missing/extra/duplicate/cyclic dependency and source-change-during-copy refusal controls.
The portable suite substitutes metadata fixtures; actual native package archive
inspection and installation require the allocated FreeBSD worker.

A fresh native GENERIC build of source candidate `0e1ddb782d1e` produced a
complete kernel set accepted by the checker, with all 114,908 original source
members preserved after the build ([native checkpoint](../verification/arm-native-kernel-20261109.json)).
The sealed set remains a development input. Its inclusion in the RAM control
below now has native build and VM evidence; physical target behavior remains
unqualified.

The subsequent [normal-ISO control](../verification/arm-kernel-vm-control-20261109.json)
boots that complete set through EFI/KVM, reports all four VM CPUs active, and
passes one serial plus eight concurrent local HTTP transfers with exact payload
checksums. It retains the old live root and does not qualify the complete RAM
preload, current Omarchy image, installation or physical boards. The earlier
retained-image installer timed out during package fetching; these controls do
not establish its cause or a repair.

## Current-Omarchy RAM and trace-volume control

The [native RAM checkpoint](../verification/arm-ram-native-20261109.json) builds
Omarchy **4.5.0_4** with its [316 pinned runtime archives](../verification/arm-ram-runtime-closure-20261109.json),
then boots the exact image from writable USB through EFI/KVM with eight CPUs
and 16 GiB RAM. The mounted root is `/dev/md0.uzip`; its complete 378-package
inventory and kernel/closure hashes match the build records after `/var`
initialization. Hyprland's version command runs and native dependency checks pass.
The retained installer's welcome screen renders; this is not a rendered desktop
or an installed-system result.

The manual control mounts the same USB disk's DATRACE partition with synchronous
writes, saves kernel diagnostics and package/CPU/kernel identities, unmounts it
and powers off. Controller readback recovers those files, verifies the package
inventory hash and all 201 raw-map entries, and passes a read-only FAT check.
Unlike the normal raw-ISO root control, this RAM-root arrangement permits the
same-medium writes without changing GEOM protections. Automatic capture and
reset/cold-power survival remain separate requirements.

Earlier attempts remain recorded: alphabetical package installation failed on
FFmpeg's old `libplacebo`; `pkg -r` did not confine arbitrary package scripts;
and a test initially queried the wrong kldstat module name. The successful build
uses frozen final tools, dependency ordering, `pkg -c` and explicit script-failure
checks. The worker's ConsoleKit history remains absent while the private root's
history exists.

The initial zlib/16 KiB control produced a 4,369,433,088-byte ISO, exceeding the
existing 3,758,096,384-byte raw release budget. The subsequent
[packed-root handoff and compression checkpoint](../verification/arm-ram-handoff-20261109.json)
recompresses the exact same UFS filesystem with LZMA/256 KiB clusters. Every
original filesystem byte is preserved; only 196,608 zero bytes are added to
complete the final logical cluster. The resulting 3,731,898,880-byte image
passes the unchanged raw limit with 26,197,504 bytes to spare. No desktop
packages, installer payloads or hardware discovery scope were removed.

That exact image boots through EFI/USB with eight VM CPUs, preserves package
identities and repeats the manual trace-write/shutdown/controller-readback
control. The platform assembler now independently checks its actual packed
root and stages both RTX Spark and M2 Pro candidates. These results use a
repack of the previously assembled filesystem; they do not qualify a fresh
full build with the updated default compression recipe. The earlier oversized
image and failed inspection of a valid short final cluster remain recorded.

This remains a development control. Its world/installer uses retained 1.5.0
inputs; the full 1.6 overlay and current upstream synchronization are pending.
The standard `xz -T0 -9` publication control produces 3,144,154,384 bytes,
exceeding the unchanged 2,147,483,648-byte asset limit. XZ integrity and full
source-image roundtrip checks pass; the release size check correctly fails.
Raw-media fit alone therefore does not resolve release packaging. An 8 GiB
USB control also boots and persists traces: FreeBSD reports the backup GPT is
not at the device's final LBA, but returned inventory/map/FAT checks pass.
Default automatic tracing, final-image installation, rendered desktop, physical
Apple and release qualification remain open.
