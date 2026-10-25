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
observed ratio and requires 4x for a compatible update and 10x for unchanged work.
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
