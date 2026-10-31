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

Daemonarchy is a FreeBSD-only product. Its OS Flavors and runtime release
qualification select FreeBSD; no Linux, macOS or Windows product qualification
is required. A build controller may run elsewhere without changing the target.
Independent portability gates in the parent framework are not product OS gates.

Wired UEFI loader remote console/control is an immediate next-release blocker
under DEBUG-001. Implementation proceeds while framework CI is pending.

The operator assigns **1.4 P0** to bidirectional network debugging from the
boot blocks and loader through a forced `mountroot>` prompt, early kernel
startup and panic under DEBUG-003 and
[issue #33](https://github.com/jordanhubbard/daemonarchy/issues/33). The
[1.4 plan](docs/roadmap/release-1.4.0.md) owns the scope;
<!-- release-sync: history -->
the [1.3.2 plan](docs/roadmap/release-1.3.2.md) retains historical design work.
<!-- /release-sync -->
The enabled plain-debug mode requires no SSH, new key or pairing. It must
support remote input as well as output at each claimed stage, bounded polling
in early/panic contexts and orderly native-NIC takeover. Preserve the
published 1.3.1 image, tags, feeds, signing material, source and build outputs;
no 1.4 implementation or hardware acceptance is claimed yet.

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
applied. The reviewed metadata-only `project adopt-original` flow now selects
original source authority in place, preserving all 272 tracked source entries at
its reviewed commit. Native retained-project execution and release enforcement
require separate demonstrated integration.

The current product release is 1.4.1, published October 31, 2026. Its published
artifact identity is recorded in [`release/current.json`](release/current.json)
and its actual qualification scope in the [release notes](docs/release-1.4.1.md);
the earlier 1.4.0 keeps its [notes](docs/release-1.4.0.md) and 1.1.1 keeps its [record](docs/testing-1.1.1.md).
Product responsibilities and current acceptance coverage are mapped in
[the architecture](docs/architecture/design-traceability.md). G7 remains unfinished:
pinned DAG/acquisition work has scoped native evidence, and a
[draft measured-dashboard candidate](https://github.com/jordanhubbard/daemonarchy/pull/21)
passes controller and native PTY checks. Complete planner integration, safe parallel
installation, physical display acceptance and the graphical manager remain open.
G8's complete source/ports Component coverage is also unfinished. Existing eight
product integration contracts and a whole-system source build are not a catalog
of every base build unit or ports origin. COMP-001 owns that additional work.
G9 is unfinished: the first native aggregate build is a baseline, not a
performance improvement or canonical per-unit Component execution result.

## Current work

INSTALL-PERF-001 (issue #134) is the first planned 1.4.1 development program. It
requires equivalent exact-image installer baselines on the MSI, MacBookPro16,1
and a VM, then at least a 10x total-time improvement on both physical machines.
The initial observer binds terminal diagnostics to exact image, package closure,
worker, storage, network and cache context; native measurements and the package
path changes remain open. PKG-001 retains exact catalogue, acquisition and safe
transaction ownership. A larger ISO, an unpinned ambient cache or parallel pkg
database writers cannot substitute for those acceptance boundaries.
PKG-002 (issue #142) self-hosts the installer's package closure for both
architectures; its first measurement tool is `scripts/package-mirror-plan.py`.
The carried queue items were audited on 2026-10-30
([release-1.4.1-audit.md](docs/roadmap/release-1.4.1-audit.md)): TESTISO-001 is closed, nine items
need the external framework, hardware or research work and moved to 1.5.0 by operator decision
([plan](docs/roadmap/release-1.5.0.md)).

VISUAL-SDK-001 (issue #139) extracts the installer's text and graphical
rendering, animation/effects, input and audio presentation surface into an
independently packaged, versioned SDK. Animation, visualizer and game content
loads through explicit trusted plugin manifests and a preemptible,
failure-isolated lifecycle; an ordinary non-installer host must consume the
same SDK. Installer progress, privileged operations and terminal outcomes remain
outside the SDK and cannot be changed or hidden by plugins.

GAME-001 (issue #137) adds approximately five or six playable classic-arcade
homages to the 1.4.1 installer, including a Space Invaders-style fixed shooter.
The games run inside the installer context through VISUAL-SDK-001 while
installation remains authoritative in the background. They may not hide prompts or results, weaken
diagnostics, consume installation input unexpectedly or materially regress the
INSTALL-PERF-001 target. Original assets and legally safe mechanics are required.

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
publish through the qualified Literate AI method. The next planned release
is 1.5.0 ([plan](docs/roadmap/release-1.5.0.md)); 1.4.0 and 1.4.1 are published ([1.4 plan](docs/roadmap/release-1.4.0.md)); 1.2.0 was never published,
and 1.3.1 followed 1.1.1. The completion audit includes all open queue and
roadmap acceptance, not just implementation code or a worker proof. The earlier
[1.2.0 completion ledger](docs/roadmap/release-1.2.0.md) expands those obligations and
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
for retained native execution, source/assets admission and release enforcement. The
controller now has a reviewed exact-wheel Standard binding with the existing
receipt contract preserved. The combined `e90cbadb` wheel passes full controller
regression, wheel qualification and installed FreeBSD/controller binding and
metadata-only original-adoption probes. Executable product profiles and native
lifecycle receipts remain open. See the
[combined checkpoint](verification/native-first-binding-integration-development.json)
and preceding [binding checkpoint](verification/standard-first-binding-development.json).
Use [the active queue](docs/roadmap/active-work.md) for stable work IDs, owners,
dependencies and acceptance checklists. [ROADMAP.md](ROADMAP.md) is the human
release/feature overview; it does not independently override completion status.

GPU-001 adds planned 1.4 glmark2 diagnostics and a Daemonarchy showcase, with
actual renderer/vendor/driver/API, FPS and frame-time evidence on physical
AMD, NVIDIA and Intel MacBook FreeBSD hardware. Software fallback does not
qualify acceleration. NET-002 separately traces installed-boot delays from
missing/disconnected Ethernet and plans bounded first-usable-interface DHCP
with serialized route/DNS publication and bounded offline boot, related to
installer NET-001. Both remain unimplemented and unqualified; see the
[1.4 plan](docs/roadmap/release-1.4.0.md) and acceptance rows A18/A19.
DEBUG-003 retains P0 priority.

## Completed work

[CHANGELOG.md](CHANGELOG.md) records published history. The 1.3.1 release shipped
MacBookPro16,1 graphics, T2 input and BCM4364 Wi-Fi support, retained
remote-debugging grants and a rotated package-signing key; see its
[release notes](docs/release-1.3.1.md). The earlier 1.1.1 release shipped
refreshed base/packages, diagnostics and installer fixes; native/VM results have
explicit artifact scope. The physical HP passed upgrade, rollback, desktop and
operator-confirmed application use. The MacBook's GPU/Wi-Fi failures and earlier
restart investigation remain open; a later SSH disconnect was verified not to
be a reboot. None of this is a new Literate AI execution receipt.
