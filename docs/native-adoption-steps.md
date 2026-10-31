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

## Framework main instead of 1.3.0

Framework main needs `contributions.roadmap_goal_manifest` in `literate.release.json` and a
reviewed Standard rebind (`litai project lifecycle rebind-standard`, plan then `--apply
--authorize-rebind`, which changes lifecycle and receipt-policy authority). The manifest
needs a `Release target:` line on each queue heading and every included goal checked off.
Do this as one operator-approved change; the 1.3.0 runtime rejects the manifest field.

## SRC-001: scheduling the controller run

A full native build is about 9,400 s (buildworld 7,931 s on 8 vCPU, 16 GiB, -j4 in the
previous baseline). madmax (32 cores, 184 GB) hosts mudflap at 16 vCPU and 48 GiB, so a
second 12 vCPU, 32 GiB, 160 GiB guest fits beside it and disk is no longer the constraint.
Recommended: a second VM, started nice'd with `-j4`, so it cannot delay the amd64 and
arm64 ISO builds on mudflap. If a second VM is not wanted, run on mudflap after both ISOs
are mastered. Register it as another LitAI worker (`litai worker add`, with its own
transport wrapper) before the run.
