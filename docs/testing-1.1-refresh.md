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
build host also needs to satisfy the jail's kernel-version requirement before
final release qualification.
