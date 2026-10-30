# Curated installer baselines

Each `NAME-development.json` is a `daemonarchy/install-baseline@1` record built
by `scripts/install-trace-baseline.py build` from the installer trace kept beside
it as `NAME.trace.jsonl.xz`. The record's `trace.sha256` is the digest of the
decompressed trace, and `tests/install-trace-baseline.py` checks that they match.
Records say how far the run got (`completeness`) and never grant acceptance.

```
xz -dc NAME.trace.jsonl.xz | sha256sum        # equals trace.sha256 in the record
python3 scripts/install-trace-baseline.py compare BASELINE.json CANDIDATE.json
python3 scripts/install-trace-baseline.py compare BASELINE.json NEW-TRACE.jsonl --fail-on-regression
```

| Record | What it is |
| --- | --- |
| `daemon-fetch-serial-20261030` | Package fetch of 304 packages (890 MiB) from `pkg.FreeBSD.org` with one worker, on daemon.local over 1 GbE: 493 s, 1.81 MiB/s. A fetch benchmark, not an install. |
| `daemon-fetch-8workers-20261030` | The same set with eight workers: 91 s, 9.78 MiB/s, mean concurrency 6.0. |
| `msi-1.4.1-candidate-prefetch-20261030` | The MSI Raider's first run with the trace. It stopped at the package fetch because an upstream package had been dropped, so it covers disk, base, loader, config and the start of the fetch only (base-system extraction 8.6 s, catalogue update 13.9 s, about 1 MiB/s to the mirror). |

A complete, equivalent-link install baseline on the MSI and the MacBook is still
owed (INSTALL-PERF-001); these records are the instrument and the first real data.
