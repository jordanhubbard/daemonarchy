---
namespace: daemonarchy
version: 1.0.0
display_name: Package DAG and parallel transactions
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.package-engine
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
# Package DAG and parallel transactions

Goals: G3, G7. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: Complete dependency plan

For every release selection, resolve all transitive dependencies to exact package identities, origins/flavors, hashes, repositories and download/installed sizes. Detect missing or changed catalogue inputs before writes.

## Requirement: Safe parallel work

Schedule independent ready packages with completed prerequisites and bounded resources. Coordinate database, file ownership, scripts, triggers and shared side effects; do not start competing uncontrolled pkg transactions.

## Requirement: Shared progress contract

Provide the same structured plan and measured events to installer ANSI visualizers and the graphical manager. Distinguish download, staging, commit, retry, failure and completion.

## Requirement: Failure and performance acceptance

Stop dependent work after failure and retain retry/recovery evidence. Demonstrate actual parallel installation and total-time improvements separately from parallel downloads. A pinned catalogue graph collector is implemented; native solver acceptance, transaction execution and parallel installation remain unfinished.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
