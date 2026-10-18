---
namespace: daemonarchy
version: 1.0.0
display_name: Rescue and approved remote diagnostics
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.diagnostics
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
# Rescue and approved remote diagnostics

Goals: G4. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: Approval and revocation

Require console-approved client access. Pair/Unpair must revoke active access and stale generation state, and permit a new pairing. Never treat an ordinary SSH disconnect as task completion.

## Requirement: Bounded evidence

Collect bounded private kernel/system/process/device observations without reading console input, credentials or broad unsafe sysctl enumeration. Retain controller evidence and explicit transport-loss records.

## Requirement: Observation identity

Distinguish a new boot from an SSH/listener restart using target identity and retained evidence. Missing panic or event output does not identify the cause of a reset.

## Requirement: Cleanup and future transport

Finite diagnostic jobs must clean up only their owned state. Early loader/kernel network debugging remains future work with explicit wired-NIC, trust and native acceptance requirements.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
