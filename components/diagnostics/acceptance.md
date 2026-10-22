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
