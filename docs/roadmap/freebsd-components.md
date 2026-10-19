# Complete FreeBSD source and ports Component coverage

- **Status:** active
- **Owning queue item:** [COMP-001](active-work.md#comp-001-model-complete-freebsd-source-and-ports-trees-as-components)
- **Completion / archival evidence:** pending canonical full-tree coverage, native lifecycle and exact release receipts

The operator requires all of `/usr/src` and all of `/usr/ports` to be represented
as Literate AI Components. G8 in [PROJECT.md](https://github.com/jordanhubbard/daemonarchy/blob/main/PROJECT.md)
owns this requirement. Two opaque checkout inputs or two whole-tree build
wrappers cannot satisfy it. Preserve the upstream implementations and normal
Git contribution workflow while putting their complete inventories, selected
dependencies and evidence under canonical Component authority.

## Boundaries and composition

| Area | Component boundary and required relationships |
| --- | --- |
| Ports | Each real `category/origin` is represented, including origins not installed in the release. Native metadata supplies build, run, library, fetch, extraction, patch and test dependencies. |
| Port variants | Architecture, OS version/ABI, FLAVOR, OPTIONS and toolchain selections qualify the origin's lock and outputs. A single origin can produce multiple packages; an installed package list is not the complete ports catalog. |
| Base userland | Native buildable programs, libraries and shared build units have Component contracts. Source directory layout helps discovery; native make metadata and reviewed mappings determine actual boundaries and dependencies. |
| Kernel | Core, architecture/platform support, drivers and modules have explicit ownership and relationships. The configured kernel composes a target selection; shared compilation/link constraints do not imply every driver can be built independently. |
| Loader and boot | Loader variants, boot libraries and platform support compose the boot products and their trust/symbol inputs. They retain their actual pre-kernel execution and testing constraints. |
| Shared inputs | Build rules, scripts, generators, tests, configuration, patches, distinfo, vendored sources, firmware references, assets, documentation and repository metadata all have authoritative owners. Consumers reference shared inputs without copying their authority. |
| System products | World, kernel, base/source packages, installer sets and images compose the selected Components. Their aggregate results cannot silently become independent per-component acceptance. |

No tracked input may disappear because it lacks a Makefile, is imported/vendor
code, or is not selected for the current release. Vendored subprojects and
overlapping build inputs need reviewed ownership. Source identity, license,
content/mode/symlink treatment and external downloads belong to admission; a
directory label or Git object inventory alone is not a Component qualification.

Every compositional unit must produce a versioned pkg artifact with complete
source/build provenance and typed dependency information. Source/build packages
account for units linked into larger artifacts; runtime installation may select
the composed kernel or system packages. Canonical Component registration or an
upstream pkgbase grouping does not by itself satisfy this invariant. It remains
unimplemented for the complete trees.

## Native dependencies and execution

Resolve conditional dependency edges for the exact target, options and source
revision on an appropriate native worker. Text searches over Makefiles cannot
establish a complete graph. Host/bootstrap tools, generated inputs, shared kernel
linking and build cycles need explicit semantics; do not conceal a cycle by
omitting an edge or advertise all source builds as an automatically parallel DAG.

The ports catalog and each selected release closure serve different purposes.
The entire catalog must be visible, but a release builds/admits the exact
required closure rather than implicitly compiling every port. Unsupported,
unselected, unbuilt and untested entries remain visible with truthful states.
The selected package graph also supplies PKG-001's installer/UI planning; its
runtime installation dependencies do not replace the broader build dependency
graph.

Preserve FreeBSD source, target/ABI, dependency and installation semantics.
Make/pkgbase and ports/poudriere are the baseline, but replacing the build
executor with Bazel, Buck2 or another suitable system is authorized. Literate AI
must bind their actions, inputs, output products, source/resolved BOMs, tests,
independent acceptance and packaging through its actual retained lifecycle.
The source-build controller is preparation for that binding, not a substitute
receipt or a second Component protocol. Conversion that retires or regenerates
upstream implementation is not implied by catalog admission.

## Coverage and evidence gates

Maintain separate counts and identities for:

1. Discovered build units/origins and every selected tracked source/support input.
2. Registered canonical Component contracts and complete input ownership.
3. Admitted source/variant inputs and selected current locks/dependency closure.
4. Actual native build and test results, including explicit skips and failures.
5. Independent acceptance, packaged products and exact release admission.

Discovery does not imply registration, and registration does not imply a build
or acceptance pass. Require zero unowned inputs and explicit shared-consumer
relationships for both pinned trees. Addition, deletion, rename or changed source,
options, toolchain, dependency or artifact must invalidate the relevant state.
Coverage must fail closed on incomplete enumeration, ambiguous ownership,
unresolved dependencies or stale bindings.

Large catalogs need bounded deterministic enumeration, useful queries and clear
per-component status; emitting thousands of placeholder specifications is not
evidence that native dependency or behavioral contracts are complete. Reuse the
framework's canonical catalog/Component/Flavor/lock owners instead of claiming
that a custom inventory JSON is equivalent to those contracts.

## Execution order and current state

SRC-001 has supplied a pinned native build controller and started its first
GENERIC build. Its eleven controller checks passed on macOS, GitHub CI and
FreeBSD. That proves controller behavior only. The current eight Daemonarchy
contracts still describe product integration, not full source/ports membership.
No complete base/ports Component catalog, current per-unit native receipt or
full-tree coverage pass is claimed.

Next action: establish complete pinned-tree coverage and reviewed build-unit
boundaries, then connect a real multi-component native fixture to the canonical
catalog, variant locks and retained lifecycle. Grow that path to complete tree
registration and the exact release closure without weakening ADOPT-002 or
RELEASE-001. Framework catalog/lifecycle gaps are tracked in [issue #74](https://github.com/jordanhubbard/literate-ai/issues/74), building on retained lifecycle issue #22.
