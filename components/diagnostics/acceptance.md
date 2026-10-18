# Rescue and approved remote diagnostics acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [tests/remote-debug-session.sh](../../tests/remote-debug-session.sh)
- [tests/remote-debug-observe.sh](../../tests/remote-debug-observe.sh)
- [tests/remote-debug-capture.py](../../tests/remote-debug-capture.py)
- [tests/remote-debug-events.py](../../tests/remote-debug-events.py)
- [tests/rescue-console.sh](../../tests/rescue-console.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **Approval and revocation:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Bounded evidence:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Observation identity:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Cleanup and future transport:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
