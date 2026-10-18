# Compatible updates and recovery public boundary

Capability: `daemonarchy.updates`, contract version 1.0.0.

This is a behavioral integration boundary over the retained implementation, not
a newly implemented RPC or JSON API. Consumers must preserve the requirements
in [the Component](../component.md) and use the existing commands/files described
in [HACKING.md](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md).

Dependencies: `daemonarchy.package-engine`, `daemonarchy.verified-boot`.

Return or record a distinct failure when the required operation fails; absent
capabilities and missing evidence cannot be encoded as success. Changes to this
boundary require review of its consumers and acceptance coverage.
