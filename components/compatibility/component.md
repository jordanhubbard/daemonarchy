---
namespace: daemonarchy
version: 1.0.0
display_name: Omarchy FreeBSD integration
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.compatibility
    version: 1.0.0
    interface:
      uri: interfaces/contract.md
      pin: null
requires: []
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
# Omarchy FreeBSD integration

Goals: G2. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: Native service semantics

Adapt Omarchy service, session, power and package operations to FreeBSD with defined status and failure behavior; do not silently declare unsupported operations successful.

## Requirement: Hardware capability reporting

Expose actual attached wireless, Bluetooth and graphics capabilities. A detected PCI device without a driver is not a working interface; missing native support remains explicit.

## Requirement: External source custody

Retain the omarchy-freebsd repository as independently maintained source. Admit exact source/package identities at integration time rather than importing an ambient sibling checkout.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
