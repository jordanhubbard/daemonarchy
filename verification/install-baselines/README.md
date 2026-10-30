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

| `msi-full-install-pre-parallel-fetch-20261030` | **The first complete real install** (exit 0, every phase through `finish`): the MSI Raider, wired gigabit, CUDA selected, before the parallel fetch. **Single machine, single run.** 2,977 s in all: fetch 2,075 s (824 archives, 3,721 MiB at 1.79 MiB/s, mean concurrency 0.74), package install 152 s, CUDA 691 s, integrity check 31 s, base 12.6 s. A concurrency below 1 means about a quarter of the fetch window had nothing transferring (roughly 0.65 s of per-archive overhead). |

To compare the next run with it, label the new trace with its context:

```
python3 scripts/install-trace-baseline.py compare \
    verification/install-baselines/msi-full-install-pre-parallel-fetch-20261030-development.json NEW-TRACE.jsonl \
    --candidate-context kind=physical "machine=MSI Raider 18 HX AI A2XWIG" "storage=NVMe 954 GB behind Intel VMD" \
    "link=wired gigabit rge0" cache_mode=network workers=16 --fail-on-regression
```

An equivalent-link baseline on the MacBook is still owed (INSTALL-PERF-001); the MSI
record is one machine and one run, not a statistical baseline.
