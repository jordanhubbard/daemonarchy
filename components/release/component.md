---
namespace: daemonarchy
version: 1.0.0
display_name: Release assembly and qualification
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.release
    version: 1.0.0
    interface:
      uri: interfaces/contract.md
      pin: null
requires:
  - requirement_id: installer
    capability: daemonarchy.installer
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
  - requirement_id: compatibility
    capability: daemonarchy.compatibility
    version_range: ">=1,<2"
    dependency_kind: runtime
    optional: false
    constraints: []
  - requirement_id: updates
    capability: daemonarchy.updates
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
# Release assembly and qualification

Goals: G6, G8, G9. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: Coherent immutable inputs

Record exact source, ports, desktop, compatibility, package catalogue, firmware and toolchain inputs. Keep kernel, world, jail and external drivers on compatible selections.

## Requirement: Complete source and ports Component coverage

Represent the complete pinned source and ports trees through canonical Component contracts and input ownership, including shared support inputs and unselected origins. Bind target/options variants and native dependencies explicitly. Reject missing or ambiguous ownership. Keep catalog, admission, selected locks, build, test and independent acceptance states distinct; qualify the exact selected release closure.

## Requirement: Artifact-bound evidence

Bind test results to exact image, source, target/firmware mode and scope. Earlier-image or component results cannot silently qualify a rebuilt final ISO.

## Requirement: Per-unit packages and measured build improvement

Produce a versioned pkg artifact for every compositional unit with exact source/build provenance and typed dependencies. Qualify source/build products separately from composed runtime installation. Use the Component graph through the native lifecycle and demonstrate materially faster end-to-end build and ISO packaging against the same-target baseline. Replacing make with another build system is permitted; correct invalidation, output and acceptance remain required.

## Requirement: Publication consistency

Publish only the approved commit and verified bytes, with matching checksums, feed selection, public certificates, documentation and changelog. Keep published tags immutable.

## Requirement: Honest release decisions

Record passed, failed, unrun and explicitly waived acceptance independently. Authorization is not a test pass, and known hardware/security limits remain visible.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
