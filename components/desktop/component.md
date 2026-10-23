---
namespace: daemonarchy
version: 1.0.0
display_name: Desktop experience and native tools
profiles: ["retained-contract"]
sample: false
provides:
  - name: daemonarchy.desktop
    version: 1.0.0
    interface:
      uri: interfaces/contract.md
      pin: null
requires:
  - requirement_id: compatibility
    capability: daemonarchy.compatibility
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
# Desktop experience and native tools

Goals: G2, G7. This is a retained product contract, not an
independently executable or regeneratively qualified Component. Existing source
and the native acceptance inventory remain authoritative for implementation status.

## Requirement: Actual graphics readiness

Permit graphical startup only with an attached active driver and the required DRM nodes. Module-load success alone is insufficient; desktop acceptance requires actual rendering and login.

## Requirement: Coherent user environment

Install the selected session, theme, menus, user defaults and native FreeBSD tools together. Preserve user customizations during updates.
While a remote debugging grant is active, show its current listener and authenticated-agent state in the menu bar, including address and port and a local administrator path to Resume or Unpair. The desktop consumes only the diagnostics Component's public status view.

## Requirement: Shared visual identity

Apply the Omarchy/Daemonarchy retro identity consistently. The planned graphical package manager uses the shared transaction plan and accurate progress; reduced motion remains available.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
