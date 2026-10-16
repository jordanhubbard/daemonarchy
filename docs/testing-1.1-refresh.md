# 1.1 source and ports refresh preparation

Started 2026-10-15; the preparation checkpoints below are historical. The
preview.13 build and its current qualification status are recorded at the end.

- FreeBSD CURRENT source: `f4fe4c3d17f9bb523981b88a01d7c0f0c0f00c36`.
- Upstream ports: `d886099247746bbd127776f779ffe5ea4d12a4e5`.
- Fork merge: `f20bb73307b4a8c7a285b4f49249469d88817362`, branch
  `daemonarchy-1.1-ports-refresh` in the Daemonarchy ports fork.

The merge preserves Daemonarchy's supporting ports. Two conflicts were resolved:
`sysutils/Makefile` keeps Daemonarchy's lazydocker port entry while accepting
upstream's removal of lava; the Quickshell IPC patch takes upstream's updated
header because its patch body is identical to Daemonarchy's fix. Upstream patch
files retain their original formatting.

The source and refreshed ports use separate clean worktrees. The original source
checkout, including its local untracked build log, and the active package-build
tree were preserved.

At this preparation checkpoint, the development image still used snapshot source
`a52c50b4b7c2652954ef1bd34710a4b1fc8ef391` and its matching jail/modules. The new
revisions are preparation only: selecting/building a new snapshot, matching jail
and kernel modules, testing all changed ports, updating optional checkout payloads,
and repeating installation/hardware qualification remain required. The current
build host is older than that jail; the isolated builder below addresses the
host requirement for subsequent builds.

## Matching snapshot and package baseline

An isolated QEMU/KVM FreeBSD builder now runs the October 12 snapshot kernel
and userspace, with 12 virtual CPUs, 24 GiB RAM, a 200 GiB virtual disk and two
package builders. Its new jail was populated from the same verified base set,
and its kernel and source tree match the selected snapshot:

- Kernel/source: `3ceb5f150bc121f5e6a3e0cc8b289279338405a1`.
- Host and jail `__FreeBSD_version`: `1600027`.
- `base.txz`: `34ffd73346ea96296e8b1a5981ed1dc36861024316f3af6eb69a8691e7e35b16`.
- `kernel.txz`: `d91d2bb49fcb9e4118f0071bfbb3681e227bb4559daa01329d6662de238ad2f9`.

The upstream HEAD refresh is retained at fork checkpoint
`369db19de9d14cd03531c8016aca39eeb9672da3`. It is ahead of the published binary
collection: Python at that HEAD requires 3.12.15, while the collection supplies
3.12.14_1. A preflight queued 938 builds and was stopped before package
publication to reconcile that mismatch.

The collection's Python package records ports revision
`3a3ea9a0eb1ff5e044373aac4a03e137ad4c878d` (October 13). The release changes
were merged onto that upstream baseline as
`a61a07081f074a6fbea1b3f7dc50274626f6a15e`, published on the fork branch
`daemonarchy-1.1-package-baseline`. The same two merge conflicts were resolved
as above, preserving the upstream IPC patch body and excluding removed lava.

The joint build is in progress against this tree. All Daemonarchy roots are
forced to build locally. The 239 copied kernel-module packages were removed
from the isolated cache, and module downloads are blocked so modules rebuild
against the selected snapshot. Downloaded source and ordinary dependency
package caches were reused. Native package QA, new checkout payloads, the
refreshed ISO and its installation/hardware checks remain pending.

## Build compatibility fixes

The first matching-snapshot build exposed two blockers; that run is not green.

- DRM 6.12.110 omitted the generated `opt_linuxkpi.h` and the common kernel
  LinuxKPI configuration include now required by the snapshot's headers. The
  failed `dmabuf` build was reproduced outside poudriere. Adding the generated
  header and configuration include to its module Makefiles passed both that
  component and the complete native DRM build. The port revision is now 4 at
  fork checkpoint `2417b7c55c8ef8d8cae312382babaecfffe272b5`; package QA and the
  dependent NVIDIA DRM build still need a clean retry.
  NVIDIA's DRM companion also omitted this generated header from its feature
  probe prerequisites. Its native build reproduced the missing-header failure
  and then passed with that prerequisite added. Its port revision is now 2 at
  `28d8f145fbec62cb70f3d794975985a26a80484b`, which includes both fixes.
- The base-only jail lacked the optional 32-bit compatibility libraries.
  Installing the published LLVM 19 package failed because it requires
  `libc++.so.1:32`. In a fresh, isolated root populated from the selected base
  set, the real package transaction reproduced this failure and then passed
  after extracting the matching `lib32.txz`. The 32-bit C++ library's dynamic
  dependencies resolved in that root. Its SHA-256 matches the cached snapshot
  manifest: `cd331179a555041a91d3d821fe8afb8c39167d1cbc963227db72e24cbd29dc41`.
  The archive is 64 MiB. The ISO builder and installer now carry/extract this
  set; expanded 32-bit libraries remain excluded from the live root. The next
  image's full size and installation still require validation.

The newly generated source seed packages also passed native `pkg add`, checksum
validation and materialization into a clean, self-contained, one-commit Git
checkout at `3ceb5f150bc121f5e6a3e0cc8b289279338405a1`, with only the public
FreeBSD source remote. The ports seed was regenerated at `28d8f145fbec`, and both trees passed native
materialization checks. The signed three-package repository passed a real
fetch/install transaction; a different valid public key rejected catalogue
queries and installation. `pkg update` alone can exit zero after reporting a
signature failure, so the negative check also verifies queries and installation.
The [published checkout repository](https://github.com/jordanhubbard/daemonarchy/releases/tag/checkouts-16-3ceb5f150bc1-28d8f145fbec-v1)
then passed signature verification and a fresh FreeBSD `pkg` download/install of
all three payloads. All nine GitHub assets match the retained local sizes and
SHA-256 digests. The installer catalogue now selects these pinned checkouts.

The original bulk run was stopped with SIGINT after 267 successful builds;
poudriere retained its uncommitted package repository for reuse. After cleanup,
the isolated ports tree advanced to `28d8f145fbec`, the verified `lib32` set was
extracted into the builder and jail, and native package QA restarted without a
forced rebuild. The now-available 32-bit libraries enable GCC multilib options,
requiring that compiler and its dependents to rebuild. The original bulk
failures remain recorded; the retry must pass before the refreshed image is
qualified.

The GPU selection table was regenerated using DRM `drm_v6.12.110_1` and NVIDIA
595.104.02. The upstream input hashes and all device selections are unchanged
from the earlier table; only its DRM source revision label changed. The image
preflight now requires DRM 6.12.110, and portable GPU selection tests passed.

## Preview.13 build and qualification (2026-10-16)

The final native bulk run completed with eight packages built, 68 fetched, and
no failures or skips, following the successful 43-package hardware retry.
The earlier failed runs above remain part of the record. The matching-module
preflight and public live-image runtime/ELF audit passed.

The image was built from installer commit
`e164e725a62098ac567771a09277d01843f6bd94`, snapshot source `3ceb5f150bc1`,
and ports `28d8f145fbec`:

- Filename: `daemonarchy-1.1.0-preview.13-amd64.iso`.
- Size: 2,054,404,096 bytes, 93,079,552 bytes below the 2 GiB limit.
- SHA-256: `2337893aa30f92dbff41f7d18c2b663713e1ebe3bd64dcf8336cf8a321894c88`.

Plain BIOS and encrypted UEFI QEMU installation/reboot checks passed. Encrypted
BIOS installed and unlocked successfully, but its first installed boot failed
the SDDM-running assertion. A second boot of that retained disk, using a
temporary QEMU snapshot, passed every installed-system assertion without
restarting SDDM manually. The first-boot failure remains unexplained; this is
not an all-green matrix. Plain UEFI with both optional checkouts is still
under validation. These checks do not qualify graphical Hyprland operation.

The published signed checkout repository and all three payload installations
passed native verification. A subsequent authoring-cache build also passed
with the snapshot download server deliberately unreachable, reusing all three
verified release sets; its image audit passed. That separate proof image is
not the public preview.13 artifact.

The physical X570 machine booted preview.13 and exposed its RTX 4090 and AX200
Wi-Fi device. Installed graphics, suspend and Windows preservation remain
unqualified. The bounded DNS-probe fix committed after this build is not in
preview.13. See the [hardware observations](testing-1.1-hardware-observations.md).
