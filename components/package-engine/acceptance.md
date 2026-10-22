# Package DAG and parallel transactions acceptance

Acceptance binds exact input/source identities, test command, worker/OS, artifact
hash, result and limitations. Historical results are evidence only for their
recorded scope; these requirements are not a current execution receipt.

The [pinned catalogue collector](../../scripts/package-dag.py) has
[controller checks](../../tests/package-dag.py) for complete transitive closure,
shared dependencies, per-selection totals, catalogue mutation, malformed input,
ABI/OSVERSION refusal, repository conflicts, cycles and preserved output.
[Its input and evidence contract](../../docs/package-dag.md) distinguishes these
graphs from native solver acceptance and installation permission. Keep PKG-001
open until actual release catalogues, native resolution, the scheduler, integrity
and failure/performance cases are exercised on native FreeBSD.

## Required scenarios

- **Complete dependency plan:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Safe parallel work:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Shared progress contract:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Failure and performance acceptance:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
