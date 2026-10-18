# Verified boot and signing maintenance acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

## Existing candidate checks

- [secureboot/tests/test_maintenance.py](../../secureboot/tests/test_maintenance.py)
- [secureboot/tests/test_signing_guards.py](../../secureboot/tests/test_signing_guards.py)
- [secureboot/tests/check-runtime-log.py](../../secureboot/tests/check-runtime-log.py)
- [secureboot/tests/check-media-log.py](../../secureboot/tests/check-media-log.py)

Read each command's platform and privilege requirements before execution. The
complete declarations and external/native gaps are in [the acceptance inventory](../../verification/acceptance-inventory.json).

## Required scenarios

- **Exact trust closure:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Preserve signing boundaries:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Scoped acceptance:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
