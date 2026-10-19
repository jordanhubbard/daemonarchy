# Release assembly and qualification public boundary

Capability: `daemonarchy.release`, contract version 1.0.0.

This is a behavioral integration boundary over the retained implementation, not
a newly implemented RPC or JSON API. Consumers must preserve the requirements
in [the Component](../component.md) and use the existing commands/files described
in [HACKING.md](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md).

Dependencies: `daemonarchy.installer`, `daemonarchy.desktop`, `daemonarchy.compatibility`, `daemonarchy.updates`, `daemonarchy.diagnostics`, `daemonarchy.verified-boot`.

Release admission must account for the complete pinned source and ports trees as
canonical Components with explicit ownership and variant-aware dependencies.
Catalog coverage and qualification of the selected native release closure are
separate results. Whole-tree build logs do not establish per-component acceptance.

Return or record a distinct failure when the required operation fails; absent
capabilities and missing evidence cannot be encoded as success. Changes to this
boundary require review of its consumers and acceptance coverage.
