# Daemonarchy project

## Goals

- **G1 — Install safely:** deliver the Omarchy desktop experience on FreeBSD with
  explicit disk selection, preserved unrelated data and verifiable completion.
- **G2 — Integrate the desktop:** provide coherent sessions, services, menus,
  artwork, native applications and supported networking/peripheral behavior.
- **G3 — Update recoverably:** coordinate packages, base, kernel and drivers with
  compatible identities, boot environments and demonstrable rollback.
- **G4 — Diagnose reliably:** provide console-approved remote access and bounded,
  private evidence that distinguishes transport loss, failed drivers and reboot.
- **G5 — Preserve trust:** verify boot, package and artifact identities while
  protecting signing credentials and existing firmware trust.
- **G6 — Release honestly:** bind published artifacts to exact inputs and scoped
  acceptance evidence, with explicit failures, exceptions and limitations.
- **G7 — Make progress useful and engaging:** deliver Winamp-inspired visuals,
  complete package dependency planning, safe parallel execution and a responsive
  graphical package manager.
- **G8 — Account for the complete operating system:** represent all selected
  `/usr/src` and `/usr/ports` inputs and build units as Literate AI Components,
  with explicit dependencies, configuration variants and per-component evidence.
  Preserve upstream source authority and contribution workflows.
- **G9 — Build and package substantially faster:** use the established component
  graph through Literate AI to improve native build and ISO packaging time with
  complete per-unit pkg provenance. Build-system replacement, including Bazel or
  Buck2, is permitted when correctness and measured end-to-end improvement pass.
  Select the executor from equivalent native measurements; wrapping opaque make
  targets in a new scheduler is not itself a performance result.

## Dependencies

The next release depends on a qualified Literate AI revision/wheel providing
first-class FreeBSD workers and retained native lifecycle/release evidence.
The framework owns that capability under FREEBSD-001; authority-only metadata
does not satisfy it. Runtime/build inputs
include upstream FreeBSD sources and ports, Omarchy, firmware and toolchains.
FreeBSD source and ports remain retained upstream implementations, but their
complete trees must be represented through canonical Component catalogs and
selected native locks; treating either tree as one opaque external input is
insufficient. The native build controller does not establish that integration.
The Daemonarchy-owned desktop and compatibility repositories remain separately
maintained source inputs. Their exact release identities and integration
contracts belong to this project's release plan; ambient neighboring checkouts
are not admitted build evidence.

## Completeness

The in-place Literate AI authority layer defines nine product goals, eight
Component contracts, interface ownership and acceptance mapping. Authority
validation, all eight contract locks and static skill checks pass. Existing source remains implementation
and release authority; it has not been relocated, regenerated or qualified as
fungible source. The automatic adoption plan reports `blocked-no-driver` for the
current shell-script build entrypoints, so its quarantine conversion was not
applied. Native retained-project execution and release enforcement require
separate demonstrated integration.

The current product release is 1.1.1. Its published artifact identity and actual
qualification scope remain in the [release record](docs/testing-1.1.1.md).
Product responsibilities and current acceptance coverage are mapped in
[the architecture](docs/architecture/design-traceability.md). G7's planner,
parallel installer, visualizers and new graphical manager remain planned work.
G8's complete source/ports Component coverage is also unfinished. Existing eight
product integration contracts and a whole-system source build are not a catalog
of every base build unit or ports origin. COMP-001 owns that additional work.
G9 is unfinished: the first native aggregate build is a baseline, not a
performance improvement or canonical per-unit Component execution result.

## Current work

The current directing goal is DEV-001: provide an operator-ready development
system using editable `/usr/src` and `/usr/ports` checkouts from the owned forks,
with build, incremental rebuild, test, package, ISO creation and installation
managed by Literate AI. Preserve the usable installed desktop while qualifying
new outputs in isolated workspaces. The parallel `/usr/daemonarchy` workspace
is now deployed on the operator workstation and native build host, with
independent source/ports checkouts and isolated output roots. The common
`litai-dev` target entrypoint remains unfinished. Ports PR #7 provides
reviewed original authority and two current native locks with the complete
installed Standard binding. The candidate wheel now validates both review
projects and all five source/ports locks on both native roles. Their receipts
remain missing and the active workspace selection is preserved. The subsequent
source prototype adds two support/bootstrap contracts for five source locks;
its installed native build-worker run has produced the selected compiled products
but has not completed acceptance. The first run reports 23 original passes and
one unauthorized root-required skip. The subsequent
[framework preview](verification/native-development-preview-ca604c00.json)
passes seven installed native SBOM checks and 62 source-controller checks;
its corrected native source run is in progress. The operator preview retains its earlier
three-source-lock selection. See the [source profile checkpoint](verification/native-source-profile.json).
Direct native make probes
compile the parser/utility and build/test/package the LZ4 port; these are
diagnostics, not admitted Component lifecycles. Unification takes priority over preserving old
build interfaces, while upstream pulls must remain practical. Existing make
targets form the initial execution bridge; Bazel is a candidate subject to native
timing and invalidation evidence. A designated cut-over follows equivalent
source/ports, package and ISO acceptance. The [workspace migration plan](docs/roadmap/native-workspace.md)
records this transition. PERF-001 establishes the source/ports graph,
executes literal Components and measures native ISO build/packaging improvement.
The [performance plan](docs/roadmap/build-performance.md)
owns its measurements and executor decision.

RELEASE-001 remains the broader release program: finish the existing backlog and
publish through the qualified Literate AI method. The planned minor release is
1.2.0, consistent with the existing early
network-debugging roadmap. The completion audit includes all open queue and
roadmap acceptance, not just implementation code or a worker proof. The
[completion ledger](docs/roadmap/release-1.2.0.md) expands those obligations and
defines the native/VM/physical worker and evidence model.

COMP-001 adds complete source/ports Component coverage to that release program.
The [component model](docs/roadmap/freebsd-components.md) defines full-tree
ownership, target/options variants, native dependency composition and evidence
states. Catalog coverage includes units outside the installed release selection;
native execution and acceptance apply to each explicitly selected closure.
PERF-001 owns actual native Component execution and measured build/packaging
acceleration. The existing make/poudriere execution is a baseline; replacement
executors and caching are eligible once their inputs and dependency semantics
are explicit and verified.


ADOPT-001 establishes the project-wide authority layer. ADOPT-002 remains open
for retained native execution, source/assets admission and release enforcement.
Use [the active queue](docs/roadmap/active-work.md) for stable work IDs, owners,
dependencies and acceptance checklists. [ROADMAP.md](ROADMAP.md) is the human
release/feature overview; it does not independently override completion status.

## Completed work

[CHANGELOG.md](CHANGELOG.md) records published history. The 1.1.1 release shipped
refreshed base/packages, diagnostics and installer fixes; native/VM results have
explicit artifact scope. The physical HP passed upgrade, rollback, desktop and
operator-confirmed application use. The MacBook's GPU/Wi-Fi failures and earlier
restart investigation remain open; a later SSH disconnect was verified not to
be a reboot. None of this is a new Literate AI execution receipt.
