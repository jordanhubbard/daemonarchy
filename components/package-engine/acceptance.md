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

The [native resolution checker](../../scripts/native-package-plan.py) compares
pkg's imported package identities and dependency records and complete dry-run
proposals with the pinned graph. Its [controller checks](../../tests/native-package-plan.py)
cover missing/changed/extra proposals, repository attribution, changed imported
metadata, retained command failures, hung-child deadlines and owned interruption
cleanup. [The native procedure](../../docs/native-package-plan.md) uses an empty
private database and frozen local metadata; it grants no installation permission
or signed-repository/lifecycle acceptance.

The [signed snapshot checker](../../scripts/signed-package-snapshot.py) uses
native public-key catalogue import and fetch/checksum verification against pinned
metadata. Its [controller controls](../../tests/signed-package-snapshot.py)
cover frozen/allowlisted serving, unsafe inputs, offline read-only replay and
exact archive inventory. [The native procedure](../../docs/signed-package-snapshot.md)
requires real wrong-key, altered-signature and corrupt-payload refusal as well as
positive observations. It grants no dependency-plan, installation or lifecycle
acceptance, and historical release fixtures cannot qualify final 1.2 inputs.

## Required scenarios

- **Complete dependency plan:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Safe parallel work:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Shared progress contract:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
- **Failure and performance acceptance:** demonstrate the stated requirement on its actual supported
  target, and retain a negative/failure case where applicable.
