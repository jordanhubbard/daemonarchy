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

Require console approval for a new agent. Preserve an installed-system hardware-debugging grant, approved keys, server identity and private evidence across reboot; resume safely without fresh confirmation or deleting stale state. Resumed background listeners refuse unknown keys. Explicit Unpair or interactive stop revokes active connections and the retained grant. Refresh runtime generations and verify listener identity before signaling a retained PID. Never treat an ordinary SSH disconnect as task completion.
Publish only grant, listener, authenticated connection, address and port status for the desktop. Update it after connection, disconnection, restart and revocation; never expose approved keys, host identity or private observations through this public view.
Keep the listener's exit-code-only status check for boot supervision, and provide a local privileged detailed status that explains missing approval, networking or listener state during hardware bring-up.

## Requirement: Bounded evidence

Passive collectors retain bounded private kernel/system/process/device observations without reading console input, credentials or broad unsafe sysctl enumeration. Retain controller evidence and explicit transport-loss records. Approved loader command input is a separate control channel; retained controller captures contain output, not typed input or pairing keys.

## Requirement: Observation identity

Distinguish a new boot from an SSH/listener restart using target identity and retained evidence. Missing panic or event output does not identify the cause of a reset.

## Requirement: Cleanup and wired boot transport

Finite diagnostic jobs clean up only their owned state. Provide an explicitly enabled wired UEFI loader console with authenticated, session-bound and sequenced input. Preserve ordinary loader variable inspection/update and boot commands, bounded private output retention, local console recovery and boot without an available peer. Reject forged, replayed, malformed and oversized input. Remove pairing key material from inspectable environment variables after activation and revoke it when disabled.

This product targets FreeBSD only. Qualify the actual FreeBSD EFI binary in a disposable UEFI VM and on the selected physical firmware/NICs. Firmware network availability and the transition to kernel networking are distinct evidence requirements; report any pre-driver gap rather than claiming continuous kernel debugging.

See [the public contract](interfaces/contract.md), [acceptance requirements](acceptance.md)
and [product traceability](../../docs/architecture/design-traceability.md).
