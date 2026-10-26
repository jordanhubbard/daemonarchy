# Release measurements and pending QA

Issue [#39](https://github.com/jordanhubbard/daemonarchy/issues/39) requires
observed clean, unchanged, compatible-update, changed-input, package-only and
ISO-only runs. `scripts/release-measurements.py` validates their measurement
records. It does not turn a command exit or a historical log into acceptance.

Run one already-authorized command under an isolated observation directory:

```sh
python3 scripts/release-measurements.py --observe /absolute/new/job \
  --timeout-seconds 300 --command litai build --help
```

The supervisor retains stdout, stderr, exit status, log digests and monotonic
elapsed nanoseconds, UTC start/end, command identity and terminal observation
identity, including command failure and timeout. `--context exact-context.json`
binds available action key, input, selection, worker pool, worker identity and ID. It refuses to
replace an existing job directory. Raw observations always have `complete:false`;
only admitted action outputs and complete acceptance can supply the final run.
Do not put private command arguments or raw logs in committed authority.

A `daemonarchy/release-measurement@1` run declares `scenario`, `baseline_kind`
(`normalized` or `historical-observation`), content identities for the selection,
measurement scope, gate scope, worker pool and retained observation, nonzero
`wall_time_ns`, `complete:true`, and one row per action. Each row names a unique
`action_id` and `action_key`, kind, disposition, reason, input/output/receipt
identities, worker ID, elapsed nanoseconds and actual cache read/write bytes.
Required gates are build, package, sign, ISO, native, fresh-install, upgrade and
rollback, each with an exact receipt identity. A package download cache's bytes
are not automatically compiler/action-cache bytes.

```sh
python3 scripts/release-measurements.py candidate.json --baseline clean.json --observations-root /retained/candidate
```

Comparison requires normalized runs with the same complete product obligations,
gate scope and worker pool. The measurement-scope identity describes equivalent
output and acceptance obligations while the exact input selection may change.
Historical 1.1.1/1.3.1 observations stay separate. The comparison computes the
observed ratio and reports a numeric threshold comparison of 4x for compatible
updates and 10x for unchanged work. Structural results always keep `target_met`
null: unsigned observations cannot establish a speedup acceptance gate.
Missing measurements, receipts or reasons refuse validation. With
`--observations-root`, executed/requalified rows must name `observation_path`,
`terminal_receipt_identity` and `command_identity`; the verifier reopens command
exit, start/end, action/selection/pool/worker context and both exact log files. Unchanged and
package/ISO-only runs cannot hide compilation; compatible updates cannot compile
Chromium/CEF. This structural validator does not authenticate receipts or establish
that the supplied scope really is equivalent; LitAI's admitted action records and
release receipt verifier remain those authorities.

`scripts/release-qa-plan.py` prepares five pending native/VM/physical obligations
from an existing LitAI release plan and its qualified-release-files manifest. It
uses the existing framework APIs to re-open current policy and verify local
artifact bytes, roles, revision, version, size and digest. It derives actual
GitHub release download URLs, requests `PACKAGE_QA_MODE=final-rc`, and excludes all
local package-cache overrides. An authenticated-receipt policy is mandatory for
readiness; the current 1.3.1 policy lacks that binding and remains a blocker.
Invoke using the exact selected framework runtime, without changing its pin:

```sh
python3 scripts/release-qa-plan.py --project /absolute/selected/project \
  --release-plan plan.json --qualified-files qualified-files.json \
  --required-role installer-iso --required-role signed-feed
```

Artifact roles must be the complete roles from the release contract, not the
example subset above. The optional `--receipt-root` names an existing owned native supervisor evidence
directory. The planner selects its not-yet-created `bhyve-work` child as `WORK`,
refusing an existing child and leaving retained supervisor files intact. It never
creates the work child. The plan never claims acceptance, signs or publishes.
Before final QA, acquire and verify public assets on the allocated native worker;
retain native signature/package checks, fresh installation and installed boot,
upgrade, rollback and the physical matrix against the same manifest. Public
availability and current authenticated receipts remain release gates. Signing
and publication run once in dependency order through `litai release publish`;
independent public verification uses `litai release verify-published`.

No clean-build normalization, actual distributed/native run, final public install,
or 1.4 speedup is claimed by these controller contract tests.

Measurement scope now includes the actual `worker_pool` descriptor (catalogue and
admission-policy identities, each worker's identity, physical parent, allocation,
capabilities, slots and CPU/RAM/disk/network budget) and `gate_scope` (exact gate,
policy and target requirements, with explicit waivers). Their identities are
computed from those contents; an arbitrary reused pool label cannot hide resource
or gate changes. Fresh `worker_observations` bind catalogue, worker, physical parent,
observation and parent-binding receipt identities to available resources.
`execution_mode:distributed` requires executed/requalified actions on at least two
physical parent identities. Two guests with different worker IDs on one physical
parent fail that check. Terminal command evidence must bind those same identities.

These structural bindings still need authentication. The coordinator can call
`verify_worker_bindings` with its independently pinned LitAI evidence plan, trust
policy, resolver, locators, trusted state and expected current project authority.
It verifies the actual pool/observation subject plus catalogue-binding, observed
parent-host and resource-capacity checks through the existing signed-evidence API.
A caller's serialized success flag is never a substitute for this verification.
No trusted physical-parent receipts or real two-machine qualification have yet
been produced by this work. Historical retries, the whole-goal elapsed duration
and hardware/ISO waivers remain ineligible normalized speed baselines.

Read-only historical recovery accepts the retained traced-build checkpoint format:

```sh
python3 scripts/release-measurements.py --recover-historical \
  verification/native-traced-build-quiet-result.json \
  --release-source d63d77f4eb3cc29e16510f7bdec73602e27c2844
```

The [recovered stage observations](../verification/release-1.4-baseline-recovery-development.json)
retain actual reported elapsed times and exits from source `7d93dff0`, including
its failed `sets` stage. They have no recovered started/terminal UTC pairs or
proven equivalent pool/gate scope. This source differs from the 1.3.1 release
gate's `d63d77f4`; these records are historical and explicitly comparison-ineligible.
They do not supply a 1.3.1 normalized baseline. The retained 1.3.1 physical
[release decision](../verification/macbook-release-decision-1.3.1.json) also records
its original final-ISO waiver and missing exact physical artifact hashes. Actual
1.3.1 per-stage supervisor records still need read-only recovery from retained
worker evidence when those workers are available. Never substitute the complete
operator-goal duration, retries or waivers for equivalent clean-build timing.

Every action duration must fit within the complete run elapsed time. Optional
`attempts` are numbered contiguously with distinct request identities, actual
terminal status/exit, command and terminal receipt identities, worker, observation
path, elapsed time and cache costs. Executed/requalified action totals must include
all attempts, including failed, interrupted and timeout attempts. Every attempt
worker must belong to the actual measured pool, and all attempt parent hosts count
in the declared execution mode. The last attempt
must succeed; earlier successful attempts cannot be silently retried. Observation
reopening checks every listed attempt and both retained logs. Reuse has no executed
attempts and retains its separate cache-admission authority.

Attempt lists alone cannot prove that an earlier attempt was omitted. The
coordinator's `compare_authenticated` API therefore requires independent verifier
configurations for both measurements. `verify_measurement` binds the complete
measurement bytes to signed LitAI evidence under current project authority and
requires trusted complete-attempt-inventory, complete-action-inventory,
current-gates, timing, cache-accounting and physical worker/resource checks.
Authenticated comparisons require attempt inventories for every action and only
then set `target_met`. No authenticated full-run measurements have been produced;
synthetic validator tests establish neither inventory completeness nor performance.

## 1.3.1 stage-timing baseline and selected targets

The [stage-timing baseline](../verification/release-1.3.1-stage-baseline-development.json)
names the required world, kernel, package-fetch, package-build, signing and ISO
stages, plus release sets. It binds the exact 1.3.1 selection (product `cdeb3434`,
source `d63d77f4`, ports `b7857842`, ISO `ef5b1bec`) and the SHA-256 of every
retained source record it cites.

Read-only recovery from the retained madmax release-builder guests produced the
actual 1.3.1 supervisor records. They are under
[`verification/release-1.3.1-stage-records/`](../verification/release-1.3.1-stage-records/),
and each is validated with:

```sh
python3 scripts/release-measurements.py --recover-supervisor \
  verification/release-1.3.1-stage-records/source-progress.tsv \
  --release-source d63d77f4eb3cc29e16510f7bdec73602e27c2844
```

The recovery pairs each UTC `start` line with its `complete` or `exit=N` line.
It retains unpaired and unparsed lines, and always reports
`historical-observation` with its normalization blockers.

| Stage | Recovered 1.3.1 timing | Selection |
| --- | --- | --- |
| World | 2,058 s, exit 0, `-j16` | exact source `d63d77f4` |
| Kernel | 240 s, exit 0, GENERIC | exact source |
| Release sets | 444 s, exit 0, base/kernel/lib32 verified | exact source |
| ISO assembly | 426 s, exit 0; earlier failed attempts of 45 s and 1 s | exact product/ports/source; output SHA-256 `ef5b1bec` |

World, kernel and sets ran in a 16-vCPU, 64 GiB guest on a shared 32-thread host.
They were an independent qualification build, and the shipped ISO used separately
imported release sets. Package build has only these records:
- two failed madmax bulks on the earlier ports tree `7e417dae`, of 4,209 s and
  32,817 s;
- a third attempt whose terminal record stays in an unreachable guest;
- an exact-selection fast race of 85,485 s that built five ports incrementally
  and did not produce the published feed.

Package fetch and signing were not recovered. The validator blocks every recovered
stage from normalized comparison, because worker pool, resource budget and gate
scope are not bound by identity and no authenticated receipts exist. These are the
best available 1.3.1 stage references, not a normalized baseline. Older retained
records from other selections stay listed and comparison-ineligible.

The same record fixes the numeric targets before 1.4 implementation:
- Speed: an unchanged rerun at most 0.1x and a compatible Chromium/CEF update at
  most 0.25x of an equivalent clean 1.4 run.
- Compilations: none in an unchanged rerun, and no Chromium or CEF compilation
  in a compatible update.
- Rebuild scope and reuse: no rebuild outside the changed closure, and every
  reuse-eligible action a cache hit when unchanged.
- No-regression guards: package-only, ISO-only and two-physical-worker runs no
  slower than the matching clean stage or run.

All retries and failed attempts count. These targets apply to the equivalent
clean 1.4 reference, not to the ineligible 1.3.1 observations.
