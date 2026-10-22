# Installation and target configuration acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [tests/installer-progress.py](../../tests/installer-progress.py) — controller and native Python/PTY progress observation; does not install a system.
- [tests/disk-layout.sh](../../tests/disk-layout.sh)
- [tests/shared-disk.sh](../../tests/shared-disk.sh)
- [tests/install-integrity.sh](../../tests/install-integrity.sh)
- [tests/boot-environment-mounts.sh](../../tests/boot-environment-mounts.sh)
- [tests/installed-desktop.sh](../../tests/installed-desktop.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **Explicit storage intent:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Verified completion:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Boot environment isolation:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Useful progress:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
