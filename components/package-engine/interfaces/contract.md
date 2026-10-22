# Package DAG and parallel transactions public boundary

Capability: `daemonarchy.package-engine`, contract version 1.0.0.

This is a behavioral integration boundary over the retained implementation.
Consumers must preserve the requirements
in [the Component](../component.md) and use the existing commands/files described
in [HACKING.md](https://github.com/jordanhubbard/daemonarchy/blob/main/HACKING.md).

Dependencies: none.

The signed-snapshot command retains its serial
`daemonarchy/signed-package-snapshot-inputs@1` and
`daemonarchy/signed-package-snapshot@1` contracts. Explicit
`daemonarchy/signed-package-snapshot-inputs@2` inputs additionally select
`fetch_workers` (one to sixteen) and optional `fetch_batch_packages` (one to 128,
default 32). All existing trust, native tool, repository, selection, size and
timeout fields remain required. The fetch timeout is common to all scheduled
fetch batches; authentication precedes that phase. The result uses
`daemonarchy/signed-package-snapshot@2` and reports actual concurrency and its
ordered progress journal. It keeps installation and lifecycle authority false.

`daemonarchy/package-progress-event@1` journal entries bind the exact input pin,
repository database pin, ordered sequence and elapsed time. Download events
distinguish started, verified, failed and cancelled batches. Completed acquisition
requires the atomically published final snapshot result bound to that journal.
Counts and bytes describe verified archives, including seed replay;
they do not claim network throughput or installation progress. Installer and GUI
consumers must retain those phase boundaries and represent waiting honestly.
Events alone are not package verification or transaction authorization.

Return or record a distinct failure when the required operation fails; absent
capabilities and missing evidence cannot be encoded as success. Changes to this
boundary require review of its consumers and acceptance coverage.
