# Rescue and approved remote diagnostics acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [tests/remote-debug-session.sh](../../tests/remote-debug-session.sh)
- [tests/remote-debug-reboot.sh](../../tests/remote-debug-reboot.sh)
- [tests/remote-debug-observe.sh](../../tests/remote-debug-observe.sh)
- [tests/remote-debug-capture.py](../../tests/remote-debug-capture.py)
- [tests/remote-debug-events.py](../../tests/remote-debug-events.py)
- [tests/rescue-console.sh](../../tests/rescue-console.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **Approval and revocation:** test first approval, legacy listener adoption,
  shutdown/stale-state resumption with stable host pin and existing agent key,
  unknown-key refusal, reused-PID/generation safety and explicit revocation.
  Check that the public status changes on connection, disconnection and Unpair
  without disclosing keys, host identity or private diagnostic output.
  Check that local detailed status distinguishes a running listener, a retained
  grant with a stopped listener, and an explicitly revoked grant while preserving
  the exit-code-only status used by boot supervision.
  Qualify actual physical reboot separately from the native process fixture.
- **Bounded evidence:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Observation identity:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Cleanup and wired boot transport:** retain actual FreeBSD EFI build identities,
  VM and physical NIC evidence for output, variable inspection/update and boot
  control. Verify forged/replayed/malformed/oversized input refusal, retransmission
  without duplicate commands, bounded queues, peer loss/reconnection, missing NIC,
  local recovery and revocation. Pairing keys and typed input must not enter
  inspectable loader variables or retained output logs. Document the exact
  firmware-to-kernel coverage gap; a packet unit test cannot close this scenario.
- **1.3.2 network bootloader debugging:** execute plain-mode activation without
  SSH or keys, remote commands and variable get/set/unset, disk kernel/module
  boot, direct UDP kernel/module transfer and boot, TFTP downloads, and downloaded
  Lua using real loader APIs. Verify actual artifacts, incomplete/corrupt transfers,
  bounded allocation/retries, ABI/dependency errors, script errors, cancellation,
  peer/NIC loss, local recovery and disk preservation. Boot/sequence validation
  provides correlation and duplicate suppression, not authentication. Retain the
  existing authenticated mode's separate regression requirements above.
- **1.3.2 early-kernel connection:** require real packets after firmware exit and
  before normal PCI/NIC attachment with exact products, NIC and boot identity.
  Retain deliberate pre-driver panic and hard-reset captures, successful continued
  boot, bounded panic polling, loss counters, stale/malformed message controls and
  safe native-driver takeover. Qualify the separate diagnostic image and actual
  MSI built-in-NIC startup capture. Use the complete
  [1.3.2 acceptance matrix](../../docs/roadmap/release-1.3.2.md#acceptance-matrix).
  Descriptor checks, a preloaded NIC module and controller-only fixtures do not
  close this scenario or establish the MSI reset's cause. USB report acceptance
  remains firmware inventory persistence; kernel capture is retained on the host.
