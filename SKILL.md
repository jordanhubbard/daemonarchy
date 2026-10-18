---
name: literate-ai
description: Maintain Daemonarchy product contracts and evidence while retaining its original FreeBSD implementation and release workflow.
metadata:
  author: "Daemonarchy maintainers <jordanhubbard@users.noreply.github.com>"
---
# Working on Daemonarchy

Start with [the documentation index](docs/README.md).
Read `PROJECT.md`, [the active queue](docs/roadmap/active-work.md),
[the architecture and acceptance map](docs/architecture/design-traceability.md),
and the selected Component contract before changing product behavior.
`HACKING.md` owns native build/test procedures;
`ROADMAP.md` summarizes feature direction.

Specifications record intended behavior. Existing source remains implementation
and release authority during this adoption. A discrepancy is work to reconcile,
not permission to delete or regenerate implementation. No conversion-stage or
native execution qualification is implied by the project manifest.

Use `litai project tracker inspect` and `litai project guidance --operation develop`
for the forge/policy, `litai work record` for new stable work IDs, and
`litai project validate` for authority validation. Run `litai verify` and report
all missing lifecycle, lock, receipt or documentation gates honestly. Native
FreeBSD/VM/hardware results must come from their actual workers and exact
artifacts; a macOS metadata check cannot replace them.

Preserve published tags and artifact bytes. Keep signing keys, credentials,
private worker addresses and raw debugging evidence out of committed authority.
Do not add source indexing unless the operator explicitly chooses it.
Document remaining lifecycle integration in the queue; never synthesize a passing
receipt or conversion status from historical logs.
