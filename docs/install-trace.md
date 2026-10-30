# Installer trace

Every installation writes a microsecond-resolution trace of its timed events so
the install can be performance-tuned and read by a person or an LLM. It records
**what happened and how long it took**: phases, storage and filesystem
operations, base-system extraction, package downloads and unpacks, device
events, and network, disk and CPU activity. It never records answers,
credentials, network names, addresses, paths or command lines.

- **Where:** `/tmp/daemonarchy-install-trace.jsonl` while the installer runs;
  `/var/db/daemonarchy/install/install-trace.jsonl` (mode 0600) on the installed
  system, written before the pool is exported, including after a failure.
- **Format:** one JSON object per line, schema `daemonarchy/install-trace@1`.
- **Reading it:** `python3 scripts/install-trace-summary.py TRACE [--json]`
  reports phases, the slowest operations, downloads (bytes, time, throughput,
  concurrency), unpack timings, per-phase network/disk/CPU totals, network
  probe timings and device events.

## Common fields

| Field | Meaning |
| --- | --- |
| `t_us` | Microseconds since the Unix epoch (wall clock). Sort by this. |
| `since_start_us` | Microseconds since the installer started. |
| `event` | The event kind, below. |
| `phase` | The installer phase when the line was written (`disk`, `base`, `loader`, `config`, `fetch`, `install`, `user`, `checkouts`, `cuda`, `finish`). Lines from helper processes (`source` = `pkg-events` or `install-trace-sampler`) omit it; place them by `t_us`. |

## Events

| Event | Written by | Fields |
| --- | --- | --- |
| `trace_start` | installer | `schema`, `image_version`, `kernel`, `arch` |
| `phase_begin`, `phase_end` | installer | `name`; `phase_end` adds `dur_us` |
| `step` | installer | `name` (a stage marker inside a phase) |
| `op_begin`, `op_end` | installer | `op` (a fixed label such as `zpool_create`, `zfs_datasets`, `extract_base`, `newfs_efi`, `pkg_fetch_all`, `pkg_install_all`, `package_integrity`, `cuda_setup`); `op_end` adds `status` and `dur_us` |
| `fetch_attempt` | installer | `attempt` |
| `download` | pkg-events or parallel-fetch | `name` (archive), `bytes`, `dur_us`: one per finished package archive. From the parallel fetch it also has `worker`, and `dur_us` is the time since that worker's previous archive finished (or its batch started), so the sum over a worker is its busy time |
| `fetch_pool_begin`, `fetch_pool_end` | parallel-fetch | `workers`, `packages`, `pending`; the end adds `complete`, `missing`, `bytes`, `dur_us` and `mean_concurrency` (summed archive time over wall time: how many connections were really busy) |
| `fetch_batch` | parallel-fetch | one `pkg fetch` process: `worker`, `packages`, `status`, `dur_us`, and for a failure `error` (`http`, `timeout`, `checksum`, `connection` or `other`) |
| `fetch_retry` | parallel-fetch | an archive queued again: `name`, `attempt`, `delay_ms` (exponential backoff, so no fixed sleeps) |
| `pkg_event` | pkg-events | `type` (pkg's event name, for example `INFO_EXTRACT`), `name` (package): install and unpack begin/finish events; progress ticks are not traced |
| `net_probe` | sampler | `host`, `dns_us`, `connect_us`, `tls_us`, `first_byte_us`, `status` (or `error`): run once before the package fetch against `pkg.FreeBSD.org` and `github.com` |
| `net_sample` | sampler | `name` (interface), cumulative `ibytes`, `obytes`, `ipkts`, `opkts`, `ierrs`, `oerrs`, per-interval `d_*`, `interval_us`; only interfaces that moved |
| `disk_sample` | sampler | `name` (device), `reads`, `writes`, `read_kib`, `write_kib`, `qlen`, `svc_s`, `busy_s`, per-interval `d_*`; only devices that moved |
| `cpu_sample` | sampler | `user`, `nice`, `system`, `interrupt`, `idle` (percent over the interval), `free_mib`, `load1` |
| `device_event` | sampler | `kind` (`attach`, `detach`, `notify`), `device`, or `system`/`subsystem`/`type` for notifications such as link up and down |
| `exit` | installer | `status`, `dur_us` (whole installation) |

The sampler runs once a second (`DAEMONARCHY_TRACE_INTERVAL` changes it) from
the start of the installer until it exits. Counters are cumulative since boot
as FreeBSD reports them; use the `d_*` fields for rates.

## What it answers

- Where the time goes by phase, and which single operation dominates a phase.
- Download time per archive, aggregate throughput and mean concurrency, so the
  effect of parallel fetch (PKG-001, PKG-002) is measured against the same trace.
- Whether the link, the disk or the CPU was the bottleneck in each phase:
  compare `net_sample`, `disk_sample` and `cpu_sample` totals with the phase
  duration.
- DNS, connect, TLS and first-byte delay to each package host before the
  transfer starts.
- When devices attached or detached and when the link changed state.

## Rules for adding events

Record a fixed label, a count, a size or a time. Never a command line, a path,
an answer, an address or a name the user chose. `trace_event` quotes and strips
values, but the rule is the safeguard. Use `traced LABEL command...` for an
external command and `trace_begin LABEL` / `trace_end LABEL` around a shell
function that relies on `set -e`.
