# ADOPT-002 and SRC-001: native adoption steps for the operator

Written 2026-10-31 against the installed framework runtime (litai 1.3.0, c345e652) and
framework main (1.4.0 development, c093657e8). It records what is already in place and the
exact steps still needed. Nothing here is claimed done: the retained native receipt
(`verification/current.json`) does not exist, and every step below that executes anything
needs the operator's authorization.

## Already in place (local, reversible)

- LitAI worker `mudflap-freebsd` (FreeBSD 16.0-CURRENT, amd64, 16 CPUs, 48 GiB) is
  registered in the private catalog (`litai worker list`). It reaches the VM through the
  `mudflap-ssh` transport wrapper (jump host, port and key stay out of the catalog).
  `litai worker test`, `probe` and `align --skip-model` pass.
- A side-by-side framework main runtime exists at `~/daemonarchy-framework-main-runtime`;
  nothing global was upgraded.
- `litai verify` fails only on the human-attested `authority-reviewed` marker in
  `design-traceability.md` (record the value `litai project documentation-review` prints,
  after reviewing the documentation), then on the missing native receipt.

## Why `.literate/legacy-lift-shift.json` is not regenerated

`litai project retained-harness readmit` is the legacy conversion path and reports
`retained_harness.metadata_missing`. The original-source route does not use it; see
[the queue entry](roadmap/active-work.md#adopt-002-qualify-retained-native-execution-and-release-enforcement).
Original-source projects use a retained-project manifest and profile.

## ADOPT-002 steps (retained native execution)

1. **Bootstrap mudflap's toolchain.** `python3` is not on PATH (only `python3.12`) and
   `gmake` is missing. Run `litai worker align --worker-id mudflap-freebsd` (add `--apply`
   to install the declared commands) and re-check `--skip-model` alignment.
2. **Author the profile** (`literate-ai/retained-project-profile@1`) outside the tree, then
   review it as authored source: target, worker identity (mudflap-freebsd), toolchain,
   dependency, test-policy and release-policy identities, the `tools` list, the complete
   action list and the package inventory. Each action has an id, a stage (acquire, stage,
   generate, build, test, docs, accept), a tool, argv, exact `requires` edges, its exact
   `inventory`, its `outputs` and a bounded timeout. Start from the five-owner prototype in
   [native-source-profile.json](../verification/native-source-profile.json) (source fork PR 4);
   it ended with `retained.tests.skip-not-authorized: truncate.deallocate`, so the
   test-policy must name every original case, its owning test action and any permitted skip
   reason exactly.
3. **Author the manifest** (`literate-ai/retained-project-manifest@1`, a streaming
   binary-capable inventory of the exact source tree) for the selected revision.
4. **Plan, read only:**
   `litai build --project . --retained-project MANIFEST --retained-project-profile PROFILE --retained-project-plan`
   Review the returned plan identity and refusals.
5. **Execute under explicit authorization** (the operator, not an agent, grants it):
   `litai build --project . --retained-project MANIFEST --retained-project-profile PROFILE --authorize-retained-project sha256:REVIEWED_PLAN_ID --allow-host-execution --worker mudflap-freebsd`
   then the same with `test` for the complete lifecycle (build, original tests, docs and
   independent acceptance). Preserve failed evidence; do not overwrite it.
6. `litai verify` should then report the receipt; renew `verification/` records. The signed
   boot bundle and feed signing remain out of scope for the framework run and stay with the
   operator's key custody.

Open until these run: privileged cleanup, protected signer binding, artifact custody and
release enforcement (the ADOPT-002 acceptance text), and framework issues 74 and 93 for
COMP-001.

## Runtime: 1.3.1 now, 1.4.0 for the authoritative evidence

The released 1.3.1 runtime (`~/daemonarchy-framework-1.3.1-runtime/venv/bin/litai`, built from tag `v1.3.1`) is used
for rehearsals: authoring, read-only plans, worker setup. Framework main (1.4.0 development) is built side by side
at `~/daemonarchy-framework-main-runtime` for read-only plans only. The authoritative native runs wait for
framework 1.4.0 (COMP-001 needs its catalog scale, per-unit packages and tree-aware transport), because the move
changes the receipt policy (see the next section).

## The Literate AI 1.4 move (prepared, not applied)

Apply sequence, per repository, once framework 1.4.0 is released and the operator authorizes it:

1. Install the 1.4.0 runtime side by side; record its identity.
2. `litai project lifecycle rebind-standard` (plan), review the plan identity and the changed fields, then
   `--apply --authorize-rebind` with that plan. This changes `lifecycle_driver` (framework distribution and policy
   identities) and the receipt policy.
3. Land the release-goal manifest (`contributions.roadmap_goal_manifest`, `docs/roadmap/release-goals.json`) and the
   `Release target:` lines on queue headings (the prepared draft change); the 1.3.x runtime rejects that field, so
   this lands only with the 1.4.0 runtime.
4. `litai verify`, rerun the repository's tests, then record the human `authority-reviewed` marker.
5. Rerun every native run whose receipt matters (see below).

What the rebind invalidates: the plan reports `evidence_after_apply`: `accepted_source_membership` and
`test_receipt` both become `stale-until-rebuild`. Any native receipt, retained-project admission or plan
authorization produced on 1.3.x is therefore not carried over, and an authorization identity is bound to the
reviewed plan, which changes with the framework identity. The framework's own code ties them together: the lifecycle driver identity (which embeds the framework
distribution identity) is written into the run's derivation (`cli/rebuild.py` records `lifecycle_driver_identity`) and a
run is refused when the project's current driver identity differs from the recorded one (v1.3.1 `cli/rebuild.py`, the
`lifecycle_driver.identity != driver.identity` checks). Run the multi-hour native builds after the move, not
before it.

## SRC-001: scheduling the controller run

A full native build is about 9,400 s (buildworld 7,931 s on 8 vCPU, 16 GiB, -j4 in the
previous baseline). madmax (32 cores, 184 GB) hosts mudflap at 16 vCPU and 48 GiB, so a
second 12 vCPU, 32 GiB, 160 GiB guest fits beside it and disk is no longer the constraint.
Recommended: a second VM, started nice'd with `-j4`, so it cannot delay the amd64 and
arm64 ISO builds on mudflap. If a second VM is not wanted, run on mudflap after both ISOs
are mastered. Register it as another LitAI worker (`litai worker add`, with its own
transport wrapper) before the run.
