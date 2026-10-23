# Desktop experience and native tools acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [tests/graphics-startup.sh](../../tests/graphics-startup.sh)
- [tests/qemu-desktop.py](../../tests/qemu-desktop.py)
- [tests/installed-desktop.sh](../../tests/installed-desktop.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **Actual graphics readiness:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Coherent user environment:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable. For remote
  debugging, inspect the actual bar and panel after boot, connection,
  disconnect and Unpair; exercise the local privileged controls without
  exposing private pairing state.
- **Shared visual identity:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
