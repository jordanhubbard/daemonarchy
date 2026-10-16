# 1.1 source and ports refresh preparation

Prepared 2026-10-15; this is not a refreshed release-candidate build.

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

The current development image still uses snapshot source
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
