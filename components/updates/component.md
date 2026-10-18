---
namespace: daemonarchy
version: 1.0.0
display_name: Compatible updates and recovery
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.updates
    version: 1.0.0
    interface:
      uri: interfaces/contract.md
      pin: null
requires:
  - requirement_id: package-engine
    capability: daemonarchy.package-engine
    version_range: ">=1,<2"
    dependency_kind: runtime
    optional: false
    constraints: []
  - requirement_id: verified-boot
    capability: daemonarchy.verified-boot
    version_range: ">=1,<2"
    dependency_kind: runtime
    optional: false
    constraints: []
authoring_inputs:
  - kind: specification-to-source-skill
    uri: skills/specification-to-source/retained-boundaries/SKILL.md
workflow_definition:
  uri: workflows/retained.md
routing_policy:
  uri: routing/retained.json
flavor_slots: []
entrypoints: []
acceptance_contracts:
  - kind: acceptance-contract
    uri: acceptance.md
source_dependencies: []
---
# Compatible updates and recovery

Goals: G3. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: ABI compatibility

Check kernel and userland compatibility before adopting a candidate package feed. A package update does not upgrade the FreeBSD base or make old drivers compatible.

## Requirement: Recoverable transactions

Preserve the original boot environment and user package selections. Qualify update, rollback and return on the actual target; metadata creation alone is not rollback evidence.

## Requirement: Exact optional sources

Verify signed checkout inputs, source identity, depth-one self-contained objects and ownership. Source offered by the release must match its selected base/ports inputs.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
