---
namespace: daemonarchy
version: 1.0.0
display_name: Verified boot and signing maintenance
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.verified-boot
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
# Verified boot and signing maintenance

Goals: G5. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: Exact trust closure

Bind selected loader, kernel and protected modules to matching manifests and certificate policy. Reject altered or untrusted protected bytes under enforcement.

## Requirement: Preserve signing boundaries

Keep private keys on authorized signing hosts. Publish only public trust material and signed artifacts. Preserve existing firmware trust entries during enrollment.

## Requirement: Scoped acceptance

Qualify enforced boot, disabled-enforcement behavior, rejection, signed maintenance and recovery separately on actual artifacts. A signature or isolated fixture does not establish a working installed desktop.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
