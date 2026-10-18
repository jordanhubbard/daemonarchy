# Package DAG and parallel transactions acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

No implementation or executable acceptance suite exists yet. Keep PKG-001
open until the release DAG, scheduler, integrity and failure/performance cases
are implemented and exercised on native FreeBSD.

## Required scenarios

- **Complete dependency plan:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Safe parallel work:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Shared progress contract:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Failure and performance acceptance:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
