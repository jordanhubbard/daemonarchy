---
namespace: daemonarchy
version: 1.0.0
display_name: Installation and target configuration
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.installer
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
  - requirement_id: desktop
    capability: daemonarchy.desktop
    version_range: ">=1,<2"
    dependency_kind: runtime
    optional: false
    constraints: []
  - requirement_id: diagnostics
    capability: daemonarchy.diagnostics
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
# Installation and target configuration

Goals: G1, G7. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: Explicit storage intent

Before target writes, present the selected disk or partition, intended layout and data-preservation boundary. Reject invalid or undersized selections before mutation.

## Requirement: Verified completion

Report installation success only after required payloads, dependency/file checks, account ownership, caches and durable target-pool completion pass. Keep rescue evidence on failure.

## Requirement: Boot environment isolation

Create the original ZFS root with canmount=noauto and explicitly mount it for installation. Inactive roots must not cover the selected environment or its devices.

## Requirement: Useful progress

Expose actual stages, byte/package totals, waiting and errors independently of ANSI animation. The planned visualizer consumes this state and preserves readable plain output.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
