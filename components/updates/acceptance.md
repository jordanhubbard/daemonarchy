# Compatible updates and recovery acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [tests/pkg-repo-dependencies.sh](../../tests/pkg-repo-dependencies.sh)
- [tests/package-repository.sh](../../tests/package-repository.sh)
- [tests/installed-checkouts.sh](../../tests/installed-checkouts.sh)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **ABI compatibility:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Recoverable transactions:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Exact optional sources:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
